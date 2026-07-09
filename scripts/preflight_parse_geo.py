"""Ship, sub, and facility placement parsers."""

import math
import re
from pathlib import Path

from preflight_constants import *
from preflight_parse_io import _line_number_at, _scenario_lua_body
from preflight_parse_lua import _parse_lua_coord_pairs, _parse_lua_string_vars, _resolve_lua_coord, _resolve_side_token
from preflight_parse_db import _infer_mission_role
from preflight_parse_missions import _parse_hostile_postures, _parse_sam_sites

def _append_geo_unit(units, body, match, kind, source, side_expr, name, dbid, lat_expr, lon_expr, var=None):
    consts = _parse_lua_coord_pairs(body)
    lua_vars = _parse_lua_string_vars(body)
    lat = _resolve_lua_coord(lat_expr, consts)
    lon = _resolve_lua_coord(lon_expr, consts)
    if lat is None or lon is None:
        return
    units.append(
        {
            "kind": kind,
            "source": source,
            "side": _resolve_side_token(side_expr, lua_vars),
            "name": name,
            "dbid": dbid,
            "lat": lat,
            "lon": lon,
            "var": var,
            "line": _line_number_at(body, match.start()),
        }
    )

def _parse_ship_placements(content):
    """List of {side, name, dbid, lat, lon, var?, kind='ship'} from place_ship in Lua."""
    body = _scenario_lua_body(content)
    ships = []
    assign_pattern = re.compile(
        r"(?:local\s+)?(\w+)\s*=\s*place_ship\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*([^,]+),\s*([^)]+)\s*\)",
        re.IGNORECASE,
    )
    direct_pattern = re.compile(
        r"^[ \t]*place_ship\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*([^,]+),\s*([^)]+)\s*\)",
        re.IGNORECASE | re.MULTILINE,
    )
    for match in assign_pattern.finditer(body):
        _append_geo_unit(
            ships, body, match, "ship", "place_ship",
            match.group(2), match.group(3), int(match.group(4)),
            match.group(5), match.group(6), var=match.group(1),
        )
    for match in direct_pattern.finditer(body):
        _append_geo_unit(
            ships, body, match, "ship", "place_ship",
            match.group(1), match.group(2), int(match.group(3)),
            match.group(4), match.group(5),
        )
    return ships

def _parse_sub_placements(content):
    """List of {side, name, dbid, lat, lon, var?, kind='sub'} from place_sub in Lua."""
    body = _scenario_lua_body(content)
    subs = []
    assign_pattern = re.compile(
        r"(?:local\s+)?(\w+)\s*=\s*place_sub\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*([^,]+),\s*([^)]+)\s*\)",
        re.IGNORECASE,
    )
    for match in assign_pattern.finditer(body):
        _append_geo_unit(
            subs, body, match, "sub", "place_sub",
            match.group(2), match.group(3), int(match.group(4)),
            match.group(5), match.group(6), var=match.group(1),
        )
    return subs

def _parse_facility_placements(content):
    """place_base / place_sam and ScenEdit_AddUnit type Facility with explicit lat/lon."""
    body = _scenario_lua_body(content)
    facilities = []
    patterns = (
        (
            "facility",
            "place_base",
            re.compile(
                r"(?:local\s+)?(\w+)\s*=\s*place_base\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*([^,]+),\s*([^)]+)\s*\)",
                re.IGNORECASE,
            ),
            lambda m: (m.group(2), m.group(3), None, m.group(4), m.group(5), m.group(1)),
        ),
        (
            "facility",
            "place_sam",
            re.compile(
                r"(?:local\s+)?(\w+)\s*=\s*place_sam\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*([^,]+),\s*([^)]+)\s*\)",
                re.IGNORECASE,
            ),
            lambda m: (m.group(2), m.group(3), int(m.group(4)), m.group(5), m.group(6), m.group(1)),
        ),
        (
            "facility",
            "place_base",
            re.compile(
                r"^[ \t]*place_base\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*([^,]+),\s*([^)]+)\s*\)",
                re.IGNORECASE | re.MULTILINE,
            ),
            lambda m: (m.group(1), m.group(2), None, m.group(3), m.group(4), None),
        ),
        (
            "facility",
            "place_sam",
            re.compile(
                r"^[ \t]*place_sam\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*([^,]+),\s*([^)]+)\s*\)",
                re.IGNORECASE | re.MULTILINE,
            ),
            lambda m: (m.group(1), m.group(2), int(m.group(3)), m.group(4), m.group(5), None),
        ),
        (
            "facility",
            "register_civilian_airport",
            re.compile(
                r"(?:local\s+)?(\w+)\s*=\s*(?:cmo\.)?register_civilian_airport\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*([^,]+),\s*([^)]+)\s*\)",
                re.IGNORECASE,
            ),
            lambda m: (m.group(2), m.group(3), None, m.group(4), m.group(5), m.group(1)),
        ),
        (
            "facility",
            "register_civilian_airport",
            re.compile(
                r"^[ \t]*(?:cmo\.)?register_civilian_airport\s*\(\s*([^,]+)\s*,\s*'([^']*)'\s*,\s*([^,]+),\s*([^)]+)\s*\)",
                re.IGNORECASE | re.MULTILINE,
            ),
            lambda m: (m.group(1), m.group(2), None, m.group(3), m.group(4), None),
        ),
    )
    for kind, source, pattern, extract in patterns:
        for match in pattern.finditer(body):
            side, name, dbid, lat_expr, lon_expr, var = extract(match)
            _append_geo_unit(
                facilities, body, match, kind, source,
                side, name, dbid, lat_expr, lon_expr, var=var,
            )

    add_unit_pattern = re.compile(
        r"ScenEdit_AddUnit\s*\(\s*\{([^}]*)\}\s*\)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in add_unit_pattern.finditer(body):
        block = match.group(1)
        if not re.search(r"type\s*=\s*'Facility'", block, re.IGNORECASE):
            continue
        if re.search(r"\bbase\s*=", block, re.IGNORECASE):
            continue
        name_m = re.search(r"\bunitname\s*=\s*'([^']*)'", block, re.IGNORECASE)
        side_m = re.search(r"\bside\s*=\s*([^,}\n]+)", block, re.IGNORECASE)
        lat_m = re.search(r"\blatitude\s*=\s*([^,}\n]+)", block, re.IGNORECASE)
        lon_m = re.search(r"\blongitude\s*=\s*([^,}\n]+)", block, re.IGNORECASE)
        dbid_m = re.search(r"\bdbid\s*=\s*(\d+)", block, re.IGNORECASE)
        if not (side_m and lat_m and lon_m):
            continue
        _append_geo_unit(
            facilities,
            body,
            match,
            "facility",
            "AddUnit",
            side_m.group(1),
            name_m.group(1) if name_m else "(unnamed facility)",
            int(dbid_m.group(1)) if dbid_m else None,
            lat_m.group(1),
            lon_m.group(1),
        )
    return facilities

def _parse_naval_placements(content):
    ships = _parse_ship_placements(content)
    for sub in _parse_sub_placements(content):
        ships.append(sub)
    return ships

def _parse_all_geo_placements(content):
    """Every independently geo-placed unit: ship, sub, facility (land vs water rules)."""
    units = _parse_naval_placements(content)
    units.extend(_parse_facility_placements(content))
    return units

def _parse_geo_unit_positions(content):
    """ref (var or table.field) -> {lat, lon, name, side}."""
    positions = {}
    consts = _parse_lua_coord_pairs(content)

    base_pattern = re.compile(
        r"(?:local\s+)?([\w.]+)\s*=\s*place_base\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*([^,]+),\s*([^)]+)\s*\)",
        re.IGNORECASE,
    )
    for match in base_pattern.finditer(content):
        lat = _resolve_lua_coord(match.group(4), consts)
        lon = _resolve_lua_coord(match.group(5), consts)
        if lat is None or lon is None:
            continue
        positions[match.group(1)] = {
            "lat": lat,
            "lon": lon,
            "name": match.group(3),
            "side": match.group(2),
        }

    sam_pattern = re.compile(
        r"(?:local\s+)?(\w+)\s*=\s*place_sam\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*\d+\s*,\s*([\d.]+)\s*,\s*([-\d.]+)\s*\)",
        re.IGNORECASE,
    )
    for match in sam_pattern.finditer(content):
        positions[match.group(1)] = {
            "lat": float(match.group(4)),
            "lon": float(match.group(5)),
            "name": match.group(3),
            "side": match.group(2),
        }

    table_sam = re.compile(
        r"(\w+)\s*=\s*place_sam\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*\d+\s*,\s*([\d.]+)\s*,\s*([-\d.]+)\s*\)",
        re.IGNORECASE,
    )
    for table_match in re.finditer(
        r"(\w+)\s*=\s*\{([^}]*place_sam[^}]*)\}", content, re.IGNORECASE | re.DOTALL
    ):
        table_var = table_match.group(1)
        for match in table_sam.finditer(table_match.group(2)):
            ref = f"{table_var}.{match.group(1)}"
            positions[ref] = {
                "lat": float(match.group(4)),
                "lon": float(match.group(5)),
                "name": match.group(3),
                "side": match.group(2),
            }
    return positions

def _parse_strike_land_target_coords(content, mission_map, striker_side="United States"):
    """
    Lat/lon of land targets for reachability: explicit AssignUnitAsTarget plus
    all hostile-side bases/SAMs when the scenario assigns via pairs() loops.
    """
    positions = _parse_geo_unit_positions(content)
    coords = []
    seen = set()

    def add_coord(ref, row, mission="strike"):
        key = (round(row["lat"], 4), round(row["lon"], 4))
        if key in seen:
            return
        seen.add(key)
        coords.append(
            {
                "ref": ref,
                "name": row.get("name") or ref,
                "lat": row["lat"],
                "lon": row["lon"],
                "mission": mission,
            }
        )

    for match in re.finditer(
        r"ScenEdit_AssignUnitAsTarget\s*\(\s*([\w.]+)\.guid\s*,\s*'([^']+)'\s*\)",
        content,
        re.IGNORECASE,
    ):
        ref = match.group(1)
        mission = match.group(2)
        if _infer_mission_role(mission, mission_map) != "strike":
            continue
        row = positions.get(ref)
        if row:
            add_coord(ref, row, mission)

    hostile_to_striker = {
        b for a, b in _parse_hostile_postures(content) if a == striker_side
    }
    for ref, row in positions.items():
        if row.get("side") in hostile_to_striker:
            add_coord(ref, row)
    for side, lat, lon in _parse_sam_sites(content):
        if side in hostile_to_striker:
            add_coord(
                f"sam:{lat},{lon}",
                {"lat": lat, "lon": lon, "name": f"SAM ({lat}, {lon})", "side": side},
            )
    return coords

__all__ = ['_append_geo_unit', '_parse_all_geo_placements', '_parse_facility_placements', '_parse_geo_unit_positions', '_parse_naval_placements', '_parse_ship_placements', '_parse_strike_land_target_coords', '_parse_sub_placements']
