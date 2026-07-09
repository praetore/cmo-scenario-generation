"""Air wings, CSG groups, and unit assignment parsers."""

import math
import re
from pathlib import Path

from preflight_constants import *
from preflight_parse_lua import _parse_lua_base_facility_dbid, _parse_lua_bool, _parse_lua_string_vars
from preflight_parse_db import _infer_mission_role

def _parse_carrier_vars_with_air_wing(content):
    carrier_vars = set(
        re.findall(r"(?:local\s+)?(\w+)\s*=\s*place_ship", content, flags=re.IGNORECASE)
    )
    operating = set()
    for var in carrier_vars:
        if re.search(rf"{var}\.guid", content):
            operating.add(var)
    return operating

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
    from preflight_parse_missions import _resolve_tlam_strike_mission

    tlam_name = _resolve_tlam_strike_mission(content) or (
        air_m.group(1) if air_m else None
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

def _ship_host_positions(ships):
    """place_ship var -> (lat, lon, label)."""
    hosts = {}
    for ship in ships:
        var = ship.get("var")
        if not var or ship.get("lat") is None:
            continue
        hosts[var] = (ship["lat"], ship["lon"], ship.get("name") or var)
    return hosts

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

__all__ = ['_csg_anchor_point', '_extract_air_assignments', '_is_csg_local_patrol_mission', '_is_helo_patrol_mission', '_parse_air_host_map', '_parse_air_spawn_wing_specs', '_parse_air_spawns_on_hosts', '_parse_carrier_vars_with_air_wing', '_parse_csg_group_constant', '_parse_csg_group_members', '_parse_direct_mission_assigned_refs', '_parse_direct_place_units', '_parse_ipairs_loop_base_spawns', '_parse_lua_tables_with_place_calls', '_parse_place_base_hosts', '_parse_ship_strike_assignments', '_parse_spawn_carrier_assignments', '_parse_tables_assigned_via_pairs_loop', '_parse_unit_group_assignments', '_ship_host_positions']
