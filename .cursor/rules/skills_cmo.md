# CMO scenario generation — skills & instructions

Primary guide for generating **Command: Modern Operations (CMO)** Lua scripts. Use it to produce syntactically correct, tactically coherent scenarios.

**Output path:** Write new scenario scripts to `generated/<scenario_name>.lua` (gitignored locally; not in the repository root).

## 1. Core sources (single source of truth)

Use **only** these Markdown files when generating code. They consolidate the official PDF, Excel, and HTML sources in an AI-friendly form:

- **`.cursor/rules/cmo_api_reference.md`** — **Required** technical reference. Current functions, wrappers, and data types. If a function is not listed here, treat it as deprecated and do not use it.
- **`.cursor/rules/logic_checks_cmo.md`** — Conceptual “rules of the game.” Use for scenario logic validation (fuel, sensors, doctrine, CSG, strike timing) instead of guessing from the PDF manual.

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
  - **Operator country:** Each unit has `OperatorCountry`. Preflight fails if `place_ship` / `place_sub` / `spawn_air_wing` uses an operator that does not match the Lua `side` (e.g. Soviet Osa on side `Cuba`).
  - **Pitfall:** “F-35A Lightning II” may map to multiple DBIDs per country — wrong ID → wrong loadouts, sensors, or markings.
- **Loadout / weapon config:**
  - **Aircraft:** `LoadoutID` is tied to `AircraftID`. Always confirm with `--loadouts` or `DataAircraftLoadouts`.
  - **Non-air:** Use `--loadouts --type [Type]` for mounts + magazines.
  - **Search:** `python scripts/db_search.py "UnitName"` and check the `Op` column.
  - **Known operator IDs:** `2061` Netherlands, `2011` Belgium, `2101` United States, `2032` France, `2035` Germany, `2006` Australia.
- **Preflight (mandatory):**

  ```bash
  python scripts/db_search.py --validate-scenario generated/YOUR_SCENARIO.lua --series DB3K --version 515
  ```

  Covers loadout pairs, mission fit, CSG, strike TOT sync, SEAD timing, nuclear policy, escorts, and more. See `logic_checks_cmo.md` §1 and §4. Exit codes: `0` / `1` / `2`.

- **Pitfall:** Do not trust stale ID lists; e.g. ID #2748 in DB3K v515 is a MiG-21R, not an F-18.

### Robustness & error prevention

- **Nil checks:** Verify `ScenEdit_AddUnit` succeeded before using `.guid`.
- **Strike escort:** Third parameter `true` on `ScenEdit_AssignUnitToMission` for strike escort slot.
- **Nullable .NET errors:** For AIR on base, prefer `altitude = '0'` (string); for ships/facilities use `altitude = 0`.

### Mission management (`ScenEdit_AddMission`)

- **Syntax:** `ScenEdit_AddMission(Side, Name, Type, {Options})`.
- **SEAD:** `Patrol` with `{type='SEAD'}` — not Strike-SEAD.
- **Assign units:** `ScenEdit_AssignUnitToMission(guid, mission)`; targets use `ScenEdit_AssignUnitAsTarget`.
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

## 6. Debugging & best practices

- Verbose `print()` during script load.
- Store `ScenEdit_AddUnit` return values.
- Match DB series/version to scenario year.
- **Pro vs Standard:** Fields marked `PRO ONLY` in `cmo_api_reference.md` require CMO Professional.
- **Deprecated:** Do not use APIs absent from `cmo_api_reference.md` (e.g. `ScenEdit_AddAircraft` → use `ScenEdit_AddUnit`).

## 7. Useful snippets

**List units on a side:**

```lua
local side = VP_GetSide({side='USA'})
for k,v in pairs(side.units) do
    print(v.name .. " (" .. v.guid .. ")")
end
```

**Set speed and altitude:**

```lua
ScenEdit_SetUnit({guid='GUID', manualSpeed=350, manualAltitude=5000})
```
