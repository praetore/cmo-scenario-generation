"""CLI: run scenario preflight validation before loading Lua in CMO."""

import argparse
import sys

from preflight_validate import validate_scenario_air_loadouts


def _print_report(report):
    for line in report["ok"]:
        print(line)
    for line in report["warnings"]:
        print(f"WARNING: {line}")
    for line in report["errors"]:
        print(f"ERROR: {line}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate a CMO scenario Lua script (loadouts, missions, timing, OOB, …)"
    )
    parser.add_argument("scenario", help="Path to scenario .lua file")
    parser.add_argument("--series", required=True, help="DB series (DB3K or CWDB)")
    parser.add_argument("--version", required=True, help="DB version (e.g., 515)")
    parser.add_argument("--db", help="Explicit path to a CMO source .db3 file")
    args = parser.parse_args()

    report = validate_scenario_air_loadouts(
        args.scenario,
        series=args.series,
        version=args.version,
        db_path=args.db,
    )
    _print_report(report)

    if report["errors"]:
        sys.exit(2)
    if report["warnings"]:
        sys.exit(1)
    print("Scenario validation passed.")


if __name__ == "__main__":
    raise SystemExit(main())
