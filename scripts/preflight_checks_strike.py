"""Strike package timing, reachability, escorts, and naval strike validators."""

import math
import re

from db_unit_queries import get_unit_weapons
from preflight_constants import *
from preflight_parse import *  # noqa: F403

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

__all__ = ['_resolve_scenedit_settime_date', '_validate_aar_for_bomber_strikes', '_validate_bomber_and_sead_escort_packages', '_validate_cvn_strike_air_schedule', '_validate_early_patrol_support_launches', '_validate_naval_strike_assignment', '_validate_naval_strike_launch_timing', '_validate_refuel_doctrine_sanity', '_validate_scenario_date_consistency', '_validate_sead_strike_launch_timing', '_validate_strike_escort_coverage', '_validate_strike_flight_package_grouping', '_validate_strike_flight_profile_and_timing', '_validate_strike_mission_escort_assignments', '_validate_strike_schedule_order', '_validate_strike_tot_reachability', '_validate_strike_tot_synchronization']
