"""Load scenario Lua and bootstrap text for preflight."""

import math
import re
from pathlib import Path

from preflight_constants import *

def load_scenario_lua_content(scenario_path):
    """Scenario file plus scenario_bootstrap.lua when the scenario dofile's it."""
    path = Path(scenario_path)
    content = path.read_text(encoding="utf-8", errors="ignore")
    bootstrap = _read_bootstrap_lua_for_preflight(content)
    if bootstrap:
        content = content + "\n\n-- [preflight: scenario_bootstrap.lua]\n" + bootstrap
    return content

def _strip_lua_comment_lines(text):
    """Blank out full-line Lua comments (keeps line numbers stable).

    The bootstrap header documents usage with sample annotations and locals
    (e.g. ``-- @strike_package ... time=HH:MM:SS`` and
    ``--   local strike_package_tot = '06:30:00'``). When the bootstrap is
    appended for preflight, those comment lines would otherwise be parsed as if
    they were real scenario metadata, producing phantom strike/SEAD errors in
    non-strike scenarios. Stripping comment-only lines from the appended
    bootstrap leaves all helper *code* intact while removing this noise. The
    scenario file itself is never stripped, so its real annotations still count.
    """
    out_lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("--"):
            out_lines.append("")
        else:
            out_lines.append(line)
    return "\n".join(out_lines)

def _read_bootstrap_lua_for_preflight(scenario_content):
    if "scenario_bootstrap" not in scenario_content:
        return ""
    repo_m = re.search(r"CMO_SCENARIO_REPO\s*=\s*\[\[(.*?)\]\]", scenario_content, re.IGNORECASE)
    if repo_m:
        boot = Path(repo_m.group(1).strip()) / "scripts" / "scenario_bootstrap.lua"
        if boot.is_file():
            return _strip_lua_comment_lines(boot.read_text(encoding="utf-8", errors="ignore"))
    default_boot = Path(__file__).resolve().parent / "scenario_bootstrap.lua"
    if default_boot.is_file():
        return _strip_lua_comment_lines(default_boot.read_text(encoding="utf-8", errors="ignore"))
    return ""

def _scenario_lua_body(content):
    """Scenario script only (exclude appended bootstrap for static side analysis)."""
    marker = "-- [preflight: scenario_bootstrap.lua]"
    if marker in content:
        return content.split(marker, 1)[0]
    return content

def _line_number_at(content, index):
    return content[:index].count("\n") + 1

__all__ = ['_line_number_at', '_read_bootstrap_lua_for_preflight', '_scenario_lua_body', '_strip_lua_comment_lines', 'load_scenario_lua_content']
