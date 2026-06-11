"""Nuclear weapon classification from CMO SQLite (DataWarhead.Type / EnumWarheadType)."""

from __future__ import annotations

from functools import lru_cache

from cmo_db import open_db

# EnumWarheadType.ID where Description = 'Nuclear'
WARHEAD_TYPE_NUCLEAR = 4001

# EnumWeaponType.ID — guided missiles (cruise subset filtered by name)
WEAPON_TYPE_GUIDED = 2001


def _is_nuclear_cruise_weapon_name(weapon_name: str | None) -> bool:
    """Land-attack nuclear cruise missiles (TLAM-N, ALCM, GLCM) — not bombs or RVs."""
    if not weapon_name:
        return False
    upper = weapon_name.upper()
    if "TLAM-N" in upper or "TLAM N" in upper:
        return True
    if "UGM-109A" in upper or "RGM-109A" in upper:
        return True
    if "BGM-109G" in upper and "GLCM" in upper:
        return True
    if "AGM-86B" in upper:
        return True
    if "AGM-129" in upper and "ACM" in upper:
        return True
    if "ALCM" in upper and "CALCM" not in upper and "CONVENTIONAL" not in upper:
        return True
    if "TOMAHAWK" in upper and "NUCLEAR" in upper:
        return True
    return False


def query_nuclear_weapon_dbids(
    db_path=None,
    series=None,
    version=None,
    *,
    force_master=False,
    prefer_source=False,
):
    """
    Return (all_nuclear_dbids, cruise_nuclear_dbids) from DB warhead links.

    - all: any DataWeapon with a DataWarhead where Type = WARHEAD_TYPE_NUCLEAR (4001)
    - cruise: subset of guided weapons (Type 2001) that are nuclear land-attack cruise
    """
    db = open_db(
        db_path=db_path,
        series=series,
        version=version,
        force_master=force_master,
        prefer_source=prefer_source,
    )
    try:
        query = """
            SELECT DISTINCT w.ID, w.Name, w.Type
            FROM DataWeapon w
            JOIN DataWeaponWarheads wh ON wh.ID = w.ID
            JOIN DataWarhead h ON h.ID = wh.ComponentID
            WHERE h.Type = ?
        """
        params = [WARHEAD_TYPE_NUCLEAR]
        query, params = db.append_meta_filters(query, params, "w")
        rows = db.cursor.execute(query, params).fetchall()

        all_ids: set[int] = set()
        cruise_ids: set[int] = set()
        for row in rows:
            wpn_id, name, wpn_type = int(row[0]), row[1], row[2]
            all_ids.add(wpn_id)
            if wpn_type == WEAPON_TYPE_GUIDED and _is_nuclear_cruise_weapon_name(name):
                cruise_ids.add(wpn_id)
        return all_ids, cruise_ids
    finally:
        db.close()


@lru_cache(maxsize=8)
def _cached_sets(db_path: str, series: str | None, version: str | None):
    return query_nuclear_weapon_dbids(db_path, series, version)


def get_nuclear_weapon_dbid_sets(db, series=None, version=None):
    """Use an open CmoDb instance; returns (all_set, cruise_set)."""
    path = str(db.path)
    return _cached_sets(path, series or db.series, version or db.version)


def weapon_dbid_is_nuclear(db, weapon_dbid, series=None, version=None) -> bool:
    if weapon_dbid is None:
        return False
    all_ids, _ = get_nuclear_weapon_dbid_sets(db, series, version)
    return int(weapon_dbid) in all_ids


def weapon_dbid_is_nuclear_cruise(db, weapon_dbid, series=None, version=None) -> bool:
    if weapon_dbid is None:
        return False
    _, cruise_ids = get_nuclear_weapon_dbid_sets(db, series, version)
    return int(weapon_dbid) in cruise_ids


def format_lua_dbid_set(dbids: set[int]) -> str:
    if not dbids:
        return "{}"
    return "{" + ",".join(f"[{i}]=true" for i in sorted(dbids)) + "}"


def inject_nuclear_dbid_tables(bootstrap_lua: str, series: str, version: str, db_path=None) -> str:
    """Replace placeholder tables in scenario_bootstrap.lua with DB-derived sets."""
    all_ids, cruise_ids = query_nuclear_weapon_dbids(
        db_path=db_path, series=series, version=version
    )
    comment = (
        f"-- DB-derived nuclear dbids ({series}/{version}): "
        f"warhead EnumWarheadType={WARHEAD_TYPE_NUCLEAR} (Nuclear); "
        f"{len(all_ids)} total, {len(cruise_ids)} cruise\n"
    )
    bootstrap_lua = bootstrap_lua.replace(
        "M.NUCLEAR_WEAPON_DBIDS = {}",
        comment + "M.NUCLEAR_WEAPON_DBIDS = " + format_lua_dbid_set(all_ids),
        1,
    )
    bootstrap_lua = bootstrap_lua.replace(
        "M.NUCLEAR_CRUISE_DBIDS = {}",
        "M.NUCLEAR_CRUISE_DBIDS = " + format_lua_dbid_set(cruise_ids),
        1,
    )
    return bootstrap_lua
