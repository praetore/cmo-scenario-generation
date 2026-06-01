# CMO scenario generation

Lua scenarios and Python tooling for **Command: Modern Operations** preflight validation and database lookup.

Python modules live under `scripts/`. Run commands from the **repository root**:

```bash
python scripts/db_search.py …
python scripts/merge_db.py …
```

## Databases (required for `scripts/db_search.py`)

CMO `.db3` files are large and **not stored in git**. Choose one setup:

### Recommended: config file (points at your game install)

1. Copy the template:

   ```bash
   copy cmo_config.example.json cmo_config.json
   ```

2. Edit `cmo_config.json` and set **one** of:

   | Field | Meaning |
   |-------|---------|
   | `db_dir` | Folder that already contains `DB3K_515.db3`, `CWDB_515.db3`, etc. (usually `…/Command Modern Operations/DB`) |
   | `cmo_install_dir` | Game root; tools append `/DB` automatically |

   Typical Steam path (adjust for your install):

   ```text
   C:\Program Files (x86)\Steam\steamapps\common\Command Modern Operations\DB
   ```

3. `cmo_config.json` is gitignored — each machine keeps its own path.

Environment overrides (optional): `CMO_DB_DIR` or `CMO_INSTALL_DIR`.

### Alternative: copy into the repo

Copy the game’s `DB` folder (or only the `.db3` files you need) into this repository’s `DB/` directory. That folder is gitignored; use it when you cannot reference the install path (e.g. portable copy, CI artifact).

```text
DB/DB3K_515.db3
```

If neither config nor local `DB/` has databases, preflight and search commands will fail with setup instructions.

## Optional: `CMO_Master.db`

Merged search DB built from all source `.db3` files in your configured DB directory:

```bash
python scripts/merge_db.py
```

`CMO_Master.db` is gitignored. Scenario preflight normally uses a single version-locked file (`DB3K_515.db3`, etc.) via `--series` / `--version`, not the master file.

## Scenario scripts

Generated Lua lives in `generated/`. Copy a script into your Command install’s `Lua` folder to run it in-game.

Preflight (from repo root):

```bash
python scripts/db_search.py --validate-scenario generated/cuba_pressure_2026.lua --series DB3K --version 515
```

## Check your setup

```bash
python -c "import sys; sys.path.insert(0, 'scripts'); from cmo_db import format_database_layout_message; print(format_database_layout_message())"
```
