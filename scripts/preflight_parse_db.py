"""CMO database lookup helpers for preflight parsing."""

import math
import re
from pathlib import Path

from preflight_constants import *

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


def _pick_series_version(db, table, unit_id, series=None, version=None):
    query = f"SELECT 1 FROM {table} WHERE ID = ?"
    params = [unit_id]
    query, params = db.append_meta_filters(query, params)
    query += " LIMIT 1"
    db.cursor.execute(query, params)
    if not db.cursor.fetchone():
        return None
    return (series or db.series, version or db.version)

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

def _aircraft_name_upper(db, aircraft_id, series, version):
    query = "SELECT Name FROM DataAircraft WHERE ID = ?"
    params = [aircraft_id]
    query, params = db.append_meta_filters(query, params)
    row = db.cursor.execute(query, params).fetchone()
    return (row[0] or "").upper() if row else ""

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

def _loadout_has_sead_role(db, loadout_id, series, version):
    loadout_query = "SELECT Name FROM DataLoadout WHERE ID = ?"
    loadout_params = [loadout_id]
    loadout_query, loadout_params = db.append_meta_filters(loadout_query, loadout_params)
    row = db.cursor.execute(loadout_query, loadout_params).fetchone()
    if not row:
        return False
    return "sead" in _loadout_roles(row[0])

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

def _loadout_flight_profile(db, loadout_id, series, version):
    roles = _loadout_roles(_loadout_name_upper(db, loadout_id, series, version))
    if "standoff" in roles:
        return "standoff"
    if "dumb_strike" in roles and "precision_strike" not in roles and "standoff" not in roles:
        return "penetration"
    if "precision_strike" in roles:
        return "precision"
    return "unknown"

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

def _is_stealth_bomber_name(name_upper):
    return any(marker in name_upper for marker in _STEALTH_BOMBER_NAME_MARKERS)

def _is_non_stealth_bomber_airframe(name_upper):
    if not name_upper or _is_stealth_bomber_name(name_upper):
        return False
    return any(marker in name_upper for marker in _NON_STEALTH_BOMBER_NAME_MARKERS)

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

__all__ = ['_air_host_capacity', '_aircraft_host_profile', '_aircraft_name_upper', '_classify_ship', '_f35_variant', '_infer_mission_role', '_is_aircraft_loadout_compatible', '_is_carrier_name', '_is_non_stealth_bomber_airframe', '_is_nuclear_loadout_name', '_is_nuclear_missile_store_for_ship', '_is_nuclear_weapon_name', '_is_placeholder_operator', '_is_standoff_only_strike_loadout', '_is_stealth_bomber_name', '_is_strike_escort_patrol_name', '_is_tanker_airframe', '_loadout_flight_profile', '_loadout_has_sead_role', '_loadout_name_tokens', '_loadout_name_upper', '_loadout_nuclear_weapon_hits', '_loadout_roles', '_mission_loadout_fit', '_national_operator_alternatives', '_normalize_nationality', '_operator_desc_matches_nationality', '_pick_series_version', '_ship_name_and_type', '_side_has_aaw_escort_with_aa_loadout', '_side_matches_operator_country', '_strike_mission_loadout_profile', '_sum_host_facility_capacity', '_unit_db_name', '_unit_operator_description', '_unit_service_record', '_weapon_matches_loadout_context']
