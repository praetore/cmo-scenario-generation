"""Generate/update scenario Lua from a declarative YAML spec.

V1 scope:
- Uses an existing Lua file as base template.
- Rewrites key timing locals, strike options, and strike-package header annotation.
- Keeps full scenario body (OOB, missions, targets) intact.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from scenario_schema import ScenarioSpec, load_scenario_spec


def _replace_local_string(text: str, name: str, value: str) -> str:
    pattern = rf"(local\s+{re.escape(name)}\s*=\s*)'[^']*'"
    new_text, n = re.subn(pattern, rf"\1'{value}'", text)
    if n == 0:
        raise ValueError(f"Could not find local string variable '{name}'")
    return new_text


def _replace_local_number(text: str, name: str, value: int) -> str:
    pattern = rf"(local\s+{re.escape(name)}\s*=\s*)\d+"
    new_text, n = re.subn(pattern, rf"\g<1>{value}", text)
    if n == 0:
        raise ValueError(f"Could not find local number variable '{name}'")
    return new_text


def _replace_option(text: str, key: str, value: str) -> str:
    pattern = rf"({re.escape(key)}\s*=\s*)([^,\n]+)"
    new_text, n = re.subn(pattern, rf"\g<1>{value}", text)
    if n == 0:
        raise ValueError(f"Could not find mission option '{key}'")
    return new_text


def _to_lua_bool(flag: bool) -> str:
    return "true" if flag else "false"


def _rewrite_strike_package_annotation(text: str, spec: ScenarioSpec) -> str:
    line = (
        "-- @strike_package mission=Caribbean Thunder Strike "
        "profile=standoff "
        f"date={spec.meta.date} "
        f"time={spec.timing.strike_tot_z} "
        "max_spread=15 "
        f"flight_size={spec.strike_options.flight_size} "
        f"use_flight_size={_to_lua_bool(spec.strike_options.use_flight_size)} "
        f"min_aircraft={spec.strike_options.min_ready_strike} "
        f"escort_flight_size={spec.strike_options.escort_flight_size} "
        f"escort_use_flight_size={_to_lua_bool(spec.strike_options.escort_use_flight_size)}"
    )
    pattern = r"^-- @strike_package .*$"
    new_text, n = re.subn(pattern, line, text, flags=re.MULTILINE)
    if n == 0:
        raise ValueError("Could not find @strike_package annotation")
    return new_text


def render_from_spec(base_text: str, spec: ScenarioSpec) -> str:
    text = base_text
    text = _replace_local_number(text, "scenario_year", spec.meta.year)
    text = _replace_local_string(text, "strike_package_date", spec.meta.date)
    text = _replace_local_string(text, "strike_package_tot", spec.timing.strike_tot_z)
    text = _replace_local_string(text, "tlam_launch_time", spec.timing.tlam_launch_z)
    text = _replace_local_string(text, "sead_package_takeoff", spec.timing.sead_takeoff_z)
    text = _replace_local_string(text, "csg_helo_takeoff", spec.timing.helo_takeoff_z)
    text = _replace_local_string(text, "aew_launch_time", spec.timing.aew_takeoff_z)
    text = _replace_local_string(text, "cap_launch_time", spec.timing.cap_takeoff_z)
    text = _replace_local_string(text, "isr_launch_time", spec.timing.isr_takeoff_z)
    text = _replace_local_string(text, "cap_assign_restore_time", spec.timing.cap_restore_z)
    text = _replace_local_string(text, "sead_assign_restore_time", spec.timing.sead_restore_z)

    text = _replace_option(text, "StrikeUseFlightSize", _to_lua_bool(spec.strike_options.use_flight_size))
    text = _replace_option(text, "StrikeFlightSize", str(spec.strike_options.flight_size))
    text = _replace_option(text, "StrikeMinAircraftReq", str(spec.strike_options.min_ready_strike))
    text = _replace_option(text, "EscortUseFlightSize", _to_lua_bool(spec.strike_options.escort_use_flight_size))
    text = _replace_option(text, "EscortFlightSizeShooter", str(spec.strike_options.escort_flight_size))
    text = _replace_option(text, "EscortMinShooter", str(spec.strike_options.min_ready_escort))
    text = _replace_option(text, "OnDeactivateUassign", _to_lua_bool(spec.strike_options.on_deactivate_unassign))

    text = _rewrite_strike_package_annotation(text, spec)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate scenario Lua from YAML spec.")
    parser.add_argument("--spec", required=True, help="Path to scenario spec YAML")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    spec = load_scenario_spec((project_root / args.spec).resolve())
    in_path = (project_root / spec.meta.input_lua).resolve()
    out_path = (project_root / spec.meta.output_lua).resolve()

    base_text = in_path.read_text(encoding="utf-8")
    rendered = render_from_spec(base_text, spec)
    out_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
