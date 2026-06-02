"""Merge scripts/scenario_bootstrap.lua into a scenario for CMO import.



CMO's scenario Lua sandbox does not provide dofile/loadfile — external bootstrap

must be inlined before running the script in the editor.

"""



import argparse

import re

import sys

from pathlib import Path



SCRIPTS_DIR = Path(__file__).resolve().parent

BOOTSTRAP_PATH = SCRIPTS_DIR / "scenario_bootstrap.lua"



# Legacy dofile loader (remove from source scenarios).

DOFILE_LOADER = re.compile(

    r"(?:--[^\n]*\n)*?"

    r"local\s+CMO_SCENARIO_REPO\s*=\s*\[\[.*?\]\]\s*\n"

    r"local\s+bootstrap_ok\s*,\s*bootstrap_err\s*=\s*pcall\s*\(\s*dofile\s*,[^\n]+\)\s*\n"

    r"if\s+not\s+bootstrap_ok\s+then\s*\n"

    r"(?:.*\n)*?"

    r"^\s*return\s*\n"

    r"\s*end\s*\n",

    re.MULTILINE,

)



# Previously inlined block (re-embed replaces it).

INLINED_BLOCK = re.compile(

    r"-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n.*?"

    r"(?=^\s*(?:if\s+not\s+cmo\.|--\s*@|\s*local\s+scenario_|\s*ScenEdit_|\s*cmo\.))",

    re.MULTILINE | re.DOTALL,

)





def _parse_db_series_version(scenario_text, series_arg, version_arg):

    series = series_arg

    version = version_arg

    if not series:

        m = re.search(

            r"assert_db_series\s*\(\s*scenario_year\s*,\s*['\"]?(DB3K|CWDB)['\"]?\s*\)",

            scenario_text,

            re.IGNORECASE,

        )

        if m:

            series = m.group(1).upper()

        else:

            m = re.search(

                r"db_series\s*=\s*\([^)]+\)\s*and\s*['\"]?(DB3K|CWDB)['\"]?",

                scenario_text,

                re.IGNORECASE,

            )

            if m:

                series = m.group(1).upper()

    if not series:

        series = "DB3K"

    if not version:

        m = re.search(r"--version\s+(\d+[a-z]?)", scenario_text, re.IGNORECASE)

        if m:

            version = m.group(1)

        else:

            version = "515"

    return series, version





def bootstrap_lua_for_inline(series="DB3K", version="515"):

    text = BOOTSTRAP_PATH.read_text(encoding="utf-8")

    text = re.sub(r"\nreturn\s+M\s*\n?\s*$", "\n", text.rstrip()) + "\n"

    from nuclear_weapons_db import inject_nuclear_dbid_tables



    return inject_nuclear_dbid_tables(text, series, version)





def find_insertion_index(lines):

    for i, line in enumerate(lines):

        if re.match(r"\s*if\s+not\s+cmo\.assert_db_series\s*\(", line):

            return i

        if re.match(r"\s*cmo\.configure_strike_timing\s*\(", line):

            return i

        if re.match(r"\s*cmo\.", line):

            return i

    return len(lines)





def embed_bootstrap(scenario_text, series="DB3K", version="515"):

    scenario_text = DOFILE_LOADER.sub("", scenario_text)

    scenario_text = INLINED_BLOCK.sub("", scenario_text)



    bootstrap = bootstrap_lua_for_inline(series, version)

    marker = (

        "-- [inlined scenario_bootstrap.lua — edit scripts/scenario_bootstrap.lua; "

        "re-run: python scripts/embed_bootstrap.py <scenario.lua>]\n"

    )

    block = marker + bootstrap + "\n"



    lines = scenario_text.splitlines(keepends=True)

    idx = find_insertion_index(lines)

    merged = "".join(lines[:idx]) + block + "".join(lines[idx:])

    return merged





def main(argv=None):

    parser = argparse.ArgumentParser(

        description="Inline scenario_bootstrap.lua for CMO import (no dofile)."

    )

    parser.add_argument("scenario", help="Scenario .lua under generated/ (uses cmo.* helpers)")

    parser.add_argument(

        "-o",

        "--output",

        help="Output path (default: <stem>_import.lua next to input)",

    )

    parser.add_argument(

        "--in-place",

        action="store_true",

        help="Overwrite the input file with the merged script",

    )

    parser.add_argument(

        "--series",

        default=None,

        help="DB series for nuclear dbid tables (default: parse from scenario or DB3K)",

    )

    parser.add_argument(

        "--version",

        default=None,

        help="DB version for nuclear dbid tables (default: parse from scenario or 515)",

    )

    args = parser.parse_args(argv)



    if not BOOTSTRAP_PATH.is_file():

        print(f"ERROR: bootstrap not found: {BOOTSTRAP_PATH}", file=sys.stderr)

        return 1



    scenario_path = Path(args.scenario)

    if not scenario_path.is_file():

        print(f"ERROR: scenario not found: {scenario_path}", file=sys.stderr)

        return 1



    scenario_text = scenario_path.read_text(encoding="utf-8", errors="ignore")

    if "scenario_bootstrap" not in scenario_text:

        print(

            "WARNING: scenario does not mention scenario_bootstrap — "

            "is this file meant to use cmo.* helpers?",

            file=sys.stderr,

        )



    series, version = _parse_db_series_version(scenario_text, args.series, args.version)

    merged = embed_bootstrap(scenario_text, series, version)



    from nuclear_weapons_db import query_nuclear_weapon_dbids



    all_ids, cruise_ids = query_nuclear_weapon_dbids(series=series, version=version)

    print(

        f"Nuclear dbids ({series}/{version}): "

        f"{len(all_ids)} warhead Type 4001, {len(cruise_ids)} cruise"

    )



    if args.in_place:

        out_path = scenario_path

    elif args.output:

        out_path = Path(args.output)

    else:

        out_path = scenario_path.with_name(f"{scenario_path.stem}_import.lua")



    out_path.write_text(merged, encoding="utf-8")

    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())


