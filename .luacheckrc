-- Luacheck config for CMO scenario Lua (preflight + agents).
-- CMO runtime is Lua 5.3 — keep lua_version in sync with AGENTS.md §2.
std = "lua53"
lua_version = "5.3"

globals = {
    "cmo",
}

ignore = {
    "113/ScenEdit_.*",
    "113/VP_.*",
    "113/World_.*",
    "113/Tool_.*",
}

max_line_length = 120
