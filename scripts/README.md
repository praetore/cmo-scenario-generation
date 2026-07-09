# Python tools

Dependencies: Python 3.10+; install with `pip install -r requirements.txt` (`global-land-mask` for the preflight land/water placement check). Luacheck is auto-installed on Windows during preflight. **Lua static analysis uses repo `.luacheckrc` (`lua_version = "5.3"` — same as CMO runtime).**

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

`generate_scenario.py` reads `generated/src/<name>_src.lua` and writes `generated/<name>.lua` for CMO: **English OOB header** (`--` line comments), inlined bootstrap, `@` annotations above scenario code, tree-shake, **English player briefings**. **Runs preflight first** — aborts without writing when preflight errors remain. Briefings: **`generated/src/<name>_briefing.txt`** (English only). Standalone: `python scripts/generate_scenario.py generated/<name>.lua` (briefing inject only). `--no-briefing` to skip briefings.

All generated scenario material under `generated/` — headers, briefings, and player-visible comments — must be **English**. See `AGENTS.md` language section.

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
| `preflight_parse.py` | Re-exports split Lua parsers (barrel) |
| `preflight_parse_io.py` | Load scenario + bootstrap text |
| `preflight_parse_math.py` | Distance, time, bbox helpers |
| `preflight_parse_lua.py` | Lua expression / annotation parsing |
| `preflight_parse_db.py` | DB lookup helpers for parsing |
| `preflight_parse_geo.py` | Ship, sub, facility placement |
| `preflight_parse_units.py` | Air wings, CSG groups, assignments |
| `preflight_parse_missions.py` | Missions, schedules, strike packages |
| `preflight_parse_sides.py` | Sides and reference points |
| `preflight_checks.py` | Re-exports split validators (barrel) |
| `preflight_checks_csg.py` | CSG formation, patrol zones, TLAM |
| `preflight_checks_strike.py` | Strike timing, escorts, naval strike |
| `preflight_checks_sead.py` | SEAD design, ISR-before-SEAD |
| `preflight_checks_oob.py` | Operator, nationality, era, nuclear |
| `preflight_checks_geo.py` | Geo placement, civilian paths |
| `preflight_checks_air.py` | Air assignments, host capacity, sides |
| `preflight_constants.py` | Shared constants |
| `preflight_report.py` | Error/warning report helpers |
| `preflight_luacheck.py` | Download/run luacheck for static Lua analysis (config: repo `.luacheckrc`, Lua 5.3) |

`preflight_validate.py` imports validators and parsers explicitly. The `preflight_checks.py` / `preflight_parse.py` barrels remain for backward compatibility.

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
python scripts/traffic_aeroapi.py key-status
python scripts/traffic_aeroapi.py count --query "-latlong \"50.7 3.3 53.6 7.3\""
python scripts/traffic_flights_to_cmo.py --name nl_traffic --box "50.7 3.3 53.6 7.3" --max-flights 40
python scripts/traffic_flights_to_cmo.py --name nl_traffic --from-json sample.json
```
