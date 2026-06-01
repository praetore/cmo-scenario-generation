import os
import re
import sqlite3
from pathlib import Path

from cmo_config import LOCAL_DB_DIR, REPO_ROOT, config_source_label, format_config_setup_hint, resolve_db_dir

DEFAULT_DB_DIR = LOCAL_DB_DIR  # repo-local fallback; prefer resolve_db_dir()
MASTER_DB = REPO_ROOT / "CMO_Master.db"

MAIN_TABLES = [
    "DataAircraft",
    "DataShip",
    "DataSubmarine",
    "DataFacility",
    "DataWeapon",
    "DataGroundUnit",
    "DataLoadout",
    "DataAircraftLoadouts",
    "DataMagazine",
    "DataMagazineWeapons",
    "DataMount",
    "DataMountWeapons",
    "DataShipMagazines",
    "DataShipMounts",
    "DataFacilityMagazines",
    "DataFacilityMounts",
    "DataSubmarineMagazines",
    "DataSubmarineMounts",
    "DataGroundUnitMagazines",
    "DataGroundUnitMounts",
    "DataAircraftMounts",
]

FTS_TABLES = [
    "DataAircraft",
    "DataShip",
    "DataSubmarine",
    "DataFacility",
    "DataWeapon",
    "DataGroundUnit",
    "DataLoadout",
]


def get_db_series(filename):
    if filename.startswith("DB3K"):
        return "DB3K"
    if filename.startswith("CWDB"):
        return "CWDB"
    return "OTHER"


def get_db_version(filename):
    match = re.search(r"_(\d+[a-z]?)\.db3$", filename, re.IGNORECASE)
    return match.group(1) if match else "0"


def list_source_dbs(db_dir=None):
    db_dir = Path(db_dir or resolve_db_dir())
    if not db_dir.is_dir():
        return []
    return sorted(path.name for path in db_dir.glob("*.db3"))


def database_layout_status(db_dir=None):
    """
    Describe which local database files exist.
    CMO_Master.db is optional (built via merge_db.py); preflight prefers DB/<series>_<ver>.db3.
    """
    db_dir = Path(db_dir or resolve_db_dir())
    sources = list_source_dbs(db_dir)
    return {
        "master_path": MASTER_DB,
        "master_exists": MASTER_DB.is_file(),
        "db_dir": db_dir,
        "db_dir_exists": db_dir.is_dir(),
        "source_dbs": sources,
        "source_count": len(sources),
        "config_source": config_source_label(),
    }


def format_database_layout_message(status=None):
    """Human-readable summary for CLI when databases are missing."""
    status = status or database_layout_status()
    lines = []
    if status["master_exists"]:
        lines.append(f"CMO_Master.db present ({status['master_path']})")
    else:
        lines.append(
            f"CMO_Master.db not found ({status['master_path']}). "
            "This file is generated locally — run: python merge_db.py"
        )
    if status["source_count"]:
        lines.append(
            f"{status['source_count']} source .db3 file(s) in {status['db_dir']} "
            f"(e.g. {status['source_dbs'][:3]})"
        )
    elif status["db_dir_exists"]:
        lines.append(f"No .db3 files in {status['db_dir']} (copy from your CMO install).")
    else:
        lines.append(f"Directory {status['db_dir']} does not exist.")
    lines.append(f"DB path source: {status.get('config_source', 'unknown')}.")
    lines.append(format_config_setup_hint())
    return "\n".join(lines)


def resolve_source_db(series, version, db_dir=None):
    if not series or not version:
        return None

    db_dir = Path(db_dir or resolve_db_dir())
    exact = db_dir / f"{series}_{version}.db3"
    if exact.is_file():
        return exact

    prefix = f"{series}_"
    suffix = f"_{version}.db3"
    matches = sorted(
        path
        for path in db_dir.glob("*.db3")
        if path.name.startswith(prefix) and path.name.endswith(suffix)
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return matches[0]
    return None


def select_db_files(db_dir, series_filters=None, versions=None, latest_per_series=None):
    db_dir = Path(db_dir)
    selected = []
    for filename in list_source_dbs(db_dir):
        series = get_db_series(filename)
        version = get_db_version(filename)
        if series_filters and series not in series_filters:
            continue
        if versions and version not in versions:
            continue
        selected.append((filename, series, version))

    if latest_per_series:
        by_series = {}
        for item in selected:
            by_series.setdefault(item[1], []).append(item)
        selected = []
        for items in by_series.values():
            items.sort(key=lambda row: row[2], reverse=True)
            selected.extend(items[:latest_per_series])
        selected.sort(key=lambda row: (row[1], row[2]))

    return selected


class DbContext:
    def __init__(self, conn, *, master, path, series=None, version=None):
        self.conn = conn
        self._cursor = conn.cursor()
        self.master = master
        self.path = Path(path)
        self.series = series
        self.version = version

    @property
    def cursor(self):
        return self._cursor

    def close(self):
        self.conn.close()

    def meta_select(self):
        if self.master:
            return "db_series, db_version"
        return f"'{self.series}' AS db_series, '{self.version}' AS db_version"

    def append_meta_filters(self, sql, params, table_alias=None):
        if not self.master:
            return sql, params

        prefix = f"{table_alias}." if table_alias else ""
        if self.series:
            sql += f" AND {prefix}db_series = ?"
            params.append(self.series)
        if self.version:
            sql += f" AND {prefix}db_version = ?"
            params.append(self.version)
        return sql, params

    def append_join_meta(self, sql, left_alias, right_alias):
        if not self.master:
            return sql
        return (
            f"{sql} AND {left_alias}.db_series = {right_alias}.db_series "
            f"AND {left_alias}.db_version = {right_alias}.db_version"
        )

    def fixed_series_version(self):
        if self.master:
            return self.series, self.version
        return self.series, self.version


def open_db(
    *,
    db_path=None,
    series=None,
    version=None,
    prefer_source=False,
    force_master=False,
    db_dir=None,
):
    if force_master:
        if not MASTER_DB.is_file():
            raise FileNotFoundError(
                f"Master database not found: {MASTER_DB}\n{format_database_layout_message()}"
            )
        conn = sqlite3.connect(MASTER_DB)
        return DbContext(conn, master=True, path=MASTER_DB, series=series, version=version)

    if db_path:
        path = Path(db_path)
        if not path.is_file():
            raise FileNotFoundError(f"Database not found: {path}")
        inferred_series = get_db_series(path.name)
        inferred_version = get_db_version(path.name)
        conn = sqlite3.connect(path)
        return DbContext(
            conn,
            master=False,
            path=path,
            series=series or inferred_series,
            version=version or inferred_version,
        )

    if prefer_source and series and version:
        source_path = resolve_source_db(series, version, db_dir=db_dir)
        if source_path:
            conn = sqlite3.connect(source_path)
            return DbContext(
                conn,
                master=False,
                path=source_path,
                series=series,
                version=version,
            )

    if not MASTER_DB.is_file():
        source_path = resolve_source_db(series, version, db_dir=db_dir) if series and version else None
        if source_path:
            conn = sqlite3.connect(source_path)
            return DbContext(
                conn,
                master=False,
                path=source_path,
                series=series or get_db_series(source_path.name),
                version=version or get_db_version(source_path.name),
            )
        raise FileNotFoundError(
            f"No database available.\n{format_database_layout_message()}"
        )

    conn = sqlite3.connect(MASTER_DB)
    return DbContext(conn, master=True, path=MASTER_DB, series=series, version=version)


def fts_match_query(search_term):
    tokens = re.findall(r'"[^"]+"|\S+', search_term.strip())
    if not tokens:
        return None
    parts = []
    for token in tokens:
        if token.startswith('"') and token.endswith('"'):
            parts.append(token)
            continue
        escaped = token.replace('"', '""')
        parts.append(f'"{escaped}"*')
    return " AND ".join(parts)


def master_has_fts(cursor, table):
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (f"fts_{table}",),
    )
    return cursor.fetchone() is not None
