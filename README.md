# CMO scenario generation

**Lua scenarios and Python tooling for [Command: Modern Operations](https://www.matrixgames.com/game/command-modern-operations) (CMO)** — built to support AI-assisted authoring, with automated “preflight” checks before you load a script in the game.

> **New to CMO?** This README is written for a lightning-talk audience: you do not need to own the game to understand what the repository does. To *run* scenarios you (or a demo machine) need a CMO install and the official databases.

---

## What is Command: Modern Operations?

CMO is a **real-time naval / air / land wargame** used by hobbyists and professionals for what-if conflict analysis. Think of it as an interactive map where:

- **Units** are real-world platforms (ships, aircraft, SAM sites, submarines) with sensors, weapons, and fuel modeled in detail.
- **Scenarios** place those units on a map with sides (e.g. Blue vs Red), missions (patrol, strike, SEAD), and victory conditions.
- **The database** (`DB3K`, `CWDB`, …) is a large SQLite dataset of equipment IDs, loadouts, and capabilities — versioned (e.g. **DB3K 515** = modern era).

CMO can build scenarios by hand in the editor, but it also exposes a **Lua scripting API** (`ScenEdit_*` functions). Running a `.lua` file can create sides, spawn units, assign missions, and set doctrine in seconds — which is what this repository automates and validates.

---

## What is this repository?

| Piece | Purpose |
|--------|---------|
| **`scripts/`** | Python tools: search the equipment DB, validate Lua before play |
| **`.cursor/rules/`** | Authoring guides for AI assistants (API reference, doctrine checks) |
| **`cmo_config.example.ini`** | Template for pointing tools at your game’s `DB` folder (not committed) |
| **`generated/`** | **Local** folder for scenario `.lua` you produce (gitignored) |

**Problem we solve:** Scenario Lua is easy to get wrong — wrong aircraft/loadout pairs, ships on land, strike timing that cannot be flown, carrier groups without escorts, nuclear weapons on by accident. A single typo in a database ID fails silently in-game or hours into a test. **Preflight** runs dozens of static checks against the same database CMO uses.

**Typical workflow:**

1. Describe a scenario (human + AI, using rules in `.cursor/rules/`).
2. Save Lua under `generated/` on your machine (not in this git repo).
3. Run **`scripts/db_search.py --validate-scenario …`** (must pass or warn).
4. **CMO import:** inline bootstrap (CMO has no `dofile`):
   ```bash
   python scripts/embed_bootstrap.py generated/YOUR_SCENARIO.lua
   ```
   Load **`generated/YOUR_SCENARIO_import.lua`** in the scenario editor.
5. Copy the `_import.lua` into CMO’s `Lua` folder if needed and execute from the editor.

```mermaid
flowchart LR
  A[Idea / OOB] --> B[Lua locally in generated/]
  B --> C[Python preflight]
  C -->|errors| B
  C -->|ok| D[CMO: Run Lua script]
  D --> E[Playtest on map]
```

---

## Repository layout

```text
cmo-scenario-generation/
├── README.md
├── LICENSE
├── cmo_config.example.ini    ← copy to cmo_config.ini
├── generated/                ← local scenario Lua (gitignored)
├── scripts/                  ← Python (run from repo root)
│   ├── db_search.py
│   ├── merge_db.py
│   ├── scenario_bootstrap.lua   ← shared Lua helpers (versioned)
│   └── scenario_*.py
├── DB/                       ← optional local .db3 copy (gitignored)
└── .cursor/rules/
```

**In git:** tooling, rules, docs, config template, `scripts/scenario_bootstrap.lua`, `generated/.gitkeep`.  
**Not in git:** scenario `.lua` under `generated/`, CMO databases, `cmo_config.ini`.

---

## For lightning-talk attendees (no CMO install)

You can still explore the repo:

1. **Inspect preflight logic** — search `def _validate_` in `scripts/scenario_checks.py` (carrier groups, strike timing, loadout fit, nuclear policy, etc.).
2. **Read authoring rules** — `.cursor/rules/logic_checks_cmo.md` (escorts, SEAD before strike, era-appropriate units).
3. **Skim the API reference** — `.cursor/rules/cmo_api_reference.md` for `ScenEdit_*` patterns.

You will **not** be able to run validation or the game without [Database setup](#database-setup).

---

## Database setup

Preflight and search need the same **SQLite `.db3` files** shipped with CMO. They are hundreds of MB each and are **not stored in this repository**.

### Recommended: config file (point at your game install)

1. Install **Command: Modern Operations** (Steam or standalone).
2. Copy the template:

   ```bash
   copy cmo_config.example.ini cmo_config.ini
   ```

3. Edit `cmo_config.ini` — set **one** of:

   | Field | Meaning |
   |-------|---------|
   | `cmo_install_dir` | **Preferred**. Game root directory; tools append `\DB` automatically |
   | `db_dir` | Optional override: direct folder containing `DB3K_515.db3`, etc. |

   Example (Windows Steam — adjust to your path):

   ```ini
   [cmo]
   cmo_install_dir = C:/Program Files (x86)/Steam/steamapps/common/Command Modern Operations
   ```

4. `cmo_config.ini` stays on your machine only (gitignored).

Optional environment variables: `CMO_DB_DIR` or `CMO_INSTALL_DIR`.

### Alternative: copy databases into the repo

Copy the `.db3` files you need into `DB/` (e.g. `DB/DB3K_515.db3`). The folder is gitignored. Use this for offline demos or CI artifacts.

### Verify setup

From the repository root:

```bash
python -c "import sys; sys.path.insert(0, 'scripts'); from cmo_db import format_database_layout_message; print(format_database_layout_message())"
```

You should see a path to your DB folder and a count of `.db3` files.

---

## Python tooling

Requires **Python 3.10+** (`sqlite3` + `PyYAML`). Run all commands from the **repository root**.

`--validate-scenario` also runs [luacheck](https://github.com/lunarmodules/luacheck) when available; on Windows it is downloaded automatically to `tools/luacheck/` on first use (`CMO_SKIP_LUACHECK_INSTALL=1` to disable).

Create `generated/` locally if it does not exist, then place your scenario `.lua` there.

### Search equipment and loadouts

```bash
python scripts/db_search.py "F/A-18E" --series DB3K --version 515
python scripts/db_search.py --loadouts 342 --series DB3K --version 515
python scripts/db_search.py --weapons 429 --type DataShip --series DB3K --version 515
```

### Validate a scenario (preflight)

Use the **same database series and version** your Lua script declares (see `db_series` / header comments in your file).

```bash
python scripts/db_search.py --validate-scenario generated/YOUR_SCENARIO.lua --series DB3K --version 515
```

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | No errors (warnings allowed) |
| `1` | Warnings only |
| `2` | Errors — fix before loading in CMO |

Checks include: aircraft/loadout compatibility, mission/loadout fit, carrier strike group composition, strike **time-on-target** vs range, SEAD timing, escort coverage for bombers, nuclear policy, operator country vs side, patrol zones near the CSG, and more.

Preflight and search use the **version-locked source `.db3`** for your scenario (`--series` / `--version` + `cmo_config.ini` → game `DB/`). That is what you need for real authoring.

---

## Running a scenario in CMO (step-by-step)

1. **Install CMO** and configure database paths (see above).
2. **Write or generate** a `.lua` scenario under `generated/` locally.
   - Optional generator flow:
     ```bash
     python scripts/generate_scenario.py --spec generated/cuba_pressure_2026.yaml
     ```
     Use an explicit YAML spec each run (no default scenario selection). Also writes `*_briefing.txt` (plain text), `*_briefing.html` + `*_briefing_loaddoc.txt` (CMO HTML/LOADDOC), and appends an in-game HTML popup via `ScenEdit_SpecialMessage` when `briefing.show_popup` is true (CMO does **not** render Markdown).
3. **Validate** with `scripts/db_search.py --validate-scenario` (above).
4. **Copy** the script into the game’s Lua directory (`[CMO install]/Lua/`, subfolders allowed).
5. **Open CMO** → Scenario Editor → run the script from the **Lua Script Console**.
6. Watch the in-game message log for `print()` output and errors.
7. **Save** as `.scen` if you want to reuse without re-running the script.

---

## Contributing / AI-assisted authoring

- Write new scenarios to **`generated/<name>.lua`** locally (folder is gitignored).
- Follow **`.cursor/rules/skills_cmo.md`** and **`.cursor/rules/logic_checks_cmo.md`**.
- API reference: **`.cursor/rules/cmo_api_reference.md`**.

Run preflight before sharing scripts with others (zip, gist, or your own fork).

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 praetore.

Scenario content you create locally is your own; keep fictional / educational framing in OOB comments when sharing demos.
