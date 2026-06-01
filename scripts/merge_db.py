import argparse
import os
import sqlite3

from cmo_config import resolve_db_dir
from cmo_db import (
    FTS_TABLES,
    MAIN_TABLES,
    MASTER_DB,
    select_db_files,
)


def create_indexes(cursor):
    print("Creating indexes...")
    for table in MAIN_TABLES:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table,),
        )
        if not cursor.fetchone():
            continue

        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        if "Name" in columns:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_name ON {table} (Name)"
            )
        if "db_version" in columns:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_version ON {table} (db_version)"
            )
        if "ID" in columns and "db_series" in columns and "db_version" in columns:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_id_series_ver "
                f"ON {table} (ID, db_series, db_version)"
            )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_DataAircraftLoadouts_pair "
        "ON DataAircraftLoadouts (ID, ComponentID, db_series, db_version)"
    )


def create_fts_indexes(cursor):
    print("Creating FTS5 indexes...")
    for table in FTS_TABLES:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table,),
        )
        if not cursor.fetchone():
            continue

        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        if "Name" not in columns:
            continue

        fts_table = f"fts_{table}"
        cursor.execute(f"DROP TABLE IF EXISTS {fts_table}")
        cursor.execute(
            f"CREATE VIRTUAL TABLE {fts_table} USING fts5(Name, content='{table}', content_rowid='rowid')"
        )
        cursor.execute(
            f"INSERT INTO {fts_table}(rowid, Name) SELECT rowid, Name FROM {table}"
        )


def merge_databases(
    db_dir=None,
    output_db=MASTER_DB,
    series_filters=None,
    versions=None,
    latest_per_series=None,
):
    db_dir = os.fspath(db_dir or resolve_db_dir())
    output_db = os.fspath(output_db)
    selected_files = select_db_files(
        db_dir,
        series_filters=series_filters,
        versions=versions,
        latest_per_series=latest_per_series,
    )
    if not selected_files:
        raise SystemExit(f"No source databases selected in {db_dir}")

    if os.path.exists(output_db):
        os.remove(output_db)

    master_conn = sqlite3.connect(output_db)
    master_cursor = master_conn.cursor()

    for i, (db_file, series, version) in enumerate(selected_files, start=1):
        print(f"Processing {db_file} ({i}/{len(selected_files)})...")
        db_path = os.path.join(db_dir, db_file)
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            for table in MAIN_TABLES:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                    (table,),
                )
                if not cursor.fetchone():
                    continue

                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]

                master_cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                    (table,),
                )
                if not master_cursor.fetchone():
                    col_defs = ", ".join([f'"{c}"' for c in columns])
                    master_cursor.execute(
                        f"CREATE TABLE {table} ({col_defs}, db_series TEXT, db_version TEXT)"
                    )

                master_cursor.execute(f"PRAGMA table_info({table})")
                master_columns = [row[1] for row in master_cursor.fetchall()]
                for col in columns:
                    if col not in master_columns:
                        master_cursor.execute(f'ALTER TABLE {table} ADD COLUMN "{col}"')

                col_names = ", ".join([f'"{c}"' for c in columns])
                placeholders = ", ".join(["?"] * len(columns))

                cursor.execute(f"SELECT {col_names} FROM {table}")
                rows = cursor.fetchall()
                rows_with_meta = [row + (series, version) for row in rows]

                master_cursor.executemany(
                    f"INSERT INTO {table} ({col_names}, db_series, db_version) "
                    f"VALUES ({placeholders}, ?, ?)",
                    rows_with_meta,
                )

            conn.close()
        except Exception as exc:
            print(f"Error processing {db_file}: {exc}")

    create_indexes(master_cursor)
    create_fts_indexes(master_cursor)

    master_conn.commit()
    master_conn.close()
    print(f"Merge complete. Master database saved to {output_db}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build CMO_Master.db from CMO source .db3 files."
    )
    parser.add_argument(
        "--db-dir",
        default=None,
        help="Source .db3 directory (default: cmo_config.json or repo DB/)",
    )
    parser.add_argument("--output", default=os.fspath(MASTER_DB))
    parser.add_argument(
        "--series",
        action="append",
        help="Only include this DB series (DB3K or CWDB). Repeatable.",
    )
    parser.add_argument(
        "--versions",
        help="Comma-separated DB versions to include, e.g. 514,515.",
    )
    parser.add_argument(
        "--latest",
        type=int,
        help="Only include the N newest versions per series.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    versions = [part.strip() for part in args.versions.split(",")] if args.versions else None
    merge_databases(
        db_dir=args.db_dir,
        output_db=args.output,
        series_filters=args.series,
        versions=versions,
        latest_per_series=args.latest,
    )
