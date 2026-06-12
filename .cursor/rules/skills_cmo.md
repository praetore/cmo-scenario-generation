# CMO scenario generation — skills & instructions

Primary guide for generating **Command: Modern Operations (CMO)** Lua scripts. Use it to produce syntactically correct, tactically coherent scenarios.

**Language — all generated output is English.** Agents and tooling must produce **English only** for anything that ends up in `generated/` or that a player/operator reads in CMO. Do not write Dutch or other non-English prose in generated material — even when the scenario theater is the Netherlands, Norway, or another non-English country.

| English required (no exceptions) | Notes |
| :--- | :--- |
| OOB / load-file header comments | Player-visible at top of `generated/<name>.lua` — **§4 Load file header** |
| Player briefings (`*_briefing.txt`, `*_briefing.html`) | **§10** — injected into load file via `ScenEdit_SpecialMessage` |
| `print()` / init log lines in scenario Lua | **§6** |
| New scenario templates and docs under `.cursor/rules/` | |
| `.cursor/rules/`, scripts, Python CLI output | |

**CMO side names** (e.g. `België`, `Nederland`) may match in-game `ScenEdit_AddSide` identifiers — that is not player prose. All descriptive text around them (headers, briefings, logs) stays **English**.

**Source-only tooling** lines at the top of `*_src.lua` (`SOURCE`, `Preflight`, `CMO load`, `Bootstrap`) are for agents; keep them English too for consistency.

**Output path:** Bootstrap scenarios use two local files under `generated/` (all `*.lua` gitignored — only `.gitkeep` placeholders are tracked):

| File | Purpose |
| :--- | :--- |
| `generated/src/<name>_src.lua` | **Source** — edit this; preflight here; **do not load in CMO** |
| `generated/<name>.lua` | **CMO load file** — built by `generate_scenario.py` (bootstrap inlined + tree-shaked) |

Standalone scenarios (no `cmo.*` helpers) remain a single `generated/<name>.lua` pasted into CMO’s Lua console the same way.

## 1. Core sources

Use these when generating code (API reference and rules in Markdown; helpers in Lua):

- **`.cursor/rules/cmo_api_reference.md`** — **Required** technical reference. Current functions, wrappers, and data types. If a function is not listed here, treat it as deprecated and do not use it.
- **`.cursor/rules/logic_checks_cmo.md`** — Conceptual “rules of the game.” Use for scenario logic validation (fuel, sensors, doctrine, CSG, strike timing) instead of guessing from the PDF manual.
- **`scripts/scenario_bootstrap.lua`** — **Helper library** (spawn, CSG, strike/TLAM timing). API reference: **`.cursor/rules/scenario_bootstrap_reference.md`**. Scenarios live under `generated/` (gitignored locally).
- **`scripts/README.md`** — Python CLI entry points and module layout (`db_search`, `validate_scenario`, `generate_scenario`, …).

### Repository layout

| Path | Purpose |
| :--- | :--- |
| `scripts/` | Python tooling — see **`scripts/README.md`** |
| `.cursor/rules/` | Agent authoring guides (this file, API reference, logic checks) |
| `generated/` | Local scenario output (gitignored) |
| `cmo_config.example.ini` | Template → copy to `cmo_config.ini` (gitignored) |
| `requirements.txt` | Optional pip deps (`global-land-mask` for geo preflight) |

### Database setup

Preflight and `db_search.py` need CMO’s `.db3` SQLite files (hundreds of MB; not in git).

1. Copy `cmo_config.example.ini` to `cmo_config.ini`; set **`cmo_install_dir`** (tools append `\DB`) or **`db_dir`** to the folder containing `DB3K_515.db3`, etc.
2. Environment overrides: **`CMO_INSTALL_DIR`**, **`CMO_DB_DIR`**.
3. Alternative: copy needed `.db3` files into repo **`DB/`** (gitignored).
4. Verify from the repository root:

   ```bash
   python -c "import sys; sys.path.insert(0, 'scripts'); from cmo_db import format_database_layout_message; print(format_database_layout_message())"
   ```

   You should see a DB path and a count of `.db3` files. Fix config before `db_search` or preflight if this fails.

### Reference PDFs (local, gitignored)

`*.pdf` (and other reference formats in `.gitignore`) may be absent in a bare clone but often exist locally under **`.cursor/rules/`** or elsewhere in the workspace.

**When any local PDF is relevant** (scenario year, theater, sides, OOB, doctrine, campaign history, game manual) — **read and use it**; do not skip it because it is not tracked in git. Before designing OOB or era-specific force levels, scan the workspace for matching `*.pdf` files.

- PDFs inform *what* nations fielded and approximate counts; **`db_search.py`** still picks CMO **DBIDs** and loadouts.
- Prefer the **edition/year closest to `scenario_year`** (inventory references go stale quickly).
- Cite the source (title + year) in the OOB header when used.
- Some PDFs are **scanned or image-heavy** — country tables may not be text-searchable; read targeted sections or fall back to other sources and note the gap.
- If no suitable PDF exists locally, note that in the OOB header and proceed with Markdown rules, Wikipedia, or other references.

## 2. Essential Lua API rules (CMO-specific)

### Unit creation (`ScenEdit_AddUnit`)

- **Required fields:** `side`, `type`, `unitname`, `dbid`.
- **Location:** `latitude` and `longitude` are required unless `base` is set.
- **Land vs water:**
  - **`Facility`:** Most land facilities (airfields, SAM) cannot be placed in open ocean — `Placement aborted`. Maritime facilities (ports/platforms) may be on water if the DB unit allows it.
  - **`Ship` / `Sub`:** **Water only** (not on land). Otherwise CMO reports errors such as `cannot place ship over land`. Check coordinates on the map or with `World_GetElevation`: elevation **> 0** = land.
  - **Best practice:** Use map/satellite imagery or the CMO cursor; when in doubt, check elevation before spawn.
  - **Land vs water (mandatory):** Ships/subs → water only; facilities (`place_base`, `place_sam`) → land only (`elevation > 0`). Bootstrap helpers enforce via `World_GetElevation`; preflight uses `global_land_mask` on **every** `place_ship` / `place_sub` / `place_base` / `place_sam` / standalone `AddUnit Facility` (`Geo placement:` errors).
  - **Lua helper** (ships/subs — also built into `cmo.place_ship` / `place_sub`):

  ```lua
  local elev = World_GetElevation({latitude=lat, longitude=lon})
  if elev and elev > 0 then
      print('ERROR: Ship/Sub placement over land at '..lat..','..lon)
      return nil
  end
  ```

- **Altitude (`altitude`):**
  - **AIR:** Required. Missing altitude causes `Missing 'Altitude'`. With a `base`, the aircraft may inherit base height, but setting altitude explicitly is safer.
  - **Other types:** Use `altitude = 0` for ships, subs, and facilities to avoid .NET nullable errors (`Object reference not set`).
- **Parameter names:** `unitname` (not `name`), `latitude` (not `lat`), `longitude` (not `long`).
- **Unit types:** `'Air'`, `'Ship'`, `'Sub'`, `'Facility'`, `'Satellite'`.
- **Base assignment:** `base = 'GUID'` to host aircraft on an airfield or carrier. Always use the base object’s `.guid` and verify it is not `nil`.

### Database & ID verification

DBIDs are **not universal** — they differ by database version (e.g. DB3K v515 vs CWDB).

- **Source database:** With `--series` and `--version`, `scripts/db_search.py` uses the matching source `.db3` (via `cmo_config.ini` → game `DB/`, or local repo `DB/`). Always pass the same series/version as your scenario.
- **Weapon verification:** SAM and some facilities may have empty DBIDs in the database.
  - **Check:** `scripts/db_search.py --weapons [ID] --type DataFacility`
  - **Empty units:** No mounts/magazines in search → unit cannot fire in-game; pick another DBID (e.g. battery/section instead of generic “SAM site”).
  - **Operator country:** Each unit has `OperatorCountry`. Preflight checks that DB operator matches `@nationality` (and loosely matches the Lua `side` for obvious mismatches, e.g. a US hull on a Cuba side).
  - **No national DB row — export proxy (preferred over Junkyard):** When authoritative references (PDF, OOB, campaign history) show a nation **operated** equipment but the DB has **no** `OperatorCountry` for that nation, use the **exporting/supplying nation's** DBID for the same platform (often the original manufacturer or Cold War supplier). Place the unit on the correct scenario **side**; annotate **`@nationality`** with the actual operator and **`@export_proxy`** with the DB supplier. Preflight accepts when the DB operator matches `@export_proxy`. Prefer this over Junkyard/Generic — exporter entries usually have correct mounts, magazines, and sensors.
  - **Junkyard/Generic — last resort:** The DB lists duplicate units under **Junkyard** (9999) or **Generic** — same name, no nation. After `db_search.py "<name>"`, **first** pick a row whose **Operator** column shows a real country or **NATO** (2060), or an **export proxy** as above. Use Junkyard/Generic only when neither a national nor exporter row fits; add `-- @operator_last_resort` and explain in the OOB header. Preflight **warns** (stronger if alternatives exist).

  ```lua
  -- @nationality Libya
  -- @export_proxy Soviet Union   -- BM-21: no Libya operator in DB; USSR export
  place_sam('Libya', 'BM-21 Battery SW Benghazi', 1959, 31.85, 19.97)
  ```
  - **Pitfall:** “F-35A Lightning II” may map to multiple DBIDs per country — wrong ID → wrong loadouts, sensors, or markings.
- **Loadout / weapon config:**
  - **Aircraft:** `LoadoutID` is tied to `AircraftID`. Always confirm with `--loadouts` or `DataAircraftLoadouts`.
  - **Non-air:** Use `--loadouts --type [Type]` for mounts + magazines.
  - **Search:** `python scripts/db_search.py "UnitName" --series DB3K --version 515` and check the `Op` column.
  - **Known operator IDs:** `2060` NATO, `2061` Netherlands, `2011` Belgium, `2101` United States, `2032` France, `2035` Germany, `2074` Poland, `2079` Russia, `2006` Australia. **Last resort:** `9999` Junkyard, Generic — only when no national row exists; tag with `@operator_last_resort`.
  - **DB lookup workflow:** `python scripts/db_search.py "E-3" --series DB3K --version 515` → read **Operator** (id + name), not just unit name; same name often has 5+ DBIDs. Match operator to scenario intent (`@nationality` / side) before writing the dbid into Lua.
- **Preflight (mandatory):**

  ```bash
  python scripts/validate_scenario.py generated/YOUR_SCENARIO.lua --series DB3K --version 515
  ```

  Covers loadout pairs, mission fit, CSG, strike timing/reachability, SEAD timing, nuclear policy, escorts, and more. See `logic_checks_cmo.md` §1 and §4. Exit codes: `0` / `1` / `2`.

- **Pitfall:** Do not trust stale ID lists; e.g. ID #2748 in DB3K v515 is a MiG-21R, not an F-18.

### Robustness & error prevention

- **Nil checks:** Verify `ScenEdit_AddUnit` succeeded before using `.guid`.
- **Strike escort:** Third parameter `true` on `ScenEdit_AssignUnitToMission` for strike escort slot.
- **Strike counts:** Count strikers (without `escort=true`) and escorts on the same Strike mission; `required_escorts = ceil(strikers ÷ StrikeFlightSize) × EscortMinShooter`. See `logic_checks_cmo.md` §1 **Strike striker/escort counts**; preflight: `Strike escort coverage`.
- **Nullable .NET errors:** For AIR on base, prefer `altitude = '0'` (string); for ships/facilities use `altitude = 0`.

### Mission management (`ScenEdit_AddMission`)

- **Syntax:** `ScenEdit_AddMission(Side, Name, Type, {Options})`.
- **SEAD:** `Patrol` with `{type='SEAD'}` — not Strike-SEAD.
- **Assign units:** `ScenEdit_AssignUnitToMission(guid, mission)` — unit **GUID** + mission **name** (see `cmo_api_reference.md` → *Practical note* under `ScenEdit_AssignUnitToMission`; mission guid is documented but often fails). Targets: `ScenEdit_AssignUnitAsTarget`.
- **Wrapper calls:** `mission:updateWPtimes()` — colon syntax, not dot (see `cmo_api_reference.md`).

### Side info (`VP_GetSide`)

- Use `VP_GetSide({side='SideName'})` — not a bare string.

### Stance / posture

`ScenEdit_SetSidePosture`: `'H'` Hostile, `'F'` Friendly, `'N'` Neutral, `'U'` Unfriendly.

## 3. Wrappers & objects

- **Fields:** `unit.altitude`, `unit.guid` (dot).
- **Methods:** `mission:updateWPtimes()`, `mission:createFlightPlans({...})` (colon).
- **GUIDs:** Use `.guid` for all cross-references.

## 4. Scenario design workflow

0. **OOB header (mandatory):** Comment block at top — historical date, year/DB, sides, missions, force composition, objectives. Cross-check force levels against **§1 Reference PDFs** when a matching local PDF exists, before locking unit counts. Format and load-file layout: **Load file header** below.
1. **Scenario date (mandatory):** One canonical `local scenario_date = 'YYYY/MM/DD'` for the historical in-game day. Derive `scenario_year`, `strike_package_date`, `ScenEdit_SetTime` StartDate/date, and `@strike_package date=` from it. Preflight: **`Scenario date:`** errors on mismatch.
2. **Sides & posture (mandatory on blank scenarios):** `ScenEdit_AddSide({side='...'})` for **every** side **before** `ScenEdit_SetSidePosture`, `ScenEdit_AddMission`, or any spawn. Preflight fails with `Sides:` if a referenced side was never added (CMO: *Unable to identify Side-A!*).
3. **Reference points:** every `ScenEdit_AddReferencePoint` needs **`side=`** matching the mission that uses the RP in `zone={...}` (duplicate name/coords per side if needed). Preflight: `Reference point:` errors.
4. Infrastructure — CSG (carrier + escorts), bases; see `logic_checks_cmo.md` §4.
5. Units — assign aircraft to bases/carriers.
6. Missions — create then assign.
7. Events — triggers/actions as needed.

### Load file header (`*_src.lua` → CMO load file)

Bootstrap scenarios: edit **`generated/src/<name>_src.lua`**, generate with **`python scripts/generate_scenario.py`**, load **`generated/<name>.lua`**. The OOB comment block at the top of the source becomes the **player-visible header** in the load file (`--` line comments). Implementation: `prepare_load_header_and_annotations()` in **`scripts/generate_source.py`**.

**Write in `_src.lua` (top → bottom):**

1. **Source-only tooling** (keep for agents; **stripped** from the load-file header): `-- SOURCE — do not load`, `-- Preflight: python scripts/validate_scenario.py …`, `-- CMO load: …`, `-- Bootstrap: scripts/scenario_bootstrap.lua …`
2. **OOB header** (player-facing): title, theater, `-- OOB (Order of Battle)`, year/DB, posture, force lists per side, missions, doctrine, objectives. **English only** — copied verbatim to the load file top (see top-of-file language rule).
3. **`-- @…` annotations** (preflight / policy — not in the visible header)
4. **Scenario Lua** (`local scenario_date`, `cmo.*`, `ScenEdit_*`, …)

Prefer **`--` line comments** for the OOB block. Block comments `--[[ … ]]` are OK in source — generate unwraps them to line comments.

**Generated load file layout:**

```text
-- CMO Scenario: …
-- OOB (Order of Battle)
-- …

local M = {}
… tree-shaken bootstrap …
cmo = M

-- @scenario_policy …
-- @strike_package …

local scenario_date = '…'
…
```

Do **not** expect `Source:` / `Bootstrap:` / `Preflight:` / `@` lines at the top of the load file — generate removes tooling from the header and places `@` lines **after** the bootstrap block, **before** scenario code. Standalone scenarios (no bootstrap) keep one file; preflight/tooling lines may remain at the bottom of the header.

**Minimal OOB skeleton in `_src.lua`:**

```lua
-- SOURCE — do not load this file in CMO. Edit <name>_src.lua in generated/src/ only.
-- Preflight: python scripts/validate_scenario.py generated/src/<name>_src.lua --series DB3K --version 515
-- CMO load:  generated/<name>.lua (python scripts/generate_scenario.py generated/src/<name>_src.lua)
-- CMO Scenario: <title>
-- <theater / sides one-liner>
--
-- OOB (Order of Battle)
-- Year/DB: YYYY | DB3K v515
-- Posture: SideA <-> SideB = Hostile
--
-- SideA (role)
-- Forces, missions, doctrine …
--
-- SideB (role)
-- …

-- @scenario_policy nuclear=false
local scenario_date = 'YYYY/MM/DD'
```

## 5. Date & time tools

**Canonical day** — define once at the top:

```lua
local scenario_date = '2011/03/19'
local scenario_year = tonumber(scenario_date:sub(1, 4))
local scenario_start_time = '08:00:00'
local strike_package_date = scenario_date

cmo.scenario_set_start(scenario_date, scenario_start_time)
```

- `scenario_date` = historical in-game calendar day (must match OOB header and `@strike_package date=`).
- `scenario_start_time` = H-hour (before first mission takeoff / strike TOT).
- **`cmo.scenario_set_start`** wraps `ScenEdit_SetTime` with correct CMO formats: `dateformat=YYYYMMDD`, `date=YYYY.MM.DD`, **`StartDate=DD.MM.YYYY`** (do not pass compact `20110319` to `StartDate` — API expects day-first).
- `cmo.mission_schedule_datetime(scenario_date, 'HH:MM:SS')` → `YYYY.MM.DD HH:MM:SS` for `ScenEdit_SetMission`.
- `CreateMissionFlightPlan` uses `DATEONTARGET = scenario_date` (slashes).
- Patrol/Support **Time on Station** in ME: `set_patrol_on_station_schedule` — **Patrol** uses `CreateMissionFlightPlan` `TIMEONTARGET`; **Support** (land ISR) uses wrapper `TimeOnTargetStation` + `CreateMissionFlightPlan` `TAKEOFFTIME` (transit default 90 min). Do not use `TIMEONTARGET` flight plan on Support — it clears GetMission fields.
- After TOT/TOS assignment: `verify_mission_schedule` — **fatal** on `TimeOnTargetStation` / on-station mismatch. Strike: `set_strike_tot_schedule` (flight plan + wrapper TOT). Patrol/Support: `set_patrol_on_station_schedule`. Unified strike `starttime`/`TakeOffTime` in GetMission often empty → `optional_fields = { 'starttime', 'takeoff' }`.
- `Tool_DateTimeToSeconds("2026-05-08 14:00:00")` / `Tool_SecondsToDateTime(seconds)` for ad-hoc math.

## 6. Init log messages (mandatory)

During Lua import, CMO shows `print()` output in the **Message Log**. Use prefixed lines so operators (and agents) can tell real failures from **known engine quirks**.

### Prefixes

| Prefix | When to use |
| :--- | :--- |
| **`ERROR:`** | Hard failure — spawn/assign failed, unit not on required mission, missing mission/targets. **Aborts scenario init** via `error()` (bootstrap helpers call `cmo.scenario_error` / `_abort_scenario_generation`). Fix before Play or re-run generate. |
| **`WARNING:`** | Suspicious but not proven broken — e.g. schedule empty **without** a known Play-deferred workaround, partial assign counts, updateWPtimes failed. |
| **`NOTE:`** | Expected CMO behaviour that **looks** wrong at init — explain what happens next (usually **after Play**). Not a failure. |
| **`OK:`** | Verified success, **or** success with a documented deferral (e.g. TLAM schedule empty until Play but event + shooter OK). |

**Rule:** If `GetMission` / ME shows empty data at import but **Play** (or a registered event) fixes it, log **`NOTE:`** or **`OK:`** with explicit text — **never `ERROR:`** for that condition alone.

### Unified strike package (air + naval assets)

One **Strike** mission is the **strike package**: it unifies all strike assets (air strikers/escorts + naval TLAM shooters) under one launch schedule and TOT. Say *unify strike assets on the package mission* — not *CSG joins the air strike*. Internal names (`STRIKE_AIR_MISSION`, `setup_csg_strike_on_air_strike`) are historical. Bootstrap helpers follow this; scenarios should mirror the summary line:

```lua
-- Hardcoded times at top (same strike_package_tot for air + TLAM):
local strike_package_tot = '06:30:00'
local tlam_launch_time = '05:45:00'
-- After OOB + targets + air flight plan:
ScenEdit_CreateMissionFlightPlan(side, STRIKE_AIR_MISSION, {
    DATEONTARGET = strike_package_date,
    TIMEONTARGET = strike_package_tot,
})
finalize_strike_air_after_flight_plan()
-- Unify naval strike assets on the same Strike mission as aircraft (launch + TOT):
local strike_ships = {}
for _, hull in ipairs({ nimitz, ddg51, ddg51_escort, bunker_hill }) do
    if hull then table.insert(strike_ships, hull) end
end
setup_csg_strike_on_air_strike(CSG_GROUP, strike_ships)  -- function name is historical; unifies strike assets
restore_all_spawned_air_assignments(STRIKE_AIR_MISSION)
print('Strike schedule (hardcoded): TOT=' .. strike_package_tot .. ' Z | TLAM launch=' .. tlam_launch_time .. ' Z')
```

**Do not** call naval `CreateMissionFlightPlan` in scenarios — it clears air ORBAT. Use `setup_csg_strike_on_air_strike` + `set_naval_strike_schedule` instead. Preflight verifies **reachability** first; only then timed `SetMission` after OOB.

**CMO quirks (general — not scenario-specific):**

| Quirk | Fix |
| :--- | :--- |
| Naval assets on unified Strike + flight plan only → Tomahawks at **scenario start** | `starttime` + `TimeOnTargetStation` on the package mission (`set_naval_strike_schedule` / `setup_csg_strike_on_air_strike`) |
| Adding naval assets or `SetMission` on the package clears **aircraft ORBAT** | `finalize_strike_air_after_flight_plan()` + `restore_all_spawned_air_assignments()` + `add_strike_assign_restore_event()` at Play |
| Empty magazines + shared strike doctrine → **guns on land** | `configure_strike_ship_weapon_policy` per hull (auto on Strike assign) + play-time WRA refresh |
| SEAD/Patrol `MinAircraftReq` × `FlightSize` = launch trigger | Set `MinAircraftReq` to **flight count**, not total aircraft (same as `StrikeMinAircraftReq × StrikeFlightSize`) |
| `AssignUnitToMission(group_name, patrol)` clears TLAM shooters | Assign patrol on **group lead (CVN) only** |

Helper messages (see `scenario_bootstrap.lua`):

- `OK: <strike mission> launch=… TOT=… (N CSG hull(s))`
- `OK: Strike ship gun policy events for … — ScenLoaded + …`

**Verification:** Message Log at import + **Mission Editor** (all strike assets — air + naval — on one Strike mission, launch/TOT visible, gun WRA blocked on land).

### When adding new CMO quirks

1. Document in bootstrap helper + **`NOTE:`/`OK:`** log (not silent).
2. Mention in this section or `logic_checks_cmo.md` if preflight/agents need it.
3. Preflight: **OK with note** when script workflow is correct; reserve **ERROR** for missing event/helper or wrong order.

## 7. Debugging & best practices

- Verbose `print()` during script load — follow §6 prefixes.
- Store `ScenEdit_AddUnit` return values.
- Match DB series/version to scenario year.
- **Pro vs Standard:** Fields marked `PRO ONLY` in `cmo_api_reference.md` require CMO Professional.
- **Deprecated:** Do not use APIs absent from `cmo_api_reference.md` (e.g. `ScenEdit_AddAircraft` → use `ScenEdit_AddUnit`).

## 8. Helpers vs ad-hoc API

| Need | Where |
| :--- | :--- |
| Spawn, CSG, strike/TLAM timing | **`scripts/scenario_bootstrap.lua`** — edit helpers here; scenarios call `cmo.*` |
| Bootstrap API & recipes | **`scenario_bootstrap_reference.md`** + **`skills_cmo.md` §9** |
| Run in CMO | **`generate_scenario.py`** → paste **`generated/<file>.lua`** into a blank scenario’s Lua console (**§9 Run in CMO**) |
| Preflight | `validate_scenario.py` on **`generated/src/<file>_src.lua`** (merges bootstrap Lua automatically) |
| Raw CMO API one-liners | `cmo_api_reference.md` |

Bootstrap **implementation** is only in `scripts/scenario_bootstrap.lua`; **documentation** is in `scenario_bootstrap_reference.md` (not inlined into CMO load files).

## 9. `scenario_bootstrap.lua` — usage for agents

### Workflow

1. Write `generated/src/<name>_src.lua` with an OOB header comment block + `cmo.*` calls (source only — not for CMO load). Header layout: **§4 Load file header**.
2. Edit or accept auto-generated player briefings — **§10** (`generated/src/<name>_briefing.txt` + `.html`).
3. **Dependencies:** On a fresh clone, or when preflight warns `global_land_mask not installed`, run `python -m pip install -r requirements.txt` from the repo root before validation (enables land/water geo checks).
4. Preflight: `python scripts/validate_scenario.py generated/src/<name>_src.lua --series DB3K --version 515`
5. Generate: `python scripts/generate_scenario.py generated/src/<name>_src.lua` → **`generated/<name>.lua`** for CMO playtest (**Run in CMO** below).

`generate_scenario.py` **re-runs preflight** on the source; if any preflight error is reported it **does not write** the load file (exit code 2).

### Run in CMO (playtest)

After generate, load the scenario in-game (user steps — describe when handing off):

1. **Command: Modern Operations** → **Scenario Editor** → create a **blank scenario** (same database as the script, e.g. DB3K 515).
2. Open the **Lua Script Console**.
3. Open **`generated/<name>.lua`** in a text editor, copy all of it, paste into the console, and **Run**.
4. Watch the message log for `OK:` / `ERROR:` / `NOTE:` lines from `print()`; press **Play**; optionally **Save** as `.scen`.

**Never** paste `generated/src/*_src.lua` — source only; bootstrap is not inlined and tooling lines must not go to CMO.

Reference implementation: your latest scenario in `generated/` (gitignored locally) — follow the skeleton below.

### Scenario skeleton

```lua
-- @scenario_policy nuclear=false
-- @strike_package mission=... date=YYYY/MM/DD time=HH:MM:SS ...
-- @naval_package mission=... launch=HH:MM:SS tot=HH:MM:SS minutes_before_strike_tot=N  (optional when naval assets share the unified strike mission)
local scenario_date = '2026/06/01'
local scenario_year = tonumber(scenario_date:sub(1, 4))
local scenario_start_time = '06:00:00'
local scenario_date_ymd = scenario_date:gsub('/', '')
local strike_package_date = scenario_date
local strike_package_tot = '06:30:00'
local tlam_launch_time = '05:54:00'
local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
if not cmo.assert_db_series(scenario_year, 'DB3K') then return end

cmo.configure_strike_timing({
    date = strike_package_date, tot = strike_package_tot,
    tlam_launch = tlam_launch_time,
    air_mission = 'My Strike Package', naval_mission = 'My Strike Package',  -- one mission unifies air + naval strike assets
    side = 'United States',
})
local place_ship = cmo.place_ship
local spawn_air_wing = cmo.spawn_air_wing
-- … alias other cmo.* helpers you use
```

### Function index (all on `cmo`)

| Category | Functions |
| :--- | :--- |
| Setup | `configure_strike_timing`, `strike_schedule_datetimes`, `set_naval_strike_schedule`, `assert_db_series`, `scenario_error`, `mission_schedule_date`, `mission_schedule_datetime` |
| Spawn | `place_base`, `place_ship`, `place_sub`, `place_sam`, `add_air_unit_checked`, `spawn_air_wing` |
| Assign | `assign_air_to_mission`, `assign_ship_to_mission`, `refresh_spawned_air_assignments`, `restore_all_spawned_air_assignments`, `resolve_mission_guid` |
| Strike timing | `set_naval_strike_schedule`, `finalize_strike_air_after_flight_plan`, `verify_spawned_air_assignments`, `add_strike_assign_restore_event` |
| Strike package / TLAM | `form_csg_group`, **`setup_csg_strike_on_air_strike`**, `configure_strike_ship_weapon_policy`, `add_strike_ship_weapon_policy_event` |
| Nuclear | `configure_nuclear_policy`, `weapon_dbid_is_nuclear` (DB warhead Type 4001 via embed), `strip_nuclear_from_unit` |

Shared mutable state: **`cmo.state`** (`spawned_air_missions`, strike mission names, dates, etc.).

### Unified strike package order (mandatory)

1. One **Strike** mission as the **strike package** — aircraft and naval TLAM shooters share it via `setup_csg_strike_on_air_strike`.
2. **CSG formation:** `form_csg_group(CSG_GROUP, cvn, {ddg, cg, …})` — escorts stay grouped; strike assets are assigned to the package mission in formation.
3. Spawn strike aircraft, assign targets; `configure_strike_mission_options` **before** spawn.
4. **Hardcoded schedule block** (after OOB): SEAD/ISR `set_patrol_on_station_schedule` (on-station), strike `set_strike_tot_schedule` (flight plan + wrapper TOT, fatal verify), then `finalize_strike_air_after_flight_plan()` → carrier CAP/AEW → `setup_csg_strike_on_air_strike` → final `set_strike_tot_schedule` wrapper reassert.
5. `finalize_strike_air_after_flight_plan()` → carrier CAP/AEW `SetMission` (after SEAD time) → `setup_csg_strike_on_air_strike(CSG_GROUP, {cvn, ddg, cg, …})` (unify naval strike assets) → `restore_all_spawned_air_assignments()` → `add_strike_assign_restore_event()` for Play.
6. Preflight must pass **Strike TOT reachability** and **SEAD flight size** before you treat times as final.

### Date formats

- `ScenEdit_SetMission` / `SetTime`: `YYYY.MM.DD HH:MM:SS` via `cmo.mission_schedule_datetime`.
- `CreateMissionFlightPlan`: `DATEONTARGET = 'YYYY/MM/DD'`, `TIMEONTARGET = 'HH:MM:SS'`.

Details and pitfalls: **`scenario_bootstrap_reference.md`**, **`logic_checks_cmo.md`** §4.

## 10. Player briefings

Player-facing scenario text lives in **sidecar files**, not in the Lua source. **English only** — same rule as OOB headers and init logs; never generate Dutch or other non-English briefings.

### Files

| Path | Role |
| :--- | :--- |
| `generated/src/<name>_briefing.txt` | Edit here (plain text, `@side` blocks) |
| `generated/src/<name>_briefing.html` | Auto-synced from `.txt`, or edit for CMO-exact HTML |

Same stem as `<name>_src.lua` (bootstrap) or standalone `generated/<name>.lua`. **English only** — no Dutch or other non-English player text. One `@side` block per playable side; side name must match `ScenEdit_AddSide` (side names may use diacritics when they match CMO, e.g. `België`).

### Format (per `@side` block)

```
SCENARIO TITLE IN CAPS
Date: DDMMYYYY | Side: Side Name | Complexity: High

I. SITUATION
...

II. INTEL
Friendly OOB: ...
Enemy Threat: ...
Environment: ...

III. MISSION
...

IV. EXECUTION & ROE
ROE: ...
Special Instructions: ...
```

If `.txt` is newer, `generate_scenario.py` regenerates `.html`; if `.html` is newer, generate uses it as-is.

### Inject (do not embed in source)

- **`generate_scenario.py`** appends `ScenEdit_SpecialMessage(...)` HTML to the **CMO load file** only.
- **Do not** put `ScenEdit_SpecialMessage` player briefings in `*_src.lua` or standalone scenario bodies. Legacy inline blocks are stripped on generate; keeping briefings in sidecar files avoids duplicates and language drift.
- Bootstrap: `python scripts/generate_scenario.py generated/src/<name>_src.lua`
- Standalone load file (briefing inject only): `python scripts/generate_scenario.py generated/<name>.lua`
- Skip: `--no-briefing`

Reference: **`scenario_bootstrap_reference.md`** (briefing section), Cuba briefing example in `generated/src/`.
