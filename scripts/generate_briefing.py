"""Player briefings for the generate domain: *_briefing.{txt,html} → ScenEdit_SpecialMessage."""

from __future__ import annotations

import html
import re
from pathlib import Path

SIDE_ADD = re.compile(
    r"ScenEdit_AddSide\s*\(\s*\{[^}]*\bside\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
SIDE_MARKER = re.compile(r"^@side\s+(.+)\s*$", re.IGNORECASE | re.MULTILINE)
SECTION_HEADING = re.compile(r"^([IVXLC]+)\.\s+(.+)$")
LABELED_LINE = re.compile(
    r"^(Friendly OOB|Enemy Threat|Environment|ROE|Special Instructions):\s*(.*)$",
    re.IGNORECASE,
)
META_LINE = re.compile(r"^Date:\s*.+\|\s*Side:\s*.+", re.IGNORECASE)
INLINE_BRIEFING_START = re.compile(
    r"\n-- =+\s*\n-- (?:Speler-briefings?|Player briefings)",
    re.IGNORECASE,
)


NON_PLAYER_SIDES = frozenset({"Civilian Air Traffic"})


def scenario_stem(lua_path: Path) -> str:
    stem = lua_path.stem
    if stem.endswith("_src"):
        stem = stem[: -len("_src")]
    return stem


from generate_constants import SOURCE_DIR


def briefing_paths_for_stem(stem: str) -> tuple[Path, Path]:
    txt = SOURCE_DIR / f"{stem}_briefing.txt"
    return txt, txt.with_suffix(".html")


def briefing_txt_path(source_lua: Path) -> Path:
    """``foo_src.lua`` → ``foo_briefing.txt`` in generated/src/."""
    return briefing_paths_for_stem(scenario_stem(source_lua))[0]


def briefing_html_path(source_lua: Path) -> Path:
    """``foo_src.lua`` → ``foo_briefing.html`` in generated/src/."""
    return briefing_paths_for_stem(scenario_stem(source_lua))[1]


def detect_sides_from_lua(lua: str) -> list[str]:
    seen: list[str] = []
    for m in SIDE_ADD.finditer(lua):
        name = m.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def detect_playable_sides_from_lua(lua: str) -> list[str]:
    return [s for s in detect_sides_from_lua(lua) if s not in NON_PLAYER_SIDES]


def scenario_title_from_lua(lua: str, fallback: str) -> str:
    for line in lua.splitlines():
        s = line.strip()
        if s.startswith("-- CMO Scenario:"):
            return s.split(":", 1)[1].strip()
    return fallback


def _strip_comment_lines(text: str, html_file: bool) -> str:
    if html_file:
        kept: list[str] = []
        for ln in text.splitlines():
            s = ln.strip()
            if s.startswith("<!--") and s.endswith("-->"):
                continue
            kept.append(ln)
        return "\n".join(kept).strip()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    return "\n".join(lines).strip()


def parse_briefing_file(text: str, *, html_file: bool = False) -> list[tuple[str, str]]:
    """Return [(side_name, body), ...] from a txt or html briefing file."""
    text = _strip_comment_lines(text, html_file)
    if not text:
        return []
    if not SIDE_MARKER.search(text):
        raise ValueError("Briefing file must contain at least one '@side Side Name' line")
    parts = SIDE_MARKER.split(text)
    if len(parts) < 3:
        return []
    out: list[tuple[str, str]] = []
    i = 1
    while i + 1 < len(parts):
        side = parts[i].strip()
        body = parts[i + 1].strip()
        if side and body:
            out.append((side, body))
        i += 2
    return out


def parse_briefing_txt(text: str) -> list[tuple[str, str]]:
    return parse_briefing_file(text, html_file=False)


def parse_briefing_html(text: str) -> list[tuple[str, str]]:
    return parse_briefing_file(text, html_file=True)


def _lua_long_string(content: str) -> str:
    level = 0
    while True:
        open_delim = "[" + "=" * level + "["
        close_delim = "]" + "=" * level + "]"
        if close_delim not in content:
            return f"{open_delim}{content}{close_delim}"
        level += 1


def _text_block_to_html(body: str, doc_title: str) -> str:
    """Plain-text briefing -> minimal HTML (CMO editor; no Markdown)."""
    chunks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    labeled: list[str] | None = None

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = "\n".join(paragraph).strip()
        if text:
            escaped = html.escape(text).replace("\n", "<br/>\n")
            chunks.append(f"<p>{escaped}</p>")
        paragraph.clear()

    def flush_list() -> None:
        if not list_items:
            return
        items = "".join(f"<li>{html.escape(t)}</li>\n" for t in list_items)
        chunks.append(f"<ul>\n{items}</ul>")
        list_items.clear()

    def flush_labeled() -> None:
        nonlocal labeled
        if not labeled:
            return
        label, text = labeled[0], labeled[1].strip()
        if text:
            chunks.append(f"<p><b>{html.escape(label)}:</b> {html.escape(text)}</p>")
        labeled = None

    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            flush_labeled()
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            flush_labeled()
            list_items.append(stripped[2:].strip())
            continue
        flush_list()
        sec = SECTION_HEADING.match(stripped)
        if sec:
            flush_paragraph()
            flush_labeled()
            chunks.append(f"<h3>{html.escape(sec.group(1))}. {html.escape(sec.group(2))}</h3>")
            continue
        lab = LABELED_LINE.match(stripped)
        if lab:
            flush_paragraph()
            flush_labeled()
            labeled = [lab.group(1), lab.group(2)]
            continue
        if labeled is not None:
            labeled[1] = f"{labeled[1]} {stripped}".strip()
            continue
        paragraph.append(stripped)
    flush_paragraph()
    flush_list()
    flush_labeled()

    title_esc = html.escape(doc_title)
    inner = "\n".join(chunks)
    return (
        f"<!DOCTYPE html>\n"
        f'<html><head><meta charset="utf-8"/><title>{title_esc}</title></head><body>\n'
        f"{inner}\n"
        f"</body></html>"
    )


def briefing_body_to_html(side: str, body: str) -> str:
    lines = [ln for ln in body.splitlines()]
    non_empty = [ln.strip() for ln in lines if ln.strip()]
    if not non_empty:
        return _text_block_to_html(body, side)

    title = non_empty[0]
    idx = 1
    meta_html = ""
    if idx < len(non_empty) and META_LINE.match(non_empty[idx]):
        meta_html = f"<p>{html.escape(non_empty[idx])}</p>\n"
        idx += 1

    rest_lines: list[str] = []
    seen = 0
    for ln in lines:
        if not ln.strip():
            rest_lines.append(ln)
            continue
        if seen < idx:
            seen += 1
            continue
        rest_lines.append(ln)
    rest = "\n".join(rest_lines).strip()

    h2 = html.escape(title)
    inner = _text_block_to_html(rest, title)
    return inner.replace(
        "<body>\n",
        f"<body>\n<h2>{h2}</h2>\n{meta_html}",
        1,
    )


def txt_entries_to_html(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(side, briefing_body_to_html(side, body)) for side, body in entries]


def write_briefing_html_file(path: Path, html_entries: list[tuple[str, str]]) -> None:
    parts = [
        "<!-- Player briefing — edit this file or the matching *_briefing.txt -->",
        "<!-- Embed uses the newer file; regenerates the other on sync. -->",
        "<!-- One @side block per side; body = full HTML for ScenEdit_SpecialMessage. -->",
        "",
    ]
    for side, doc in html_entries:
        parts.extend([f"@side {side}", doc.strip(), ""])
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def sync_briefing_files(
    txt_path: Path,
    html_path: Path,
) -> tuple[list[tuple[str, str]], str]:
    """
    Keep txt/html in sync. Return (html_docs_for_inject, sync_note).

    html_docs: [(side, full_html_document), ...]
    sync_note: 'txt', 'html', 'txt+html_written', or 'none'
    """
    txt_exists = txt_path.is_file()
    html_exists = html_path.is_file()
    if not txt_exists and not html_exists:
        return [], "none"

    if txt_exists and html_exists:
        txt_mtime = txt_path.stat().st_mtime
        html_mtime = html_path.stat().st_mtime
        if txt_mtime >= html_mtime:
            txt_entries = parse_briefing_txt(txt_path.read_text(encoding="utf-8", errors="ignore"))
            html_entries = txt_entries_to_html(txt_entries)
            write_briefing_html_file(html_path, html_entries)
            return html_entries, "txt+html_written"
        html_entries = parse_briefing_html(html_path.read_text(encoding="utf-8", errors="ignore"))
        return html_entries, "html"

    if txt_exists:
        txt_entries = parse_briefing_txt(txt_path.read_text(encoding="utf-8", errors="ignore"))
        html_entries = txt_entries_to_html(txt_entries)
        write_briefing_html_file(html_path, html_entries)
        return html_entries, "txt+html_written"

    html_entries = parse_briefing_html(html_path.read_text(encoding="utf-8", errors="ignore"))
    return html_entries, "html"


def render_briefing_lua(html_entries: list[tuple[str, str]]) -> str:
    if not html_entries:
        return ""
    lines = [
        "",
        "-- =============================================================================",
        "-- Player briefings (from generated/src/*_briefing.txt + *_briefing.html)",
        "-- =============================================================================",
    ]
    for side, html_doc in html_entries:
        side_lit = side.replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"ScenEdit_SpecialMessage('{side_lit}', {_lua_long_string(html_doc)})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def strip_inline_briefings(scenario_lua: str) -> str:
    """Remove legacy in-src ScenEdit_SpecialMessage briefing blocks."""
    m = INLINE_BRIEFING_START.search(scenario_lua)
    if m:
        return scenario_lua[: m.start()].rstrip() + "\n"
    return scenario_lua


def _stub_body_text(scenario_title: str, side: str) -> str:
    short = scenario_title.upper()
    return "\n".join(
        [
            short,
            f"Date: TBD | Side: {side} | Complexity: Medium",
            "",
            "I. SITUATION",
            "(TBD)",
            "",
            "II. INTEL",
            "Friendly OOB: (TBD)",
            "Enemy Threat: (TBD)",
            "Environment: (TBD)",
            "",
            "III. MISSION",
            "(TBD)",
            "",
            "IV. EXECUTION & ROE",
            "ROE: (TBD)",
            "Special Instructions: (TBD)",
        ]
    )


def write_briefing_stub(txt_path: Path, sides: list[str], scenario_title: str | None = None) -> None:
    title = scenario_title or txt_path.stem.replace("_briefing", "").replace("_", " ").title()
    parts = [
        "# Player briefing (English). Edit txt or html; generate_scenario injects ScenEdit_SpecialMessage.",
        "# Multi-side: one @side block per playable side. Format: TITLE / Date|Side|Complexity / I-IV sections.",
        "",
    ]
    for side in sides:
        parts.extend([f"@side {side}", _stub_body_text(title, side), ""])
    txt_path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def write_briefing_pair(
    txt_path: Path,
    html_path: Path,
    sides: list[str],
    scenario_title: str | None = None,
) -> None:
    """Create matching txt + html briefing stubs."""
    write_briefing_stub(txt_path, sides, scenario_title)
    txt_entries = parse_briefing_txt(txt_path.read_text(encoding="utf-8"))
    write_briefing_html_file(html_path, txt_entries_to_html(txt_entries))


def append_briefings(
    source_lua: Path,
    scenario_lua: str,
    create_stub: bool = True,
) -> tuple[str, bool, str]:
    """Return (scenario_lua + briefing calls, stub_was_created, sync_note)."""
    scenario_lua = strip_inline_briefings(scenario_lua)
    txt_path = briefing_txt_path(source_lua)
    html_path = briefing_html_path(source_lua)
    stub_created = False

    if not txt_path.is_file() and not html_path.is_file():
        if not create_stub:
            return scenario_lua, False, "none"
        sides = detect_playable_sides_from_lua(scenario_lua)
        if not sides:
            sides = detect_sides_from_lua(scenario_lua) or ["SIDE_NAME"]
        title = scenario_title_from_lua(scenario_lua, scenario_stem(source_lua).replace("_", " ").title())
        write_briefing_pair(txt_path, html_path, sides, title)
        stub_created = True

    try:
        html_entries, sync_note = sync_briefing_files(txt_path, html_path)
    except ValueError as exc:
        raise ValueError(f"{txt_path.name} / {html_path.name}: {exc}") from exc

    if not html_entries:
        return scenario_lua, stub_created, sync_note
    return scenario_lua.rstrip() + "\n" + render_briefing_lua(html_entries), stub_created, sync_note


def inject_briefings_into_load(
    load_path: Path,
    create_stub: bool = True,
) -> tuple[bool, str]:
    """Inject player briefings into a standalone ``generated/<name>.lua`` load file."""
    load_path = load_path.resolve()
    lua_text = load_path.read_text(encoding="utf-8", errors="ignore")
    stem = scenario_stem(load_path)
    txt_path, html_path = briefing_paths_for_stem(stem)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    stub_created = False

    if not txt_path.is_file() and not html_path.is_file():
        if not create_stub:
            return False, "none"
        sides = detect_playable_sides_from_lua(lua_text) or detect_sides_from_lua(lua_text) or ["SIDE_NAME"]
        title = scenario_title_from_lua(lua_text, stem.replace("_", " ").title())
        write_briefing_pair(txt_path, html_path, sides, title)
        stub_created = True

    html_entries, sync_note = sync_briefing_files(txt_path, html_path)
    merged = strip_inline_briefings(lua_text)
    if html_entries:
        merged = merged.rstrip() + "\n" + render_briefing_lua(html_entries)
    load_path.write_text(merged, encoding="utf-8")
    return stub_created, sync_note
