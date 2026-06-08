# Python tools

Dependencies: Python 3.10+; install with `pip install -r requirements.txt` (`PyYAML`, `global-land-mask` for the preflight ship/sub land-vs-water check). Luacheck is auto-installed on Windows during preflight.

Run from the repository root, e.g.:

```bash
python scripts/generate_scenario.py --spec generated/YOUR_SCENARIO.yaml
python scripts/db_search.py --validate-scenario generated/YOUR_SCENARIO.lua --series DB3K --version 515
```

| Module | Role |
|--------|------|
| `db_search.py` | CLI: search, loadouts, scenario preflight |
| `install_luacheck.py` | Download Windows `luacheck.exe` to `tools/luacheck/` (used by preflight auto-install) |
| `merge_db.py` | Optional: merge `.db3` files into `CMO_Master.db` for ad-hoc search (`--master`); not used for preflight |
| `cmo_config.py` | Resolve `cmo_config.ini` / env → DB directory |
| `cmo_db.py` | SQLite open helpers |
| `scenario_*.py` | Lua parsing and validation checks |
| `generate_scenario.py` | Spec-driven Lua generator (v1; updates key locals/options; writes briefing .txt/.html/LOADDOC; optional HTML popup in Lua) |
| `scenario_briefing.py` | Briefing plain-text + HTML renderer for CMO (not Markdown) |
| `scenario_schema.py` | YAML schema + validation for declarative scenario specs |
| `scenario_bootstrap.lua` | Shared CMO Lua helpers — **API docs in file header** (lines 1–100); see also `skills_cmo.md` §8 |
| `embed_bootstrap.py` | Merge bootstrap into scenario for CMO import (no `dofile`) |
| `aeroapi.py` | FlightAware AeroAPI v4 client + CLI (`key-status`, `search`, `positions`, `count`, `flight`) |
| `flights_to_cmo.py` | Live AeroAPI flights → self-contained CMO Lua of neutral civilian traffic (skips when no API key) |
| `aircraft_type_map.py` | Map ICAO `aircraft_type` → CMO `DataAircraft` DBID via the local DB (no API cost; version-correct, civilian-preferred) |

## FlightAware AeroAPI (optional)

For live civilian-traffic generation, set a FlightAware AeroAPI key in
`cmo_config.ini` under `[aeroapi] api_key` (gitignored) or the `AEROAPI_API_KEY`
env var. Without a key the traffic generator skips cleanly. Behind a
TLS-intercepting proxy set `[aeroapi] ca_bundle` (preferred) or `verify_ssl = false`.
Full reference: `.cursor/rules/aeroapi_reference.md`.

Each flight's ICAO aircraft type is mapped to a real CMO airframe DBID against
the local DB (`--series/--version`, default `DB3K 515`); unmapped types fall back
to `--dbid` (default `3970`, Boeing 737-800). **Cost:** only `/flights/search`
is billed — exactly `--max-pages` queries per run (default `2`). Mapping is local.

```bash
python scripts/aeroapi.py key-status
python scripts/flights_to_cmo.py --name nl_traffic --box "50.7 3.3 53.6 7.3" --max-flights 40
# Offline, zero API cost (saved response):
python scripts/flights_to_cmo.py --name nl_traffic --from-json sample.json
```
