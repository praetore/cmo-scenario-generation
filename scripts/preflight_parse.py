"""Lua scenario parsing helpers for preflight validation."""

import math
import re
from pathlib import Path

from preflight_constants import *

def load_scenario_lua_content(scenario_path):
    """Scenario file plus scenario_bootstrap.lua when the scenario dofile's it."""
    path = Path(scenario_path)
    content = path.read_text(encoding="utf-8", errors="ignore")
    bootstrap = _read_bootstrap_lua_for_preflight(content)
    if bootstrap:
        content = content + "\n\n-- [preflight: scenario_bootstrap.lua]\n" + bootstrap
    return content

def _strip_lua_comment_lines(text):
    """Blank out full-line Lua comments (keeps line numbers stable).

    The bootstrap header documents usage with sample annotations and locals
    (e.g. ``-- @strike_package ... time=HH:MM:SS`` and
    ``--   local strike_package_tot = '06:30:00'``). When the bootstrap is
    appended for preflight, those comment lines would otherwise be parsed as if
    they were real scenario metadata, producing phantom strike/SEAD errors in
    non-strike scenarios. Stripping comment-only lines from the appended
    bootstrap leaves all helper *code* intact while removing this noise. The
    scenario file itself is never stripped, so its real annotations still count.
    """
    out_lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("--"):
            out_lines.append("")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)

def _read_bootstrap_lua_for_preflight(scenario_content):
    if "scenario_bootstrap" not in scenario_content:
        return ""
    repo_m = re.search(r"CMO_SCENARIO_REPO\s*=\s*\[\[(.*?)\]\]", scenario_content, re.IGNORECASE)
    if repo_m:
        boot = Path(repo_m.group(1).strip()) / "scripts" / "scenario_bootstrap.lua"
        if boot.is_file():
            return _strip_lua_comment_lines(boot.read_text(encoding="utf-8", errors="ignore"))
    default_boot = Path(__file__).resolve().parent / "scenario_bootstrap.lua"
    if default_boot.is_file():
        return _strip_lua_comment_lines(default_boot.read_text(encoding="utf-8", errors="ignore"))
    return ""

def _pick_series_version(db, table, unit_id, series=None, version=None):
    query = f"SELECT 1 FROM {table} WHERE ID = ?"
    params = [unit_id]
    query, params = db.append_meta_filters(query, params)
    query += " LIMIT 1"
    db.cursor.execute(query, params)
    if not db.cursor.fetchone():
        return None
    return (series or db.series, version or db.version)

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

def _zone_centroid(point_names, point_map):
    coords = [point_map[name] for name in point_names if name in point_map]
    if not coords:
        return None
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return lat, lon

def _csg_anchor_point(content, ships, consts):
    """Best CSG centre for patrol-zone proximity checks."""
    if "csg_lat" in consts and "csg_lon" in consts:
        return consts["csg_lat"], consts["csg_lon"], "csg_lat/csg_lon"
    for ship in ships:
        if ship.get("var") == "nimitz" and ship.get("lat") is not None:
            return ship["lat"], ship["lon"], "CVN (nimitz)"
    for ship in ships:
        name_u = (ship.get("name") or "").upper()
        if ship.get("lat") is None:
            continue
        if "CVN" in name_u or "CARRIER" in name_u:
            return ship["lat"], ship["lon"], ship.get("name") or ship.get("var")
    return None

def _is_csg_local_patrol_mission(mission_name):
    lower = mission_name.lower()
    if any(marker in lower for marker in _THEATER_PATROL_ZONE_EXEMPT):
        return False
    return any(marker in lower for marker in _CSG_LOCAL_MISSION_HINTS)

def _is_helo_patrol_mission(mission_name, mission_map):
    lower = mission_name.lower()
    if any(marker in lower for marker in _THEATER_PATROL_ZONE_EXEMPT):
        return False
    role = mission_map.get(mission_name, "")
    if role not in ("patrol", "support"):
        return False
    return "asw" in lower or "asu" in lower or "helo" in lower

def _ship_host_positions(ships):
    """place_ship var -> (lat, lon, label)."""
    hosts = {}
    for ship in ships:
        var = ship.get("var")
        if not var or ship.get("lat") is None:
            continue
        hosts[var] = (ship["lat"], ship["lon"], ship.get("name") or var)
    return hosts

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

def _bbox_for_zone(rp_names, ref_points, margin=0.02):
    lats = []
    lons = []
    for name in rp_names:
        if name not in ref_points:
            return None
        lat, lon = ref_points[name]
        lats.append(lat)
        lons.append(lon)
    if not lats:
        return None
    return (
        min(lats) - margin,
        max(lats) + margin,
        min(lons) - margin,
        max(lons) + margin,
    )

def _point_in_bbox(lat, lon, bbox):
    min_lat, max_lat, min_lon, max_lon = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

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

def _parse_carrier_vars_with_air_wing(content):
    carrier_vars = set(
        re.findall(r"(?:local\s+)?(\w+)\s*=\s*place_ship", content, flags=re.IGNORECASE)
    )
    operating = set()
    for var in carrier_vars:
        if re.search(rf"{var}\.guid", content):
            operating.add(var)
    return operating

def _ship_name_and_type(db, ship_id, series, version):
    query = "SELECT Name, Type FROM DataShip WHERE ID = ?"
    params = [ship_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    if not row:
        return None, None
    return row[0], row[1]

def _is_carrier_name(name_upper):
    if any(marker in name_upper for marker in _LHA_CARRIER_MARKERS):
        return "amphib"  # aviation ship, lighter escort expectation
    if any(marker in name_upper for marker in _CARRIER_NAME_MARKERS):
        return "cvn"
    if name_upper.startswith("CV") and "CVN" not in name_upper:
        return "cvn"
    return None

def _classify_ship(db, ship_id, series, version):
    name, ship_type = _ship_name_and_type(db, ship_id, series, version)
    if not name:
        return "unknown", None
    name_upper = name.upper()
    role = _is_carrier_name(name_upper)
    if role:
        return "carrier", role
    if any(marker in name_upper for marker in _ESCORT_NAME_MARKERS):
        return "escort", name
    if ship_type is not None and 3101 <= int(ship_type) <= 3108:
        return "escort", name
    return "other", name

def _approx_deg_distance(lat1, lon1, lat2, lon2):
    return math.hypot(lat2 - lat1, lon2 - lon1)

def _haversine_nm(lat1, lon1, lat2, lon2):
    """Great-circle distance in nautical miles."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3440.065 * 2 * math.asin(math.sqrt(min(1.0, a)))

def _flight_minutes_for_nm(distance_nm, speed_kts, overhead_min=0):
    if distance_nm <= 0 or speed_kts <= 0:
        return overhead_min
    return int(math.ceil(distance_nm / speed_kts * 60.0)) + overhead_min

def _parse_csg_group_constant(content):
    match = re.search(r"local\s+CSG_GROUP\s*=\s*'([^']+)'", content, re.IGNORECASE)
    return match.group(1) if match else None

def _parse_csg_group_members(content):
    """All ship vars in form_csg_group(NAME, lead, {members}) plus lead."""
    match = re.search(
        r"form_csg_group\s*\(\s*[^,]+,\s*(\w+)\s*,\s*\{([^}]*)\}\s*\)",
        content,
        re.IGNORECASE,
    )
    if not match:
        return set(), None
    lead = match.group(1)
    members = {lead}
    for var in re.findall(r"\b(\w+)\b", match.group(2)):
        members.add(var)
    return members, lead

def _parse_unit_group_assignments(content, group_name_literals=None):
    """place_ship var -> group name from ScenEdit_SetUnit / u.group."""
    literals = set(group_name_literals or [])
    csg_const = _parse_csg_group_constant(content)
    if csg_const:
        literals.add(csg_const)
    groups = {}
    for match in re.finditer(
        r"ScenEdit_SetUnit\s*\(\s*\{([^}]+)\}",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        block = match.group(1)
        guid_m = re.search(r"guid\s*=\s*(\w+)\.guid", block, re.IGNORECASE)
        group_m = re.search(r"group\s*=\s*([^,}]+)", block, re.IGNORECASE)
        if not guid_m or not group_m:
            continue
        raw = group_m.group(1).strip()
        if raw.startswith("'") and raw.endswith("'"):
            groups[guid_m.group(1)] = raw.strip("'")
        elif raw == "group_name" or raw == "CSG_GROUP":
            if csg_const:
                groups[guid_m.group(1)] = csg_const
    for match in re.finditer(r"(\w+)\.group\s*=\s*'([^']+)'", content, flags=re.IGNORECASE):
        groups[match.group(1)] = match.group(2)
    return groups

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
        spd = _parse_strike_package_date(content)
        if spd:
            out["strike_package_date"] = spd
    return out

def _max_distance_nm(origin, targets):
    if not targets:
        return None, None
    best_nm = -1.0
    best = None
    for t in targets:
        nm = _haversine_nm(origin[0], origin[1], t["lat"], t["lon"])
        if nm > best_nm:
            best_nm = nm
            best = t
    return best_nm, best

def _loadout_has_sead_role(db, loadout_id, series, version):
    loadout_query = "SELECT Name FROM DataLoadout WHERE ID = ?"
    loadout_params = [loadout_id]
    loadout_query, loadout_params = db.append_meta_filters(loadout_query, loadout_params)
    row = db.cursor.execute(loadout_query, loadout_params).fetchone()
    if not row:
        return False
    return "sead" in _loadout_roles(row[0])

def _infer_mission_role(mission_name, mission_map):
    if mission_name in mission_map:
        return mission_map[mission_name]
    upper = mission_name.upper()
    if "SEAD" in upper or "WILD WEASEL" in upper or "IRON HAND" in upper:
        return "sead"
    if "STRIKE" in upper:
        return "strike"
    if any(token in upper for token in ("AWACS", "AEW", "MAINSTAY", "ORBIT", "SUPPORT")):
        return "support"
    if any(token in upper for token in ("CAP", "ESCORT", "FIGHTER", "PATROL", "AAW")):
        return "aaw"
    return "unknown"

def _is_nuclear_weapon_name(weapon_name):
    if not weapon_name:
        return False
    upper = weapon_name.upper()
    if "NUCLEAR" in upper or "NUCL" in upper:
        return True
    if "TLAM-N" in upper or "TLAM N" in upper:
        return True
    if "AGM-86B" in upper:
        return True
    if "AGM-129" in upper and "ACM" in upper:
        return True
    if "BGM-109G" in upper and "GLCM" in upper:
        return True
    for marker in ("B61", "B83", "W80", "W87", "W78", "B28 ", "B57 "):
        if marker in upper:
            return True
    if "ALCM" in upper and "CALCM" not in upper and "CONVENTIONAL" not in upper:
        return True
    return False

def _is_nuclear_missile_store_for_ship(weapon_name):
    """Nuclear cruise/ballistic stores relevant to US CSG (not corrupt DB RV rows)."""
    upper = weapon_name.upper()
    return (
        "TOMAHAWK" in upper
        or "TLAM" in upper
        or "AGM-86B" in upper
        or ("AGM-129" in upper and "ACM" in upper)
        or ("BGM-109G" in upper and "GLCM" in upper)
    )

def _is_nuclear_loadout_name(loadout_name):
    if not loadout_name:
        return False
    upper = loadout_name.upper()
    for marker in _NUCLEAR_LOADOUT_NAME_MARKERS:
        if marker in upper:
            return True
    if "ALCM" in upper and "CALCM" not in upper and "CONVENTIONAL" not in upper:
        return True
    return False

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

def _loadout_name_tokens(loadout_name):
    """Meaningful tokens from loadout name for cross-checking linked weapons."""
    if not loadout_name:
        return set()
    tokens = set()
    for part in re.split(r"[^A-Za-z0-9/]+", loadout_name.upper()):
        if len(part) >= 3:
            tokens.add(part)
    return tokens

def _weapon_matches_loadout_context(weapon_name, loadout_name):
    """Ignore corrupt DB rows where the weapon name shares nothing with the loadout."""
    if not weapon_name or not loadout_name:
        return False
    w_upper = weapon_name.upper()
    tokens = _loadout_name_tokens(loadout_name)
    for token in tokens:
        if token in w_upper:
            return True
    # Common explicit pairings when tokenization is thin (e.g. "AARGM" vs "AGM-88E").
    loadout_upper = loadout_name.upper()
    if "TOMahawk".upper() in loadout_upper and "TOMAHAWK" in w_upper:
        return True
    if "CALCM" in loadout_upper and ("CALCM" in w_upper or "AGM-86C" in w_upper):
        return True
    if "ALCM" in loadout_upper and "ALCM" in w_upper:
        return True
    if "TLAM" in loadout_upper and "TLAM" in w_upper:
        return True
    return False

def _loadout_nuclear_weapon_hits(
    db, loadout_id, series, version, loadout_name, required_only=False
):
    """[(weapon_name, optional)] for nuclear weapons credibly linked to this loadout."""
    from db_nuclear import weapon_dbid_is_nuclear

    query = """
        SELECT w.ID, w.Name, dlw.Optional
        FROM DataLoadoutWeapons dlw
        LEFT JOIN DataWeapon w ON dlw.ComponentID = w.ID
        WHERE dlw.ID = ?
    """
    params = [loadout_id]
    query, params = db.append_meta_filters(query, params, "dlw")
    hits = []
    for row in db.cursor.execute(query, params).fetchall():
        wpn_id, name, optional = row[0], row[1], row[2]
        if required_only and optional:
            continue
        is_nuclear = wpn_id is not None and weapon_dbid_is_nuclear(
            db, wpn_id, series, version
        )
        if not is_nuclear and (not name or not _is_nuclear_weapon_name(name)):
            continue
        if not name or not _weapon_matches_loadout_context(name, loadout_name):
            continue
        hits.append((name, bool(optional)))
    return hits

def _loadout_roles(loadout_name):
    name = loadout_name.upper()
    roles = set()
    if any(token in name for token in ("AEW", "EARLY WARNING", "AWACS")):
        roles.add("support")
    if any(
        token in name
        for token in (
            "A/A:",
            "AIM-",
            " AA-",
            "SPARROW",
            "SIDEWINDER",
            "AMRAAM",
            "ARCHER",
            "ALAMO",
            "APEX",
            "APHID",
            "ATOLL",
            "R-27",
            "R-73",
            "R-24",
            "R-60",
        )
    ):
        roles.add("aaw")
    if any(
        token in name
        for token in (
            "HARM",
            "AGM-88",
            "AARGM",
            " ARM",
            "KH-58",
            "ALARM",
            "MARTEL",
            "WILD WEASEL",
            "WEASEL",
            "KH-25MP",
            "KEGLER",
            "KILTER",
            "KRYPTON P",
            "KH-31P",
            "SHRIKE",
            "ANTI-RADIATION",
        )
    ):
        roles.add("sead")
    if "ANTI-SHIP" in name or "KH-31A" in name:
        roles.add("ash")
    if any(
        token in name
        for token in (
            "FAB-",
            "GPB",
            "BOMB",
            "FRAG",
            "LGB",
            "JDAM",
            "KAB-",
            "OFAB",
            "MK82",
            "MK84",
            "CLUSTER",
            "ROCKETS",
            "KAREN [KH-25L]",
        )
    ):
        roles.add("strike")
    if "FERRY" in name:
        roles.add("ferry")
    if any(
        token in name
        for token in (
            "JDAM",
            "JSOW",
            "JASSM",
            "AGM-158",
            "AGM-154",
            "CALCM",
            "ALCM",
            "AGM-86",
            "GBU-",
            "Paveway",
            "LGB",
            "BROACH",
        )
    ):
        roles.add("precision_strike")
        roles.add("strike")
    if any(
        token in name
        for token in (
            "LDGP",
            " GPB",
            "UNGUIDED",
            "IRON BOMB",
            "GP BOMB",
            "FAB-",
            "OFAB",
            "MK82 LDGP",
        )
    ) or (
        "MK84" in name
        and "LDGP" in name
        and "JDAM" not in name
    ):
        roles.add("dumb_strike")
    if any(
        token in name
        for token in (
            "CALCM",
            "ALCM",
            "AGM-86",
            "AGM-158",
            "JASSM",
            "TOMAHAWK",
            "BGM-109",
            "CRUISE MISSILE",
        )
    ):
        roles.add("standoff")
        roles.add("strike")
    if "TANKER" in name or "BOOM" in name or "DROGUE" in name:
        roles.add("tanker")
    return roles or {"unknown"}

def _parse_scenario_year(content):
    match = re.search(r"scenario_year\s*=\s*(\d{4})", content, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _normalize_date_slash_key(date_str):
    """Canonical YYYY/MM/DD from slash, dot, compact, or CMO SetTime YYYYMMDD."""
    if not date_str:
        return None
    s = str(date_str).strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}/{s[4:6]}/{s[6:8]}"
    s = s.replace(".", "/").replace("-", "/")
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        return f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"
    return None


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

def _unit_service_record(db, table, unit_id, series, version):
    """Name, YearCommissioned, YearDecommissioned from DataAircraft, DataShip, or DataSubmarine."""
    if table not in ("DataAircraft", "DataShip", "DataSubmarine"):
        return None, None, None, ""
    query = f"SELECT Name, YearCommissioned, YearDecommissioned FROM {table} WHERE ID = ?"
    params = [unit_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    if not row:
        return None, None, None, ""
    name = row[0] or ""
    commissioned = int(row[1]) if row[1] not in (None, 0, "") else None
    decommissioned = int(row[2]) if row[2] not in (None, 0, "") else None
    return name, commissioned, decommissioned, name

def _unit_operator_description(db, table, unit_id, series, version):
    if table not in (
        "DataAircraft",
        "DataShip",
        "DataSubmarine",
        "DataFacility",
        "DataGroundUnit",
    ):
        return None, ""
    query = f"SELECT OperatorCountry FROM {table} WHERE ID = ?"
    params = [unit_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    if not row or row[0] in (None, ""):
        return None, ""
    op_id = int(row[0])
    op_query = "SELECT Description FROM EnumOperatorCountry WHERE ID = ?"
    op_row = db.cursor.execute(op_query, [op_id]).fetchone()
    return op_id, (op_row[0] if op_row else "")


def _is_placeholder_operator(op_desc):
    """True for CMO Junkyard / Generic DB placeholders (last-resort operators only)."""
    op_l = (op_desc or "").strip().lower()
    return op_l in ("junkyard", "generic") or "junkyard" in op_l


def _unit_db_name(db, table, unit_id, series, version):
    query = f"SELECT Name FROM {table} WHERE ID = ?"
    params = [unit_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    return (row[0] or "").strip() if row else ""


def _national_operator_alternatives(db, table, unit_id, series, version, limit=5):
    """
    Other DB entries with the same unit Name but a real (non-placeholder) operator.
    Used to warn when Junkyard/Generic was chosen while national variants exist.
    """
    if table not in ("DataAircraft", "DataShip", "DataSubmarine", "DataFacility", "DataGroundUnit"):
        return []
    name = _unit_db_name(db, table, unit_id, series, version)
    if not name:
        return []
    query = f"SELECT ID, OperatorCountry FROM {table} WHERE Name = ? AND ID != ?"
    params = [name, unit_id]
    query, params = db.append_meta_filters(query, params)
    rows = db.cursor.execute(query, params).fetchall()
    alts = []
    for alt_id, op_id in rows:
        if op_id in (None, ""):
            continue
        _oid, op_desc = _unit_operator_description(db, table, int(alt_id), series, version)
        if not op_desc or _is_placeholder_operator(op_desc):
            continue
        short = op_desc.split("[")[0].strip()
        alts.append(f"ID {alt_id} ({short})")
        if len(alts) >= limit:
            break
    return alts


def _side_matches_operator_country(side, operator_desc):
    """True when scenario side plausibly matches DB OperatorCountry description."""
    if not operator_desc:
        return True
    side_l = (side or "").strip().lower()
    op_l = operator_desc.lower()
    if _is_placeholder_operator(operator_desc):
        return True
    if side_l == "cuba":
        return "cuba" in op_l
    if side_l in ("united states", "usa", "us"):
        return (
            "united states" in op_l
            or op_l.startswith("us ")
            or "u.s." in op_l
            or op_l == "usa"
        )
    if side_l in ("nato", "allies"):
        return "nato" in op_l or "united states" in op_l or "united kingdom" in op_l
    if side_l in ("warsaw pact", "soviet union", "ussr"):
        return "soviet" in op_l or "russia" in op_l
    return True

_NATIONALITY_ALIASES = {
    "usa": "united states",
    "us": "united states",
    "u.s.": "united states",
    "america": "united states",
    "uk": "united kingdom",
    "britain": "united kingdom",
    "great britain": "united kingdom",
    "holland": "netherlands",
    "dutch": "netherlands",
    "nl": "netherlands",
    "polish": "poland",
    "pl": "poland",
    "german": "germany",
    "frg": "germany",
    "deutschland": "germany",
    "russian": "russia",
    "rf": "russia",
    "ussr": "soviet union",
    "soviet": "soviet union",
    "french": "france",
    "italian": "italy",
    "norwegian": "norway",
    "belgian": "belgium",
    "danish": "denmark",
    "turkish": "turkey",
    "spanish": "spain",
    "canadian": "canada",
    "australian": "australia",
    "japanese": "japan",
    "czech": "czech republic",
}


def _normalize_nationality(text):
    """Lowercase, drop bracketed/parenthetical qualifiers, resolve common aliases."""
    if not text:
        return ""
    t = re.sub(r"[\[(].*?[\])]", "", text)  # strip "[1992-]", "[FRG/Reunified]", "(...)"
    t = t.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return _NATIONALITY_ALIASES.get(t, t)


def _operator_desc_matches_nationality(declared, operator_desc):
    """True when a declared nationality plausibly matches a DB OperatorCountry description."""
    decl = _normalize_nationality(declared)
    op = _normalize_nationality(operator_desc)
    if not decl or not op:
        return False
    if decl == op:
        return True
    # Junkyard/Generic do not prove the declared nationality — last resort only.
    if _is_placeholder_operator(operator_desc):
        return False
    # NATO operator (e.g. E-3A Component) matches @nationality NATO only.
    if op == "nato" or "nato" in op:
        return decl == "nato"
    # Substring either direction (e.g. "korea" vs "south korea").
    return decl in op or op in decl


def _loadout_name_upper(db, loadout_id, series, version):
    query = "SELECT Name FROM DataLoadout WHERE ID = ?"
    params = [loadout_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    return (row[0] or "").upper() if row else ""

def _f35_variant(name_upper):
    if "F-35B" in name_upper:
        return "B"
    if "F-35C" in name_upper:
        return "C"
    if "F-35A" in name_upper:
        return "A"
    return None

def _is_tanker_airframe(name_upper):
    return any(
        marker in name_upper
        for marker in ("KC-46", "KC-135", "KC-10", "KC-767", "KC-30", "KC-707", "TANKER")
    )

def _parse_spawn_carrier_assignments(content):
    """(side, aircraft_id, loadout_id, mission_name, carrier_var) per spawn on carrier.guid."""
    carrier_vars = set(
        re.findall(r"(?:local\s+)?(\w+)\s*=\s*place_ship", content, flags=re.IGNORECASE)
    )
    rows = []
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'([^']+)'\s*,\s*(\w+)\.guid(?:\s*,\s*(?:true|false))?",
        re.IGNORECASE,
    )
    for match in wing_pattern.finditer(content):
        base_var = match.group(6)
        if base_var in carrier_vars:
            rows.append(
                (
                    match.group(1),
                    int(match.group(3)),
                    int(match.group(4)),
                    match.group(5),
                    base_var,
                )
            )
    helper_on_carrier = re.compile(
        r"add_air_unit_checked\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*[^,]+,\s*(\d+|nil)\s*,\s*'([^']*)'\s*,\s*(\w+)\.guid",
        re.IGNORECASE,
    )
    for match in helper_on_carrier.finditer(content):
        if match.group(3).lower() == "nil":
            continue
        base_var = match.group(5)
        if base_var in carrier_vars:
            rows.append(
                (
                    match.group(1),
                    int(match.group(2)),
                    int(match.group(3)),
                    match.group(4),
                    base_var,
                )
            )
    return rows

def _parse_lua_base_facility_dbid(content):
    match = re.search(r"BASE_FACILITY_DBID\s*=\s*(\d+)", content, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None

def _parse_place_base_hosts(content):
    """Map host ref (var or table.field) -> {kind, dbid, name, side}."""
    default_dbid = _parse_lua_base_facility_dbid(content)
    hosts = {}
    if default_dbid is None:
        return hosts

    direct_pattern = re.compile(
        r"(?:local\s+)?(\w+)\s*=\s*place_base\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,",
        re.IGNORECASE,
    )
    for match in direct_pattern.finditer(content):
        hosts[match.group(1)] = {
            "kind": "facility",
            "dbid": default_dbid,
            "name": match.group(3),
            "side": match.group(2),
        }

    table_pattern = re.compile(
        r"(\w+)\s*=\s*\{([^}]*place_base[^}]*)\}",
        re.IGNORECASE | re.DOTALL,
    )
    field_pattern = re.compile(
        r"(\w+)\s*=\s*place_base\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,",
        re.IGNORECASE,
    )
    for table_match in table_pattern.finditer(content):
        table_var = table_match.group(1)
        for field_match in field_pattern.finditer(table_match.group(2)):
            ref = f"{table_var}.{field_match.group(1)}"
            hosts[ref] = {
                "kind": "facility",
                "dbid": default_dbid,
                "name": field_match.group(3),
                "side": field_match.group(2),
            }
    return hosts

def _parse_air_host_map(content, ships):
    """All known air hosts: place_ship vars + place_base refs."""
    hosts = {}
    for ship in ships:
        if ship.get("var"):
            hosts[ship["var"]] = {
                "kind": "ship",
                "dbid": ship["dbid"],
                "name": ship.get("name"),
                "side": ship.get("side"),
            }
    hosts.update(_parse_place_base_hosts(content))
    return hosts

def _parse_air_spawns_on_hosts(content, host_refs):
    """Spawn rows with base_ref = var.guid or table.field.guid."""
    if not host_refs:
        return []
    rows = []
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'([^']+)'\s*,\s*((?:\w+\.)?\w+)\.guid(?:\s*,\s*(?:true|false))?",
        re.IGNORECASE,
    )
    for match in wing_pattern.finditer(content):
        base_ref = match.group(6)
        if base_ref not in host_refs:
            continue
        rows.append(
            {
                "base_ref": base_ref,
                "count": int(match.group(2)),
                "aircraft_id": int(match.group(3)),
                "loadout_id": int(match.group(4)),
                "mission": match.group(5),
            }
        )
    helper_pattern = re.compile(
        r"add_air_unit_checked\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*[^,]+,\s*(\d+|nil)\s*,\s*'([^']*)'\s*,\s*((?:\w+\.)?\w+)\.guid",
        re.IGNORECASE,
    )
    for match in helper_pattern.finditer(content):
        if match.group(3).lower() == "nil":
            continue
        base_ref = match.group(5)
        if base_ref not in host_refs:
            continue
        rows.append(
            {
                "base_ref": base_ref,
                "count": 1,
                "aircraft_id": int(match.group(2)),
                "loadout_id": int(match.group(3)),
                "mission": match.group(4),
            }
        )
    return rows

def _parse_ipairs_loop_base_spawns(content, host_refs):
    """
    for _, key in ipairs({'a','b'}) do local base = table[key] ... spawn(..., base.guid)
    Attributes wing spawns inside the loop to each table.key host ref.
    """
    extra = []
    loop_pattern = re.compile(
        r"for\s+_,\s*(\w+)\s+in\s+ipairs\s*\(\s*\{([^}]+)\}\s*\)\s+do(.*?)end",
        re.IGNORECASE | re.DOTALL,
    )
    wing_in_loop = re.compile(
        r"spawn_air_wing\s*\(\s*'[^']*'\s*,\s*[^,]+,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'([^']+)'\s*,\s*base\.guid",
        re.IGNORECASE,
    )
    for loop_match in loop_pattern.finditer(content):
        keys = re.findall(r"'(\w+)'", loop_match.group(2))
        body = loop_match.group(3)
        if not re.search(
            rf"local\s+base\s*=\s*(\w+)\[\s*{re.escape(loop_match.group(1))}\s*\]",
            body,
            re.IGNORECASE,
        ):
            continue
        table_match = re.search(
            rf"local\s+base\s*=\s*(\w+)\[\s*{re.escape(loop_match.group(1))}\s*\]",
            body,
            re.IGNORECASE,
        )
        if not table_match:
            continue
        table_var = table_match.group(1)
        for wing_match in wing_in_loop.finditer(body):
            count = int(wing_match.group(1))
            aircraft_id = int(wing_match.group(2))
            mission = wing_match.group(4)
            for key in keys:
                base_ref = f"{table_var}.{key}"
                if base_ref in host_refs:
                    extra.append(
                        {
                            "base_ref": base_ref,
                            "count": count,
                            "aircraft_id": aircraft_id,
                            "loadout_id": int(wing_match.group(3)),
                            "mission": mission,
                        }
                    )
    return extra

def _aircraft_host_profile(db, aircraft_id, series, version):
    query = "SELECT Category, PhysicalSizeCode FROM DataAircraft WHERE ID = ?"
    params = [aircraft_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    if not row:
        return None, None
    return int(row[0]), int(row[1])

def _sum_host_facility_capacity(
    db, component_table, host_id, aircraft_ids, series, version, *, berth_only=False
):
    profiles = []
    for aircraft_id in aircraft_ids:
        profile = _aircraft_host_profile(db, aircraft_id, series, version)
        if profile[0] is None:
            return "missing_aircraft"
        profiles.append(profile)

    max_phys = max(phys for _cat, phys in profiles)
    has_helo = any(cat == _AIRCRAFT_CATEGORY_HELICOPTER for cat, _phys in profiles)

    comp_query = f"SELECT ComponentID FROM {component_table} WHERE ID = ?"
    comp_params = [host_id]
    comp_query, comp_params = db.append_meta_filters(comp_query, comp_params)
    component_rows = db.cursor.execute(comp_query, comp_params).fetchall()
    if not component_rows:
        return 0

    berth_total = 0
    has_runway = False
    for (component_id,) in component_rows:
        fac_query = "SELECT Type, PhysicalSize, Capacity FROM DataAircraftFacility WHERE ID = ?"
        fac_params = [component_id]
        fac_query, fac_params = db.append_meta_filters(fac_query, fac_params)
        fac = db.cursor.execute(fac_query, fac_params).fetchone()
        if not fac:
            continue
        fac_type, fac_phys, capacity = int(fac[0]), int(fac[1]), int(fac[2])
        if fac_phys < max_phys:
            continue
        if fac_type in _RUNWAY_HOST_FACILITY_TYPES:
            has_runway = True
            if berth_only:
                continue
        if has_helo and fac_type not in _HELO_HOST_FACILITY_TYPES:
            continue
        if berth_only and fac_type not in _BERTH_HOST_FACILITY_TYPES:
            continue
        berth_total += capacity

    if berth_only and berth_total == 0 and has_runway:
        return _HOST_CAPACITY_RUNWAY_UNLIMITED
    return berth_total

def _air_host_capacity(db, host, aircraft_ids, series, version):
    if host["kind"] == "ship":
        result = _sum_host_facility_capacity(
            db,
            "DataShipAircraftFacilities",
            host["dbid"],
            aircraft_ids,
            series,
            version,
            berth_only=False,
        )
    else:
        result = _sum_host_facility_capacity(
            db,
            "DataFacilityAircraftFacilities",
            host["dbid"],
            aircraft_ids,
            series,
            version,
            berth_only=True,
        )
    if result == "missing_aircraft":
        return "missing_aircraft"
    return result

def _parse_lua_tables_with_place_calls(content, call_names):
    """table_name -> [field names] for fields that call place_* in a table literal."""
    tables = {}
    call_alt = "|".join(re.escape(c) for c in call_names)
    table_pattern = re.compile(
        rf"(\w+)\s*=\s*\{{([^}}]*(?:{call_alt})[^}}]*)\}}",
        re.IGNORECASE | re.DOTALL,
    )
    call_pat = "|".join(re.escape(c) for c in call_names)
    field_pattern = re.compile(rf"(\w+)\s*=\s*(?:{call_pat})\s*\(", re.IGNORECASE)
    for table_match in table_pattern.finditer(content):
        fields = []
        for field_match in field_pattern.finditer(table_match.group(2)):
            fields.append(field_match.group(1))
        if fields:
            tables[table_match.group(1)] = fields
    return tables

def _parse_direct_place_units(content, call_names):
    """ref -> {side, name, kind} for local var = place_*()."""
    units = {}
    for call_name in call_names:
        pattern = re.compile(
            rf"(?:local\s+)?(\w+)\s*=\s*{re.escape(call_name)}\s*\(\s*'([^']*)'\s*,\s*'([^']*)'",
            re.IGNORECASE,
        )
        for match in pattern.finditer(content):
            units[match.group(1)] = {
                "side": match.group(2),
                "name": match.group(3),
                "kind": call_name,
            }
    return units

def _parse_tables_assigned_via_pairs_loop(content):
    """Tables (or table.field refs) assigned via for _, u in pairs(...) do ... AssignUnitToMission(u.guid)."""
    assigned_tables = set()
    assigned_table_fields = set()
    assigned_inline_vars = set()
    table_loop = re.compile(
        r"for\s+_,\s*(\w+)\s+in\s+(?:pairs|ipairs)\s*\(\s*(\w+)\s*\)\s+do",
        re.IGNORECASE,
    )
    inline_loop = re.compile(
        r"for\s+_,\s*(\w+)\s+in\s+(?:pairs|ipairs)\s*\(\s*\{([^}]+)\}\s*\)\s+do",
        re.IGNORECASE,
    )
    assign_iter = re.compile(
        r"ScenEdit_AssignUnitToMission\s*\(\s*(\w+)\.guid",
        re.IGNORECASE,
    )

    def _body_assigns_iter(start_index, iter_var):
        snippet = content[start_index : start_index + 1500]
        return bool(
            re.search(
                rf"ScenEdit_AssignUnitToMission\s*\(\s*{re.escape(iter_var)}\.guid",
                snippet,
                re.IGNORECASE,
            )
        )

    for loop_match in table_loop.finditer(content):
        iter_var, table_name = loop_match.group(1), loop_match.group(2)
        if _body_assigns_iter(loop_match.end(), iter_var):
            assigned_tables.add(table_name)

    for loop_match in inline_loop.finditer(content):
        iter_var = loop_match.group(1)
        if not _body_assigns_iter(loop_match.end(), iter_var):
            continue
        inline_body = loop_match.group(2)
        for table_name, field_name in re.findall(r"(\w+)\.(\w+)", inline_body):
            assigned_table_fields.add(f"{table_name}.{field_name}")
        for bare_var in re.findall(r"\b([A-Za-z_]\w*)\b", inline_body):
            if bare_var in ("true", "false", "nil"):
                continue
            assigned_inline_vars.add(bare_var)

    return assigned_tables, assigned_table_fields, assigned_inline_vars

def _parse_direct_mission_assigned_refs(content):
    refs = set()
    for match in re.finditer(
        r"ScenEdit_AssignUnitToMission\s*\(\s*(\w+)\.guid",
        content,
        flags=re.IGNORECASE,
    ):
        refs.add(match.group(1))
    if re.search(_CSG_TLAM_SHIP_ASSIGN_CALL, content, re.IGNORECASE):
        members, _lead = _parse_csg_group_members(content)
        for var in members:
            refs.add(var)
    return refs

def _parse_air_spawn_wing_specs(content):
    """Each spawn_air_wing row: side, count, aircraft_id, loadout_id, mission, escort."""
    specs = []
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'([^']+)'\s*,\s*[^,]+(?:\s*,\s*(true|false))?\s*\)",
        re.IGNORECASE,
    )
    for match in wing_pattern.finditer(content):
        specs.append(
            {
                "side": match.group(1),
                "count": int(match.group(2)),
                "aircraft_id": int(match.group(3)),
                "loadout_id": int(match.group(4)),
                "mission": match.group(5),
                "escort": _parse_lua_bool(match.group(6)) if match.group(6) else False,
            }
        )
    return specs

def _parse_ship_strike_assignments(content, mission_map):
    """(ship_var, mission_name) where mission is a Strike."""
    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    rows = []
    for match in re.finditer(
        r"ScenEdit_AssignUnitToMission\s*\(\s*(\w+)\.guid\s*,\s*'([^']+)'(?:\s*,\s*(true|false))?\s*\)",
        content,
        flags=re.IGNORECASE,
    ):
        mission = match.group(2)
        if mission in strike_missions or _infer_mission_role(mission, mission_map) == "strike":
            if match.group(3) and _parse_lua_bool(match.group(3)):
                continue
            rows.append((match.group(1), mission))
    lua_vars = _parse_lua_string_vars(content)
    for match in re.finditer(
        r"assign_ship_to_mission\s*\(\s*[^,]+,\s*(\w+)\s*,\s*'([^']+)'\s*\)",
        content,
        flags=re.IGNORECASE,
    ):
        mission = match.group(2)
        if mission in strike_missions or _infer_mission_role(mission, mission_map) == "strike":
            rows.append((match.group(1), mission))
    tlam_m = re.search(
        r"local\s+TLAM_STRIKE_MISSION\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    air_m = re.search(
        r"local\s+STRIKE_AIR_MISSION\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    tlam_name = (
        tlam_m.group(1)
        if tlam_m
        else (air_m.group(1) if air_m else "Caribbean TLAM Salvo")
    )
    scenario_only = content.split("-- [preflight: scenario_bootstrap.lua]")[0]
    csg_strike_inline = re.search(
        r"setup_csg_strike_on_air_strike\s*\(\s*\w+\s*,\s*\{([^}]+)\}\s*\)",
        scenario_only,
        re.IGNORECASE | re.DOTALL,
    )
    csg_strike_vars = []
    if csg_strike_inline:
        csg_strike_vars = re.findall(r"\b(\w+)\b", csg_strike_inline.group(1))
    elif re.search(
        r"setup_csg_strike_on_air_strike\s*\(\s*\w+\s*,\s*(\w+)\s*\)",
        scenario_only,
        re.IGNORECASE,
    ):
        list_m = re.search(
            r"for\s+_\s*,\s*hull\s+in\s+ipairs\s*\(\s*\{([^}]+)\}\s*\)",
            scenario_only,
            re.IGNORECASE | re.DOTALL,
        )
        if list_m:
            csg_strike_vars = re.findall(r"\b(\w+)\b", list_m.group(1))
    if csg_strike_vars:
        air_name = air_m.group(1) if air_m else tlam_name
        for ship_var in csg_strike_vars:
            if ship_var.lower() in ("hull", "ship_unit", "cg_unit"):
                continue
            if re.search(rf"\blocal\s+{re.escape(ship_var)}\s*=", content, re.IGNORECASE):
                rows.append((ship_var, air_name))
    return rows

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
    )
    key_pattern = "|".join(known_keys)
    for match in re.finditer(rf"({key_pattern})=([^#]+?)(?=\s+(?:{key_pattern})=|$)", blob):
        kv[match.group(1)] = match.group(2).strip()
    if not kv:
        kv = dict(re.findall(r"([\w_]+)=([^\s#]+)", blob))
    return kv

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
        ("scenario_start_time", "cuba_mission_start_dt"),
    ):
        hhmm = expanded.get(time_key)
        if date and hhmm:
            expanded[dt_key] = f"{date} {hhmm}"
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
    """Map TLAM_STRIKE_MISSION-style locals to 'Caribbean TLAM Salvo'."""
    if not name:
        return name
    bare = name.strip().strip("'\"")
    return lua_vars.get(bare.lower(), bare)

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

def _strike_mission_loadout_profile(db, assignments, mission_name, series, version):
    """Dominant flight profile implied by striker loadouts on one strike mission."""
    counts = {"standoff": 0, "penetration": 0, "precision": 0, "unknown": 0}
    for _side, aircraft_id, loadout_id, mname, escort_flag in assignments:
        if escort_flag is True or aircraft_id == 0 or mname != mission_name:
            continue
        profile = _loadout_flight_profile(db, loadout_id, series, version)
        counts[profile] = counts.get(profile, 0) + 1
    if counts["standoff"] > 0 and counts["penetration"] == 0:
        return "standoff"
    if counts["penetration"] > 0 and counts["standoff"] == 0:
        return "penetration"
    if counts["standoff"] > 0 and counts["penetration"] > 0:
        return "mixed"
    if counts["precision"] > 0:
        return "precision"
    return "unknown"

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
    if not (date and isr_station_m):
        return {}
    if not re.search(
        r"set_patrol_on_station_schedule\s*\([^)]*Caribbean ISR Orbit",
        content,
        re.IGNORECASE,
    ):
        return {}
    station = isr_station_m.group(1)
    return {"Caribbean ISR Orbit": {"time_on_target": f"{date} {station}"}}

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
    mission = None
    m = re.search(r"local\s+TLAM_STRIKE_MISSION\s*=\s*'([^']+)'", content, re.IGNORECASE)
    if m:
        mission = m.group(1)
    if not mission:
        naval_pkgs = _parse_naval_package_annotations(content)
        if naval_pkgs:
            mission = naval_pkgs[0].get("mission")
    if not mission:
        mission = "Caribbean TLAM Salvo"
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
    """ScenEdit_SetMission for Caribbean TLAM Salvo-style blocks with tlam_launch_dt."""
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

def _time_to_minutes(hhmmss):
    parts = hhmmss.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return h * 60 + m + (1 if s >= 30 else 0)
    except ValueError:
        return None


def _minutes_to_hhmmss(total_minutes):
    """Clock time on same calendar day (wraps at 24h)."""
    if total_minutes is None:
        return None
    minutes = int(total_minutes) % (24 * 60)
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}:00"

def _normalize_date_key(date_str):
    """Normalize scenario dates to YYYYMMDD for comparison."""
    if not date_str:
        return None
    digits = re.sub(r"\D", "", str(date_str))
    if len(digits) != 8:
        return digits or None
    if int(digits[:4]) > 1900:
        return digits
    # MMDDYYYY (public CMO default)
    return digits[4:8] + digits[0:4]

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

def _strike_air_counts_by_mission(content, mission_map):
    """Per strike mission: striker/escort counts from all spawn_air_wing rows."""
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

def _is_standoff_only_strike_loadout(db, loadout_id, series, version):
    loadout_u = _loadout_name_upper(db, loadout_id, series, version)
    roles = _loadout_roles(loadout_u)
    return "standoff" in roles and "dumb_strike" not in roles

def _mission_loadout_fit(mission_role, loadout_roles):
    if mission_role == "unknown" or "unknown" in loadout_roles:
        return True, None
    if mission_role == "support":
        if "support" in loadout_roles or "tanker" in loadout_roles:
            return True, None
        return False, "support mission requires AEW/early-warning or tanker loadout"
    if mission_role == "sead":
        if "ash" in loadout_roles and "sead" not in loadout_roles:
            return False, "SEAD mission cannot use anti-ship-only loadout"
        if "sead" in loadout_roles:
            return True, None
        return False, "SEAD mission requires ARM/SEAD loadout"
    if mission_role == "strike":
        if (
            "strike" in loadout_roles
            or "precision_strike" in loadout_roles
            or "standoff" in loadout_roles
        ):
            return True, None
        if "aaw" in loadout_roles and "strike" not in loadout_roles:
            return False, "strike mission requires strike loadout, not A/A-only"
        return False, "strike mission requires strike loadout"
    if mission_role == "aaw":
        if "ash" in loadout_roles and "aaw" not in loadout_roles and "sead" not in loadout_roles:
            return False, "CAP/escort mission cannot use anti-ship-only loadout"
        if "strike" in loadout_roles and "aaw" not in loadout_roles and "sead" not in loadout_roles:
            return False, "CAP/escort mission cannot use strike-only loadout"
        if "aaw" in loadout_roles or "sead" in loadout_roles:
            return True, None
        return False, "CAP/escort mission requires A/A or SEAD-capable loadout"
    return True, None

def _parse_lua_bool(value):
    return value and value.lower() == "true"

def _extract_air_assignments(content):
    """(side, aircraft_id, loadout_id, mission_name, strike_escort); strike_escort is True/False/None."""
    assignments = []
    helper_pattern = re.compile(
        r"add_air_unit_checked\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*[^,]+,\s*(\d+|nil)\s*,\s*(?:'([^']*)'|nil)(?:\s*,\s*(true|false))?\s*\)",
        re.IGNORECASE,
    )
    wing_pattern = re.compile(
        r"spawn_air_wing\s*\(\s*'([^']*)'\s*,\s*[^,]+,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'([^']+)'\s*,\s*[^,]+(?:\s*,\s*(true|false))?\s*\)",
        re.IGNORECASE,
    )
    assign_pattern = re.compile(
        r"ScenEdit_AssignUnitToMission\s*\(\s*[^,]+,\s*'([^']+)'\s*(?:,\s*(true|false))?\s*\)",
        re.IGNORECASE,
    )

    for match in helper_pattern.finditer(content):
        if match.group(3).lower() == "nil":
            continue
        side = match.group(1) or ""
        mission_name = match.group(4) or ""
        escort_flag = _parse_lua_bool(match.group(5)) if match.group(5) else None
        assignments.append((side, int(match.group(2)), int(match.group(3)), mission_name, escort_flag))

    for match in wing_pattern.finditer(content):
        side = match.group(1) or ""
        wing_count = int(match.group(2))
        aircraft_id = int(match.group(3))
        loadout_id = int(match.group(4))
        mission_name = match.group(5)
        escort_flag = _parse_lua_bool(match.group(6)) if match.group(6) else None
        for _ in range(wing_count):
            assignments.append((side, aircraft_id, loadout_id, mission_name, escort_flag))

    for match in assign_pattern.finditer(content):
        mission_name = match.group(1)
        escort_flag = _parse_lua_bool(match.group(2)) if match.group(2) else None
        assignments.append(("", 0, 0, mission_name, escort_flag))

    return assignments

def _aircraft_name_upper(db, aircraft_id, series, version):
    query = "SELECT Name FROM DataAircraft WHERE ID = ?"
    params = [aircraft_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    return (row[0] or "").upper() if row else ""

def _is_stealth_bomber_name(name_upper):
    return any(marker in name_upper for marker in _STEALTH_BOMBER_NAME_MARKERS)

def _is_non_stealth_bomber_airframe(name_upper):
    if not name_upper or _is_stealth_bomber_name(name_upper):
        return False
    return any(marker in name_upper for marker in _NON_STEALTH_BOMBER_NAME_MARKERS)

def _is_aircraft_loadout_compatible(db, aircraft_id, loadout_id, series=None, version=None):
    query = """
        SELECT 1
        FROM DataAircraftLoadouts
        WHERE ID = ? AND ComponentID = ?
    """
    params = [aircraft_id, loadout_id]
    query, params = db.append_meta_filters(query, params)
    query += " LIMIT 1"
    db.cursor.execute(query, params)
    return db.cursor.fetchone() is not None


def _loadout_flight_profile(db, loadout_id, series, version):
    roles = _loadout_roles(_loadout_name_upper(db, loadout_id, series, version))
    if "standoff" in roles:
        return "standoff"
    if "dumb_strike" in roles and "precision_strike" not in roles and "standoff" not in roles:
        return "penetration"
    if "precision_strike" in roles:
        return "precision"
    return "unknown"


def _is_strike_escort_patrol_name(mission_name, mission_map):
    """Separate patrol used as strike-package escort instead of Strike escort slot (escort=true)."""
    if not mission_name or mission_map.get(mission_name) == "strike":
        return False
    upper = mission_name.upper()
    if "ESCORT" not in upper:
        return False
    if "SEAD" in upper or "WILD WEASEL" in upper or "HAMMER ESCORT" in upper:
        return False
    if "STRIKE" in upper and "ESCORT" in upper:
        return True
    if "THUNDER ESCORT" in upper:
        return True
    return False


def _side_has_aaw_escort_with_aa_loadout(db, side, assignments, mission_map, series, version):
    """AAW escort via Strike escort slot (escort=true) and/or SEAD/CAP patrol with A/A loadout."""
    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    for s2, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if s2 != side or not mission_name or aircraft_id == 0:
            continue
        loadout_query = "SELECT Name FROM DataLoadout WHERE ID = ?"
        loadout_params = [loadout_id]
        loadout_query, loadout_params = db.append_meta_filters(loadout_query, loadout_params)
        loadout_row = db.cursor.execute(loadout_query, loadout_params).fetchone()
        if not loadout_row:
            continue
        if "aaw" not in _loadout_roles(loadout_row[0]) and "sead" not in _loadout_roles(loadout_row[0]):
            continue
        if mission_name in strike_missions and escort_flag is True:
            return True
        if _infer_mission_role(mission_name, mission_map) == "aaw":
            return True
    return False


def _scenario_lua_body(content):
    """Scenario script only (exclude appended bootstrap for static side analysis)."""
    marker = "-- [preflight: scenario_bootstrap.lua]"
    if marker in content:
        return content.split(marker, 1)[0]
    return content


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


def _line_number_at(content, index):
    return content[:index].count("\n") + 1


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


__all__ = sorted(name for name in globals() if not name.startswith("__"))
