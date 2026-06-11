# CMO Scenario Logic & Validation Checks

This document contains conceptual gameplay rules and logic from the CMO manual. Use these checks to verify whether a generated scenario is functionally sound and realistic.

## 1. Logistics & Fuel (Fuel Management)
- **Bingo Fuel**: Units turn back to base when they have just enough fuel to land safely.
  - *Check*: Is the distance to the target within the unit's range? If not, add tankers (`AAR`) to the mission.
- **Air-to-Air Refueling (AAR)**: Tankers must fly at the correct position and altitude.
  - *Check*: Do strike aircraft have a refuel doctrine that allows tankers?
  - *Check (Bomber strike — only when needed)*: **CALCM/JASSM standoff** from a reasonably nearby land base (e.g. continental US → regional target) → tanker **not** mandatory. **Penetration/LDGP** or extreme range → KC mission **or** targeted `use_refuel_unrep`. Do **not** set `Yes_Yes` on a strike with **20+ carrier fighters**: CMO sends everyone to 1–2 tankers (queue, mid-air collisions); prefer `No_No` + `Bingo` RTB.
- **Magazines & Stores**: Units without ammunition in their magazines cannot rearm.
  - *Check (Aircraft)*: Does the base/carrier have the correct `Loadouts` in stock (magazines) for stationed aircraft? Use `scripts/db_search.py --loadouts [ID] --type DataAircraft` to find compatible loadouts. **Critical**: Always verify that the `LoadoutID` appears on the authorized list for the specific `AircraftID`.
  - *Check (Loadout Compatibility)*: Ensure the chosen `LoadoutID` is actually linked to the aircraft in the database (`DataAircraftLoadouts` table). A loadout from another country or another variant of the same airframe may not work.
  - *Check (Non-Air Vehicles)*: For `DataShip`, `DataSubmarine`, `DataFacility`, and `DataGroundUnit`, verify effective "loadout" via mounts + magazines with `scripts/db_search.py --loadouts [ID] --type [Type]`.
  - *Check (Legacy alternative)*: `scripts/db_search.py --weapons [ID] --type [Type]` performs the same internal armament check.
  - *Check (Scenario preflight — mandatory)*: Always run `python scripts/db_search.py --validate-scenario generated/<scenario>.lua --series <DB3K|CWDB> --version <version>` before delivering a script (scenarios live in `generated/`). Also checks **wrapper colon syntax** (`mission:updateWPtimes()`, not `mission.updateWPtimes()`). With series+version, validation runs against the matching source `.db3` (path via `cmo_config.json` → game `DB/`, or local repo `DB/`); use `CMO_Master.db` only for exploration or with `--master`.
  - *Check (Mission/Loadout fit — mandatory)*: A loadout that technically fits an airframe may still be wrong for the mission role. Per mission, verify the loadout role matches the mission type:
    - `AAW/CAP/Escort` → A/A loadout (or SEAD-capable escort such as Wild Weasel).
    - `SEAD` → **Patrol** mission with `type='SEAD'` (not Strike); ARM/SEAD loadout on that mission; no anti-ship-only or strike-only loadouts. The strike target list does **not** cover SEAD fires — only emitters in the patrol zone.
    - `Strike` → strike loadout (bombs/AG); no A/A-only loadouts.
    - `Support/AEW` → AEW/early-warning loadout.
    - The same `--validate-scenario` run now reports mission/loadout mismatches alongside DB compatibility.
  - *Check (Strike package escort — mandatory)*: **Non-stealth bombers** on a **Strike** mission and every **SEAD** mission must be supported by **fighter escort** (CAP/AAW with A/A loadout on the same side). SEAD flights also need their own escort (not only the strike wave).
    - **Stealth bombers** (e.g. B-2, F-117, B-21 in the DB name) are outside this hard requirement; document escort anyway if scenario doctrine requires it.
    - **Standoff bombers**: Only **CALCM/ALCM/JASSM**-type loadouts on Strike (no penetration with LDGP) → **no** mandatory fighter escort in preflight, but **do** check AAR/range; `--validate-scenario` warns.
    - **Heuristic in `scripts/db_search.py`**: classification on `DataAircraft.Name` (e.g. B-52, B-1, Tu-95, Tu-22, Su-24, F-111, …); stealth markers excluded. Missing escort fails `--validate-scenario`. Pass explicit Lua-side as the first argument of `add_air_unit_checked` / `spawn_air_wing`, otherwise the check cannot be enforced per side.
  - *Check (Strike flight profile vs munitions — mandatory)*: **Standoff** loadouts (CALCM, JSOW, JASSM, …) do not belong on **penetration** flight paths (ingress over the target like dumb bombs). Set `-- @strike_package mission=<StrikeName> profile=standoff|penetration time=HH:MM:SS date=YYYY/MM/DD max_spread=N` and `-- @strike_wave id=... role=naval_strike|air_strike|air_standoff offset=<minutes vs TOT>` in the Lua script; call `ScenEdit_CreateMissionFlightPlan` with the same `TIMEONTARGET` for all air strikers. Doctrine: `ShotgunOneEngagementBVR` / `ShotgunBVR` for standoff, not `Shotgun50_ToO` (penetration behavior). Preflight compares loadout classes, annotations, flight-plan calls, and wave spread.
  - *Check (Strike timing — mandatory)*: **Hardcode one clock** — `local strike_package_tot = 'HH:MM:SS'` at scenario top; reuse for air `CreateMissionFlightPlan` `TIMEONTARGET`, naval `TimeOnTargetStation`, and `@strike_package` / `@naval_package` annotations. **No** `sync_naval_strike_tot` / `sync_air_strike_tot` in scenario scripts. Derive `strike_tot_dt = mission_schedule_datetime(strike_package_date, strike_package_tot)` once **after OOB**; all timed `ScenEdit_SetMission` / flight plans **after** last `place_ship` / `spawn_air_wing` / `AssignUnitAsTarget`. TLAM: `setup_solo_tlam_shooter(cg)` → assign CG → `set_naval_strike_schedule` (hardcoded launch + TOT). Preflight: **`Strike timing`** + **`Strike schedule order`**.
  - *Check (Strike TOT reachability — mandatory)*: Before finalizing times, preflight computes whether each strike asset can hit targets by `strike_package_tot` (TLAM cruise from CG, carrier transit from CSG, B-52/CALCM from staging, SEAD transit). If **too early**, fail with **suggested minimum TOT** (`Raise strike_package_tot to at least HH:MM:SS Z`) — fix locals/annotations, **then** run SetMission blocks. Do not SetMission until reachability passes.
  - *Check (Naval TLAM timing — mandatory)*: **Naval strike assets on the same Strike mission as aircraft fire Tomahawks at scenario start** unless that mission has explicit **`starttime` + `TimeOnTargetStation`** (~20–35 min before TOT). **Preferred (2026+):** unify all TLAM-capable hulls with aircraft on **one strike package mission** via `setup_csg_strike_on_air_strike(group, {cvn, ddg, cg, …})` — CSG stays in **`form_csg_group`**, one TOT in ME for the whole package. **Legacy:** separate naval-only Strike + solo CG → `setup_solo_tlam_shooter(cg)` (`group=''`, no naval flight plan). Document launch/TOT with `-- @naval_package mission=<name> launch=HH:MM:SS tot=HH:MM:SS` (mission name may match the unified package). **Never** naval-only `CreateMissionFlightPlan` on a ship strike (clears ME TOT). **Init log:** `NOTE:`/`OK:` when `GetMission` empty at import on legacy solo paths — see `skills_cmo.md` §6. Preflight: naval timing + **TLAM schedule workflow**.
  - *Check (Strike ship gun policy — mandatory on any Strike-assigned warship)*: Any CSG hull on a **Strike** mission (CVN/DDG/CG) uses **standoff weapons only** for the land attack — **never** main gun on land (`WRA_GUN_LAND_BLOCK` / land target WRA `none`). **Surface gun:** **self-defence only** — unit `weapon_control_status_surface=0` (HOLD), `engage_opportunity_targets=false`, surface gun WRA offensive range `none`, self-defence `max`. Mission `weapon_state_planned='ShotgunBVR'`, `weapon_state_rtb='Winchester'`. Applied automatically via `configure_strike_ship_weapon_policy()` in `assign_ship_to_mission` + `add_strike_ship_weapon_policy_event` (ScenLoaded, 00:00:05, TLAM launch). Shared strike doctrine (`ShotgunOneEngagementBVR`) otherwise lets empty-magazine ships shell land targets. Preflight: **`Strike ship guns`** in `--validate-scenario`. Aliases: `configure_tlam_shooter_weapon_policy`.
  - *Check (Other assets — warning)*: CAP/AEW/ISR patrols without `starttime` while the strike package has a flight plan → warning (may launch early); SEAD and naval have their own hard checks.
  - *Check (No nuclear weapons — unless `@scenario_policy nuclear=true`)*: Conventional scenarios use **no** nuclear loadouts and set `use_nuclear_weapons='No'`. Nuclear classification uses **DB** `DataWarhead.Type = 4001` (EnumWarheadType Nuclear), embedded as `M.NUCLEAR_WEAPON_DBIDS` / `M.NUCLEAR_CRUISE_DBIDS` via `embed_bootstrap.py`. Runtime `strip_nuclear_from_unit()` removes by dbid and replaces cruise with UGM-109 TACTOM/TLAM-C.
  - *Check (Mission assignment — mandatory)*: Every `place_ship` / `place_sub` / `place_sam` must get `ScenEdit_AssignUnitToMission` (directly or `for _, u in pairs(table)`). **Aircraft**: `spawn_air_wing` → existing mission; set `mission=` on `ScenEdit_AddUnit` (not for strike escort) **and** `assign_air_to_mission` (guid/name × mission name/guid, `SetUnit` fallback). **Never** `ScenEdit_SetMission` on the strike package after aircraft are assigned (clears ORBAT). Configure strike flight size via `configure_strike_mission_options` before spawn; package TOT via `CreateMissionFlightPlan` TIMEONTARGET only. After flight plan: `finalize_strike_air_after_flight_plan()` (restore **all** spawned air). If unifying naval strike assets runs **after** that (`setup_csg_strike_on_air_strike`, `setup_solo_tlam_shooter`, or naval `SetMission`), call `restore_all_spawned_air_assignments()` again + `add_strike_assign_restore_event()` for Play (CAP/SEAD launch can unassign strikers). Strike escort: `AssignUnitToMission(..., true)`. Preflight: **`Mission assignment`** + **`Aircraft mission assignment`**.
  - *Check (Carrier strike flight-size — mandatory for large CSG strike)*: With **≥6 strikers** or **≥6 escorts** on one Strike mission (carrier **or** landbase), CMO must **not** launch everything as singles. Set via `configure_strike_mission_options` / `ScenEdit_SetMission`:
    - `StrikeUseFlightSize = true`, `StrikeFlightSize = 4` (or 2/6/8), optionally `StrikeMinAircraftReq` (e.g. 8) so the first wave waits for enough aircraft;
    - `EscortUseFlightSize = true`, `EscortFlightSizeShooter = 4`, optionally `EscortMinShooter`.
    - Document in `-- @strike_package ... flight_size=4 use_flight_size=true min_aircraft=8 escort_flight_size=4 escort_use_flight_size=true`.
    - Do **not** set `UseFlightSize=false` / `useflightsize=false` on that mission — that forces one-by-one launch. Preflight counts carrier-based wings for flight-size settings; **striker/escort balance** applies to all bases (see **Strike striker/escort counts**).
  - *Check (Era-appropriate OOB — mandatory)*: Set `local scenario_year = YYYY` (and `db_series`) in every scenario. Preflight compares **no fixed DBID list**, but:
    - **Platform**: `YearCommissioned` / `YearDecommissioned` from the DB vs `scenario_year` (not yet in service → **error**; DB marks decommissioned before scenario year → **warning**).
    - **Strike munitions** (year ≥ 2000): loadout **name** heuristic — no strike that is **only** unguided (`LDGP`, `Mk84 LDGP`, …); precision/standoff (`JDAM`, `JSOW`, `GBU-`, `CALCM`, `JASSM`, …) is OK. **Error** from year ≥ 2010; **warning** 2000–2009.
    - **Role fit** (not a mandatory type): F-35A/B/C and carrier type via **name** in the DB; bomber escort via **name** patterns — not "use aircraft X".
    - **Deliberate exception** (e.g. obsolete defender): document in the scenario header; the validator cannot infer intent.
  - *Check (Strike escort slot — mandatory)*: Fighter escort for a **Strike** mission belongs in the **escort layer of that Strike mission**, not on a loose patrol with "Escort" in the name. Use `ScenEdit_AssignUnitToMission(unit, '<StrikeMission>', true)` — 3rd parameter `escort=True` (see `.cursor/rules/cmo_api_reference.md`). Strikers on the same Strike mission: 2 parameters or `false`. `--validate-scenario` fails on patrol missions like `Strike Escort CAP` for strike escorts, or on Strike without at least one `escort=true` assignment.
  - *Check (Strike striker/escort counts — mandatory)*: **Count and document** — track the **exact counts** per Strike mission and verify they align with flight-size settings. CMO de-assigns strikers (often from a second base, e.g. Sigonella) when there are too few escorts for the number of strike flights.
    - **Count strikers:** sum of all `spawn_air_wing(..., '<StrikeMission>', base, …)` **without** `escort=true` (carrier and land bases).
    - **Count escorts:** sum of all `spawn_air_wing(..., '<StrikeMission>', base, true)` on the **same** Strike mission.
    - **Mission options:** `StrikeFlightSize`, `StrikeMinAircraftReq`, `EscortFlightSizeShooter`, `EscortMinShooter` via `configure_strike_mission_options` before spawn; document in OOB header and `-- @strike_package` (`flight_size`, `min_aircraft`, `escort_flight_size`, `min_ready_escort`).
    - **Required escorts** (when `StrikeUseFlightSize=true`):
      - `strike_flights = ceil(strikers ÷ StrikeFlightSize)`
      - `required_escorts = strike_flights × EscortMinShooter`
      - **Escorts placed ≥ required_escorts** — otherwise preflight fails and CMO leaves part of the package unassigned.
    - **CMO trigger-minimum (critical):** with `StrikeUseFlightSize=true`, the engine multiplies **`StrikeMinAircraftReq × StrikeFlightSize`** into the minimum to start the mission (not the raw MinReq). Example: MinReq=8 + flight size 4 → **32** needed, while OOB has 12 → *"mission will never take off"*. Set MinReq to **number of strike flights** (e.g. 2 for 8 strikers in flights of 4), not total strikers. Escorts: similarly `EscortMinShooter × EscortFlightSizeShooter`.
    - **Example (Harmattan):** 8 strikers, `StrikeFlightSize=4` → 2 strike flights → `EscortMinShooter=2` → **minimum 4 escorts**. With only 2 escorts, CMO de-assigns the second flight (6× Rafale Sigonella).
    - **Alternative (historical OOB with few escorts):** single wave — `StrikeFlightSize = strikers` (e.g. 8) and `StrikeMinAircraftReq = strikers`; then 2 escorts suffice for the whole package (less realistic for CMO flight-size, but closer to real order of magnitude).
    - **CAP/SEAD on separate missions** do **not** count as strike escort (only `escort=true` on the Strike mission).
    - **OOB vs mission (mandatory):** `spawn_air_wing` counts must match `configure_strike_mission_options` — **exact count**: `(strikers + escorts) ≥ StrikeMinAircraftReq × StrikeFlightSize`; escorts ≥ `ceil(strikers ÷ StrikeFlightSize) × EscortMinShooter`.
    - **Preflight:** `--validate-scenario` → **`Strike OOB vs mission`** (`_validate_strike_escort_coverage`); counts all `spawn_air_wing` rows against mission options and `@strike_package`, not only carrier.
  - *Check (SEAD mission — mandatory)*: In CMO, **SEAD is always `ScenEdit_AddMission(..., 'Patrol', {type='SEAD', zone={...}})`**, never `Strike`. SEAD patrols engage **radar/emitter contacts within the zone**; SAMs on the strike target list are not automatically suppressed there.
    - **Zones**: Every `place_sam` / IADS site must fall within the bounding box of at least one SEAD patrol zone (multiple zones for dispersed SAM belts: west/east).
    - **Shooters**: Only aircraft with **ARM/SEAD loadout** on the Patrol/SEAD mission; **not** A/A-only escort on the same SEAD mission (`SEAD Escort CAP` = separate AAW patrol).
    - **Numbers**: At least `ceil(number_of_SAM_sites / 2)` SEAD shooters per attacking side; **warning** if shooters `<` number of SAM sites.
    - **Escort**: SEAD sorties still need **AAW/CAP escort** on another mission (see strike-package check); Growlers on SEAD do not count as escort.
    - **WCS land**: With side-wide `WCS TIGHT` on land: on SEAD missions often set `weapon_control_status_land=0` (FREE) via `ScenEdit_SetDoctrine({side=..., mission=...})`, otherwise HARMs often will not fire on passive SAMs.
    - **Timing vs strike (mandatory for large carrier SEAD)**: Do **not** let **Wild Weasel SEAD** and **`SEAD Escort CAP`** launch at scenario start while the strike wave is still on deck — Growlers/escort Hornets otherwise engage fighters before strike escorts/strikers are airborne. Set `ScenEdit_SetMission` with `starttime` + `TakeOffTime` (e.g. ~15–20 min before `@strike_package` TOT, after expected strike takeoff), optionally `UseFlightSize`/`FlightSize` on SEAD patrols. Document with `-- @sead_package missions=...,SEAD Escort CAP date=YYYY/MM/DD takeoff=HH:MM:SS minutes_before_strike_tot=N`. Set scenario start (`ScenEdit_SetTime`) before that takeoff. **Note**: 18 min before TOT is often **not enough transit** to the SEAD box (~270 nm from CSG) — preflight warns; intent is SEAD *start* shortly before strike, not full suppression at TOT.
    - **ISR before SEAD (mandatory when ISR orbits precede Wild Weasel)**: Patrol/Support **on-station** in ME = **`CreateMissionFlightPlan` `TIMEONTARGET`** (via `set_patrol_on_station_schedule`) — `SetMission` `TimeOnTargetStation` alone leaves ME empty. CMO backs off launch from transit; `starttime`/`TakeOffTime` alone often still launches at H-hour. Derive `isr_on_station_time = sead_on_station_time − isr_recon_min` (`cmo.hms_subtract_minutes`). Run patrol flight plans before the strike flight plan. Hold SEAD land WCS (`weapon_control_status_land=2`) until on-station; `add_mission_schedule_restore_event({ schedule_mode='on_station', ... })` re-applies flight plan at Play. Document `-- @isr_package on_station=HH:MM:SS recon_min=N` and `-- @sead_package on_station=HH:MM:SS`. Preflight: **`ISR before SEAD`**.
    - **CMO trigger-minimum (Patrol/SEAD — critical):** Same rule as carrier Strike: with `UseFlightSize=true`, the engine requires **`MinAircraftReq × FlightSize`** aircraft before the patrol launches (not the raw `MinAircraftReq`). Example: 4 Growlers, `MinAircraftReq=4`, `FlightSize=2` → trigger **8** → *"mission will never take off"* and aircraft removed. Set `MinAircraftReq` to **number of flights** (e.g. 2 for two flights of 2), not total airframe count. Preflight: **`SEAD flight size`**.
    - **Preflight**: `scripts/db_search.py --validate-scenario` also checks: `ScenEdit_SetTime` before SEAD takeoff; `@sead_package minutes_before_strike_tot` vs computed delta; SEAD not too early before TOT (before strike-escort launch); `@strike_package date` vs `DATEONTARGET`.
  - *Check (Sustainability)*: Is there enough stock for repeated sorties or prolonged combat?
- **Magazine Capacity**:
  - *Check*: Is the magazine not overfilled? (CMO simulates space usage in magazines.)
  - *Check*: Are magazines assigned to the correct weapon systems (mounts)?

## 2. Sensors & Detection (The OODA Loop)
- **Radar Horizon**: Low-altitude sensors have limited range due to earth curvature.
  - *Check*: If units fly low (sea-skimming), they may only be detected at short range. Is that intended for a surprise attack?
- **EMCON (Emission Control)**: Active radars reveal unit position.
  - *Check*: Should attackers approach **Silent** (passive sensors only) to avoid detection?
- **Weather & Time of Day**: Fog, rain, and night affect visual and IR sensors.
  - *Check*: Do units in a night scenario have the right sensors (FLIR, IR) to find targets?

## 3. Doctrine & Rules of Engagement (ROE)
- **Weapon Control Status (WCS)**:
  - `FREE`: Engage anything not identified as friendly.
  - `TIGHT`: Engage only units identified as hostile.
  - `HOLD`: Engage only in self-defense.
  - *Check*: Does WCS match the political situation of the scenario?
- **Proficiency Levels**: Affects reaction time, gunnery, and damage control.
  - *Levels*: `Novice`, `Cadet`, `Regular`, `Veteran`, `Ace`.
  - *Check*: Are proficiency levels on both sides balanced for the desired difficulty?

### Side-Specific Doctrine & Proficiency Profiles
- **Goal**: Define a "character profile" per side (Proficiency + WCS + doctrine behavior) so scenarios start tactically consistent.
- **Profile example (Israel)**:
  - `Proficiency`: `Ace`
  - `WCS`: `TIGHT`
  - Doctrine focus: conservative BVR use, `Winchester`/`Joker` discipline, controlled engagements.
- **Profile example (Syria)**:
  - `Proficiency`: `Regular`
  - `WCS`: `FREE`
  - Doctrine focus: more aggressive salvo use, `Shotgun`-like behavior, less fuel/ammo conservation.
- **Check**: Record these profiles explicitly at scenario setup and change them only deliberately as part of scenario design (not arbitrarily per prompt).

## 4. Carrier Strike Group (CSG) — Not CVN Alone
- **Reality**: A **CVN/CV** rarely deploys alone. A typical **Carrier Strike Group** includes the carrier, **1× cruiser (CG)**, and **2×+ destroyers (DDG)** for AAW/ASW/ASuW, plus often unseen support (submarine, oiler) outside the Lua OOB.
- **Why scripts sometimes had solo CVN**: simplified air-only scenario (carrier air wing + land base only), less DB lookup work; that is **not** representative of maritime order of battle.
- *Check (mandatory in preflight)*: Does each side with **carrier + air wing on carrier** (`spawn_air_wing` / `add_air_unit_checked` with `carrier.guid`) have at least **2 nearby surface escorts** (DDG/CG within ~0.55° of the carrier)? **Warning** with exactly 2 escorts; **LHA/LHD** at least 1 escort.
- *Check*: Group escorts around carrier coordinates; a lone DDG hundreds of km away does not count.
- **Formation (mandatory)**: **Full CSG** in **`form_csg_group`** (lead = CVN): CVN + DDGs + **CG** (all escorts in one surface group). **Preferred TLAM:** after `CreateMissionFlightPlan`, `setup_csg_strike_on_air_strike(CSG_GROUP, {cvn, ddg, cg, …})` unifies naval strike assets on the package mission while ships stay in formation. **Legacy:** CG solo outside group → `setup_solo_tlam_shooter(cg)`; `finalize_detached_tlam_shooter` / grouped `finalize_csg_tlam` — see `skills_cmo.md` §9.
- **TOT sync (mandatory)**: `local strike_package_tot` is the single impact time for the **whole strike package** — aircraft via `CreateMissionFlightPlan` `TIMEONTARGET`, naval via `TimeOnTargetStation` on the same mission (`set_naval_strike_schedule` / `setup_csg_strike_on_air_strike`, with `starttime` = TLAM launch). **Do not** call `CreateMissionFlightPlan` on a ship-only naval strike. Run naval asset unification **after** the aircraft flight plan; then `restore_all_spawned_air_assignments()` (adding ships / `SetMission` can clear aircraft ORBAT). `@strike_package time=` and `@naval_package tot=` must match when both are used. Preflight: **Strike TOT sync** + **TLAM schedule workflow**.
- **TOT reachability (mandatory)**: Heuristic on distance CSG/land staging → targets: TLAM launch ≥ Tomahawk cruise, carrier `StartTime`→TOT ≥ transit+deck overhead, B-52 CALCM ≥ bomber transit, SEAD takeoff vs SEAD zone distance. Preflight: **Strike TOT reachability** (ERROR/WARNING). Scenario start must be before implicit B-52 takeoff.
- *Preflight*: `scripts/db_search.py --validate-scenario` (heuristic on `place_ship` + DB `DataShip` name/type).
- **Helicopters (SH-60, etc.)**: In the **DB** on CVN/CG/DDG; spawn explicitly as `Air` with `base=ddg.guid` on **`Patrol` ASW** (torpedo loadout) and **`Patrol` naval** (Hellfire/ASuW) when the opponent has **FAC/OPV/sub**. Usually from **DDG/CG**, not CVN. **DDG 51** typically has **2** helo spots; more aircraft on one ship → CMO **`Unable to host unit`**. Preflight counts `spawn_air_wing` / `add_air_unit_checked` on `*.guid` against `DataShipAircraftFacilities` + `DataAircraftFacility` (helos: pad/hangar/deck, no catapult). Set `starttime`/`TakeOffTime` before the CSG reaches the threat coast.
- **Patrol zones at the CSG (mandatory in preflight)**: **Carrier CAP**, **Carrier AEW Orbit**, **CSG ASW Screen**, and **CSG ASuW Patrol** must sit above/near the carrier — not a fixed theater grid (e.g. 22.5°N while the CSG is at 19°N). Declare `local csg_lat, csg_lon = …` and set reference points at `csg_lat ± offset` / `csg_lon ± offset`. Preflight (`Patrol zone proximity`) fails if the zone centroid is **>1.5°** from `csg_lat/csg_lon`. **Helo patrols** (`spawn_air_wing` on host ship guid): zone centroid within **~2°** of the host ship. Theater boxes (**SEAD Escort CAP**, **Wild Weasel**, **ISR Orbit**, land-based CAP) are excluded.
- **Opponent surface threat**: For useful ASW/ASuW helos, include a **credible coastal/naval mix** (FAC, corvettes, OPVs, patrol craft, subs) in open water. Use the correct **OperatorCountry** in the DB — do not assign export hulls to a side that did not operate them. Preflight: **`Operator country`** + **`Era fit`**.
- **Cruise missiles (TLAM)**: CG/DDG (and optionally CVN if scripted) carry Tomahawk in VLS. **Preferred:** all naval strike assets on the **unified timed strike package** with explicit launch + TOT — see §1 *Naval TLAM timing*. **Legacy:** separate `<NavalStrikeName>`. Preflight warns if CSG warships lack strike assignment; **OK** when `setup_csg_strike_on_air_strike` unifies the full CSG onto the package mission.
- **F-35 variants**:
  - **F-35C** → **CVN** (catapult carrier), strike/CAP after SEAD; may share a strike mission with F/A-18 (layered risk: stealth first, Hornet mass).
  - **F-35B** → **LHA/LHD** (STOVL), **not** on Nimitz/CVN in Lua.
  - **F-35A** → land bases; do not spawn on carrier.
  - Preflight **error** for F-35A/B on `carrier.guid` in `spawn_air_wing` / `add_air_unit_checked`.
- **Strike munitions (era)**: No fixed loadout IDs — preflight classifies loadout **names**. From ~2000, no dumb-only strike; standoff (CALCM/JASSM-like) → no mandatory fighter escort, but check AAR/range.
- **Bombers on Strike**: escort/AAR rules apply by **type** (name/heuristic), not a single aircraft or loadout ID.

## 5. Unit Placement (Land vs Water)
- **Ships & submarines**: Must **not** be placed on land (`cannot place ship over land`). Use open sea (positive depth / elevation ≤ 0).
  - *Check (mandatory)*: Before `ScenEdit_AddUnit` for `Ship`/`Sub`: `World_GetElevation({latitude=..., longitude=...})`. If elevation **> 0** → location is land; pick other coordinates or verify on the map (e.g. open sea south of an island, not over the island).
  - *Check*: Submarines not too shallow (grounding) and not too deep for the DB unit; see also §6 bathymetry.
- **Facilities (airfields, SAM)**: Usually on **land**; not in open ocean unless the DB unit is a maritime facility (port/platform).
  - *Check*: See `.cursor/rules/skills_cmo.md` — land-based facilities in water often yield `Placement aborted`.
- **Preflight tooling**: `scripts/db_search.py --validate-scenario` now runs a **land/water check** for every `place_ship` / `place_sub` via the `global_land_mask` package (NOAA-derived ~1 km land/ocean mask). A naval unit whose coordinates fall on land **fails** with `Ship/sub placement over land: …` before CMO import. Install with `pip install -r requirements.txt`; if the package is missing the check degrades to a warning and is skipped. This does **not** replace the in-Lua `World_GetElevation` guard at script load (finer resolution, also handles depth/bathymetry and seabed grounding) — near-coast placements within the mask resolution can still need a manual elevation check.

## 6. Landing Facilities & Bases
- **Runway & Pad Compatibility**: Not every aircraft can land on every runway.
  - *Check*: Is the runway long enough for heavy bombers? (Large bases vs small airstrips.)
- **Carrier Operations**: Only carrier-suitable aircraft can operate from carriers.
  - *Check*: Is the aircraft classified as **Fixed Wing, Carrier Capable** (`Category = 2002`)?
  - *Check*: **F-35C** / F/A-18 / E-2 / EA-18 on CVN; **F-35B** only on LHA/LHD — see §4.
  - *Check (Technical)*: Does the ship have **Carrier Catapult** (`DataAircraftFacility Type 2005`) and **Carrier Arresting Gear** (`Type 2007`) for standard carrier aircraft?
  - *Check (mandatory in preflight)*: **Host capacity** — per `place_ship` / `place_base` with `spawn_air_wing(..., N, ..., host.guid)` or `table.field.guid`: total **N** must not exceed the sum of suitable **hangar/pad** slots (`scripts/db_search.py` → `Air host`). **Runway-only** placeholder bases (`BASE_FACILITY_DBID`, e.g. 1995) are not slot-counted (CMO does not limit there like DDG pads). `for _, k in ipairs({...}) do ... base.guid` is checked per base key.
  - *Check (STOVL/VTOL)*: For ships without catapult (e.g. LHA/LHD): Is the aircraft **VTOL** (`RunwayLength 2001`) or **STOVL** (`RunwayLength 3005`)? Does the ship have a **Ski Jump** (`Type 2006`) or **Flat-Top Deck** (`Type 6001/6002`)?
  - *Check*: Are you trying to station land-based F-15s (`Category 2001`) on a carrier? That causes errors when adding units via Lua.

## 7. Weapons & WRA (Weapon Release Authority)
- **Salvo Size**: How many missiles are fired at one target?
  - *Check*: Avoid "overkill" (e.g. 8 missiles on one small patrol boat) by setting WRA correctly in doctrine.
- **Engagement Range**: Weapons have minimum and maximum range.
  - *Check*: Is the target within the effective envelope of the chosen armament?
- **Strike ship main gun (any warship on Strike — CVN/DDG/CG)**:
  - *Check (land — mandatory)*: Main gun WRA **none** on all land target types — cruise missiles handle the strike; guns must not engage land targets when magazines are empty.
  - *Check (surface — mandatory)*: WCS **HOLD** on surface (`weapon_control_status_surface=0`); gun WRA offensive range **none**, self-defence range **max** — may fire on threatening surface contacts, must not hunt.
  - *Check (hunting — mandatory)*: `engage_opportunity_targets=false`, unit/mission `ShotgunBVR` / `Winchester` — no opportunistic surface/land gun engagements after the missile salvo. Applied via `configure_strike_ship_weapon_policy` + play-time refresh events.

## 8. Submarine Operations & ASW
- **Thermocline (Layer)**: Temperature layers in the water can bend sonar.
  - *Check*: Submarines can hide below the layer to avoid detection by surface ships. Is depth set correctly relative to the thermocline?
- **Convergence Zones (CZ)**: Sound can travel long distances in deep water.
  - *Check*: In deep water, sensors may pick up contacts at specific CZ ranges (e.g. 30 or 60 nm). Account for this in unit placement.
- **Cavitation**: Fast submarines are noisy from bubble collapse at the screw.
  - *Check*: Above ~5–10 kn (depth-dependent), a submarine is much easier to detect.
- **Battery & Propulsion (Diesel-Electric vs Nuclear)**:
  - *Check (SSK)*: Do diesel-electric submarines (e.g. Khalid or Kalvari class) have enough battery for the operation? Must they snorkel regularly to recharge? (Snorkeling greatly increases detection risk.)
  - *Check (AIP)*: Does the submarine have Air-Independent Propulsion (AIP) for longer submerged endurance?
- **Depth Settings**:
  - *Check*: Is the submarine at a safe depth for local seabed (bathymetry)? Use `World_GetElevation` to check depth.
- **Sonar Signature**:
  - *Check*: Is the submarine **Silent** (low speed, minimal emissions)? Use EMCON to avoid unnecessary active sonar.

## 9. Electronic Warfare (EW)
- **OECM vs DECM**: Offensive ECM (jammers) disrupts enemy radars but also reveals position (home-on-jam). Defensive ECM helps defeat incoming missiles.
  - *Check*: Does the strike force include dedicated EW aircraft (e.g. EA-18G Growler)? Is jamming doctrine enabled?
- **ELINT (Electronic Intelligence)**: Passive sensors can detect and identify enemy radars without being detected.
  - *Check*: Use ELINT units to map the enemy **Electronic Order of Battle (EOB)** before the attack.

## 10. Communications & Satellites
- **Comms Disruption**: Units can lose HQ contact or be jammed.
  - *Check*: Is comms jamming a factor? Do units have alternate links (e.g. satellite)?
- **Satellite Pass**: Satellites follow fixed orbits and are not always over the target area.
  - *Check*: If the scenario depends on satellite reconnaissance, do passes occur during the scenario timeframe?

## 11. Civil Traffic & Neutral Parties
- **Collateral Damage**: Hitting civilians can cost points or escalate the scenario.
  - *Check*: Is civil shipping or air traffic present to complicate target identification?
- **Identification**: Ensure neutral units are not marked hostile by mistake (WCS Tight/Hold).
- **Realistic flight paths (no aimless loiter) — mandatory**: A civilian air unit created with only `heading`/`speed` and **no plotted course** flies straight and then loiters/circles aimlessly at the last point — unrealistic and a distraction. Every civilian-side air unit must be one of:
  - *Transit (majority)*: a plotted `course` — a table of `{latitude=, longitude=}` waypoints set via `ScenEdit_SetUnit({guid=…, course={…}})` — whose **final waypoint lies outside the scenario area**, so the aircraft flies through and exits cleanly instead of circling.
  - *Landing (small minority)*: assigned a **same-side** civilian airfield (`base = <airport guid>`) with `rtb = true`, so CMO flies the approach and lands. RTB requires the airfield to be on the **same side** as the airliner — add 1–2 civilian airfields for the landers.
  - *Check (proportion)*: Only a **small portion** of civilian flights should land inside the scenario area; **most** are overflights that exit. Do not make all (or nearly all) civilian flights land.
  - *Preflight*: `scripts/db_search.py --validate-scenario` warns when a civilian side has air traffic but **no** plotted `course` and **no** `base`+`rtb` (aimless-loiter antipattern), and when civilian airfields are present but no flight is set to transit through.

## 12. Terrain & Environment (Land Operations)
- **Line of Sight (LOS)**: Mountains and buildings block land radars and weapons.
  - *Check*: Are SAM sites on strategic high ground? Are they masked by nearby hills?
- **Mobility**: Terrain types (marsh, forest, urban) affect land unit speed.
  - *Check*: Are land unit paths realistic for the terrain?

## 13. Logistics & Cargo Operations
- **Cargo Transfers**: Units can move cargo (troops, supplies) between bases and ships.
  - *Check*: Use `ScenEdit_TransferCargo` to move items. Is the receiving unit (`Facility`, `Ship`) large enough?
- **Unloading**: Unloading cargo takes time.
  - *Check*: Plan so troops are not combat-ready immediately on arrival if they still need `ScenEdit_UnloadCargo`.

## 14. Mine Warfare
- **Minefields**: Mines can passively deny areas.
  - *Check*: Use `ScenEdit_AddMinefield` to lay fields. Does the opponent have mine countermeasures to clear a path?
- **Detection**: Mines are hard to detect without specialized sonar.
  - *Check*: Does the scenario balance invisible threat vs detection capability?

## 15. Era-Appropriate OOB (No Fixed Unit List)

- **Principle**: Scenario year determines what is **realistic** — not a hardcoded "use F-35C id 824" list. Choose units via `scripts/db_search.py` within the correct `db_series`/`version`; preflight then checks fit against `scenario_year`.
- **Required in Lua**: `local scenario_year = YYYY` (e.g. 1989, 2026) alongside `db_series` / DB lock.
- **What `--validate-scenario` does (generic)**:
  - DB **commission/decommission** vs scenario year for each unique aircraft and ship in the script.
  - **Munitions era**: strike loadouts with only unguided names in modern years (see §1).
  - **Role fit**: carrier-capable variants, CSG composition, SEAD=Patrol, tanker for long-range strike — by **category/name**, not a single national inventory.
- **What it does not do**: no requirement for "at least 4× stealth" or "Super Hornet only"; it does not replace scenario design. Deliberate obsolete opponents (MiG-21, SA-2) in 2026 are allowed — expect decommission warnings unless explained in comments.
- **Workflow**: scenario_date → DB series (§18) → search suitable units → precision/standoff loadouts for that year → preflight.
- **Nationality / OperatorCountry (per hull) — mandatory**: The DB `OperatorCountry` of each spawned/placed unit must match its intended nationality. A **coalition side name** (e.g. `NATO Air Defense`, which hosts Polish, Dutch, German and US hulls) **cannot** enforce this — the side-level operator check passes anything. Declare intent explicitly with an inline `-- @nationality <Country>` annotation on each `spawn_air_wing` / `add_air_unit_checked` / `place_ship` / `place_sub` / `place_sam` line (on the same line or the line directly above the call).
  - *Preflight*: `--validate-scenario` resolves the DB `OperatorCountry` for the dbid and **errors** on mismatch. `NATO` operator matches `@nationality NATO` only; **Junkyard/Generic do not prove** a declared `@nationality` (warning). Bracketed forms (`Russia [1992-]`, `Germany [FRG/Reunified]`) and common aliases (dutch→Netherlands, polish→Poland, usa→United States, …) are normalized.
  - *Pitfall*: same airframe name, different national DBID — e.g. F-35A id **3326** is **Norwegian**, id **3902** is **Dutch**; a Polish "F-16C" labelled with a US-operated dbid is also wrong. Always confirm the operator before delivery (`db_search.py "<unit>"` → **Operator** column shows id + country name).
  - *Export proxy — when the nation is missing from the DB*: If references confirm country **X** operated a system but `db_search.py` shows **no** row with `Operator` = X, use the **exporting/supplying nation's** DBID (same equipment name/type). Annotate `-- @nationality X` (scenario truth) and `-- @export_proxy <supplier>` (DB operator). Unit stays on side X. Preflight **OK** when DB `OperatorCountry` matches `@export_proxy`. **Prefer** exporter rows over Junkyard/Generic — mounts/magazines are usually complete. Document the source in the OOB header.
  - *Junkyard/Generic — last resort only*: CMO duplicates many units under `OperatorCountry` **Junkyard** (id **9999**) or **Generic** — same `Name`, no real nation. **Prefer** a national, NATO, or **export-proxy** DBID whenever one exists (e.g. E-3C **304** = Junkyard → use **3186** NATO, **209** US, or **97** UK). Use Junkyard/Generic **only when no suitable national or exporter variant exists**; document why in the scenario header and add `-- @operator_last_resort` on the spawn line. Preflight **warns** on Junkyard/Generic (stronger warning when national alternatives exist); wrong-nationality mismatches remain **errors** unless `@export_proxy` documents the supplier, Junkyard+`@nationality` mismatch is a **warning**.

## 16. Scenario date consistency (mandatory)
- **One calendar day**: `local scenario_date = 'YYYY/MM/DD'` is the historical in-game date (must match the OOB header). Derive from it:
  - `scenario_year = tonumber(scenario_date:sub(1, 4))`
  - `strike_package_date = scenario_date`
  - `ScenEdit_SetTime` `StartDate` / `date` → `scenario_date:gsub('/', '')` (YYYYMMDD)
  - `@strike_package date=` and `@sead_package date=` → same `scenario_date`
- **Symptom**: CMO scenario clock or strike flight plans on the wrong day; era-fit checks use a different year than the scripted events.
- **Check**: `--validate-scenario` reports **`Scenario date:`** errors when `scenario_year`, `strike_package_date`, `SetTime`, or package annotations disagree with `scenario_date`. Warning if `scenario_date` is missing.

## 17. Sides must exist before use (mandatory)
- **Blank scenario rule**: Lua that builds a scenario from scratch must call `ScenEdit_AddSide({side='SideName'})` for each side **before** any `ScenEdit_SetSidePosture`, `ScenEdit_SetSideOptions`, `ScenEdit_AddMission`, `ScenEdit_SetMission`, `ScenEdit_SetDoctrine`, `spawn_air_wing` / `place_*`, or `ScenEdit_AddUnit`.
- **Symptom in CMO**: `ScenEdit_SetSidePosture 0 : ,Unable to identify Side-A!` when posture runs against a side that was never added.
- **Check**: `python scripts/db_search.py --validate-scenario generated/<file>.lua` reports **`Sides:`** errors for missing or out-of-order `ScenEdit_AddSide`. Resolves `local SIDE_X = 'France'` aliases used in AddSide/posture calls.
- **Order**: first reference to a side must be **after** its `ScenEdit_AddSide` line (not only existence).

### Geo placement — land vs water (mandatory)
- **Ship / sub** (`place_ship`, `place_sub`): coordinates must be **water** (`World_GetElevation` ≤ 0 in Lua; preflight uses `global_land_mask`). CMO: *cannot place ship over land*.
- **Facility / land unit** (`place_base`, `place_sam`, `ScenEdit_AddUnit` type `Facility` with lat/lon): must be **land** (elevation > 0). CMO: *This point appears to be underwater. Placement aborted!*
- **Check**: `--validate-scenario` reports **`Geo placement:`** for every independently placed unit (not aircraft on `base=`). Install `global-land-mask` (see `requirements.txt`).
- **Runtime**: `scenario_bootstrap.lua` — `place_base` / `place_sam` call `_require_land_placement`; `place_ship` / `place_sub` keep existing elevation guards.

### Reference points (mandatory `side=`)
- **Rule**: every `ScenEdit_AddReferencePoint({...})` must set **`side = 'SideName'`** (or `PlayerSide`). RPs are stored per side; the same `name` may exist on multiple sides.
- **Symptom in CMO**: `ScenEdit_AddReferencePoint 0 : ,Missing 'Side' please choose one of PlayerSide, France, Libya`.
- **Mission zones**: a patrol/support `zone = { 'RP-A', 'RP-B' }` on side `France` requires `AddReferencePoint` rows with **`side='France'`** and those exact names (duplicate coords on `Libya` if a Libya mission reuses the same RP names).
- **Check**: `--validate-scenario` reports **`Reference point:`** errors for missing `side=`, unknown side, or zone/RP side mismatch.

## 18. Database Series Mapping (DB3K vs CWDB)
- **Hard year rule**:
  - If `Year > 1980` → use `DB3K`.
  - If `Year < 1980` → use `CWDB`.
- **Check**: Choose the database series from scenario year first, then look up all DBIDs/loadouts/weapons within that same series.
- **Critical warning**: Never mix IDs from `DB3K` and `CWDB` in the same script or scenario object model; that can cause fatal errors/crashes in the CMO engine.

---
*Use these checks as a pre-flight checklist before delivering the final Lua script.*
