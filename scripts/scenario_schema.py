"""Schema and validation for declarative scenario specs (YAML)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_HHMMSS_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
_YYYYMMDD_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
_BRIEFING_COMPLEXITY = frozenset({"Low", "Med", "High"})


@dataclass
class MetaSpec:
    name: str
    year: int
    date: str
    input_lua: str
    output_lua: str


@dataclass
class TimingSpec:
    strike_tot_z: str
    tlam_launch_z: str
    sead_takeoff_z: str
    helo_takeoff_z: str
    aew_takeoff_z: str
    cap_takeoff_z: str
    isr_takeoff_z: str
    cap_restore_z: str
    sead_restore_z: str


@dataclass
class StrikeOptionsSpec:
    use_flight_size: bool
    flight_size: int
    min_ready_strike: int
    escort_use_flight_size: bool
    escort_flight_size: int
    min_ready_escort: int
    on_deactivate_unassign: bool


@dataclass
class BriefingSpec:
    title: str | None
    player_side: str
    complexity: str
    situation: str
    friendly_oob: str
    enemy_threat: str
    environment: str
    mission: str
    roe: str
    special_instructions: str
    show_popup: bool


@dataclass
class ScenarioSpec:
    meta: MetaSpec
    timing: TimingSpec
    strike_options: StrikeOptionsSpec
    briefing: BriefingSpec


def _require_keys(obj: dict[str, Any], keys: list[str], section: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ValueError(f"Missing keys in '{section}': {', '.join(missing)}")


def _validate_time(label: str, value: str) -> str:
    if not _HHMMSS_RE.match(value):
        raise ValueError(f"{label} must be HH:MM:SS, got '{value}'")
    return value


def load_scenario_spec(path: str | Path) -> ScenarioSpec:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Scenario spec root must be a mapping/object")
    _require_keys(raw, ["meta", "timing", "strike_options", "briefing"], "root")

    meta_raw = raw["meta"]
    _require_keys(meta_raw, ["name", "year", "date", "input_lua", "output_lua"], "meta")
    if not _YYYYMMDD_RE.match(str(meta_raw["date"])):
        raise ValueError("meta.date must be YYYY/MM/DD")

    timing_raw = raw["timing"]
    _require_keys(
        timing_raw,
        [
            "strike_tot_z",
            "tlam_launch_z",
            "sead_takeoff_z",
            "helo_takeoff_z",
            "aew_takeoff_z",
            "cap_takeoff_z",
            "isr_takeoff_z",
            "cap_restore_z",
            "sead_restore_z",
        ],
        "timing",
    )

    opts_raw = raw["strike_options"]
    _require_keys(
        opts_raw,
        [
            "use_flight_size",
            "flight_size",
            "min_ready_strike",
            "escort_use_flight_size",
            "escort_flight_size",
            "min_ready_escort",
            "on_deactivate_unassign",
        ],
        "strike_options",
    )

    meta = MetaSpec(
        name=str(meta_raw["name"]),
        year=int(meta_raw["year"]),
        date=str(meta_raw["date"]),
        input_lua=str(meta_raw["input_lua"]),
        output_lua=str(meta_raw["output_lua"]),
    )
    timing = TimingSpec(
        strike_tot_z=_validate_time("timing.strike_tot_z", str(timing_raw["strike_tot_z"])),
        tlam_launch_z=_validate_time("timing.tlam_launch_z", str(timing_raw["tlam_launch_z"])),
        sead_takeoff_z=_validate_time("timing.sead_takeoff_z", str(timing_raw["sead_takeoff_z"])),
        helo_takeoff_z=_validate_time("timing.helo_takeoff_z", str(timing_raw["helo_takeoff_z"])),
        aew_takeoff_z=_validate_time("timing.aew_takeoff_z", str(timing_raw["aew_takeoff_z"])),
        cap_takeoff_z=_validate_time("timing.cap_takeoff_z", str(timing_raw["cap_takeoff_z"])),
        isr_takeoff_z=_validate_time("timing.isr_takeoff_z", str(timing_raw["isr_takeoff_z"])),
        cap_restore_z=_validate_time("timing.cap_restore_z", str(timing_raw["cap_restore_z"])),
        sead_restore_z=_validate_time("timing.sead_restore_z", str(timing_raw["sead_restore_z"])),
    )
    strike_options = StrikeOptionsSpec(
        use_flight_size=bool(opts_raw["use_flight_size"]),
        flight_size=int(opts_raw["flight_size"]),
        min_ready_strike=int(opts_raw["min_ready_strike"]),
        escort_use_flight_size=bool(opts_raw["escort_use_flight_size"]),
        escort_flight_size=int(opts_raw["escort_flight_size"]),
        min_ready_escort=int(opts_raw["min_ready_escort"]),
        on_deactivate_unassign=bool(opts_raw["on_deactivate_unassign"]),
    )

    briefing_raw = raw["briefing"]
    _require_keys(
        briefing_raw,
        [
            "player_side",
            "complexity",
            "situation",
            "friendly_oob",
            "enemy_threat",
            "environment",
            "mission",
            "roe",
            "special_instructions",
        ],
        "briefing",
    )
    complexity = str(briefing_raw["complexity"])
    if complexity not in _BRIEFING_COMPLEXITY:
        raise ValueError(
            f"briefing.complexity must be one of {sorted(_BRIEFING_COMPLEXITY)}, got '{complexity}'"
        )
    title_raw = briefing_raw.get("title")
    briefing = BriefingSpec(
        title=str(title_raw).strip() if title_raw else None,
        player_side=str(briefing_raw["player_side"]),
        complexity=complexity,
        situation=str(briefing_raw["situation"]).strip(),
        friendly_oob=str(briefing_raw["friendly_oob"]).strip(),
        enemy_threat=str(briefing_raw["enemy_threat"]).strip(),
        environment=str(briefing_raw["environment"]).strip(),
        mission=str(briefing_raw["mission"]).strip(),
        roe=str(briefing_raw["roe"]).strip(),
        special_instructions=str(briefing_raw["special_instructions"]).strip(),
        show_popup=bool(briefing_raw.get("show_popup", True)),
    )
    return ScenarioSpec(meta=meta, timing=timing, strike_options=strike_options, briefing=briefing)
