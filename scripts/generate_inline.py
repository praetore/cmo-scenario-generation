"""Generate domain — inline scenario_bootstrap.lua and tree-shake unused helpers."""

from __future__ import annotations

import re

from generate_constants import (
    ALIAS_ENTRY,
    ALIAS_M,
    BOOTSTRAP_PATH,
    CMO_ENTRY,
    CONST_M,
    INLINED_MARKER,
    M_MEMBER,
)


def parse_db_series_version(scenario_text, series_arg, version_arg):
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


def strip_bootstrap_doc_preamble(lua: str) -> str:
    m = re.search(r"^local M\s*=\s*\{\}\s*$", lua, re.MULTILINE)
    if not m:
        return lua
    return lua[m.start() :]


def bootstrap_lua_for_inline(series="DB3K", version="515"):
    text = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    text = re.sub(r"\nreturn\s+M\s*\n?\s*$", "\n", text.rstrip()) + "\n"
    from db_nuclear import inject_nuclear_dbid_tables

    text = inject_nuclear_dbid_tables(text, series, version)
    return strip_bootstrap_doc_preamble(text)


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
