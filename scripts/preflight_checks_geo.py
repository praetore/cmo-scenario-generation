"""Geo placement, reference points, and civilian flight path validators."""

import math
import re

from db_unit_queries import get_unit_weapons
from preflight_constants import *
from preflight_parse import *  # noqa: F403

_CIV_SIDE_RE = re.compile(
    r"ScenEdit_AddSide\s*\(\s*\{[^}]*?side\s*=\s*'([^']*)'", re.IGNORECASE
)
_ADDUNIT_BLOCK_RE = re.compile(
    r"ScenEdit_AddUnit\s*\(\s*\{(.*?)\}\s*\)", re.IGNORECASE | re.DOTALL
)


def _validate_reference_points(content):
    """
    CMO requires side= on every ScenEdit_AddReferencePoint (RPs are per-side).
    Mission patrol zones must reference RPs created on the same side as the mission.
    """
    errors = []
    warnings = []
    ok = []

    rp_calls = _parse_reference_point_calls(content)
    if not rp_calls:
        return errors, warnings, ok

    added_sides, _referenced_sides = _parse_scenario_sides(content)
    missing_side = [r for r in rp_calls if not r["has_side"]]
    for row in missing_side:
        label = row["name"] or "(unnamed)"
        errors.append(
            f"Reference point: '{label}' at line {row['line']} has no side= in "
            "ScenEdit_AddReferencePoint — CMO reports Missing 'Side' "
            "(choose PlayerSide or a side from ScenEdit_AddSide)."
        )

    unresolved_side = [
        r for r in rp_calls if r["has_side"] and not r["side"]
    ]
    for row in unresolved_side:
        label = row["name"] or "(unnamed)"
        errors.append(
            f"Reference point: '{label}' at line {row['line']} has side= but the "
            "value is not a string literal or local SIDE_* alias — preflight cannot verify it."
        )

    for row in rp_calls:
        if not row["side"] or not row["has_side"]:
            continue
        if added_sides and row["side"] not in added_sides:
            label = row["name"] or "(unnamed)"
            errors.append(
                f"Reference point: '{label}' at line {row['line']} uses side='{row['side']}' "
                "but that side has no ScenEdit_AddSide — CMO cannot resolve the side."
            )
        elif added_sides and row["line"] < added_sides[row["side"]]:
            label = row["name"] or "(unnamed)"
            errors.append(
                f"Reference point: '{label}' at line {row['line']} is created before "
                f"ScenEdit_AddSide for '{row['side']}' at line {added_sides[row['side']]}."
            )

    rp_index = _reference_points_by_side_name(content)
    for side, mission, zone_names in _parse_mission_side_zones(content):
        for rp_name in zone_names:
            if (side, rp_name) not in rp_index:
                errors.append(
                    f"Reference point: mission '{mission}' on side '{side}' uses zone RP "
                    f"'{rp_name}' but no ScenEdit_AddReferencePoint declares "
                    f"{{ side='{side}', name='{rp_name}', ... }} — zones are per-side in CMO."
                )

    if not missing_side and not unresolved_side:
        declared = len([r for r in rp_calls if r["has_side"] and r["side"]])
        if declared:
            ok.append(
                f"OK: Reference points — {declared} AddReferencePoint call(s) declare side=."
            )
        zone_checks = _parse_mission_side_zones(content)
        if zone_checks and not any(
            e.startswith("Reference point: mission") for e in errors
        ):
            ok.append(
                f"OK: Reference points — mission zone RPs match side-tagged AddReferencePoint "
                f"({len(zone_checks)} zoned mission(s))."
            )

    return errors, warnings, ok

def _validate_civilian_flight_paths(content):
    """
    Civilian air traffic must have realistic flight paths (logic_checks §11): a plotted
    `course` that exits the area (transit, majority) or `base`+`rtb` to land (small minority).
    Civilian air added with only heading/speed loiters/circles aimlessly — flag it.
    """
    errors = []
    warnings = []
    ok = []

    civ_sides = {
        s for s in _CIV_SIDE_RE.findall(content) if "civ" in s.lower()
    }
    if not civ_sides:
        return errors, warnings, ok

    def block_is_civ_air(block):
        has_air = re.search(r"type\s*=\s*'Air'", block, re.IGNORECASE)
        if not has_air:
            return False
        return any(
            re.search(r"side\s*=\s*'" + re.escape(side) + r"'", block, re.IGNORECASE)
            for side in civ_sides
        )

    has_civ_air = any(
        block_is_civ_air(m.group(1)) for m in _ADDUNIT_BLOCK_RE.finditer(content)
    )
    uses_civilian_helper = re.search(
        r"\b(?:cmo\.)?add_civilian_airliner\s*\(", content
    ) is not None
    if not has_civ_air and not uses_civilian_helper:
        return errors, warnings, ok
    if not has_civ_air:
        has_civ_air = uses_civilian_helper

    if uses_civilian_helper:
        ok.append(
            "OK: Civilian flight paths — add_civilian_airliner sets theater exit course or RTB "
            "(logic_checks_cmo.md §11)."
        )
        return errors, warnings, ok

    has_course = re.search(r"\bcourse\s*=", content) is not None
    has_landing = re.search(r"\brtb\s*=\s*true\b", content, re.IGNORECASE) is not None

    if not has_course and not has_landing:
        warnings.append(
            "Civilian flight paths: civilian air traffic has no plotted 'course' and no "
            "'base'+'rtb' — aircraft fly straight, then loiter/circle aimlessly. Give transit "
            "flights a course (final waypoint outside the area) and land only a small portion "
            "(base+rtb to a same-side civilian airfield). See logic_checks_cmo.md §11."
        )
        return errors, warnings, ok

    ok.append(
        "OK: Civilian flight paths — plotted course and/or RTB landing present "
        "(no aimless-loiter antipattern)."
    )
    if has_landing and not has_course:
        warnings.append(
            "Civilian flight paths: RTB/landing present but no plotted transit 'course' — most "
            "civilian flights should be overflights that exit the area; only a small portion "
            "should land (logic_checks_cmo.md §11)."
        )
    return errors, warnings, ok

def _validate_unit_geo_placement(units):
    """Land vs water placement for every independently placed unit.

    - **Ship / sub** (`place_ship`, `place_sub`, AddUnit Ship/Sub): must be **water**
      (CMO: *cannot place ship over land*).
    - **Facility** (`place_base`, `place_sam`, AddUnit Facility): must be **land**
      (CMO: *Placement aborted — underwater*).

    Uses ``global_land_mask`` (~1 km). Preflight counterpart to ``World_GetElevation``
    guards in ``scenario_bootstrap.lua``.
    """
    errors = []
    warnings = []
    ok = []
    if not units:
        return errors, warnings, ok

    try:
        from global_land_mask import globe
    except ImportError:
        warnings.append(
            "Geo placement: global_land_mask not installed — land/water checks skipped. "
            "Run 'pip install global-land-mask' (see requirements.txt)."
        )
        return errors, warnings, ok

    naval_checked = 0
    land_checked = 0
    for unit in units:
        lat = unit.get("lat")
        lon = unit.get("lon")
        if lat is None or lon is None:
            continue
        kind = unit.get("kind") or "unknown"
        source = unit.get("source") or "spawn"
        label = unit.get("name") or f"DBID {unit.get('dbid')}"
        side = unit.get("side") or "?"
        line = unit.get("line")
        where = f"line {line} " if line else ""
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            warnings.append(
                f"Geo placement: {kind} '{label}' ({where}{source}, side {side}) has "
                f"out-of-range coordinates lat={lat}, lon={lon} — skipped."
            )
            continue
        try:
            is_land = bool(globe.is_land(lat, lon))
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(
                f"Geo placement: could not evaluate '{label}' (lat={lat}, lon={lon}): {exc}"
            )
            continue

        if kind in ("ship", "sub"):
            naval_checked += 1
            if is_land:
                noun = "submarine" if kind == "sub" else "ship"
                errors.append(
                    f"Geo placement: {noun} '{label}' ({where}{source}, side {side}) at "
                    f"lat={lat}, lon={lon} is on land — CMO rejects "
                    f"('cannot place ship over land'). Use open water."
                )
        elif kind == "facility":
            land_checked += 1
            if not is_land:
                errors.append(
                    f"Geo placement: facility '{label}' ({where}{source}, side {side}) at "
                    f"lat={lat}, lon={lon} is underwater per global_land_mask — CMO aborts "
                    f"facility placement ('This point appears to be underwater'). Nudge coords inland."
                )

    if naval_checked and not any("ship" in e or "submarine" in e for e in errors):
        ok.append(
            f"OK: Geo placement — {naval_checked} naval unit(s) over water (global_land_mask)."
        )
    if land_checked and not any("facility" in e for e in errors):
        ok.append(
            f"OK: Geo placement — {land_checked} facility/land unit(s) on land (global_land_mask)."
        )
    return errors, warnings, ok

def _validate_ship_sub_water_placement(ships):
    """Backward-compatible wrapper — prefer ``_parse_all_geo_placements`` + ``_validate_unit_geo_placement``."""
    return _validate_unit_geo_placement(ships)

__all__ = ['_validate_civilian_flight_paths', '_validate_reference_points', '_validate_ship_sub_water_placement', '_validate_unit_geo_placement']
