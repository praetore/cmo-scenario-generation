"""CSG formation, patrol zones, and TLAM schedule validators."""

import math
import re

from db_unit_queries import get_unit_weapons
from preflight_constants import *
from preflight_parse import *  # noqa: F403

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

__all__ = ['_validate_carrier_strike_groups', '_validate_csg_formation', '_validate_patrol_zone_proximity', '_validate_tlam_schedule_workflow', '_validate_tlam_shooter_weapon_policy']
