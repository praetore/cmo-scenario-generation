"""Search CMO equipment databases (units, loadouts, weapons)."""

import argparse
import sys

from cmo_db import open_db
from db_unit_queries import get_loadouts, get_unit_weapons

SEARCH_TABLES = [
    "DataAircraft",
    "DataShip",
    "DataSubmarine",
    "DataFacility",
    "DataWeapon",
    "DataGroundUnit",
]


def search_db(
    search_term,
    db_series=None,
    db_version=None,
    limit=10,
    search_id=False,
    db_path=None,
):
    db = open_db(db_path=db_path, series=db_series, version=db_version)
    cursor = db.cursor
    results = []

    for table in SEARCH_TABLES:
        cols = f"ID, Name, {db.meta_select()}, OperatorCountry"
        if table == "DataAircraft":
            cols += ", Category, RunwayLengthCode"
        else:
            cols += ", 0 as Category, 0 as RunwayLengthCode"

        params = []
        if search_id:
            try:
                params = [int(search_term)]
            except ValueError:
                params = [search_term]
            query = f"SELECT {cols}, '{table}' as Type FROM {table} WHERE ID = ?"
        else:
            query = f"SELECT {cols}, '{table}' as Type FROM {table} WHERE Name LIKE ?"
            params = [f"%{search_term}%"]

        query, params = db.append_meta_filters(query, params)
        if not search_id:
            query += f" LIMIT {limit}"

        try:
            cursor.execute(query, params)
            results.extend(cursor.fetchall())
        except Exception:
            continue

    db.close()
    return results


def _db_mode_args(args):
    return {"db_path": args.db}


def _print_weapon_config(data, unit_type, unit_id):
    if not data or (not data["magazines"] and not data["mounts"]):
        print(f"No weapon configuration found for {unit_type} ID '{unit_id}'")
        return

    print(f"Weapon configuration for {unit_type} ID '{unit_id}'")
    if data["magazines"]:
        print("\n### MAGAZINES ###")
        print(f"{'Mag ID':<10} | {'Name':<40} | {'Series/Ver':<12}")
        print("-" * 100)
        for mag in data["magazines"]:
            print(f"{mag['id']:<10} | {mag['name']:<40} | {mag['series']}/{mag['version']}")
            for w_id, w_name, qty in mag["weapons"]:
                print(f"  -> {qty:>4}x [ID {w_id:>5}] {w_name}")

    if data["mounts"]:
        print("\n### MOUNTS ###")
        print(f"{'Mount ID':<10} | {'Name':<40} | {'Series/Ver':<12}")
        print("-" * 100)
        for mount in data["mounts"]:
            print(f"{mount['id']:<10} | {mount['name']:<40} | {mount['series']}/{mount['version']}")
            for w_id, w_name, load in mount["weapons"]:
                print(f"  -> {load:>4}x [ID {w_id:>5}] {w_name}")


def main():
    parser = argparse.ArgumentParser(description="Search CMO equipment databases")
    parser.add_argument("term", nargs="?", help="The search term or ID")
    parser.add_argument("--series", help="DB series (DB3K or CWDB)")
    parser.add_argument("--version", help="DB version (e.g., 515)")
    parser.add_argument("--limit", type=int, default=5, help="Limit results per type")
    parser.add_argument("--id", action="store_true", help="Search by ID instead of name")
    parser.add_argument("--loadouts", help="Show loadouts/weapon config for a specific Unit ID")
    parser.add_argument("--weapons", help="Show magazines and mounts for a specific Unit ID")
    parser.add_argument(
        "--type",
        help="Unit type for --loadouts/--weapons (DataAircraft, DataShip, DataFacility, DataSubmarine, DataGroundUnit)",
    )
    parser.add_argument(
        "--validate-scenario",
        help="(deprecated) Use validate_scenario.py instead",
    )
    parser.add_argument("--db", help="Explicit path to a CMO source .db3 file")

    args = parser.parse_args()
    db_kwargs = _db_mode_args(args)

    if args.validate_scenario:
        print(
            "Note: --validate-scenario on db_search.py is deprecated; "
            "use: python scripts/validate_scenario.py <scenario.lua> --series ... --version ...",
            file=sys.stderr,
        )
        from preflight_validate import validate_scenario_air_loadouts

        report = validate_scenario_air_loadouts(
            args.validate_scenario,
            series=args.series,
            version=args.version,
            **db_kwargs,
        )
        for line in report["ok"]:
            print(line)
        for line in report["warnings"]:
            print(f"WARNING: {line}")
        for line in report["errors"]:
            print(f"ERROR: {line}")
        if report["errors"]:
            sys.exit(2)
        if report["warnings"]:
            sys.exit(1)
        print("Scenario validation passed.")
        return

    if args.loadouts:
        unit_type = args.type or "DataAircraft"
        if unit_type == "DataAircraft":
            results = get_loadouts(args.loadouts, args.series, args.version, **db_kwargs)
            if not results:
                print(f"No loadouts found for Aircraft ID '{args.loadouts}'")
                return
            print(f"{'Loadout ID':<12} | {'Series':<6} | {'Ver':<5} | {'Name'}")
            print("-" * 100)
            for lid, name, ser, ver in results:
                print(f"{lid:<12} | {ser:<6} | {ver:<5} | {name}")
            return

        _print_weapon_config(
            get_unit_weapons(args.loadouts, unit_type, args.series, args.version, **db_kwargs),
            unit_type,
            args.loadouts,
        )
        return

    if args.weapons:
        unit_type = args.type or "DataShip"
        data = get_unit_weapons(args.weapons, unit_type, args.series, args.version, **db_kwargs)
        if not data:
            print(f"No weapon/magazine data found for {unit_type} ID '{args.weapons}'")
            return
        _print_weapon_config(data, unit_type, args.weapons)
        return

    if not args.term:
        parser.print_help()
        return

    results = search_db(
        args.term,
        args.series,
        args.version,
        args.limit,
        args.id,
        **db_kwargs,
    )

    if not results:
        print(f"No results found for '{args.term}'")
        return

    op_cache = {}

    def _operator_label(op_id, cursor):
        if op_id in op_cache:
            return op_cache[op_id]
        row = cursor.execute(
            "SELECT Description FROM EnumOperatorCountry WHERE ID = ?", [op_id]
        ).fetchone()
        desc = (row[0] if row else "?").split("[")[0].strip()
        op_cache[op_id] = f"{op_id} {desc}"
        return op_cache[op_id]

    db = open_db(
        db_path=db_kwargs.get("db_path"),
        series=args.series,
        version=args.version,
    )
    cursor = db.cursor

    print(
        f"{'ID':<10} | {'Type':<15} | {'Series':<6} | {'Ver':<5} | {'Operator':<22} | "
        f"{'Cat/RW':<10} | {'Name'}"
    )
    print("-" * 120)
    for res in results:
        id_val, name, series, version, operator, cat, rw, type_val = res
        extra = ""
        if type_val == "DataAircraft":
            extra = f"{cat}/{rw}"
            if cat == 2002:
                extra += " (CC)"
            if rw == 2001:
                extra += " (VTOL)"
            if rw == 3005:
                extra += " (STOVL)"

        print(
            f"{id_val:<10} | {type_val:<15} | {series:<6} | {version:<5} | "
            f"{_operator_label(operator, cursor):<22} | {extra:<10} | {name}"
        )
    db.close()


if __name__ == "__main__":
    main()
