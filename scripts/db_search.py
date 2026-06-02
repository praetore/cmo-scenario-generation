"""Search CMO databases and run scenario preflight validation."""

import argparse
import re
import sys
from pathlib import Path

from cmo_config import format_config_setup_hint, resolve_db_dir
from cmo_db import (
    format_database_layout_message,
    fts_match_query,
    master_has_fts,
    open_db,
    resolve_source_db,
)
from scenario_checks import *
from scenario_constants import *
from scenario_lua import *
from db_unit_queries import get_loadouts, get_unit_weapons
from scenario_report import empty_report, extend_report, run_check

SEARCH_TABLES = [
    "DataAircraft",
    "DataShip",
    "DataSubmarine",
    "DataFacility",
    "DataWeapon",
    "DataGroundUnit",
]


def search_db(
    search_term,
    db_series=None,
    db_version=None,
    limit=10,
    search_id=False,
    db_path=None,
    force_master=False,
    prefer_source=False,
):
    db = open_db(
        db_path=db_path,
        series=db_series,
        version=db_version,
        prefer_source=prefer_source,
        force_master=force_master,
    )
    cursor = db.cursor
    results = []

    for table in SEARCH_TABLES:
        cols = f"ID, Name, {db.meta_select()}, OperatorCountry"
        if table == "DataAircraft":
            cols += ", Category, RunwayLengthCode"
        else:
            cols += ", 0 as Category, 0 as RunwayLengthCode"

        params = []
        if search_id:
            try:
                params = [int(search_term)]
            except ValueError:
                params = [search_term]
            query = f"SELECT {cols}, '{table}' as Type FROM {table} WHERE ID = ?"
        elif db.master and not search_id and master_has_fts(cursor, table):
            match_query = fts_match_query(search_term)
            if not match_query:
                db.close()
                return []
            query = (
                f"SELECT {cols}, '{table}' as Type FROM {table} "
                f"WHERE rowid IN (SELECT rowid FROM fts_{table} WHERE Name MATCH ?)"
            )
            params = [match_query]
        else:
            query = f"SELECT {cols}, '{table}' as Type FROM {table} WHERE Name LIKE ?"
            params = [f"%{search_term}%"]

        query, params = db.append_meta_filters(query, params)
        if not search_id:
            if db.master:
                query += " ORDER BY db_version DESC"
            query += f" LIMIT {limit}"

        try:
            cursor.execute(query, params)
            results.extend(cursor.fetchall())
        except Exception:
            continue

    db.close()
    return results

def validate_scenario_air_loadouts(
    scenario_path,
    series=None,
    version=None,
    db_path=None,
    force_master=False,
    prefer_source=True,
):
    path = Path(scenario_path)
    if not path.exists():
        return {"errors": [f"Scenario file not found: {scenario_path}"], "warnings": [], "ok": []}

    if prefer_source and series and version and not db_path and not force_master:
        source_path = resolve_source_db(series, version)
        if not source_path:
            return {
                "errors": [
                    f"Source database not found for {series} {version} in {resolve_db_dir()}. "
                    "Place the matching .db3 file, fix cmo_config.ini, or use --master.\n"
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
            "errors": [],
            "warnings": [f"No air dbid/loadoutid pairs found in {scenario_path}"],
            "ok": [],
        }

    db = open_db(
        db_path=db_path,
        series=series,
        version=version,
        prefer_source=prefer_source,
        force_master=force_master,
    )
    cursor = db.cursor

    errors = []
    warnings = []
    ok = [f"Validation database: {db.path}"]

    wrap_errors, wrap_warnings, wrap_ok = _validate_wrapper_colon_syntax(content)
    errors.extend(wrap_errors)
    warnings.extend(wrap_warnings)
    ok.extend(wrap_ok)

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
            if db.master:
                series_only_ok = _is_aircraft_loadout_compatible(
                    db, aircraft_id, loadout_id, series or a_series, None
                )
                if series_only_ok:
                    warnings.append(
                        f"Aircraft {aircraft_id} + Loadout {loadout_id} compatible in series {series or a_series}, "
                        f"but not in requested version {version or a_version}"
                    )
                else:
                    errors.append(
                        f"Incompatible pair: Aircraft DBID {aircraft_id} cannot use Loadout ID {loadout_id} "
                        f"(series={series or a_series}, version={version or a_version})"
                    )
                    continue
            else:
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

    sead_time_errors, sead_time_warnings, sead_time_ok = _validate_sead_strike_launch_timing(
        content, mission_map
    )
    errors.extend(sead_time_errors)
    warnings.extend(sead_time_warnings)
    ok.extend(sead_time_ok)

    db.close()
    return {"errors": errors, "warnings": warnings, "ok": ok}

def _db_mode_args(args):
    prefer_source = bool(args.series and args.version and not args.master and not args.db)
    return {
        "db_path": args.db,
        "force_master": args.master,
        "prefer_source": prefer_source,
    }

def main():
    parser = argparse.ArgumentParser(description="Search and validate against CMO databases")
    parser.add_argument("term", nargs="?", help="The search term or ID")
    parser.add_argument("--series", help="Filter by DB series (DB3K or CWDB)")
    parser.add_argument("--version", help="Filter by DB version (e.g., 515)")
    parser.add_argument("--limit", type=int, default=5, help="Limit results per type")
    parser.add_argument("--id", action="store_true", help="Search by ID instead of name")
    parser.add_argument("--loadouts", help="Show loadouts/weapon config for a specific Unit ID")
    parser.add_argument("--weapons", help="Show magazines and mounts for a specific Unit ID")
    parser.add_argument(
        "--type",
        help="Unit type for --loadouts/--weapons (DataAircraft, DataShip, DataFacility, DataSubmarine, DataGroundUnit)",
    )
    parser.add_argument(
        "--validate-scenario",
        help="Validate air dbid/loadout pairs in a Lua scenario file",
    )
    parser.add_argument("--db", help="Explicit path to a CMO source .db3 file")
    parser.add_argument(
        "--master",
        action="store_true",
        help="Force queries against CMO_Master.db instead of a version-locked source .db3",
    )

    args = parser.parse_args()
    db_kwargs = _db_mode_args(args)

    if args.validate_scenario:
        report = validate_scenario_air_loadouts(
            args.validate_scenario,
            series=args.series,
            version=args.version,
            **db_kwargs,
        )
        for line in report["ok"]:
            print(line)
        for line in report["warnings"]:
            print(f"WARNING: {line}")
        for line in report["errors"]:
            print(f"ERROR: {line}")

        if report["errors"]:
            sys.exit(2)
        if report["warnings"]:
            sys.exit(1)
        print("Scenario air loadout validation passed.")
        return

    if args.loadouts:
        unit_type = args.type or "DataAircraft"
        if unit_type == "DataAircraft":
            results = get_loadouts(args.loadouts, args.series, args.version, **db_kwargs)
            if not results:
                print(f"No loadouts found for Aircraft ID '{args.loadouts}'")
                return
            print(f"{'Loadout ID':<12} | {'Series':<6} | {'Ver':<5} | {'Name'}")
            print("-" * 100)
            for lid, name, ser, ver in results:
                print(f"{lid:<12} | {ser:<6} | {ver:<5} | {name}")
            return

        data = get_unit_weapons(args.loadouts, unit_type, args.series, args.version, **db_kwargs)
        if not data or (not data["magazines"] and not data["mounts"]):
            print(f"No weapon configuration found for {unit_type} ID '{args.loadouts}'")
            return

        print(f"Weapon configuration for {unit_type} ID '{args.loadouts}'")
        if data["magazines"]:
            print("\n### MAGAZINES ###")
            print(f"{'Mag ID':<10} | {'Name':<40} | {'Series/Ver':<12}")
            print("-" * 100)
            for mag in data["magazines"]:
                print(f"{mag['id']:<10} | {mag['name']:<40} | {mag['series']}/{mag['version']}")
                for w_id, w_name, qty in mag["weapons"]:
                    print(f"  -> {qty:>4}x [ID {w_id:>5}] {w_name}")

        if data["mounts"]:
            print("\n### MOUNTS ###")
            print(f"{'Mount ID':<10} | {'Name':<40} | {'Series/Ver':<12}")
            print("-" * 100)
            for mount in data["mounts"]:
                print(f"{mount['id']:<10} | {mount['name']:<40} | {mount['series']}/{mount['version']}")
                for w_id, w_name, load in mount["weapons"]:
                    print(f"  -> {load:>4}x [ID {w_id:>5}] {w_name}")
        return

    if args.weapons:
        unit_type = args.type or "DataShip"
        data = get_unit_weapons(args.weapons, unit_type, args.series, args.version, **db_kwargs)
        if not data:
            print(f"No weapon/magazine data found for {unit_type} ID '{args.weapons}'")
            return

        if data["magazines"]:
            print("\n### MAGAZINES ###")
            print(f"{'Mag ID':<10} | {'Name':<40} | {'Series/Ver':<12}")
            print("-" * 100)
            for mag in data["magazines"]:
                print(f"{mag['id']:<10} | {mag['name']:<40} | {mag['series']}/{mag['version']}")
                for w_id, w_name, qty in mag["weapons"]:
                    print(f"  -> {qty:>4}x [ID {w_id:>5}] {w_name}")

        if data["mounts"]:
            print("\n### MOUNTS ###")
            print(f"{'Mount ID':<10} | {'Name':<40} | {'Series/Ver':<12}")
            print("-" * 100)
            for mount in data["mounts"]:
                print(f"{mount['id']:<10} | {mount['name']:<40} | {mount['series']}/{mount['version']}")
                for w_id, w_name, load in mount["weapons"]:
                    print(f"  -> {load:>4}x [ID {w_id:>5}] {w_name}")
        return

    if not args.term:
        parser.print_help()
        return

    results = search_db(
        args.term,
        args.series,
        args.version,
        args.limit,
        args.id,
        **db_kwargs,
    )

    if not results:
        print(f"No results found for '{args.term}'")
        return

    print(f"{'ID':<10} | {'Type':<15} | {'Series':<6} | {'Ver':<5} | {'Op':<5} | {'Cat/RW':<10} | {'Name'}")
    print("-" * 110)
    for res in results:
        id_val, name, series, version, operator, cat, rw, type_val = res
        extra = ""
        if type_val == "DataAircraft":
            extra = f"{cat}/{rw}"
            if cat == 2002:
                extra += " (CC)"
            if rw == 2001:
                extra += " (VTOL)"
            if rw == 3005:
                extra += " (STOVL)"

        print(
            f"{id_val:<10} | {type_val:<15} | {series:<6} | {version:<5} | {operator:<5} | {extra:<10} | {name}"
        )

if __name__ == "__main__":
    main()

