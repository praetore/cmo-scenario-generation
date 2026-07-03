"""Luacheck Play-time event scripts materialized from scenario_bootstrap.lua.

Luacheck on scenario *_src.lua does not parse Lua inside string literals (ScriptText
fragments built by M.build_*_script). This module materializes representative event
scripts and runs luacheck on them during preflight.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP_PATH = REPO_ROOT / "scripts" / "scenario_bootstrap.lua"

_SAMPLE_GUID = "00000000-0000-0000-0000-000000000001"
_SAMPLE_SIDE = "United States"
_SAMPLE_MISSION = "Carrier Air Strike"


def _parse_lua_string_table(content: str, table_name: str) -> list[str]:
    m = re.search(
        rf"M\.{re.escape(table_name)}\s*=\s*\{{(.*?)\n\}}",
        content,
        re.DOTALL,
    )
    if not m:
        return []
    return re.findall(r"'([^']*)'", m.group(1))


def _q_lua_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def materialize_strike_ship_weapon_policy_script(bootstrap_text: str) -> str:
    """Mirror M.build_strike_ship_weapon_policy_script with sample unit/side."""
    land_types = _parse_lua_string_table(bootstrap_text, "LAND_STRIKE_WRA_TARGET_TYPES")
    surface_types = _parse_lua_string_table(
        bootstrap_text, "SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES"
    )
    side = _q_lua_str(_SAMPLE_SIDE)
    guid = _SAMPLE_GUID
    land_list = ", ".join(f"'{_q_lua_str(t)}'" for t in land_types)
    surface_list = ", ".join(f"'{_q_lua_str(t)}'" for t in surface_types)
    lines = [
        "do",
        f"  local u = ScenEdit_GetUnit({{guid='{guid}'}})",
        "  if u and u.mounts then",
        '  local wra_land = { "none", "none", "none", "none" }',
        '  local wra_surface = { "inherit", "inherit", "none", "max" }',
        f"  local land_types = {{ {land_list} }}",
        f"  local surface_types = {{ {surface_list} }}",
        f"  ScenEdit_SetDoctrine({{side='{side}', guid='{guid}'}}, {{weapon_state_planned='ShotgunBVR', weapon_state_rtb='Winchester', engage_opportunity_targets=false, gun_strafing=0, weapon_control_status_surface=0, weapon_control_status_subsurface=0}})",
        "  for _, mount in ipairs(u.mounts) do",
        '    local mn = mount.name and string.upper(tostring(mount.name)) or ""',
        "    local is_gun = false",
        '    if not string.find(mn, "PHALANX") and not string.find(mn, "CIWS") and not string.find(mn, "SEA RAM") then',
        '      if string.find(mn, "MK45") or string.find(mn, "MK 45") or string.find(mn, \'5"/\') or string.find(mn, "OTO") or string.find(mn, "76MM") then is_gun = true end',
        "    end",
        "    if is_gun and mount.weapons then",
        "      for _, w in ipairs(mount.weapons) do",
        "        local dbid = w.wpn_dbid or w.dbid",
        "        if dbid then",
        "          for _, tt in ipairs(land_types) do",
        f'            pcall(function() ScenEdit_SetDoctrineWRA({{side="{side}", guid="{guid}", weapon_id=tostring(dbid), target_type=tt}}, wra_land) end)',
        "          end",
        "          for _, tt in ipairs(surface_types) do",
        f'            pcall(function() ScenEdit_SetDoctrineWRA({{side="{side}", guid="{guid}", weapon_id=tostring(dbid), target_type=tt}}, wra_surface) end)',
        "          end",
        "        end",
        "      end",
        "    end",
        "  end",
        "  end",
        "end",
    ]
    return "\r\n".join(lines)


def materialize_strike_assign_restore_script() -> str:
    """Sample striker + escort restore lines (M.build_strike_assign_restore_script shape)."""
    mission = _q_lua_str(_SAMPLE_MISSION)
    side = _q_lua_str(_SAMPLE_SIDE)
    guid_striker = _SAMPLE_GUID
    guid_escort = "00000000-0000-0000-0000-000000000002"
    lines = [
        "local function _strike_restore_unit(guid, side, mission, escort)",
        "  local _u = ScenEdit_GetUnit({guid=guid})",
        "  if not _u then return end",
        "  local _ml = tostring(_u.assignedMission or _u.mission or '')",
        "  if _ml ~= '' and string.find(string.lower(_ml), string.lower(mission), 1, true) then return end",
        "  local _alt = tonumber(_u.altitude) or 0",
        "  if _alt > 400 then return end",
        "  if _alt >= 50 then return end",
        "  pcall(function() ScenEdit_SetUnit({guid=guid, side=side, mission=mission}) end)",
        "end",
        "print('NOTE: Strike assign restore event')",
        f"_strike_restore_unit('{guid_escort}', '{side}', '{mission}', true)",
        f"_strike_restore_unit('{guid_striker}', '{side}', '{mission}', false)",
        "print('OK: Strike assign restore — 2 aircraft')",
    ]
    return "\r\n".join(lines)


def _scan_script_builder_string_literals(bootstrap_text: str) -> list[str]:
    """Flag break/continue inside quoted fragments of M.build_*_script (heuristic)."""
    errors: list[str] = []
    for match in re.finditer(
        r"function M\.(build_\w+_script)\([^)]*\)(.*?)^end",
        bootstrap_text,
        re.MULTILINE | re.DOTALL,
    ):
        func_name = match.group(1)
        body = match.group(2)
        for line_no, line in enumerate(body.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            if re.search(r"['\"].*\b(break|continue)\b.*['\"]", stripped):
                errors.append(
                    f"Lua static analysis: {func_name} embeds '{stripped[:60]}...' — "
                    f"break/continue in event ScriptText must be inside a loop (use if/return or restructure do/end)."
                )
    return errors


def materialize_bootstrap_event_scripts(
    bootstrap_path: Path | None = None,
) -> list[tuple[str, str]]:
    path = bootstrap_path or BOOTSTRAP_PATH
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [
        ("strike_ship_weapon_policy", materialize_strike_ship_weapon_policy_script(text)),
        ("strike_assign_restore", materialize_strike_assign_restore_script()),
    ]


def validate_bootstrap_event_scripts(
    run_luacheck_fn,
    bootstrap_path: Path | None = None,
) -> dict:
    """Materialize bootstrap Play-time scripts and luacheck them."""
    path = bootstrap_path or BOOTSTRAP_PATH
    if not path.is_file():
        return {"errors": [], "warnings": [], "ok": []}

    text = path.read_text(encoding="utf-8", errors="ignore")
    errors = list(_scan_script_builder_string_literals(text))
    warnings: list[str] = []
    ok: list[str] = []

    snippets = materialize_bootstrap_event_scripts(path)
    with tempfile.TemporaryDirectory(prefix="cmo_event_scripts_") as tmp:
        paths: list[str] = []
        for name, script in snippets:
            out = Path(tmp) / f"{name}.lua"
            out.write_text(script, encoding="utf-8", newline="\n")
            paths.append(str(out))
        lint = run_luacheck_fn(paths)
        errors.extend(lint.get("errors", []))
        warnings.extend(lint.get("warnings", []))
        if not lint.get("errors") and snippets:
            ok.append(
                f"OK: Lua static analysis — materialized {len(snippets)} bootstrap event script(s)."
            )

    return {"errors": errors, "warnings": warnings, "ok": ok}
