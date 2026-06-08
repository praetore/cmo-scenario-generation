# CMO scenario generation — skills & instructions

Primary guide for generating **Command: Modern Operations (CMO)** Lua scripts. Use it to produce syntactically correct, tactically coherent scenarios.

**Output path:** Write scenario scripts to `generated/<scenario_name>.lua`. The folder is in git (via `.gitkeep`); `*.lua` inside it are gitignored locally.

## 1. Core sources

Use these when generating code (API reference and rules in Markdown; helpers in Lua):

- **`.cursor/rules/cmo_api_reference.md`** — **Required** technical reference. Current functions, wrappers, and data types. If a function is not listed here, treat it as deprecated and do not use it.
- **`.cursor/rules/logic_checks_cmo.md`** — Conceptual “rules of the game.” Use for scenario logic validation (fuel, sensors, doctrine, CSG, strike timing) instead of guessing from the PDF manual.
- **`scripts/scenario_bootstrap.lua`** — **Helper library** (spawn, CSG, strike/TLAM timing). Full API reference in the file header (lines 1–100). Generated scenarios live in `generated/` (gitignored locally).

## 2. Essential Lua API rules (CMO-specific)

### Unit creation (`ScenEdit_AddUnit`)

- **Required fields:** `side`, `type`, `unitname`, `dbid`.
- **Location:** `latitude` and `longitude` are required unless `base` is set.
- **Land vs water:**
  - **`Facility`:** Most land facilities (airfields, SAM) cannot be placed in open ocean — `Placement aborted`. Maritime facilities (ports/platforms) may be on water if the DB unit allows it.
  - **`Ship` / `Sub`:** **Water only** (not on land). Otherwise CMO reports errors such as `cannot place ship over land`. Check coordinates on the map or with `World_GetElevation`: elevation **> 0** = land.
  - **Best practice:** Use map/satellite imagery or the CMO cursor; when in doubt, check elevation before spawn.
  - **Lua helper** (recommended for `place_ship` / `place_sub`):

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

- **Source vs master:** With `--series` and `--version`, `scripts/db_search.py` uses the matching source `.db3` (via `cmo_config.json` or local `DB/`). Use `CMO_Master.db` (from `scripts/merge_db.py`) only for cross-version exploration (`--master`).
- **Building master:** `python scripts/merge_db.py` merges source DBs. Limit with `--series`, `--versions`, or `--latest N`.
- **Weapon verification:** SAM and some facilities may have empty or wrong DBIDs in merged DBs.
  - **Check:** `scripts/db_search.py --weapons [ID] --type DataFacility`
  - **Empty units:** No mounts/magazines in search → unit cannot fire in-game; pick another DBID (e.g. battery/section instead of generic “SAM site”).
  - **Operator country:** Each unit has `OperatorCountry`. Preflight fails if `place_ship` / `place_sub` / `spawn_air_wing` uses an operator that does not match the Lua `side` (e.g. a Soviet-operated hull placed on a NATO side).
  - **Junkyard/Generic — last resort:** The DB lists duplicate units under **Junkyard** (9999) or **Generic** — same name, no nation. After `db_search.py "<name>"`, **first** pick a row whose **Operator** column shows a real country or **NATO** (2060). Use Junkyard/Generic only when no national variant fits; add `-- @operator_last_resort` and explain in the OOB header. Preflight **warns** (stronger if alternatives exist).
  - **Pitfall:** “F-35A Lightning II” may map to multiple DBIDs per country — wrong ID → wrong loadouts, sensors, or markings.
- **Loadout / weapon config:**
  - **Aircraft:** `LoadoutID` is tied to `AircraftID`. Always confirm with `--loadouts` or `DataAircraftLoadouts`.
  - **Non-air:** Use `--loadouts --type [Type]` for mounts + magazines.
  - **Search:** `python scripts/db_search.py "UnitName"` and check the `Op` column.
  - **Known operator IDs:** `2060` NATO, `2061` Netherlands, `2011` Belgium, `2101` United States, `2032` France, `2035` Germany, `2074` Poland, `2079` Russia, `2006` Australia. **Last resort:** `9999` Junkyard, Generic — only when no national row exists; tag with `@operator_last_resort`.
  - **DB lookup workflow:** `python scripts/db_search.py "E-3" --series DB3K --version 515` → read **Operator** (id + name), not just unit name; same name often has 5+ DBIDs. Match operator to scenario intent (`@nationality` / side) before writing the dbid into Lua.
- **Preflight (mandatory):**

  ```bash
  python scripts/db_search.py --validate-scenario generated/YOUR_SCENARIO.lua --series DB3K --version 515
  ```

  Covers loadout pairs, mission fit, CSG, strike timing/reachability, SEAD timing, nuclear policy, escorts, and more. See `logic_checks_cmo.md` §1 and §4. Exit codes: `0` / `1` / `2`.

- **Pitfall:** Do not trust stale ID lists; e.g. ID #2748 in DB3K v515 is a MiG-21R, not an F-18.

### Robustness & error prevention

- **Nil checks:** Verify `ScenEdit_AddUnit` succeeded before using `.guid`.
- **Strike escort:** Third parameter `true` on `ScenEdit_AssignUnitToMission` for strike escort slot.
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

0. **OOB header (mandatory):** Comment block at top — year/DB, sides, missions, force composition, objectives.
1. Sides & posture.
2. Infrastructure — CSG (carrier + escorts), bases; see `logic_checks_cmo.md` §4.
3. Units — assign aircraft to bases/carriers.
4. Missions — create then assign.
5. Events — triggers/actions as needed.

## 5. Date & time tools

- `Tool_DateTimeToSeconds("2026-05-08 14:00:00")`
- `Tool_SecondsToDateTime(seconds)`

## 6. Init log messages (mandatory)

During Lua import, CMO shows `print()` output in the **Message Log**. Use prefixed lines so operators (and agents) can tell real failures from **known engine quirks**.

### Prefixes

| Prefix | When to use |
| :--- | :--- |
| **`ERROR:`** | Hard failure — spawn/assign failed, unit not on required mission, missing mission/targets. Script may still finish loading; user must fix before Play. |
| **`WARNING:`** | Suspicious but not proven broken — e.g. schedule empty **without** a known Play-deferred workaround, partial assign counts, updateWPtimes failed. |
| **`NOTE:`** | Expected CMO behaviour that **looks** wrong at init — explain what happens next (usually **after Play**). Not a failure. |
| **`OK:`** | Verified success, **or** success with a documented deferral (e.g. TLAM schedule empty until Play but event + shooter OK). |

**Rule:** If `GetMission` / ME shows empty data at import but **Play** (or a registered event) fixes it, log **`NOTE:`** or **`OK:`** with explicit text — **never `ERROR:`** for that condition alone.

### TLAM + solo CG (template)

Bootstrap helpers follow this; scenarios should mirror the summary line:

```lua
-- Hardcoded times at top (same strike_package_tot for air + TLAM):
local strike_package_tot = '06:30:00'
local tlam_launch_time = '05:54:00'
-- After OOB + targets:
local strike_tot_dt = mission_schedule_datetime(strike_package_date, strike_package_tot)
-- Air TOT:
ScenEdit_CreateMissionFlightPlan(side, STRIKE_AIR_MISSION, {
    DATEONTARGET = strike_package_date,
    TIMEONTARGET = strike_package_tot,
})
-- TLAM (no sync_* — setup_solo_tlam_shooter sets schedule after CG assign):
setup_solo_tlam_shooter(bunker_hill)
print('Strike schedule (hardcoded): TOT=' .. strike_package_tot .. ' Z | TLAM launch=' .. tlam_launch_time .. ' Z')
```

**Do not** call `sync_naval_strike_tot`, `sync_air_strike_tot`, or naval `CreateMissionFlightPlan` in scenarios — they clear air ORBAT or add fragile sync. Preflight verifies **reachability** first; only then timed `SetMission` after OOB.

Helper messages (see `scenario_bootstrap.lua`):

- `NOTE: … schedule empty in GetMission after solo assign … check ME (TLAM event restores at Play if needed)`
- `OK: TLAM detached finalize — TOT=…` / `OK: TLAM event "…" (ScenLoaded, Time=…)`
- **Legacy grouped CG:** `finalize_csg_tlam` — ME schedule often empty; prefer `setup_solo_tlam_shooter`.

**Verification:** Message Log at import + **Mission Editor** (launch/TOT on Caribbean TLAM Salvo, CG solo, CVN+DDGs in CSG group).

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
| Bootstrap API & recipes | **`skills_cmo.md` §9** + bootstrap file header |
| Run in CMO | **`python scripts/embed_bootstrap.py generated/<file>.lua`** → `<file>_import.lua` |
| Preflight | `db_search.py --validate-scenario` merges bootstrap automatically |
| Raw CMO API one-liners | `cmo_api_reference.md` |

Do **not** copy the full bootstrap into Markdown — that drifts from preflight.

## 9. `scenario_bootstrap.lua` — usage for agents

### Workflow

1. Write `generated/<name>.lua` with `cmo.*` calls (requires embed before CMO run).
2. Preflight: `python scripts/db_search.py --validate-scenario generated/<name>.lua --series DB3K --version 515`
3. Import: `python scripts/embed_bootstrap.py generated/<name>.lua` → load `generated/<name>_import.lua` in CMO.

Reference implementation: your latest scenario in `generated/` (gitignored locally) — follow the skeleton below.

### Scenario skeleton

```lua
-- @scenario_policy nuclear=false
-- @strike_package mission=... date=YYYY/MM/DD time=HH:MM:SS ...
-- @naval_package mission=... launch=HH:MM:SS tot=HH:MM:SS minutes_before_strike_tot=N
local scenario_year = 2026
local strike_package_date = '2026/06/01'
local strike_package_tot = '06:30:00'
local tlam_launch_time = '05:54:00'
local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
if not cmo.assert_db_series(scenario_year, 'DB3K') then return end

cmo.configure_strike_timing({
    date = strike_package_date, tot = strike_package_tot,
    tlam_launch = tlam_launch_time,
    air_mission = 'My Air Strike', naval_mission = 'My TLAM Salvo',
    side = 'United States',
})
local place_ship = cmo.place_ship
local spawn_air_wing = cmo.spawn_air_wing
-- … alias other cmo.* helpers you use
```

### Function index (all on `cmo`)

| Category | Functions |
| :--- | :--- |
| Setup | `configure_strike_timing`, `strike_schedule_datetimes`, `set_naval_strike_schedule`, `assert_db_series`, `mission_schedule_date`, `mission_schedule_datetime` |
| Spawn | `place_base`, `place_ship`, `place_sub`, `place_sam`, `add_air_unit_checked`, `spawn_air_wing` |
| Assign | `assign_air_to_mission`, `assign_ship_to_mission`, `refresh_spawned_air_assignments`, `restore_all_spawned_air_assignments`, `resolve_mission_guid` |
| Strike timing | `set_naval_strike_schedule`, `setup_solo_tlam_shooter`, `finalize_strike_air_after_flight_plan`, `verify_spawned_air_assignments` |
| CSG / TLAM | `form_csg_group`, `setup_solo_tlam_shooter`, `add_tlam_shooter_event`, `finalize_detached_tlam_shooter` (legacy), `finalize_csg_tlam` (legacy grouped) |
| Nuclear | `configure_nuclear_policy`, `weapon_dbid_is_nuclear` (DB warhead Type 4001 via embed), `strip_nuclear_from_unit` |

Shared mutable state: **`cmo.state`** (`spawned_air_missions`, strike mission names, dates, etc.).

### CSG + TLAM order (mandatory)

1. Two Strike missions: **air** + **naval TLAM** (never put ships on the air strike mission).
2. **CSG group:** `form_csg_group(CSG_GROUP, cvn, {ddg, …})` — **CG not in group**.
3. Spawn air, assign strike targets.
4. **Hardcoded schedule block** (after OOB): `strike_tot_dt`, `tlam_launch_dt`, SEAD/helo `SetMission`, then air `CreateMissionFlightPlan` with `TIMEONTARGET = strike_package_tot`.
5. `finalize_strike_air_after_flight_plan()` → `setup_solo_tlam_shooter(cg)` → `restore_all_spawned_air_assignments()`.
6. Preflight must pass **Strike TOT reachability** before you treat times as final.

### Date formats

- `ScenEdit_SetMission` / `SetTime`: `YYYY.MM.DD HH:MM:SS` via `cmo.mission_schedule_datetime`.
- `CreateMissionFlightPlan`: `DATEONTARGET = 'YYYY/MM/DD'`, `TIMEONTARGET = 'HH:MM:SS'`.

Details and pitfalls: **`scripts/scenario_bootstrap.lua`** header and **`logic_checks_cmo.md`** §4.
