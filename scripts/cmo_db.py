import os
import re
import sqlite3
from pathlib import Path

from cmo_config import LOCAL_DB_DIR, config_source_label, format_config_setup_hint, resolve_db_dir

DEFAULT_DB_DIR = LOCAL_DB_DIR  # repo-local fallback; prefer resolve_db_dir()


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
    """Describe which local CMO source .db3 files exist."""
    db_dir = Path(db_dir or resolve_db_dir())
    sources = list_source_dbs(db_dir)
    return {
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


class DbContext:
    def __init__(self, conn, *, path, series=None, version=None):
        self.conn = conn
        self._cursor = conn.cursor()
        self.path = Path(path)
        self.series = series
        self.version = version

    @property
    def cursor(self):
        return self._cursor

    def close(self):
        self.conn.close()

    def meta_select(self):
        return f"'{self.series}' AS db_series, '{self.version}' AS db_version"

    def append_meta_filters(self, sql, params, table_alias=None):
        return sql, params

    def append_join_meta(self, sql, left_alias, right_alias):
        return sql

    def fixed_series_version(self):
        return self.series, self.version


def open_db(*, db_path=None, series=None, version=None, db_dir=None):
    if db_path:
        path = Path(db_path)
        if not path.is_file():
            raise FileNotFoundError(f"Database not found: {path}")
        inferred_series = get_db_series(path.name)
        inferred_version = get_db_version(path.name)
        conn = sqlite3.connect(path)
        return DbContext(
            conn,
            path=path,
            series=series or inferred_series,
            version=version or inferred_version,
        )

    if series and version:
        source_path = resolve_source_db(series, version, db_dir=db_dir)
        if source_path:
            conn = sqlite3.connect(source_path)
            return DbContext(
                conn,
                path=source_path,
                series=series,
                version=version,
            )

    raise FileNotFoundError(
        f"No database available for series={series!r} version={version!r}.\n"
        f"{format_database_layout_message()}"
    )
