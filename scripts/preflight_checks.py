"""Scenario preflight validators (used by preflight_validate.validate_scenario_air_loadouts)."""

import math
import re

from db_unit_queries import get_unit_weapons
from preflight_constants import *
from preflight_parse import *
from preflight_report import extend_report, run_check

def _validate_patrol_zone_proximity(content, mission_map, ships):
    errors = []
    warnings = []
    ok = []

    if not ships:
        return errors, warnings, ok

    points, consts = _parse_reference_points_resolved(content)
    zones = _parse_mission_zone_map(content)
    anchor = _csg_anchor_point(content, ships, consts)
    if not anchor:
        warnings.append(
            "Patrol zone proximity: no csg_lat/csg_lon or CVN placement found — "
            "CSG-local patrol box checks skipped."
        )
        return errors, warnings, ok

    anchor_lat, anchor_lon, anchor_label = anchor
    ship_hosts = _ship_host_positions(ships)
    host_refs = set(ship_hosts.keys())

    for mission_name, point_names in zones.items():
        if not _is_csg_local_patrol_mission(mission_name):
            continue
        centroid = _zone_centroid(point_names, points)
        if not centroid:
            errors.append(
                f"Patrol zone proximity: mission '{mission_name}' has no resolvable reference points."
            )
            continue
        dist = _approx_deg_distance(anchor_lat, anchor_lon, centroid[0], centroid[1])
        if dist > _CSG_LOCAL_PATROL_MAX_DEG:
            errors.append(
                f"Patrol zone proximity: '{mission_name}' station centroid is {dist:.2f}° from "
                f"{anchor_label} ({anchor_lat}, {anchor_lon}) — CAP/AEW should stay within "
                f"~{_CSG_LOCAL_PATROL_MAX_DEG}° (~90 nm) of the CSG. Tie zone refs to csg_lat/csg_lon."
            )
        else:
            ok.append(
                f"OK: Patrol zone '{mission_name}' centroid {dist:.2f}° from CSG ({anchor_label})."
            )

    helo_spawns = _parse_air_spawns_on_hosts(content, host_refs)
    helo_missions = {row["mission"] for row in helo_spawns if _is_helo_patrol_mission(row["mission"], mission_map)}
    for mission_name in sorted(helo_missions):
        point_names = zones.get(mission_name, [])
        centroid = _zone_centroid(point_names, points)
        if not centroid:
            errors.append(
                f"Helo patrol zone: mission '{mission_name}' has no resolvable patrol zone."
            )
            continue
        hosts_for_mission = {
            row["base_ref"]
            for row in helo_spawns
            if row["mission"] == mission_name and row["base_ref"] in ship_hosts
        }
        if not hosts_for_mission:
            warnings.append(
                f"Helo patrol zone: mission '{mission_name}' has no spawn_air_wing on a placed ship host."
            )
            continue
        for host_ref in sorted(hosts_for_mission):
            host_lat, host_lon, host_label = ship_hosts[host_ref]
            dist = _approx_deg_distance(host_lat, host_lon, centroid[0], centroid[1])
            if dist > _CSG_HELO_PATROL_MAX_DEG:
                errors.append(
                    f"Helo patrol zone: '{mission_name}' patrol box is {dist:.2f}° from host "
                    f"'{host_label}' ({host_ref}) — Seahawk/ASW routes should be near the DDG/CG. "
                    f"Use csg_lat/csg_lon offsets for US_ASW_* points."
                )
            else:
                ok.append(
                    f"OK: Helo patrol '{mission_name}' zone {dist:.2f}° from host {host_label} ({host_ref})."
                )

    return errors, warnings, ok

def _validate_csg_formation(content, air_carrier_vars):
    """CSG surface ships should share one group; escorts must not sail solo ASW patrols."""
    errors = []
    warnings = []
    ok = []

    if not air_carrier_vars:
        return errors, warnings, ok

    csg_group = _parse_csg_group_constant(content)
    group_map = _parse_unit_group_assignments(content)
    scenario_body = content.split("-- [preflight: scenario_bootstrap.lua]")[0]
    grouped_tlam = bool(re.search(_GROUPED_CSG_STRIKE_CALL, scenario_body, re.IGNORECASE))
    has_form_helper = bool(
        re.search(r"function\s+(?:M\.)?form_csg_group\s*\(", content, re.IGNORECASE)
        or re.search(r"form_csg_group\s*=\s*cmo\.form_csg_group", content, re.IGNORECASE)
    )
    has_form_call = bool(
        re.search(r"form_csg_group\s*\(\s*CSG_GROUP\s*,\s*nimitz", content, re.IGNORECASE)
    )
    if has_form_call and csg_group:
        for var in _CSG_GROUP_MEMBER_VARS:
            if re.search(rf"\blocal\s+{var}\s*=", content):
                group_map[var] = csg_group

    placed_csg = [var for var in _CSG_FORMATION_VARS if re.search(rf"\blocal\s+{var}\s*=", content)]
    if not placed_csg:
        return errors, warnings, ok

    for match in re.finditer(
        r"ScenEdit_AssignUnitToMission\s*\(\s*(\w+)\.guid\s*,\s*'([^']+)'(?:\s*,\s*(true|false))?\s*\)",
        content,
        flags=re.IGNORECASE,
    ):
        var = match.group(1)
        mission = match.group(2)
        if var not in placed_csg or match.group(3):
            continue
        lower = mission.lower()
        if any(marker in lower for marker in _CSG_SHIP_MISSIONS_BREAKING_FORMATION):
            errors.append(
                f"CSG formation: ship '{var}' assigned to '{mission}' — escorts/carrier must not "
                f"patrol independently. Group the CSG and use 'CSG Station Keeping' for movement; "
                f"keep ASW on embarked helos (CSG ASW Screen)."
            )

    if csg_group:
        placed_group_members = [
            var
            for var in _CSG_GROUP_MEMBER_VARS
            if re.search(rf"\blocal\s+{var}\s*=", content)
        ]
        missing_group = [
            var for var in placed_group_members if group_map.get(var) != csg_group
        ]
        if missing_group:
            errors.append(
                f"CSG formation: not all CSG ships are in group '{csg_group}' "
                f"(missing/wrong group: {', '.join(missing_group)}). "
                f"Call form_csg_group after place_ship."
            )
        elif len(placed_group_members) >= 2:
            suffix = (
                " (unified strike package)."
                if grouped_tlam
                else "."
            )
            ok.append(
                f"OK: CSG formation — {len(placed_group_members)} ship(s) in group '{csg_group}'" + suffix
            )
        cg_in_group_tlam_fix = grouped_tlam
        if (
            _CSG_STRIKE_SHIP_VAR in placed_csg
            and group_map.get(_CSG_STRIKE_SHIP_VAR) == csg_group
            and not cg_in_group_tlam_fix
        ):
            warnings.append(
                f"CSG formation: '{_CSG_STRIKE_SHIP_VAR}' is in formation group '{csg_group}' without "
                "setup_csg_strike_on_air_strike after form_csg_group — TLAM strike assignment may be missing."
            )
    elif len(placed_csg) >= 2:
        errors.append(
            "CSG formation: carrier strike group ships are placed but no CSG_GROUP / "
            "form_csg_group() — escorts will scatter on separate patrol missions."
        )

    if has_form_helper and not has_form_call:
        warnings.append(
            "CSG formation: form_csg_group() is defined but never called."
        )

    station_assigned = bool(
        re.search(
            rf"ScenEdit_SetMission\s*\([^)]*'(?:Carrier CAP|Carrier AEW|CSG Station Keeping)'",
            scenario_body,
            re.IGNORECASE,
        )
        or re.search(
            rf"ScenEdit_AssignUnitToMission\s*\(\s*{_CSG_GROUP_LEAD_VAR}\.guid",
            scenario_body,
            re.IGNORECASE,
        )
    )

    patrol_assigns = {}
    for match in re.finditer(
        r"ScenEdit_AssignUnitToMission\s*\(\s*(\w+)\.guid\s*,\s*'([^']+)'(?:\s*,\s*(true|false))?\s*\)",
        content,
        flags=re.IGNORECASE,
    ):
        var = match.group(1)
        if var not in placed_csg or match.group(3):
            continue
        patrol_assigns.setdefault(var, []).append(match.group(2))

    for var in _CSG_ESCORT_VARS:
        if var not in placed_csg:
            continue
        for mission in patrol_assigns.get(var, []):
            if _CSG_PATROL_MISSION in mission.lower():
                errors.append(
                    f"CSG formation: escort '{var}' assigned to '{mission}' — only the group lead "
                    f"({_CSG_GROUP_LEAD_VAR}) or group name should carry the CSG patrol mission; "
                    "escorts follow in formation."
                )

    if _CSG_GROUP_LEAD_VAR in placed_csg and not station_assigned:
        has_csg_station = bool(
            re.search(
                r"ScenEdit_AddMission\s*\([^)]*'CSG Station Keeping'",
                scenario_body,
                re.IGNORECASE,
            )
        )
        if has_csg_station:
            warnings.append(
                f"CSG formation: group lead '{_CSG_GROUP_LEAD_VAR}' should carry carrier patrol "
                f"(ScenEdit_SetMission or AssignUnitToMission on lead only — not group-wide)."
            )
        elif re.search(_CSG_TLAM_SHIP_ASSIGN_CALL, content, re.IGNORECASE):
            ok.append(
                "OK: CSG formation — group-only (no CSG Station Keeping); unified strike package in formation."
            )

    if _CSG_STRIKE_SHIP_VAR in placed_csg:
        allowed_strike_missions = _csg_allowed_ship_strike_missions(content)
        tlam_example = _resolve_tlam_strike_mission(content) or "TLAM Strike"
        striker_missions = patrol_assigns.get(_CSG_STRIKE_SHIP_VAR, [])
        for mission in striker_missions:
            if mission.lower() not in allowed_strike_missions:
                errors.append(
                    f"CSG formation: '{_CSG_STRIKE_SHIP_VAR}' on '{mission}' — use a separate timed "
                    f"Strike (e.g. {tlam_example}) while the ship stays in the CSG group."
                )
        striker_on_tlam = bool(
            re.search(_CSG_TLAM_SHIP_ASSIGN_CALL, scenario_body, re.IGNORECASE)
        )
        if striker_on_tlam and grouped_tlam:
            ok.append(
                "OK: CSG TLAM — unified strike package (setup_csg_strike_on_air_strike)."
            )
        elif not striker_on_tlam and grouped_tlam:
            errors.append(
                "CSG TLAM: form_csg_group without setup_csg_strike_on_air_strike — "
                "unify naval strike assets on the package mission after the air flight plan."
            )
        elif not striker_on_tlam and station_assigned:
            warnings.append(
                f"CSG formation: CG '{_CSG_STRIKE_SHIP_VAR}' has no unified strike package assignment."
            )

    if re.search(
        r"ScenEdit_AssignUnitToMission\s*\(\s*CSG_GROUP\s*,\s*'CSG Station Keeping'",
        content,
        re.IGNORECASE,
    ):
        warnings.append(
            "CSG formation: AssignUnitToMission(group_name, patrol) clears TLAM shooters in the ME — "
            "assign patrol on the group lead only."
        )

    tlam_sched_errors, tlam_sched_warnings, tlam_sched_ok = _validate_tlam_schedule_workflow(content)
    errors.extend(tlam_sched_errors)
    warnings.extend(tlam_sched_warnings)
    ok.extend(tlam_sched_ok)

    return errors, warnings, ok

def _validate_tlam_schedule_workflow(content):
    """
    CMO clears naval Strike starttime/TOT when SetUnit/AssignUnitToMission assigns ships.
    setup_csg_strike_on_air_strike restores schedule via set_naval_strike_schedule at init.
    """
    errors = []
    warnings = []
    ok = []
    scenario_body = content.split("-- [preflight: scenario_bootstrap.lua]")[0]

    has_naval = bool(
        re.search(
            r"@naval_package|TLAM_STRIKE_MISSION|setup_csg_strike_on_air_strike",
            content,
            re.IGNORECASE,
        )
    )
    if not has_naval:
        return errors, warnings, ok

    apply_fn = re.search(
        r"function\s+M\.setup_csg_strike_on_air_strike\s*\([\s\S]*?^end",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if apply_fn:
        body = apply_fn.group(0)
        if "set_naval_strike_schedule" not in body:
            errors.append(
                "TLAM schedule: setup_csg_strike_on_air_strike must call "
                "set_naval_strike_schedule (hardcoded starttime + TimeOnTargetStation) after ship assign."
            )
        else:
            ok.append("OK: TLAM schedule — set_naval_strike_schedule in setup_csg_strike_on_air_strike.")

    if re.search(_CSG_TLAM_SHIP_ASSIGN_CALL, scenario_body, re.IGNORECASE):
        ok.append("OK: TLAM schedule — naval assets unified on strike package at init end.")
        apply_pos = -1
        air_fp_pos = -1
        apply_call = re.search(
            r"(?<!function\s)setup_csg_strike_on_air_strike\s*\(",
            scenario_body,
            re.IGNORECASE,
        )
        air_fp = re.search(
            r"ScenEdit_CreateMissionFlightPlan\s*\(",
            scenario_body,
            re.IGNORECASE,
        )
        if apply_call:
            apply_pos = apply_call.start()
        if air_fp:
            air_fp_pos = air_fp.start()
        if apply_pos >= 0 and air_fp_pos >= 0 and apply_pos < air_fp_pos:
            errors.append(
                "TLAM schedule: setup_csg_strike_on_air_strike must run after air "
                "CreateMissionFlightPlan — naval assign clears mission times."
            )
    elif re.search(r"@naval_package", content, re.IGNORECASE):
        errors.append(
            "TLAM schedule: use setup_csg_strike_on_air_strike(group, {cvn, ddg, cg, ...}) "
            "after the air flight plan — not inline SetMission alone."
        )

    if re.search(
        r"ScenEdit_SetMission\s*\([^)]*TLAM[^)]*starttime\s*=\s*tlam_launch_dt",
        content,
        re.IGNORECASE,
    ):
        warnings.append(
            "TLAM schedule: inline ScenEdit_SetMission(starttime=tlam_launch_dt) before ship assign "
            "is wiped by SetUnit — use setup_csg_strike_on_air_strike + set_naval_strike_schedule."
        )

    gun_errors, gun_warnings, gun_ok = _validate_tlam_shooter_weapon_policy(content)
    errors.extend(gun_errors)
    warnings.extend(gun_warnings)
    ok.extend(gun_ok)

    return errors, warnings, ok

def _validate_tlam_shooter_weapon_policy(content):
    """Strike ships: main gun never on land; surface gun self-defence only; no opportunistic hunting."""
    errors = []
    warnings = []
    ok = []

    has_strike_ships = bool(
        re.search(
            r"@naval_package|TLAM_STRIKE_MISSION|setup_csg_strike_on_air_strike|assign_ship_to_mission",
            content,
            re.IGNORECASE,
        )
    )
    if not has_strike_ships:
        return errors, warnings, ok

    if not re.search(r"M\.LAND_STRIKE_WRA_TARGET_TYPES\s*=", content):
        errors.append("Strike ship guns: bootstrap missing M.LAND_STRIKE_WRA_TARGET_TYPES.")
    if not re.search(r"M\.SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES\s*=", content):
        errors.append(
            "Strike ship guns: bootstrap missing M.SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES."
        )
    if not re.search(
        r"M\.WRA_GUN_SURFACE_SELF_DEFENSE\s*=\s*\{\s*'inherit'\s*,\s*'inherit'\s*,\s*'none'\s*,\s*'max'\s*\}",
        content,
    ):
        errors.append(
            "Strike ship guns: M.WRA_GUN_SURFACE_SELF_DEFENSE must be "
            "{ 'inherit', 'inherit', 'none', 'max' } (no offensive surface fire; self-defence allowed)."
        )
    else:
        ok.append(
            "OK: Strike ship guns — surface WRA firing=none, self-defence=max."
        )
    if not re.search(
        r"M\.WRA_GUN_LAND_BLOCK\s*=\s*\{\s*'none'\s*,\s*'none'\s*,\s*'none'\s*,\s*'none'\s*\}",
        content,
    ):
        errors.append(
            "Strike ship guns: M.WRA_GUN_LAND_BLOCK must block all land gun WRA entries."
        )
    else:
        ok.append("OK: Strike ship guns — land gun WRA fully blocked.")

    policy_body = None
    policy_match = re.search(
        r"function\s+M\.configure_strike_ship_weapon_policy\s*\([\s\S]*?^end",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if not policy_match:
        errors.append(
            "Strike ship guns: configure_strike_ship_weapon_policy() missing from bootstrap."
        )
    else:
        policy_body = policy_match.group(0)
        if not re.search(r"weapon_control_status_surface\s*=\s*0", policy_body):
            errors.append(
                "Strike ship guns: unit doctrine must set weapon_control_status_surface=0 "
                "(HOLD — no active surface hunting)."
            )
        else:
            ok.append(
                "OK: Strike ship guns — unit WCS surface HOLD (self-defence only)."
            )
        if not re.search(r"engage_opportunity_targets\s*=\s*false", policy_body):
            errors.append(
                "Strike ship guns: engage_opportunity_targets=false required (no opportunistic hunting)."
            )
        else:
            ok.append("OK: Strike ship guns — engage_opportunity_targets=false.")
        if not re.search(
            r"weapon_state_planned\s*=\s*'ShotgunBVR'", policy_body, re.IGNORECASE
        ):
            errors.append(
                "Strike ship guns: unit doctrine must set weapon_state_planned='ShotgunBVR' "
                "(no gun fallback when missiles spent on Strike missions)."
            )
        else:
            ok.append(
                "OK: Strike ship guns — unit ShotgunBVR (standoff only; blocks gun fallback)."
            )
        if not re.search(r"_apply_strike_ship_gun_wra", policy_body):
            errors.append(
                "Strike ship guns: configure_strike_ship_weapon_policy must call _apply_strike_ship_gun_wra()."
            )

    apply_match = re.search(
        r"function\s+M\._apply_strike_ship_gun_wra\s*\([\s\S]*?^end",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if not apply_match:
        errors.append("Strike ship guns: _apply_strike_ship_gun_wra() missing from bootstrap.")
    else:
        apply_body = apply_match.group(0)
        if "WRA_GUN_SURFACE_SELF_DEFENSE" not in apply_body:
            errors.append(
                "Strike ship guns: _apply_strike_ship_gun_wra must apply WRA_GUN_SURFACE_SELF_DEFENSE."
            )
        if "WRA_GUN_LAND_BLOCK" not in apply_body:
            errors.append(
                "Strike ship guns: _apply_strike_ship_gun_wra must apply WRA_GUN_LAND_BLOCK."
            )
        if "SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES" not in apply_body:
            errors.append(
                "Strike ship guns: _apply_strike_ship_gun_wra must iterate SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES."
            )

    assign_match = re.search(
        r"function\s+M\.assign_ship_to_mission\s*\([\s\S]*?^end",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if assign_match:
        body = assign_match.group(0)
        if "configure_strike_ship_weapon_policy" not in body:
            errors.append(
                "Strike ship guns: assign_ship_to_mission must apply configure_strike_ship_weapon_policy "
                "on successful Strike mission assign."
            )
        elif "_is_strike_ship_mission" not in body:
            warnings.append(
                "Strike ship guns: assign_ship_to_mission should gate policy via _is_strike_ship_mission()."
            )
        else:
            ok.append(
                "OK: Strike ship guns — assign_ship_to_mission auto-applies policy on Strike missions."
            )
    fn_match = re.search(
        r"function\s+M\.setup_csg_strike_on_air_strike\s*\([\s\S]*?^end",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if fn_match:
        body = fn_match.group(0)
        has_policy = "configure_strike_ship_weapon_policy" in body
        has_events = "add_strike_ship_weapon_policy_event" in body
        if not has_policy:
            errors.append(
                "Strike ship guns: setup_csg_strike_on_air_strike must call configure_strike_ship_weapon_policy()."
            )
        elif not has_events:
            warnings.append(
                "Strike ship guns: setup_csg_strike_on_air_strike should register "
                "add_strike_ship_weapon_policy_event for Play-time WRA refresh."
            )
        else:
            ok.append(
                "OK: Strike ship guns — setup_csg_strike_on_air_strike applies policy + Play refresh."
            )

    mission_match = re.search(
        r"function\s+M\.configure_naval_strike_doctrine\s*\([\s\S]*?^end",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if mission_match:
        mission_body = mission_match.group(0)
        if re.search(
            r"Shotgun50_ToO|Shotgun75_ToO|ShotgunOneEngagementBVR_Opportunity_WVR_Guns|ShotgunBVR_WVR_Guns",
            mission_body,
            re.IGNORECASE,
        ):
            errors.append(
                "Strike ship guns: naval strike mission weapon_state must not use ToO/guns modes."
            )
        elif not re.search(r"weapon_state_planned\s*=\s*'ShotgunBVR'", mission_body):
            warnings.append(
                "Strike ship guns: naval strike mission should use weapon_state_planned='ShotgunBVR'."
            )
        else:
            ok.append(
                "OK: Strike ship guns — naval strike mission ShotgunBVR (standoff; no gun fallback)."
            )

    return errors, warnings, ok

def _resolve_scenedit_settime_date(content, canonical_scenario_date):
    """
    Resolve the calendar day used in ScenEdit_SetTime — literal YYYYMMDD or
    scenario_date_ymd derived from scenario_date.
    """
    set_date_key, _set_time = _parse_scenario_start_time(content)
    if set_date_key:
        return _normalize_date_slash_key(set_date_key)
    if not canonical_scenario_date:
        return None
    uses_set_time = bool(re.search(r"ScenEdit_SetTime\s*\(", content, re.IGNORECASE))
    uses_helper = bool(
        re.search(r"(?:cmo\.)?scenario_set_start\s*\(\s*scenario_date\b", content, re.IGNORECASE)
    )
    if not uses_set_time and not uses_helper:
        return None
    if uses_helper and canonical_scenario_date:
        return canonical_scenario_date
    if re.search(
        r"local\s+scenario_date_ymd\s*=\s*scenario_date:gsub\s*\(\s*'/'\s*,\s*''\s*\)",
        content,
        re.IGNORECASE,
    ) and re.search(
        r"dateformat\s*=\s*'YYYYMMDD'",
        content,
        re.IGNORECASE,
    ) and re.search(
        r"date\s*=\s*(?:scenario_date_ymd|cmo\.mission_schedule_date\s*\(\s*scenario_date\s*\)|"
        r"mission_schedule_date\s*\(\s*scenario_date\s*\))",
        content,
        re.IGNORECASE,
    ):
        return canonical_scenario_date
    return None


def _validate_scenario_date_consistency(content):
    """
    One canonical calendar day: local scenario_date drives SetTime, strike_package_date,
    @strike_package date=, and scenario_year.
    """
    errors = []
    warnings = []
    ok = []

    canonical = _parse_scenario_date(content)
    if not canonical:
        warnings.append(
            "Scenario date: define local scenario_date = 'YYYY/MM/DD' (historical in-game day) "
            "and derive strike_package_date + ScenEdit_SetTime from it."
        )
        return errors, warnings, ok

    year = int(canonical[:4])
    scenario_year = _parse_scenario_year(content)
    if scenario_year is not None and scenario_year != year:
        errors.append(
            f"Scenario date: scenario_year={scenario_year} disagrees with "
            f"scenario_date={canonical} (year {year})."
        )

    strike_date_m = re.search(
        r"local\s+strike_package_date\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    if strike_date_m:
        strike_date = _normalize_date_slash_key(strike_date_m.group(1))
        if strike_date and strike_date != canonical:
            errors.append(
                f"Scenario date: strike_package_date='{strike_date_m.group(1)}' "
                f"!= scenario_date {canonical}."
            )
    elif re.search(r"strike_package_date\s*=\s*scenario_date", content, re.IGNORECASE):
        ok.append(f"OK: Scenario date — strike_package_date derived from scenario_date ({canonical}).")
    else:
        warnings.append(
            f"Scenario date: set local strike_package_date = scenario_date "
            f"(canonical day is {canonical})."
        )

    set_slash = _resolve_scenedit_settime_date(content, canonical)
    if set_slash is None:
        if re.search(r"ScenEdit_SetTime\s*\(", content, re.IGNORECASE):
            warnings.append(
                "Scenario date: ScenEdit_SetTime present but StartDate/date not tied to "
                "scenario_date — use cmo.scenario_set_start(scenario_date, time) or "
                "date=YYYY.MM.DD + StartDate=DD.MM.YYYY."
            )
        elif not re.search(
            r"(?:cmo\.)?scenario_set_start\s*\(\s*scenario_date\b", content, re.IGNORECASE
        ):
            warnings.append(
                "Scenario date: no ScenEdit_SetTime / scenario_set_start — set H-hour from scenario_date."
            )
    elif set_slash != canonical:
        errors.append(
            f"Scenario date: ScenEdit_SetTime date {set_slash} != scenario_date {canonical}."
        )

    packages, _waves = _parse_strike_package_annotations(content)
    for pkg in packages:
        ann_date = pkg.get("date")
        if ann_date:
            ann_key = _normalize_date_slash_key(ann_date)
            if ann_key and ann_key != canonical:
                errors.append(
                    f"Scenario date: @strike_package date={ann_date} "
                    f"!= scenario_date {canonical}."
                )

    sead_pkgs = _parse_sead_package_annotations(content)
    for pkg in sead_pkgs:
        ann_date = pkg.get("date")
        if ann_date:
            ann_key = _normalize_date_slash_key(ann_date)
            if ann_key and ann_key != canonical:
                errors.append(
                    f"Scenario date: @sead_package date={ann_date} "
                    f"!= scenario_date {canonical}."
                )

    if not errors:
        ok.append(f"OK: Scenario date — all declared dates align on {canonical}.")
    return errors, warnings, ok


def _validate_strike_tot_synchronization(content, mission_map):
    """Hardcoded strike timing: one strike_package_tot everywhere; no sync_* in scenario body."""
    errors = []
    warnings = []
    ok = []
    scenario_body = content.split("-- [preflight: scenario_bootstrap.lua]")[0]

    tot_m = re.search(r"local\s+strike_package_tot\s*=\s*'([^']+)'", content, re.IGNORECASE)
    if not tot_m:
        warnings.append(
            "Strike timing: no local strike_package_tot — define one canonical TOT at scenario top."
        )
        return errors, warnings, ok

    canonical_tot = tot_m.group(1)
    date_m = re.search(r"local\s+strike_package_date\s*=\s*'([^']+)'", content, re.IGNORECASE)
    canonical_date = date_m.group(1) if date_m else None

    packages, _waves = _parse_strike_package_annotations(content)
    strike_pkg = next((p for p in packages if p.get("mission")), packages[0] if packages else {})
    naval_pkgs = _parse_naval_package_annotations(content)
    naval_pkg = naval_pkgs[0] if naval_pkgs else {}
    air_strike_name = (
        _resolve_strike_air_mission(content)
        or strike_pkg.get("mission")
    )
    tlam_mission = _resolve_tlam_strike_mission(content) or naval_pkg.get("mission")

    if strike_pkg.get("time") and strike_pkg["time"] != canonical_tot:
        errors.append(
            f"Strike timing: @strike_package time={strike_pkg['time']} differs from "
            f"strike_package_tot='{canonical_tot}'."
        )
    if naval_pkg.get("tot") and naval_pkg["tot"] != canonical_tot:
        errors.append(
            f"Strike timing: @naval_package tot={naval_pkg['tot']} differs from "
            f"strike_package_tot='{canonical_tot}'."
        )

    legacy_sync = re.search(
        r"(?<!function\s)(?:sync_naval_strike_tot|sync_air_strike_tot|sync_strike_package_tot|"
        r"restore_naval_strike_schedule|setup_solo_tlam_shooter|setup_tlam_on_air_strike|"
        r"setup_csg_tlam_on_air_strike|apply_naval_strike_flight_plan|finalize_csg_tlam|"
        r"finalize_detached_tlam_shooter|assign_tlam_shooter|assign_csg_group_missions)\s*\(",
        scenario_body,
        re.IGNORECASE,
    )
    if legacy_sync:
        errors.append(
            "Strike timing: remove legacy TLAM helpers (sync_*, setup_solo_tlam_shooter, "
            "apply_naval_strike_flight_plan, finalize_csg_tlam, assign_tlam_shooter, …) — "
            "use setup_csg_strike_on_air_strike + hardcoded strike_package_tot."
        )

    if not re.search(
        r"local\s+strike_tot_dt\s*=\s*mission_schedule_datetime\s*\(\s*strike_package_date\s*,\s*strike_package_tot\s*\)",
        scenario_body,
        re.IGNORECASE,
    ):
        warnings.append(
            "Strike timing: define strike_tot_dt = mission_schedule_datetime(strike_package_date, "
            "strike_package_tot) once after OOB — reuse for all SetMission schedules."
        )

    flight_plans = _parse_mission_flight_plan_calls(content)
    for _side, mission, fp_date, fp_time in flight_plans:
        if mission == air_strike_name and fp_time and fp_time != canonical_tot:
            errors.append(
                f"Strike timing: CreateMissionFlightPlan TIMEONTARGET={fp_time} on "
                f"'{mission}' != strike_package_tot {canonical_tot}."
            )
        if mission == air_strike_name and canonical_date and fp_date and fp_date != canonical_date:
            errors.append(
                f"Strike timing: CreateMissionFlightPlan DATEONTARGET={fp_date} on "
                f"'{mission}' != strike_package_date {canonical_date}."
            )

    if re.search(r"TIMEONTARGET\s*=\s*strike_package_tot", scenario_body, re.IGNORECASE):
        ok.append(f"OK: Strike timing — air flight plan uses strike_package_tot {canonical_tot}.")

    if re.search(_GROUPED_CSG_STRIKE_CALL, scenario_body, re.IGNORECASE):
        if re.search(r"local\s+tlam_launch_time\s*=", scenario_body, re.IGNORECASE):
            ok.append(
                f"OK: Strike timing — naval package via setup_csg_strike_on_air_strike "
                f"(tlam_launch_time + strike_package_tot {canonical_tot})."
            )

    order_errors, order_warnings, order_ok = _validate_strike_schedule_order(scenario_body)
    errors.extend(order_errors)
    warnings.extend(order_warnings)
    ok.extend(order_ok)

    cvn_errors, cvn_warnings, cvn_ok = _validate_cvn_strike_air_schedule(content, scenario_body)
    errors.extend(cvn_errors)
    warnings.extend(cvn_warnings)
    ok.extend(cvn_ok)

    if not errors:
        ok.append(
            f"OK: Strike timing — hardcoded TOT {canonical_tot} for air '{air_strike_name}' "
            f"and naval '{tlam_mission}'."
        )

    return errors, warnings, ok


def _validate_strike_schedule_order(scenario_body):
    """Timed SetMission / CreateMissionFlightPlan must run after unit placement."""
    errors = []
    warnings = []
    ok = []

    oob_markers = list(
        re.finditer(
            r"(?:place_ship|place_sub|place_sam|place_base|spawn_air_wing|"
            r"ScenEdit_AssignUnitAsTarget)\s*\(",
            scenario_body,
            re.IGNORECASE,
        )
    )
    schedule_markers = list(
        re.finditer(
            r"ScenEdit_SetMission\s*\([^)]*(?:starttime|TimeOnTargetStation|TakeOffTime)|"
            r"ScenEdit_CreateMissionFlightPlan\s*\(",
            scenario_body,
            re.IGNORECASE,
        )
    )
    if not schedule_markers:
        warnings.append(
            "Strike schedule order: no timed SetMission or CreateMissionFlightPlan found."
        )
        return errors, warnings, ok

    if not oob_markers:
        warnings.append(
            "Strike schedule order: no place_ship/spawn_air_wing found — cannot verify order."
        )
        return errors, warnings, ok

    last_oob = oob_markers[-1].start()
    first_schedule = schedule_markers[0].start()
    if first_schedule < last_oob:
        errors.append(
            "Strike schedule order: timed SetMission/CreateMissionFlightPlan appears before "
            "the last unit spawn or strike target assignment — place OOB first, then set schedules."
        )
    else:
        ok.append(
            "OK: Strike schedule order — timed missions set after last spawn/target assignment."
        )

    return errors, warnings, ok


def _validate_cvn_strike_air_schedule(content, scenario_body):
    """CVN patrol SetMission after air flight plan; CAP launch after SEAD/strike launch window."""
    errors = []
    warnings = []
    ok = []

    if not re.search(r"spawn_air_wing\s*\([^)]*'Carrier CAP'", content, re.IGNORECASE):
        return errors, warnings, ok

    fp = re.search(r"ScenEdit_CreateMissionFlightPlan\s*\(", scenario_body, re.IGNORECASE)
    finalize = re.search(
        r"finalize_strike_air_after_flight_plan\s*\(", scenario_body, re.IGNORECASE
    )
    cap_set = re.search(
        r"ScenEdit_SetMission\s*\(\s*'United States'\s*,\s*'Carrier CAP'",
        scenario_body,
        re.IGNORECASE,
    )
    if fp and cap_set and cap_set.start() < fp.start():
        errors.append(
            "Carrier air ops: ScenEdit_SetMission on 'Carrier CAP' before "
            "CreateMissionFlightPlan — CVN patrol SetMission clears strike ORBAT. "
            "Schedule AEW/CAP/SEAD after finalize_strike_air_after_flight_plan()."
        )
    elif fp and cap_set and finalize and cap_set.start() > finalize.start():
        ok.append(
            "OK: Carrier air ops — Carrier CAP SetMission after air flight plan finalize."
        )

    timing = _parse_lua_timing_vars(content)
    cap_t = timing.get("cap_launch_time")
    sead_t = timing.get("sead_on_station_time") or timing.get("sead_package_takeoff")
    cap_min = _time_to_minutes(cap_t) if cap_t else None
    sead_min = _time_to_minutes(sead_t) if sead_t else None
    if cap_min is not None and sead_min is not None and cap_min <= sead_min:
        errors.append(
            f"Carrier CAP: cap_launch_time={cap_t} must be after sead_package_takeoff={sead_t} "
            "so strike aircraft launch before CAP sorties (CMO deck-queue quirk)."
        )
    elif cap_min is not None and sead_min is not None:
        ok.append(
            f"OK: Carrier CAP launch {cap_t} is after SEAD takeoff {sead_t}."
        )

    if cap_set and not re.search(
        r"ScenEdit_SetMission\s*\(\s*'United States'\s*,\s*'Carrier CAP'[\s\S]*?"
        r"OnDeactivateUassign\s*=\s*false",
        scenario_body,
        re.IGNORECASE,
    ):
        warnings.append(
            "Carrier CAP: set OnDeactivateUassign=false — mission deactivation can unassign CAP "
            "and disturb CVN strike ORBAT."
        )

    if cap_set and re.search(r"spawn_air_wing\s*\([^)]*'Carrier CAP'", content, re.IGNORECASE):
        if not re.search(r"add_strike_assign_restore_event\s*\(", scenario_body, re.IGNORECASE):
            warnings.append(
                "Carrier air ops: add_strike_assign_restore_event() recommended — CAP/SEAD launch at Play "
                "can unassign strike aircraft; Time triggers after cap/sead launch restore ORBAT."
            )
        else:
            ok.append("OK: Carrier air ops — strike assign restore events registered for Play.")

    return errors, warnings, ok


def _validate_strike_tot_reachability(
    content, mission_map, ships, assignments, db=None, series=None, version=None
):
    """
    Heuristic: can each strike asset reach its targets by strike_package_tot given
    scenario StartTime, TLAM launch, and SEAD takeoff?
    """
    errors = []
    warnings = []
    ok = []

    timing = _parse_lua_timing_vars(content)
    strike_tot = timing.get("strike_package_tot")
    if not strike_tot:
        return errors, warnings, ok

    tot_min = _time_to_minutes(strike_tot)
    if tot_min is None:
        return errors, warnings, ok

    scenario_date, scenario_start = _parse_scenario_start_time(content)
    start_min = _time_to_minutes(scenario_start) if scenario_start else None
    if start_min is None:
        warnings.append(
            "Strike TOT reachability: no ScenEdit_SetTime StartTime — cannot compare "
            "implied takeoff times to scenario start."
        )
        start_min = tot_min

    min_feasible_tot = start_min
    min_feasible_reasons = []

    targets = _parse_strike_land_target_coords(content, mission_map)
    if not targets:
        warnings.append(
            "Strike TOT reachability: no strike target coordinates found — skipped distance checks."
        )
        return errors, warnings, ok

    consts = _parse_lua_coord_pairs(content)
    csg_anchor = _csg_anchor_point(content, ships, consts)
    if not csg_anchor:
        warnings.append("Strike TOT reachability: no CSG anchor — skipped carrier/TLAM checks.")
        csg_anchor = None

    tlam_launch = timing.get("tlam_launch_time")
    tlam_launch_min = _time_to_minutes(tlam_launch) if tlam_launch else None
    tlam_lead = (tot_min - tlam_launch_min) if tlam_launch_min is not None else None

    sead_takeoff = timing.get("sead_package_takeoff")
    sead_takeoff_min = _time_to_minutes(sead_takeoff) if sead_takeoff else None
    sead_lead = (tot_min - sead_takeoff_min) if sead_takeoff_min is not None else None

    staging_hosts = _parse_place_base_hosts(content)
    bomber_staging_refs = set()
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*\d+\s*,\s*'([^']+)'\s*,\s*([\w.]+)\.guid",
        re.IGNORECASE,
    )
    for match in wing_pattern.finditer(content):
        prefix = match.group(1).upper()
        aircraft_id = int(match.group(2))
        mission_name = match.group(3)
        host_ref = match.group(4)
        if _infer_mission_role(mission_name, mission_map) != "strike":
            continue
        if host_ref not in staging_hosts:
            continue
        is_bomber = "BUFF" in prefix or "B-52" in prefix
        if db is not None and series and version:
            name_u = _aircraft_name_upper(db, aircraft_id, series, version)
            is_bomber = is_bomber or _is_non_stealth_bomber_airframe(name_u)
        if is_bomber:
            bomber_staging_refs.add(host_ref)

    geo = _parse_geo_unit_positions(content)

    if csg_anchor and tlam_lead is None and not tlam_launch:
        ok.append(
            "OK: Strike TOT reachability — TLAM TOT-only sync (no tlam_launch_time); "
            "CMO schedules Tomahawk launch from range to TimeOnTargetStation."
        )

    if csg_anchor and tlam_lead is not None:
        tlam_origin = csg_anchor[:2]
        for ship in ships:
            if ship.get("var") == "bunker_hill" and ship.get("lat") is not None:
                tlam_origin = (ship["lat"], ship["lon"])
                break
        dist_nm, farthest = _max_distance_nm(tlam_origin, targets)
        if dist_nm is not None and farthest:
            required = _flight_minutes_for_nm(dist_nm, _TOMAHAWK_CRUISE_KTS)
            margin = tlam_lead - required
            label = farthest.get("name") or farthest.get("ref")
            if margin < -3:
                need_tot = tlam_launch_min + required + _TOT_REACH_MARGIN_WARN_MIN
                if need_tot > min_feasible_tot:
                    min_feasible_tot = need_tot
                    min_feasible_reasons.append(
                        f"TLAM cruise {required} min from launch {tlam_launch}"
                    )
                errors.append(
                    f"Strike TOT reachability: TLAM launch {tlam_launch} ({tlam_lead} min before TOT) "
                    f"is ~{-margin} min short for {dist_nm:.0f} nm to farthest target '{label}' "
                    f"(~{required} min at {_TOMAHAWK_CRUISE_KTS} kts). "
                    f"Raise strike_package_tot to at least "
                    f"{_minutes_to_hhmmss(need_tot)} or launch earlier."
                )
            elif margin < 3:
                warnings.append(
                    f"Strike TOT reachability: TLAM launch only {tlam_lead} min before TOT but "
                    f"~{required} min needed for {dist_nm:.0f} nm to '{label}' (margin {margin} min)."
                )
            else:
                ok.append(
                    f"OK: Strike TOT reachability — TLAM {tlam_lead} min lead covers "
                    f"{dist_nm:.0f} nm to '{label}' (~{required} min cruise)."
                )

    if csg_anchor:
        dist_nm, farthest = _max_distance_nm(csg_anchor[:2], targets)
        if dist_nm is not None and farthest:
            required = _flight_minutes_for_nm(
                dist_nm, _CARRIER_STRIKER_CRUISE_KTS, _CARRIER_STRIKE_OVERHEAD_MIN
            )
            window = tot_min - start_min
            margin = window - required
            label = farthest.get("name") or farthest.get("ref")
            if margin < _TOT_REACH_MARGIN_ERROR_MIN:
                need_tot = start_min + required + _TOT_REACH_MARGIN_WARN_MIN
                if need_tot > min_feasible_tot:
                    min_feasible_tot = need_tot
                    min_feasible_reasons.append(
                        f"carrier strike ~{required} min from H+0 to '{label}'"
                    )
                errors.append(
                    f"Strike TOT reachability: carrier package needs ~{required} min from "
                    f"scenario start {scenario_start} to TOT {strike_tot} for {dist_nm:.0f} nm "
                    f"to '{label}' (window {window} min). "
                    f"Raise strike_package_tot to at least {_minutes_to_hhmmss(need_tot)}."
                )
            elif margin < _TOT_REACH_MARGIN_WARN_MIN:
                warnings.append(
                    f"Strike TOT reachability: carrier strike tight — {window} min H+0 to TOT window, "
                    f"~{required} min needed to '{label}' ({margin} min margin)."
                )
            else:
                ok.append(
                    f"OK: Strike TOT reachability — carrier {window} min start to TOT covers "
                    f"{dist_nm:.0f} nm strike ({margin} min margin)."
                )

    points, _consts = _parse_reference_points_resolved(content)
    zones = _parse_mission_zone_map(content)
    sead_missions = [n for n, role in mission_map.items() if role == "sead"]
    if csg_anchor and sead_lead is not None and sead_missions:
        farthest_sead_nm = 0.0
        farthest_zone = None
        for mission_name in sead_missions:
            zone_names = zones.get(mission_name) or []
            centroid = _zone_centroid(zone_names, points)
            if not centroid:
                continue
            nm = _haversine_nm(csg_anchor[0], csg_anchor[1], centroid[0], centroid[1])
            if nm > farthest_sead_nm:
                farthest_sead_nm = nm
                farthest_zone = mission_name
        if farthest_zone and farthest_sead_nm > 0:
            transit = _flight_minutes_for_nm(farthest_sead_nm, _SEAD_TRANSIT_KTS, overhead_min=0)
            if sead_lead < transit - 15:
                errors.append(
                    f"Strike TOT reachability: SEAD takeoff {sead_takeoff} ({sead_lead} min before TOT) "
                    f"cannot reach '{farthest_zone}' (~{farthest_sead_nm:.0f} nm, ~{transit} min transit) "
                    "before strike time — SEAD will still be en route at TOT."
                )
            elif sead_lead < transit - 5:
                warnings.append(
                    f"Strike TOT reachability: SEAD {sead_lead} min before TOT is tight for "
                    f"~{farthest_sead_nm:.0f} nm to '{farthest_zone}' (~{transit} min transit)."
                )
            else:
                ok.append(
                    f"OK: Strike TOT reachability — SEAD {sead_lead} min lead vs "
                    f"~{transit} min transit to '{farthest_zone}'."
                )

    for host_ref in sorted(bomber_staging_refs):
        row = geo.get(host_ref)
        if not row:
            continue
        dist_nm, farthest = _max_distance_nm((row["lat"], row["lon"]), targets)
        if dist_nm is None or not farthest:
            continue
        required = _flight_minutes_for_nm(
            dist_nm, _BOMBER_TRANSIT_KTS, _BOMBER_STARTUP_OVERHEAD_MIN
        )
        window = tot_min - start_min
        margin = window - required
        label = farthest.get("name") or farthest.get("ref")
        host_name = row.get("name") or host_ref
        if margin < _TOT_REACH_MARGIN_ERROR_MIN:
            need_tot = start_min + required + _TOT_REACH_MARGIN_WARN_MIN
            if need_tot > min_feasible_tot:
                min_feasible_tot = need_tot
                min_feasible_reasons.append(
                    f"bomber '{host_name}' ~{required} min to '{label}'"
                )
            errors.append(
                f"Strike TOT reachability: B-52/CALCM from '{host_name}' needs ~{required} min to "
                f"launch standoff weapons at {dist_nm:.0f} nm ('{label}') but scenario window "
                f"{scenario_start} to {strike_tot} is only {window} min. "
                f"Raise strike_package_tot to at least {_minutes_to_hhmmss(need_tot)}."
            )
        elif margin < _TOT_REACH_MARGIN_WARN_MIN:
            warnings.append(
                f"Strike TOT reachability: bomber from '{host_name}' tight — {window} min window, "
                f"~{required} min needed for '{label}' ({margin} min margin). Verify ME flight plan takeoff."
            )
        else:
            ok.append(
                f"OK: Strike TOT reachability — bomber '{host_name}' {window} min window vs "
                f"~{required} min for {dist_nm:.0f} nm to '{label}'."
            )

    if min_feasible_reasons and tot_min < min_feasible_tot:
        suggested = _minutes_to_hhmmss(min_feasible_tot)
        errors.append(
            f"Strike TOT reachability: strike_package_tot={strike_tot} is too early — "
            f"minimum feasible TOT is {suggested} Z ({'; '.join(min_feasible_reasons)}). "
            "Update strike_package_tot / @strike_package / @naval_package, then run SetMission blocks."
        )
    elif min_feasible_reasons:
        ok.append(
            f"OK: Strike TOT reachability — strike_package_tot {strike_tot} meets computed minimum "
            f"{_minutes_to_hhmmss(min_feasible_tot)} Z."
        )

    return errors, warnings, ok

def _validate_carrier_strike_groups(content, db, series, version):
    errors = []
    warnings = []
    ok = []
    ships = _parse_ship_placements(content)
    if not ships:
        return errors, warnings, ok

    air_carrier_vars = _parse_carrier_vars_with_air_wing(content)
    by_side = {}
    for ship in ships:
        by_side.setdefault(ship["side"], []).append(ship)

    for side, side_ships in by_side.items():
        carriers = []
        escorts = []
        for ship in side_ships:
            role, sub = _classify_ship(db, ship["dbid"], series, version)
            ship["role"] = role
            ship["subtype"] = sub
            if role == "carrier":
                carriers.append(ship)
            elif role == "escort":
                escorts.append(ship)

        if not carriers:
            continue

        for carrier in carriers:
            if carrier.get("var"):
                if carrier["var"] not in air_carrier_vars:
                    continue
            elif not air_carrier_vars:
                continue

            nearby = [
                esc
                for esc in escorts
                if _approx_deg_distance(
                    carrier["lat"], carrier["lon"], esc["lat"], esc["lon"]
                )
                <= _CSG_ESCORT_MAX_DEG_DISTANCE
            ]
            cvn_like = carrier.get("subtype") == "cvn"
            min_error = 1 if carrier.get("subtype") == "amphib" else _CSG_MIN_ESCORTS_ERROR
            min_warn = 2 if carrier.get("subtype") == "amphib" else _CSG_MIN_ESCORTS_WARN
            label = carrier.get("name") or f"ship DBID {carrier['dbid']}"

            if len(nearby) < min_error:
                errors.append(
                    f"Carrier strike group: side '{side}' has carrier '{label}' with air wing "
                    f"but only {len(nearby)} surface escort(s) within ~{_CSG_ESCORT_MAX_DEG_DISTANCE}° "
                    f"(need at least {min_error} for "
                    f"{'CVN/CV' if cvn_like else 'amphib'} ops). Add DDG/CG near the carrier."
                )
            elif len(nearby) < min_warn:
                warnings.append(
                    f"Carrier strike group: '{label}' has {len(nearby)} nearby escort(s); "
                    f"typical CSG has {min_warn}+ (e.g. 1× CG and 2× DDG)."
                )
            else:
                ok.append(
                    f"OK: CSG '{label}' on '{side}' with {len(nearby)} nearby surface escort(s)."
                )

            far_escorts = len(escorts) - len(nearby)
            if far_escorts > 0 and len(nearby) >= min_error:
                warnings.append(
                    f"Carrier strike group: {far_escorts} escort(s) on '{side}' are placed far from "
                    f"carrier '{label}' (>{_CSG_ESCORT_MAX_DEG_DISTANCE}°); group them with the CSG."
                )

    air_carrier_vars = _parse_carrier_vars_with_air_wing(content)
    form_errors, form_warnings, form_ok = _validate_csg_formation(content, air_carrier_vars)
    errors.extend(form_errors)
    warnings.extend(form_warnings)
    ok.extend(form_ok)

    return errors, warnings, ok

def _validate_sead_mission_design(content, mission_map, mission_zones, assignments, db, series, version):
    errors = []
    warnings = []
    ok = []

    sead_missions = {name for name, role in mission_map.items() if role == "sead"}
    ref_points = _parse_reference_points(content)
    all_sam_sites = _parse_sam_sites(content)
    hostile_postures = _parse_hostile_postures(content)
    sead_sides = _sides_with_sead_missions(mission_map, assignments)
    sam_sites = []
    for sead_side in sead_sides:
        sam_sites.extend(_enemy_sam_sites_for_sead_side(sead_side, all_sam_sites, hostile_postures))
    if sead_missions and not sam_sites and all_sam_sites:
        sam_sites = [(lat, lon) for _side, lat, lon in all_sam_sites]
    mission_wcs = _parse_mission_land_wcs_overrides(content)
    side_land_wcs = _parse_side_land_wcs(content)

    for name, role in mission_map.items():
        upper = name.upper()
        if "SEAD" not in upper and "WILD WEASEL" not in upper and "IRON HAND" not in upper:
            continue
        if "ESCORT" in upper and role == "aaw":
            continue
        if role == "strike":
            errors.append(
                f"SEAD mission type: '{name}' is declared as Strike; use Patrol with type='SEAD'."
            )
        elif role != "sead":
            errors.append(
                f"SEAD mission type: '{name}' must be ScenEdit_AddMission(..., 'Patrol', {{type='SEAD', zone={{...}}}})."
            )

    for name in sead_missions:
        if name not in mission_zones or not mission_zones[name]:
            warnings.append(
                f"SEAD zone: mission '{name}' has no parseable zone={{...}} reference points in Lua."
            )

    sead_bboxes = []
    for name in sead_missions:
        rp_names = mission_zones.get(name, [])
        bbox = _bbox_for_zone(rp_names, ref_points)
        if bbox:
            sead_bboxes.append((name, bbox))
        elif rp_names:
            warnings.append(
                f"SEAD zone: mission '{name}' references unknown RPs: "
                f"{', '.join(n for n in rp_names if n not in ref_points)}"
            )

    if sam_sites and sead_bboxes:
        uncovered = []
        for idx, (lat, lon) in enumerate(sam_sites, start=1):
            if not any(_point_in_bbox(lat, lon, bbox) for _n, bbox in sead_bboxes):
                uncovered.append((idx, lat, lon))
        zone_names = ", ".join(n for n, _ in sead_bboxes)
        if len(uncovered) == len(sam_sites):
            errors.append(
                f"SEAD zone coverage: all {len(sam_sites)} hostile SAM site(s) lie outside Patrol/SEAD "
                f"zone(s) ({zone_names})."
            )
        elif uncovered:
            sample = "; ".join(
                f"#{idx} {lat},{lon}" for idx, lat, lon in uncovered[:3]
            )
            if len(uncovered) > 3:
                sample += f"; +{len(uncovered) - 3} more"
            warnings.append(
                f"SEAD zone coverage: {len(uncovered)}/{len(sam_sites)} hostile SAM site(s) outside "
                f"Patrol/SEAD zone(s) ({zone_names}): {sample}."
            )
        else:
            ok.append(
                f"OK: All {len(sam_sites)} hostile SAM site(s) fall inside at least one SEAD patrol zone."
            )
    elif sam_sites and not sead_bboxes:
        warnings.append(
            "SEAD zone coverage: SAM sites present in Lua but no SEAD patrol zones could be validated."
        )

    shooters_by_side = {}
    aa_only_on_sead = []
    for side, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if aircraft_id == 0 or mission_name not in sead_missions or escort_flag is True:
            continue
        has_sead = _loadout_has_sead_role(db, loadout_id, series, version)
        loadout_query = "SELECT Name FROM DataLoadout WHERE ID = ?"
        loadout_params = [loadout_id]
        loadout_query, loadout_params = db.append_meta_filters(loadout_query, loadout_params)
        loadout_row = db.cursor.execute(loadout_query, loadout_params).fetchone()
        roles = _loadout_roles(loadout_row[0]) if loadout_row else set()
        if has_sead:
            shooters_by_side[side or "?"] = shooters_by_side.get(side or "?", 0) + 1
        elif "aaw" in roles and "sead" not in roles:
            aa_only_on_sead.append((aircraft_id, mission_name))

    for aircraft_id, mission_name in aa_only_on_sead:
        errors.append(
            f"SEAD shooter loadout: aircraft {aircraft_id} on Patrol/SEAD mission '{mission_name}' "
            "uses A/A-only loadout; assign ARM/SEAD loadouts to the SEAD mission and keep escort on a separate AAW patrol."
        )

    if sam_sites:
        min_shooters = max(2, math.ceil(len(sam_sites) / 2))
        total_shooters = sum(shooters_by_side.values())
        if total_shooters < min_shooters:
            errors.append(
                f"SEAD capacity: {total_shooters} ARM/SEAD shooter assignment(s) for {len(sam_sites)} "
                f"SAM site(s); need at least {min_shooters} (ceil(SAM/2), minimum 2)."
            )
        elif total_shooters < len(sam_sites):
            warnings.append(
                f"SEAD capacity: {total_shooters} shooter(s) for {len(sam_sites)} SAM site(s); "
                "prefer at least one SEAD flight per SAM belt or per site in dense IADS."
            )
        else:
            ok.append(
                f"OK: SEAD shooter count ({total_shooters}) meets or exceeds SAM site count ({len(sam_sites)})."
            )
    elif sead_missions and sum(shooters_by_side.values()) == 0:
        warnings.append(
            "SEAD capacity: Patrol/SEAD mission(s) exist but no ARM/SEAD loadout assignments were detected."
        )

    if side_land_wcs == 1 and sead_missions:
        for mission_name in sead_missions:
            if mission_wcs.get(mission_name) != 0:
                warnings.append(
                    f"SEAD ROE: side uses WCS TIGHT on land (weapon_control_status_land=1) but mission "
                    f"'{mission_name}' does not override with weapon_control_status_land=0 (FREE); "
                    "HARM launches against passive SAMs may be blocked."
                )
        for mission_name in sead_missions:
            if mission_wcs.get(mission_name) == 0:
                ok.append(f"OK: SEAD mission '{mission_name}' sets land WCS FREE for emitter engagements.")
                break

    if sead_missions and not errors:
        ok.append(f"OK: {len(sead_missions)} Patrol/SEAD mission(s) declared with correct mission class.")

    return errors, warnings, ok

def _validate_no_nuclear_weapons(content, unique_pairs, ships, db, series, version):
    errors = []
    warnings = []
    ok = []

    if _parse_scenario_policy_nuclear(content):
        ok.append("OK: Nuclear policy — @scenario_policy nuclear=true (checks skipped).")
        return errors, warnings, ok

    sides_in_scenario = set(re.findall(r"ScenEdit_AddSide\s*\(\s*\{[^}]*side\s*=\s*'([^']+)'", content))
    nuc_doctrine = _parse_use_nuclear_weapons_doctrine(content)
    for side in sorted(sides_in_scenario):
        if side not in nuc_doctrine:
            warnings.append(
                f"Nuclear policy: side '{side}' has no use_nuclear_weapons='No' in ScenEdit_SetDoctrine — "
                "CMO may allow nuclear release by default."
            )
        elif nuc_doctrine[side] is not False:
            errors.append(
                f"Nuclear policy: side '{side}' must set use_nuclear_weapons='No' for conventional scenarios."
            )
    if sides_in_scenario and all(nuc_doctrine.get(s) is False for s in sides_in_scenario):
        ok.append(
            "OK: Nuclear policy — all sides set use_nuclear_weapons='No' in doctrine."
        )

    if not re.search(
        r"function\s+(?:M\.)?strip_nuclear_from_unit\s*\(", content, re.IGNORECASE
    ) and not re.search(r"strip_nuclear_from_unit\s*=\s*cmo\.strip_nuclear_from_unit", content, re.IGNORECASE):
        warnings.append(
            "Nuclear policy: no strip_nuclear_from_unit() — ship VLS may still list TLAM-N until stripped at runtime."
        )
    elif not re.search(r"strip_nuclear_from_unit\s*\(", content, re.IGNORECASE):
        warnings.append(
            "Nuclear policy: strip_nuclear_from_unit() defined but never called on placed ships."
        )
    else:
        ok.append("OK: Nuclear policy — strip_nuclear_from_unit() present and called.")
        if re.search(
            r"NUCLEAR_WEAPON_DBIDS|NUCLEAR_CRUISE_DBIDS|conventional_tlam_dbid",
            content,
            re.IGNORECASE,
        ):
            ok.append(
                "OK: Nuclear policy — DB-derived nuclear dbid sets (warhead Type 4001) in bootstrap."
            )

    checked_loadouts = set()
    for aircraft_id, loadout_id in unique_pairs:
        if loadout_id in checked_loadouts:
            continue
        checked_loadouts.add(loadout_id)
        loadout_name = _loadout_name_upper(db, loadout_id, series, version)
        if _is_nuclear_loadout_name(loadout_name):
            errors.append(
                f"Nuclear loadout: aircraft {aircraft_id} uses loadout {loadout_id} "
                f"('{loadout_name}') — pick a conventional loadout (CALCM/JDAM/JSOW, not ALCM/TLAM-N/nuclear)."
            )
            continue
        required_hits = _loadout_nuclear_weapon_hits(
            db, loadout_id, series, version, loadout_name, required_only=True
        )
        optional_hits = _loadout_nuclear_weapon_hits(
            db, loadout_id, series, version, loadout_name, required_only=False
        )
        optional_only = [h for h in optional_hits if h not in required_hits]
        for wname, _optional in required_hits:
            errors.append(
                f"Nuclear loadout: loadout {loadout_id} ('{loadout_name}') requires nuclear weapon "
                f"'{wname}' — use a different loadout ID."
            )
        for wname, _optional in optional_only:
            warnings.append(
                f"Nuclear loadout: loadout {loadout_id} ('{loadout_name}') lists optional nuclear "
                f"weapon '{wname}' (usually not mounted)."
            )

    if checked_loadouts and not any("Nuclear loadout:" in e for e in errors):
        ok.append(
            f"OK: Nuclear loadout check — {len(checked_loadouts)} unique loadout(s) have no required nuclear stores."
        )

    # Ship DB templates: warn if default magazines include nuclear (Lua strip should run at runtime).
    from db_nuclear import weapon_dbid_is_nuclear

    for ship in ships:
        if ship.get("kind") == "sub":
            continue
        role, _ = _classify_ship(db, ship["dbid"], series, version)
        if role not in ("carrier", "escort"):
            continue
        weapons_info = get_unit_weapons(
            ship["dbid"], "DataShip", series=series, version=version, db_path=db.path
        )
        if not weapons_info:
            continue
        nuc_weapons = []
        for bucket in ("magazines", "mounts"):
            for mount in weapons_info.get(bucket, []):
                for w in mount.get("weapons", []):
                    wdbid = w[0] if w else None
                    wname = w[1] if len(w) > 1 else None
                    if wdbid and weapon_dbid_is_nuclear(db, wdbid, series, version):
                        nuc_weapons.append(wname or f"ID {wdbid}")
                    elif wname and _is_nuclear_missile_store_for_ship(wname):
                        nuc_weapons.append(wname)
        if nuc_weapons:
            label = ship.get("name") or f"DBID {ship['dbid']}"
            warnings.append(
                f"Nuclear magazine (DB default): ship '{label}' DB lists nuclear-capable stores "
                f"(e.g. {nuc_weapons[0]}) — ensure strip_nuclear_from_unit() runs after spawn (replaces cruise with UGM-109 TLAM)."
            )

    return errors, warnings, ok

def _validate_operator_country_oob(content, assignments, naval_units, db, series, version):
    """
    OperatorCountry vs Lua side (skills_cmo nationaliteit). Catches Soviet hulls on Cuba side, etc.
    """
    errors = []
    warnings = []
    ok = []
    checked = set()
    ok_logged = False

    def check_unit(side, table, unit_id, label):
        nonlocal ok_logged
        key = (side, table, unit_id)
        if key in checked:
            return
        checked.add(key)
        op_id, op_desc = _unit_operator_description(db, table, unit_id, series, version)
        if op_id is None and not op_desc:
            warnings.append(
                f"Operator country: no OperatorCountry for {label} (ID {unit_id}, {table})."
            )
            return
        if not _side_matches_operator_country(side, op_desc):
            errors.append(
                f"Operator country: side '{side}' hosts '{label}' (ID {unit_id}) with "
                f"OperatorCountry '{op_desc}' — use a DB entry operated by that side."
            )
            return
        if _is_placeholder_operator(op_desc):
            if _spawn_has_operator_last_resort(content, label, unit_id):
                ok.append(
                    f"OK: Operator last resort — '{label}' (ID {unit_id}) uses '{op_desc}' "
                    f"with documented @operator_last_resort."
                )
            else:
                alts = _national_operator_alternatives(
                    db, table, unit_id, series, version
                )
                if alts:
                    warnings.append(
                        f"Operator country: '{label}' (ID {unit_id}) uses placeholder "
                        f"OperatorCountry '{op_desc}' but national/NATO variants exist: "
                        f"{', '.join(alts)}. Prefer those; Junkyard/Generic only as last "
                        f"resort (add -- @operator_last_resort if truly unavoidable)."
                    )
                else:
                    warnings.append(
                        f"Operator country: '{label}' (ID {unit_id}) uses placeholder "
                        f"OperatorCountry '{op_desc}' — no national variant found in DB; "
                        f"acceptable last resort. Document why in the scenario header and "
                        f"add -- @operator_last_resort on the spawn line."
                    )
        if not ok_logged:
            ok_logged = True

    for unit in naval_units:
        table = "DataSubmarine" if unit.get("kind") == "sub" else "DataShip"
        label = unit.get("name") or f"ID {unit['dbid']}"
        check_unit(unit["side"], table, unit["dbid"], label)

    seen_air = set()
    for side, aircraft_id, _loadout_id, _mission_name, _escort_flag in assignments:
        if not side or aircraft_id == 0 or aircraft_id in seen_air:
            continue
        seen_air.add(aircraft_id)
        name, _, _, _ = _unit_service_record(db, "DataAircraft", aircraft_id, series, version)
        check_unit(side, "DataAircraft", aircraft_id, name or f"aircraft {aircraft_id}")

    if not errors and ok_logged:
        ok.append(
            "OK: OperatorCountry matches scenario side for placed naval units and spawned aircraft."
        )
    return errors, warnings, ok

# Helper call -> DB table for declared-nationality lookups.
_NATIONALITY_SPAWN_PATTERNS = (
    # spawn_air_wing('side', 'prefix', count, dbid, ...)
    (
        "DataAircraft",
        re.compile(
            r"spawn_air_wing\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*\d+\s*,\s*(\d+)",
            re.IGNORECASE,
        ),
    ),
    # add_air_unit_checked('side', 'name', dbid, ...)
    (
        "DataAircraft",
        re.compile(
            r"add_air_unit_checked\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)",
            re.IGNORECASE,
        ),
    ),
    # place_ship('side', 'name', dbid, ...)
    (
        "DataShip",
        re.compile(
            r"place_ship\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)", re.IGNORECASE
        ),
    ),
    # place_sub('side', 'name', dbid, ...)
    (
        "DataSubmarine",
        re.compile(
            r"place_sub\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)", re.IGNORECASE
        ),
    ),
    # place_sam('side', 'name', dbid, ...)
    (
        "DataFacility",
        re.compile(
            r"place_sam\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)", re.IGNORECASE
        ),
    ),
)

_NATIONALITY_ANNOTATION_RE = re.compile(
    r"--\s*@nationality\s+([^\n]+?)\s*$", re.IGNORECASE
)
_EXPORT_PROXY_ANNOTATION_RE = re.compile(
    r"--\s*@export_proxy\s+([^\n]+?)\s*$", re.IGNORECASE
)
_OPERATOR_LAST_RESORT_RE = re.compile(
    r"--\s*@operator_last_resort\b", re.IGNORECASE
)


def _annotation_on_line_or_prev(lines, idx, pattern):
    """Return first capture from pattern on line idx or the preceding comment line."""
    m = pattern.search(lines[idx])
    if m:
        return m.group(1).strip()
    if idx > 0 and lines[idx - 1].strip().startswith("--"):
        m = pattern.search(lines[idx - 1])
        if m:
            return m.group(1).strip()
    return None


def _line_has_operator_last_resort(lines, idx):
    if _OPERATOR_LAST_RESORT_RE.search(lines[idx]):
        return True
    if idx > 0 and lines[idx - 1].strip().startswith("--"):
        return bool(_OPERATOR_LAST_RESORT_RE.search(lines[idx - 1]))
    return False


def _spawn_has_operator_last_resort(content, label, unit_id):
    """True when the place/spawn line for this dbid carries @operator_last_resort."""
    patterns = [
        rf"place_(?:ship|sub|sam)\s*\([^)]*'{re.escape(label)}'[^)]*,\s*{unit_id}\b",
        rf"add_air_unit_checked\s*\([^)]*'{re.escape(label)}'[^)]*,\s*{unit_id}\b",
        rf"spawn_air_wing\s*\([^)]*,\s*{unit_id}\s*,",
    ]
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if not any(re.search(p, line, re.IGNORECASE) for p in patterns):
            continue
        if _line_has_operator_last_resort(lines, idx):
            return True
    return False


def _parse_declared_nationalities(content):
    """
    Find spawn/place calls carrying an inline `-- @nationality <Country>` annotation.

    Returns list of (table, dbid, label, declared_nationality, line_no, export_proxy).
    Annotations may sit on the same line as the call or on comment-only lines directly above.
    """
    lines = content.splitlines()
    decl_on_line = [None] * len(lines)
    proxy_on_line = [None] * len(lines)
    for idx, line in enumerate(lines):
        m = _NATIONALITY_ANNOTATION_RE.search(line)
        if m:
            decl_on_line[idx] = m.group(1).strip()
        m = _EXPORT_PROXY_ANNOTATION_RE.search(line)
        if m:
            proxy_on_line[idx] = m.group(1).strip()

    results = []
    for idx, line in enumerate(lines):
        for table, pattern in _NATIONALITY_SPAWN_PATTERNS:
            m = pattern.search(line)
            if not m:
                continue
            label = m.group(1)
            dbid = int(m.group(2))
            declared = _annotation_on_line_or_prev(lines, idx, _NATIONALITY_ANNOTATION_RE)
            if declared is None and idx > 0:
                prev = lines[idx - 1].strip()
                if prev.startswith("--") and decl_on_line[idx - 1]:
                    declared = decl_on_line[idx - 1]
            export_proxy = _annotation_on_line_or_prev(lines, idx, _EXPORT_PROXY_ANNOTATION_RE)
            if export_proxy is None and idx > 0:
                prev = lines[idx - 1].strip()
                if prev.startswith("--") and proxy_on_line[idx - 1]:
                    export_proxy = proxy_on_line[idx - 1]
            if declared:
                results.append((table, dbid, label, declared, idx + 1, export_proxy))
    return results


def _validate_declared_nationality(content, db, series, version):
    """
    Cross-check inline `-- @nationality <Country>` annotations against the DB
    OperatorCountry of each spawned/placed unit. Catches e.g. a Norwegian hull
    labelled as Dutch on a coalition side (where the side name cannot enforce it).
    """
    errors = []
    warnings = []
    ok = []

    declared_units = _parse_declared_nationalities(content)
    if not declared_units:
        warnings.append(
            "Nationality: no '-- @nationality <Country>' annotations found — add them on "
            "spawn_air_wing/add_air_unit_checked/place_ship/place_sub/place_sam lines so "
            "preflight can verify each hull's DB OperatorCountry (coalition sides cannot)."
        )
        return errors, warnings, ok

    direct_match = 0
    export_proxy_ok = 0
    for table, dbid, label, declared, line_no, export_proxy in declared_units:
        _op_id, op_desc = _unit_operator_description(db, table, dbid, series, version)
        if not op_desc:
            warnings.append(
                f"Nationality: no OperatorCountry in DB for {label} (ID {dbid}, {table}, "
                f"line {line_no}) — cannot verify declared '{declared}'."
            )
            continue
        if _operator_desc_matches_nationality(declared, op_desc):
            direct_match += 1
            continue
        if export_proxy and _operator_desc_matches_nationality(export_proxy, op_desc):
            export_proxy_ok += 1
            ok.append(
                f"OK: Export proxy — '{label}' (ID {dbid}, line {line_no}): "
                f"@nationality {declared} uses DB entry operated by '{op_desc}' "
                f"(@export_proxy {export_proxy})."
            )
            continue
        if _is_placeholder_operator(op_desc):
            alts = [
                a for a in _national_operator_alternatives(db, table, dbid, series, version)
                if declared.lower() in a.lower()
                or _normalize_nationality(declared) in _normalize_nationality(a).lower()
            ]
            alt_hint = f" Prefer: {', '.join(alts)}." if alts else ""
            warnings.append(
                f"Nationality: {label} (ID {dbid}, line {line_no}) is Junkyard/Generic "
                f"— cannot verify '@nationality {declared}'.{alt_hint} Use a national "
                f"DBID when available; else @export_proxy <supplier> or @operator_last_resort."
            )
        else:
            errors.append(
                f"Nationality mismatch: {label} (ID {dbid}, {table}, line {line_no}) is "
                f"operated by '{op_desc}' in the DB but declared '@nationality {declared}'. "
                f"Pick a DB entry operated by {declared}, add @export_proxy <exporter> if "
                f"the DB only lists the supplying nation, or correct the annotation."
            )
    has_mismatch = any(e.startswith("Nationality mismatch") for e in errors)
    if direct_match and not has_mismatch:
        ok.append(
            f"OK: Nationality — {direct_match} annotated unit(s) match their DB OperatorCountry."
        )
    if export_proxy_ok and not has_mismatch:
        ok.append(
            f"OK: Export proxy — {export_proxy_ok} unit(s) use supplier DBIDs with "
            f"documented @export_proxy."
        )
    return errors, warnings, ok


_CIV_SIDE_RE = re.compile(
    r"ScenEdit_AddSide\s*\(\s*\{[^}]*?side\s*=\s*'([^']*)'", re.IGNORECASE
)
_ADDUNIT_BLOCK_RE = re.compile(
    r"ScenEdit_AddUnit\s*\(\s*\{(.*?)\}\s*\)", re.IGNORECASE | re.DOTALL
)


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


def _validate_reference_points(content):
    """
    CMO requires side= on every ScenEdit_AddReferencePoint (RPs are per-side).
    Mission patrol zones must reference RPs created on the same side as the mission.
    """
    errors = []
    warnings = []
    ok = []

    rp_calls = _parse_reference_point_calls(content)
    if not rp_calls:
        return errors, warnings, ok

    added_sides, _referenced_sides = _parse_scenario_sides(content)
    missing_side = [r for r in rp_calls if not r["has_side"]]
    for row in missing_side:
        label = row["name"] or "(unnamed)"
        errors.append(
            f"Reference point: '{label}' at line {row['line']} has no side= in "
            "ScenEdit_AddReferencePoint — CMO reports Missing 'Side' "
            "(choose PlayerSide or a side from ScenEdit_AddSide)."
        )

    unresolved_side = [
        r for r in rp_calls if r["has_side"] and not r["side"]
    ]
    for row in unresolved_side:
        label = row["name"] or "(unnamed)"
        errors.append(
            f"Reference point: '{label}' at line {row['line']} has side= but the "
            "value is not a string literal or local SIDE_* alias — preflight cannot verify it."
        )

    for row in rp_calls:
        if not row["side"] or not row["has_side"]:
            continue
        if added_sides and row["side"] not in added_sides:
            label = row["name"] or "(unnamed)"
            errors.append(
                f"Reference point: '{label}' at line {row['line']} uses side='{row['side']}' "
                "but that side has no ScenEdit_AddSide — CMO cannot resolve the side."
            )
        elif added_sides and row["line"] < added_sides[row["side"]]:
            label = row["name"] or "(unnamed)"
            errors.append(
                f"Reference point: '{label}' at line {row['line']} is created before "
                f"ScenEdit_AddSide for '{row['side']}' at line {added_sides[row['side']]}."
            )

    rp_index = _reference_points_by_side_name(content)
    for side, mission, zone_names in _parse_mission_side_zones(content):
        for rp_name in zone_names:
            if (side, rp_name) not in rp_index:
                errors.append(
                    f"Reference point: mission '{mission}' on side '{side}' uses zone RP "
                    f"'{rp_name}' but no ScenEdit_AddReferencePoint declares "
                    f"{{ side='{side}', name='{rp_name}', ... }} — zones are per-side in CMO."
                )

    if not missing_side and not unresolved_side:
        declared = len([r for r in rp_calls if r["has_side"] and r["side"]])
        if declared:
            ok.append(
                f"OK: Reference points — {declared} AddReferencePoint call(s) declare side=."
            )
        zone_checks = _parse_mission_side_zones(content)
        if zone_checks and not any(
            e.startswith("Reference point: mission") for e in errors
        ):
            ok.append(
                f"OK: Reference points — mission zone RPs match side-tagged AddReferencePoint "
                f"({len(zone_checks)} zoned mission(s))."
            )

    return errors, warnings, ok


def _validate_civilian_flight_paths(content):
    """
    Civilian air traffic must have realistic flight paths (logic_checks §11): a plotted
    `course` that exits the area (transit, majority) or `base`+`rtb` to land (small minority).
    Civilian air added with only heading/speed loiters/circles aimlessly — flag it.
    """
    errors = []
    warnings = []
    ok = []

    civ_sides = {
        s for s in _CIV_SIDE_RE.findall(content) if "civ" in s.lower()
    }
    if not civ_sides:
        return errors, warnings, ok

    def block_is_civ_air(block):
        has_air = re.search(r"type\s*=\s*'Air'", block, re.IGNORECASE)
        if not has_air:
            return False
        return any(
            re.search(r"side\s*=\s*'" + re.escape(side) + r"'", block, re.IGNORECASE)
            for side in civ_sides
        )

    has_civ_air = any(
        block_is_civ_air(m.group(1)) for m in _ADDUNIT_BLOCK_RE.finditer(content)
    )
    uses_civilian_helper = re.search(
        r"\b(?:cmo\.)?add_civilian_airliner\s*\(", content
    ) is not None
    if not has_civ_air and not uses_civilian_helper:
        return errors, warnings, ok
    if not has_civ_air:
        has_civ_air = uses_civilian_helper

    if uses_civilian_helper:
        ok.append(
            "OK: Civilian flight paths — add_civilian_airliner sets theater exit course or RTB "
            "(logic_checks_cmo.md §11)."
        )
        return errors, warnings, ok

    has_course = re.search(r"\bcourse\s*=", content) is not None
    has_landing = re.search(r"\brtb\s*=\s*true\b", content, re.IGNORECASE) is not None

    if not has_course and not has_landing:
        warnings.append(
            "Civilian flight paths: civilian air traffic has no plotted 'course' and no "
            "'base'+'rtb' — aircraft fly straight, then loiter/circle aimlessly. Give transit "
            "flights a course (final waypoint outside the area) and land only a small portion "
            "(base+rtb to a same-side civilian airfield). See logic_checks_cmo.md §11."
        )
        return errors, warnings, ok

    ok.append(
        "OK: Civilian flight paths — plotted course and/or RTB landing present "
        "(no aimless-loiter antipattern)."
    )
    if has_landing and not has_course:
        warnings.append(
            "Civilian flight paths: RTB/landing present but no plotted transit 'course' — most "
            "civilian flights should be overflights that exit the area; only a small portion "
            "should land (logic_checks_cmo.md §11)."
        )
    return errors, warnings, ok

def _validate_era_appropriate_oob(scenario_year, assignments, ships, db, series, version):
    """
    Generic era fit: DB service dates vs scenario_year. Does not prescribe specific DBIDs.
    """
    errors = []
    warnings = []
    ok = []
    if not scenario_year:
        warnings.append(
            "Era fit: no scenario_year in Lua — era checks skipped. "
            "Set e.g. local scenario_year = 2026 for time-appropriate validation."
        )
        return errors, warnings, ok

    issues = 0
    seen_air = set()
    for _side, aircraft_id, _loadout_id, _mission_name, _escort_flag in assignments:
        if aircraft_id == 0 or aircraft_id in seen_air:
            continue
        seen_air.add(aircraft_id)
        name, commissioned, decommissioned, _ = _unit_service_record(
            db, "DataAircraft", aircraft_id, series, version
        )
        if not name:
            continue
        if commissioned and commissioned > scenario_year:
            errors.append(
                f"Era fit ({scenario_year}): aircraft '{name}' (ID {aircraft_id}) "
                f"enters service in {commissioned}."
            )
            issues += 1
        elif decommissioned and decommissioned < scenario_year:
            warnings.append(
                f"Era fit ({scenario_year}): aircraft '{name}' (ID {aircraft_id}) "
                f"is marked out of service in DB from {decommissioned}."
            )
            issues += 1

    seen_naval = set()
    for unit in ships:
        unit_id = unit.get("dbid")
        if not unit_id or unit_id in seen_naval:
            continue
        seen_naval.add(unit_id)
        table = "DataSubmarine" if unit.get("kind") == "sub" else "DataShip"
        name, commissioned, decommissioned, _ = _unit_service_record(
            db, table, unit_id, series, version
        )
        if not name:
            continue
        label = unit.get("name") or name
        kind = "submarine" if unit.get("kind") == "sub" else "ship"
        if commissioned and commissioned > scenario_year:
            errors.append(
                f"Era fit ({scenario_year}): {kind} '{label}' (ID {unit_id}) "
                f"enters service in {commissioned}."
            )
            issues += 1
        elif decommissioned and decommissioned < scenario_year:
            warnings.append(
                f"Era fit ({scenario_year}): {kind} '{label}' (ID {unit_id}) "
                f"is marked out of service in DB from {decommissioned}."
            )
            issues += 1

    if not issues and (seen_air or seen_naval):
        ok.append(
            f"OK: Era fit — assigned platforms match scenario_year {scenario_year} "
            "(DB YearCommissioned / YearDecommissioned)."
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

def _validate_strike_flight_profile_and_timing(
    content, assignments, mission_map, ships, ship_strike_assigns, db, series, version
):
    """
    Standoff loadouts need standoff flight profiles/plans; strike waves need aligned TOT offsets.
    Uses @strike_package / @strike_wave annotations and CreateMissionFlightPlan when present.
    """
    errors = []
    warnings = []
    ok = []
    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    if not strike_missions:
        return errors, warnings, ok

    packages, waves = _parse_strike_package_annotations(content)
    flight_plans = _parse_mission_flight_plan_calls(content)
    ships_on_strike = {m for _v, m in ship_strike_assigns}

    package_by_mission = {p.get("mission"): p for p in packages if p.get("mission")}

    for mission_name in strike_missions:
        declared = (package_by_mission.get(mission_name) or {}).get("profile", "").lower()
        inferred = _strike_mission_loadout_profile(db, assignments, mission_name, series, version)
        has_naval = mission_name in ships_on_strike
        default_mission = packages[-1].get("mission") if packages else None
        mission_waves = [
            w
            for w in waves
            if (w.get("mission") or default_mission) == mission_name
        ]
        mission_fps = [fp for fp in flight_plans if fp[1] == mission_name]
        weapon_state = _parse_strike_weapon_state_planned(content, mission_name)

        if inferred in ("standoff", "mixed") or declared == "standoff":
            if declared == "penetration":
                errors.append(
                    f"Strike flight profile: mission '{mission_name}' loadouts are standoff-class "
                    f"but @strike_package profile=penetration (expects ingress over target / dumb-bomb paths)."
                )
            elif declared != "standoff" and inferred == "standoff":
                warnings.append(
                    f"Strike flight profile: mission '{mission_name}' uses standoff munitions — add "
                    f"'-- @strike_package mission={mission_name} profile=standoff time=HH:MM:SS date=YYYY/MM/DD' "
                    "and ScenEdit_CreateMissionFlightPlan after OOB; regenerate paths in ME if still penetration."
                )
            if not mission_fps:
                warnings.append(
                    f"Strike flight plan: mission '{mission_name}' has no ScenEdit_CreateMissionFlightPlan — "
                    "aircraft may keep legacy penetration waypoints. Add TIMEONTARGET aligned to strike waves."
                )
            ws_upper = (weapon_state or "").upper()
            if weapon_state and not any(m in ws_upper for m in _STANDOFF_WEAPON_STATE_MARKERS):
                warnings.append(
                    f"Strike doctrine: mission '{mission_name}' uses standoff loadouts but "
                    f"weapon_state_planned='{weapon_state}' (prefer ShotgunOneEngagementBVR / ShotgunBVR for SO)."
                )

        if declared == "standoff" and inferred == "penetration":
            errors.append(
                f"Strike flight profile: mission '{mission_name}' declares profile=standoff but "
                "striker loadouts are penetration/dumb-only."
            )

        if mission_waves:
            try:
                offsets = [int(w.get("offset", w.get("offset_minutes", "0"))) for w in mission_waves]
            except ValueError:
                offsets = []
            if offsets:
                max_spread = 15
                pkg = package_by_mission.get(mission_name) or {}
                if pkg.get("max_spread"):
                    try:
                        max_spread = int(pkg["max_spread"])
                    except ValueError:
                        pass
                spread = max(offsets) - min(offsets)
                if spread > max_spread:
                    errors.append(
                        f"Strike timing: mission '{mission_name}' wave offsets span {spread} min "
                        f"(max_spread={max_spread}). Align TLAM, carrier strike, and B-52 CALCM to the same TOT window."
                    )
                elif spread > 0:
                    ok.append(
                        f"OK: Strike timing '{mission_name}' wave offsets within {spread} min (limit {max_spread})."
                    )
                else:
                    ok.append(
                        f"OK: Strike timing '{mission_name}' — all @strike_wave offsets at same TOT (0 spread)."
                    )

                naval = [w for w in mission_waves if "naval" in w.get("role", "")]
                air_standoff = [w for w in mission_waves if "standoff" in w.get("role", "")]
                air_strike = [w for w in mission_waves if w.get("role", "") in ("air_strike", "air")]
                if naval and (air_strike or air_standoff):
                    n_off = int(naval[0].get("offset", 0))
                    a_off = int((air_strike or air_standoff)[0].get("offset", 0))
                    if n_off + 30 < a_off:
                        warnings.append(
                            f"Strike timing: mission '{mission_name}' TLAM wave offset ({n_off}) is "
                            f"much earlier than air ({a_off}) — Tomahawks may impact long before air ordnance. "
                            "Raise air offset or delay naval fire via events to match TOT."
                        )

        tot_times = {fp[3] for fp in mission_fps if fp[3]}
        if len(tot_times) > 1:
            errors.append(
                f"Strike timing: mission '{mission_name}' has multiple TIMEONTARGET values {sorted(tot_times)} — "
                "use one synchronized TOT for all air strikers on the same package."
            )
        elif len(tot_times) == 1 and mission_waves:
            pkg = package_by_mission.get(mission_name) or {}
            if pkg.get("time") and pkg["time"] != next(iter(tot_times)):
                warnings.append(
                    f"Strike timing: @strike_package time={pkg.get('time')} differs from "
                    f"CreateMissionFlightPlan TIMEONTARGET={next(iter(tot_times))}."
                )

        mission_fp_dates = {fp[2] for fp in mission_fps if fp[2]}
        pkg = package_by_mission.get(mission_name) or {}
        if pkg.get("date") and mission_fp_dates:
            pkg_date = _normalize_date_key(pkg["date"])
            for fp_date in mission_fp_dates:
                if pkg_date and _normalize_date_key(fp_date) != pkg_date:
                    errors.append(
                        f"Strike timing: @strike_package date={pkg.get('date')} differs from "
                        f"CreateMissionFlightPlan DATEONTARGET={fp_date} on '{mission_name}'."
                    )
                    break
            else:
                if pkg_date:
                    ok.append(
                        f"OK: Strike timing '{mission_name}' — @strike_package date matches flight plan."
                    )

        if has_naval and inferred == "standoff" and not mission_waves:
            warnings.append(
                f"Strike timing: mission '{mission_name}' has naval TLAM + standoff air but no @strike_wave "
                "offsets — document synchronized impact times (TLAM often fires too early without events)."
            )

    return errors, warnings, ok

def _validate_strike_flight_package_grouping(content, mission_map):
    """
    Large carrier strike packages should use StrikeUseFlightSize + StrikeFlightSize so jets
    wait and launch in flights, not one-by-one.
    """
    errors = []
    warnings = []
    ok = []
    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    if not strike_missions:
        return errors, warnings, ok

    set_mission = _parse_set_mission_strike_flight_settings(content)
    packages, _waves = _parse_strike_package_annotations(content)
    package_by_mission = {p.get("mission"): p for p in packages if p.get("mission")}
    carrier_counts = _carrier_air_counts_by_mission(content)

    for mission_name in strike_missions:
        counts = carrier_counts.get(mission_name, {"strikers": 0, "escorts": 0})
        strikers = counts["strikers"]
        escorts = counts["escorts"]
        if strikers < _STRIKE_MIN_CARRIER_STRIKERS_GROUPING and escorts < _STRIKE_MIN_CARRIER_ESCORTS_GROUPING:
            continue

        pkg = package_by_mission.get(mission_name) or {}
        sm = set_mission.get(mission_name) or {}

        ann_use = pkg.get("use_flight_size", "").lower()
        ann_use_bool = None
        if ann_use in ("true", "yes", "1"):
            ann_use_bool = True
        elif ann_use in ("false", "no", "0"):
            ann_use_bool = False

        strike_use = sm.get("strike_use_flight_size")
        if strike_use is None and ann_use_bool is not None:
            strike_use = ann_use_bool

        strike_size = sm.get("strike_flight_size")
        if strike_size is None and pkg.get("flight_size"):
            strike_size = _parse_flight_size_value(pkg.get("flight_size"))

        escort_use = sm.get("escort_use_flight_size")
        ann_escort_use = pkg.get("escort_use_flight_size", "").lower()
        if escort_use is None and ann_escort_use in ("true", "yes", "1"):
            escort_use = True
        elif escort_use is None and ann_escort_use in ("false", "no", "0"):
            escort_use = False

        escort_size = sm.get("escort_flight_size")
        if escort_size is None and pkg.get("escort_flight_size"):
            escort_size = _parse_flight_size_value(pkg.get("escort_flight_size"))

        if strikers >= _STRIKE_MIN_CARRIER_STRIKERS_GROUPING:
            if strike_use is False:
                errors.append(
                    f"Strike flight package: mission '{mission_name}' has {strikers} carrier strikers but "
                    "StrikeUseFlightSize/UseFlightSize=false — CMO launches singles instead of waiting for "
                    "flight-size groups. Set StrikeUseFlightSize=true and StrikeFlightSize>=2 via "
                    "ScenEdit_SetMission."
                )
            elif strike_use is not True:
                errors.append(
                    f"Strike flight package: mission '{mission_name}' has {strikers} carrier strikers without "
                    "StrikeUseFlightSize=true (ScenEdit_SetMission or @strike_package use_flight_size=true). "
                    "Jets will launch piecemeal instead of forming flights."
                )
            elif strike_size is not None and strike_size < 2:
                errors.append(
                    f"Strike flight package: mission '{mission_name}' StrikeFlightSize={strike_size} — "
                    "use at least 2 (typically 4) so the package waits for multi-ship flights."
                )
            elif strike_use is True and strike_size is not None and strike_size >= 2:
                ok.append(
                    f"OK: Strike flight package '{mission_name}' — {strikers} carrier strikers, "
                    f"UseFlightSize with flight size {strike_size}."
                )
            min_ac = sm.get("strike_min_aircraft")
            if min_ac is None and pkg.get("min_aircraft"):
                try:
                    min_ac = int(pkg["min_aircraft"])
                except ValueError:
                    min_ac = None
            if strikers >= 8 and min_ac is None:
                warnings.append(
                    f"Strike flight package: mission '{mission_name}' has {strikers} carrier strikers but no "
                    "StrikeMinAircraftReq / @strike_package min_aircraft — consider a minimum package size "
                    "so the first wave waits for more aircraft (e.g. 8)."
                )

        if escorts >= _STRIKE_MIN_CARRIER_ESCORTS_GROUPING:
            if escort_use is False:
                errors.append(
                    f"Strike flight package: mission '{mission_name}' has {escorts} carrier escorts but "
                    "EscortUseFlightSize=false — escorts launch individually. Set EscortUseFlightSize=true "
                    "and EscortFlightSizeShooter>=2."
                )
            elif escort_use is not True:
                warnings.append(
                    f"Strike flight package: mission '{mission_name}' has {escorts} carrier escorts without "
                    "EscortUseFlightSize=true — escort fighters may not wait for flight-size groups."
                )
            elif escort_size is not None and escort_size >= 2 and escort_use is True:
                ok.append(
                    f"OK: Strike escort package '{mission_name}' — {escorts} carrier escorts, "
                    f"flight size {escort_size}."
                )

    return errors, warnings, ok

def _validate_strike_escort_coverage(content, mission_map):
    """
    CMO drops strikers when escort count cannot cover each strike flight.
    Required escorts ≈ ceil(strikers / strike_flight_size) * escort_min_shooter.
    """
    errors = []
    warnings = []
    ok = []
    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    set_mission = _parse_set_mission_strike_flight_settings(content)
    packages, _waves = _parse_strike_package_annotations(content)
    merged_pkg = _merge_strike_package_annotations(packages)
    air_counts = _strike_air_counts_by_mission(content, mission_map)
    for mission_name in air_counts:
        if _infer_mission_role(mission_name, mission_map) == "strike":
            strike_missions.add(mission_name)
    if not strike_missions:
        return errors, warnings, ok

    for mission_name in strike_missions:
        counts = air_counts.get(mission_name, {"strikers": 0, "escorts": 0})
        strikers = counts["strikers"]
        escorts = counts["escorts"]
        if strikers < 2:
            continue

        pkg = merged_pkg
        sm = set_mission.get(mission_name) or {}

        strike_use = sm.get("strike_use_flight_size")
        ann_use = pkg.get("use_flight_size", "").lower()
        if strike_use is None and ann_use in ("true", "yes", "1"):
            strike_use = True
        elif strike_use is None and ann_use in ("false", "no", "0"):
            strike_use = False

        strike_size = sm.get("strike_flight_size")
        if strike_size is None and pkg.get("flight_size"):
            strike_size = _parse_flight_size_value(pkg.get("flight_size"))
        if strike_size is None or strike_size < 1:
            strike_size = 4

        escort_flight_size = sm.get("escort_flight_size")
        if escort_flight_size is None and pkg.get("escort_flight_size"):
            escort_flight_size = _parse_flight_size_value(pkg.get("escort_flight_size"))

        escort_min = sm.get("escort_min_shooter")
        if escort_min is None and pkg.get("min_ready_escort"):
            try:
                escort_min = int(pkg["min_ready_escort"])
            except ValueError:
                escort_min = None
        if escort_flight_size is None or escort_flight_size < 1:
            escort_flight_size = escort_min if escort_min and escort_min > 0 else 4
        if escort_min is None or escort_min == 0:
            escort_min = escort_flight_size if escort_flight_size and escort_flight_size > 0 else 2

        min_strikers = sm.get("strike_min_aircraft")
        if min_strikers is None and pkg.get("min_aircraft"):
            try:
                min_strikers = int(pkg["min_aircraft"])
            except ValueError:
                min_strikers = None

        if strike_use is False:
            continue

        strike_flights = math.ceil(strikers / strike_size)
        required_escorts = strike_flights * escort_min
        oob_vs_mission_ok = True
        total_on_mission = strikers + escorts

        # CMO runtime: min to trigger ≈ StrikeMinAircraftReq × StrikeFlightSize (not raw MinReq).
        cmo_trigger_min = None
        if min_strikers is not None:
            cmo_trigger_min = (
                min_strikers * strike_size if strike_use else min_strikers
            )
            if total_on_mission < cmo_trigger_min:
                oob_vs_mission_ok = False
                errors.append(
                    f"Strike OOB vs mission: '{mission_name}' has {total_on_mission} aircraft on "
                    f"mission ({strikers} strikers + {escorts} escorts) but CMO trigger minimum "
                    f"is {cmo_trigger_min} (StrikeMinAircraftReq={min_strikers} × "
                    f"StrikeFlightSize={strike_size}) — mission will never take off and "
                    "aircraft are removed. Lower MinAircraftReq or add aircraft."
                )
            elif strikers < cmo_trigger_min:
                warnings.append(
                    f"Strike OOB vs mission: '{mission_name}' has {strikers} strikers but CMO "
                    f"trigger needs {cmo_trigger_min} total on mission — escorts may count toward "
                    "the threshold at runtime."
                )

        cmo_escort_trigger_min = None
        if escort_min is not None and escorts > 0:
            escort_use = sm.get("escort_use_flight_size")
            ann_escort_use = pkg.get("escort_use_flight_size", "").lower()
            if escort_use is None and ann_escort_use in ("true", "yes", "1"):
                escort_use = True
            cmo_escort_trigger_min = (
                escort_min * escort_flight_size if escort_use else escort_min
            )
            if escorts < cmo_escort_trigger_min:
                oob_vs_mission_ok = False
                errors.append(
                    f"Strike OOB vs mission: '{mission_name}' has {escorts} escort(s) but CMO "
                    f"escort trigger minimum is {cmo_escort_trigger_min} "
                    f"(EscortMinShooter={escort_min} × EscortFlightSizeShooter="
                    f"{escort_flight_size})."
                )

        if escorts < required_escorts:
            oob_vs_mission_ok = False
            errors.append(
                f"Strike OOB vs mission: '{mission_name}' has {strikers} strikers "
                f"(StrikeFlightSize={strike_size} → {strike_flights} strike flight(s)) but only "
                f"{escorts} escort(s) with EscortMinShooter={escort_min} — need at least "
                f"{required_escorts} escort aircraft or strikers deassign (e.g. distant base). "
                f"Add escorts or set StrikeFlightSize={strikers} for a single wave."
            )
        elif (
            escorts >= required_escorts
            and escort_flight_size >= 2
            and escorts % escort_flight_size != 0
        ):
            warnings.append(
                f"Strike OOB vs mission: '{mission_name}' has {escorts} escort(s) — not a multiple "
                f"of EscortFlightSizeShooter={escort_flight_size}; CMO may hold spare escorts on deck."
            )

        if oob_vs_mission_ok and escorts >= required_escorts:
            trigger_part = ""
            if cmo_trigger_min is not None:
                trigger_part = (
                    f", CMO trigger {cmo_trigger_min} "
                    f"(MinReq {min_strikers} x flight {strike_size}) <= {total_on_mission} on mission"
                )
            ok.append(
                f"OK: Strike OOB vs mission '{mission_name}' — OOB {strikers} strikers + "
                f"{escorts} escorts matches mission (flight size {strike_size}, "
                f"{strike_flights} strike flight(s), {required_escorts} escorts required"
                f"{trigger_part})."
            )

    return errors, warnings, ok

def _validate_sead_strike_launch_timing(content, mission_map):
    """
    Carrier SEAD should not launch at scenario start while strike package is still on deck.
    Requires starttime/TakeOffTime on SEAD (+ SEAD escort CAP) aligned before strike TOT.
    """
    errors = []
    warnings = []
    ok = []

    packages, _waves = _parse_strike_package_annotations(content)
    sead_packages = _parse_sead_package_annotations(content)
    strike_pkg = next((p for p in packages if p.get("mission")), packages[0] if packages else {})
    sead_pkg = sead_packages[0] if sead_packages else {}

    strike_tot = strike_pkg.get("time")
    strike_date = strike_pkg.get("date")
    flight_plans = _parse_mission_flight_plan_calls(content)
    if not strike_tot and flight_plans:
        strike_tot = next((fp[3] for fp in flight_plans if fp[3]), None)
    if not strike_date and flight_plans:
        strike_date = next((fp[2] for fp in flight_plans if fp[2]), None)

    carrier_counts = _carrier_air_counts_by_mission(content)
    growler_on_sead = 0
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'[^']*'\s*,\s*[^,]+,\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*,\s*'([^']+)'\s*,\s*(\w+)\.guid",
        re.IGNORECASE,
    )
    carrier_vars = set(
        re.findall(r"(?:local\s+)?(\w+)\s*=\s*place_ship", content, flags=re.IGNORECASE)
    )
    sead_mission_names = {n for n, role in mission_map.items() if role == "sead"}
    for match in wing_pattern.finditer(content):
        if match.group(4) not in carrier_vars:
            continue
        if match.group(3) in sead_mission_names:
            growler_on_sead += int(match.group(1))

    if growler_on_sead < 4 and not sead_pkg.get("missions"):
        return errors, warnings, ok

    schedule = _parse_mission_schedule_settings(content)
    delayed_names = set()
    if sead_pkg.get("missions"):
        delayed_names.update(
            n.strip() for n in sead_pkg["missions"].split(",") if n.strip()
        )
    delayed_names.update(_sead_missions_needing_delayed_launch(content, mission_map, carrier_counts))
    if not delayed_names:
        return errors, warnings, ok

    sead_takeoff = sead_pkg.get("on_station") or sead_pkg.get("takeoff")
    if not sead_takeoff:
        for var_name in ("sead_on_station_time", "sead_package_takeoff"):
            takeoff_var = re.search(
                rf"local\s+{var_name}\s*=\s*'([^']+)'", content, re.IGNORECASE
            )
            if takeoff_var:
                sead_takeoff = takeoff_var.group(1)
                break
    tot_minutes = _time_to_minutes(strike_tot) if strike_tot else None
    takeoff_minutes = _time_to_minutes(sead_takeoff) if sead_takeoff else None
    lead_before_tot = (
        (tot_minutes - takeoff_minutes)
        if tot_minutes is not None and takeoff_minutes is not None
        else None
    )

    scenario_start_date, scenario_start_time = _parse_scenario_start_time(content)
    scenario_start_minutes = _time_to_minutes(scenario_start_time) if scenario_start_time else None
    sead_date_key = _normalize_date_key(sead_pkg.get("date") or strike_date)

    if delayed_names:
        if scenario_start_time is None:
            warnings.append(
                "SEAD timing: no ScenEdit_SetTime (StartTime/time) — scenario may use editor "
                "default start and launch patrols together with SEAD unless missions are scheduled."
            )
        elif takeoff_minutes is not None and scenario_start_minutes is not None:
            if takeoff_minutes <= scenario_start_minutes:
                errors.append(
                    f"SEAD timing: SEAD takeoff {sead_takeoff} is not after scenario "
                    f"StartTime {scenario_start_time} — SEAD can launch immediately at H-hour."
                )
            elif takeoff_minutes - scenario_start_minutes < 15:
                warnings.append(
                    f"SEAD timing: only {takeoff_minutes - scenario_start_minutes} min between "
                    f"scenario start ({scenario_start_time}) and SEAD takeoff ({sead_takeoff}) — "
                    "strike escorts may not be airborne yet."
                )
            else:
                ok.append(
                    f"OK: SEAD timing — scenario starts {scenario_start_time}, "
                    f"SEAD takeoff {sead_takeoff}."
                )
        if (
            sead_date_key
            and scenario_start_date
            and sead_date_key != scenario_start_date
        ):
            warnings.append(
                f"SEAD timing: @sead_package date and scenario StartDate differ "
                f"({sead_pkg.get('date') or strike_date} vs parsed start date)."
            )

    if lead_before_tot is not None and sead_pkg.get("minutes_before_strike_tot"):
        try:
            declared_lead = int(sead_pkg["minutes_before_strike_tot"])
            if abs(declared_lead - lead_before_tot) > 1:
                errors.append(
                    f"SEAD timing: @sead_package minutes_before_strike_tot={declared_lead} but "
                    f"takeoff {sead_takeoff} vs strike TOT {strike_tot} is {lead_before_tot} min — "
                    "fix annotation or times."
                )
            else:
                ok.append(
                    f"OK: SEAD timing — minutes_before_strike_tot={declared_lead} matches "
                    f"takeoff/TOT delta."
                )
        except ValueError:
            warnings.append(
                "SEAD timing: @sead_package minutes_before_strike_tot is not an integer."
            )

    strike_mission_names = {n for n, role in mission_map.items() if role == "strike"}
    carrier_escorts_on_strike = sum(
        counts["escorts"]
        for mname, counts in carrier_counts.items()
        if mname in strike_mission_names
    )
    if (
        lead_before_tot is not None
        and carrier_escorts_on_strike >= 4
        and flight_plans
    ):
        if lead_before_tot >= _STRIKE_ESCORT_TYPICAL_LAUNCH_MIN_BEFORE_TOT:
            ok.append(
                f"OK: SEAD timing — takeoff {lead_before_tot} min before TOT; SEAD/SEAD-escort "
                f"launch before typical strike package (~{_STRIKE_ESCORT_TYPICAL_LAUNCH_MIN_BEFORE_TOT} min pre-TOT)."
            )
        elif lead_before_tot < 20:
            warnings.append(
                f"SEAD timing: SEAD takeoff only {lead_before_tot} min before strike TOT — "
                "Growlers may not reach the SAM box before strikers ingress; use ~30+ min "
                "(see @sead_package minutes_before_strike_tot)."
            )
        else:
            ok.append(
                f"OK: SEAD timing — takeoff {lead_before_tot} min before TOT."
            )

    for mission_name in sorted(delayed_names):
        sched = schedule.get(mission_name) or {}
        if (
            not sched.get("starttime")
            and not sched.get("takeoff_time")
            and not sched.get("time_on_target")
        ):
            errors.append(
                f"SEAD timing: mission '{mission_name}' has no starttime/TakeOffTime/TimeOnTargetStation — "
                "Growlers/SEAD-escort launch at scenario start. Use TimeOnTargetStation (on-station) "
                "or starttime/TakeOffTime ~25–35 min before strike TOT (see @sead_package)."
            )
            continue
        sched_label = (
            f"on-station {sched.get('time_on_target', '').split()[-1]}"
            if sched.get("time_on_target")
            else f"takeoff {sead_takeoff}"
        )
        if strike_tot and sead_takeoff and tot_minutes is not None and takeoff_minutes is not None:
            if takeoff_minutes >= tot_minutes:
                warnings.append(
                    f"SEAD timing: '{mission_name}' {sched_label} is not before "
                    f"strike TOT {strike_tot}."
                )
            elif tot_minutes - takeoff_minutes > 45:
                warnings.append(
                    f"SEAD timing: '{mission_name}' {sched_label} is more than 45 min "
                    f"before strike TOT {strike_tot} — may still fight MiGs alone for too long."
                )
            else:
                ok.append(
                    f"OK: SEAD timing '{mission_name}' — {sched_label}, strike TOT {strike_tot}."
                )
        else:
            ok.append(
                f"OK: SEAD timing '{mission_name}' — delayed schedule via SetMission."
            )

    if growler_on_sead >= 4 and strike_tot and not sead_pkg and not sead_packages:
        warnings.append(
            "SEAD timing: carrier SEAD package detected but no @sead_package annotation — "
            "document takeoff time relative to strike TOT for maintainers."
        )

    sead_loop_m = re.search(
        r"for\s+_\s*,\s*sead_mission\s+in\s+ipairs\s*\(\s*sead_timed_missions\s*\)\s*do\s*"
        r"ScenEdit_SetMission\s*\([^,]+,\s*sead_mission\s*,\s*\{([^}]*)\}",
        content,
        re.IGNORECASE,
    )
    list_m = re.search(
        r"local\s+sead_timed_missions\s*=\s*\{([^}]+)\}",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if sead_loop_m and list_m:
        block = sead_loop_m.group(1)
        min_req_m = re.search(r"MinAircraftReq\s*=\s*(\d+)", block, re.IGNORECASE)
        flight_m = re.search(r"FlightSize\s*=\s*(\d+)", block, re.IGNORECASE)
        use_fs_m = re.search(r"UseFlightSize\s*=\s*(true|false)", block, re.IGNORECASE)
        min_req = int(min_req_m.group(1)) if min_req_m else None
        flight_size = int(flight_m.group(1)) if flight_m else 1
        use_flight_size = _parse_lua_bool(use_fs_m.group(1)) if use_fs_m else False
        if min_req and use_flight_size:
            trigger = min_req * flight_size
            spawn_counts = {}
            for spec in _parse_air_spawn_wing_specs(content):
                spawn_counts[spec["mission"]] = (
                    spawn_counts.get(spec["mission"], 0) + spec["count"]
                )
            for mission_name in re.findall(r"'([^']+)'", list_m.group(1)):
                available = spawn_counts.get(mission_name, 0)
                if available < trigger:
                    errors.append(
                        f"SEAD flight size: mission '{mission_name}' has {available} aircraft "
                        f"but CMO requires {trigger} to launch "
                        f"(MinAircraftReq={min_req} × FlightSize={flight_size}) — "
                        "mission will never take off and aircraft are removed. "
                        "Lower MinAircraftReq or add aircraft."
                    )
                else:
                    ok.append(
                        f"OK: SEAD flight size '{mission_name}' — {available} aircraft "
                        f"meets trigger {trigger} (MinAircraftReq={min_req} × FlightSize={flight_size})."
                    )

    return errors, warnings, ok

def _validate_isr_before_sead(content):
    """MQ-4C on-station before SEAD on-station (TimeOnTargetStation preferred)."""
    errors = []
    warnings = []
    ok = []

    recon_m = re.search(r"local\s+isr_recon_min\s*=\s*(\d+)", content, re.IGNORECASE)
    sead_station_m = re.search(
        r"local\s+sead_on_station_time\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    if not (recon_m and sead_station_m):
        return errors, warnings, ok

    recon = int(recon_m.group(1))
    sead_station = sead_station_m.group(1)
    sead_min = _time_to_minutes(sead_station)
    if sead_min is None:
        return errors, warnings, ok

    isr_station_m = re.search(
        r"local\s+isr_on_station_time\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    if isr_station_m:
        isr_station = isr_station_m.group(1)
        isr_min = _time_to_minutes(isr_station)
    else:
        isr_min = sead_min - recon
        isr_station = f"{isr_min // 60:02d}:{isr_min % 60:02d}:00"

    if isr_min is None or isr_min + recon > sead_min:
        errors.append(
            f"ISR timing: ISR on-station {isr_station} + {recon} min recon exceeds "
            f"SEAD on-station {sead_station}."
        )
        return errors, warnings, ok

    if not re.search(
        r"local\s+isr_on_station_time\s*=\s*cmo\.hms_subtract_minutes\s*\(\s*sead_on_station_time\s*,\s*isr_recon_min\s*\)",
        content,
        re.IGNORECASE,
    ):
        warnings.append(
            "ISR timing: derive isr_on_station_time from sead_on_station_time minus isr_recon_min "
            "(cmo.hms_subtract_minutes)."
        )

    schedule = _parse_mission_schedule_settings(content)
    isr_missions = _parse_isr_mission_names(content)
    isr_primary = isr_missions[0] if isr_missions else None
    isr_label = isr_primary or "primary ISR mission"
    isr_sched = (schedule.get(isr_primary) or {}) if isr_primary else {}
    sead_shooters, sead_escorts = _parse_sead_mission_names(content)
    sead_check_missions = sead_shooters + sead_escorts + ["SEAD Escort CAP"]
    sead_sched_any = any(
        (schedule.get(m) or {}).get("time_on_target") for m in sead_check_missions
    )
    has_isr_schedule_call = bool(
        re.search(
            r"set_patrol_on_station_schedule\s*\([^)]*ISR_(?:WEST|EAST)_MISSION",
            content,
            re.IGNORECASE,
        )
        or (
            isr_primary
            and re.search(
                rf"set_patrol_on_station_schedule\s*\([^)]*{re.escape(isr_primary)}",
                content,
                re.IGNORECASE,
            )
        )
    )
    if isr_sched.get("time_on_target") or has_isr_schedule_call:
        ok.append(
            f"OK: ISR before SEAD — ISR on-station {isr_station} Z ({recon} min recon before SEAD on-station {sead_station})."
        )
    else:
        warnings.append(
            f"ISR timing: {isr_label} has no TimeOnTargetStation — drone may launch at H-hour."
        )

    if sead_sched_any or re.search(
        r"set_patrol_on_station_schedule\s*\([\s\S]*?sead_on_station_dt",
        content,
        re.IGNORECASE,
    ):
        ok.append(
            f"OK: SEAD on-station schedule — CreateMissionFlightPlan TIMEONTARGET {sead_station} (CMO backs off launch)."
        )
    else:
        warnings.append(
            "SEAD timing: prefer set_patrol_on_station_schedule / TimeOnTargetStation over starttime/TakeOffTime."
        )

    if not re.search(
        r"add_mission_schedule_restore_event\s*\([\s\S]*?SEAD on-station schedule restore",
        content,
        re.IGNORECASE,
    ):
        warnings.append(
            "ISR/SEAD timing: add_mission_schedule_restore_event (on_station) recommended at Play."
        )
    escort_per_zone_m = re.search(
        r"local\s+sead_escort_per_zone\s*=\s*(\d+)", content, re.IGNORECASE
    )
    growler_count = len(
        re.findall(
            r"spawn_air_wing\s*\([^)]*Growler SEAD",
            content,
            re.IGNORECASE,
        )
    )
    if escort_per_zone_m and growler_count >= 2:
        per_zone = int(escort_per_zone_m.group(1))
        if per_zone < 4:
            warnings.append(
                f"SEAD escort: sead_escort_per_zone={per_zone} is thin for 4 Growlers per box "
                "(prefer ≥4 escorts per SEAD theater)."
            )
        else:
            ok.append(
                f"OK: SEAD escort — {per_zone} Hornets per theater ({per_zone * 2} total) for "
                f"{growler_count * 4} Growlers."
            )

    sead_hold_mission = sead_shooters[0] if sead_shooters else None
    sead_hold = (
        re.search(
            rf"{re.escape(sead_hold_mission)}[\s\S]{{0,400}}?weapon_control_status_land\s*=\s*2",
            content,
            re.IGNORECASE,
        )
        if sead_hold_mission
        else None
    )
    if sead_hold:
        ok.append("OK: SEAD land WCS HOLD until on-station — no HARM fires before ISR recon window.")
    else:
        warnings.append(
            "ISR/SEAD timing: set weapon_control_status_land=2 (HOLD) on SEAD until on-station event sets FREE."
        )

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

def _validate_modern_strike_munitions(scenario_year, assignments, mission_map, db, series, version):
    errors = []
    warnings = []
    ok = []
    if not scenario_year or scenario_year < 2000:
        return errors, warnings, ok

    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    dumb_on_strike = []
    for side, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if escort_flag is True or aircraft_id == 0 or mission_name not in strike_missions:
            continue
        loadout_u = _loadout_name_upper(db, loadout_id, series, version)
        roles = _loadout_roles(loadout_u)
        if "dumb_strike" in roles and "precision_strike" not in roles and "standoff" not in roles:
            dumb_on_strike.append((side, aircraft_id, loadout_id, loadout_u))

    if not dumb_on_strike:
        if scenario_year >= 2000:
            ok.append(
                f"OK: Era-appropriate strike munitions for {scenario_year} "
                "(loadout names classified as precision/standoff, not dumb-only)."
            )
        return errors, warnings, ok

    for side, aircraft_id, loadout_id, loadout_u in dumb_on_strike:
        msg = (
            f"Era-appropriate munitions ({scenario_year}): strike uses primarily unguided loadout "
            f"({loadout_u}, aircraft {aircraft_id}, loadout {loadout_id}). "
            "Use precision/standoff names in the loadout (JDAM, JSOW, JASSM, CALCM, GBU-, etc.)."
        )
        if scenario_year >= 2010:
            errors.append(msg)
        else:
            warnings.append(msg)
    return errors, warnings, ok

def _validate_aar_for_bomber_strikes(
    content, assignments, mission_map, db, series, version
):
    errors = []
    warnings = []
    ok = []
    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    refuel_missions = _parse_strike_refuel_doctrine(content)

    bomber_needs_aar = False
    bomber_standoff_only = False
    for side, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if escort_flag is True or aircraft_id == 0 or mission_name not in strike_missions:
            continue
        if not _is_non_stealth_bomber_airframe(
            _aircraft_name_upper(db, aircraft_id, series, version)
        ):
            continue
        if _is_standoff_only_strike_loadout(db, loadout_id, series, version):
            bomber_standoff_only = True
        else:
            bomber_needs_aar = True

    if not bomber_needs_aar and not bomber_standoff_only:
        return errors, warnings, ok

    if bomber_standoff_only and not bomber_needs_aar:
        ok.append(
            "OK: Bomber strike uses standoff-only loadout — AAR optional for regional CALCM/JASSM packages."
        )
        return errors, warnings, ok

    tanker_support = False
    tanker_ok_logged = set()
    for side, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if escort_flag is True or aircraft_id == 0:
            continue
        name_u = _aircraft_name_upper(db, aircraft_id, series, version)
        loadout_u = _loadout_name_upper(db, loadout_id, series, version)
        role = _infer_mission_role(mission_name, mission_map)
        if not _is_tanker_airframe(name_u) and "tanker" not in _loadout_roles(loadout_u):
            continue
        if role in ("support", "aaw", "unknown") and mission_name:
            upper_m = mission_name.upper()
            if any(t in upper_m for t in ("AAR", "TANKER", "REFUEL", "ORBIT")) or role == "support":
                tanker_support = True
                if mission_name not in tanker_ok_logged:
                    tanker_ok_logged.add(mission_name)
                    ok.append(
                        f"OK: Tanker support ({name_u}) on mission '{mission_name}' "
                        "for long-range strike package."
                    )

    doctrine_refuel = bool(refuel_missions & strike_missions)
    if doctrine_refuel and bomber_needs_aar:
        ok.append("OK: Strike mission doctrine enables air-to-air refueling (use_refuel_unrep).")

    if bomber_needs_aar and not tanker_support and not doctrine_refuel:
        warnings.append(
            "AAR package: penetration bomber on Strike without KC-tanker Support mission "
            "and without use_refuel_unrep. Add tankers or enable refuel only for that package."
        )
    return errors, warnings, ok

def _validate_refuel_doctrine_sanity(content, assignments, mission_map, db, series, version):
    """Warn when Yes_Yes refuel on strike overloads few tankers (carrier queue crashes)."""
    errors = []
    warnings = []
    ok = []
    refuel_strikes = _parse_strike_refuel_doctrine(content)
    if not refuel_strikes:
        ok.append("OK: Strike mission(s) use use_refuel_unrep=No — aircraft RTB at Bingo instead of tanker queue.")
        return errors, warnings, ok

    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    carrier_vars = set(
        re.findall(r"(?:local\s+)?(\w+)\s*=\s*place_ship", content, flags=re.IGNORECASE)
    )
    carrier_strike = 0
    total_strike_air = 0
    tanker_count = 0

    for side, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if aircraft_id == 0 or mission_name not in strike_missions:
            continue
        if mission_name not in refuel_strikes:
            continue
        total_strike_air += 1
        on_carrier = any(
            f", {cv}.guid" in content or f", {cv}.guid," in content
            for cv in carrier_vars
            if re.search(
                rf"spawn_air_wing\s*\([^)]*,\s*{re.escape(str(aircraft_id))}\s*,\s*{re.escape(str(loadout_id))}\s*,\s*'{re.escape(mission_name)}'\s*,\s*{cv}\.guid",
                content,
                re.IGNORECASE,
            )
        )
        if on_carrier:
            carrier_strike += 1
        name_u = _aircraft_name_upper(db, aircraft_id, series, version)
        if _is_tanker_airframe(name_u):
            tanker_count += 1

    for mission_name in refuel_strikes:
        if total_strike_air > 8 and tanker_count < max(2, total_strike_air // 12):
            warnings.append(
                f"AAR capacity: mission '{mission_name}' has use_refuel_unrep=Yes with "
                f"~{total_strike_air} strike-aircraft but only {tanker_count} tanker(s) — "
                "expect long queues and mid-air refueling collisions; use No_No for carrier "
                "strikes or add tankers / split missions."
            )
        if carrier_strike >= 12 and tanker_count <= 2:
            warnings.append(
                f"AAR doctrine: mission '{mission_name}' sends {carrier_strike}+ carrier-based "
                "strikers/escorts to tankers — usually unnecessary within regional strike range; "
                "set use_refuel_unrep='No_No' and fuel_state_rtb='Bingo' so excess aircraft RTB."
            )
    return errors, warnings, ok

def _validate_naval_strike_launch_timing(content, mission_map, ships):
    """
    Ships on a Strike mission with air CreateMissionFlightPlan fire TLAMs at scenario start.
    Require a separate timed naval Strike (starttime + TimeOnTargetStation) or documented delay.
    """
    errors = []
    warnings = []
    ok = []
    if not ships:
        return errors, warnings, ok

    strike_assigns = _parse_ship_strike_assignments(content, mission_map)
    if not strike_assigns:
        return errors, warnings, ok

    flight_plans = _parse_mission_flight_plan_calls(content)
    packages, waves = _parse_strike_package_annotations(content)
    naval_packages = _parse_naval_package_annotations(content)
    strike_pkg = next((p for p in packages if p.get("mission")), packages[0] if packages else {})
    naval_pkg = naval_packages[0] if naval_packages else {}
    strike_tot = strike_pkg.get("time")
    if not strike_tot and flight_plans:
        strike_tot = next((fp[3] for fp in flight_plans if fp[3]), None)

    air_counts = _aircraft_count_on_strike_missions(content, mission_map)
    schedule = _parse_mission_schedule_settings(content)
    ship_by_var = {s["var"]: s for s in ships if s.get("var")}

    for var, mission in strike_assigns:
        ship = ship_by_var.get(var)
        label = (ship.get("name") if ship else None) or var
        mission_fps = [fp for fp in flight_plans if fp[1] == mission]
        air_on_mission = air_counts.get(mission, 0)
        sched = schedule.get(mission) or {}
        has_timing = bool(
            sched.get("starttime") or sched.get("takeoff_time") or sched.get("time_on_target")
        )
        if not has_timing and re.search(
            r"setup_csg_strike_on_air_strike\s*\(",
            content,
            re.IGNORECASE,
        ):
            if naval_pkg.get("tot") or naval_pkg.get("launch") or sched.get("time_on_target"):
                has_timing = True

        unified_air_tlam = bool(
            re.search(
                r"setup_csg_strike_on_air_strike\s*\(",
                content,
                re.IGNORECASE,
            )
            or (
                naval_pkg.get("mission")
                and strike_pkg.get("mission")
                and naval_pkg["mission"].strip().lower()
                == strike_pkg["mission"].strip().lower()
            )
        )
        tlam_example = _resolve_tlam_strike_mission(content) or "TLAM Strike"
        if air_on_mission > 0 and mission_fps and not unified_air_tlam:
            errors.append(
                f"Naval strike timing: '{label}' on Strike '{mission}' shares the mission with "
                f"{air_on_mission} aircraft and CreateMissionFlightPlan — Tomahawks launch at "
                "scenario start while air sorts to TOT. Move the cruiser to a separate timed "
                f"Strike (e.g. {tlam_example}) with starttime and TimeOnTargetStation."
            )
            continue
        if air_on_mission > 0 and mission_fps and unified_air_tlam:
            if not has_timing and not (naval_pkg.get("launch") and naval_pkg.get("tot")):
                errors.append(
                    f"Naval strike timing: '{label}' on shared Strike '{mission}' needs "
                    "starttime + TimeOnTargetStation via setup_csg_strike_on_air_strike (see @naval_package)."
                )
                continue

        if not has_timing:
            errors.append(
                f"Naval strike timing: '{label}' on Strike '{mission}' has no starttime or "
                "TimeOnTargetStation — surface TLAMs fire immediately. Use "
                "setup_csg_strike_on_air_strike after the air flight plan (see @naval_package)."
            )
            continue

        launch_time = naval_pkg.get("launch")
        if not launch_time and sched.get("starttime"):
            parts = sched["starttime"].split()
            if len(parts) >= 2:
                launch_time = parts[-1]
        tot_minutes = _time_to_minutes(strike_tot) if strike_tot else None
        launch_minutes = _time_to_minutes(launch_time) if launch_time else None
        if tot_minutes is not None and launch_minutes is not None:
            lead = tot_minutes - launch_minutes
            if launch_minutes >= tot_minutes:
                warnings.append(
                    f"Naval strike timing: '{label}' launch {launch_time} is not before "
                    f"strike TOT {strike_tot}."
                )
            elif lead < _TLAM_LAUNCH_MIN_BEFORE_TOT:
                warnings.append(
                    f"Naval strike timing: '{label}' launch only {lead} min before TOT — "
                    "Tomahawks may impact after air ordnance."
                )
            elif lead > _TLAM_LAUNCH_MAX_BEFORE_TOT:
                warnings.append(
                    f"Naval strike timing: '{label}' launch {lead} min before TOT — "
                    "TLAMs may impact long before the strike package TOT window."
                )
            else:
                ok.append(
                    f"OK: Naval strike timing '{label}' — launch {launch_time}, "
                    f"{lead} min before strike TOT {strike_tot}."
                )
        elif sched.get("time_on_target") and strike_tot:
            ok.append(
                f"OK: Naval strike timing '{label}' — TOT sync {strike_tot} "
                f"(TimeOnTargetStation; CMO auto-launch from range)."
            )
        else:
            ok.append(
                f"OK: Naval strike timing '{label}' on '{mission}' — delayed via SetMission schedule."
            )

    naval_waves = [w for w in waves if "naval" in w.get("role", "")]
    if naval_waves and strike_assigns and not naval_pkg:
        warnings.append(
            "Naval strike timing: @strike_wave role=naval_strike present but no @naval_package — "
            "document TLAM launch time relative to strike TOT."
        )

    ann_launch = naval_pkg.get("launch")
    ann_tot_min = _time_to_minutes(strike_tot) if strike_tot else None
    ann_launch_min = _time_to_minutes(ann_launch) if ann_launch else None
    if naval_pkg.get("minutes_before_strike_tot") and ann_tot_min is not None and ann_launch_min is not None:
        try:
            declared = int(naval_pkg["minutes_before_strike_tot"])
            lead = ann_tot_min - ann_launch_min
            if abs(declared - lead) > 1:
                errors.append(
                    f"Naval strike timing: @naval_package minutes_before_strike_tot={declared} "
                    f"but launch/TOT delta is {lead} min."
                )
        except ValueError:
            warnings.append(
                "Naval strike timing: @naval_package minutes_before_strike_tot is not an integer."
            )

    return errors, warnings, ok

def _validate_early_patrol_support_launches(content, mission_map):
    """Warn when CAP/AEW/ISR have no starttime but strike uses a synchronized flight plan."""
    warnings = []
    ok = []
    flight_plans = _parse_mission_flight_plan_calls(content)
    if not flight_plans:
        return [], ok

    schedule = _parse_mission_schedule_settings(content)
    early_roles = {"aaw", "support"}
    sides_with_strike_fp = {fp[0] for fp in flight_plans}
    unscheduled = []
    wing_on_mission = re.compile(
        r"spawn_air_wing\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*'([^']+)'\s*,",
        re.IGNORECASE,
    )
    missions_with_air = {m for _, m in wing_on_mission.findall(content)}
    for name, role in mission_map.items():
        if role not in early_roles:
            continue
        sched_row = schedule.get(name, {})
        if sched_row.get("starttime") or sched_row.get("time_on_target"):
            continue
        if name not in missions_with_air:
            continue
        if sides_with_strike_fp and not any(
            side for side, mission in wing_on_mission.findall(content) if mission == name and side in sides_with_strike_fp
        ):
            continue
        unscheduled.append(name)

    if unscheduled:
        warnings.append(
            "Strike timing: patrol/support missions without starttime launch at scenario start "
            f"while strike package uses CreateMissionFlightPlan: {', '.join(sorted(unscheduled))}. "
            "Set starttime if early CAP/AEW/ISR orbit is undesired (SEAD/naval have dedicated checks)."
        )
    return warnings, ok

def _validate_naval_strike_assignment(content, ships, mission_map, db, series, version):
    errors = []
    warnings = []
    ok = []
    if not ships:
        return errors, warnings, ok

    carrier_vars = _parse_carrier_vars_with_air_wing(content)
    if not carrier_vars:
        return errors, warnings, ok

    ship_by_var = {s["var"]: s for s in ships if s.get("var")}
    strike_assigns = _parse_ship_strike_assignments(content, mission_map)
    assigned_vars = {var for var, _ in strike_assigns}

    has_cg_ddg = False
    for ship in ships:
        role, _ = _classify_ship(db, ship["dbid"], series, version)
        if role == "escort":
            has_cg_ddg = True
            break

    if not has_cg_ddg:
        return errors, warnings, ok

    if strike_assigns:
        for var, mission in strike_assigns:
            ship = ship_by_var.get(var)
            label = ship["name"] if ship else var
            ok.append(f"OK: Surface unit '{label}' assigned to Strike '{mission}' (TLAM/land strike).")
        return errors, warnings, ok

    warnings.append(
        "Naval strike: CSG includes CG/DDG but no ScenEdit_AssignUnitToMission(ship.guid, '<Strike>') "
        "found. Consider assigning a cruiser to the land-strike mission for opening TLAM salvo."
    )
    return errors, warnings, ok

def _validate_strike_mission_escort_assignments(content, mission_map, assignments):
    """
    CMO API: ScenEdit_AssignUnitToMission(unit, mission, escort)
    For Strike missions, escort fighters must use escort=True (3rd parameter).
    """
    errors = []
    ok = []
    strike_missions = [name for name, role in mission_map.items() if role == "strike"]
    if not strike_missions:
        return errors, ok

    for _side, aircraft_id, _loadout_id, mission_name, escort_flag in assignments:
        if aircraft_id == 0:
            continue
        if _is_strike_escort_patrol_name(mission_name, mission_map):
            errors.append(
                f"Strike escort assignment: aircraft {aircraft_id} assigned to patrol mission "
                f"'{mission_name}' instead of a Strike mission with ScenEdit_AssignUnitToMission(..., "
                f"'<StrikeMission>', true). See ScenEdit_AssignUnitToMission escort parameter."
            )
        if mission_name in strike_missions and escort_flag is True:
            ok.append(f"OK: Strike escort slot on '{mission_name}' (escort=true)")
        if mission_name in strike_missions and escort_flag is False:
            errors.append(
                f"Strike escort flag: aircraft {aircraft_id} on Strike mission '{mission_name}' "
                "uses escort=false; escort fighters must use true as 3rd parameter."
            )

    for mission_name in strike_missions:
        has_escort_slot = any(
            m == mission_name and escort_flag is True
            for _s, _a, _l, m, escort_flag in assignments
            if _a != 0
        )
        has_strikers = any(
            m == mission_name and escort_flag is not True
            for _s, _a, _l, m, escort_flag in assignments
            if _a != 0
        )
        if has_strikers and not has_escort_slot:
            errors.append(
                f"Strike escort slot: Strike mission '{mission_name}' has strikers but no unit "
                "assigned with ScenEdit_AssignUnitToMission(unit, mission, true)."
            )
        elif has_escort_slot:
            ok.append(f"OK: Strike mission '{mission_name}' has escort-slot assignment(s)")

    return errors, ok

def _validate_bomber_and_sead_escort_packages(db, assignments, mission_map, series, version):
    """
    Require dedicated fighter escort (CAP/AAW with A/A loadout) when:
    - a non-stealth bomber-type airframe flies on a Strike mission, or
    - any aircraft flies on a SEAD mission (SEAD flights need escorts too).
    """
    errors = []
    warnings = []
    sides_needing_escort = set()
    no_side_for_escort_check = False
    standoff_warned = set()

    for side, aircraft_id, loadout_id, mission_name, _escort_flag in assignments:
        if not mission_name or aircraft_id == 0:
            continue
        role = _infer_mission_role(mission_name, mission_map)
        if role == "sead":
            if not side:
                no_side_for_escort_check = True
                continue
            sides_needing_escort.add(side)
            continue
        if role == "strike":
            name_u = _aircraft_name_upper(db, aircraft_id, series, version)
            if _is_non_stealth_bomber_airframe(name_u):
                if _is_standoff_only_strike_loadout(db, loadout_id, series, version):
                    key = (aircraft_id, mission_name)
                    if key not in standoff_warned:
                        standoff_warned.add(key)
                        warnings.append(
                            f"Strike package: {name_u.strip()} uses standoff-only loadout on "
                            f"'{mission_name}' (escort requirement waived); still model tankers/range "
                            "if originating far from the CSG."
                        )
                    continue
                if not side:
                    no_side_for_escort_check = True
                    continue
                sides_needing_escort.add(side)

    if no_side_for_escort_check:
        warnings.append(
            "Strike/SEAD escort check: some strike or SEAD spawns omit an explicit Lua `side` string "
            "(first argument to add_air_unit_checked / spawn_air_wing). Escort coverage could not be "
            "verified for those lines."
        )

    for side in sorted(sides_needing_escort):
        if _side_has_aaw_escort_with_aa_loadout(db, side, assignments, mission_map, series, version):
            continue
        errors.append(
            f"Strike package escort: side '{side}' uses non-stealth bombers on Strike and/or flies SEAD, "
            "but has no AAW/CAP mission assignment with an A/A-capable loadout (fighter escort for strike "
            "and for SEAD sorties). Add escorts or adjust mission names so SEAD/strike packages are covered."
        )
    return errors, warnings


def _validate_unit_geo_placement(units):
    """Land vs water placement for every independently placed unit.

    - **Ship / sub** (`place_ship`, `place_sub`, AddUnit Ship/Sub): must be **water**
      (CMO: *cannot place ship over land*).
    - **Facility** (`place_base`, `place_sam`, AddUnit Facility): must be **land**
      (CMO: *Placement aborted — underwater*).

    Uses ``global_land_mask`` (~1 km). Preflight counterpart to ``World_GetElevation``
    guards in ``scenario_bootstrap.lua``.
    """
    errors = []
    warnings = []
    ok = []
    if not units:
        return errors, warnings, ok

    try:
        from global_land_mask import globe
    except ImportError:
        warnings.append(
            "Geo placement: global_land_mask not installed — land/water checks skipped. "
            "Run 'pip install global-land-mask' (see requirements.txt)."
        )
        return errors, warnings, ok

    naval_checked = 0
    land_checked = 0
    for unit in units:
        lat = unit.get("lat")
        lon = unit.get("lon")
        if lat is None or lon is None:
            continue
        kind = unit.get("kind") or "unknown"
        source = unit.get("source") or "spawn"
        label = unit.get("name") or f"DBID {unit.get('dbid')}"
        side = unit.get("side") or "?"
        line = unit.get("line")
        where = f"line {line} " if line else ""
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            warnings.append(
                f"Geo placement: {kind} '{label}' ({where}{source}, side {side}) has "
                f"out-of-range coordinates lat={lat}, lon={lon} — skipped."
            )
            continue
        try:
            is_land = bool(globe.is_land(lat, lon))
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(
                f"Geo placement: could not evaluate '{label}' (lat={lat}, lon={lon}): {exc}"
            )
            continue

        if kind in ("ship", "sub"):
            naval_checked += 1
            if is_land:
                noun = "submarine" if kind == "sub" else "ship"
                errors.append(
                    f"Geo placement: {noun} '{label}' ({where}{source}, side {side}) at "
                    f"lat={lat}, lon={lon} is on land — CMO rejects "
                    f"('cannot place ship over land'). Use open water."
                )
        elif kind == "facility":
            land_checked += 1
            if not is_land:
                errors.append(
                    f"Geo placement: facility '{label}' ({where}{source}, side {side}) at "
                    f"lat={lat}, lon={lon} is underwater per global_land_mask — CMO aborts "
                    f"facility placement ('This point appears to be underwater'). Nudge coords inland."
                )

    if naval_checked and not any("ship" in e or "submarine" in e for e in errors):
        ok.append(
            f"OK: Geo placement — {naval_checked} naval unit(s) over water (global_land_mask)."
        )
    if land_checked and not any("facility" in e for e in errors):
        ok.append(
            f"OK: Geo placement — {land_checked} facility/land unit(s) on land (global_land_mask)."
        )
    return errors, warnings, ok


def _validate_ship_sub_water_placement(ships):
    """Backward-compatible wrapper — prefer ``_parse_all_geo_placements`` + ``_validate_unit_geo_placement``."""
    return _validate_unit_geo_placement(ships)


__all__ = sorted(
    name
    for name, value in globals().items()
    if not name.startswith("__") and callable(value)
)


__all__ = sorted(
    name
    for name, value in globals().items()
    if not name.startswith("__") and callable(value)
)

