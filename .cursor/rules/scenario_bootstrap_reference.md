# `scenario_bootstrap.lua` — helper reference

Implementation: **`scripts/scenario_bootstrap.lua`**. Scenarios call helpers as **`cmo.*`** after embed (`cmo = M`).

**Authoring workflow**

1. Write **`generated/src/<scenario>_src.lua`** using `cmo.*` (see setup below).
2. Player briefing (English, sidecar only — **not** inline in Lua): **`generated/src/<scenario>_briefing.txt`** (+ auto-synced `.html`). See **`skills_cmo.md` §10**.
3. Preflight: `python scripts/validate_scenario.py generated/src/<scenario>_src.lua ...`
4. **Build CMO file (mandatory after every src edit):** `python scripts/generate_scenario.py generated/src/<scenario>_src.lua` → **`generated/<scenario>.lua`**. The agent runs this — do not leave it to the user. Source changes are invisible in CMO until this step succeeds.
5. Load **`generated/<scenario>.lua`** in CMO (never load `*_src.lua`).

### Player briefing files (`*_briefing.txt` + `*_briefing.html`)

- Paths: **`generated/src/<name>_briefing.txt`** and **`.html`** (same stem as `<name>_src.lua` or standalone `<name>.lua`).
- **English only.** One `@side` block per playable side (name must match `ScenEdit_AddSide`).
- **Do not embed briefings in Lua source.** No `ScenEdit_SpecialMessage` player text in `*_src.lua` or standalone scenario bodies — only in these sidecar files. `generate_scenario.py` injects HTML into the CMO load file; it strips legacy inline briefing blocks from source when building the load file.
- **Body format** (per side):

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

- Edit `.txt` (easier) or `.html` (CMO-exact). If `.txt` is newer, generate regenerates `.html`; if `.html` is newer, generate uses it as-is.
- **Bootstrap:** `python scripts/generate_scenario.py generated/src/<name>_src.lua` (generate + briefing).
- **Standalone load file:** `python scripts/generate_scenario.py generated/<name>.lua` (briefing inject only).
- Skip briefings: `--no-briefing`

See also: **`skills_cmo.md` §6 (logs), §10 (briefings)**, **`logic_checks_cmo.md` §4**.

---

## Setup (top of every bootstrap scenario)

```lua
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
-- Alias helpers you use: local place_ship = cmo.place_ship
```

## Preflight annotations (parsed from scenario comment lines)

| Tag | Example |
| :--- | :--- |
| `@scenario_policy` | `nuclear=false` |
| `@strike_package` | `mission=... date=YYYY/MM/DD time=HH:MM:SS max_spread=15` |
| `@naval_package` | `mission=... launch=HH:MM:SS tot=HH:MM:SS minutes_before_strike_tot=N` |
| `@sead_package` | `missions=... takeoff=HH:MM:SS minutes_before_strike_tot=N` |
| `@strike_wave` | `id=tlam role=naval_strike offset=0 mission=...` |

## Date/time formats (do not mix)

| Use | Format |
| :--- | :--- |
| `ScenEdit_SetTime`, `ScenEdit_SetMission` | `YYYY.MM.DD HH:MM:SS` — use `cmo.mission_schedule_datetime` |
| `CreateMissionFlightPlan` `DATEONTARGET` | `YYYY/MM/DD` |
| Launch/TOT inside helpers | Use `cmo.*` schedule helpers (CMO upvalue pitfall if relying on outer locals) |

## `cmo.state` (shared mutable state)

`configure_strike_timing` and scenario init fill: `BASE_FACILITY_DBID`, `spawned_air_missions`, `mission_guid_cache`, `strike_side`, `strike_package_date`, `strike_package_tot`, `tlam_launch_time`, `STRIKE_AIR_MISSION`, `TLAM_STRIKE_MISSION`, `db_series`, `nuclear_weapons_allowed`, `conventional_tlam_dbid`.

---

## Function reference (all on `cmo` after embed)

### Setup

| Function | Purpose |
| :--- | :--- |
| `configure_strike_timing(cfg)` | `date`, `tot`, `tlam_launch`, `air_mission`, `naval_mission`, `side` |
| `assert_db_series(year, expected)` | e.g. `assert_db_series(2026, 'DB3K')` |
| `mission_schedule_date('2026/06/01')` | → `'2026.06.01'` |
| `mission_schedule_datetime(date, '06:30:00')` | CMO datetime string |
| `minutes_from_hms` / `hms_from_minutes` / `hms_subtract_minutes` | Clock math for ISR→SEAD sequencing |
| `add_mission_schedule_restore_event(opts)` | ScenLoaded + Time — re-apply on-station or takeoff schedule at Play. `restore_times` = list of **absolute** `HH:MM:SS` on `start_date` (not offset from H-hour); use `scenario_start + 5s` when H-hour ≠ `00:00:00`. Optional `extra_script` (appended on `station_hms` / `takeoff_hms` trigger only). |

### Spawn

Nil + `ERROR` print on failure; `place_ship` / `place_sub` check elevation.

| Function | Notes |
| :--- | :--- |
| `place_base(side, name, lat, lon)` | Uses `state.BASE_FACILITY_DBID` |
| `place_ship`, `place_sub`, `place_sam` | Land/water checks via `World_GetElevation` |
| `add_air_unit_checked(...)` | Requires `loadoutid` |
| `spawn_air_wing(...)` | Batch spawn + assign |

### Civilian air traffic (§11 — no aimless loiter)

Register the engagement box once, add 1–3 same-side airports, then one call per airliner.

| Function | Notes |
| :--- | :--- |
| `configure_civilian_traffic({ theater = { lat_min, lat_max, lon_min, lon_max } })` | Theater bounds for exit courses |
| `register_civilian_airport(side, name, lat, lon)` | Civilian-side airfield + RTB target — **uses `place_base`** (land only; preflight geo-checked). Avoid reclaimed-island ICAO coords (e.g. HK Chek Lap Kok → use Shenzhen or verified land). |
| `add_civilian_airliner(side, name, dbid, loadoutid, lat, lon, alt_m, heading, speed_kts, opts?)` | **auto**: straight exit course (fuel-capped); **land**: lead-in + gradual approach (no RTB snap); **transit**: force theater exit |

```lua
cmo.configure_civilian_traffic({
    theater = { lat_min = 17, lat_max = 26, lon_min = 62, lon_max = 74 },
})
cmo.register_civilian_airport('Civilian Air Traffic', 'Karachi Jinnah Intl', 24.90, 67.16)
cmo.add_civilian_airliner('Civilian Air Traffic', 'EK512 (A6-ENU)', 3977, 19921,
    22.10, 68.40, 11582, 120, 470)
```

### Mission assign

| Function | Notes |
| :--- | :--- |
| `assign_air_to_mission(side, guid, name, mission, strike_escort?)` | |
| `assign_ship_to_mission(side, ship, mission, group_name?)` | `group_name` only for legacy grouped fallback |
| `refresh_spawned_air_assignments(mission_filter?)` | Re-assign tracked spawns |
| `restore_all_spawned_air_assignments(mission_filter?)` | After TLAM/naval schedule mutations |
| `resolve_mission_guid(side, mission_name)` | |

### Strike timing

Use these in scenarios — do not reimplement schedule logic ad hoc.

| Function | Purpose |
| :--- | :--- |
| `strike_schedule_datetimes()` | `{ tot, tlam_launch }` from `cmo.state` + scenario locals |
| `set_patrol_on_station_schedule(...)` | SEAD/ISR: `CreateMissionFlightPlan` TIMEONTARGET |
| `set_strike_tot_schedule(...)` | Strike TOT: flight plan + wrapper + fatal verify |
| `set_naval_strike_schedule(...)` | Unified package launch/TOT after ship assign |
| `setup_csg_strike_on_air_strike(group, {cvn, ddg, cg, ...})` | Naval assets on package mission + gun policy |
| `ungroup_unit(ship, side?)` | Only when leaving an existing group — never `group='none'` on solo ships |
| `finalize_strike_air_after_flight_plan()` | `updateWPtimes` + restore all spawned air |
| `add_strike_assign_restore_event(opts)` | Play-time ORBAT restore |
| `verify_mission_schedule(...)` | `GetMission` check; `error()` on mismatch unless `opts.fatal=false` |
| `verify_spawned_air_assignments(mission?)` | WARNING if aircraft unassigned |
| `configure_strike_mission_options(side, mission, opts)` | **Before** `spawn_air_wing` (`SetMission` clears assignments) |

### Strike package + TLAM

| Function | Purpose |
| :--- | :--- |
| `form_csg_group(group_name, cvn_lead, {ddg, cg, ...})` | CSG formation |
| `configure_strike_ship_weapon_policy(unit, opts)` | Auto via strike-ship assign |
| `add_strike_ship_weapon_policy_event(ship, opts)` | Play-time WRA refresh |

### Nuclear policy (`@scenario_policy nuclear=false`)

| Function | Purpose |
| :--- | :--- |
| `configure_nuclear_policy({ allowed=false, ... })` | Side doctrine + strip policy |
| `weapon_dbid_is_nuclear(dbid)` / `weapon_dbid_is_nuclear_cruise(dbid)` | DB sets injected at generate time |
| `weapon_name_is_nuclear(name)` | Fallback when dbid unknown |
| `conventional_tlam_dbid()` / `strip_nuclear_from_unit(unit, opts?)` | After `place_ship` on CSG |

---

## Recipes

### Unified strike package with naval TLAM (preferred)

1. One **Strike** mission = strike package (`OnDeactivateUassign=false`); `configure_strike_timing` may use the same name for air and naval.
2. `form_csg_group(CSG_GROUP, cvn, {ddg1, ddg2, cg})`.
3. Configure strike options **before** spawn; assign targets.
4. Schedule block: SEAD/ISR on-station → strike TOT → `finalize_strike_air_after_flight_plan()` → carrier CAP/AEW → `setup_csg_strike_on_air_strike` → `restore_all_spawned_air_assignments` → `add_strike_assign_restore_event`.
5. Naval: **no** `CreateMissionFlightPlan` on ship-only strike.

### Aircraft-only strike package

`configure_strike_timing` without `naval_mission`; skip naval TLAM steps.

### Support already on-orbit at scenario start (ISR / AEW demo)

Use when `on_station == scenario_start_time` and the first sortie must be **airborne at Play**, not on deck.

1. Create Support mission + zone RPs; `set_patrol_on_station_schedule` with `takeoff_time_hms = scenario_start_time`, `transit_minutes = 0`, `flight_size = 1`, `min_aircraft_req = 1`, `on_deactivate_unassign = false`.
2. **First flight** — spawn without base at orbit (not `spawn_air_wing`):

```lua
local u = ScenEdit_AddUnit({
    type = 'Air', side = side, unitname = 'Triton #1', dbid = 2846, loadoutid = 13986,
    latitude = isr_lat, longitude = isr_lon, altitude = 50000,
    mission = 'Caribbean ISR Orbit',
})
ScenEdit_SetUnit({ guid = u.guid, throttle = 'Cruise', timetoready_minutes = 0 })
-- track in spawned_air_missions + assign_air_to_mission (or local helper mirroring add_air_unit_checked)
```

3. **Relief pool** — `cmo.add_air_unit_checked(..., 'Triton #2', …, base_guid, …)` for `#2…#N` (carrier or land base).
4. After **all** schedule / strike / `restore_all_spawned_air_assignments` calls, re-`SetUnit` orbit position on first-flight GUIDs.
5. Register Play events (`ScenLoaded` + `Time` at `03:00:05` if H-hour is `03:00:00`) with `launch=true` on those GUIDs. Set `restore_times` on `add_mission_schedule_restore_event` to match H-hour + 5s, not `00:00:05`.
6. Regenerate (agent — after every src change): `python scripts/generate_scenario.py generated/src/<name>_src.lua`.

Reference implementation: `generated/src/cuba_pressure_2026_demo_src.lua`.

---

## Init log prefixes (`skills_cmo.md` §6)

| Prefix | Meaning |
| :--- | :--- |
| `ERROR:` | Hard failure — aborts scenario Lua init (`error()` after log line) |
| `WARNING:` | Suspicious; no known Play workaround |
| `NOTE:` | Expected import quirk |
| `OK:` | Verified success |

End scenarios with a Strike TOT summary line when applicable.

## Pitfalls

- **Mission names, not guids** for `AssignUnitToMission` / `SetUnit(mission=)`.
- **Groups:** use a name string to join; do not set `group='none'` on ships never grouped (CMO creates a group literally named `"none"`). Use `ungroup_unit()` to leave a group.
- **No external Lua:** use `generate_scenario.py` (CMO has no `dofile`).
- **`SetMission` on strike package after aircraft assigned** clears the package — configure options before spawn; TOT via `CreateMissionFlightPlan`.
- **Naval TLAM:** `setup_csg_strike_on_air_strike` keeps ships in CSG; `set_naval_strike_schedule` after assign.
- **SEAD** = Patrol type `SEAD`, not Strike; set `starttime`/`TakeOffTime` before strike TOT.
- **Hosted aircraft “teleport”:** `SetUnit` lat/lon/altitude on units with `base=` does not make them airborne — spawn on-orbit flights without `base`, or use `launch=true` at Play.
- **Support `FlightSize` for single on-station + pool:** `FlightSize=1`, `MinAircraftReq=1`, `OnDeactivateUassign=false` when N aircraft rotate one orbit (ISR/AEW).
- **`restore_times`:** absolute `HH:MM:SS` on scenario date — align first entry with `scenario_start_time + 5s` when H-hour is not midnight.
