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
   - Bootstrap scenarios: edit `generated/src/<name>_src.lua` and **`generated/src/<name>_briefing.txt`** (English player briefings — see `skills_cmo.md` §10; do not embed inline `ScenEdit_SpecialMessage` in source).
   - Load `generated/<name>.lua` in CMO (built by generate step below).
   - Standalone scripts: single `generated/<name>.lua` (no `_src`; briefing sidecar optional).
3. Run **`scripts/validate_scenario.py …`** on the **source** file (`generated/src/*_src.lua` when using bootstrap).
4. **CMO import** (bootstrap scenarios only):
   ```bash
   python scripts/generate_scenario.py generated/src/YOUR_SCENARIO_src.lua
   ```
   Load **`generated/YOUR_SCENARIO.lua`** in the scenario editor (never load `generated/src/*_src.lua`).
5. Copy the scenario `.lua` into CMO’s `Lua` folder if needed and execute from the editor.

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
│   ├── db_search.py             ← DB lookup CLI
│   ├── validate_scenario.py     ← preflight CLI
│   ├── generate_scenario.py     ← CMO load file generation (CLI)
│   ├── generate_briefing.py     ← player briefing sync/inject
│   ├── generate_constants.py    ← paths + shared regex
│   ├── generate_source.py       ← source/load text transforms
│   ├── generate_inline.py       ← bootstrap inline + tree-shake
│   ├── scenario_bootstrap.lua   ← shared Lua helpers (versioned)
│   └── preflight_*.py, db_*.py, traffic_*.py, cmo_*.py
├── DB/                       ← optional local .db3 copy (gitignored)
└── .cursor/rules/
```

**In git:** tooling, rules, docs, config template, `scripts/scenario_bootstrap.lua`, `generated/.gitkeep`, `generated/src/.gitkeep`.
**Not in git:** any scenario `.lua` under `generated/` or `generated/src/` (CMO load files and `*_src.lua` sources), CMO databases, `cmo_config.ini`.

---

## For lightning-talk attendees (no CMO install)

You can still explore the repo:

1. **Inspect preflight logic** — search `def _validate_` in `scripts/preflight_checks.py` (carrier groups, strike timing, loadout fit, nuclear policy, etc.).
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

Requires **Python 3.10+** (`sqlite3` in the standard library). Run all commands from the **repository root**.

`validate_scenario.py` also runs [luacheck](https://github.com/lunarmodules/luacheck) when available; on Windows it is downloaded automatically to `tools/luacheck/` on first use (`CMO_SKIP_LUACHECK_INSTALL=1` to disable).

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
python scripts/validate_scenario.py generated/YOUR_SCENARIO.lua --series DB3K --version 515
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
2. **Write** scenario source locally: `generated/src/<name>_src.lua` (bootstrap) or `generated/<name>.lua` (standalone). Player briefings go in **`generated/src/<name>_briefing.txt`** — `generate_scenario.py` injects them; do not embed inline `ScenEdit_SpecialMessage` in the Lua source.
3. **Validate** with `scripts/validate_scenario.py` (above).
4. **Generate** (bootstrap): `python scripts/generate_scenario.py generated/src/<name>_src.lua` — also runs preflight; **does not write** the load file if preflight errors remain.
5. **Copy** the load file (`generated/<name>.lua`) into the game’s Lua directory (`[CMO install]/Lua/`, subfolders allowed).
6. **Open CMO** → Scenario Editor → run the script from the **Lua Script Console**.
7. Watch the in-game message log for `print()` output and errors (English prefixes — `skills_cmo.md` §6).
8. **Save** as `.scen` if you want to reuse without re-running the script.

---

## Contributing / AI-assisted authoring

- Bootstrap scenarios: edit **`generated/src/<name>_src.lua`** + **`generated/src/<name>_briefing.txt`**; run **`generate_scenario.py`** before loading in CMO.
- Standalone scenarios: single **`generated/<name>.lua`** (briefing sidecar optional).
- Follow **`.cursor/rules/skills_cmo.md`** (English logs §6, briefings §10) and **`.cursor/rules/logic_checks_cmo.md`**.
- API reference: **`.cursor/rules/cmo_api_reference.md`**.

Run preflight before sharing scripts with others (zip, gist, or your own fork).

---

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 praetore.

Scenario content you create locally is your own; keep fictional / educational framing in OOB comments when sharing demos.
