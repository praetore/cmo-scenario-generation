# Python tools

Dependencies: Python 3.10+; install with `pip install -r requirements.txt` (`global-land-mask` for the preflight land/water placement check). Luacheck is auto-installed on Windows during preflight.

Run from the repository root.

## CLI entry points

| Script | Domain |
|--------|--------|
| `db_search.py` | DB lookup — search units, `--loadouts`, `--weapons` |
| `validate_scenario.py` | Preflight — validate scenario Lua before CMO import |
| `generate_scenario.py` | **Generate** — build CMO load file from `*_src.lua` |
| `generate_briefing.py` | **Generate** — briefing txt/html sync (used by `generate_scenario`) |

```bash
python scripts/db_search.py "F-35C" --series DB3K --version 515
python scripts/validate_scenario.py generated/src/YOUR_SCENARIO_src.lua --series DB3K --version 515
python scripts/generate_scenario.py generated/src/YOUR_SCENARIO_src.lua
```

`generate_scenario.py` reads `generated/src/<name>_src.lua` and writes `generated/<name>.lua` for CMO (inline bootstrap + tree-shake + player briefings). **Runs preflight first** — aborts without writing the load file when preflight reports errors. Player briefings live in **`generated/src/<name>_briefing.txt`** (English; not inline in Lua — see `.cursor/rules/skills_cmo.md` §10). Standalone load files: `python scripts/generate_scenario.py generated/<name>.lua` (briefing inject only). Use `--no-briefing` to skip briefings.

`db_search.py --validate-scenario` still works but is deprecated; use `validate_scenario.py`.

## Modules by domain

### DB (`db_*`, `cmo_*`)

| Module | Role |
|--------|------|
| `cmo_config.py` | Resolve `cmo_config.ini` / env → DB directory |
| `cmo_db.py` | Open version-locked CMO `.db3` files |
| `db_unit_queries.py` | Loadouts, magazines, mounts |
| `db_nuclear.py` | Nuclear weapon DBID classification from SQLite |

### Preflight (`preflight_*`)

| Module | Role |
|--------|------|
| `preflight_validate.py` | Orchestrates full scenario validation |
| `preflight_parse.py` | Parse scenario Lua for units, missions, sides |
| `preflight_checks.py` | Individual validation checks |
| `preflight_constants.py` | Shared constants |
| `preflight_report.py` | Error/warning report helpers |
| `preflight_luacheck.py` | Download/run luacheck for static Lua analysis |

### Generate (`generate_*`)

| Module | Role |
|--------|------|
| `generate_scenario.py` | CLI — build CMO load file from source |
| `generate_constants.py` | Paths, shared regex, path helpers |
| `generate_source.py` | Source/load text transforms, headers, strip inlined blocks |
| `generate_inline.py` | Inline `scenario_bootstrap.lua` + tree-shake |
| `generate_briefing.py` | Sync `*_briefing.txt` + `.html`, inject `ScenEdit_SpecialMessage` |
| `scenario_bootstrap.lua` | Shared CMO Lua helpers (implementation) |
| `.cursor/rules/scenario_bootstrap_reference.md` | Bootstrap API, recipes, pitfalls (authors/agents) |

### Traffic — optional (`traffic_*`)

| Module | Role |
|--------|------|
| `traffic_aeroapi.py` | FlightAware AeroAPI v4 client + CLI |
| `traffic_flights_to_cmo.py` | Live flights → neutral civilian CMO Lua |
| `traffic_aircraft_type_map.py` | ICAO type → CMO `DataAircraft` DBID |

## FlightAware AeroAPI (optional)

Set a FlightAware AeroAPI key in `cmo_config.ini` under `[aeroapi] api_key` or `AEROAPI_API_KEY`.
Full reference: `.cursor/rules/aeroapi_reference.md`.

```bash
python scripts/traffic_aeroapi.py flights --origin EHAM
python scripts/traffic_flights_to_cmo.py --origin EHAM --limit 20
```
