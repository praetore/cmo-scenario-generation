# Python tools

Dependencies: Python 3.10+; install with `pip install -r requirements.txt` (`global-land-mask` for the preflight land/water placement check). Luacheck is auto-installed on Windows during preflight.

Run from the repository root.

## CLI entry points

| Script | Domain |
|--------|--------|
| `db_search.py` | DB lookup — search units, `--loadouts`, `--weapons` |
| `validate_scenario.py` | Preflight — validate scenario Lua before CMO import |
| `embed_bootstrap.py` | Packaging — inline bootstrap into the scenario file (in place) |

```bash
python scripts/db_search.py "F-35C" --series DB3K --version 515
python scripts/validate_scenario.py generated/YOUR_SCENARIO.lua --series DB3K --version 515
python scripts/embed_bootstrap.py generated/YOUR_SCENARIO.lua
```

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
| `preflight_checks.py` | Individual validators (strike, CSG, SEAD, OOB, geo, …) |
| `preflight_parse.py` | Lua parsing helpers |
| `preflight_constants.py` | Shared constants and patterns |
| `preflight_report.py` | Error/warning report helpers |
| `preflight_luacheck.py` | Download/run luacheck for static Lua analysis |

### Packaging

| Module | Role |
|--------|------|
| `embed_bootstrap.py` | Merge `scenario_bootstrap.lua` into scenario for CMO |
| `scenario_bootstrap.lua` | Shared CMO Lua helpers — API docs in file header; see `skills_cmo.md` §8 |

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
python scripts/traffic_flights_to_cmo.py --name nl_traffic --box "50.7 3.3 53.6 7.3" --max-flights 40
python scripts/traffic_flights_to_cmo.py --name nl_traffic --from-json sample.json
```
