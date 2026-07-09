"""Mission, schedule, and strike-package parsers."""

import math
import re
from pathlib import Path

from preflight_constants import *
from preflight_parse_math import _normalize_date_key, _normalize_date_slash_key
from preflight_parse_lua import _parse_annotation_kv_blob, _parse_flight_size_value, _parse_lua_bool, _parse_lua_local_string, _parse_lua_mission_option_bool, _parse_lua_mission_option_value, _parse_lua_string_list, _parse_lua_string_vars, _parse_lua_timing_vars, _resolve_lua_datetime_token, _resolve_lua_mission_name

def _classify_scenario_mission(mission_class, subtype):
    mission_class = (mission_class or "").upper()
    subtype = (subtype or "").upper()
    if mission_class == "PATROL" and subtype == "SEAD":
        return "sead"
    if mission_class == "PATROL" and subtype == "AAW":
        return "aaw"
    if mission_class == "STRIKE":
        return "strike"
    if mission_class == "SUPPORT":
        return "support"
    return mission_class.lower() if mission_class else "unknown"

def _parse_scenario_missions(content):
    missions = {}
    lua_vars = _parse_lua_string_vars(content)
    typed_mission_pattern = re.compile(
        r"ScenEdit_AddMission\s*\(\s*'[^']*'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*"
        r"\{type='([^']+)'(?:,\s*zone=\{([^}]+)\})?\}\s*\)",
        re.IGNORECASE,
    )
    zone_only_mission_pattern = re.compile(
        r"ScenEdit_AddMission\s*\(\s*'[^']*'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*"
        r"\{zone=\{([^}]+)\}\}\s*\)",
        re.IGNORECASE,
    )
    flex_mission_pattern = re.compile(
        r"ScenEdit_AddMission\s*\(\s*(?:'[^']*'|\w+)\s*,\s*(?:'([^']+)'|(\w+))\s*,\s*'([^']+)'\s*,\s*\{([^}]*)\}\s*\)",
        re.IGNORECASE,
    )
    for match in typed_mission_pattern.finditer(content):
        name = match.group(1)
        missions[name] = _classify_scenario_mission(match.group(2), match.group(3))
    for match in zone_only_mission_pattern.finditer(content):
        name = match.group(1)
        if name not in missions:
            missions[name] = _classify_scenario_mission(match.group(2), None)
    for match in flex_mission_pattern.finditer(content):
        name = _resolve_lua_mission_name(match.group(1) or match.group(2), lua_vars)
        if not name or name in missions:
            continue
        block = match.group(4)
        mission_class = match.group(3)
        subtype_m = re.search(r"type\s*=\s*'([^']+)'", block, re.IGNORECASE)
        subtype = subtype_m.group(1) if subtype_m else None
        missions[name] = _classify_scenario_mission(mission_class, subtype)
    return missions

def _parse_mission_zone_map(content):
    """Mission name -> list of reference point names in patrol/support zone."""
    zones = {}
    rp_pattern = re.compile(r"'([^']+)'")
    typed_mission_pattern = re.compile(
        r"ScenEdit_AddMission\s*\(\s*'[^']*'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*"
        r"\{type='([^']+)'(?:,\s*zone=\{([^}]+)\})?\}\s*\)",
        re.IGNORECASE,
    )
    zone_only_mission_pattern = re.compile(
        r"ScenEdit_AddMission\s*\(\s*'[^']*'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*"
        r"\{zone=\{([^}]+)\}\}\s*\)",
        re.IGNORECASE,
    )
    for match in typed_mission_pattern.finditer(content):
        if match.group(4):
            zones[match.group(1)] = rp_pattern.findall(match.group(4))
    for match in zone_only_mission_pattern.finditer(content):
        zones[match.group(1)] = rp_pattern.findall(match.group(3))
    return zones

def _parse_sam_sites(content):
    """(side, latitude, longitude) from place_sam(...) calls."""
    sites = []
    pattern = re.compile(
        r"place_sam\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*\d+\s*,\s*([\d.]+)\s*,\s*([-\d.]+)\s*\)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(content):
        sites.append((match.group(1), float(match.group(2)), float(match.group(3))))
    return sites

def _parse_hostile_postures(content):
    """Set of (side_a, side_b) where side_a is Hostile toward side_b."""
    hostile = set()
    pattern = re.compile(
        r"ScenEdit_SetSidePosture\s*\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'H'\s*\)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(content):
        hostile.add((match.group(1), match.group(2)))
    return hostile

def _sides_with_sead_missions(mission_map, assignments):
    sides = set()
    sead_names = {name for name, role in mission_map.items() if role == "sead"}
    for side, _aid, _lid, mission_name, _escort in assignments:
        if mission_name in sead_names and side:
            sides.add(side)
    return sides

def _enemy_sam_sites_for_sead_side(sead_side, sam_sites, hostile_postures):
    enemies = {other for actor, other in hostile_postures if actor == sead_side}
    return [(lat, lon) for side, lat, lon in sam_sites if side in enemies]

def _parse_mission_land_wcs_overrides(content):
    """Mission name -> weapon_control_status_land if set in ScenEdit_SetDoctrine mission block."""
    overrides = {}
    pattern = re.compile(
        r"ScenEdit_SetDoctrine\s*\(\s*\{[^}]*mission\s*=\s*'([^']+)'[^}]*\}\s*,\s*\{([^}]*)\}\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(content):
        block = match.group(2)
        land_match = re.search(
            r"weapon_control_status_land\s*=\s*(\d+)", block, re.IGNORECASE
        )
        if land_match:
            overrides[match.group(1)] = int(land_match.group(1))
    return overrides

def _parse_side_land_wcs(content):
    side_pattern = re.compile(
        r"ScenEdit_SetDoctrine\s*\(\s*\{[^}]*side\s*=\s*'([^']+)'[^}]*\}\s*,\s*\{([^}]*)\}\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in side_pattern.finditer(content):
        if "mission" in match.group(0).lower():
            continue
        block = match.group(2)
        land_match = re.search(
            r"weapon_control_status_land\s*=\s*(\d+)", block, re.IGNORECASE
        )
        if land_match:
            return int(land_match.group(1))
    return None

def _parse_scenario_policy_nuclear(content):
    """True if @scenario_policy explicitly allows nuclear weapons."""
    for line in content.splitlines():
        if "@scenario_policy" not in line.lower():
            continue
        blob = line.split("@scenario_policy", 1)[-1].lower()
        if re.search(r"nuclear\s*=\s*true", blob):
            return True
        if re.search(r"nuclear\s*=\s*yes", blob):
            return True
    return False

def _parse_use_nuclear_weapons_doctrine(content):
    """side -> True/False/None from ScenEdit_SetDoctrine use_nuclear_weapons."""
    by_side = {}
    for match in re.finditer(
        r"ScenEdit_SetDoctrine\s*\(\s*\{[^}]*side\s*=\s*'([^']+)'[^}]*\}\s*,\s*\{([^}]+)\}\s*\)",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        side = match.group(1)
        block = match.group(2)
        nuc = re.search(
            r"use_nuclear_weapons\s*=\s*'([^']+)'",
            block,
            re.IGNORECASE,
        )
        if not nuc:
            nuc = re.search(r"use_nuclear_weapons\s*=\s*(true|false)", block, re.IGNORECASE)
        if not nuc:
            continue
        val = nuc.group(1).strip().lower()
        if val in ("no", "false", "0"):
            by_side[side] = False
        elif val in ("yes", "true", "1"):
            by_side[side] = True
    return by_side

def _parse_strike_refuel_doctrine(content):
    missions_with_refuel = set()
    pattern = re.compile(
        r"ScenEdit_SetDoctrine\s*\(\s*\{[^}]*mission\s*=\s*'([^']+)'[^}]*\}\s*,\s*\{([^}]*)\}\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(content):
        block = match.group(2)
        if re.search(r"use_refuel_unrep\s*=\s*'Yes", block, re.IGNORECASE):
            missions_with_refuel.add(match.group(1))
    return missions_with_refuel

def _parse_naval_package_annotations(content):
    """@naval_package — timed TLAM / naval strike asset launch vs unified strike package TOT."""
    packages = []
    for line in content.splitlines():
        if "@naval_package" not in line.lower():
            continue
        blob = line.split("@naval_package", 1)[-1]
        packages.append(_parse_annotation_kv_blob(blob))
    return packages

def _parse_sead_package_annotations(content):
    """@sead_package — delayed SEAD / SEAD-escort launch relative to strike TOT."""
    packages = []
    for line in content.splitlines():
        if "@sead_package" not in line.lower():
            continue
        blob = line.split("@sead_package", 1)[-1]
        packages.append(_parse_annotation_kv_blob(blob))
    return packages

def _parse_task_pool_annotations(content):
    """@task_pool — strike task pool name and child package list."""
    for line in content.splitlines():
        if "@task_pool" not in line.lower():
            continue
        blob = line.split("@task_pool", 1)[-1]
        return _parse_annotation_kv_blob(blob)
    return {}

def _parse_isr_package_annotations(content):
    """@isr_package — ISR on-station timing and mission name(s)."""
    packages = []
    for line in content.splitlines():
        if "@isr_package" not in line.lower():
            continue
        blob = line.split("@isr_package", 1)[-1]
        packages.append(_parse_annotation_kv_blob(blob))
    return packages

def _parse_isr_mission_names(content):
    """ISR patrol mission names from locals or @isr_package (supports West+East combined)."""
    west = _parse_lua_local_string(content, "ISR_WEST_MISSION")
    east = _parse_lua_local_string(content, "ISR_EAST_MISSION")
    names = [m for m in (west, east) if m]
    if names:
        return names
    for pkg in _parse_isr_package_annotations(content):
        mission = (pkg.get("mission") or "").strip()
        if not mission:
            continue
        parts = [p.strip() for p in re.split(r"\s*\+\s*", mission) if p.strip()]
        if parts:
            return parts
    return []

def _parse_sead_mission_names(content):
    """SEAD shooter and escort mission names from locals or @sead_package."""
    shooters = _parse_lua_string_list(content, "sead_shooter_missions")
    escorts = _parse_lua_string_list(content, "sead_escort_missions")
    if not shooters:
        timed = _parse_lua_string_list(content, "sead_timed_missions")
        if timed:
            shooters = timed
    if not shooters:
        for pkg in _parse_sead_package_annotations(content):
            missions = (pkg.get("missions") or "").strip()
            if missions:
                shooters = [m.strip() for m in missions.split(",") if m.strip()]
                break
    if not escorts:
        escorts = _parse_lua_string_list(content, "sead_escort_missions")
    return shooters, escorts

def _resolve_strike_air_mission(content):
    name = _parse_lua_local_string(content, "STRIKE_AIR_MISSION")
    if name:
        return name
    _, waves = _parse_strike_package_annotations(content)
    for wave in waves:
        if wave.get("role") == "air_strike" and wave.get("mission"):
            return wave["mission"]
    packages, _ = _parse_strike_package_annotations(content)
    for pkg in packages:
        mission = pkg.get("mission") or ""
        if mission and "carrier" in mission.lower():
            return mission
    if packages:
        return packages[0].get("mission")
    return None

def _resolve_tlam_strike_mission(content):
    name = _parse_lua_local_string(content, "TLAM_STRIKE_MISSION")
    if name:
        return name
    naval = _parse_naval_package_annotations(content)
    if naval and naval[0].get("mission"):
        return naval[0]["mission"]
    _, waves = _parse_strike_package_annotations(content)
    for wave in waves:
        if wave.get("role") == "naval_strike" and wave.get("mission"):
            return wave["mission"]
    return None

def _resolve_strike_taskpool(content):
    name = _parse_lua_local_string(content, "STRIKE_TASKPOOL")
    if name:
        return name
    pool = _parse_task_pool_annotations(content)
    return pool.get("name")

def _csg_allowed_ship_strike_missions(content):
    """Strike missions a CSG escort may use while remaining in formation (from scenario locals/annotations)."""
    allowed = set()
    for name in (
        _resolve_tlam_strike_mission(content),
        _resolve_strike_taskpool(content),
        _resolve_strike_air_mission(content),
    ):
        if name:
            allowed.add(name.lower())
    return allowed

def _parse_strike_package_annotations(content):
    """@strike_package / @strike_wave comment metadata (generic, no fixed DBIDs)."""
    packages = []
    waves = []
    for line in content.splitlines():
        if "@strike_package" not in line.lower():
            continue
        blob = line.split("@strike_package", 1)[-1]
        packages.append(_parse_annotation_kv_blob(blob))
    for line in content.splitlines():
        if "@strike_wave" not in line.lower():
            continue
        blob = line.split("@strike_wave", 1)[-1]
        waves.append(_parse_annotation_kv_blob(blob))
    return packages, waves

def _merge_strike_package_annotations(packages):
    """Combine split -- @strike_package comment lines into one key/value map."""
    merged = {}
    for pkg in packages:
        for key, value in pkg.items():
            if value:
                merged[key] = value
    return merged

def _parse_mission_flight_plan_calls(content):
    """(side, mission, date_on_target, time_on_target) from CreateMissionFlightPlan / createFlightPlans."""
    rows = []
    lua_vars = _parse_lua_string_vars(content)
    pattern = re.compile(
        r"(?:ScenEdit_CreateMissionFlightPlan|\.createFlightPlans)\s*\(\s*'([^']*)'\s*,\s*([^,]+)\s*,\s*\{([^}]*)\}",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(content):
        block = match.group(3)
        mission = _resolve_lua_mission_name(match.group(2), lua_vars)
        date_m = re.search(r"DATEONTARGET\s*=\s*([^,\s}]+)", block, re.IGNORECASE)
        time_m = re.search(r"TIMEONTARGET\s*=\s*([^,\s}]+)", block, re.IGNORECASE)
        date_val = _resolve_lua_datetime_token(date_m.group(1), lua_vars) if date_m else None
        time_val = _resolve_lua_datetime_token(time_m.group(1), lua_vars) if time_m else None
        rows.append((match.group(1), mission, date_val, time_val))
    return rows

def _parse_strike_weapon_state_planned(content, mission_name):
    pattern = re.compile(
        r"ScenEdit_SetDoctrine\s*\(\s*\{[^}]*mission\s*=\s*'"
        + re.escape(mission_name)
        + r"'[^}]*\}\s*,\s*\{([^}]*)\}\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(content):
        block = match.group(1)
        ws = re.search(r"weapon_state_planned\s*=\s*'([^']+)'", block, re.IGNORECASE)
        if ws:
            return ws.group(1)
    return None

def _parse_mission_schedule_settings(content):
    """mission_name -> {starttime, takeoff_time} from ScenEdit_SetMission."""
    settings = {}
    lua_vars = _parse_lua_string_vars(content)
    pattern = re.compile(
        r"ScenEdit_SetMission\s*\(\s*'[^']*'\s*,\s*([^,]+)\s*,\s*\{([^}]*)\}",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(content):
        mission = _resolve_lua_mission_name(match.group(1), lua_vars)
        block = match.group(2)
        row = settings.setdefault(mission, {})
        start = _parse_lua_mission_option_value(block, "starttime")
        if start:
            row["starttime"] = start
        takeoff = _parse_lua_mission_option_value(block, "TakeOffTime")
        if takeoff:
            row["takeoff_time"] = takeoff
        tot_station = _parse_lua_mission_option_value(block, "TimeOnTargetStation")
        if tot_station:
            row["time_on_target"] = tot_station
    for mission, row in settings.items():
        for key in ("starttime", "takeoff_time", "time_on_target"):
            if key not in row:
                continue
            resolved = _resolve_lua_datetime_token(row[key], lua_vars)
            if resolved:
                row[key] = resolved
    settings.update(_parse_sead_timed_mission_loop(content))
    settings.update(_parse_isr_on_station_schedule(content))
    settings.update(_parse_naval_timed_mission_loop(content))
    settings.update(_parse_bootstrap_naval_schedule(content))
    return settings

def _parse_isr_on_station_schedule(content):
    """ISR Support on-station via set_patrol_on_station_schedule (CreateMissionFlightPlan TIMEONTARGET)."""
    date = _parse_strike_package_date(content)
    isr_station_m = re.search(
        r"local\s+isr_on_station_time\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    isr_missions = _parse_isr_mission_names(content)
    if not (date and isr_station_m and isr_missions):
        return {}
    has_isr_schedule = bool(
        re.search(
            r"set_patrol_on_station_schedule\s*\([^)]*ISR_WEST_MISSION",
            content,
            re.IGNORECASE,
        )
        or re.search(
            r"set_patrol_on_station_schedule\s*\([^)]*ISR_EAST_MISSION",
            content,
            re.IGNORECASE,
        )
    )
    if not has_isr_schedule:
        primary = isr_missions[0]
        has_isr_schedule = bool(
            re.search(
                rf"set_patrol_on_station_schedule\s*\([^)]*{re.escape(primary)}",
                content,
                re.IGNORECASE,
            )
        )
    if not has_isr_schedule:
        return {}
    station = isr_station_m.group(1)
    mission = isr_missions[0]
    return {mission: {"time_on_target": f"{date} {station}"}}

def _parse_bootstrap_naval_schedule(content):
    """TLAM schedule via setup_csg_strike_on_air_strike + set_naval_strike_schedule."""
    if not re.search(r"function\s+M\.setup_csg_strike_on_air_strike\s*\(", content, re.IGNORECASE):
        return {}
    timing = _parse_lua_timing_vars(content)
    date = timing.get("strike_package_date")
    launch = timing.get("tlam_launch_time")
    tot = timing.get("strike_package_tot")
    if not (date and tot):
        return {}
    if not re.search(
        r"(?<!function\s)setup_csg_strike_on_air_strike\s*\(",
        content,
        re.IGNORECASE,
    ):
        return {}
    mission = _resolve_tlam_strike_mission(content)
    if not mission:
        return {}
    tot_dt = f"{date} {tot}"
    row = {"time_on_target": tot_dt}
    if launch:
        launch_dt = f"{date} {launch}"
        row["starttime"] = launch_dt
        row["takeoff_time"] = launch_dt
    return {mission: row}

def _parse_sead_timed_mission_loop(content):
    """Variable-based SEAD delay loop: for _, sead_mission in ipairs(sead_timed_missions)."""
    date = _parse_strike_package_date(content)
    station_m = re.search(r"local\s+sead_on_station_time\s*=\s*'([^']+)'", content, re.IGNORECASE)
    takeoff_m = re.search(r"local\s+sead_package_takeoff\s*=\s*'([^']+)'", content, re.IGNORECASE)
    list_m = re.search(
        r"local\s+sead_(?:timed|shooter)_missions\s*=\s*\{([^}]+)\}",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not (date and list_m):
        return {}
    if not re.search(
        r"for\s+_\s*,\s*sead_mission\s+in\s+ipairs\s*\(\s*sead_(?:timed|shooter)_missions\s*\)",
        content,
        re.IGNORECASE,
    ):
        return {}
    shooter_missions = re.findall(r"'([^']+)'", list_m.group(1))
    escort_list_m = re.search(
        r"local\s+sead_escort_missions\s*=\s*\{([^}]+)\}",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    escort_station_m = re.search(
        r"local\s+sead_escort_on_station_time\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    escort_missions = (
        re.findall(r"'([^']+)'", escort_list_m.group(1)) if escort_list_m else []
    )
    escort_station = escort_station_m.group(1) if escort_station_m else None
    if station_m and re.search(
        r"set_patrol_on_station_schedule\s*\([\s\S]*?sead_on_station_dt",
        content,
        re.IGNORECASE,
    ):
        station = station_m.group(1)
        result = {m: {"time_on_target": f"{date} {station}"} for m in shooter_missions}
        if escort_missions and escort_station and re.search(
            r"for\s+_\s*,\s*escort_mission\s+in\s+ipairs\s*\(\s*sead_escort_missions\s*\)",
            content,
            re.IGNORECASE,
        ):
            for em in escort_missions:
                result[em] = {"time_on_target": f"{date} {escort_station}"}
        return result
    if takeoff_m and re.search(
        r"ScenEdit_SetMission\s*\([\s\S]*?starttime\s*=\s*sead_launch_dt",
        content,
        re.IGNORECASE,
    ):
        takeoff = takeoff_m.group(1)
        launch_dt = f"{date} {takeoff}"
        return {
            m: {"starttime": launch_dt, "takeoff_time": launch_dt} for m in shooter_missions
        }
    return {}

def _parse_naval_timed_mission_loop(content):
    """ScenEdit_SetMission for timed naval strike blocks with tlam_launch_dt."""
    date = _parse_strike_package_date(content)
    launch_m = re.search(r"local\s+tlam_launch_time\s*=\s*'([^']+)'", content, re.IGNORECASE)
    tot_m = re.search(r"local\s+strike_package_tot\s*=\s*'([^']+)'", content, re.IGNORECASE)
    mission_m = re.search(
        r"ScenEdit_SetMission\s*\(\s*'[^']*'\s*,\s*([^,]+)\s*,\s*\{[\s\S]*?"
        r"starttime\s*=\s*(?:tlam_launch_dt|launch_dt|"
        r"mission_schedule_datetime\s*\(\s*strike_package_date\s*,\s*tlam_launch_time\s*\))",
        content,
        re.IGNORECASE,
    )
    if not (date and launch_m and mission_m):
        return {}
    lua_vars = _parse_lua_string_vars(content)
    mission_name = _resolve_lua_mission_name(mission_m.group(1), lua_vars)
    launch_dt = f"{date} {launch_m.group(1)}"
    row = {
        "starttime": launch_dt,
        "takeoff_time": launch_dt,
    }
    if tot_m:
        row["time_on_target"] = f"{date} {tot_m.group(1)}"
    return {mission_name: row}

def _aircraft_count_on_strike_missions(content, mission_map):
    """Strike mission name -> number of air wing spawns (excludes ships)."""
    strike_names = {n for n, role in mission_map.items() if role == "strike"}
    counts = {n: 0 for n in strike_names}
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'[^']*'\s*,\s*(\d+)\s*,\s*\d+\s*,\s*\d+\s*,\s*'([^']+)'\s*,",
        re.IGNORECASE,
    )
    for match in wing_pattern.finditer(content):
        mission = match.group(2)
        if mission in counts:
            counts[mission] += int(match.group(1))
    helper_pattern = re.compile(
        r"add_air_unit_checked\s*\(\s*'[^']*'\s*,\s*[^,]+,\s*(\d+)\s*,\s*[^,]+,\s*(\d+|nil)\s*,\s*'([^']*)'",
        re.IGNORECASE,
    )
    for match in helper_pattern.finditer(content):
        if match.group(2).lower() == "nil":
            continue
        mission = match.group(3)
        if mission in counts:
            counts[mission] += 1
    return counts

def _parse_scenario_year(content):
    match = re.search(r"scenario_year\s*=\s*(\d{4})", content, re.IGNORECASE)
    return int(match.group(1)) if match else None

def _parse_scenario_date(content):
    """local scenario_date = 'YYYY/MM/DD' — canonical in-game calendar day."""
    match = re.search(r"local\s+scenario_date\s*=\s*'([^']+)'", content, re.IGNORECASE)
    return _normalize_date_slash_key(match.group(1)) if match else None

def _parse_strike_package_date(content):
    """Strike-package calendar day (literal or aliased from scenario_date)."""
    match = re.search(
        r"local\s+strike_package_date\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    if match:
        return _normalize_date_slash_key(match.group(1))
    return _parse_scenario_date(content)

def _parse_scenario_start_time(content):
    """(date_key, time_hhmmss) from ScenEdit_SetTime or cmo.scenario_set_start."""
    helper = re.search(
        r"(?:cmo\.)?scenario_set_start\s*\(\s*(?:scenario_date|strike_package_date)\s*,\s*(?:scenario_start_time|['\"]([^'\"]+)['\"])\s*\)",
        content,
        re.IGNORECASE,
    )
    if helper:
        canon = _parse_scenario_date(content)
        if canon:
            time_val = helper.group(1)
            if not time_val:
                tm = re.search(r"local\s+scenario_start_time\s*=\s*'([^']+)'", content, re.IGNORECASE)
                time_val = tm.group(1) if tm else None
            return _normalize_date_key(canon), time_val
    match = re.search(
        r"ScenEdit_SetTime\s*\(\s*\{([^}]*)\}",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None, None
    block = match.group(1)
    start_time = _parse_lua_mission_option_value(block, "StartTime") or _parse_lua_mission_option_value(
        block, "time"
    )
    start_date = _parse_lua_mission_option_value(block, "StartDate") or _parse_lua_mission_option_value(
        block, "date"
    )
    return _normalize_date_key(start_date), start_time

def _strike_air_counts_by_mission(content, mission_map):
    """Per strike mission: striker/escort counts from all spawn_air_wing rows."""
    from preflight_parse_units import _parse_air_spawn_wing_specs

    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    counts = {}
    for spec in _parse_air_spawn_wing_specs(content):
        mission = spec["mission"]
        if mission not in strike_missions:
            continue
        bucket = counts.setdefault(mission, {"strikers": 0, "escorts": 0})
        if spec["escort"]:
            bucket["escorts"] += spec["count"]
        else:
            bucket["strikers"] += spec["count"]
    return counts

def _carrier_air_counts_by_mission(content):
    """Per strike mission: carrier-based striker/escort counts from spawn_air_wing on carrier.guid."""
    carrier_vars = set(
        re.findall(r"(?:local\s+)?(\w+)\s*=\s*place_ship", content, flags=re.IGNORECASE)
    )
    counts = {}
    pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'[^']*'\s*,\s*[^,]+,\s*(\d+)\s*,\s*\d+\s*,\s*\d+\s*,\s*'([^']+)'\s*,\s*(\w+)\.guid(?:\s*,\s*(true|false))?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(content):
        if match.group(3) not in carrier_vars:
            continue
        n = int(match.group(1))
        mission = match.group(2)
        is_escort = _parse_lua_bool(match.group(4)) if match.group(4) else False
        bucket = counts.setdefault(mission, {"strikers": 0, "escorts": 0})
        if is_escort:
            bucket["escorts"] += n
        else:
            bucket["strikers"] += n
    return counts

def _sead_missions_needing_delayed_launch(content, mission_map, carrier_counts):
    """SEAD patrol names + SEAD Escort CAP when carrier-based SEAD package is large."""
    names = {n for n, role in mission_map.items() if role == "sead"}
    for mname, counts in carrier_counts.items():
        if "SEAD" in mname.upper() and "ESCORT" in mname.upper() and counts.get("strikers", 0) >= 4:
            names.add(mname)
    return names

def _parse_set_mission_strike_flight_settings(content):
    """mission_name -> strike/escort flight-size options from SetMission / configure_strike_mission_options."""
    settings = {}
    lua_vars = _parse_lua_string_vars(content)
    pattern = re.compile(
        r"(?:ScenEdit_SetMission|configure_strike_mission_options)\s*\(\s*(?:'[^']*'|\w+)\s*,\s*(?:'([^']+)'|(\w+))\s*,\s*\{([^}]*)\}",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(content):
        mission = _resolve_lua_mission_name(match.group(1) or match.group(2), lua_vars)
        block = match.group(3)
        row = settings.setdefault(mission, {})
        for src_key, dst_key in (
            ("StrikeUseFlightSize", "strike_use_flight_size"),
            ("UseFlightSize", "strike_use_flight_size"),
            ("useflightsize", "strike_use_flight_size"),
            ("StrikeFlightSize", "strike_flight_size"),
            ("FlightSize", "strike_flight_size"),
            ("StrikeMinAircraftReq", "strike_min_aircraft"),
            ("EscortUseFlightSize", "escort_use_flight_size"),
            ("EscortFlightSizeShooter", "escort_flight_size"),
            ("EscortMinShooter", "escort_min_shooter"),
        ):
            if dst_key in ("strike_flight_size", "escort_flight_size"):
                val = _parse_lua_mission_option_value(block, src_key)
                if val is not None:
                    row[dst_key] = _parse_flight_size_value(val)
            elif dst_key in ("strike_min_aircraft", "escort_min_shooter"):
                val = _parse_lua_mission_option_value(block, src_key)
                if val is not None and str(val).isdigit():
                    row[dst_key] = int(val)
            else:
                bool_val = _parse_lua_mission_option_bool(block, src_key)
                if bool_val is not None:
                    row[dst_key] = bool_val
    return settings

__all__ = ['_aircraft_count_on_strike_missions', '_carrier_air_counts_by_mission', '_classify_scenario_mission', '_csg_allowed_ship_strike_missions', '_enemy_sam_sites_for_sead_side', '_merge_strike_package_annotations', '_parse_bootstrap_naval_schedule', '_parse_hostile_postures', '_parse_isr_mission_names', '_parse_isr_on_station_schedule', '_parse_isr_package_annotations', '_parse_mission_flight_plan_calls', '_parse_mission_land_wcs_overrides', '_parse_mission_schedule_settings', '_parse_mission_zone_map', '_parse_naval_package_annotations', '_parse_naval_timed_mission_loop', '_parse_sam_sites', '_parse_scenario_date', '_parse_scenario_missions', '_parse_scenario_policy_nuclear', '_parse_scenario_start_time', '_parse_scenario_year', '_parse_sead_mission_names', '_parse_sead_package_annotations', '_parse_sead_timed_mission_loop', '_parse_set_mission_strike_flight_settings', '_parse_side_land_wcs', '_parse_strike_package_annotations', '_parse_strike_package_date', '_parse_strike_refuel_doctrine', '_parse_strike_weapon_state_planned', '_parse_task_pool_annotations', '_parse_use_nuclear_weapons_doctrine', '_resolve_strike_air_mission', '_resolve_strike_taskpool', '_resolve_tlam_strike_mission', '_sead_missions_needing_delayed_launch', '_sides_with_sead_missions', '_strike_air_counts_by_mission']
