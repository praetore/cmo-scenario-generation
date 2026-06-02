# Python tools

Dependencies: Python 3.10+ and `PyYAML` (`pip install pyyaml`).

Run from the repository root, e.g.:

```bash
python scripts/generate_scenario.py --spec generated/cuba_pressure_2026.yaml
python scripts/db_search.py --validate-scenario generated/YOUR_SCENARIO.lua --series DB3K --version 515
python scripts/merge_db.py
```

| Module | Role |
|--------|------|
| `db_search.py` | CLI: search, loadouts, scenario preflight |
| `merge_db.py` | Build `CMO_Master.db` from source `.db3` files |
| `cmo_config.py` | Resolve `cmo_config.ini` / env → DB directory |
| `cmo_db.py` | SQLite open helpers |
| `scenario_*.py` | Lua parsing and validation checks |
| `generate_scenario.py` | Spec-driven Lua generator (v1; updates key locals/options in a base scenario; requires explicit `--spec` YAML) |
| `scenario_schema.py` | YAML schema + validation for declarative scenario specs |
| `scenario_bootstrap.lua` | Shared CMO Lua helpers — **API docs in file header** (lines 1–100); see also `skills_cmo.md` §8 |
| `embed_bootstrap.py` | Merge bootstrap into scenario for CMO import (no `dofile`) |
