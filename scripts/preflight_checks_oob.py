"""OOB, operator country, nationality, era, and nuclear policy validators."""

import math
import re

from db_unit_queries import get_unit_weapons
from preflight_constants import *
from preflight_parse import *  # noqa: F403

# Helper call -> DB table for declared-nationality lookups.
_NATIONALITY_SPAWN_PATTERNS = (
    (
        "DataAircraft",
        re.compile(
            r"spawn_air_wing\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*\d+\s*,\s*(\d+)",
            re.IGNORECASE,
        ),
    ),
    (
        "DataAircraft",
        re.compile(
            r"add_air_unit_checked\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)",
            re.IGNORECASE,
        ),
    ),
    (
        "DataShip",
        re.compile(
            r"place_ship\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)", re.IGNORECASE
        ),
    ),
    (
        "DataSubmarine",
        re.compile(
            r"place_sub\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)", re.IGNORECASE
        ),
    ),
    (
        "DataFacility",
        re.compile(
            r"place_sam\s*\(\s*'[^']*'\s*,\s*'([^']*)'\s*,\s*(\d+)", re.IGNORECASE
        ),
    ),
)

_NATIONALITY_ANNOTATION_RE = re.compile(
    r"--\s*@nationality\s+([^\n]+?)\s*$", re.IGNORECASE
)
_EXPORT_PROXY_ANNOTATION_RE = re.compile(
    r"--\s*@export_proxy\s+([^\n]+?)\s*$", re.IGNORECASE
)
_OPERATOR_LAST_RESORT_RE = re.compile(
    r"--\s*@operator_last_resort\b", re.IGNORECASE
)


def _validate_no_nuclear_weapons(content, unique_pairs, ships, db, series, version):
    errors = []
    warnings = []
    ok = []

    if _parse_scenario_policy_nuclear(content):
        ok.append("OK: Nuclear policy — @scenario_policy nuclear=true (checks skipped).")
        return errors, warnings, ok

    sides_in_scenario = set(re.findall(r"ScenEdit_AddSide\s*\(\s*\{[^}]*side\s*=\s*'([^']+)'", content))
    nuc_doctrine = _parse_use_nuclear_weapons_doctrine(content)
    for side in sorted(sides_in_scenario):
        if side not in nuc_doctrine:
            warnings.append(
                f"Nuclear policy: side '{side}' has no use_nuclear_weapons='No' in ScenEdit_SetDoctrine — "
                "CMO may allow nuclear release by default."
            )
        elif nuc_doctrine[side] is not False:
            errors.append(
                f"Nuclear policy: side '{side}' must set use_nuclear_weapons='No' for conventional scenarios."
            )
    if sides_in_scenario and all(nuc_doctrine.get(s) is False for s in sides_in_scenario):
        ok.append(
            "OK: Nuclear policy — all sides set use_nuclear_weapons='No' in doctrine."
        )

    if not re.search(
        r"function\s+(?:M\.)?strip_nuclear_from_unit\s*\(", content, re.IGNORECASE
    ) and not re.search(r"strip_nuclear_from_unit\s*=\s*cmo\.strip_nuclear_from_unit", content, re.IGNORECASE):
        warnings.append(
            "Nuclear policy: no strip_nuclear_from_unit() — ship VLS may still list TLAM-N until stripped at runtime."
        )
    elif not re.search(r"strip_nuclear_from_unit\s*\(", content, re.IGNORECASE):
        warnings.append(
            "Nuclear policy: strip_nuclear_from_unit() defined but never called on placed ships."
        )
    else:
        ok.append("OK: Nuclear policy — strip_nuclear_from_unit() present and called.")
        if re.search(
            r"NUCLEAR_WEAPON_DBIDS|NUCLEAR_CRUISE_DBIDS|conventional_tlam_dbid",
            content,
            re.IGNORECASE,
        ):
            ok.append(
                "OK: Nuclear policy — DB-derived nuclear dbid sets (warhead Type 4001) in bootstrap."
            )

    checked_loadouts = set()
    for aircraft_id, loadout_id in unique_pairs:
        if loadout_id in checked_loadouts:
            continue
        checked_loadouts.add(loadout_id)
        loadout_name = _loadout_name_upper(db, loadout_id, series, version)
        if _is_nuclear_loadout_name(loadout_name):
            errors.append(
                f"Nuclear loadout: aircraft {aircraft_id} uses loadout {loadout_id} "
                f"('{loadout_name}') — pick a conventional loadout (CALCM/JDAM/JSOW, not ALCM/TLAM-N/nuclear)."
            )
            continue
        required_hits = _loadout_nuclear_weapon_hits(
            db, loadout_id, series, version, loadout_name, required_only=True
        )
        optional_hits = _loadout_nuclear_weapon_hits(
            db, loadout_id, series, version, loadout_name, required_only=False
        )
        optional_only = [h for h in optional_hits if h not in required_hits]
        for wname, _optional in required_hits:
            errors.append(
                f"Nuclear loadout: loadout {loadout_id} ('{loadout_name}') requires nuclear weapon "
                f"'{wname}' — use a different loadout ID."
            )
        for wname, _optional in optional_only:
            warnings.append(
                f"Nuclear loadout: loadout {loadout_id} ('{loadout_name}') lists optional nuclear "
                f"weapon '{wname}' (usually not mounted)."
            )

    if checked_loadouts and not any("Nuclear loadout:" in e for e in errors):
        ok.append(
            f"OK: Nuclear loadout check — {len(checked_loadouts)} unique loadout(s) have no required nuclear stores."
        )

    # Ship DB templates: warn if default magazines include nuclear (Lua strip should run at runtime).
    from db_nuclear import weapon_dbid_is_nuclear

    for ship in ships:
        if ship.get("kind") == "sub":
            continue
        role, _ = _classify_ship(db, ship["dbid"], series, version)
        if role not in ("carrier", "escort"):
            continue
        weapons_info = get_unit_weapons(
            ship["dbid"], "DataShip", series=series, version=version, db_path=db.path
        )
        if not weapons_info:
            continue
        nuc_weapons = []
        for bucket in ("magazines", "mounts"):
            for mount in weapons_info.get(bucket, []):
                for w in mount.get("weapons", []):
                    wdbid = w[0] if w else None
                    wname = w[1] if len(w) > 1 else None
                    if wdbid and weapon_dbid_is_nuclear(db, wdbid, series, version):
                        nuc_weapons.append(wname or f"ID {wdbid}")
                    elif wname and _is_nuclear_missile_store_for_ship(wname):
                        nuc_weapons.append(wname)
        if nuc_weapons:
            label = ship.get("name") or f"DBID {ship['dbid']}"
            warnings.append(
                f"Nuclear magazine (DB default): ship '{label}' DB lists nuclear-capable stores "
                f"(e.g. {nuc_weapons[0]}) — ensure strip_nuclear_from_unit() runs after spawn (replaces cruise with UGM-109 TLAM)."
            )

    return errors, warnings, ok

def _validate_operator_country_oob(content, assignments, naval_units, db, series, version):
    """
    OperatorCountry vs Lua side (AGENTS.md nationality). Catches Soviet hulls on Cuba side, etc.
    """
    errors = []
    warnings = []
    ok = []
    checked = set()
    ok_logged = False

    def check_unit(side, table, unit_id, label):
        nonlocal ok_logged
        key = (side, table, unit_id)
        if key in checked:
            return
        checked.add(key)
        op_id, op_desc = _unit_operator_description(db, table, unit_id, series, version)
        if op_id is None and not op_desc:
            warnings.append(
                f"Operator country: no OperatorCountry for {label} (ID {unit_id}, {table})."
            )
            return
        if not _side_matches_operator_country(side, op_desc):
            errors.append(
                f"Operator country: side '{side}' hosts '{label}' (ID {unit_id}) with "
                f"OperatorCountry '{op_desc}' — use a DB entry operated by that side."
            )
            return
        if _is_placeholder_operator(op_desc):
            if _spawn_has_operator_last_resort(content, label, unit_id):
                ok.append(
                    f"OK: Operator last resort — '{label}' (ID {unit_id}) uses '{op_desc}' "
                    f"with documented @operator_last_resort."
                )
            else:
                alts = _national_operator_alternatives(
                    db, table, unit_id, series, version
                )
                if alts:
                    warnings.append(
                        f"Operator country: '{label}' (ID {unit_id}) uses placeholder "
                        f"OperatorCountry '{op_desc}' but national/NATO variants exist: "
                        f"{', '.join(alts)}. Prefer those; Junkyard/Generic only as last "
                        f"resort (add -- @operator_last_resort if truly unavoidable)."
                    )
                else:
                    warnings.append(
                        f"Operator country: '{label}' (ID {unit_id}) uses placeholder "
                        f"OperatorCountry '{op_desc}' — no national variant found in DB; "
                        f"acceptable last resort. Document why in the scenario header and "
                        f"add -- @operator_last_resort on the spawn line."
                    )
        if not ok_logged:
            ok_logged = True

    for unit in naval_units:
        table = "DataSubmarine" if unit.get("kind") == "sub" else "DataShip"
        label = unit.get("name") or f"ID {unit['dbid']}"
        check_unit(unit["side"], table, unit["dbid"], label)

    seen_air = set()
    for side, aircraft_id, _loadout_id, _mission_name, _escort_flag in assignments:
        if not side or aircraft_id == 0 or aircraft_id in seen_air:
            continue
        seen_air.add(aircraft_id)
        name, _, _, _ = _unit_service_record(db, "DataAircraft", aircraft_id, series, version)
        check_unit(side, "DataAircraft", aircraft_id, name or f"aircraft {aircraft_id}")

    if not errors and ok_logged:
        ok.append(
            "OK: OperatorCountry matches scenario side for placed naval units and spawned aircraft."
        )
    return errors, warnings, ok

def _annotation_on_line_or_prev(lines, idx, pattern):
    """Return first capture from pattern on line idx or the preceding comment line."""
    m = pattern.search(lines[idx])
    if m:
        return m.group(1).strip()
    if idx > 0 and lines[idx - 1].strip().startswith("--"):
        m = pattern.search(lines[idx - 1])
        if m:
            return m.group(1).strip()
    return None

def _line_has_operator_last_resort(lines, idx):
    if _OPERATOR_LAST_RESORT_RE.search(lines[idx]):
        return True
    if idx > 0 and lines[idx - 1].strip().startswith("--"):
        return bool(_OPERATOR_LAST_RESORT_RE.search(lines[idx - 1]))
    return False

def _spawn_has_operator_last_resort(content, label, unit_id):
    """True when the place/spawn line for this dbid carries @operator_last_resort."""
    patterns = [
        rf"place_(?:ship|sub|sam)\s*\([^)]*'{re.escape(label)}'[^)]*,\s*{unit_id}\b",
        rf"add_air_unit_checked\s*\([^)]*'{re.escape(label)}'[^)]*,\s*{unit_id}\b",
        rf"spawn_air_wing\s*\([^)]*,\s*{unit_id}\s*,",
    ]
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if not any(re.search(p, line, re.IGNORECASE) for p in patterns):
            continue
        if _line_has_operator_last_resort(lines, idx):
            return True
    return False

def _parse_declared_nationalities(content):
    """
    Find spawn/place calls carrying an inline `-- @nationality <Country>` annotation.

    Returns list of (table, dbid, label, declared_nationality, line_no, export_proxy).
    Annotations may sit on the same line as the call or on comment-only lines directly above.
    """
    lines = content.splitlines()
    decl_on_line = [None] * len(lines)
    proxy_on_line = [None] * len(lines)
    for idx, line in enumerate(lines):
        m = _NATIONALITY_ANNOTATION_RE.search(line)
        if m:
            decl_on_line[idx] = m.group(1).strip()
        m = _EXPORT_PROXY_ANNOTATION_RE.search(line)
        if m:
            proxy_on_line[idx] = m.group(1).strip()

    results = []
    for idx, line in enumerate(lines):
        for table, pattern in _NATIONALITY_SPAWN_PATTERNS:
            m = pattern.search(line)
            if not m:
                continue
            label = m.group(1)
            dbid = int(m.group(2))
            declared = _annotation_on_line_or_prev(lines, idx, _NATIONALITY_ANNOTATION_RE)
            if declared is None and idx > 0:
                prev = lines[idx - 1].strip()
                if prev.startswith("--") and decl_on_line[idx - 1]:
                    declared = decl_on_line[idx - 1]
            export_proxy = _annotation_on_line_or_prev(lines, idx, _EXPORT_PROXY_ANNOTATION_RE)
            if export_proxy is None and idx > 0:
                prev = lines[idx - 1].strip()
                if prev.startswith("--") and proxy_on_line[idx - 1]:
                    export_proxy = proxy_on_line[idx - 1]
            if declared:
                results.append((table, dbid, label, declared, idx + 1, export_proxy))
    return results

def _validate_declared_nationality(content, db, series, version):
    """
    Cross-check inline `-- @nationality <Country>` annotations against the DB
    OperatorCountry of each spawned/placed unit. Catches e.g. a Norwegian hull
    labelled as Dutch on a coalition side (where the side name cannot enforce it).
    """
    errors = []
    warnings = []
    ok = []

    declared_units = _parse_declared_nationalities(content)
    if not declared_units:
        warnings.append(
            "Nationality: no '-- @nationality <Country>' annotations found — add them on "
            "spawn_air_wing/add_air_unit_checked/place_ship/place_sub/place_sam lines so "
            "preflight can verify each hull's DB OperatorCountry (coalition sides cannot)."
        )
        return errors, warnings, ok

    direct_match = 0
    export_proxy_ok = 0
    for table, dbid, label, declared, line_no, export_proxy in declared_units:
        _op_id, op_desc = _unit_operator_description(db, table, dbid, series, version)
        if not op_desc:
            warnings.append(
                f"Nationality: no OperatorCountry in DB for {label} (ID {dbid}, {table}, "
                f"line {line_no}) — cannot verify declared '{declared}'."
            )
            continue
        if _operator_desc_matches_nationality(declared, op_desc):
            direct_match += 1
            continue
        if export_proxy and _operator_desc_matches_nationality(export_proxy, op_desc):
            export_proxy_ok += 1
            ok.append(
                f"OK: Export proxy — '{label}' (ID {dbid}, line {line_no}): "
                f"@nationality {declared} uses DB entry operated by '{op_desc}' "
                f"(@export_proxy {export_proxy})."
            )
            continue
        if _is_placeholder_operator(op_desc):
            alts = [
                a for a in _national_operator_alternatives(db, table, dbid, series, version)
                if declared.lower() in a.lower()
                or _normalize_nationality(declared) in _normalize_nationality(a).lower()
            ]
            alt_hint = f" Prefer: {', '.join(alts)}." if alts else ""
            warnings.append(
                f"Nationality: {label} (ID {dbid}, line {line_no}) is Junkyard/Generic "
                f"— cannot verify '@nationality {declared}'.{alt_hint} Use a national "
                f"DBID when available; else @export_proxy <supplier> or @operator_last_resort."
            )
        else:
            errors.append(
                f"Nationality mismatch: {label} (ID {dbid}, {table}, line {line_no}) is "
                f"operated by '{op_desc}' in the DB but declared '@nationality {declared}'. "
                f"Pick a DB entry operated by {declared}, add @export_proxy <exporter> if "
                f"the DB only lists the supplying nation, or correct the annotation."
            )
    has_mismatch = any(e.startswith("Nationality mismatch") for e in errors)
    if direct_match and not has_mismatch:
        ok.append(
            f"OK: Nationality — {direct_match} annotated unit(s) match their DB OperatorCountry."
        )
    if export_proxy_ok and not has_mismatch:
        ok.append(
            f"OK: Export proxy — {export_proxy_ok} unit(s) use supplier DBIDs with "
            f"documented @export_proxy."
        )
    return errors, warnings, ok

def _validate_era_appropriate_oob(scenario_year, assignments, ships, db, series, version):
    """
    Generic era fit: DB service dates vs scenario_year. Does not prescribe specific DBIDs.
    """
    errors = []
    warnings = []
    ok = []
    if not scenario_year:
        warnings.append(
            "Era fit: no scenario_year in Lua — era checks skipped. "
            "Set e.g. local scenario_year = 2026 for time-appropriate validation."
        )
        return errors, warnings, ok

    issues = 0
    seen_air = set()
    for _side, aircraft_id, _loadout_id, _mission_name, _escort_flag in assignments:
        if aircraft_id == 0 or aircraft_id in seen_air:
            continue
        seen_air.add(aircraft_id)
        name, commissioned, decommissioned, _ = _unit_service_record(
            db, "DataAircraft", aircraft_id, series, version
        )
        if not name:
            continue
        if commissioned and commissioned > scenario_year:
            errors.append(
                f"Era fit ({scenario_year}): aircraft '{name}' (ID {aircraft_id}) "
                f"enters service in {commissioned}."
            )
            issues += 1
        elif decommissioned and decommissioned < scenario_year:
            warnings.append(
                f"Era fit ({scenario_year}): aircraft '{name}' (ID {aircraft_id}) "
                f"is marked out of service in DB from {decommissioned}."
            )
            issues += 1

    seen_naval = set()
    for unit in ships:
        unit_id = unit.get("dbid")
        if not unit_id or unit_id in seen_naval:
            continue
        seen_naval.add(unit_id)
        table = "DataSubmarine" if unit.get("kind") == "sub" else "DataShip"
        name, commissioned, decommissioned, _ = _unit_service_record(
            db, table, unit_id, series, version
        )
        if not name:
            continue
        label = unit.get("name") or name
        kind = "submarine" if unit.get("kind") == "sub" else "ship"
        if commissioned and commissioned > scenario_year:
            errors.append(
                f"Era fit ({scenario_year}): {kind} '{label}' (ID {unit_id}) "
                f"enters service in {commissioned}."
            )
            issues += 1
        elif decommissioned and decommissioned < scenario_year:
            warnings.append(
                f"Era fit ({scenario_year}): {kind} '{label}' (ID {unit_id}) "
                f"is marked out of service in DB from {decommissioned}."
            )
            issues += 1

    if not issues and (seen_air or seen_naval):
        ok.append(
            f"OK: Era fit — assigned platforms match scenario_year {scenario_year} "
            "(DB YearCommissioned / YearDecommissioned)."
        )
    return errors, warnings, ok

def _validate_modern_strike_munitions(scenario_year, assignments, mission_map, db, series, version):
    errors = []
    warnings = []
    ok = []
    if not scenario_year or scenario_year < 2000:
        return errors, warnings, ok

    strike_missions = {name for name, role in mission_map.items() if role == "strike"}
    dumb_on_strike = []
    for side, aircraft_id, loadout_id, mission_name, escort_flag in assignments:
        if escort_flag is True or aircraft_id == 0 or mission_name not in strike_missions:
            continue
        loadout_u = _loadout_name_upper(db, loadout_id, series, version)
        roles = _loadout_roles(loadout_u)
        if "dumb_strike" in roles and "precision_strike" not in roles and "standoff" not in roles:
            dumb_on_strike.append((side, aircraft_id, loadout_id, loadout_u))

    if not dumb_on_strike:
        if scenario_year >= 2000:
            ok.append(
                f"OK: Era-appropriate strike munitions for {scenario_year} "
                "(loadout names classified as precision/standoff, not dumb-only)."
            )
        return errors, warnings, ok

    for side, aircraft_id, loadout_id, loadout_u in dumb_on_strike:
        msg = (
            f"Era-appropriate munitions ({scenario_year}): strike uses primarily unguided loadout "
            f"({loadout_u}, aircraft {aircraft_id}, loadout {loadout_id}). "
            "Use precision/standoff names in the loadout (JDAM, JSOW, JASSM, CALCM, GBU-, etc.)."
        )
        if scenario_year >= 2010:
            errors.append(msg)
        else:
            warnings.append(msg)
    return errors, warnings, ok

__all__ = ['_annotation_on_line_or_prev', '_line_has_operator_last_resort', '_parse_declared_nationalities', '_spawn_has_operator_last_resort', '_validate_declared_nationality', '_validate_era_appropriate_oob', '_validate_modern_strike_munitions', '_validate_no_nuclear_weapons', '_validate_operator_country_oob']
