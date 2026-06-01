#!/usr/bin/env python3
"""Split db_search.py into scenario_constants, scenario_lua, scenario_checks."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = SCRIPTS / "db_search.py"

PARSER_EXTRA = frozenset(
    {
        "_resolve_lua_coord",
        "_resolve_lua_datetime_token",
        "_expand_lua_datetime_vars",
        "_zone_centroid",
        "_csg_anchor_point",
        "_ship_host_positions",
        "_bbox_for_zone",
        "_point_in_bbox",
        "_enemy_sam_sites_for_sead_side",
        "_sides_with_sead_missions",
        "_is_csg_local_patrol_mission",
        "_is_helo_patrol_mission",
        "_approx_deg_distance",
        "_haversine_nm",
        "_flight_minutes_for_nm",
        "_max_distance_nm",
        "_time_to_minutes",
        "_normalize_date_key",
        "_infer_mission_role",
        "_strike_mission_loadout_profile",
        "_parse_lua_bool",
        "_parse_flight_size_value",
        "_parse_lua_mission_option_bool",
        "_parse_lua_mission_option_value",
        "_aircraft_count_on_strike_missions",
        "_carrier_air_counts_by_mission",
        "_sead_missions_needing_delayed_launch",
        "_aircraft_name_upper",
        "_is_aircraft_loadout_compatible",
        "_loadout_has_sead_role",
        "_loadout_roles",
        "_loadout_name_tokens",
        "_weapon_matches_loadout_context",
        "_loadout_nuclear_weapon_hits",
        "_loadout_name_upper",
        "_f35_variant",
        "_is_tanker_airframe",
        "_is_stealth_bomber_name",
        "_is_non_stealth_bomber_airframe",
        "_is_standoff_only_strike_loadout",
        "_is_nuclear_weapon_name",
        "_is_nuclear_missile_store_for_ship",
        "_is_nuclear_loadout_name",
        "_mission_loadout_fit",
        "_classify_ship",
        "_ship_name_and_type",
        "_is_carrier_name",
        "_unit_service_record",
        "_unit_operator_description",
        "_side_matches_operator_country",
        "_aircraft_host_profile",
        "_sum_host_facility_capacity",
        "_air_host_capacity",
        "_pick_series_version",
        "_extract_air_assignments",
    }
)

KEEP_IN_DB_SEARCH = frozenset(
    {
        "search_db",
        "get_loadouts",
        "get_unit_weapons",
        "validate_scenario_air_loadouts",
        "main",
        "_db_mode_args",
    }
)


def _is_constant_assign(node: ast.Assign) -> bool:
    if not node.targets:
        return False
    target = node.targets[0]
    if not isinstance(target, ast.Name):
        return False
    name = target.id
    return name.isupper() or (name.startswith("_") and not name.startswith("__"))


def main():
    text = SRC.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)

    def seg(node):
        return "".join(lines[node.lineno - 1 : node.end_lineno])

    constants: list[str] = []
    parsers: list[str] = []
    validators: list[str] = []
    keepers: list[str] = []
    imports: list[str] = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(seg(node))
            continue
        if isinstance(node, ast.Assign) and _is_constant_assign(node):
            constants.append(seg(node))
            continue
        if isinstance(node, ast.FunctionDef):
            name = node.name
            if name in KEEP_IN_DB_SEARCH:
                keepers.append(seg(node))
            elif name.startswith("_parse_") or name in PARSER_EXTRA:
                parsers.append(seg(node))
            elif name.startswith("_validate_"):
                validators.append(seg(node))
            else:
                keepers.append(seg(node))
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        keepers.append(seg(node))

    lua_header = '''"""Lua scenario parsing helpers for db_search preflight."""

import math
import re

from scenario_constants import *

'''
    checks_header = '''"""Scenario preflight validators (used by db_search.validate_scenario_air_loadouts)."""

import math
import re

from scenario_constants import *
from scenario_lua import *
from scenario_report import extend_report, run_check

'''
    const_header = '''"""Constants for scenario preflight checks."""

import re

'''
    db_header = '''"""Search CMO databases and run scenario preflight validation."""

import argparse
import math
import re
import sys
from pathlib import Path

from cmo_db import (
    DEFAULT_DB_DIR,
    database_layout_status,
    fts_match_query,
    master_has_fts,
    open_db,
    resolve_source_db,
)
from scenario_checks import *
from scenario_constants import *
from scenario_lua import *
from scenario_report import empty_report, extend_report, run_check

SEARCH_TABLES = [
    "DataAircraft",
    "DataShip",
    "DataSubmarine",
    "DataFacility",
    "DataWeapon",
    "DataGroundUnit",
]


'''
    (SCRIPTS / "scenario_constants.py").write_text(const_header + "\n".join(constants) + "\n", encoding="utf-8")
    (SCRIPTS / "scenario_lua.py").write_text(lua_header + "\n".join(parsers) + "\n", encoding="utf-8")
    (SCRIPTS / "scenario_checks.py").write_text(checks_header + "\n".join(validators) + "\n", encoding="utf-8")
    (SCRIPTS / "db_search.py").write_text(db_header + "\n".join(keepers) + "\n", encoding="utf-8")
    print(f"constants: {len(constants)} assigns")
    print(f"lua: {len(parsers)} functions")
    print(f"checks: {len(validators)} functions")
    print(f"db_search: {len(keepers)} functions kept")


if __name__ == "__main__":
    main()
