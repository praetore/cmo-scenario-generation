"""Generate domain — source/load text transforms, headers, strip inlined bootstrap."""

from __future__ import annotations

import re
from pathlib import Path

from generate_constants import (
    AUTHORING_COMMENT,
    DOFILE_LOADER,
    INLINED_MARKER,
    SINGLE_INLINED,
    TOOLING_IN_COMMENT,
    embedded_scenario_path,
    relocate_legacy_source,
    repo_relative,
)


def find_insertion_index(lines):
    """Legacy helper — bootstrap is placed before all scenario code."""
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
    if _is_authoring_comment_line(line):
        return None
    if TOOLING_IN_COMMENT.match(line):
        return None
    return line


def _split_scenario_for_embed(text: str) -> tuple[str, str]:
    """Split source into (load-file preamble comments, scenario Lua after header block)."""
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


def _unwrap_block_comments(text: str) -> str:
    """Convert --[[ ... ]] blocks to line comments (WARNO-style header)."""

    def repl(match: re.Match[str]) -> str:
        lines: list[str] = []
        for raw in match.group(1).splitlines():
            stripped = raw.strip()
            if not stripped:
                lines.append("--")
                continue
            if stripped.startswith("--"):
                lines.append(stripped)
            else:
                lines.append("-- " + stripped)
        return "\n".join(lines) + "\n"

    return re.sub(r"--\[\[(.*?)\]\]", repl, text, flags=re.DOTALL)


def _is_load_header_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("--"):
        return False
    if AUTHORING_COMMENT.match(stripped) or TOOLING_IN_COMMENT.match(stripped):
        return True
    if re.match(
        r"^--\s*(?:Source:|Bootstrap:|Preflight:|\s*\(DB IDs/)",
        stripped,
        re.IGNORECASE,
    ):
        return True
    return False


def prepare_load_header_and_annotations(preamble: str) -> tuple[str, str]:
    """Player-facing load-file header (OOB only) + preflight @ annotations before scenario code."""
    text = _unwrap_block_comments(preamble)
    header_lines: list[str] = []
    ann_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if re.match(r"^--\s*@", stripped):
            ann_lines.append(line)
            continue
        if _is_load_header_noise(stripped):
            continue
        header_lines.append(line)
    header = "".join(header_lines).rstrip()
    if header:
        header += "\n\n"
    annotations = "".join(ann_lines)
    if annotations and not annotations.endswith("\n\n"):
        annotations = annotations.rstrip() + "\n\n"
    return header, annotations


def _bootstrap_signature_index(text: str) -> int | None:
    m = re.search(
        r"^(-- \[inlined scenario_bootstrap|^function M\.|^local M = \{\})",
        text,
        re.MULTILINE,
    )
    return m.start() if m else None


def _scenario_body_start(pattern_text: str) -> re.Match[str] | None:
    return re.search(
        r"^\s*(?:if\s+not\s+cmo\.assert_db_series|ScenEdit_AddSide|ScenEdit_SetTime)",
        pattern_text,
        re.MULTILINE,
    )


def _trim_to_scenario_header(text: str) -> str:
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
    if src_path is not None:
        src_disp = repo_relative(src_path)
        embed_disp = repo_relative(embedded_scenario_path(src_path))
    else:
        name = src_basename or "<name>_src.lua"
        src_disp = f"generated/src/{name}"
        embed_disp = f"generated/{name.replace('_src.lua', '.lua')}"
    text = re.sub(
        r"--\s*CMO import:.*\n(?:--\s*→[^\n]*_import\.lua[^\n]*\n)?",
        f"-- CMO load: {embed_disp} (run: python scripts/generate_scenario.py {src_disp})\n",
        text,
        count=1,
    )
    text = re.sub(
        r"-- CMO: python scripts/(?:generate_scenario|embed_bootstrap)\.py[^\n]*\n",
        f"-- CMO load: {embed_disp} (run: python scripts/generate_scenario.py {src_disp})\n",
        text,
        count=1,
    )
    text = re.sub(
        r"-- CMO load: generated/[^\n]*\n",
        f"-- CMO load: {embed_disp} (run: python scripts/generate_scenario.py {src_disp})\n",
        text,
        count=1,
    )
    text = re.sub(r"[^\n]*_import\.lua[^\n]*\n", "", text)
    text = re.sub(r"db_search\.py --validate-scenario", "validate_scenario.py", text)
    text = re.sub(
        r"python scripts/db_search\.py --validate-scenario",
        "python scripts/validate_scenario.py",
        text,
    )
    return text


def _strip_inlined_blocks(text: str) -> str:
    while SINGLE_INLINED.search(text):
        text = SINGLE_INLINED.sub("", text, count=1)
    return text


def _strip_pre_marker_orphan(text: str) -> str:
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
    while True:
        marker = INLINED_MARKER.search(text)
        if not marker:
            return text
        tail = text[marker.start() :]
        if re.match(
            r"^(?:-- \[inlined scenario_bootstrap\.lua[^\n]*\]\n)?local M\s*=\s*\{.*?^cmo\s*=\s*M\s*\n",
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
    if INLINED_MARKER.search(text) or re.search(r"^local M\s*=\s*\{", text, re.MULTILINE):
        return text
    if not re.search(r"^function M\.", text, re.MULTILINE):
        return text
    scenario_m = _scenario_body_start(text)
    if not scenario_m:
        return text
    header = _trim_to_scenario_header(text[: scenario_m.start()])
    return header + text[scenario_m.start() :]


def prepare_scenario_source(text: str) -> str:
    text = DOFILE_LOADER.sub("", text)
    text = _strip_inlined_blocks(text)
    text = _strip_pre_marker_orphan(text)
    text = _strip_incomplete_inlined(text)
    text = _strip_orphan_bootstrap(text)
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
        f"(python scripts/generate_scenario.py {src_disp})\n"
    )
    text = prepare_scenario_source(text)
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
    text = prepare_scenario_source(scenario_text)
    if src_path is not None:
        text = apply_source_header(text, src_path)
    return text
