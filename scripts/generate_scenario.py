"""Generate CMO load files from generated/src/*_src.lua (CLI entry point).

Authoring convention:
  - Edit ``generated/src/<name>_src.lua`` (source; do not load in CMO).
  - Run ``python scripts/generate_scenario.py generated/src/<name>_src.lua``.
  - Load ``generated/<name>.lua`` in the scenario editor.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from generate_constants import (
    BOOTSTRAP_PATH,
    GENERATED_DIR,
    INLINED_MARKER,
    SOURCE_DIR,
    embedded_scenario_path,
    ensure_source_dir,
    is_source_scenario_path,
    repo_relative,
    resolve_source_input,
    source_scenario_path,
)
from generate_inline import (
    bootstrap_lua_for_inline,
    parse_db_series_version,
    tree_shake_bootstrap,
)
from generate_source import (
    _split_scenario_for_embed,
    apply_source_header,
    prepare_load_header_and_annotations,
    prepare_scenario_source,
)


def generate_scenario(
    scenario_text,
    series="DB3K",
    version="515",
    tree_shake=True,
    src_path: Path | str | None = None,
    inject_briefing: bool = True,
):
    scenario_text = prepare_scenario_source(scenario_text)
    preamble, scenario_code = _split_scenario_for_embed(scenario_text)

    briefing_stub = False
    briefing_sync = "none"
    if inject_briefing and src_path is not None:
        from generate_briefing import append_briefings

        scenario_code, briefing_stub, briefing_sync = append_briefings(
            Path(src_path), scenario_code, create_stub=True
        )

    bootstrap = bootstrap_lua_for_inline(series, version)
    block = bootstrap + "\n"
    load_header, annotations = prepare_load_header_and_annotations(preamble)
    merged = load_header + block + annotations + scenario_code
    shake_stats = {
        "skipped": True,
        "reason": "tree-shake disabled",
        "briefing_stub": briefing_stub,
        "briefing_sync": briefing_sync,
    }
    if tree_shake:
        merged, shake_stats = tree_shake_bootstrap(merged)
    shake_stats["briefing_stub"] = briefing_stub
    shake_stats["briefing_sync"] = briefing_sync
    return merged, shake_stats


def _preflight_gate(source_path: Path, series: str, version: str) -> int:
    """Run preflight on source; return 0 if ok, 2 if errors (do not write load file)."""
    from preflight_validate import validate_scenario_air_loadouts

    report = validate_scenario_air_loadouts(
        str(source_path),
        series=series,
        version=version,
    )
    for line in report.get("ok", []):
        print(line)
    for line in report.get("warnings", []):
        print(f"WARNING: {line}", file=sys.stderr)
    for line in report.get("errors", []):
        print(f"ERROR: {line}", file=sys.stderr)
    if report["errors"]:
        print(
            f"Generate aborted — fix {len(report['errors'])} preflight error(s) in "
            f"{repo_relative(source_path)}.",
            file=sys.stderr,
        )
        return 2
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Generate CMO load file from generated/src/*_src.lua (inline bootstrap + briefings), "
            "or inject briefings into a standalone generated/*.lua load file."
        )
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        help="Source scenario .lua in generated/src/ (e.g. generated/src/foo_src.lua)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write CMO load file elsewhere (default: generated/<name>.lua without _src)",
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
    parser.add_argument(
        "--no-shake",
        action="store_true",
        help="Skip tree-shaking unused bootstrap helpers after generate",
    )
    parser.add_argument(
        "--extract-source",
        metavar="EMBEDDED",
        help=(
            "Extract generated/<name>_src.lua from an embedded generated/<name>.lua "
            "(migration helper; does not run generate)"
        ),
    )
    parser.add_argument(
        "--migrate-embedded",
        action="store_true",
        help=(
            "For each embedded *.lua in generated/ (not *_src), write *_src.lua and rebuild "
            "the CMO load file"
        ),
    )
    parser.add_argument(
        "--no-briefing",
        action="store_true",
        help="Do not inject player briefings from generated/src/*_briefing.txt",
    )
    parser.add_argument(
        "--relocate-sources",
        action="store_true",
        help="Move generated/*_src.lua into generated/src/ and refresh headers",
    )
    args = parser.parse_args(argv)

    if not BOOTSTRAP_PATH.is_file():
        print(f"ERROR: bootstrap not found: {BOOTSTRAP_PATH}", file=sys.stderr)
        return 1

    if args.relocate_sources:
        return _cmd_relocate_sources()
    if args.migrate_embedded:
        return _cmd_migrate_embedded(args)
    if args.extract_source:
        return _cmd_extract_source(Path(args.extract_source))
    if not args.scenario:
        parser.error("scenario path required (or use --extract-source / --migrate-embedded)")

    input_path = resolve_source_input(args.scenario)
    raw = Path(args.scenario)
    if input_path is None and raw.is_file() and raw.suffix.lower() == ".lua":
        raw = raw.resolve()
        if raw.parent.resolve() == GENERATED_DIR.resolve():
            if args.no_briefing:
                print("Load file given with --no-briefing; nothing to do.", file=sys.stderr)
                return 0
            from generate_briefing import (
                briefing_html_path,
                briefing_txt_path,
                inject_briefings_into_load,
            )

            stub, sync = inject_briefings_into_load(raw)
            txt_path = briefing_txt_path(raw)
            html_path = briefing_html_path(raw)
            if stub:
                print(f"Briefing stubs: {repo_relative(txt_path)} + {repo_relative(html_path)}")
            elif sync == "txt+html_written":
                print(f"Briefing: {repo_relative(txt_path)} -> updated {repo_relative(html_path)}")
            else:
                print(f"Briefing: {repo_relative(txt_path)} + {repo_relative(html_path)}")
            print(f"Updated {repo_relative(raw)}")
            return 0

    if input_path is None:
        suggested = source_scenario_path(raw if raw.suffix else GENERATED_DIR / raw.name)
        print(f"ERROR: source not found: {args.scenario}", file=sys.stderr)
        print(
            f"  Expected: {repo_relative(suggested)} (*_src.lua under generated/src/)",
            file=sys.stderr,
        )
        if raw.is_file() and not is_source_scenario_path(raw):
            print(
                f"  To extract from embedded: "
                f"python scripts/generate_scenario.py --extract-source {raw}",
                file=sys.stderr,
            )
        elif raw.is_file():
            print(
                "  Relocate: python scripts/generate_scenario.py --relocate-sources",
                file=sys.stderr,
            )
        return 1

    if input_path.parent.resolve() != SOURCE_DIR.resolve():
        print(
            f"ERROR: source must live in {repo_relative(SOURCE_DIR)}/ "
            f"(got {repo_relative(input_path.parent)}/)",
            file=sys.stderr,
        )
        return 1

    out_path = Path(args.output) if args.output else embedded_scenario_path(input_path)
    scenario_text = input_path.read_text(encoding="utf-8", errors="ignore")

    if not re.search(r"\bcmo\.", scenario_text):
        print(
            "ERROR: source has no cmo.* calls — bootstrap generate is not needed.\n"
            "  Standalone scenarios: edit and load generated/<name>.lua directly (no _src).",
            file=sys.stderr,
        )
        return 1

    series, version = parse_db_series_version(scenario_text, args.series, args.version)
    if _preflight_gate(input_path, series, version) != 0:
        return 2
    merged, shake_stats = generate_scenario(
        scenario_text,
        series,
        version,
        tree_shake=not args.no_shake,
        src_path=input_path,
        inject_briefing=not args.no_briefing,
    )
    if not args.no_briefing:
        from generate_briefing import briefing_html_path, briefing_txt_path

        txt_rel = repo_relative(briefing_txt_path(input_path))
        html_rel = repo_relative(briefing_html_path(input_path))
        if shake_stats.get("briefing_stub"):
            print(f"Briefing stubs created: {txt_rel} + {html_rel}")
        else:
            sync = shake_stats.get("briefing_sync", "")
            if sync == "txt+html_written":
                print(f"Briefing: {txt_rel} -> updated {html_rel}")
            elif sync == "html":
                print(f"Briefing: {html_rel} (newer than txt)")
            else:
                print(f"Briefing: {txt_rel} + {html_rel}")
    if not shake_stats.get("skipped"):
        print(
            f"Tree-shake: kept {shake_stats['kept_functions']}/"
            f"{shake_stats['total_functions']} helpers "
            f"({shake_stats['removed_functions']} removed, "
            f"{shake_stats['lines_saved']} bootstrap lines saved)"
        )
        if shake_stats["roots"]:
            print(f"  entry points: {', '.join(shake_stats['roots'])}")
    elif not args.no_shake:
        print(f"Tree-shake skipped: {shake_stats.get('reason', 'unknown')}")

    from db_nuclear import query_nuclear_weapon_dbids

    all_ids, cruise_ids = query_nuclear_weapon_dbids(series=series, version=version)
    print(
        f"Nuclear dbids ({series}/{version}): "
        f"{len(all_ids)} warhead Type 4001, {len(cruise_ids)} cruise"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(merged, encoding="utf-8")
    line_count = len(merged.splitlines())
    print(f"Wrote CMO load file {repo_relative(out_path)} ({out_path.stat().st_size} bytes, {line_count} lines)")
    print(f"Source (edit): {repo_relative(input_path)}")

    return 0


def _cmd_extract_source(embedded_path: Path) -> int:
    if not embedded_path.is_file():
        print(f"ERROR: file not found: {embedded_path}", file=sys.stderr)
        return 1
    if is_source_scenario_path(embedded_path):
        print(f"ERROR: {embedded_path.name} is already a source file.", file=sys.stderr)
        return 1
    ensure_source_dir()
    src_path = source_scenario_path(embedded_path.resolve())
    text = embedded_path.read_text(encoding="utf-8", errors="ignore")
    if (
        INLINED_MARKER.search(text) is None
        and not re.search(r"^local M\s*=\s*\{", text, re.MULTILINE)
        and "cmo." not in text
    ):
        print(
            f"WARNING: {embedded_path.name} does not look embedded; copying as source anyway.",
            file=sys.stderr,
        )
    source = apply_source_header(text, src_path)
    src_path.write_text(source, encoding="utf-8")
    print(f"Wrote source {repo_relative(src_path)} ({len(source.splitlines())} lines)")
    print(f"CMO load file: {repo_relative(embedded_scenario_path(src_path))}")
    return 0


def _cmd_relocate_sources() -> int:
    ensure_source_dir()
    rc = 0
    for legacy in sorted(GENERATED_DIR.glob("*_src.lua")):
        dest = SOURCE_DIR / legacy.name
        print(f"=== {legacy.name} -> {repo_relative(dest)} ===")
        text = legacy.read_text(encoding="utf-8", errors="ignore")
        source = apply_source_header(text, dest)
        dest.write_text(source, encoding="utf-8")
        legacy.unlink()
        if _main_generate_only([str(dest)]) != 0:
            rc = 1
    if not list(GENERATED_DIR.glob("*_src.lua")) and not list(SOURCE_DIR.glob("*_src.lua")):
        print("No *_src.lua files found to relocate.")
    return rc


def _uses_bootstrap_helpers(text: str) -> bool:
    if INLINED_MARKER.search(text):
        return True
    return bool(re.search(r"\bcmo\.(assert_db_series|configure_)", text))


def _cmd_migrate_embedded(args) -> int:
    if not GENERATED_DIR.is_dir():
        print(f"ERROR: {repo_relative(GENERATED_DIR)} not found", file=sys.stderr)
        return 1
    ensure_source_dir()
    rc = 0
    for embedded in sorted(GENERATED_DIR.glob("*.lua")):
        if is_source_scenario_path(embedded):
            continue
        text = embedded.read_text(encoding="utf-8", errors="ignore")
        if not _uses_bootstrap_helpers(text):
            print(f"Skip (standalone): {embedded.name}")
            continue
        src_path = source_scenario_path(embedded)
        print(f"=== {embedded.name} -> {src_path.name} ===")
        if _cmd_extract_source(embedded) != 0:
            rc = 1
            continue
        gen_argv = [str(src_path)]
        if args.series:
            gen_argv.extend(["--series", args.series])
        if args.version:
            gen_argv.extend(["--version", args.version])
        if args.no_shake:
            gen_argv.append("--no-shake")
        if _main_generate_only(gen_argv) != 0:
            rc = 1
    return rc


def _main_generate_only(argv: list[str]) -> int:
    """Run generate for one ``generated/src/*_src.lua`` (used by migrate/relocate)."""
    input_path = resolve_source_input(argv[0])
    if input_path is None:
        print(f"ERROR: source not found: {argv[0]}", file=sys.stderr)
        return 1
    out_path = embedded_scenario_path(input_path)
    scenario_text = input_path.read_text(encoding="utf-8", errors="ignore")
    series, version = parse_db_series_version(scenario_text, None, None)
    for i, arg in enumerate(argv):
        if arg == "--series" and i + 1 < len(argv):
            series = argv[i + 1]
        if arg == "--version" and i + 1 < len(argv):
            version = argv[i + 1]
    tree_shake = "--no-shake" not in argv
    inject_briefing = "--no-briefing" not in argv
    if _preflight_gate(input_path, series, version) != 0:
        return 2
    merged, shake_stats = generate_scenario(
        scenario_text,
        series,
        version,
        tree_shake=tree_shake,
        src_path=input_path,
        inject_briefing=inject_briefing,
    )
    if not shake_stats.get("skipped"):
        print(
            f"Tree-shake: kept {shake_stats['kept_functions']}/"
            f"{shake_stats['total_functions']} helpers"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(merged, encoding="utf-8")
    print(f"Wrote CMO load file {repo_relative(out_path)} ({len(merged.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
