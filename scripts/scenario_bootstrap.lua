-- =============================================================================
-- scenario_bootstrap.lua — shared CMO scenario helpers (tracked in git)
-- =============================================================================
--
-- PURPOSE
--   Reusable Lua for generated/ scenarios: spawn, mission assign, CSG formation,
--   synchronized air + TLAM strike timing, nuclear strip. Single source of truth;
--   preflight (db_search.py) merges this file when validating scenarios.
--
-- WORKFLOW (authors)
--   1. Write generated/<scenario>.lua using cmo.* (see SETUP below).
--   2. Preflight: python scripts/db_search.py --validate-scenario generated/<scenario>.lua ...
--   3. CMO import: python scripts/embed_bootstrap.py generated/<scenario>.lua
--      → generated/<scenario>_import.lua  (CMO has no dofile/loadfile)
--   4. Load *_import.lua in the scenario editor (or save scenario after run).
--
-- SETUP (top of every scenario that uses bootstrap)
--   local scenario_year = 2026
--   local strike_package_date = '2026/06/01'
--   local strike_package_tot = '06:30:00'
--   local tlam_launch_time = '05:54:00'
--   local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
--   if not cmo.assert_db_series(scenario_year, 'DB3K') then return end
--   cmo.configure_strike_timing({
--       date = strike_package_date, tot = strike_package_tot,
--       tlam_launch = tlam_launch_time,
--       air_mission = 'My Air Strike', naval_mission = 'My TLAM Salvo',
--       side = 'United States',
--   })
--   -- Alias helpers you need: local place_ship = cmo.place_ship  (see REFERENCE)
--
-- PREFLIGHT ANNOTATIONS (comment lines at top of scenario; parsed by db_search.py)
--   -- @scenario_policy nuclear=false
--   -- @strike_package mission=<AirStrike> profile=standoff date=YYYY/MM/DD time=HH:MM:SS max_spread=15
--   -- @naval_package mission=<NavalStrike> launch=HH:MM:SS tot=HH:MM:SS minutes_before_strike_tot=N
--   -- @sead_package missions=Wild Weasel SEAD West takeoff=HH:MM:SS minutes_before_strike_tot=N
--   -- @strike_wave id=tlam role=naval_strike offset=0 mission=<NavalStrike>
--
-- DATE/TIME FORMATS (do not mix)
--   ScenEdit_SetTime / ScenEdit_SetMission  →  YYYY.MM.DD HH:MM:SS  (use mission_schedule_datetime)
--   CreateMissionFlightPlan DATEONTARGET    →  YYYY/MM/DD
--   Compute launch/TOT inside sync_* helpers (CMO upvalue pitfall if using outer locals).
--
-- cmo.state (shared; configure_strike_timing fills strike fields)
--   BASE_FACILITY_DBID, spawned_air_missions, mission_guid_cache,
--   strike_side, strike_package_date, strike_package_tot, tlam_launch_time,
--   STRIKE_AIR_MISSION, TLAM_STRIKE_MISSION, db_series
--
-- REFERENCE — functions on global cmo (after embed) or M internally
--
--   Setup
--     configure_strike_timing(cfg)     date, tot, tlam_launch, air_mission, naval_mission, side
--     assert_db_series(year, expected) e.g. assert_db_series(2026, 'DB3K')
--     mission_schedule_date('2026/06/01')       → '2026.06.01'
--     mission_schedule_datetime(date, '06:30:00')
--
--   Spawn (nil + ERROR print on failure; place_ship/place_sub check elevation)
--     place_base(side, name, lat, lon)   generic airfield dbid from state.BASE_FACILITY_DBID
--     place_ship, place_sub, place_sam (place_base/place_sam/ship/sub check World_GetElevation)
--     add_air_unit_checked(side, name, dbid, base_guid, loadoutid, mission, escort?)
--     spawn_air_wing(side, prefix, count, dbid, loadoutid, mission, base_guid, escort?)
--
--   Mission assign
--     assign_air_to_mission(side, guid, name, mission, strike_escort?)
--     assign_ship_to_mission(side, ship, mission, group_name?)  group_name only for legacy grouped fallback
--     refresh_spawned_air_assignments(mission_filter?)           re-assign tracked spawns
--     resolve_mission_guid(side, mission_name)
--
--   Strike timing (hardcoded — no sync_* in scenarios; see RECIPES)
--     strike_schedule_datetimes()      { tot, tlam_launch } from cmo.state date + HH:MM:SS locals
--     set_naval_strike_schedule()      one SetMission after CG assign (starttime + TimeOnTargetStation)
--     setup_solo_tlam_shooter(cg)      assign CG → set_naval_strike_schedule → weapon policy (no naval flight plan)
--     setup_solo_tlam_shooter(cg)      apply_naval(cg, nil) — CG never in CSG group
--     ungroup_unit(ship, side?)        only if already in a surface group — never on solo ships (group='none' creates a spurious ORBAT group)
--     verify_solo_tlam_shooter(cg)     log OK/WARNING if still in a surface group
--     finalize_strike_air_after_flight_plan()  updateWPtimes + restore ALL spawned air (never SetMission on air strike)
--     restore_all_spawned_air_assignments()    re-run after TLAM/naval CreateMissionFlightPlan (clears strike ORBAT)
--     add_strike_assign_restore_event(opts)     ScenLoaded + Time events re-assign strike ORBAT at Play (after CAP/SEAD launch)
--     verify_spawned_air_assignments(mission?)   log WARNING if any spawned aircraft still unassigned
--     configure_strike_mission_options(side, mission, opts)  call before spawn_air_wing (SetMission clears assignments)
--
--   CSG + TLAM
--     form_csg_group(group_name, cvn_lead, {ddg, ...})   **CVN + DDGs only** — CG TLAM shooter stays solo
--     assign_csg_group_missions(group, lead, patrol_mission, strike_unit, strike_mission, side?)
--       Patrol on LEAD only — never AssignUnitToMission(group_name, patrol).
--     setup_solo_tlam_shooter(cg_unit)                  preferred: CG not in any surface group
--     configure_tlam_shooter_weapon_policy(cg)          guns: no land; surface self-defence only; no hunt
--     assign_tlam_shooter(cg_unit, group_name?)          thin wrapper → assign_ship_to_mission
--     finalize_detached_tlam_shooter(cvn, cg, {ddgs}, CSG_GROUP, patrol?)  legacy (regroups CVN+DDGs, CG solo)
--     finalize_csg_tlam(cvn, cg, {ddgs}, CSG_GROUP, patrol)  **legacy grouped CG** — ME schedule often empty
--     restore_tlam_shooter_and_schedule(cg, group_name)
--     refresh_csg_patrol(cvn, patrol_mission)
--     verify_csg_patrol(cvn, patrol_mission)
--
--   Nuclear policy (@scenario_policy nuclear=false)
--     configure_nuclear_policy({ allowed=false, tlam_replacement_dbid? })
--     weapon_dbid_is_nuclear(dbid)  weapon_dbid_is_nuclear_cruise(dbid)  (DB sets from embed)
--     weapon_name_is_nuclear(name)  fallback when dbid unknown at runtime
--     conventional_tlam_dbid()  strip_nuclear_from_unit(unit)  after place_ship on CSG
--
-- RECIPE — CSG + solo TLAM (worked example: skills_cmo.md §9; scenarios live in generated/ and are gitignored)
--   1. Two Strike missions: air strike + naval TLAM (both type Land, OnDeactivateUassign=false)
--   2. form_csg_group(CSG_GROUP, cvn, {ddg1, ddg2}) — **no CG**; spawn CG before grouping (never add to CSG group)
--   3. Optional: assign_csg_group_missions(..., patrol on CVN lead only) — omit CSG Station Keeping if CG ME conflict
--   … air flight plan → finalize_strike_air_after_flight_plan() → CVN AEW/CAP/SEAD SetMission (cap after SEAD time) → restore strike assign …
--   7. setup_solo_tlam_shooter(cg) — no ScenEdit events; schedule via set_naval_strike_schedule at init
--   Naval strike: **no** CreateMissionFlightPlan (clears ME TOT for ship-only strikes). Schedule via sync_naval_strike_tot only.
--
-- RECIPE — air strike only (no TLAM)
--   configure_strike_timing without naval_mission; skip apply_naval / add_tlam_* ;
--   use steps 6–7 only for carrier/land strike package.
--
-- INIT LOG (Message Log during Lua import — skills_cmo.md §6)
--   ERROR:   hard failure (spawn/assign/mission missing)
--   WARNING: suspicious, no known Play-deferred workaround
--   NOTE:    expected quirk at import (e.g. solo CG + empty GetMission until Play)
--   OK:      verified success, or deferred success with explanation
--   Helpers emit NOTE/OK for empty TLAM schedule after solo assign; scenarios should
--   end with a Strike TOT summary line when tot=='' (see skills_cmo.md §6).
--
-- PITFALLS
--   • AssignUnitToMission / SetUnit(mission=): use mission **name**, not guid — guid attempts log
--     "Couldn't find the mission <guid>" even when the name works.
--   • ScenEdit_SetUnit({ group = ... }): use a **name string** to join a group. Do **not** set group='none' on ships that were never grouped — CMO creates an ORBAT group literally named "none". Use group='none' only via ungroup_unit() when leaving an existing group.
--   • CMO cannot dofile external files — use embed_bootstrap.py for import.
--   • ScenEdit_SetMission on an air Strike after aircraft are assigned clears every unit on that mission — configure strike options before spawn_air_wing; air TOT via CreateMissionFlightPlan only.
--   • CG in surface group + TLAM Strike: ME launch/TOT often empty — use setup_solo_tlam_shooter (group='').
--   • AssignUnitToMission on CG clears GetMission starttime/TOT at import — sync after assign via set_naval_strike_schedule.
--   • SEAD = Patrol type SEAD, not Strike; set starttime/TakeOffTime before strike TOT.
--
-- See also: .cursor/rules/skills_cmo.md §6–§9, logic_checks_cmo.md §4
-- =============================================================================

local M = {}

M.state = {
    BASE_FACILITY_DBID = 1995,
    spawned_air_missions = {},
    mission_guid_cache = {},
    strike_side = 'United States',
    strike_package_date = nil,
    strike_package_tot = nil,
    tlam_launch_time = nil,
    STRIKE_AIR_MISSION = nil,
    TLAM_STRIKE_MISSION = nil,
    scenario_year = nil,
    nuclear_weapons_allowed = false,
    conventional_tlam_dbid = nil,
}

function M.configure_strike_timing(cfg)
    if not cfg then
        return
    end
    M.state.strike_package_date = cfg.date or M.state.strike_package_date
    M.state.strike_package_tot = cfg.tot or M.state.strike_package_tot
    M.state.tlam_launch_time = cfg.tlam_launch or M.state.tlam_launch_time
    M.state.STRIKE_AIR_MISSION = cfg.air_mission or M.state.STRIKE_AIR_MISSION
    M.state.TLAM_STRIKE_MISSION = cfg.naval_mission or M.state.TLAM_STRIKE_MISSION
    M.state.strike_side = cfg.side or M.state.strike_side
end

function M.mission_schedule_date(date_slash)
    return date_slash:gsub('/', '.')
end

function M.mission_schedule_datetime(date_slash, time_hms)
    return M.mission_schedule_date(date_slash) .. ' ' .. time_hms
end

-- scenario_date 'YYYY/MM/DD' → ScenEdit_SetTime (dateformat YYYYMMDD; StartDate DD.MM.YYYY per API)
function M.scenario_set_start(date_slash, time_hms)
    local y, m, d = date_slash:match('^(%d+)/(%d+)/(%d+)$')
    if not y then
        print('ERROR: scenario_set_start — bad date ' .. tostring(date_slash) .. ' (want YYYY/MM/DD)')
        return
    end
    ScenEdit_SetTime({
        dateformat = 'YYYYMMDD',
        date = M.mission_schedule_date(date_slash),
        time = time_hms,
        StartDate = string.format('%s.%s.%s', d, m, y),
        StartTime = time_hms,
    })
end

function M.resolve_mission_guid(side, mission_name)
    if not mission_name or mission_name == '' then
        return nil
    end
    local key = side .. '|' .. mission_name
    if M.state.mission_guid_cache[key] then
        return M.state.mission_guid_cache[key]
    end
    local m = ScenEdit_GetMission(side, mission_name)
    if m and m.guid then
        M.state.mission_guid_cache[key] = m.guid
        return m.guid
    end
    return nil
end

function M.assign_air_to_mission(side, unit_guid, unit_name, mission_name, strike_escort)
    if not unit_guid or not mission_name then
        return false
    end
    local mission_guid = M.resolve_mission_guid(side, mission_name)
    local unit_refs = { unit_guid }
    if unit_name and unit_name ~= '' then
        table.insert(unit_refs, unit_name)
    end
    -- Mission name only — AssignUnitToMission(mission_guid) often logs "Couldn't find the mission <guid>".
    for _, uref in ipairs(unit_refs) do
        local assigned
        if strike_escort then
            assigned = ScenEdit_AssignUnitToMission(uref, mission_name, true)
        else
            assigned = ScenEdit_AssignUnitToMission(uref, mission_name)
        end
        if assigned then
            return true
        end
    end

    local u_check = ScenEdit_GetUnit({ guid = unit_guid })
    if u_check and M._unit_on_mission(u_check, mission_name) then
        return true
    end

    if not strike_escort then
        ScenEdit_SetUnit({ guid = unit_guid, side = side, mission = mission_name })
        u_check = ScenEdit_GetUnit({ guid = unit_guid })
        if u_check and M._unit_on_mission(u_check, mission_name) then
            return true
        end
    end
    return false
end

function M.restore_all_spawned_air_assignments(mission_filter)
    return M.refresh_spawned_air_assignments(mission_filter)
end

function M._restore_air_after_naval_schedule_mutation()
    if not M.state.spawned_air_missions or #M.state.spawned_air_missions == 0 then
        return 0, 0
    end
    local ok, fail = M.refresh_spawned_air_assignments(nil)
    if ok > 0 or fail > 0 then
        print('Air assign restore after naval schedule: ' .. ok .. ' OK, ' .. fail .. ' failed')
    end
    return ok, fail
end

function M._is_real_surface_group_name(grp)
    if grp == nil or grp == '' then
        return false
    end
    if string.lower(tostring(grp)) == 'none' then
        return false
    end
    return true
end

function M._unit_is_in_surface_group(ship_unit)
    return M._is_real_surface_group_name(M._unit_group_label(ship_unit))
end

function M.ungroup_unit(ship_unit, side)
    if not ship_unit or not ship_unit.guid then
        return false
    end
    if not M._unit_is_in_surface_group(ship_unit) then
        return true
    end
    side = side or M.state.strike_side or 'United States'
    ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = 'none' })
    return true
end

function M._unit_group_label(ship_unit)
    if not ship_unit or not ship_unit.guid then
        return ''
    end
    local u = ScenEdit_GetUnit({ guid = ship_unit.guid })
    return M._unit_group_name(u)
end

function M.verify_solo_tlam_shooter(ship_unit)
    if not ship_unit or not ship_unit.guid then
        return false
    end
    local grp = M._unit_group_label(ship_unit)
    if not M._is_real_surface_group_name(grp) then
        print('OK: ' .. tostring(ship_unit.name) .. ' solo (no surface group)')
        return true
    end
    print('WARNING: ' .. tostring(ship_unit.name) .. ' still in group "' .. grp ..
        '" — expected solo for TLAM ME schedule')
    M.ungroup_unit(ship_unit)
    return false
end

function M.assign_ship_to_mission(side, ship_unit, mission_name, group_name)
    if not ship_unit or not ship_unit.guid or not mission_name then
        return false
    end
    local mission_guid = M.resolve_mission_guid(side, mission_name)
    local function assigned()
        local u = ScenEdit_GetUnit({ guid = ship_unit.guid })
        if u then
            local on_mission = u.assignedMission or u.mission or ''
            if on_mission ~= '' then
                if on_mission == mission_name or on_mission == (mission_guid or '') then
                    return true
                end
                if string.find(string.lower(tostring(on_mission)), string.lower(mission_name), 1, true) then
                    return true
                end
            end
        end
        local m = ScenEdit_GetMission(side, mission_name)
        if m and m.unitlist then
            for _, ug in ipairs(m.unitlist) do
                if ug == ship_unit.guid then
                    return true
                end
            end
        end
        return false
    end

    local grp = (group_name and group_name ~= '') and group_name or nil
    local unit_refs = { ship_unit.guid }
    if ship_unit.name and ship_unit.name ~= '' then
        table.insert(unit_refs, ship_unit.name)
    end

    -- Solo (no group_name): assign without touching group; ungroup only if already in a CSG formation.
    if not grp then
        if M._unit_is_in_surface_group(ship_unit) then
            M.ungroup_unit(ship_unit, side)
        end
        for _, uref in ipairs(unit_refs) do
            ScenEdit_AssignUnitToMission(uref, mission_name)
        end
        if assigned() then
            return true
        end
        ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, mission = mission_name })
        if assigned() then
            return true
        end
        local u_wrap = ScenEdit_GetUnit({ guid = ship_unit.guid })
        if u_wrap then
            u_wrap.mission = mission_name
            if assigned() then
                return true
            end
        end
        return assigned()
    end

    -- Grouped (legacy): AssignUnitToMission then group-only SetUnit — never mission+group in one SetUnit.
    if grp and grp ~= '' then
        for _, uref in ipairs(unit_refs) do
            ScenEdit_AssignUnitToMission(uref, mission_name)
        end
        if assigned() then
            ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            return assigned()
        end
    end

    ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, mission = mission_name })
    if assigned() then
        return true
    end

    for _, uref in ipairs(unit_refs) do
        if ScenEdit_AssignUnitToMission(uref, mission_name) then
            if grp and grp ~= '' then
                ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            end
            return true
        end
    end

    local u_wrap = ScenEdit_GetUnit({ guid = ship_unit.guid })
    if u_wrap then
        u_wrap.mission = mission_name
        if assigned() then
            return true
        end
    end

    if grp and grp ~= '' then
        M.ungroup_unit(ship_unit, side)
        ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, mission = mission_name })
        if assigned() then
            ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            return assigned()
        end
        for _, uref in ipairs(unit_refs) do
            ScenEdit_AssignUnitToMission(uref, mission_name)
        end
        if assigned() then
            ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            return assigned()
        end
        ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
    end

    return assigned()
end

function M.refresh_spawned_air_assignments(mission_filter)
    local ok_n, fail_n = 0, 0
    for _, entry in ipairs(M.state.spawned_air_missions) do
        if not mission_filter or entry.mission == mission_filter then
            if M.assign_air_to_mission(entry.side, entry.guid, entry.name, entry.mission, entry.escort) then
                ok_n = ok_n + 1
            else
                fail_n = fail_n + 1
            end
        end
    end
    return ok_n, fail_n
end

function M.configure_strike_mission_options(side, mission_name, opts)
    side = side or M.state.strike_side
    mission_name = mission_name or M.state.STRIKE_AIR_MISSION
    if not mission_name or not opts then
        return false
    end
    if opts.OnDeactivateUassign == nil then
        opts.OnDeactivateUassign = false
    end
    ScenEdit_SetMission(side, mission_name, opts)
    return true
end

function M.strike_schedule_datetimes()
    local date = M.state.strike_package_date
    return {
        tot = M.mission_schedule_datetime(date, M.state.strike_package_tot),
        tlam_launch = M.mission_schedule_datetime(date, M.state.tlam_launch_time),
    }
end

function M.set_naval_strike_schedule(side, mission_name, launch_dt, tot_dt)
    side = side or M.state.strike_side or 'United States'
    mission_name = mission_name or M.state.TLAM_STRIKE_MISSION
    if not mission_name or not launch_dt or not tot_dt then
        return false
    end
    ScenEdit_SetMission(side, mission_name, {
        starttime = launch_dt,
        TimeOnTargetStation = tot_dt,
        OnDeactivateUassign = false,
        isactive = true,
    })
    return true
end

-- Deprecated: scenarios use hardcoded strike_package_tot + set_naval_strike_schedule. Kept for legacy callers.
function M.sync_air_strike_tot()
    return
end

function M.sync_naval_strike_tot()
    local sched = M.strike_schedule_datetimes()
    M.set_naval_strike_schedule(M.state.strike_side, M.state.TLAM_STRIKE_MISSION, sched.tlam_launch, sched.tot)
    return sched.tlam_launch, sched.tot
end

function M.restore_naval_strike_schedule()
    return M.sync_naval_strike_tot()
end

function M._reassert_naval_strike_schedule(side, naval_mission, launch_dt, tot_dt)
    return M.set_naval_strike_schedule(side, naval_mission, launch_dt, tot_dt)
end

function M._assign_solo_tlam_shooter(side, ship_unit, mission_name)
    if not ship_unit or not ship_unit.guid or not mission_name then
        return false
    end
    -- SetUnit(mission=) first — AssignUnitToMission clears starttime/TOT on naval Strike.
    ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, mission = mission_name })
    local u = ScenEdit_GetUnit({ guid = ship_unit.guid })
    if M._unit_mission_label(u) == '' then
        ScenEdit_AssignUnitToMission(ship_unit.guid, mission_name)
    end
    u = ScenEdit_GetUnit({ guid = ship_unit.guid })
    if M._unit_mission_label(u) == '' then
        return false
    end
    local m = ScenEdit_GetMission(side, mission_name)
    if m and m.unitlist then
        for _, ug in ipairs(m.unitlist) do
            if ug == ship_unit.guid then
                return true
            end
        end
    end
    return M._unit_mission_label(u) ~= ''
end

function M._naval_flight_plan_opts()
    -- Same TOT anchor as air CreateMissionFlightPlan — no TAKEOFFTIME (that becomes ME TakeOffTime, not TOT sync).
    return {
        DATEONTARGET = M.state.strike_package_date,
        TIMEONTARGET = M.state.strike_package_tot,
    }
end

function M._run_naval_mission_flight_plan(side, naval_mission)
    local fp_opts = M._naval_flight_plan_opts()
    local m = ScenEdit_GetMission(side, naval_mission)
    if m and m.createFlightPlans then
        local ok_fp = pcall(function() m:createFlightPlans(fp_opts) end)
        if ok_fp then
            pcall(function() m:updateWPtimes() end)
            M.sync_naval_strike_tot()
            return
        end
    end
    ScenEdit_CreateMissionFlightPlan(side, naval_mission, fp_opts)
    m = ScenEdit_GetMission(side, naval_mission)
    if m then
        pcall(function() m:updateWPtimes() end)
    end
    M.sync_naval_strike_tot()
end

function M._mission_field_nonempty(value)
    if value == nil then
        return false
    end
    local s = tostring(value)
    return s ~= '' and s ~= 'nil'
end

function M._mission_starttime_set(m, expected)
    if not m or not expected or expected == '' then
        return false
    end
    return M._mission_field_nonempty(m.starttime)
end

function M._unit_mission_label(unit)
    if not unit then
        return ''
    end
    local mref = unit.assignedMission or unit.mission
    if mref == nil or mref == '' then
        return ''
    end
    if type(mref) == 'table' then
        return tostring(mref.name or mref.guid or '')
    end
    return tostring(mref)
end

function M._unit_on_mission(unit, mission_name)
    if not unit or not mission_name or mission_name == '' then
        return false
    end
    local label = M._unit_mission_label(unit)
    if label == '' then
        return false
    end
    if string.find(string.lower(label), string.lower(mission_name), 1, true) then
        return true
    end
    return false
end

-- ScenEdit_SetUnit({ group = ... }) requires a group name string — GetUnit().group is often a SurfaceGroup wrapper.
function M._unit_group_name(unit)
    if not unit then
        return ''
    end
    local g = unit.groupname or unit.group
    if g == nil or g == '' then
        return ''
    end
    if type(g) == 'string' then
        return g
    end
    if type(g) == 'table' then
        local n = g.name or g.Name or ''
        if n ~= '' then
            return tostring(n)
        end
        return ''
    end
    return tostring(g)
end

function M.apply_naval_strike_flight_plan(shooter_unit, group_name)
    if not group_name or group_name == '' then
        return M.setup_solo_tlam_shooter(shooter_unit)
    end
    local side = M.state.strike_side
    local naval_mission = M.state.TLAM_STRIKE_MISSION
    local sched = M.strike_schedule_datetimes()
    if shooter_unit and M._unit_is_in_surface_group(shooter_unit) then
        M.ungroup_unit(shooter_unit, side)
    end
    local shooter_ok = shooter_unit and
        M.assign_ship_to_mission(side, shooter_unit, naval_mission, group_name) or false
    if shooter_ok then
        M.set_naval_strike_schedule(side, naval_mission, sched.tlam_launch, sched.tot)
    end
    return shooter_ok
end

function M.ensure_naval_strike_me_schedule()
    local sched = M.strike_schedule_datetimes()
    local ok = M.set_naval_strike_schedule(
        M.state.strike_side, M.state.TLAM_STRIKE_MISSION, sched.tlam_launch, sched.tot)
    M._restore_air_after_naval_schedule_mutation()
    return ok
end

-- TLAM shooter weapon policy: Tomahawk for land strike; main gun never on land; surface gun
-- only when threatened (WCS HOLD + WRA self-defence); no opportunistic hunting.
M.WRA_GUN_LAND_BLOCK = { 'none', 'none', 'none', 'none' }
M.WRA_GUN_SURFACE_SELF_DEFENSE = { 'inherit', 'inherit', 'none', 'max' }

M.LAND_STRIKE_WRA_TARGET_TYPES = {
    'Land_Contact_Unknown_Type',
    'Land_Structure_Soft_Unspecified',
    'Land_Structure_Soft_Building_Surface',
    'Land_Structure_Soft_Building_Reveted',
    'Land_Structure_Soft_Structure_Open',
    'Land_Structure_Soft_Structure_Reveted',
    'Land_Structure_Hardened_Unspecified',
    'Land_Structure_Hardened_Building_Surface',
    'Land_Structure_Hardened_Building_Reveted',
    'Land_Structure_Hardened_Building_Bunker',
    'Land_Structure_Hardened_Building_Underground',
    'Land_Structure_Hardened_Structure_Open',
    'Land_Structure_Hardened_Structure_Reveted',
    'Runway_Facility_Unspecified',
    'Runway',
    'Runway_Grade_Taxiway',
    'Runway_Access_Point',
    'Mobile_Target_Soft_Unspecified',
    'Mobile_Target_Soft_Mobile_Vehicle',
    'Mobile_Target_Soft_Mobile_Personnel',
    'Mobile_Target_Hardened_Unspecified',
    'Mobile_Target_Hardened_Mobile_Vehicle',
    'Emitter_Unspecified',
    'Emitter_Radar',
    'Emitter_Jammer',
    'Air_Base_Single_Unit_Airfield',
    'Underwater_Structure',
}

M.SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES = {
    'Surface_Contact_Unknown_Type',
    'Ship_Unspecified',
    'Submarine_Surfaced',
    'Ship_Surface_Combatant_0_500_tons',
    'Ship_Surface_Combatant_501_1500_tons',
    'Ship_Surface_Combatant_1501_5000_tons',
    'Ship_Surface_Combatant_5001_10000_tons',
    'Ship_Surface_Combatant_10001_25000_tons',
    'Ship_Surface_Combatant_25001_45000_tons',
    'Ship_Surface_Combatant_45001_95000_tons',
    'Ship_Surface_Combatant_95000_tons',
}

function M._mount_is_strike_gun(mount)
    if not mount or not mount.name then
        return false
    end
    local u = string.upper(tostring(mount.name))
    if string.find(u, 'PHALANX') or string.find(u, 'CIWS') or string.find(u, 'SEA RAM') or
        string.find(u, 'RAM MOUNT') or string.find(u, 'GOALKEEPER') then
        return false
    end
    if string.find(u, 'MK45') or string.find(u, 'MK 45') or string.find(u, '5"/') or
        string.find(u, '5 INCH') or string.find(u, 'OTO') or string.find(u, '76MM') or
        string.find(u, 'NAVAL GUN') then
        return true
    end
    if mount.weapons then
        for _, w in ipairs(mount.weapons) do
            local wn = w.name and string.upper(tostring(w.name)) or ''
            if wn ~= '' and string.find(wn, 'SHELL') and not string.find(wn, 'GATLING') then
                return true
            end
        end
    end
    return false
end

function M._collect_strike_gun_weapon_dbids(unit_wrap)
    local dbids = {}
    if not unit_wrap or not unit_wrap.mounts then
        return dbids
    end
    for _, mount in ipairs(unit_wrap.mounts) do
        if M._mount_is_strike_gun(mount) and mount.weapons then
            for _, w in ipairs(mount.weapons) do
                local dbid = w.wpn_dbid or w.dbid
                if dbid then
                    dbids[dbid] = true
                end
            end
        end
    end
    return dbids
end

function M._apply_tlam_shooter_gun_wra(unit_guid, side, gun_dbids)
    local land_rules, surface_rules = 0, 0
    for dbid, _ in pairs(gun_dbids) do
        for _, target_type in ipairs(M.LAND_STRIKE_WRA_TARGET_TYPES) do
            local ok = pcall(function()
                ScenEdit_SetDoctrineWRA({
                    side = side,
                    guid = unit_guid,
                    weapon_id = tostring(dbid),
                    target_type = target_type,
                }, M.WRA_GUN_LAND_BLOCK)
            end)
            if ok then
                land_rules = land_rules + 1
            end
        end
        for _, target_type in ipairs(M.SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES) do
            local ok = pcall(function()
                ScenEdit_SetDoctrineWRA({
                    side = side,
                    guid = unit_guid,
                    weapon_id = tostring(dbid),
                    target_type = target_type,
                }, M.WRA_GUN_SURFACE_SELF_DEFENSE)
            end)
            if ok then
                surface_rules = surface_rules + 1
            end
        end
    end
    return land_rules, surface_rules
end

function M.configure_naval_strike_doctrine(side)
    side = side or M.state.strike_side or 'United States'
    local mission = M.state.TLAM_STRIKE_MISSION
    if not mission then
        return false
    end
    ScenEdit_SetDoctrine({ side = side, mission = mission }, {
        weapon_state_planned = 'ShotgunBVR',
        weapon_state_rtb = 'Winchester',
        gun_strafing = 0,
        engage_opportunity_targets = false,
    })
    return true
end

function M.configure_tlam_shooter_weapon_policy(unit, opts)
    opts = opts or {}
    if not unit or not unit.guid then
        return 0, 0
    end
    local side = opts.side or M.state.strike_side or 'United States'
    local u = ScenEdit_GetUnit({ guid = unit.guid })
    if not u then
        return 0, 0
    end
    -- Land WCS stays inherited (TIGHT) so TLAM can engage assigned land targets; guns blocked via WRA.
    ScenEdit_SetDoctrine({ side = side, guid = unit.guid }, {
        engage_opportunity_targets = false,
        gun_strafing = 0,
        weapon_control_status_surface = 0,
        weapon_control_status_subsurface = 0,
    })
    local land_rules, surface_rules = M._apply_tlam_shooter_gun_wra(
        unit.guid, side, M._collect_strike_gun_weapon_dbids(u))
    if land_rules > 0 or surface_rules > 0 then
        print('OK: ' .. tostring(u.name or unit.guid) ..
            ' — TLAM shooter guns: land blocked (' .. land_rules ..
            ' WRA), surface self-defence only (' .. surface_rules .. ' WRA)')
    end
    return land_rules, surface_rules
end

M.disable_strike_guns_on_unit = M.configure_tlam_shooter_weapon_policy

function M.build_tlam_shooter_weapon_policy_script(ship_unit)
    if not ship_unit or not ship_unit.guid then
        return ''
    end
    local side = M._q_lua_str(M.state.strike_side or 'United States')
    local guid = ship_unit.guid
    local mission = M._q_lua_str(M.state.TLAM_STRIKE_MISSION or '')
    local land_types, surface_types = {}, {}
    for _, t in ipairs(M.LAND_STRIKE_WRA_TARGET_TYPES) do
        table.insert(land_types, "'" .. M._q_lua_str(t) .. "'")
    end
    for _, t in ipairs(M.SURFACE_SELF_DEFENSE_WRA_TARGET_TYPES) do
        table.insert(surface_types, "'" .. M._q_lua_str(t) .. "'")
    end
    return table.concat({
        'do',
        "  local u = ScenEdit_GetUnit({guid='" .. guid .. "'})",
        '  if not u or not u.mounts then break end',
        '  local wra_land = { "none", "none", "none", "none" }',
        '  local wra_surface = { "inherit", "inherit", "none", "max" }',
        '  local land_types = { ' .. table.concat(land_types, ', ') .. ' }',
        '  local surface_types = { ' .. table.concat(surface_types, ', ') .. ' }',
        "  ScenEdit_SetDoctrine({side='" .. side .. "', guid='" .. guid .. "'}, {engage_opportunity_targets=false, gun_strafing=0, weapon_control_status_surface=0, weapon_control_status_subsurface=0})",
        "  if '" .. mission .. "' ~= '' then",
        "    ScenEdit_SetDoctrine({side='" .. side .. "', mission='" .. mission .. "'}, {weapon_state_planned='ShotgunBVR', weapon_state_rtb='Winchester', gun_strafing=0, engage_opportunity_targets=false})",
        '  end',
        '  for _, mount in ipairs(u.mounts) do',
        '    local mn = mount.name and string.upper(tostring(mount.name)) or ""',
        '    local is_gun = false',
        '    if not string.find(mn, "PHALANX") and not string.find(mn, "CIWS") and not string.find(mn, "SEA RAM") then',
        '      if string.find(mn, "MK45") or string.find(mn, "MK 45") or string.find(mn, \'5"/\') or string.find(mn, "OTO") or string.find(mn, "76MM") then is_gun = true end',
        '    end',
        '    if is_gun and mount.weapons then',
        '      for _, w in ipairs(mount.weapons) do',
        '        local dbid = w.wpn_dbid or w.dbid',
        '        if dbid then',
        '          for _, tt in ipairs(land_types) do',
        '            pcall(function() ScenEdit_SetDoctrineWRA({side="' .. side .. '", guid="' .. guid .. '", weapon_id=tostring(dbid), target_type=tt}, wra_land) end)',
        '          end',
        '          for _, tt in ipairs(surface_types) do',
        '            pcall(function() ScenEdit_SetDoctrineWRA({side="' .. side .. '", guid="' .. guid .. '", weapon_id=tostring(dbid), target_type=tt}, wra_surface) end)',
        '          end',
        '        end',
        '      end',
        '    end',
        '  end',
        'end',
    }, '\r\n')
end

M.build_disable_strike_guns_script = M.build_tlam_shooter_weapon_policy_script

-- CG 52 solo op Caribbean TLAM Salvo (niet in CSG-groep — CMO ME toont launch/TOT betrouwbaarder).
function M.setup_solo_tlam_shooter(ship_unit)
    if not ship_unit or not ship_unit.guid then
        return false
    end
    local side = M.state.strike_side or 'United States'
    local naval_mission = M.state.TLAM_STRIKE_MISSION
    local sched = M.strike_schedule_datetimes()
    M.configure_naval_strike_doctrine(side)
    if M._unit_is_in_surface_group(ship_unit) then
        M.ungroup_unit(ship_unit, side)
    end
    local ok = M._assign_solo_tlam_shooter(side, ship_unit, naval_mission)
    if ok then
        print('TLAM shooter assigned: ' .. tostring(ship_unit.name) .. ' (solo — not in CSG group)')
        M.set_naval_strike_schedule(side, naval_mission, sched.tlam_launch, sched.tot)
        print('OK: ' .. naval_mission .. ' launch=' .. tostring(sched.tlam_launch) ..
            ' TOT=' .. tostring(sched.tot))
    else
        print('ERROR: TLAM shooter assign failed: ' .. tostring(ship_unit.name))
    end
    M.configure_tlam_shooter_weapon_policy(ship_unit)
    M.verify_solo_tlam_shooter(ship_unit)
    M.verify_tlam_mission_has_shooter(ship_unit)
    return ok
end

function M.refresh_csg_patrol(lead_unit, patrol_mission, side)
    side = side or M.state.strike_side or 'United States'
    if not lead_unit or not lead_unit.guid or not patrol_mission then
        return false
    end
    if ScenEdit_AssignUnitToMission(lead_unit.guid, patrol_mission) then
        return true
    end
    ScenEdit_SetUnit({ guid = lead_unit.guid, side = side, mission = patrol_mission })
    return true
end

function M.verify_csg_patrol(lead_unit, patrol_mission)
    if not lead_unit or not lead_unit.guid then
        print('WARNING: CSG patrol verify — no group lead')
        return false
    end
    local u = ScenEdit_GetUnit({ guid = lead_unit.guid })
    local label = M._unit_mission_label(u)
    if label ~= '' and string.find(string.lower(label), string.lower(patrol_mission), 1, true) then
        print('OK: CSG lead ' .. tostring(lead_unit.name) .. ' on patrol ' .. patrol_mission)
        return true
    end
    print('ERROR: CSG lead ' .. tostring(lead_unit.name) .. ' not on ' .. patrol_mission ..
        ' (mission="' .. label .. '")')
    return false
end

-- SetMission then assign — inline at init via set_naval_strike_schedule / run_tlam_restore.
function M._q_lua_str(s)
    return tostring(s):gsub("'", "\\'")
end

function M.run_tlam_restore(ship_unit, group_name)
    if not ship_unit or not ship_unit.guid or not M.state.TLAM_STRIKE_MISSION then
        return false
    end
    local side = M.state.strike_side
    local mission = M.state.TLAM_STRIKE_MISSION
    if M._is_real_surface_group_name(group_name) and M._unit_is_in_surface_group(ship_unit) then
        M.ungroup_unit(ship_unit, side)
    end
    local sched = M.strike_schedule_datetimes()
    local ok
    if group_name and group_name ~= '' then
        ok = M.assign_ship_to_mission(side, ship_unit, mission, group_name)
    else
        ok = M._assign_solo_tlam_shooter(side, ship_unit, mission)
    end
    M.set_naval_strike_schedule(side, mission, sched.tlam_launch, sched.tot)
    M.configure_naval_strike_doctrine(side)
    M.configure_tlam_shooter_weapon_policy(ship_unit, { side = side })
    local m = ScenEdit_GetMission(side, mission)
    if M._mission_field_nonempty(m and m.TimeOnTargetStation) then
        print('OK: TLAM restore — TOT=' .. tostring(m.TimeOnTargetStation) ..
            ' starttime=' .. tostring(m.starttime or ''))
    elseif ok then
        print('NOTE: TLAM restore — shooter assigned; schedule may stay empty in GetMission until Play (solo CG).')
    end
    return ok
end

function M.restore_tlam_shooter_and_schedule(ship_unit, group_name)
    return M.run_tlam_restore(ship_unit, group_name)
end

function M.finalize_csg_tlam(lead_unit, cg_unit, escort_units, group_name, patrol_mission)
    if not lead_unit or not cg_unit then
        return false
    end
    escort_units = escort_units or {}
    local members = { cg_unit }
    for _, u in ipairs(escort_units) do
        if u and u.guid then
            table.insert(members, u)
        end
    end
    M.form_csg_group(group_name, lead_unit, members)
    if patrol_mission and patrol_mission ~= '' then
        M.refresh_csg_patrol(lead_unit, patrol_mission)
    end
    local cg_u = ScenEdit_GetUnit({ guid = cg_unit.guid })
    local cg_mission = M._unit_mission_label(cg_u)
    local naval_mission = M.state.TLAM_STRIKE_MISSION
    local cg_on_tlam = cg_mission ~= '' and
        string.find(string.lower(cg_mission), string.lower(naval_mission), 1, true)
    if cg_on_tlam then
        ScenEdit_SetUnit({ guid = cg_unit.guid, side = M.state.strike_side, group = group_name })
        M.sync_naval_strike_tot()
    else
        M.restore_tlam_shooter_and_schedule(cg_unit, group_name)
    end
    if patrol_mission and patrol_mission ~= '' then
        M.verify_csg_patrol(lead_unit, patrol_mission)
    end
    M.verify_tlam_mission_has_shooter(cg_unit)
    M.sync_naval_strike_tot()
    local m = ScenEdit_GetMission(M.state.strike_side, naval_mission)
    if M._mission_field_nonempty(m and m.TimeOnTargetStation) then
        print('OK: TLAM finalize — TOT=' .. tostring(m.TimeOnTargetStation) ..
            ' starttime=' .. tostring(m.starttime or ''))
        return true
    end
    print('OK: TLAM finalize — schedule empty in GetMission (grouped CG); sim/ME may differ.')
    return true
end

-- CG outside CSG group: ME shows TLAM unitlist + launch/TOT; CSG stays CVN + DDGs on patrol.
function M.finalize_detached_tlam_shooter(lead_unit, cg_unit, escort_units, csg_group_name, patrol_mission)
    if not lead_unit or not cg_unit then
        return false
    end
    escort_units = escort_units or {}
    M.form_csg_group(csg_group_name, lead_unit, escort_units)
    if patrol_mission and patrol_mission ~= '' then
        M.refresh_csg_patrol(lead_unit, patrol_mission)
    end
    M.apply_naval_strike_flight_plan(cg_unit, nil)
    if patrol_mission and patrol_mission ~= '' then
        M.verify_csg_patrol(lead_unit, patrol_mission)
    end
    M.verify_tlam_mission_has_shooter(cg_unit)
    local m = ScenEdit_GetMission(M.state.strike_side, M.state.TLAM_STRIKE_MISSION)
    if M._mission_field_nonempty(m and m.TimeOnTargetStation) then
        print('OK: TLAM detached finalize — TOT=' .. tostring(m.TimeOnTargetStation) ..
            ' starttime=' .. tostring(m.starttime or ''))
        return true
    end
    print('WARNING: TLAM detached finalize — schedule still empty in GetMission (check ME manually).')
    return false
end

function M.sync_strike_package_tot()
    M.sync_naval_strike_tot()
end

function M.finalize_strike_air_after_flight_plan()
    local air_mission = M.state.STRIKE_AIR_MISSION
    local m = ScenEdit_GetMission(M.state.strike_side, air_mission)
    if m and m.updateWPtimes then
        local ok_wp, err_wp = pcall(function()
            m:updateWPtimes()
        end)
        if not ok_wp then
            print('WARNING: updateWPtimes failed: ' .. tostring(err_wp))
        end
    end
    -- CreateMissionFlightPlan may drop assignments; restore all spawned aircraft (never SetMission on air strike here).
    local ok, fail = M.refresh_spawned_air_assignments(nil)
    if fail > 0 then
        ok, fail = M.refresh_spawned_air_assignments(nil)
    end
    print('Air assign after flight plan: ' .. ok .. ' OK, ' .. fail .. ' failed')
    return ok, fail
end

function M.verify_spawned_air_assignments(mission_filter)
    mission_filter = mission_filter or M.state.STRIKE_AIR_MISSION
    local missing = 0
    local checked = 0
    for _, entry in ipairs(M.state.spawned_air_missions or {}) do
        if not mission_filter or entry.mission == mission_filter then
            checked = checked + 1
            local u = ScenEdit_GetUnit({ guid = entry.guid })
            if not u or not M._unit_on_mission(u, entry.mission) then
                missing = missing + 1
            end
        end
    end
    if missing > 0 then
        print('WARNING: ' .. missing .. ' aircraft unassigned (checked ' .. checked ..
            (mission_filter and (' on ' .. mission_filter) or '') .. ')')
    elseif checked > 0 then
        print('OK: All ' .. checked .. ' spawned aircraft assigned' ..
            (mission_filter and (' on ' .. mission_filter) or ''))
    end
    return missing, checked
end

-- Play-time: carrier air ops can drop strike ORBAT when CAP/SEAD launch — re-assign via separate events (never SetMission on strike).
function M.build_strike_assign_restore_script(mission_filter)
    mission_filter = mission_filter or M.state.STRIKE_AIR_MISSION
    local side = M.state.strike_side or 'United States'
    local q = M._q_lua_str
    local lines = { "print('NOTE: Strike assign restore event')" }
    local count = 0
    for _, entry in ipairs(M.state.spawned_air_missions or {}) do
        if not mission_filter or entry.mission == mission_filter then
            count = count + 1
            local mission = entry.mission
            local entry_side = entry.side or side
            local guid = entry.guid
            if entry.escort then
                table.insert(lines,
                    "ScenEdit_AssignUnitToMission('" .. guid .. "', '" .. q(mission) .. "', true)")
                if entry.name and entry.name ~= '' then
                    table.insert(lines,
                        "ScenEdit_AssignUnitToMission('" .. q(entry.name) .. "', '" .. q(mission) .. "', true)")
                end
            else
                table.insert(lines,
                    "ScenEdit_AssignUnitToMission('" .. guid .. "', '" .. q(mission) .. "')")
                if entry.name and entry.name ~= '' then
                    table.insert(lines,
                        "ScenEdit_AssignUnitToMission('" .. q(entry.name) .. "', '" .. q(mission) .. "')")
                end
                table.insert(lines,
                    "ScenEdit_SetUnit({guid='" .. guid .. "', side='" .. q(entry_side) ..
                    "', mission='" .. q(mission) .. "'})")
            end
        end
    end
    if count == 0 then
        return ''
    end
    table.insert(lines, "print('OK: Strike assign restore — " .. count .. " aircraft')")
    return table.concat(lines, '\r\n')
end

function M.run_strike_assign_restore(mission_filter)
    mission_filter = mission_filter or M.state.STRIKE_AIR_MISSION
    local ok, fail = M.refresh_spawned_air_assignments(mission_filter)
    if ok > 0 or fail > 0 then
        print('Strike assign restore inline: ' .. ok .. ' OK, ' .. fail .. ' failed')
    end
    return ok, fail
end

function M.add_strike_assign_restore_event(opts)
    opts = opts or {}
    local mission_filter = opts.mission or M.state.STRIKE_AIR_MISSION
    local script = M.build_strike_assign_restore_script(mission_filter)
    if script == '' then
        print('WARNING: Strike assign restore — no spawned aircraft for ' .. tostring(mission_filter))
        return false
    end

    if opts.run_now then
        M.run_strike_assign_restore(mission_filter)
    end

    local base_event = opts.event_name or 'Strike assign restore'
    local start_date = opts.start_date or M.state.strike_package_date
    local restore_times = opts.restore_times or { '00:00:05' }

    for _, suffix in ipairs({ '', ' (load)', ' (time)' }) do
        local label = base_event .. suffix
        pcall(function() ScenEdit_SetEvent(label, { mode = 'remove' }) end)
        pcall(function() ScenEdit_SetTrigger({ mode = 'remove', name = label .. ' trigger' }) end)
        pcall(function() ScenEdit_SetAction({ mode = 'remove', name = label .. ' action' }) end)
    end
    for i = 1, #restore_times do
        local label = base_event .. ' (time ' .. i .. ')'
        pcall(function() ScenEdit_SetEvent(label, { mode = 'remove' }) end)
        pcall(function() ScenEdit_SetTrigger({ mode = 'remove', name = label .. ' trigger' }) end)
        pcall(function() ScenEdit_SetAction({ mode = 'remove', name = label .. ' action' }) end)
    end

    local function register_event(event_label, trigger_name, trigger_def)
        local action_name = event_label .. ' action'
        ScenEdit_SetTrigger(trigger_def)
        ScenEdit_SetAction({
            mode = 'add',
            type = 'LuaScript',
            name = action_name,
            ScriptText = script,
        })
        ScenEdit_SetEvent(event_label, {
            mode = 'add',
            Description = event_label,
            IsActive = true,
            IsRepeatable = false,
            IsShown = true,
        })
        ScenEdit_SetEventTrigger(event_label, { mode = 'add', name = trigger_name })
        ScenEdit_SetEventAction(event_label, { mode = 'add', name = action_name })
    end

    register_event(base_event .. ' (load)', base_event .. ' load trigger', {
        mode = 'add',
        type = 'ScenLoaded',
        name = base_event .. ' load trigger',
    })

    local time_labels = {}
    for i, hhmmss in ipairs(restore_times) do
        local dt = M.mission_schedule_datetime(start_date, hhmmss)
        local event_label = base_event .. ' (time ' .. i .. ')'
        register_event(event_label, event_label .. ' trigger', {
            mode = 'add',
            type = 'Time',
            name = event_label .. ' trigger',
            Time = dt,
        })
        table.insert(time_labels, dt)
    end

    print('OK: Strike assign restore events "' .. base_event .. '" — ScenLoaded + ' ..
        #restore_times .. ' Time trigger(s)' ..
        (#time_labels > 0 and (' | times=' .. table.concat(time_labels, ', ')) or ''))
    return true
end

function M.assign_tlam_shooter(ship_unit, group_name)
    if not ship_unit or not M.state.TLAM_STRIKE_MISSION then
        return false
    end
    return M.assign_ship_to_mission(
        M.state.strike_side,
        ship_unit,
        M.state.TLAM_STRIKE_MISSION,
        group_name
    )
end

function M.verify_tlam_mission_has_shooter(ship_unit)
    local side = M.state.strike_side
    local naval_mission = M.state.TLAM_STRIKE_MISSION
    if not ship_unit or not ship_unit.guid then
        print('WARNING: TLAM salvo — geen CG-shooter geplaatst')
        return false
    end
    local m = ScenEdit_GetMission(side, naval_mission)
    if not m then
        print('WARNING: Mission ' .. naval_mission .. ' NOT found')
        return false
    end
    local on_unitlist = false
    if m.unitlist then
        for _, ug in ipairs(m.unitlist) do
            if ug == ship_unit.guid then
                on_unitlist = true
                break
            end
        end
    end
    local u = ScenEdit_GetUnit({ guid = ship_unit.guid })
    local unit_mission = M._unit_mission_label(u)
    local unitlist_n = m.unitlist and #m.unitlist or 0
    print('TLAM verify: unitlist=' .. unitlist_n .. ' | ' .. tostring(ship_unit.name) ..
        ' mission="' .. unit_mission .. '" on_unitlist=' .. tostring(on_unitlist))
    if on_unitlist then
        print('OK: ' .. naval_mission .. ' has shooter on unitlist (' .. tostring(ship_unit.name) .. ')')
        return true
    end
    if unit_mission ~= '' and string.find(string.lower(unit_mission), string.lower(naval_mission), 1, true) then
        print('OK: ' .. tostring(ship_unit.name) .. ' shows assigned mission ' .. unit_mission)
        return true
    end
    print('WARNING: ' .. naval_mission .. ' has no shooter — open mission in ME and assign ' ..
        tostring(ship_unit.name) .. ' manually if needed.')
    return false
end

function M.add_air_unit_checked(side, unitname, dbid, base_guid, loadoutid, mission_name, strike_escort)
    if loadoutid == nil then
        print('ERROR: Missing LoadoutID voor ' .. unitname .. ' (DBID ' .. dbid .. ')')
        return nil
    end
    if not base_guid then
        print('ERROR: Geen basis voor ' .. unitname)
        return nil
    end

    local host = ScenEdit_GetUnit({ guid = base_guid })
    local base_ref = tostring(base_guid)
    if host and host.name then
        base_ref = host.name
    end

    local add_params = {
        type = 'Air',
        unitname = unitname,
        side = side,
        dbid = dbid,
        base = base_ref,
        loadoutid = loadoutid,
        altitude = '0',
    }
    if mission_name and not strike_escort then
        add_params.mission = mission_name
    end
    if host and host.latitude and host.longitude then
        add_params.latitude = host.latitude
        add_params.longitude = host.longitude
    end
    local u = ScenEdit_AddUnit(add_params)

    if not u or not u.guid then
        print('ERROR: Air spawn mislukt: ' .. unitname)
        return nil
    end

    local created = ScenEdit_GetUnit({ guid = u.guid })
    if created and created.loadoutdbid ~= nil and tonumber(created.loadoutdbid) ~= tonumber(loadoutid) then
        print('WARNING: Loadout afwijking voor ' .. unitname .. ' | preferred=' .. loadoutid ..
            ' actief=' .. tostring(created.loadoutdbid))
    end

    if mission_name then
        ScenEdit_SetUnit({ guid = u.guid, timetoready_minutes = 0 })
        table.insert(M.state.spawned_air_missions, {
            guid = u.guid,
            name = unitname,
            side = side,
            mission = mission_name,
            escort = strike_escort,
        })
        if not M.assign_air_to_mission(side, u.guid, unitname, mission_name, strike_escort) then
            print('ERROR: AssignUnitToMission mislukt: ' .. unitname .. ' -> ' .. mission_name)
        end
    end
    return u
end

function M.spawn_air_wing(side, prefix, count, dbid, loadoutid, mission_name, base_guid, strike_escort)
    for i = 1, count do
        M.add_air_unit_checked(side, prefix .. ' #' .. i, dbid, base_guid, loadoutid, mission_name, strike_escort)
    end
end

function M._require_land_placement(unitname, latitude, longitude)
    local elev = World_GetElevation({ latitude = latitude, longitude = longitude })
    if elev == nil then
        print('WARNING: World_GetElevation nil for ' .. unitname .. ' at ' .. latitude .. ',' .. longitude)
        return true
    end
    if elev <= 0 then
        print('ERROR: Facility placement underwater at ' .. unitname .. ' at ' .. latitude .. ',' .. longitude ..
            ' (elevation=' .. tostring(elev) .. 'm)')
        return false
    end
    return true
end

function M.place_base(side, unitname, latitude, longitude)
    if not M._require_land_placement(unitname, latitude, longitude) then
        return nil
    end
    local base = ScenEdit_AddUnit({
        type = 'Facility',
        unitname = unitname,
        side = side,
        dbid = M.state.BASE_FACILITY_DBID,
        latitude = latitude,
        longitude = longitude,
        altitude = 0,
    })
    if not base then
        print('ERROR: Basis kon niet worden geplaatst: ' .. unitname)
    end
    return base
end

function M.place_sam(side, unitname, dbid, latitude, longitude)
    if not M._require_land_placement(unitname, latitude, longitude) then
        return nil
    end
    local sam = ScenEdit_AddUnit({
        type = 'Facility',
        unitname = unitname,
        side = side,
        dbid = dbid,
        latitude = latitude,
        longitude = longitude,
        altitude = 0,
    })
    if not sam then
        print('ERROR: SAM kon niet worden geplaatst: ' .. unitname)
    end
    return sam
end

function M.place_sub(side, unitname, dbid, latitude, longitude)
    local elev = World_GetElevation({ latitude = latitude, longitude = longitude })
    if elev and elev > 0 then
        print('ERROR: Submarine placement over land: ' .. unitname .. ' at ' .. latitude .. ',' .. longitude)
        return nil
    end
    local sub = ScenEdit_AddUnit({
        type = 'Sub',
        unitname = unitname,
        side = side,
        dbid = dbid,
        latitude = latitude,
        longitude = longitude,
        altitude = -50,
    })
    if not sub then
        print('ERROR: Onderzeeër kon niet worden geplaatst: ' .. unitname)
    end
    return sub
end

function M.place_ship(side, unitname, dbid, latitude, longitude)
    local elev = World_GetElevation({ latitude = latitude, longitude = longitude })
    if elev and elev > 0 then
        print('ERROR: Cannot place ship over land: ' .. unitname .. ' at ' .. latitude .. ',' .. longitude ..
            ' (elevation=' .. tostring(elev) .. 'm)')
        return nil
    end
    local ship = ScenEdit_AddUnit({
        type = 'Ship',
        unitname = unitname,
        side = side,
        dbid = dbid,
        latitude = latitude,
        longitude = longitude,
        altitude = 0,
    })
    if not ship then
        print('ERROR: Schip kon niet worden geplaatst: ' .. unitname)
    end
    return ship
end

function M.configure_nuclear_policy(cfg)
    cfg = cfg or {}
    if cfg.allowed ~= nil then
        M.state.nuclear_weapons_allowed = cfg.allowed == true
    end
    if cfg.tlam_replacement_dbid then
        M.state.conventional_tlam_dbid = cfg.tlam_replacement_dbid
    end
end

function M.weapon_name_is_nuclear(name)
    if not name then
        return false
    end
    local u = string.upper(tostring(name))
    if string.find(u, 'NUCLEAR') or string.find(u, 'NUCL') then
        return true
    end
    if string.find(u, 'TLAM%-N') or string.find(u, 'TLAM N') then
        return true
    end
    if string.find(u, 'AGM%-86B') then
        return true
    end
    if string.find(u, 'AGM%-129') and string.find(u, 'ACM') then
        return true
    end
    if string.find(u, 'BGM%-109G') and string.find(u, 'GLCM') then
        return true
    end
    if string.find(u, 'B61') or string.find(u, 'B83') or string.find(u, 'W80') or string.find(u, 'W87') then
        return true
    end
    if string.find(u, 'ALCM') and not string.find(u, 'CALCM') and not string.find(u, 'CONVENTIONAL') then
        return true
    end
    return false
end

function M.weapon_name_is_nuclear_cruise(name)
    if not name then
        return false
    end
    local u = string.upper(tostring(name))
    if string.find(u, 'TLAM%-N') or string.find(u, 'TLAM N') then
        return true
    end
    if string.find(u, 'UGM%-109A') or string.find(u, 'RGM%-109A') then
        return true
    end
    if string.find(u, 'BGM%-109G') and string.find(u, 'GLCM') then
        return true
    end
    if string.find(u, 'ALCM') and not string.find(u, 'CALCM') and not string.find(u, 'CONVENTIONAL') then
        return true
    end
    return false
end

-- Filled by embed_bootstrap.py from DataWarhead.Type=4001 (EnumWarheadType Nuclear).
M.NUCLEAR_WEAPON_DBIDS = {}
M.NUCLEAR_CRUISE_DBIDS = {}

function M.weapon_dbid_is_nuclear(dbid)
    if not dbid then
        return false
    end
    return M.NUCLEAR_WEAPON_DBIDS[dbid] == true
end

function M.weapon_dbid_is_nuclear_cruise(dbid)
    if not dbid then
        return false
    end
    return M.NUCLEAR_CRUISE_DBIDS[dbid] == true
end

function M._weapon_entry_is_nuclear(wname, dbid)
    if dbid and M.weapon_dbid_is_nuclear(dbid) then
        return true
    end
    if not dbid and wname then
        return M.weapon_name_is_nuclear(wname)
    end
    return false
end

function M._weapon_entry_is_nuclear_cruise(wname, dbid)
    if dbid and M.weapon_dbid_is_nuclear_cruise(dbid) then
        return true
    end
    if not dbid and wname then
        return M.weapon_name_is_nuclear_cruise(wname)
    end
    return false
end

function M._weapon_loaded_qty(w)
    if not w then
        return 1
    end
    local q = w.current or w.number or w.count or w.qty
    if type(q) == 'number' and q > 0 then
        return q
    end
    return 1
end

function M.weapon_is_conventional_ship_cruise(wname, dbid)
    if M._weapon_entry_is_nuclear(wname, dbid) then
        return false
    end
    if not wname then
        return false
    end
    local u = string.upper(tostring(wname))
    if string.find(u, 'UGM%-109') or string.find(u, 'RGM%-109') then
        return true
    end
    if string.find(u, 'TOMAHAWK') or string.find(u, 'TLAM') or string.find(u, 'TACTOM') then
        return true
    end
    return false
end

function M._count_conventional_cruise_on_unit(unit_wrap)
    local counts = {}
    local function note(wname, dbid, qty)
        if not dbid or not M.weapon_is_conventional_ship_cruise(wname, dbid) then
            return
        end
        counts[dbid] = (counts[dbid] or 0) + (qty or 1)
    end
    if unit_wrap.mounts then
        for _, mount in ipairs(unit_wrap.mounts) do
            if mount.weapons then
                for _, w in ipairs(mount.weapons) do
                    note(w.name, w.wpn_dbid or w.dbid, M._weapon_loaded_qty(w))
                end
            end
            if unit_wrap.getUnitMountMagazine and mount.guid then
                local ok, mm = pcall(function()
                    return unit_wrap:getUnitMountMagazine(mount.guid)
                end)
                if ok and mm and mm.weapons then
                    for _, w in ipairs(mm.weapons) do
                        note(w.name, w.wpn_dbid or w.dbid, M._weapon_loaded_qty(w))
                    end
                end
            end
        end
    end
    if unit_wrap.magazines then
        for _, mag in ipairs(unit_wrap.magazines) do
            if mag.weapons then
                for _, w in ipairs(mag.weapons) do
                    note(w.name, w.wpn_dbid or w.dbid, M._weapon_loaded_qty(w))
                end
            end
        end
    end
    return counts
end

-- Prefer Tomahawk/TLAM already loaded on the unit (same VLS cell type); fallback to era default UGM-109.
function M.pick_conventional_cruise_replacement_dbid(unit_wrap, opts)
    opts = opts or {}
    if opts.tlam_replacement_dbid then
        return opts.tlam_replacement_dbid
    end
    local counts = M._count_conventional_cruise_on_unit(unit_wrap)
    local best_dbid, best_n = nil, 0
    for dbid, n in pairs(counts) do
        if n > best_n then
            best_dbid, best_n = dbid, n
        end
    end
    if best_dbid then
        return best_dbid
    end
    return M.conventional_tlam_dbid()
end

function M._add_cruise_to_mount(unit_guid, mount_guid, replacement_dbid, number)
    if not mount_guid or not replacement_dbid or not number or number <= 0 then
        return 0
    end
    return ScenEdit_AddReloadsToUnit({
        guid = unit_guid,
        wpn_dbid = replacement_dbid,
        mount_guid = mount_guid,
        new = true,
        number = number,
    }) or 0
end

function M._add_cruise_to_magazine(unit_guid, mag_guid, replacement_dbid, number)
    if not mag_guid or not replacement_dbid or not number or number <= 0 then
        return 0
    end
    return ScenEdit_AddWeaponToUnitMagazine({
        guid = unit_guid,
        wpn_dbid = replacement_dbid,
        mag_guid = mag_guid,
        new = true,
        number = number,
    }) or 0
end

function M._strip_reload_on_mount(unit_guid, mount_guid, dbid, wname, replacement_dbid, replace_cruise)
    local n = ScenEdit_AddReloadsToUnit({
        guid = unit_guid,
        wpn_dbid = dbid,
        mount_guid = mount_guid,
        remove = true,
        number = 999,
    }) or 0
    local added = 0
    if n > 0 and replace_cruise and replacement_dbid and
        M._weapon_entry_is_nuclear_cruise(wname, dbid) then
        added = M._add_cruise_to_mount(unit_guid, mount_guid, replacement_dbid, n)
    end
    return n, added
end

function M._strip_weapon_in_magazine(unit_guid, mag_guid, dbid, wname, replacement_dbid, replace_cruise)
    local n = ScenEdit_AddWeaponToUnitMagazine({
        guid = unit_guid,
        wpn_dbid = dbid,
        mag_guid = mag_guid,
        remove = true,
        number = 999,
    }) or 0
    local added = 0
    if n > 0 and replace_cruise and replacement_dbid and
        M._weapon_entry_is_nuclear_cruise(wname, dbid) then
        added = M._add_cruise_to_magazine(unit_guid, mag_guid, replacement_dbid, n)
    end
    return n, added
end

function M._strip_nuclear_from_mount_stores(unit_wrap, mount, replacement_dbid, replace_cruise)
    if not mount or not mount.guid then
        return 0, 0
    end
    local removed, replaced = 0, 0
    local function tally(wname, dbid, mount_guid, mag_guid)
        if not M._weapon_entry_is_nuclear(wname, dbid) or not dbid then
            return
        end
        local n, a
        if mount_guid then
            n, a = M._strip_reload_on_mount(unit_wrap.guid, mount_guid, dbid, wname, replacement_dbid, replace_cruise)
        else
            n, a = M._strip_weapon_in_magazine(unit_wrap.guid, mag_guid, dbid, wname, replacement_dbid, replace_cruise)
        end
        removed = removed + n
        replaced = replaced + a
    end
    if mount.weapons then
        for _, w in ipairs(mount.weapons) do
            tally(w.name, w.wpn_dbid or w.dbid, mount.guid, nil)
        end
    end
    if unit_wrap.getUnitMountMagazine then
        local ok, mm = pcall(function()
            return unit_wrap:getUnitMountMagazine(mount.guid)
        end)
        if ok and mm and mm.weapons and mm.guid then
            for _, w in ipairs(mm.weapons) do
                tally(w.name, w.wpn_dbid or w.dbid, nil, mm.guid)
            end
        end
    end
    for dbid, _ in pairs(M.NUCLEAR_WEAPON_DBIDS) do
        local n, a = M._strip_reload_on_mount(
            unit_wrap.guid, mount.guid, dbid, nil, replacement_dbid, replace_cruise)
        removed = removed + n
        replaced = replaced + a
    end
    return removed, replaced
end

function M._first_vls_mount_guid(unit_wrap)
    if not unit_wrap or not unit_wrap.mounts then
        return nil
    end
    for _, mount in ipairs(unit_wrap.mounts) do
        if mount.guid and mount.name and string.find(string.upper(tostring(mount.name)), 'MK41') then
            return mount.guid
        end
    end
    for _, mount in ipairs(unit_wrap.mounts) do
        if mount.guid and mount.name and string.find(string.upper(tostring(mount.name)), 'VLS') then
            return mount.guid
        end
    end
    return unit_wrap.mounts[1] and unit_wrap.mounts[1].guid or nil
end

function M.conventional_tlam_dbid()
    if M.state.conventional_tlam_dbid then
        return M.state.conventional_tlam_dbid
    end
    local year = M.state.scenario_year or 2026
    if year >= 2020 then
        return 4033 -- UGM-109J Tomahawk Blk V TACTOM
    end
    if year >= 2004 then
        return 810 -- UGM-109E Tomahawk Blk IV TACTOM
    end
    return 811 -- UGM-109C Tomahawk Blk III TLAM-C
end

function M.strip_nuclear_from_unit(unit, opts)
    opts = opts or {}
    if M.state.nuclear_weapons_allowed then
        return 0, 0
    end
    if not unit or not unit.guid then
        return 0, 0
    end
    local u = ScenEdit_GetUnit({ guid = unit.guid })
    if not u then
        return 0, 0
    end
    local replace_cruise = opts.replace_cruise ~= false
    local replacement_dbid = M.pick_conventional_cruise_replacement_dbid(u, opts)
    local removed = 0
    local replaced = 0
    if u.mounts then
        for _, mount in ipairs(u.mounts) do
            local n, a = M._strip_nuclear_from_mount_stores(u, mount, replacement_dbid, replace_cruise)
            removed = removed + n
            replaced = replaced + a
        end
    end
    if u.magazines then
        for _, mag in ipairs(u.magazines) do
            if mag.weapons and mag.guid then
                for _, w in ipairs(mag.weapons) do
                    local wname = w.name
                    local dbid = w.wpn_dbid or w.dbid
                    if M._weapon_entry_is_nuclear(wname, dbid) and dbid then
                        local n, a = M._strip_weapon_in_magazine(
                            u.guid, mag.guid, dbid, wname, replacement_dbid, replace_cruise)
                        removed = removed + n
                        replaced = replaced + a
                    end
                end
            end
        end
    end
    for dbid, _ in pairs(M.NUCLEAR_WEAPON_DBIDS) do
        local n = ScenEdit_AddReloadsToUnit({
            guid = u.guid,
            wpn_dbid = dbid,
            remove = true,
            number = 999,
        }) or 0
        if n > 0 then
            removed = removed + n
            if replace_cruise and replacement_dbid and M.NUCLEAR_CRUISE_DBIDS[dbid] then
                local mount_guid = M._first_vls_mount_guid(u)
                local added = 0
                if mount_guid then
                    added = M._add_cruise_to_mount(u.guid, mount_guid, replacement_dbid, n)
                else
                    added = ScenEdit_AddReloadsToUnit({
                        guid = u.guid,
                        wpn_dbid = replacement_dbid,
                        new = true,
                        number = n,
                    }) or 0
                end
                replaced = replaced + added
            end
        end
    end
    return removed, replaced
end

function M.assign_csg_group_missions(group_name, lead_unit, patrol_mission, strike_unit, strike_mission, side)
    side = side or M.state.strike_side or 'United States'
    if lead_unit and lead_unit.guid and patrol_mission then
        ScenEdit_AssignUnitToMission(lead_unit.guid, patrol_mission)
        -- Do NOT AssignUnitToMission(group_name, patrol): CMO applies patrol to all group members
        -- and clears a CG's separate TLAM Strike assignment in the Mission Editor.
    end
    if strike_unit and strike_mission then
        if not M.assign_ship_to_mission(side, strike_unit, strike_mission, group_name) then
            print('ERROR: TLAM shooter niet op missie: ' .. tostring(strike_unit.name or strike_unit.guid) ..
                ' -> ' .. tostring(strike_mission))
        end
    end
end

-- CVN + CG + DDGs in one CMO group; TLAM schedule may be empty at import until Play (see INIT LOG).
function M.form_csg_group(group_name, lead, members)
    if not lead or not lead.guid then
        print('ERROR: CSG group zonder lead')
        return
    end
    ScenEdit_SetUnit({ guid = lead.guid, group = group_name, groupLead = lead.guid })
    for _, u in ipairs(members) do
        if u and u.guid then
            ScenEdit_SetUnit({ guid = u.guid, group = group_name })
        end
    end
    local lead_u = ScenEdit_GetUnit({ guid = lead.guid })
    if lead_u then
        lead_u.formation = {
            name = 'Column',
            spacing = 2000,
            spacing_unit = 'm',
            transpose = true,
        }
    end
end

function M.assert_db_series(scenario_year, expected)
    expected = expected or 'DB3K'
    local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
    M.state.db_series = db_series
    M.state.scenario_year = scenario_year
    if db_series ~= expected then
        print('ERROR: Scenario year ' .. scenario_year .. ' expects database series ' .. expected)
        return false
    end
    return true
end

cmo = M
return M
