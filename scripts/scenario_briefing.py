"""Render player briefing for CMO (plain text + HTML; not Markdown)."""

from __future__ import annotations

import html
import re
from pathlib import Path

from scenario_schema import BriefingSpec, MetaSpec, ScenarioSpec

_YYYYMMDD_SLASH = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")


def meta_date_to_ddmmyyyy(date: str) -> str:
    m = _YYYYMMDD_SLASH.match(date)
    if not m:
        raise ValueError(f"meta.date must be YYYY/MM/DD for briefing, got '{date}'")
    y, mo, d = m.groups()
    return f"{d}{mo}{y}"


def _briefing_stem(meta: MetaSpec) -> str:
    return Path(meta.output_lua).stem


def default_briefing_txt_path(meta: MetaSpec) -> Path:
    return Path(meta.output_lua).with_name(f"{_briefing_stem(meta)}_briefing.txt")


def default_briefing_html_path(meta: MetaSpec) -> Path:
    return Path(meta.output_lua).with_name(f"{_briefing_stem(meta)}_briefing.html")


def default_briefing_loaddoc_path(meta: MetaSpec) -> Path:
    return Path(meta.output_lua).with_name(f"{_briefing_stem(meta)}_briefing_loaddoc.txt")


def _title(spec: ScenarioSpec) -> str:
    b = spec.briefing
    return b.title or spec.meta.name.replace("_", " ").title()


def _esc(text: str) -> str:
    return html.escape(text.strip())


def render_briefing_plain(spec: ScenarioSpec) -> str:
    """Plain text for ScenEdit → Edit Briefing (no Markdown — CMO shows it literally)."""
    b = spec.briefing
    date_str = meta_date_to_ddmmyyyy(spec.meta.date)
    title = _title(spec)

    def p(body: str) -> str:
        return body.strip()

    return f"""{title.upper()}
Date: {date_str} | Side: {b.player_side} | Complexity: {b.complexity}

I. SITUATION
{p(b.situation)}

II. INTEL
Friendly OOB: {p(b.friendly_oob)}
Enemy Threat: {p(b.enemy_threat)}
Environment: {p(b.environment)}

III. MISSION
{p(b.mission)}

IV. EXECUTION & ROE
ROE: {p(b.roe)}
Special Instructions: {p(b.special_instructions)}
"""


def render_briefing_html(spec: ScenarioSpec) -> str:
    """HTML for LOADDOC side briefings and ScenEdit_SpecialMessage (CMO-native rich text)."""
    b = spec.briefing
    date_str = meta_date_to_ddmmyyyy(spec.meta.date)
    title = _esc(_title(spec))

    def para(body: str) -> str:
        return f"<p>{_esc(body).replace(chr(10), '<br/>')}</p>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>{title}</title></head><body>
<h2>{title}</h2>
<p><b>Date:</b> {date_str} | <b>Side:</b> {_esc(b.player_side)} | <b>Complexity:</b> {_esc(b.complexity)}</p>
<h3>I. SITUATION</h3>
{para(b.situation)}
<h3>II. INTEL</h3>
<ul>
<li><b>Friendly OOB:</b> {_esc(b.friendly_oob).replace(chr(10), '<br/>')}</li>
<li><b>Enemy Threat:</b> {_esc(b.enemy_threat).replace(chr(10), '<br/>')}</li>
<li><b>Environment:</b> {_esc(b.environment).replace(chr(10), '<br/>')}</li>
</ul>
<h3>III. MISSION</h3>
<p><b>{_esc(b.mission).replace(chr(10), '<br/>')}</b></p>
<h3>IV. EXECUTION &amp; ROE</h3>
<ul>
<li><b>ROE:</b> {_esc(b.roe).replace(chr(10), '<br/>')}</li>
<li><b>Special Instructions:</b> {_esc(b.special_instructions).replace(chr(10), '<br/>')}</li>
</ul>
</body></html>
"""


def render_briefing_loaddoc(meta: MetaSpec) -> str:
    """Single line to paste into ScenEdit side briefing when the .html sits beside the .scen."""
    name = default_briefing_html_path(meta).name
    return f"[LOADDOC]{name}[/LOADDOC]"


def append_briefing_popup(lua_text: str, spec: ScenarioSpec) -> str:
    """Append ScenEdit_SpecialMessage HTML popup at scenario init (works without .scen briefing field)."""
    if not spec.briefing.show_popup:
        return lua_text
    side = spec.briefing.player_side.replace("'", "\\'")
    body = render_briefing_html(spec)
    return (
        f"{lua_text.rstrip()}\n\n"
        "-- Player briefing popup (HTML; CMO does not render Markdown in the editor)\n"
        f"ScenEdit_SpecialMessage('{side}', [=[{body}]=])\n"
    )


# Back-compat alias
def default_briefing_path(meta: MetaSpec) -> Path:
    return default_briefing_txt_path(meta)


def render_briefing(spec: ScenarioSpec) -> str:
    return render_briefing_plain(spec)
