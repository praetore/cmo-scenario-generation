# Python tools

Run from the repository root, e.g.:

```bash
python scripts/db_search.py --validate-scenario generated/cuba_pressure_2026.lua --series DB3K --version 515
python scripts/merge_db.py
```

| Module | Role |
|--------|------|
| `db_search.py` | CLI: search, loadouts, scenario preflight |
| `merge_db.py` | Build `CMO_Master.db` from source `.db3` files |
| `cmo_config.py` | Resolve `cmo_config.json` / env → DB directory |
| `cmo_db.py` | SQLite open helpers |
| `scenario_*.py` | Lua parsing and validation checks |
