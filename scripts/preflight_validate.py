"""Scenario preflight validation orchestrator."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from cmo_config import format_config_setup_hint, resolve_db_dir
from preflight_luacheck import install_luacheck_local, luacheck_exe_path
from cmo_db import format_database_layout_message, open_db, resolve_source_db
from preflight_checks import *
from preflight_constants import *
from preflight_parse import *

_LUACHECK_TOOLS_EXE = luacheck_exe_path()


def _resolve_luacheck_bin():
    """PATH, then repo tools/luacheck/ (preflight_luacheck.py default)."""
    for name in ("luacheck", "luacheck.exe"):
        found = shutil.which(name)
        if found:
            return found
    if _LUACHECK_TOOLS_EXE.is_file():
        return str(_LUACHECK_TOOLS_EXE)
    return None


def _try_install_luacheck():
    """Repo-local install when not on PATH. Returns a status line or None on skip/failure."""
    if os.environ.get("CMO_SKIP_LUACHECK_INSTALL"):
        return None
    if sys.platform != "win32":
        return None
    try:
        install_luacheck_local(quiet=True)
    except OSError as exc:
        return f"Lua static analysis: local install failed ({exc})."
    if _LUACHECK_TOOLS_EXE.is_file():
        return "Lua static analysis: installed luacheck locally (tools/luacheck/)."
    return "Lua static analysis: local install failed (download incomplete)."


def _ensure_luacheck_bin():
    """PATH or tools/luacheck/; on Windows, download locally if neither (no PATH changes)."""
    found = _resolve_luacheck_bin()
    if found:
        return found, []
    install_note = _try_install_luacheck()
    notes = [install_note] if install_note else []
    return _resolve_luacheck_bin(), notes


def _run_luacheck(scenario_path):
    """Run luacheck for static Lua preflight."""
    luacheck_bin, install_notes = _ensure_luacheck_bin()
    if not luacheck_bin:
        warnings = [
            n
            for n in install_notes
            if n and "failed" in n.lower()
        ]
        if not warnings:
            warnings = [
                "Lua static analysis: luacheck not found (install on PATH, or "
                "python scripts/preflight_luacheck.py for tools/luacheck/; "
                "CMO_SKIP_LUACHECK_INSTALL=1 disables local auto-download on Windows)."
            ]
        return {"errors": [], "warnings": warnings, "ok": []}

    # luacheck 1.x does not expand '*' in --globals (a name like 'ScenEdit_*' is
    # taken literally), so the CMO API was never actually whitelisted. Use
    # --ignore <code>/<var-pattern> (Lua patterns) for the API prefixes instead,
    # and whitelist the single 'cmo' bootstrap global by exact name. The trailing
    # '--' is required: without it the --globals/--ignore list swallows the file
    # path, leaving luacheck with no file to check (critical exit, reported as a
    # bogus "luacheck failed with errors").
    cmd = [
        luacheck_bin,
        "--codes",
        "--ranges",
        "--no-color",
        "--globals",
        "cmo",
        "--ignore",
        "113/ScenEdit_.*",
        "113/VP_.*",
        "113/World_.*",
        "113/Tool_.*",
        "--",
        scenario_path,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except Exception as exc:
        return {
            "errors": [],
            "warnings": [f"Lua static analysis: failed to run luacheck: {exc}"],
            "ok": [],
        }

    output_lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    ok_notes = [n for n in install_notes if n and "installed" in n.lower()]
    if proc.returncode == 0:
        ok = ["OK: Lua static analysis (luacheck) passed."]
        ok.extend(ok_notes)
        return {"errors": [], "warnings": [], "ok": ok}
    if proc.returncode == 1:
        return {
            "errors": [],
            "warnings": [f"Lua static analysis: {ln}" for ln in output_lines]
            or ["Lua static analysis: luacheck warnings found."],
            "ok": ok_notes,
        }
    return {
        "errors": [f"Lua static analysis: {ln}" for ln in output_lines]
        or ["Lua static analysis: luacheck failed with errors."],
        "warnings": [],
        "ok": ok_notes,
    }


def validate_scenario_air_loadouts(
    scenario_path,
    series=None,
    version=None,
    db_path=None,
):
    path = Path(scenario_path)
    if not path.exists():
        return {"errors": [f"Scenario file not found: {scenario_path}"], "warnings": [], "ok": []}
    lint_report = _run_luacheck(str(path))

    if series and version and not db_path:
        source_path = resolve_source_db(series, version)
        if not source_path:
            return {
                "errors": [
                    f"Source database not found for {series} {version} in {resolve_db_dir()}. "
                    "Place the matching .db3 file or fix cmo_config.ini.\n"
                    + format_database_layout_message()
                    + "\n"
                    + format_config_setup_hint()
                ],
                "warnings": [],
                "ok": [],
            }

    content = load_scenario_lua_content(path)
    mission_map = _parse_scenario_missions(content)
    mission_zones = _parse_mission_zone_map(content)
    assignments = _extract_air_assignments(content)

    direct_pattern = re.compile(
        r"ScenEdit_AddUnit\s*\(\s*\{[^}]*type\s*=\s*'Air'[^}]*dbid\s*=\s*(\d+)[^}]*loadoutid\s*=\s*(\d+)[^}]*\}",
        re.IGNORECASE | re.DOTALL,
    )
    helper_pattern = re.compile(
        r"add_air_unit_checked\s*\(\s*'[^']*'\s*,\s*[^,]+,\s*(\d+)\s*,\s*[^,]+,\s*(\d+|nil)\s*,",
        re.IGNORECASE,
    )
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\([^,]+,\s*[^,]+,\s*\d+\s*,\s*(\d+)\s*,\s*(\d+)\s*,",
        re.IGNORECASE,
    )

    pairs = []
    for match in direct_pattern.finditer(content):
        pairs.append((int(match.group(1)), int(match.group(2))))
    for match in helper_pattern.finditer(content):
        loadout_id = match.group(2)
        if loadout_id.lower() == "nil":
            continue
        pairs.append((int(match.group(1)), int(loadout_id)))
    for match in wing_pattern.finditer(content):
        pairs.append((int(match.group(1)), int(match.group(2))))

    seen = set()
    unique_pairs = []
    for pair in pairs:
        if pair not in seen:
            unique_pairs.append(pair)
            seen.add(pair)

    if not unique_pairs:
        return {
            "errors": lint_report["errors"],
            "warnings": lint_report["warnings"]
            + [f"No air dbid/loadoutid pairs found in {scenario_path}"],
            "ok": lint_report["ok"],
        }

    db = open_db(db_path=db_path, series=series, version=version)
    cursor = db.cursor

    errors = list(lint_report["errors"])
    warnings = list(lint_report["warnings"])
    ok = list(lint_report["ok"]) + [f"Validation database: {db.path}"]

    wrap_errors, wrap_warnings, wrap_ok = _validate_wrapper_colon_syntax(content)
    errors.extend(wrap_errors)
    warnings.extend(wrap_warnings)
    ok.extend(wrap_ok)

    side_errors, side_warnings, side_ok = _validate_sides_created_before_use(content)
    errors.extend(side_errors)
    warnings.extend(side_warnings)
    ok.extend(side_ok)

    rp_errors, rp_warnings, rp_ok = _validate_reference_points(content)
    errors.extend(rp_errors)
    warnings.extend(rp_warnings)
    ok.extend(rp_ok)

    for aircraft_id, loadout_id in unique_pairs:
        aircraft_sv = _pick_series_version(db, "DataAircraft", aircraft_id, series, version)
        if not aircraft_sv:
            errors.append(
                f"Aircraft DBID {aircraft_id} not found (series={series or '*'}, version={version or '*'})"
            )
            continue
        a_series, a_version = aircraft_sv

        loadout_sv = _pick_series_version(
            db, "DataLoadout", loadout_id, series or a_series, version or a_version
        )
        if not loadout_sv:
            errors.append(
                f"Loadout ID {loadout_id} not found (series={series or a_series}, version={version or a_version})"
            )
            continue
        l_series, l_version = loadout_sv

        strict_ok = _is_aircraft_loadout_compatible(
            db, aircraft_id, loadout_id, series or a_series, version or a_version
        )
        if not strict_ok:
            errors.append(
                f"Incompatible pair: Aircraft DBID {aircraft_id} cannot use Loadout ID {loadout_id} "
                f"(series={series or a_series}, version={version or a_version})"
            )
            continue

        ok.append(
            f"OK: Aircraft {aircraft_id} -> Loadout {loadout_id} "
            f"(aircraft {a_series}/{a_version}, loadout {l_series}/{l_version})"
        )

    checked_mission_fit = set()
    for side, aircraft_id, loadout_id, mission_name, _escort_flag in assignments:
        if not mission_name or aircraft_id == 0:
            continue
        fit_key = (aircraft_id, loadout_id, mission_name)
        if fit_key in checked_mission_fit:
            continue
        checked_mission_fit.add(fit_key)

        aircraft_sv = _pick_series_version(db, "DataAircraft", aircraft_id, series, version)
        if not aircraft_sv:
            continue
        a_series, a_version = aircraft_sv

        loadout_query = "SELECT Name FROM DataLoadout WHERE ID = ?"
        loadout_params = [loadout_id]
        loadout_query, loadout_params = db.append_meta_filters(loadout_query, loadout_params)
        loadout_name_row = cursor.execute(loadout_query, loadout_params).fetchone()
        if not loadout_name_row:
            continue
        mission_role = _infer_mission_role(mission_name, mission_map)
        loadout_role_set = _loadout_roles(loadout_name_row[0])
        if mission_role == "strike" and _escort_flag is True:
            fit_ok = "aaw" in loadout_role_set or "sead" in loadout_role_set
            reason = None if fit_ok else "strike escort slot requires A/A or SEAD-capable loadout"
        else:
            fit_ok, reason = _mission_loadout_fit(mission_role, loadout_role_set)
        if fit_ok:
            ok.append(
                f"OK: Mission fit {mission_name} ({mission_role}) <- Aircraft {aircraft_id} / Loadout {loadout_id} ({', '.join(sorted(loadout_role_set))})"
            )
        else:
            errors.append(
                f"Mission/loadout mismatch: mission '{mission_name}' ({mission_role}) with Aircraft {aircraft_id} / Loadout {loadout_id} ({loadout_name_row[0]}): {reason}"
            )

    pack_errors, pack_warnings = _validate_bomber_and_sead_escort_packages(
        db, assignments, mission_map, series, version
    )
    errors.extend(pack_errors)
    warnings.extend(pack_warnings)

    escort_errors, escort_ok = _validate_strike_mission_escort_assignments(
        content, mission_map, assignments
    )
    errors.extend(escort_errors)
    ok.extend(escort_ok)

    sead_errors, sead_warnings, sead_ok = _validate_sead_mission_design(
        content, mission_map, mission_zones, assignments, db, series, version
    )
    errors.extend(sead_errors)
    warnings.extend(sead_warnings)
    ok.extend(sead_ok)

    csg_errors, csg_warnings, csg_ok = _validate_carrier_strike_groups(
        content, db, series, version
    )
    errors.extend(csg_errors)
    warnings.extend(csg_warnings)
    ok.extend(csg_ok)

    scenario_year = _parse_scenario_year(content)
    ships = _parse_naval_placements(content)
    geo_units = _parse_all_geo_placements(content)

    water_errors, water_warnings, water_ok = _validate_unit_geo_placement(geo_units)
    errors.extend(water_errors)
    warnings.extend(water_warnings)
    ok.extend(water_ok)

    patrol_errors, patrol_warnings, patrol_ok = _validate_patrol_zone_proximity(
        content, mission_map, ships
    )
    errors.extend(patrol_errors)
    warnings.extend(patrol_warnings)
    ok.extend(patrol_ok)

    op_errors, op_warnings, op_ok = _validate_operator_country_oob(
        content, assignments, ships, db, series, version
    )
    errors.extend(op_errors)
    warnings.extend(op_warnings)
    ok.extend(op_ok)

    nat_errors, nat_warnings, nat_ok = _validate_declared_nationality(
        content, db, series, version
    )
    errors.extend(nat_errors)
    warnings.extend(nat_warnings)
    ok.extend(nat_ok)

    civ_errors, civ_warnings, civ_ok = _validate_civilian_flight_paths(content)
    errors.extend(civ_errors)
    warnings.extend(civ_warnings)
    ok.extend(civ_ok)

    host_errors, host_warnings, host_ok = _validate_air_host_capacity(
        content, db, ships, series, version
    )
    errors.extend(host_errors)
    warnings.extend(host_warnings)
    ok.extend(host_ok)

    assign_errors, assign_warnings, assign_ok = _validate_unit_mission_assignments(
        content, mission_map
    )
    errors.extend(assign_errors)
    warnings.extend(assign_warnings)
    ok.extend(assign_ok)

    nuc_errors, nuc_warnings, nuc_ok = _validate_no_nuclear_weapons(
        content, unique_pairs, ships, db, series, version
    )
    errors.extend(nuc_errors)
    warnings.extend(nuc_warnings)
    ok.extend(nuc_ok)

    f35_errors, f35_warnings, f35_ok = _validate_f35_carrier_assignments(
        content, db, series, version
    )
    errors.extend(f35_errors)
    warnings.extend(f35_warnings)
    ok.extend(f35_ok)

    era_errors, era_warnings, era_ok = _validate_era_appropriate_oob(
        scenario_year, assignments, ships, db, series, version
    )
    errors.extend(era_errors)
    warnings.extend(era_warnings)
    ok.extend(era_ok)

    mun_errors, mun_warnings, mun_ok = _validate_modern_strike_munitions(
        scenario_year, assignments, mission_map, db, series, version
    )
    errors.extend(mun_errors)
    warnings.extend(mun_warnings)
    ok.extend(mun_ok)

    aar_errors, aar_warnings, aar_ok = _validate_aar_for_bomber_strikes(
        content, assignments, mission_map, db, series, version
    )
    errors.extend(aar_errors)
    warnings.extend(aar_warnings)
    ok.extend(aar_ok)

    refuel_errors, refuel_warnings, refuel_ok = _validate_refuel_doctrine_sanity(
        content, assignments, mission_map, db, series, version
    )
    errors.extend(refuel_errors)
    warnings.extend(refuel_warnings)
    ok.extend(refuel_ok)

    naval_errors, naval_warnings, naval_ok = _validate_naval_strike_assignment(
        content, ships, mission_map, db, series, version
    )
    errors.extend(naval_errors)
    warnings.extend(naval_warnings)
    ok.extend(naval_ok)

    naval_time_errors, naval_time_warnings, naval_time_ok = _validate_naval_strike_launch_timing(
        content, mission_map, ships
    )
    errors.extend(naval_time_errors)
    warnings.extend(naval_time_warnings)
    ok.extend(naval_time_ok)

    date_errors, date_warnings, date_ok = _validate_scenario_date_consistency(content)
    errors.extend(date_errors)
    warnings.extend(date_warnings)
    ok.extend(date_ok)

    tot_errors, tot_warnings, tot_ok = _validate_strike_tot_synchronization(
        content, mission_map
    )
    errors.extend(tot_errors)
    warnings.extend(tot_warnings)
    ok.extend(tot_ok)

    reach_errors, reach_warnings, reach_ok = _validate_strike_tot_reachability(
        content, mission_map, ships, assignments, db, series, version
    )
    errors.extend(reach_errors)
    warnings.extend(reach_warnings)
    ok.extend(reach_ok)

    patrol_warnings, patrol_ok = _validate_early_patrol_support_launches(content, mission_map)
    warnings.extend(patrol_warnings)
    ok.extend(patrol_ok)

    ship_strike_assigns = _parse_ship_strike_assignments(content, mission_map)
    fp_errors, fp_warnings, fp_ok = _validate_strike_flight_profile_and_timing(
        content,
        assignments,
        mission_map,
        ships,
        ship_strike_assigns,
        db,
        series,
        version,
    )
    errors.extend(fp_errors)
    warnings.extend(fp_warnings)
    ok.extend(fp_ok)

    grp_errors, grp_warnings, grp_ok = _validate_strike_flight_package_grouping(
        content, mission_map
    )
    errors.extend(grp_errors)
    warnings.extend(grp_warnings)
    ok.extend(grp_ok)

    esc_cov_errors, esc_cov_warnings, esc_cov_ok = _validate_strike_escort_coverage(
        content, mission_map
    )
    errors.extend(esc_cov_errors)
    warnings.extend(esc_cov_warnings)
    ok.extend(esc_cov_ok)

    sead_time_errors, sead_time_warnings, sead_time_ok = _validate_sead_strike_launch_timing(
        content, mission_map
    )
    errors.extend(sead_time_errors)
    warnings.extend(sead_time_warnings)
    ok.extend(sead_time_ok)

    isr_sead_errors, isr_sead_warnings, isr_sead_ok = _validate_isr_before_sead(content)
    errors.extend(isr_sead_errors)
    warnings.extend(isr_sead_warnings)
    ok.extend(isr_sead_ok)

    db.close()
    return {"errors": errors, "warnings": warnings, "ok": ok}

