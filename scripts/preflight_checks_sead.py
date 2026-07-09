"""SEAD mission design and ISR-before-SEAD validators."""

import math
import re

from db_unit_queries import get_unit_weapons
from preflight_constants import *
from preflight_parse import *  # noqa: F403

def _validate_sead_mission_design(content, mission_map, mission_zones, assignments, db, series, version):
    errors = []
    warnings = []
    ok = []

    sead_missions = {name for name, role in mission_map.items() if role == "sead"}
    ref_points = _parse_reference_points(content)
    all_sam_sites = _parse_sam_sites(content)
    hostile_postures = _parse_hostile_postures(content)
    sead_sides = _sides_with_sead_missions(mission_map, assignments)
    sam_sites = []
    for sead_side in sead_sides:
        sam_sites.extend(_enemy_sam_sites_for_sead_side(sead_side, all_sam_sites, hostile_postures))
    if sead_missions and not sam_sites and all_sam_sites:
        sam_sites = [(lat, lon) for _side, lat, lon in all_sam_sites]
    mission_wcs = _parse_mission_land_wcs_overrides(content)
    side_land_wcs = _parse_side_land_wcs(content)

    for name, role in mission_map.items():
        upper = name.upper()
        if "SEAD" not in upper and "WILD WEASEL" not in upper and "IRON HAND" not in upper:
            continue
        if "ESCORT" in upper and role == "aaw":
            continue
        if role == "strike":
            errors.append(
                f"SEAD mission type: '{name}' is declared as Strike; use Patrol with type='SEAD'."
            )
        elif role != "sead":
            errors.append(
                f"SEAD mission type: '{name}' must be ScenEdit_AddMission(..., 'Patrol', {{type='SEAD', zone={{...}}}})."
            )

    for name in sead_missions:
        if name not in mission_zones or not mission_zones[name]:
            warnings.append(
                f"SEAD zone: mission '{name}' has no parseable zone={{...}} reference points in Lua."
            )

    sead_bboxes = []
    for name in sead_missions:
        rp_names = mission_zones.get(name, [])
        bbox = _bbox_for_zone(rp_names, ref_points)
        if bbox:
            sead_bboxes.append((name, bbox))
        elif rp_names:
            warnings.append(
                f"SEAD zone: mission '{name}' references unknown RPs: "
                f"{', '.join(n for n in rp_names if n not in ref_points)}"
            )

    if sam_sites and sead_bboxes:
        uncovered = []
        for idx, (lat, lon) in enumerate(sam_sites, start=1):
            if not any(_point_in_bbox(lat, lon, bbox) for _n, bbox in sead_bboxes):
                uncovered.append((idx, lat, lon))
        zone_names = ", ".join(n for n, _ in sead_bboxes)
        if len(uncovered) == len(sam_sites):
            errors.append(
                f"SEAD zone coverage: all {len(sam_sites)} hostile SAM site(s) lie outside Patrol/SEAD "
                f"zone(s) ({zone_names})."
            )
        elif uncovered:
            sample = "; ".join(
                f"#{idx} {lat},{lon}" for idx, lat, lon in uncovered[:3]
            )
            if len(uncovered) > 3:
                sample += f"; +{len(uncovered) - 3} more"
            warnings.append(
                f"SEAD zone coverage: {len(uncovered)}/{len(sam_sites)} hostile SAM site(s) outside "
                f"Patrol/SEAD zone(s) ({zone_names}): {sample}."
            )
        else:
            ok.append(
                f"OK: All {len(sam_sites)} hostile SAM site(s) fall inside at least one SEAD patrol zone."
            )
    elif sam_sites and not sead_bboxes:
        warnings.append(
            "SEAD zone coverage: SAM sites present in Lua but no SEAD patrol zones could be validated."
        )

    shooters_by_side = {}
    aa_only_on_sead = []
    for side, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if aircraft_id == 0 or mission_name not in sead_missions or escort_flag is True:
            continue
        has_sead = _loadout_has_sead_role(db, loadout_id, series, version)
        loadout_query = "SELECT Name FROM DataLoadout WHERE ID = ?"
        loadout_params = [loadout_id]
        loadout_query, loadout_params = db.append_meta_filters(loadout_query, loadout_params)
        loadout_row = db.cursor.execute(loadout_query, loadout_params).fetchone()
        roles = _loadout_roles(loadout_row[0]) if loadout_row else set()
        if has_sead:
            shooters_by_side[side or "?"] = shooters_by_side.get(side or "?", 0) + 1
        elif "aaw" in roles and "sead" not in roles:
            aa_only_on_sead.append((aircraft_id, mission_name))

    for aircraft_id, mission_name in aa_only_on_sead:
        errors.append(
            f"SEAD shooter loadout: aircraft {aircraft_id} on Patrol/SEAD mission '{mission_name}' "
            "uses A/A-only loadout; assign ARM/SEAD loadouts to the SEAD mission and keep escort on a separate AAW patrol."
        )

    if sam_sites:
        min_shooters = max(2, math.ceil(len(sam_sites) / 2))
        total_shooters = sum(shooters_by_side.values())
        if total_shooters < min_shooters:
            errors.append(
                f"SEAD capacity: {total_shooters} ARM/SEAD shooter assignment(s) for {len(sam_sites)} "
                f"SAM site(s); need at least {min_shooters} (ceil(SAM/2), minimum 2)."
            )
        elif total_shooters < len(sam_sites):
            warnings.append(
                f"SEAD capacity: {total_shooters} shooter(s) for {len(sam_sites)} SAM site(s); "
                "prefer at least one SEAD flight per SAM belt or per site in dense IADS."
            )
        else:
            ok.append(
                f"OK: SEAD shooter count ({total_shooters}) meets or exceeds SAM site count ({len(sam_sites)})."
            )
    elif sead_missions and sum(shooters_by_side.values()) == 0:
        warnings.append(
            "SEAD capacity: Patrol/SEAD mission(s) exist but no ARM/SEAD loadout assignments were detected."
        )

    if side_land_wcs == 1 and sead_missions:
        for mission_name in sead_missions:
            if mission_wcs.get(mission_name) != 0:
                warnings.append(
                    f"SEAD ROE: side uses WCS TIGHT on land (weapon_control_status_land=1) but mission "
                    f"'{mission_name}' does not override with weapon_control_status_land=0 (FREE); "
                    "HARM launches against passive SAMs may be blocked."
                )
        for mission_name in sead_missions:
            if mission_wcs.get(mission_name) == 0:
                ok.append(f"OK: SEAD mission '{mission_name}' sets land WCS FREE for emitter engagements.")
                break

    if sead_missions and not errors:
        ok.append(f"OK: {len(sead_missions)} Patrol/SEAD mission(s) declared with correct mission class.")

    return errors, warnings, ok

def _validate_isr_before_sead(content):
    """MQ-4C on-station before SEAD on-station (TimeOnTargetStation preferred)."""
    errors = []
    warnings = []
    ok = []

    recon_m = re.search(r"local\s+isr_recon_min\s*=\s*(\d+)", content, re.IGNORECASE)
    sead_station_m = re.search(
        r"local\s+sead_on_station_time\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    if not (recon_m and sead_station_m):
        return errors, warnings, ok

    recon = int(recon_m.group(1))
    sead_station = sead_station_m.group(1)
    sead_min = _time_to_minutes(sead_station)
    if sead_min is None:
        return errors, warnings, ok

    isr_station_m = re.search(
        r"local\s+isr_on_station_time\s*=\s*'([^']+)'", content, re.IGNORECASE
    )
    if isr_station_m:
        isr_station = isr_station_m.group(1)
        isr_min = _time_to_minutes(isr_station)
    else:
        isr_min = sead_min - recon
        isr_station = f"{isr_min // 60:02d}:{isr_min % 60:02d}:00"

    if isr_min is None or isr_min + recon > sead_min:
        errors.append(
            f"ISR timing: ISR on-station {isr_station} + {recon} min recon exceeds "
            f"SEAD on-station {sead_station}."
        )
        return errors, warnings, ok

    if not re.search(
        r"local\s+isr_on_station_time\s*=\s*cmo\.hms_subtract_minutes\s*\(\s*sead_on_station_time\s*,\s*isr_recon_min\s*\)",
        content,
        re.IGNORECASE,
    ):
        warnings.append(
            "ISR timing: derive isr_on_station_time from sead_on_station_time minus isr_recon_min "
            "(cmo.hms_subtract_minutes)."
        )

    schedule = _parse_mission_schedule_settings(content)
    isr_missions = _parse_isr_mission_names(content)
    isr_primary = isr_missions[0] if isr_missions else None
    isr_label = isr_primary or "primary ISR mission"
    isr_sched = (schedule.get(isr_primary) or {}) if isr_primary else {}
    sead_shooters, sead_escorts = _parse_sead_mission_names(content)
    sead_check_missions = sead_shooters + sead_escorts + ["SEAD Escort CAP"]
    sead_sched_any = any(
        (schedule.get(m) or {}).get("time_on_target") for m in sead_check_missions
    )
    has_isr_schedule_call = bool(
        re.search(
            r"set_patrol_on_station_schedule\s*\([^)]*ISR_(?:WEST|EAST)_MISSION",
            content,
            re.IGNORECASE,
        )
        or (
            isr_primary
            and re.search(
                rf"set_patrol_on_station_schedule\s*\([^)]*{re.escape(isr_primary)}",
                content,
                re.IGNORECASE,
            )
        )
    )
    if isr_sched.get("time_on_target") or has_isr_schedule_call:
        ok.append(
            f"OK: ISR before SEAD — ISR on-station {isr_station} Z ({recon} min recon before SEAD on-station {sead_station})."
        )
    else:
        warnings.append(
            f"ISR timing: {isr_label} has no TimeOnTargetStation — drone may launch at H-hour."
        )

    if sead_sched_any or re.search(
        r"set_patrol_on_station_schedule\s*\([\s\S]*?sead_on_station_dt",
        content,
        re.IGNORECASE,
    ):
        ok.append(
            f"OK: SEAD on-station schedule — CreateMissionFlightPlan TIMEONTARGET {sead_station} (CMO backs off launch)."
        )
    else:
        warnings.append(
            "SEAD timing: prefer set_patrol_on_station_schedule / TimeOnTargetStation over starttime/TakeOffTime."
        )

    if not re.search(
        r"add_mission_schedule_restore_event\s*\([\s\S]*?SEAD on-station schedule restore",
        content,
        re.IGNORECASE,
    ):
        warnings.append(
            "ISR/SEAD timing: add_mission_schedule_restore_event (on_station) recommended at Play."
        )
    escort_per_zone_m = re.search(
        r"local\s+sead_escort_per_zone\s*=\s*(\d+)", content, re.IGNORECASE
    )
    growler_count = len(
        re.findall(
            r"spawn_air_wing\s*\([^)]*Growler SEAD",
            content,
            re.IGNORECASE,
        )
    )
    if escort_per_zone_m and growler_count >= 2:
        per_zone = int(escort_per_zone_m.group(1))
        if per_zone < 4:
            warnings.append(
                f"SEAD escort: sead_escort_per_zone={per_zone} is thin for 4 Growlers per box "
                "(prefer ≥4 escorts per SEAD theater)."
            )
        else:
            ok.append(
                f"OK: SEAD escort — {per_zone} Hornets per theater ({per_zone * 2} total) for "
                f"{growler_count * 4} Growlers."
            )

    sead_hold_mission = sead_shooters[0] if sead_shooters else None
    sead_hold = (
        re.search(
            rf"{re.escape(sead_hold_mission)}[\s\S]{{0,400}}?weapon_control_status_land\s*=\s*2",
            content,
            re.IGNORECASE,
        )
        if sead_hold_mission
        else None
    )
    if sead_hold:
        ok.append("OK: SEAD land WCS HOLD until on-station — no HARM fires before ISR recon window.")
    else:
        warnings.append(
            "ISR/SEAD timing: set weapon_control_status_land=2 (HOLD) on SEAD until on-station event sets FREE."
        )

    return errors, warnings, ok

__all__ = ['_validate_isr_before_sead', '_validate_sead_mission_design']
