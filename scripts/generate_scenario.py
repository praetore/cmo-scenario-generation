"""Merge scripts/scenario_bootstrap.lua into a scenario for CMO.

CMO's scenario Lua sandbox does not provide dofile/loadfile — external bootstrap
must be inlined before running the script in the editor.

Authoring convention:
  - Edit ``generated/src/<name>_src.lua`` (source; do not load in CMO).
  - Run ``python scripts/embed_bootstrap.py generated/src/<name>_src.lua``.
  - Load ``generated/<name>.lua`` in the scenario editor (embedded + tree-shaked).
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
GENERATED_DIR = REPO_ROOT / "generated"
SOURCE_DIR = GENERATED_DIR / "src"
BOOTSTRAP_PATH = SCRIPTS_DIR / "scenario_bootstrap.lua"
SOURCE_SUFFIX = "_src"

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

# Previously inlined block (re-embed replaces it). One marker … cmo = M block per iteration.
SINGLE_INLINED = re.compile(
    r"-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n.*?^cmo\s*=\s*M\s*\n",
    re.MULTILINE | re.DOTALL,
)

INLINED_MARKER = re.compile(
    r"^-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n",
    re.MULTILINE,
)
CMO_ASSIGN = re.compile(r"^cmo\s*=\s*M\s*$", re.MULTILINE)
FUNCTION_M = re.compile(r"^function M\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
CONST_M = re.compile(r"^M\.([A-Z][A-Z0-9_]*)\s*=")
ALIAS_M = re.compile(r"^M\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*M\.([A-Za-z_][A-Za-z0-9_]*)")
M_MEMBER = re.compile(r"\bM\.([A-Za-z_][A-Za-z0-9_]*)")
CMO_ENTRY = re.compile(r"\bcmo\.([A-Za-z_][A-Za-z0-9_]*)")
ALIAS_ENTRY = re.compile(
    r"local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*cmo\.([A-Za-z_][A-Za-z0-9_]*)"
)
# Lines that belong only in generated/src/*_src.lua — never in the CMO load file.
AUTHORING_COMMENT = re.compile(
    r"^--\s*(?:SOURCE — do not load|Preflight:\s*python scripts/validate_scenario|"
    r"CMO load:|Bootstrap:\s*scripts/scenario_bootstrap)",
    re.IGNORECASE,
)
TOOLING_IN_COMMENT = re.compile(
    r"^\s*(?:--\s*)?(?:CMO|Preflight):\s*python scripts/(?:embed_bootstrap|validate_scenario)",
    re.IGNORECASE,
)


def repo_relative(path: Path) -> str:
    """Path relative to repository root, forward slashes (for Lua headers)."""
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def is_source_scenario_path(path: Path) -> bool:
    stem = path.stem
    if stem.endswith("_import"):
        stem = stem[: -len("_import")]
    return stem.endswith(SOURCE_SUFFIX)


def embedded_scenario_path(source_path: Path) -> Path:
    """Map ``generated/src/foo_src.lua`` → ``generated/foo.lua`` (CMO load file)."""
    stem = source_path.stem
    if stem.endswith("_import"):
        stem = stem[: -len("_import")]
    if stem.endswith(SOURCE_SUFFIX):
        stem = stem[: -len(SOURCE_SUFFIX)]
    return GENERATED_DIR / f"{stem}{source_path.suffix}"


def source_scenario_path(any_path: Path) -> Path:
    """Map ``generated/foo.lua`` → ``generated/src/foo_src.lua``."""
    stem = any_path.stem
    if stem.endswith("_import"):
        stem = stem[: -len("_import")]
    if stem.endswith(SOURCE_SUFFIX):
        name = any_path.name
    else:
        name = f"{stem}{SOURCE_SUFFIX}{any_path.suffix}"
    return SOURCE_DIR / name


def ensure_source_dir() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)


def relocate_legacy_source(path: Path) -> Path:
    """Move ``generated/<name>_src.lua`` into ``generated/src/`` if needed."""
    path = path.resolve()
    if path.parent == SOURCE_DIR.resolve():
        return path
    if path.parent == GENERATED_DIR.resolve() and is_source_scenario_path(path):
        ensure_source_dir()
        dest = SOURCE_DIR / path.name
        if dest.resolve() != path:
            if dest.is_file():
                path.unlink()
            else:
                shutil.move(str(path), str(dest))
            print(f"Relocated source -> {repo_relative(dest)}")
        return dest.resolve()
    return path


def resolve_source_input(arg: str) -> Path | None:
    """Resolve CLI argument to an existing ``generated/src/*_src.lua`` file."""
    raw = Path(arg)
    candidates: list[Path] = []
    if raw.is_file():
        candidates.append(raw.resolve())
    candidates.extend(
        [
            (SOURCE_DIR / raw.name).resolve(),
            (SOURCE_DIR / raw).resolve(),
            (GENERATED_DIR / raw.name).resolve(),
            raw.resolve(),
        ]
    )
    seen: set[Path] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if cand.is_file() and is_source_scenario_path(cand):
            return relocate_legacy_source(cand)
    return None


def canonical_scenario_path(path: Path) -> Path:
    """Resolve embed output path from a source path."""
    if is_source_scenario_path(path):
        return embedded_scenario_path(path)
    stem = path.stem
    if stem.endswith("_import"):
        return path.with_name(f"{stem[: -len('_import')]}{path.suffix}")
    return path


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
        version = m.group(1) if m else "515"
    return series, version


def bootstrap_lua_for_inline(series="DB3K", version="515"):
    text = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    text = re.sub(r"\nreturn\s+M\s*\n?\s*$", "\n", text.rstrip()) + "\n"
    from db_nuclear import inject_nuclear_dbid_tables

    text = inject_nuclear_dbid_tables(text, series, version)
    return _strip_bootstrap_doc_preamble(text)


def _strip_bootstrap_doc_preamble(lua: str) -> str:
    """Drop the bootstrap file header comments — docs live in git / skills_cmo.md."""
    m = re.search(r"^local M\s*=\s*\{\}\s*$", lua, re.MULTILINE)
    if not m:
        return lua
    return lua[m.start() :]


def find_insertion_index(lines):
    """Legacy helper — embed now places bootstrap before all scenario code."""
    last_header = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("--") or stripped == "":
            last_header = i + 1
            continue
        if re.match(r"local scenario_", line) or re.match(r"local db_series", stripped):
            last_header = i + 1
            continue
        if re.search(r"\bcmo\.", line):
            return i
        if re.match(r"if\s+not\s+cmo\.", stripped):
            return i
        if re.match(r"ScenEdit_", stripped):
            return i
    return last_header


def _is_authoring_comment_line(line: str) -> bool:
    return bool(AUTHORING_COMMENT.match(line.strip()))


def _scrub_authoring_line(line: str) -> str | None:
    """Drop src-only / tooling comment lines; return line or None."""
    if _is_authoring_comment_line(line):
        return None
    if TOOLING_IN_COMMENT.match(line):
        return None
    return line


def _split_scenario_for_embed(text: str) -> tuple[str, str]:
    """Split source into (load-file preamble comments, scenario Lua after ``cmo = M``).

    Bootstrap is inserted before both parts so scenario locals and ``cmo.*`` calls
    run after helpers are defined.
    """
    lines = text.splitlines(keepends=True)
    preamble: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("--[["):
            block: list[str] = []
            while i < len(lines):
                kept = _scrub_authoring_line(lines[i])
                if kept is not None:
                    block.append(kept)
                if "]]" in lines[i]:
                    i += 1
                    break
                i += 1
            if block:
                preamble.extend(block)
            continue
        if stripped == "" or stripped.startswith("--"):
            kept = _scrub_authoring_line(line)
            if kept is not None:
                preamble.append(kept)
            i += 1
            continue
        break
    preamble_text = "".join(preamble).rstrip()
    if preamble_text:
        preamble_text += "\n\n"
    return preamble_text, "".join(lines[i:])


def _bootstrap_signature_index(text: str) -> int | None:
    m = re.search(
        r"^(-- \[inlined scenario_bootstrap|^function M\.|^local M = \{\})",
        text,
        re.MULTILINE,
    )
    return m.start() if m else None


def _trim_to_scenario_header(text: str) -> str:
    """Keep only comment lines and scenario ``local`` declarations."""
    boot_i = _bootstrap_signature_index(text)
    if boot_i is not None:
        text = text[:boot_i]
    scenario_m = _scenario_body_start(text)
    if scenario_m:
        text = text[: scenario_m.start()]
    return text.rstrip() + "\n\n" if text.strip() else ""


def _normalize_workflow_comments(
    text: str, src_path: Path | None = None, src_basename: str | None = None
) -> str:
    """Update legacy workflow lines in scenario headers."""
    if src_path is not None:
        src_disp = repo_relative(src_path)
        embed_disp = repo_relative(embedded_scenario_path(src_path))
    else:
        name = src_basename or "<name>_src.lua"
        src_disp = f"generated/src/{name}"
        embed_disp = f"generated/{name.replace('_src.lua', '.lua')}"
    text = re.sub(
        r"--\s*CMO import:.*\n(?:--\s*→[^\n]*_import\.lua[^\n]*\n)?",
        f"-- CMO load: {embed_disp} (run: python scripts/embed_bootstrap.py {src_disp})\n",
        text,
        count=1,
    )
    text = re.sub(
        r"-- CMO: python scripts/embed_bootstrap\.py[^\n]*\n",
        f"-- CMO load: {embed_disp} (run: python scripts/embed_bootstrap.py {src_disp})\n",
        text,
        count=1,
    )
    text = re.sub(
        r"-- CMO load: generated/[^\n]*\n",
        f"-- CMO load: {embed_disp} (run: python scripts/embed_bootstrap.py {src_disp})\n",
        text,
        count=1,
    )
    text = re.sub(r"[^\n]*_import\.lua[^\n]*\n", "", text)
    text = re.sub(
        r"db_search\.py --validate-scenario",
        "validate_scenario.py",
        text,
    )
    text = re.sub(
        r"python scripts/db_search\.py --validate-scenario",
        "python scripts/validate_scenario.py",
        text,
    )
    return text


def apply_source_header(text: str, src_path: Path) -> str:
    """Ensure source files declare they must not be loaded in CMO."""
    src_path = relocate_legacy_source(src_path.resolve())
    src_disp = repo_relative(src_path)
    embed_disp = repo_relative(embedded_scenario_path(src_path))
    banner = (
        f"-- SOURCE — do not load this file in CMO. Edit {src_path.name} in generated/src/ only.\n"
        f"-- Preflight: python scripts/validate_scenario.py {src_disp} ...\n"
        f"-- CMO load:  {embed_disp} "
        f"(python scripts/embed_bootstrap.py {src_disp})\n"
    )
    text = _prepare_scenario_source(text)
    text = _normalize_workflow_comments(text, src_path=src_path)
    if text.startswith("-- SOURCE — do not load"):
        text = re.sub(
            r"^-- SOURCE — do not load[^\n]*\n"
            r"(?:-- Preflight:[^\n]*\n)?"
            r"(?:-- CMO load:[^\n]*\n)?",
            banner,
            text,
            count=1,
        )
        return text
    return banner + text.lstrip()


def extract_source_text(scenario_text: str, src_path: Path | None = None) -> str:
    """Strip inlined bootstrap; return clean source body."""
    text = _prepare_scenario_source(scenario_text)
    if src_path is not None:
        text = apply_source_header(text, src_path)
    return text


def _strip_inlined_blocks(text: str) -> str:
    """Remove every inlined bootstrap block (marker through ``cmo = M``)."""
    while SINGLE_INLINED.search(text):
        text = SINGLE_INLINED.sub("", text, count=1)
    return text


def _scenario_body_start(pattern_text: str) -> re.Match[str] | None:
    return re.search(
        r"^\s*(?:if\s+not\s+cmo\.assert_db_series|ScenEdit_AddSide|ScenEdit_SetTime)",
        pattern_text,
        re.MULTILINE,
    )


def _strip_pre_marker_orphan(text: str) -> str:
    """Drop bootstrap debris between the scenario header and the first inlined marker."""
    marker = INLINED_MARKER.search(text)
    if not marker:
        return text
    prefix = text[: marker.start()]
    orphan = prefix
    if not re.search(r"^function M\.|^local M = \{\}", orphan, re.MULTILINE):
        return text
    header = _trim_to_scenario_header(prefix)
    return header + text[marker.start() :]


def _strip_incomplete_inlined(text: str) -> str:
    """Remove a marker-led bootstrap fragment that never reached ``cmo = M``."""
    while True:
        marker = INLINED_MARKER.search(text)
        if not marker:
            return text
        tail = text[marker.start() :]
        if re.match(
            r"^-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n.*?^cmo\s*=\s*M\s*\n",
            tail,
            re.MULTILINE | re.DOTALL,
        ):
            return text
        after_marker = text[marker.end() :]
        scenario_m = _scenario_body_start(after_marker)
        if not scenario_m:
            return text
        text = text[: marker.start()] + after_marker[scenario_m.start() :]


def _strip_orphan_bootstrap(text: str) -> str:
    """Remove broken bootstrap fragments left without an inlined marker."""
    if INLINED_MARKER.search(text):
        return text
    if not re.search(r"^function M\.", text, re.MULTILINE):
        return text
    scenario_m = _scenario_body_start(text)
    if not scenario_m:
        return text
    header = _trim_to_scenario_header(text[: scenario_m.start()])
    return header + text[scenario_m.start() :]


def _prepare_scenario_source(text: str) -> str:
    text = DOFILE_LOADER.sub("", text)
    text = _strip_inlined_blocks(text)
    text = _strip_pre_marker_orphan(text)
    text = _strip_incomplete_inlined(text)
    text = _strip_orphan_bootstrap(text)
    return text


def _top_level_kind(line: str) -> str | None:
    if re.match(r"^function M\.", line):
        return "function"
    if CONST_M.match(line):
        return "const"
    if ALIAS_M.match(line):
        return "alias"
    if re.match(r"^cmo\s*=\s*M\s*$", line.strip()):
        return "footer"
    return None


def _split_embedded(merged_text: str):
    """Split merged file into (before, bootstrap_block, scenario_after)."""
    marker = INLINED_MARKER.search(merged_text)
    if not marker:
        return None
    block_m = re.search(
        r"^-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n.*?^cmo\s*=\s*M\s*$",
        merged_text[marker.start() :],
        re.MULTILINE | re.DOTALL,
    )
    if not block_m:
        return None
    boot_end = marker.start() + block_m.end()
    if boot_end < len(merged_text) and merged_text[boot_end] == "\n":
        boot_end += 1
    return merged_text[: marker.start()], merged_text[marker.start() : boot_end], merged_text[boot_end:]


def _collect_entry_points(scenario_after: str) -> set[str]:
    """Roots for tree-shake: direct ``cmo.*`` use and ``local alias = cmo.fn`` aliases."""
    roots: set[str] = set()
    for m in CMO_ENTRY.finditer(scenario_after):
        name = m.group(1)
        if name != "state":
            roots.add(name)
    aliases: dict[str, str] = {}
    for m in ALIAS_ENTRY.finditer(scenario_after):
        aliases[m.group(1)] = m.group(2)
        roots.add(m.group(2))
    for alias, func in aliases.items():
        if re.search(rf"\b{re.escape(alias)}\s*\(", scenario_after):
            roots.add(func)
    return roots


def _transitive_needed(roots: set[str], functions: dict[str, str]) -> set[str]:
    needed = set(roots)
    queue = list(roots)
    while queue:
        name = queue.pop()
        body = functions.get(name)
        if not body:
            continue
        for callee in M_MEMBER.findall(body):
            if callee == "state" or callee in needed:
                continue
            if callee in functions:
                needed.add(callee)
                queue.append(callee)
    return needed


def _needed_constants(needed_functions: set[str], functions: dict[str, str]) -> set[str]:
    consts: set[str] = set()
    for name in needed_functions:
        body = functions.get(name, "")
        for m in CONST_M.finditer(body):
            consts.add(m.group(1))
    return consts


def _parse_bootstrap_segments(bootstrap_block: str) -> tuple[str, str, list[dict]]:
    """Return (marker, head, segments) from an inlined bootstrap block."""
    marker_m = INLINED_MARKER.match(bootstrap_block)
    if not marker_m:
        raise ValueError("bootstrap block missing inlined marker")
    marker = marker_m.group(0)
    lines = bootstrap_block[marker_m.end() :].splitlines(keepends=True)

    segments: list[dict] = []
    preamble: list[str] = []
    pending_comments: list[str] = []
    i = 0

    def take_comments() -> str:
        text = "".join(pending_comments)
        pending_comments.clear()
        return text

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        kind = _top_level_kind(line)

        if kind is None:
            if not segments:
                preamble.append(line)
            elif stripped.startswith("--") or stripped == "":
                pending_comments.append(line)
            else:
                pending_comments.append(line)
            i += 1
            continue

        if kind == "function":
            name_m = re.match(r"^function M\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
            j = i + 1
            while j < len(lines) and _top_level_kind(lines[j]) is None:
                j += 1
            segments.append(
                {
                    "type": "function",
                    "name": name_m.group(1),
                    "leading": take_comments(),
                    "text": "".join(lines[i:j]),
                }
            )
            i = j
            continue

        if kind == "const":
            name_m = CONST_M.match(line)
            j = i + 1
            while j < len(lines) and _top_level_kind(lines[j]) is None:
                j += 1
            segments.append(
                {
                    "type": "const",
                    "name": name_m.group(1),
                    "leading": take_comments(),
                    "text": "".join(lines[i:j]),
                }
            )
            i = j
            continue

        if kind == "alias":
            name_m = ALIAS_M.match(line)
            segments.append(
                {
                    "type": "alias",
                    "name": name_m.group(1),
                    "target": name_m.group(2),
                    "leading": take_comments(),
                    "text": line if line.endswith("\n") else line + "\n",
                }
            )
            i += 1
            continue

        if kind == "footer":
            segments.append(
                {
                    "type": "footer",
                    "leading": take_comments(),
                    "text": line if line.endswith("\n") else line + "\n",
                }
            )
            break

    head = "".join(preamble)
    return marker, head, segments


def tree_shake_bootstrap(merged_text: str) -> tuple[str, dict]:
    """Remove unused ``M.*`` helpers from the inlined bootstrap block."""
    split = _split_embedded(merged_text)
    if split is None:
        return merged_text, {"skipped": True, "reason": "no inlined bootstrap block"}

    before, bootstrap_block, scenario_after = split
    original_lines = len(bootstrap_block.splitlines())

    marker, head, segments = _parse_bootstrap_segments(bootstrap_block)
    functions = {
        seg["name"]: seg["text"] for seg in segments if seg["type"] == "function"
    }
    total_functions = len(functions)

    roots = _collect_entry_points(scenario_after)
    needed_functions = _transitive_needed(roots, functions)
    needed_constants = _needed_constants(needed_functions, functions)
    needed_aliases = {
        seg["name"]
        for seg in segments
        if seg["type"] == "alias" and seg["target"] in needed_functions
    }

    parts = [marker, head]
    for seg in segments:
        if seg["type"] == "function":
            if seg["name"] in needed_functions:
                parts.append(seg.get("leading", "") + seg["text"])
        elif seg["type"] == "const":
            if seg["name"] in needed_constants:
                parts.append(seg.get("leading", "") + seg["text"])
        elif seg["type"] == "alias":
            if seg["name"] in needed_aliases:
                parts.append(seg.get("leading", "") + seg["text"])
        elif seg["type"] == "footer":
            parts.append(seg.get("leading", "") + seg["text"])

    if not parts[-1].endswith("\n"):
        parts[-1] += "\n"

    new_bootstrap = "".join(parts)
    new_lines = len(new_bootstrap.splitlines())
    removed = total_functions - len(needed_functions)

    stats = {
        "skipped": False,
        "roots": sorted(roots),
        "kept_functions": len(needed_functions),
        "removed_functions": removed,
        "total_functions": total_functions,
        "kept_constants": len(needed_constants),
        "lines_before": original_lines,
        "lines_after": new_lines,
        "lines_saved": original_lines - new_lines,
    }
    return before + new_bootstrap + scenario_after, stats


def embed_bootstrap(
    scenario_text,
    series="DB3K",
    version="515",
    tree_shake=True,
    src_path: Path | str | None = None,
):
    scenario_text = _prepare_scenario_source(scenario_text)
    preamble, scenario_code = _split_scenario_for_embed(scenario_text)

    bootstrap = bootstrap_lua_for_inline(series, version)
    from datetime import datetime, timezone

    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_rel = repo_relative(src_path) if src_path else "generated/src/<name>_src.lua"
    marker = (
        f"-- [inlined scenario_bootstrap.lua @ {built_at} UTC — "
        "edit scripts/scenario_bootstrap.lua; "
        f"source: {src_rel}; "
        f"re-run: python scripts/embed_bootstrap.py {src_rel}]\n"
    )
    block = marker + bootstrap + "\n"
    merged = block + preamble + scenario_code
    shake_stats = {"skipped": True, "reason": "tree-shake disabled"}
    if tree_shake:
        merged, shake_stats = tree_shake_bootstrap(merged)
    return merged, shake_stats


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Build CMO load file from a *_src.lua source "
            "(inline bootstrap + tree-shake into generated/<name>.lua)."
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
        help="Skip tree-shaking unused bootstrap helpers after embed",
    )
    parser.add_argument(
        "--extract-source",
        metavar="EMBEDDED",
        help=(
            "Extract generated/<name>_src.lua from an embedded generated/<name>.lua "
            "(migration helper; does not run embed)"
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
    if input_path is None:
        raw = Path(args.scenario)
        suggested = source_scenario_path(raw if raw.suffix else GENERATED_DIR / raw.name)
        print(f"ERROR: source not found: {args.scenario}", file=sys.stderr)
        print(
            f"  Expected: {repo_relative(suggested)} (*_src.lua under generated/src/)",
            file=sys.stderr,
        )
        if raw.is_file() and not is_source_scenario_path(raw):
            print(
                f"  To extract from embedded: "
                f"python scripts/embed_bootstrap.py --extract-source {raw}",
                file=sys.stderr,
            )
        elif raw.is_file():
            print(
                f"  Relocate: python scripts/embed_bootstrap.py --relocate-sources",
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
            "ERROR: source has no cmo.* calls — bootstrap embed is not needed.\n"
            "  Standalone scenarios: edit and load generated/<name>.lua directly (no _src).",
            file=sys.stderr,
        )
        return 1

    series, version = _parse_db_series_version(scenario_text, args.series, args.version)
    merged, shake_stats = embed_bootstrap(
        scenario_text,
        series,
        version,
        tree_shake=not args.no_shake,
        src_path=input_path,
    )
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
    if INLINED_MARKER.search(text) is None and "cmo." not in text:
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
    """Move legacy ``generated/*_src.lua`` into ``generated/src/``."""
    ensure_source_dir()
    rc = 0
    for legacy in sorted(GENERATED_DIR.glob("*_src.lua")):
        dest = SOURCE_DIR / legacy.name
        print(f"=== {legacy.name} -> {repo_relative(dest)} ===")
        text = legacy.read_text(encoding="utf-8", errors="ignore")
        source = apply_source_header(text, dest)
        dest.write_text(source, encoding="utf-8")
        legacy.unlink()
        embed_argv = [str(dest)]
        if _main_embed_only(embed_argv) != 0:
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
        embed_argv = [str(src_path)]
        if args.series:
            embed_argv.extend(["--series", args.series])
        if args.version:
            embed_argv.extend(["--version", args.version])
        if args.no_shake:
            embed_argv.append("--no-shake")
        if _main_embed_only(embed_argv) != 0:
            rc = 1
    return rc


def _main_embed_only(argv: list[str]) -> int:
    """Run embed for one ``generated/src/*_src.lua`` (used by migrate/relocate)."""
    input_path = resolve_source_input(argv[0])
    if input_path is None:
        print(f"ERROR: source not found: {argv[0]}", file=sys.stderr)
        return 1
    out_path = embedded_scenario_path(input_path)
    scenario_text = input_path.read_text(encoding="utf-8", errors="ignore")
    series, version = _parse_db_series_version(scenario_text, None, None)
    for i, arg in enumerate(argv):
        if arg == "--series" and i + 1 < len(argv):
            series = argv[i + 1]
        if arg == "--version" and i + 1 < len(argv):
            version = argv[i + 1]
    tree_shake = "--no-shake" not in argv
    merged, shake_stats = embed_bootstrap(
        scenario_text,
        series,
        version,
        tree_shake=tree_shake,
        src_path=input_path,
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
