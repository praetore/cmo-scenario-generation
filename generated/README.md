# Generated scenario scripts

Agent-produced CMO Lua scenarios live here. Copy the file you need into your Command install’s `Lua` folder (or a subfolder under it), then run it from the scenario editor.

## Preflight

From the repository root:

```bash
python scripts/db_search.py --validate-scenario generated/cuba_pressure_2026.lua --series DB3K --version 515
```

Replace the filename for other scenarios in this directory.
