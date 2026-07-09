"""Air assignments, host capacity, sides, and syntax validators."""

import math
import re

from db_unit_queries import get_unit_weapons
from preflight_constants import *
from preflight_parse import *  # noqa: F403

def _validate_sides_created_before_use(content):
    """
    CMO Lua on a blank scenario requires ScenEdit_AddSide before SetSidePosture,
    missions, or unit spawn — otherwise 'Unable to identify Side-A!'.
    """
    errors = []
    warnings = []
    ok = []

    added, referenced = _parse_scenario_sides(content)
    if not referenced:
        return errors, warnings, ok

    if not added:
        sample = ", ".join(sorted(referenced.keys())[:4])
        errors.append(
            "Sides: script references side(s) "
            f"({sample}{'...' if len(referenced) > 4 else ''}) but has no "
            "ScenEdit_AddSide({side='...'}) — CMO reports 'Unable to identify Side-A!' "
            "on a blank scenario. Add AddSide for every side before SetSidePosture/missions/spawn."
        )
        return errors, warnings, ok

    for side in sorted(referenced.keys()):
        ref_line, api = referenced[side]
        if side not in added:
            errors.append(
                f"Sides: '{side}' used at line {ref_line} ({api}) but never created with "
                f"ScenEdit_AddSide({{side='{side}'}}) — CMO cannot resolve the side on a blank scenario."
            )
            continue
        if ref_line < added[side]:
            errors.append(
                f"Sides: '{side}' first used at line {ref_line} ({api}) before "
                f"ScenEdit_AddSide at line {added[side]} — create the side before posture/missions/units."
            )

    missing = [s for s in referenced if s not in added]
    if not missing and not any(e.startswith("Sides:") and "before" in e for e in errors):
        ok.append(
            f"OK: Sides — {len(added)} ScenEdit_AddSide call(s) cover all "
            f"{len(referenced)} referenced side(s) in correct order."
        )
    elif not missing and errors:
        ok.append(
            f"OK: Sides — all {len(referenced)} referenced side(s) have ScenEdit_AddSide "
            "(fix ordering errors above)."
        )

    return errors, warnings, ok

def _validate_air_host_capacity(content, db, ships, series, version):
    errors = []
    warnings = []
    ok = []
    hosts = _parse_air_host_map(content, ships)
    if not hosts:
        return errors, warnings, ok

    host_refs = set(hosts.keys())
    spawns = _parse_air_spawns_on_hosts(content, host_refs)
    spawns.extend(_parse_ipairs_loop_base_spawns(content, host_refs))
    if not spawns:
        return errors, warnings, ok

    demand = {}
    aircraft_by_host = {}
    for row in spawns:
        base_ref = row["base_ref"]
        demand[base_ref] = demand.get(base_ref, 0) + row["count"]
        aircraft_by_host.setdefault(base_ref, set()).add(row["aircraft_id"])

    for base_ref, count in sorted(demand.items()):
        host = hosts.get(base_ref)
        if not host:
            continue
        capacity = _air_host_capacity(db, host, aircraft_by_host[base_ref], series, version)
        if capacity == "missing_aircraft":
            warnings.append(
                f"Air host: could not resolve aircraft DB row(s) for spawns on '{base_ref}'."
            )
            continue

        label = host.get("name") or base_ref
        kind_label = "Facility" if host["kind"] == "facility" else "Ship"
        db_label = f"{host['kind']} DB {host['dbid']}"

        if capacity == _HOST_CAPACITY_RUNWAY_UNLIMITED:
            ok.append(
                f"OK: {kind_label} air host '{label}' ({base_ref}): {count} aircraft on "
                f"runway-style {db_label} — berth slots not capped in preflight."
            )
            continue

        if count > capacity:
            ac_list = ", ".join(str(a) for a in sorted(aircraft_by_host[base_ref]))
            errors.append(
                f"Air host: {count} aircraft (IDs {ac_list}) on '{label}' ({base_ref}, "
                f"{db_label}) exceeds host capacity {capacity} — CMO returns "
                "'Unable to host unit'. Use a larger airfield DB, split across bases, "
                "or reduce spawn count."
            )
        else:
            ok.append(
                f"OK: {kind_label} air host '{label}' ({base_ref}): {count}/{capacity} "
                f"hosted aircraft slot(s)."
            )
    return errors, warnings, ok

def _validate_aircraft_mission_assignments(content, mission_map):
    """spawn_air_wing aircraft must target a defined mission via add_air_unit_checked."""
    errors = []
    warnings = []
    ok = []

    helper_match = re.search(
        r"function\s+add_air_unit_checked\s*\(.*?\)(.*?)end\s*\n\s*local function spawn_air_wing",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    mut_errors, mut_warnings, mut_ok = _validate_air_assign_after_mission_mutations(content)
    errors.extend(mut_errors)
    warnings.extend(mut_warnings)
    ok.extend(mut_ok)

    if not helper_match:
        warnings.append(
            "Aircraft mission assignment: no add_air_unit_checked/spawn_air_wing helper pair found."
        )
        return errors, warnings, ok

    helper_body = helper_match.group(1)
    assigns_via_helper = bool(
        re.search(r"assign_air_to_mission\s*\(", helper_body, re.IGNORECASE)
    )
    assigns_via_api = bool(
        re.search(r"ScenEdit_AssignUnitToMission\s*\(", helper_body, re.IGNORECASE)
    )
    if not assigns_via_helper and not assigns_via_api:
        errors.append(
            "Aircraft mission assignment: add_air_unit_checked does not call "
            "assign_air_to_mission or ScenEdit_AssignUnitToMission — aircraft will stay unassigned."
        )
    if not re.search(r"add_params\.mission\s*=", helper_body, re.IGNORECASE):
        warnings.append(
            "Aircraft mission assignment: add_air_unit_checked does not set mission= on "
            "ScenEdit_AddUnit — CMO may show aircraft as Unassigned until AssignUnitToMission runs."
        )

    specs = _parse_air_spawn_wing_specs(content)
    if not specs:
        warnings.append("Aircraft mission assignment: no spawn_air_wing calls found.")
        return errors, warnings, ok

    total_aircraft = 0
    missions_used = set()
    for spec in specs:
        total_aircraft += spec["count"]
        mission = spec["mission"]
        missions_used.add(mission)
        if not mission:
            errors.append("Aircraft mission assignment: spawn_air_wing with empty mission name.")
            continue
        if mission not in mission_map:
            errors.append(
                f"Aircraft mission assignment: spawn_air_wing targets '{mission}' but "
                "ScenEdit_AddMission never defines that mission name."
            )
            continue
        role = mission_map.get(mission)
        if spec["escort"] and role != "strike":
            errors.append(
                f"Aircraft mission assignment: spawn_air_wing uses escort=true on non-strike "
                f"mission '{mission}' (role={role})."
            )

    for match in re.finditer(
        r"add_air_unit_checked\s*\(\s*'[^']*'\s*,\s*[^,]+,\s*\d+\s*,\s*[^,]+,\s*nil\s*,",
        content,
        re.IGNORECASE,
    ):
        errors.append(
            "Aircraft mission assignment: add_air_unit_checked called with nil mission_name."
        )

    if "spawned_air_missions" in content and (
        re.search(
            r"for\s+_,\s*entry\s+in\s+ipairs\s*\(\s*spawned_air_missions\s*\)",
            content,
            re.IGNORECASE,
        )
        or re.search(r"finalize_strike_air_after_flight_plan\s*\(", content, re.IGNORECASE)
    ):
        ok.append(
            f"OK: Aircraft mission assignment — {total_aircraft} aircraft from spawn_air_wing; "
            "assign_air_to_mission + mission= on AddUnit; post-flight-plan finalize present."
        )
    elif not errors:
        warnings.append(
            f"Aircraft mission assignment: {total_aircraft} spawn_air_wing aircraft assign via helper, "
            "but no finalize_strike_air_after_flight_plan (CreateMissionFlightPlan may drop assignments)."
        )
        ok.append(
            f"OK: Aircraft mission assignment — {total_aircraft} aircraft target "
            f"{len(missions_used)} mission(s) via spawn_air_wing + AssignUnitToMission in helper."
        )

    return errors, warnings, ok

def _validate_air_assign_after_mission_mutations(content):
    """CreateMissionFlightPlan / TLAM init can clear air ORBAT — restore after last mutation."""
    errors = []
    warnings = []
    ok = []
    scenario_body = content.split("-- [preflight: scenario_bootstrap.lua]")[0]

    if not re.search(r"CreateMissionFlightPlan\s*\(", scenario_body, re.IGNORECASE):
        return errors, warnings, ok

    strike_m = re.search(
        r"local\s+STRIKE_AIR_MISSION\s*=\s*'([^']+)'", scenario_body, re.IGNORECASE
    )
    strike_name = strike_m.group(1) if strike_m else _resolve_strike_air_mission(content)
    if not strike_name:
        warnings.append(
            "Air assignment: no STRIKE_AIR_MISSION local — carrier strike name checks skipped."
        )
        return errors, warnings, ok

    if not re.search(r"finalize_strike_air_after_flight_plan\s*\(", scenario_body, re.IGNORECASE):
        errors.append(
            "Air assignment: CreateMissionFlightPlan without finalize_strike_air_after_flight_plan() — "
            "strike aircraft will appear unassigned."
        )
    else:
        ok.append("OK: Air assignment — finalize_strike_air_after_flight_plan after flight plan.")

    spawn_matches = list(re.finditer(r"spawn_air_wing\s*\(", scenario_body, re.IGNORECASE))
    if spawn_matches:
        post_spawn = scenario_body[spawn_matches[-1].end() :]
        for m in re.finditer(
            rf"ScenEdit_SetMission\s*\(\s*'[^']+'\s*,\s*'{re.escape(strike_name)}'\s*,",
            post_spawn,
            re.IGNORECASE,
        ):
            errors.append(
                f"Air assignment: ScenEdit_SetMission on '{strike_name}' after spawn_air_wing — "
                "CMO clears all aircraft on that mission (use configure_strike_mission_options before spawn)."
            )

    if re.search(
        r"setup_csg_strike_on_air_strike",
        scenario_body,
        re.IGNORECASE,
    ):
        if re.search(r"finalize_strike_air_after_flight_plan\s*\(", scenario_body, re.IGNORECASE):
            if not re.search(
                r"restore_all_spawned_air_assignments\s*\(", scenario_body, re.IGNORECASE
            ):
                errors.append(
                    "Air assignment: TLAM/naval init after air flight plan must call "
                    "restore_all_spawned_air_assignments() — naval CreateMissionFlightPlan clears strike ORBAT."
                )
            else:
                ok.append(
                    "OK: Air assignment — restore_all_spawned_air_assignments after TLAM/naval init."
                )

    if re.search(r"verify_spawned_air_assignments\s*\(", scenario_body, re.IGNORECASE):
        ok.append("OK: Air assignment — verify_spawned_air_assignments logs unassigned at init end.")

    if re.search(
        r"function\s+M\._restore_air_after_naval_schedule_mutation\s*\(",
        content,
        re.IGNORECASE,
    ):
        ok.append(
            "OK: Air assignment — bootstrap restores air after naval CreateMissionFlightPlan."
        )
    return errors, warnings, ok

def _validate_unit_mission_assignments(content, mission_map):
    """
    Placed ships/subs/SAMs must have ScenEdit_AssignUnitToMission (direct or pairs-loop).
    Aircraft: see _validate_aircraft_mission_assignments. Facilities: warning if unassigned.
    """
    errors = []
    warnings = []
    ok = []

    direct_units = _parse_direct_place_units(content, _PLACE_UNIT_CALLS)
    unit_tables = _parse_lua_tables_with_place_calls(content, _PLACE_UNIT_CALLS)
    assigned_refs = _parse_direct_mission_assigned_refs(content)
    assigned_tables, assigned_table_fields, assigned_inline_vars = _parse_tables_assigned_via_pairs_loop(content)
    csg_members, csg_lead = _parse_csg_group_members(content)
    field_parent_table = {}
    for table_name, fields in unit_tables.items():
        for field in fields:
            field_parent_table[field] = table_name

    unassigned = []
    assigned_count = 0

    for ref, info in sorted(direct_units.items()):
        if ref in assigned_refs:
            assigned_count += 1
            continue
        if (
            csg_members
            and ref in csg_members
            and ref != csg_lead
            and ref != _CSG_STRIKE_SHIP_VAR
            and re.search(_GROUPED_CSG_STRIKE_CALL, content, re.IGNORECASE)
        ):
            assigned_count += 1
            continue
        if ref == _CSG_STRIKE_SHIP_VAR and re.search(
            _CSG_TLAM_SHIP_ASSIGN_CALL,
            content,
            re.IGNORECASE,
        ):
            assigned_count += 1
            continue
        parent_table = field_parent_table.get(ref)
        if parent_table and parent_table in assigned_tables:
            assigned_count += 1
            continue
        if parent_table and f"{parent_table}.{ref}" in assigned_table_fields:
            assigned_count += 1
            continue
        if ref in assigned_inline_vars:
            assigned_count += 1
            continue
        unassigned.append((ref, info.get("name") or ref, info.get("kind"), info.get("side")))

    for table_name, fields in sorted(unit_tables.items()):
        for field in fields:
            full_ref = f"{table_name}.{field}"
            if table_name in assigned_tables or full_ref in assigned_table_fields:
                assigned_count += 1
                continue
            unassigned.append((full_ref, field, "table", table_name))

    for ref, name, kind, side in unassigned:
        errors.append(
            f"Mission assignment: '{name}' ({ref}, {kind}) has no ScenEdit_AssignUnitToMission — "
            f"unit will appear unassigned in CMO. Assign to a patrol/strike/support mission."
        )

    direct_bases = _parse_direct_place_units(content, _FACILITY_PLACE_CALLS)
    base_tables = _parse_lua_tables_with_place_calls(content, _FACILITY_PLACE_CALLS)
    for ref in direct_bases:
        if ref not in assigned_refs:
            warnings.append(
                f"Mission assignment: facility '{ref}' has no mission (often OK if only an air spawn host)."
            )
    for table_name, fields in base_tables.items():
        for field in fields:
            full_ref = f"{table_name}.{field}"
            if table_name in assigned_tables or full_ref in assigned_table_fields:
                continue
            warnings.append(f"Mission assignment: facility '{full_ref}' has no mission.")

    if not errors and assigned_count:
        ok.append(
            f"OK: Mission assignment — {assigned_count} placed ship/sub/SAM unit(s) covered by "
            "AssignUnitToMission (direct, pairs-loop, or CSG group lead/strike with escorts following formation)."
        )

    air_errors, air_warnings, air_ok = _validate_aircraft_mission_assignments(content, mission_map)
    errors.extend(air_errors)
    warnings.extend(air_warnings)
    ok.extend(air_ok)

    return errors, warnings, ok

def _validate_f35_carrier_assignments(content, db, series, version):
    errors = []
    warnings = []
    ok = []
    ok_logged = set()
    for side, aircraft_id, loadout_id, mission_name, carrier_var in _parse_spawn_carrier_assignments(
        content
    ):
        name_u = _aircraft_name_upper(db, aircraft_id, series, version)
        variant = _f35_variant(name_u)
        if not variant:
            continue
        if variant == "C":
            ok_key = (aircraft_id, carrier_var, mission_name)
            if ok_key not in ok_logged:
                ok_logged.add(ok_key)
                ok.append(
                    f"OK: F-35C (aircraft {aircraft_id}) on carrier '{carrier_var}' "
                    f"for mission '{mission_name}' — correct for CVN strike/CAP."
                )
        elif variant == "B":
            errors.append(
                f"F-35 carrier fit: F-35B (aircraft {aircraft_id}) spawned on carrier '{carrier_var}' "
                f"for mission '{mission_name}'. F-35B belongs on LHA/LHD (STOVL), not catapult CVN; use F-35C."
            )
        elif variant == "A":
            errors.append(
                f"F-35 carrier fit: F-35A (aircraft {aircraft_id}) on carrier '{carrier_var}' — "
                "use F-35C for carrier strike/CAP."
            )
    return errors, warnings, ok

def _validate_wrapper_colon_syntax(content):
    errors = []
    warnings = []
    ok = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        match = _WRONG_WRAPPER_DOT_CALL.search(line)
        if match:
            errors.append(
                f"Lua wrapper syntax line {line_no}: use colon for instance method "
                f"'{match.group(1)}' (e.g. mission:{match.group(1)}()), not '.{match.group(1)}()' — "
                "see cmo_api_reference.md Wrapper-aanroep."
            )
    if not errors:
        ok.append("OK: No wrapper instance methods called with dot syntax (obj.method()).")
    return errors, warnings, ok

__all__ = ['_validate_air_assign_after_mission_mutations', '_validate_air_host_capacity', '_validate_aircraft_mission_assignments', '_validate_f35_carrier_assignments', '_validate_sides_created_before_use', '_validate_unit_mission_assignments', '_validate_wrapper_colon_syntax']
