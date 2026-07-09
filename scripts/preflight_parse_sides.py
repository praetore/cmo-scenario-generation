"""Sides and reference-point parsers."""

import math
import re
from pathlib import Path

from preflight_constants import *
from preflight_parse_io import _line_number_at, _scenario_lua_body
from preflight_parse_lua import _parse_lua_coord_pairs, _parse_lua_string_vars, _resolve_lua_coord, _resolve_lua_mission_name, _resolve_lua_side_token

def _parse_reference_points(content):
    """Reference point name -> (latitude, longitude)."""
    points = {}
    patterns = (
        re.compile(
            r"ScenEdit_AddReferencePoint\s*\(\s*\{[^}]*name\s*=\s*'([^']+)'[^}]*"
            r"latitude\s*=\s*([\d.]+)[^}]*longitude\s*=\s*([-\d.]+)",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"ScenEdit_AddReferencePoint\s*\(\s*\{[^}]*name\s*=\s*'([^']+)'[^}]*"
            r"longitude\s*=\s*([-\d.]+)[^}]*latitude\s*=\s*([\d.]+)",
            re.IGNORECASE | re.DOTALL,
        ),
    )
    for pattern in patterns:
        for match in pattern.finditer(content):
            if pattern is patterns[0]:
                points[match.group(1)] = (float(match.group(2)), float(match.group(3)))
            else:
                points[match.group(1)] = (float(match.group(3)), float(match.group(2)))
    return points

def _parse_reference_points_resolved(content):
    """All reference points including latitude=csg_lat + offset style expressions."""
    consts = _parse_lua_coord_pairs(content)
    points = _parse_reference_points(content)
    expr_pattern = re.compile(
        r"ScenEdit_AddReferencePoint\s*\(\s*\{[^}]*name\s*=\s*'([^']+)'[^}]*"
        r"latitude\s*=\s*([^,}]+)[^}]*longitude\s*=\s*([^,}]+)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in expr_pattern.finditer(content):
        name = match.group(1)
        if name in points:
            continue
        lat = _resolve_lua_coord(match.group(2).strip(), consts)
        lon = _resolve_lua_coord(match.group(3).strip(), consts)
        if lat is not None and lon is not None:
            points[name] = (lat, lon)
    return points, consts

def _parse_reference_point_calls(content):
    """
    Each ScenEdit_AddReferencePoint({...}) call.

    Returns list of dicts: name, side (resolved or None), line, has_side (bool).
    """
    body = _scenario_lua_body(content)
    lua_vars = _parse_lua_string_vars(body)
    rows = []
    pattern = re.compile(
        r"ScenEdit_AddReferencePoint\s*\(\s*\{([^}]*)\}\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(body):
        block = match.group(1)
        name_m = re.search(r"\bname\s*=\s*'([^']*)'", block, re.IGNORECASE)
        side_m = re.search(r"\bside\s*=\s*([^,}\n]+)", block, re.IGNORECASE)
        side = None
        has_side = side_m is not None
        if side_m:
            side = _resolve_lua_side_token(side_m.group(1), lua_vars)
        rows.append(
            {
                "name": name_m.group(1) if name_m else None,
                "side": side,
                "line": _line_number_at(body, match.start()),
                "has_side": has_side,
            }
        )
    return rows

def _parse_mission_side_zones(content):
    """(side, mission_name, [zone_rp_names]) from ScenEdit_AddMission with zone={...}."""
    body = _scenario_lua_body(content)
    lua_vars = _parse_lua_string_vars(body)
    rows = []
    header = re.compile(
        r"ScenEdit_AddMission\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,",
        re.IGNORECASE,
    )
    for match in header.finditer(body):
        side = _resolve_lua_side_token(match.group(1), lua_vars)
        mission = _resolve_lua_mission_name(match.group(2), lua_vars)
        opts_start = body.find("{", match.end())
        if opts_start < 0:
            continue
        depth = 0
        opts_end = None
        for i in range(opts_start, len(body)):
            ch = body[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    opts_end = i + 1
                    break
        if opts_end is None:
            continue
        snippet = body[opts_start:opts_end]
        zone_m = re.search(r"zone\s*=\s*\{([^}]+)\}", snippet, re.IGNORECASE)
        if not zone_m:
            continue
        zone_names = re.findall(r"'([^']+)'", zone_m.group(1))
        if side and mission and zone_names:
            rows.append((side, mission, zone_names))
    return rows

def _reference_points_by_side_name(content):
    """Set of (side, rp_name) from AddReferencePoint calls that declare side=."""
    out = set()
    for row in _parse_reference_point_calls(content):
        if row["has_side"] and row["side"] and row["name"]:
            out.add((row["side"], row["name"]))
    return out

def _parse_scenario_sides(content):
    """
    Collect sides created via ScenEdit_AddSide and sides referenced by ScenEdit_* / spawn helpers.

    Returns:
        added: dict side_name -> line number of first ScenEdit_AddSide
        referenced: dict side_name -> (line number of first use, api hint)
    """
    body = _scenario_lua_body(content)
    lua_vars = _parse_lua_string_vars(body)
    added = {}
    referenced = {}

    def note_added(side, line_no):
        if side and side not in added:
            added[side] = line_no

    def note_ref(side, line_no, api):
        if side and side not in referenced:
            referenced[side] = (line_no, api)

    for match in re.finditer(
        r"ScenEdit_AddSide\s*\(\s*\{[^}]*\bside\s*=\s*([^,}]+)",
        body,
        re.IGNORECASE | re.DOTALL,
    ):
        side = _resolve_lua_side_token(match.group(1), lua_vars)
        note_added(side, _line_number_at(body, match.start()))

    ref_patterns = (
        (
            "SetSidePosture",
            re.compile(
                r"ScenEdit_SetSidePosture\s*\(\s*([^,]+)\s*,\s*([^,]+)\s*,",
                re.IGNORECASE,
            ),
            lambda m: (
                _resolve_lua_side_token(m.group(1), lua_vars),
                _resolve_lua_side_token(m.group(2), lua_vars),
            ),
        ),
        (
            "SetSideOptions",
            re.compile(
                r"ScenEdit_SetSideOptions\s*\(\s*\{[^}]*\bside\s*=\s*([^,}]+)",
                re.IGNORECASE | re.DOTALL,
            ),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "AddMission",
            re.compile(r"ScenEdit_AddMission\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "SetMission",
            re.compile(r"ScenEdit_SetMission\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "SetDoctrine",
            re.compile(
                r"ScenEdit_SetDoctrine\s*\(\s*\{[^}]*\bside\s*=\s*([^,}]+)",
                re.IGNORECASE | re.DOTALL,
            ),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "CreateMissionFlightPlan",
            re.compile(
                r"ScenEdit_CreateMissionFlightPlan\s*\(\s*([^,]+)\s*,",
                re.IGNORECASE,
            ),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "spawn_air_wing",
            re.compile(r"spawn_air_wing\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "add_air_unit_checked",
            re.compile(r"add_air_unit_checked\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "place_ship",
            re.compile(r"place_ship\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "place_sub",
            re.compile(r"place_sub\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "place_sam",
            re.compile(r"place_sam\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "place_base",
            re.compile(r"place_base\s*\(\s*([^,]+)\s*,", re.IGNORECASE),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
        (
            "configure_strike_timing",
            re.compile(
                r"configure_strike_timing\s*\(\s*\{[^}]*\bside\s*=\s*([^,}]+)",
                re.IGNORECASE | re.DOTALL,
            ),
            lambda m: (_resolve_lua_side_token(m.group(1), lua_vars),),
        ),
    )

    for api, pattern, extract in ref_patterns:
        for match in pattern.finditer(body):
            line_no = _line_number_at(body, match.start())
            for side in extract(match):
                note_ref(side, line_no, api)

    for match in re.finditer(
        r"ScenEdit_AddUnit\s*\(\s*\{([^}]*)\}\s*\)",
        body,
        re.IGNORECASE | re.DOTALL,
    ):
        block = match.group(1)
        side_m = re.search(r"\bside\s*=\s*([^,}\n]+)", block, re.IGNORECASE)
        if side_m:
            side = _resolve_lua_side_token(side_m.group(1), lua_vars)
            note_ref(side, _line_number_at(body, match.start()), "AddUnit")

    return added, referenced

__all__ = ['_parse_mission_side_zones', '_parse_reference_point_calls', '_parse_reference_points', '_parse_reference_points_resolved', '_parse_scenario_sides', '_reference_points_by_side_name']
