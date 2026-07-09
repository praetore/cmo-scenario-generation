"""Lua expression and annotation parsing helpers."""

import math
import re
from pathlib import Path

from preflight_constants import *

def _parse_lua_coord_pairs(content):
    """Map Lua variable names to floats from `local a, b = lat, lon` declarations."""
    consts = {}
    pair_pattern = re.compile(
        r"local\s+(\w+)\s*,\s*(\w+)\s*=\s*([-\d.]+)\s*,\s*([-\d.]+)",
        re.IGNORECASE,
    )
    for match in pair_pattern.finditer(content):
        consts[match.group(1)] = float(match.group(3))
        consts[match.group(2)] = float(match.group(4))
    return consts

def _resolve_lua_coord(expr, consts):
    expr = expr.strip()
    if re.fullmatch(r"-?[\d.]+", expr):
        return float(expr)
    if expr in consts:
        return consts[expr]
    add = re.fullmatch(r"(\w+)\s*\+\s*([\d.]+)", expr)
    if add and add.group(1) in consts:
        return consts[add.group(1)] + float(add.group(2))
    sub = re.fullmatch(r"(\w+)\s*-\s*([\d.]+)", expr)
    if sub and sub.group(1) in consts:
        return consts[sub.group(1)] - float(sub.group(2))
    return None

def _resolve_side_token(side_expr, lua_vars):
    return _resolve_lua_side_token(side_expr, lua_vars) or side_expr.strip().strip("'\"")

def _resolve_lua_side_token(token, lua_vars):
    """Resolve 'France', SIDE_FR, or \"Libya\" to a side name string."""
    if not token:
        return None
    token = token.strip()
    if (token.startswith("'") and token.endswith("'")) or (
        token.startswith('"') and token.endswith('"')
    ):
        return token.strip("'\"")
    return lua_vars.get(token.lower())

def _parse_lua_string_vars(content):
    """local name = 'value' string assignments."""
    vars_map = {}
    for match in re.finditer(
        r"local\s+(\w+)\s*=\s*'([^']*)'",
        content,
        re.IGNORECASE,
    ):
        vars_map[match.group(1).lower()] = match.group(2)
    return _expand_lua_datetime_vars(vars_map)

def _expand_lua_datetime_vars(vars_map):
    """Derived datetimes from strike_package_date + time fragments."""
    expanded = dict(vars_map)
    date = expanded.get("strike_package_date")
    tot = expanded.get("strike_package_tot")
    if date and tot:
        date_dots = date.replace("/", ".")
        expanded["strike_tot_dt"] = f"{date_dots} {tot}"
        expanded["tot_dt"] = expanded["strike_tot_dt"]
    launch = expanded.get("tlam_launch_time")
    if date and launch:
        date_dots = date.replace("/", ".")
        expanded["tlam_launch_dt"] = f"{date_dots} {launch}"
        expanded["launch_dt"] = expanded["tlam_launch_dt"]
    sead = expanded.get("sead_package_takeoff")
    if date and sead:
        expanded["sead_launch_dt"] = f"{date} {sead}"
    csg_helo = expanded.get("csg_helo_takeoff")
    if date and csg_helo:
        expanded["csg_helo_launch_dt"] = f"{date} {csg_helo}"
    for time_key, dt_key in (
        ("isr_launch_time", "isr_launch_dt"),
        ("aew_launch_time", "aew_launch_dt"),
        ("cap_launch_time", "cap_launch_dt"),
    ):
        hhmm = expanded.get(time_key)
        if date and hhmm:
            expanded[dt_key] = f"{date} {hhmm}"
    for key, val in expanded.items():
        if key.endswith("_mission_start") and date and val:
            expanded.setdefault("defender_mission_start_dt", f"{date} {val}")
    return expanded

def _resolve_lua_datetime_token(token, lua_vars):
    if not token:
        return None
    token = token.strip()
    if (token.startswith("'") and token.endswith("'")) or (
        token.startswith('"') and token.endswith('"')
    ):
        return token.strip("'\"")
    return lua_vars.get(token.lower())

def _resolve_lua_mission_name(name, lua_vars):
    """Resolve mission token (literal or local var like STRIKE_AIR_MISSION)."""
    if not name:
        return name
    bare = name.strip().strip("'\"")
    return lua_vars.get(bare.lower(), bare)

def _parse_lua_timing_vars(content):
    """strike_package_tot, tlam_launch_time, sead_on_station_time from local assignments."""
    out = {}
    for key in (
        "strike_package_tot",
        "tlam_launch_time",
        "sead_on_station_time",
        "sead_escort_on_station_time",
        "sead_package_takeoff",
        "isr_on_station_time",
        "strike_package_date",
        "cap_launch_time",
        "aew_launch_time",
    ):
        m = re.search(rf"local\s+{key}\s*=\s*'([^']+)'", content, re.IGNORECASE)
        if m:
            out[key] = m.group(1)
    if "strike_package_date" not in out:
        from preflight_parse_missions import _parse_strike_package_date

        spd = _parse_strike_package_date(content)
        if spd:
            out["strike_package_date"] = spd
    return out

def _parse_lua_local_string(content, var_name):
    match = re.search(
        rf"local\s+{re.escape(var_name)}\s*=\s*'([^']*)'",
        content,
        re.IGNORECASE,
    )
    return match.group(1) if match else None

def _parse_lua_string_list(content, var_name):
    match = re.search(
        rf"local\s+{re.escape(var_name)}\s*=\s*\{{([^}}]+)\}}",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    return re.findall(r"'([^']+)'", match.group(1))

def _parse_lua_base_facility_dbid(content):
    match = re.search(r"BASE_FACILITY_DBID\s*=\s*(\d+)", content, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None

def _parse_lua_bool(value):
    return value and value.lower() == "true"

def _parse_flight_size_value(raw):
    if raw is None:
        return None
    text = str(raw).strip().strip("'\"")
    if not text:
        return None
    if text.isdigit():
        return int(text)
    normalized = re.sub(r"[^a-z0-9]", "", text.lower())
    return _FLIGHT_SIZE_NAME_TO_INT.get(normalized)

def _parse_lua_mission_option_bool(block, *keys):
    for key in keys:
        match = re.search(rf"{re.escape(key)}\s*=\s*(true|false)", block, re.IGNORECASE)
        if match:
            return _parse_lua_bool(match.group(1))
    return None

def _parse_lua_mission_option_value(block, *keys):
    for key in keys:
        match = re.search(
            rf"{re.escape(key)}\s*=\s*('[^']*'|\"[^\"]*\"|[^,\s}}]+)",
            block,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip().strip("'\"")
    return None

def _parse_annotation_kv_blob(blob):
    """Parse @strike_package / @strike_wave key=value pairs (mission names may contain spaces)."""
    kv = {}
    blob = blob.strip()
    quoted = re.findall(r"([\w_]+)='([^']*)'", blob)
    for key, value in quoted:
        kv[key] = value
    if quoted:
        return kv
    known_keys = (
        "mission",
        "profile",
        "time",
        "date",
        "max_spread",
        "id",
        "role",
        "offset",
        "offset_minutes",
        "flight_size",
        "use_flight_size",
        "min_aircraft",
        "escort_flight_size",
        "escort_use_flight_size",
        "escort_min_shooter",
        "missions",
        "takeoff",
        "minutes_before_strike_tot",
        "launch",
        "tot",
        "name",
        "packages",
        "on_station",
        "recon_min",
        "transit_min",
        "drones",
        "west",
        "east",
        "before_sead_on_station",
        "escort_on_station",
        "escort_per_zone",
        "escort_flight_size",
        "escort_min_aircraft",
    )
    key_pattern = "|".join(known_keys)
    for match in re.finditer(rf"({key_pattern})=([^#]+?)(?=\s+(?:{key_pattern})=|$)", blob):
        kv[match.group(1)] = match.group(2).strip()
    if not kv:
        kv = dict(re.findall(r"([\w_]+)=([^\s#]+)", blob))
    return kv

__all__ = ['_expand_lua_datetime_vars', '_parse_annotation_kv_blob', '_parse_flight_size_value', '_parse_lua_base_facility_dbid', '_parse_lua_bool', '_parse_lua_coord_pairs', '_parse_lua_local_string', '_parse_lua_mission_option_bool', '_parse_lua_mission_option_value', '_parse_lua_string_list', '_parse_lua_string_vars', '_parse_lua_timing_vars', '_resolve_lua_coord', '_resolve_lua_datetime_token', '_resolve_lua_mission_name', '_resolve_lua_side_token', '_resolve_side_token']
