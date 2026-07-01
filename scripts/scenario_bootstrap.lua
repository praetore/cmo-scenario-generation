-- scenario_bootstrap.lua — CMO scenario helpers (implementation only).
-- Reference: .cursor/rules/scenario_bootstrap_reference.md
-- Workflow: generated/src/<name>_src.lua → generate_scenario.py → generated/<name>.lua

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
    strike_mission_names = {},
    scenario_year = nil,
    nuclear_weapons_allowed = false,
    conventional_tlam_dbid = nil,
    civilian_theater = nil,
    civilian_airports = {},
}

function M.register_strike_mission(mission_name)
    if mission_name and mission_name ~= '' then
        M.state.strike_mission_names[mission_name] = true
    end
end

function M._is_strike_ship_mission(mission_name)
    if not mission_name or mission_name == '' then
        return false
    end
    if M.state.strike_mission_names[mission_name] then
        return true
    end
    local side = M.state.strike_side or 'United States'
    local m = ScenEdit_GetMission(side, mission_name)
    if m then
        local t = tostring(m.type or m.missiontype or m.missionType or '')
        if string.lower(t) == 'strike' then
            return true
        end
    end
    return false
end

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
    M.register_strike_mission(M.state.STRIKE_AIR_MISSION)
    M.register_strike_mission(M.state.TLAM_STRIKE_MISSION)
end

function M.mission_schedule_date(date_slash)
    return date_slash:gsub('/', '.')
end

function M.mission_schedule_datetime(date_slash, time_hms)
    return M.mission_schedule_date(date_slash) .. ' ' .. time_hms
end

function M.minutes_from_hms(time_hms)
    local h, m, s = tostring(time_hms):match('^(%d+):(%d+):(%d+)$')
    if not h then
        return nil
    end
    return tonumber(h) * 60 + tonumber(m) + (tonumber(s) or 0) / 60
end

function M.hms_from_minutes(minutes)
    local mins = math.max(0, math.floor((minutes or 0) + 0.5))
    return string.format('%02d:%02d:00', math.floor(mins / 60) % 24, mins % 60)
end

function M.hms_subtract_minutes(time_hms, delta_minutes)
    local base = M.minutes_from_hms(time_hms)
    if not base then
        return time_hms
    end
    return M.hms_from_minutes(base - (delta_minutes or 0))
end

-- scenario_date 'YYYY/MM/DD' → ScenEdit_SetTime (dateformat YYYYMMDD; StartDate DD.MM.YYYY per API)
function M.scenario_set_start(date_slash, time_hms)
    local y, m, d = date_slash:match('^(%d+)/(%d+)/(%d+)$')
    if not y then
        M._abort_scenario_generation('scenario_set_start — bad date ' .. tostring(date_slash) .. ' (want YYYY/MM/DD)')
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

function M.assign_ship_to_mission(side, ship_unit, mission_name, group_name)
    if not ship_unit or not ship_unit.guid or not mission_name then
        return false
    end
    side = side or M.state.strike_side or 'United States'
    local function done(result)
        if result and M._is_strike_ship_mission(mission_name) then
            M.configure_strike_ship_weapon_policy(ship_unit, { side = side })
        end
        return result
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
            return done(true)
        end
        ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, mission = mission_name })
        if assigned() then
            return done(true)
        end
        local u_wrap = ScenEdit_GetUnit({ guid = ship_unit.guid })
        if u_wrap then
            u_wrap.mission = mission_name
            if assigned() then
                return done(true)
            end
        end
        return done(assigned())
    end

    -- Grouped (legacy): AssignUnitToMission then group-only SetUnit — never mission+group in one SetUnit.
    if grp and grp ~= '' then
        for _, uref in ipairs(unit_refs) do
            ScenEdit_AssignUnitToMission(uref, mission_name)
        end
        if assigned() then
            ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            return done(assigned())
        end
    end

    ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, mission = mission_name })
    if assigned() then
        return done(true)
    end

    for _, uref in ipairs(unit_refs) do
        if ScenEdit_AssignUnitToMission(uref, mission_name) then
            if grp and grp ~= '' then
                ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            end
            return done(true)
        end
    end

    local u_wrap = ScenEdit_GetUnit({ guid = ship_unit.guid })
    if u_wrap then
        u_wrap.mission = mission_name
        if assigned() then
            return done(true)
        end
    end

    if grp and grp ~= '' then
        M.ungroup_unit(ship_unit, side)
        ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, mission = mission_name })
        if assigned() then
            ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            return done(assigned())
        end
        for _, uref in ipairs(unit_refs) do
            ScenEdit_AssignUnitToMission(uref, mission_name)
        end
        if assigned() then
            ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
            return done(assigned())
        end
        ScenEdit_SetUnit({ guid = ship_unit.guid, side = side, group = grp })
    end

    return done(assigned())
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
    local sched = {
        tot = M.mission_schedule_datetime(date, M.state.strike_package_tot),
        tlam_launch = nil,
    }
    if M.state.tlam_launch_time then
        sched.tlam_launch = M.mission_schedule_datetime(date, M.state.tlam_launch_time)
    end
    return sched
end

function M._station_schedule_parts(station_dt, opts)
    opts = opts or {}
    local date_slash = opts.date or M.state.strike_package_date
    local time_hms = opts.station_time_hms
    if station_dt then
        if not time_hms then
            time_hms = station_dt:match('%s(%d+:%d+:%d+)$')
        end
        if not date_slash then
            local date_dot = station_dt:match('^(%d+%.%d+%.%d+)')
            if date_dot then
                date_slash = date_dot:gsub('%.', '/')
            end
        end
    end
    return date_slash, time_hms
end

function M._cmo_wrapper_datetime(date_slash, time_hms)
    local y, mo, d = date_slash:match('(%d+)/(%d+)/(%d+)')
    if not y then
        return nil
    end
    return string.format('%s.%s.%s %s', tonumber(d), tonumber(mo), y, time_hms)
end

function M._mission_is_support(m)
    if not m then
        return false
    end
    local t = string.lower(tostring(m.typeS or m.type or ''))
    return t:find('support', 1, true) ~= nil
end

function M._apply_on_station_times(side, mission_name, date_slash, time_hms, opts)
    opts = opts or {}
    local station_dt = M.mission_schedule_datetime(date_slash, time_hms)
    local wrapper_dt = M._cmo_wrapper_datetime(date_slash, time_hms)
    local takeoff_hms = opts.takeoff_time_hms
    if not takeoff_hms and opts.transit_minutes then
        takeoff_hms = M.hms_subtract_minutes(time_hms, opts.transit_minutes)
    end
    local takeoff_dt = takeoff_hms and M.mission_schedule_datetime(date_slash, takeoff_hms)
    local takeoff_wrapper = takeoff_hms and M._cmo_wrapper_datetime(date_slash, takeoff_hms)

    local set_opts = {
        TimeOnTargetStation = wrapper_dt or station_dt,
        OnDeactivateUassign = opts.on_deactivate_unassign == true,
        isactive = opts.isactive ~= false,
    }
    if opts.use_flight_size ~= false then
        set_opts.UseFlightSize = true
        set_opts.FlightSize = opts.flight_size or 2
        if opts.min_aircraft_req then
            set_opts.MinAircraftReq = opts.min_aircraft_req
        end
    end
    if takeoff_dt then
        set_opts.starttime = takeoff_wrapper or takeoff_dt
        set_opts.TakeOffTime = takeoff_wrapper or takeoff_dt
    end
    ScenEdit_SetMission(side, mission_name, set_opts)
    local m = ScenEdit_GetMission(side, mission_name)
    if m then
        m.TimeOnTargetStation = wrapper_dt or station_dt
        if takeoff_wrapper then
            m.starttime = takeoff_wrapper
            m.TakeOffTime = takeoff_wrapper
        end
        pcall(function() m:updateWPtimes() end)
        m = ScenEdit_GetMission(side, mission_name)
    end
    return m, takeoff_hms
end

function M._apply_strike_tot_times(side, mission_name, date_slash, tot_hms, opts)
    opts = opts or {}
    local tot_dt = M.mission_schedule_datetime(date_slash, tot_hms)
    local wrapper_dt = M._cmo_wrapper_datetime(date_slash, tot_hms)
    local launch_hms = opts.launch_hms
    if not launch_hms and opts.launch_dt then
        launch_hms = opts.launch_dt:match('(%d+:%d+:%d+)$')
    end
    local launch_dt = launch_hms and M.mission_schedule_datetime(date_slash, launch_hms)
    local launch_wrapper = launch_hms and M._cmo_wrapper_datetime(date_slash, launch_hms)

    local set_opts = {
        TimeOnTargetStation = wrapper_dt or tot_dt,
    }
    if opts.on_deactivate_unassign ~= nil then
        set_opts.OnDeactivateUassign = opts.on_deactivate_unassign
    end
    if opts.isactive ~= nil then
        set_opts.isactive = opts.isactive
    end
    if launch_dt and not opts.wrapper_only then
        set_opts.starttime = launch_wrapper or launch_dt
        set_opts.TakeOffTime = launch_wrapper or launch_dt
    end
    if not opts.wrapper_only then
        ScenEdit_SetMission(side, mission_name, set_opts)
    end
    local m = ScenEdit_GetMission(side, mission_name)
    if m then
        m.TimeOnTargetStation = wrapper_dt or tot_dt
        if launch_wrapper and not opts.wrapper_only then
            m.starttime = launch_wrapper
            m.TakeOffTime = launch_wrapper
        end
        pcall(function() m:updateWPtimes() end)
        m = ScenEdit_GetMission(side, mission_name)
    end
    return m
end

-- Strike package TOT: CreateMissionFlightPlan TIMEONTARGET + wrapper TimeOnTargetStation (fatal verify on TOT).
function M.set_strike_tot_schedule(side, mission_name, tot_dt, opts)
    opts = opts or {}
    side = side or M.state.strike_side or 'United States'
    mission_name = mission_name or M.state.STRIKE_AIR_MISSION
    if not mission_name or not tot_dt then
        return false
    end
    local date_slash = opts.date or M.state.strike_package_date
    local tot_hms = opts.tot_hms or tot_dt:match('%s(%d+:%d+:%d+)$')
    if not tot_hms then
        M._abort_scenario_generation('Strike TOT — cannot parse tot_dt for ' .. tostring(mission_name))
    end
    if opts.launch_dt and not opts.launch_hms then
        opts.launch_hms = opts.launch_dt:match('(%d+:%d+:%d+)$')
    end

    if not opts.skip_flight_plan and not opts.wrapper_only then
        M._apply_strike_tot_times(side, mission_name, date_slash, tot_hms, opts)
        local fp_opts = { DATEONTARGET = date_slash, TIMEONTARGET = tot_hms }
        local m = ScenEdit_GetMission(side, mission_name)
        local fp_ok = false
        if m and m.createFlightPlans then
            fp_ok = pcall(function() m:createFlightPlans(fp_opts) end)
        end
        if not fp_ok then
            ScenEdit_CreateMissionFlightPlan(side, mission_name, fp_opts)
        end
    end
    M._apply_strike_tot_times(side, mission_name, date_slash, tot_hms, opts)

    if opts.verify ~= false then
        M.verify_mission_schedule(side, mission_name, {
            tot_hms = tot_hms,
            launch_dt = opts.launch_dt,
        }, {
            label = mission_name .. ' strike TOT',
            optional_fields = { 'starttime', 'takeoff' },
        })
    end
    return true
end

-- Patrol/Support on-station: Patrol → CreateMissionFlightPlan TIMEONTARGET; Support → TAKEOFFTIME + wrapper TOS (land ISR).
function M.set_patrol_on_station_schedule(side, mission_name, station_dt, opts)
    opts = opts or {}
    if not mission_name or not station_dt then
        return false
    end
    side = side or M.state.strike_side or 'United States'
    local date_slash, time_hms = M._station_schedule_parts(station_dt, opts)
    if not date_slash or not time_hms then
        M._abort_scenario_generation('Patrol on-station — cannot parse schedule for ' .. tostring(mission_name))
    end

    local m0 = ScenEdit_GetMission(side, mission_name)
    local is_support = M._mission_is_support(m0)
    if is_support and not opts.takeoff_time_hms and not opts.transit_minutes then
        opts.transit_minutes = 90
    end

    local m, takeoff_hms = M._apply_on_station_times(side, mission_name, date_slash, time_hms, opts)

    if is_support then
        if takeoff_hms then
            ScenEdit_CreateMissionFlightPlan(side, mission_name, {
                TAKEOFFDATE = date_slash,
                TAKEOFFTIME = takeoff_hms,
            })
            m, _ = M._apply_on_station_times(side, mission_name, date_slash, time_hms, opts)
        end
    else
        local fp_opts = {
            DATEONTARGET = date_slash,
            TIMEONTARGET = time_hms,
        }
        local fp_ok = false
        if m and m.createFlightPlans then
            fp_ok = pcall(function() m:createFlightPlans(fp_opts) end)
        end
        if not fp_ok then
            ScenEdit_CreateMissionFlightPlan(side, mission_name, fp_opts)
        end
        m, _ = M._apply_on_station_times(side, mission_name, date_slash, time_hms, opts)
    end

    if opts.verify ~= false then
        M.verify_mission_schedule(side, mission_name, { tos_hms = time_hms }, {
            label = mission_name .. ' on-station',
            optional_fields = is_support and { 'starttime', 'takeoff' } or nil,
        })
    end
    return true
end

function M._verify_field_optional(opts, field_name)
    local names = opts.optional_fields
    if not names then
        return false
    end
    for _, name in ipairs(names) do
        if name == field_name then
            return true
        end
    end
    return false
end

function M.set_naval_strike_schedule(side, mission_name, launch_dt, tot_dt)
    side = side or M.state.strike_side or 'United States'
    mission_name = mission_name or M.state.TLAM_STRIKE_MISSION
    if not mission_name or not tot_dt then
        return false
    end
    return M.set_strike_tot_schedule(side, mission_name, tot_dt, {
        date = M.state.strike_package_date,
        launch_dt = launch_dt,
        on_deactivate_unassign = false,
        isactive = true,
        skip_flight_plan = true,
    })
end

function M._mission_field_nonempty(value)
    if value == nil then
        return false
    end
    local s = tostring(value)
    return s ~= '' and s ~= 'nil'
end

-- Extract HH:MM:SS from Mission wrapper DateTime (starttime / TakeOffTime / TimeOnTargetStation).
function M._normalize_mission_datetime(value)
    if not M._mission_field_nonempty(value) then
        return nil
    end
    return tostring(value):match('(%d+:%d+:%d+)')
end

function M._expected_schedule_hms(expected, keys)
    if not expected then
        return nil
    end
    for _, key in ipairs(keys) do
        local raw = expected[key]
        if raw and raw ~= '' then
            local hms = tostring(raw):match('(%d+:%d+:%d+)$')
            if hms then
                return hms
            end
            return tostring(raw)
        end
    end
    return nil
end

function M._abort_scenario_generation(reason)
    print('ERROR: ' .. reason)
    error(reason, 0)
end

-- Public alias: any bootstrap ERROR aborts scenario init (no partial OOB).
function M.scenario_error(reason)
    M._abort_scenario_generation(reason)
end

-- Post-assignment check via ScenEdit_GetMission (Mission wrapper fields).
-- expected: { tot_hms|tos_hms, starttime_hms|launch_dt, takeoff_hms|takeoff_dt }
-- Default: fatal — mismatch aborts scenario Lua init via error().
function M.verify_mission_schedule(side, mission_name, expected, opts)
    opts = opts or {}
    expected = expected or {}
    side = side or M.state.strike_side or 'United States'
    local fatal = opts.fatal ~= false
    if not mission_name then
        if fatal then
            M._abort_scenario_generation('Mission schedule verify — mission_name required')
        end
        return false
    end
    local label = opts.label or mission_name
    local m = ScenEdit_GetMission(side, mission_name)
    if not m then
        local msg = 'Mission schedule verify FAILED — GetMission nil for ' .. label
        if fatal then
            M._abort_scenario_generation(msg)
        end
        print('ERROR: ' .. msg)
        return false
    end

    local issues = {}
    local notes = {}
    local ok_parts = {}

    local exp_tos = M._expected_schedule_hms(expected, {
        'tos_hms', 'tot_hms', 'time_on_target_station_hms',
    })
    if not exp_tos and expected.time_on_target_station_dt then
        _, exp_tos = M._station_schedule_parts(expected.time_on_target_station_dt, expected)
    end
    if exp_tos then
        local actual_raw = m.TimeOnTargetStation
        local actual_hms = M._normalize_mission_datetime(actual_raw)
        if not actual_hms then
            table.insert(issues, 'TimeOnTargetStation empty (expected ' .. exp_tos .. ')')
        elseif actual_hms ~= exp_tos then
            table.insert(issues,
                'TimeOnTargetStation=' .. tostring(actual_raw) .. ' (hms ' .. actual_hms .. ', expected ' .. exp_tos .. ')')
        else
            table.insert(ok_parts, 'TimeOnTargetStation=' .. tostring(actual_raw))
        end
    end

    local exp_start = M._expected_schedule_hms(expected, { 'starttime_hms', 'launch_hms' })
    if not exp_start and expected.launch_dt then
        exp_start = expected.launch_dt:match('(%d+:%d+:%d+)$')
    end
    if exp_start then
        local actual_raw = m.starttime
        local actual_hms = M._normalize_mission_datetime(actual_raw)
        if not actual_hms then
            local msg = 'starttime empty (expected ' .. exp_start .. ')'
            if M._verify_field_optional(opts, 'starttime') then
                table.insert(notes, msg)
            else
                table.insert(issues, msg)
            end
        elseif actual_hms ~= exp_start then
            local msg = 'starttime=' .. tostring(actual_raw) .. ' (hms ' .. actual_hms .. ', expected ' .. exp_start .. ')'
            if M._verify_field_optional(opts, 'starttime') then
                table.insert(notes, msg)
            else
                table.insert(issues, msg)
            end
        else
            table.insert(ok_parts, 'starttime=' .. tostring(actual_raw))
        end
    end

    local exp_takeoff = M._expected_schedule_hms(expected, { 'takeoff_hms' })
    if not exp_takeoff and expected.takeoff_dt then
        exp_takeoff = expected.takeoff_dt:match('(%d+:%d+:%d+)$')
    end
    if not exp_takeoff and exp_start and M._verify_field_optional(opts, 'takeoff') then
        exp_takeoff = exp_start
    end
    if exp_takeoff then
        local actual_raw = m.TakeOffTime
        local actual_hms = M._normalize_mission_datetime(actual_raw)
        if not actual_hms then
            local msg = 'TakeOffTime empty (expected ' .. exp_takeoff .. ')'
            if M._verify_field_optional(opts, 'takeoff') then
                table.insert(notes, msg)
            else
                table.insert(issues, msg)
            end
        elseif actual_hms ~= exp_takeoff then
            local msg = 'TakeOffTime=' .. tostring(actual_raw) .. ' (hms ' .. actual_hms .. ', expected ' .. exp_takeoff .. ')'
            if M._verify_field_optional(opts, 'takeoff') then
                table.insert(notes, msg)
            else
                table.insert(issues, msg)
            end
        else
            table.insert(ok_parts, 'TakeOffTime=' .. tostring(actual_raw))
        end
    end

    if #ok_parts == 0 and #issues == 0 and #notes == 0 then
        print('NOTE: Mission schedule verify — ' .. label .. ': no expected fields to compare')
        return true
    end
    if #issues > 0 then
        local snapshot = 'GetMission snapshot — starttime=' .. tostring(m.starttime or '') ..
            ' TakeOffTime=' .. tostring(m.TakeOffTime or '') ..
            ' TimeOnTargetStation=' .. tostring(m.TimeOnTargetStation or '')
        local msg = 'Mission schedule verify FAILED — ' .. label .. ': ' ..
            table.concat(issues, '; ') .. ' | ' .. snapshot
        if fatal then
            M._abort_scenario_generation(msg)
        end
        print('ERROR: ' .. msg)
        return false
    end
    local ok_msg = 'OK: Mission schedule verify — ' .. label .. ': ' .. table.concat(ok_parts, ', ')
    if #notes > 0 then
        ok_msg = ok_msg .. ' | NOTE: ' .. table.concat(notes, '; ')
    end
    print(ok_msg)
    return true
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

-- Strike-ship weapon policy (any surface unit on a Strike mission): standoff missiles only;
-- main gun never on land; surface gun only when threatened (WCS HOLD + WRA self-defence).
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

function M._apply_strike_ship_gun_wra(unit_guid, side, gun_dbids)
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
    local mission = M.state.STRIKE_AIR_MISSION or M.state.TLAM_STRIKE_MISSION
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

function M.configure_strike_ship_weapon_policy(unit, opts)
    opts = opts or {}
    if not unit or not unit.guid then
        return 0, 0
    end
    local side = opts.side or M.state.strike_side or 'United States'
    local u = ScenEdit_GetUnit({ guid = unit.guid })
    if not u then
        return 0, 0
    end
    -- Unit doctrine overrides shared strike mission (ShotgunOneEngagement* allows gun fallback when magazines spent).
    -- Land WCS stays inherited so missiles can engage assigned targets; guns blocked via WRA + ShotgunBVR.
    ScenEdit_SetDoctrine({ side = side, guid = unit.guid }, {
        weapon_state_planned = 'ShotgunBVR',
        weapon_state_rtb = 'Winchester',
        engage_opportunity_targets = false,
        gun_strafing = 0,
        weapon_control_status_surface = 0,
        weapon_control_status_subsurface = 0,
    })
    local land_rules, surface_rules = M._apply_strike_ship_gun_wra(
        unit.guid, side, M._collect_strike_gun_weapon_dbids(u))
    if land_rules > 0 or surface_rules > 0 then
        print('OK: ' .. tostring(u.name or unit.guid) ..
            ' — strike ship guns: land blocked (' .. land_rules ..
            ' WRA), surface self-defence only (' .. surface_rules .. ' WRA)')
    end
    return land_rules, surface_rules
end

M.disable_strike_guns_on_unit = M.configure_strike_ship_weapon_policy

function M.build_strike_ship_weapon_policy_script(ship_unit)
    if not ship_unit or not ship_unit.guid then
        return ''
    end
    local side = M._q_lua_str(M.state.strike_side or 'United States')
    local guid = ship_unit.guid
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
        "  ScenEdit_SetDoctrine({side='" .. side .. "', guid='" .. guid .. "'}, {weapon_state_planned='ShotgunBVR', weapon_state_rtb='Winchester', engage_opportunity_targets=false, gun_strafing=0, weapon_control_status_surface=0, weapon_control_status_subsurface=0})",
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

M.build_tlam_shooter_weapon_policy_script = M.build_strike_ship_weapon_policy_script
M.build_disable_strike_guns_script = M.build_strike_ship_weapon_policy_script

-- Re-apply strike-ship gun block at Play (mission assign can reset unit WRA / weapon state).
function M.add_strike_ship_weapon_policy_event(ship_unit, opts)
    opts = opts or {}
    if not ship_unit or not ship_unit.guid then
        return false
    end
    local script = M.build_strike_ship_weapon_policy_script(ship_unit)
    if script == '' then
        return false
    end
    local base_event = opts.event_name or ('Strike ship gun policy ' .. tostring(ship_unit.name or ship_unit.guid))
    local start_date = opts.start_date or M.state.strike_package_date
    local refresh_times = opts.refresh_times
    if not refresh_times then
        refresh_times = { '00:00:05' }
        if M.state.tlam_launch_time then
            table.insert(refresh_times, M.state.tlam_launch_time)
        end
    end

    for _, suffix in ipairs({ '', ' (load)', ' (time)' }) do
        local label = base_event .. suffix
        pcall(function() ScenEdit_SetEvent(label, { mode = 'remove' }) end)
        pcall(function() ScenEdit_SetTrigger({ mode = 'remove', name = label .. ' trigger' }) end)
        pcall(function() ScenEdit_SetAction({ mode = 'remove', name = label .. ' action' }) end)
    end
    for i = 1, #refresh_times do
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
    for i, hhmmss in ipairs(refresh_times) do
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
    print('OK: Strike ship gun policy events for ' .. tostring(ship_unit.name) ..
        ' — ScenLoaded + ' .. table.concat(time_labels, ', '))
    return true
end

-- Unify naval strike assets on the package Strike mission (in formation). All TLAM-capable hulls may fire; gun policy per hull.
-- Function name is historical (STRIKE_AIR_MISSION); concept = strike asset unification, not "CSG joins air strike".
function M.setup_csg_strike_on_air_strike(group_name, strike_ships)
    if not group_name or group_name == '' then
        M._abort_scenario_generation('setup_csg_strike_on_air_strike — group_name required')
    end
    if not strike_ships or #strike_ships == 0 then
        M._abort_scenario_generation('setup_csg_strike_on_air_strike — no strike ships')
    end
    local side = M.state.strike_side or 'United States'
    local strike_mission = M.state.STRIKE_AIR_MISSION
    if not strike_mission then
        M._abort_scenario_generation('setup_csg_strike_on_air_strike — STRIKE_AIR_MISSION not configured')
    end
    M.configure_naval_strike_doctrine(side)
    local sched = M.strike_schedule_datetimes()
    local ok_count, fail_count = 0, 0
    for _, ship_unit in ipairs(strike_ships) do
        if ship_unit and ship_unit.guid then
            if M.assign_ship_to_mission(side, ship_unit, strike_mission, group_name) then
                ok_count = ok_count + 1
                print('Strike package naval asset: ' .. tostring(ship_unit.name) .. ' → ' .. strike_mission ..
                    ' (group ' .. tostring(group_name) .. ')')
                M.configure_strike_ship_weapon_policy(ship_unit, { side = side })
                M.add_strike_ship_weapon_policy_event(ship_unit)
            else
                fail_count = fail_count + 1
                M._abort_scenario_generation('strike package naval assign failed: ' .. tostring(ship_unit.name))
            end
        end
    end
    if ok_count > 0 then
        M.set_naval_strike_schedule(side, strike_mission, sched.tlam_launch, sched.tot)
        if sched.tlam_launch then
            print('OK: ' .. strike_mission .. ' launch=' .. tostring(sched.tlam_launch) ..
                ' TOT=' .. tostring(sched.tot) .. ' (' .. ok_count .. ' CSG hull(s))')
        else
            print('OK: ' .. strike_mission .. ' TOT=' .. tostring(sched.tot) ..
                ' (' .. ok_count .. ' CSG hull(s))')
        end
    end
    M._restore_air_after_naval_schedule_mutation()
    for _, ship_unit in ipairs(strike_ships) do
        if ship_unit and ship_unit.guid then
            M.configure_strike_ship_weapon_policy(ship_unit, { side = side })
        end
    end
    print('OK: unified strike package — ' .. ok_count .. ' naval asset(s), ' .. fail_count .. ' failed on ' .. strike_mission)
    return ok_count > 0 and fail_count == 0
end

function M._q_lua_str(s)
    return tostring(s):gsub("'", "\\'")
end

function M.finalize_strike_air_after_flight_plan()
    local air_mission = M.state.STRIKE_AIR_MISSION
    local side = M.state.strike_side
    local sched = M.strike_schedule_datetimes()
    local m = ScenEdit_GetMission(side, air_mission)
    if m and m.updateWPtimes then
        local ok_wp, err_wp = pcall(function()
            m:updateWPtimes()
        end)
        if not ok_wp then
            print('WARNING: updateWPtimes failed: ' .. tostring(err_wp))
        end
    end
    -- CreateMissionFlightPlan may drop assignments; restore all spawned aircraft (never SetMission on strike package here).
    local ok, fail = M.refresh_spawned_air_assignments(nil)
    if fail > 0 then
        ok, fail = M.refresh_spawned_air_assignments(nil)
    end
    print('Air assign after flight plan: ' .. ok .. ' OK, ' .. fail .. ' failed')
    -- Reassert TOT via wrapper only (SetMission on strike package after assign clears ORBAT).
    M.set_strike_tot_schedule(side, air_mission, sched.tot, {
        skip_flight_plan = true,
        wrapper_only = true,
        verify = true,
    })
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

-- Re-apply patrol/strike mission schedule at Play (carrier air ops can clear ME schedule).
function M.add_mission_schedule_restore_event(opts)
    opts = opts or {}
    local side = opts.side or M.state.strike_side or 'United States'
    local missions = opts.missions
    if not missions or #missions == 0 then
        return false
    end
    local start_date = opts.start_date or M.state.strike_package_date
    local schedule_mode = opts.schedule_mode or 'takeoff'
    local takeoff_hms = opts.takeoff_hms
    local station_hms = opts.station_hms or takeoff_hms
    if schedule_mode == 'on_station' then
        if not station_hms then
            return false
        end
    elseif not takeoff_hms then
        return false
    end
    local takeoff_dt = takeoff_hms and M.mission_schedule_datetime(start_date, takeoff_hms) or nil
    local station_dt = station_hms and M.mission_schedule_datetime(start_date, station_hms) or nil
    local flight_size = opts.flight_size or 2
    local min_req = opts.min_aircraft_req or 2
    local restore_times = opts.restore_times or { '00:00:05' }
    local base_event = opts.event_name or 'Mission schedule restore'
    local trigger_hms = (schedule_mode == 'on_station') and station_hms or takeoff_hms

    local lines = {}
    for _, mission_name in ipairs(missions) do
        if schedule_mode == 'on_station' and station_hms and station_dt then
            table.insert(lines, string.format(
                "ScenEdit_CreateMissionFlightPlan('%s', '%s', {DATEONTARGET='%s', TIMEONTARGET='%s'})",
                side:gsub("'", "\\'"),
                mission_name:gsub("'", "\\'"),
                start_date:gsub("'", "\\'"),
                station_hms
            ))
            table.insert(lines, string.format(
                "ScenEdit_SetMission('%s', '%s', {TimeOnTargetStation='%s', UseFlightSize=true, FlightSize=%d, MinAircraftReq=%d, OnDeactivateUassign=false, isactive=true})",
                side:gsub("'", "\\'"),
                mission_name:gsub("'", "\\'"),
                station_dt:gsub("'", "\\'"),
                flight_size,
                min_req
            ))
        else
            table.insert(lines, string.format(
                "ScenEdit_SetMission('%s', '%s', {starttime='%s', TakeOffTime='%s', UseFlightSize=true, FlightSize=%d, MinAircraftReq=%d, OnDeactivateUassign=false, isactive=true})",
                side:gsub("'", "\\'"),
                mission_name:gsub("'", "\\'"),
                takeoff_dt,
                takeoff_dt,
                flight_size,
                min_req
            ))
        end
    end
    table.insert(lines, "print('OK: Mission schedule restore — " .. #missions .. " mission(s)')")
    local base_script = table.concat(lines, '\r\n')
    local full_script = base_script
    if opts.extra_script and opts.extra_script ~= '' then
        full_script = base_script .. '\r\n' .. opts.extra_script
    end

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

    local function register_event(event_label, trigger_name, trigger_def, event_script)
        local action_name = event_label .. ' action'
        ScenEdit_SetTrigger(trigger_def)
        ScenEdit_SetAction({
            mode = 'add',
            type = 'LuaScript',
            name = action_name,
            ScriptText = event_script or base_script,
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
    }, base_script)

    local time_labels = {}
    for i, hhmmss in ipairs(restore_times) do
        local dt = M.mission_schedule_datetime(start_date, hhmmss)
        local event_label = base_event .. ' (time ' .. i .. ')'
        local event_script = base_script
        if opts.extra_script and opts.extra_script ~= '' and hhmmss == trigger_hms then
            event_script = full_script
        end
        register_event(event_label, event_label .. ' trigger', {
            mode = 'add',
            type = 'Time',
            name = event_label .. ' trigger',
            Time = dt,
        }, event_script)
        table.insert(time_labels, dt)
    end

    local mode_label = (schedule_mode == 'on_station') and 'on-station' or 'takeoff'
    print('OK: Mission schedule restore "' .. base_event .. '" (' .. mode_label .. ') — ScenLoaded + ' ..
        #restore_times .. ' Time trigger(s)' ..
        (#time_labels > 0 and (' | times=' .. table.concat(time_labels, ', ')) or ''))
    return true
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

function M.verify_tlam_mission_has_shooter(ship_unit)
    local side = M.state.strike_side
    local naval_mission = M.state.TLAM_STRIKE_MISSION
    if not ship_unit or not ship_unit.guid then
        print('WARNING: TLAM salvo — no CG shooter placed')
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
        M._abort_scenario_generation('Missing LoadoutID for ' .. unitname .. ' (DBID ' .. dbid .. ')')
    end
    if not base_guid then
        M._abort_scenario_generation('No base for ' .. unitname)
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
        M._abort_scenario_generation('Air spawn failed: ' .. unitname)
    end

    local created = ScenEdit_GetUnit({ guid = u.guid })
    if created and created.loadoutdbid ~= nil and tonumber(created.loadoutdbid) ~= tonumber(loadoutid) then
        print('WARNING: Loadout mismatch for ' .. unitname .. ' | preferred=' .. loadoutid ..
            ' active=' .. tostring(created.loadoutdbid))
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
            M._abort_scenario_generation('AssignUnitToMission failed: ' .. unitname .. ' -> ' .. mission_name)
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
        M._abort_scenario_generation('Facility placement underwater at ' .. unitname .. ' at ' .. latitude .. ',' .. longitude ..
            ' (elevation=' .. tostring(elev) .. 'm)')
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
        M._abort_scenario_generation('Could not place base: ' .. unitname)
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
        M._abort_scenario_generation('Could not place SAM: ' .. unitname)
    end
    return sam
end

function M.place_sub(side, unitname, dbid, latitude, longitude)
    local elev = World_GetElevation({ latitude = latitude, longitude = longitude })
    if elev and elev > 0 then
        M._abort_scenario_generation('Submarine placement over land: ' .. unitname .. ' at ' .. latitude .. ',' .. longitude)
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
        M._abort_scenario_generation('Could not place submarine: ' .. unitname)
    end
    return sub
end

function M.place_ship(side, unitname, dbid, latitude, longitude)
    local elev = World_GetElevation({ latitude = latitude, longitude = longitude })
    if elev and elev > 0 then
        M._abort_scenario_generation('Cannot place ship over land: ' .. unitname .. ' at ' .. latitude .. ',' .. longitude ..
            ' (elevation=' .. tostring(elev) .. 'm)')
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
        M._abort_scenario_generation('Could not place ship: ' .. unitname)
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

-- Filled by generate_scenario.py from DataWarhead.Type=4001 (EnumWarheadType Nuclear).
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

-- CVN + CG + DDGs in one CMO group.
function M.form_csg_group(group_name, lead, members)
    if not lead or not lead.guid then
        M._abort_scenario_generation('CSG group without lead')
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

-- Civilian airliners: exit the engagement box on a plotted course, or RTB and land.
-- Avoids aimless loiter/circles in the play area (logic_checks_cmo.md §11).
M.CIVILIAN_ENDURANCE_H = {
    [3977] = 20.0,  -- Boeing 777-200
    [3970] = 7.0,   -- Boeing 737-800
    [32] = 18.0,    -- Airbus A.340-500
    [604] = 16.0,   -- Boeing 747-200B
    [2591] = 4.5,   -- ATR-72-500
}

function M._transit_waypoint_nm(lat, lon, heading_deg, distance_nm)
    local h = math.rad(heading_deg)
    local dlat = math.cos(h) * distance_nm / 60.0
    local dlon = math.sin(h) * distance_nm / (60.0 * math.max(0.1, math.cos(math.rad(lat))))
    return lat + dlat, lon + dlon
end

function M._point_outside_theater(lat, lon, theater)
    return lat < theater.lat_min or lat > theater.lat_max
        or lon < theater.lon_min or lon > theater.lon_max
end

function M._theater_exit_distance_nm(lat, lon, heading, theater, leg_nm)
    leg_nm = leg_nm or 150
    local clat, clon = lat, lon
    local total = 0
    for _ = 1, 50 do
        clat, clon = M._transit_waypoint_nm(clat, clon, heading, leg_nm)
        total = total + leg_nm
        if M._point_outside_theater(clat, clon, theater) then
            return total
        end
    end
    return total
end

function M._theater_exit_course(lat, lon, heading, theater, leg_nm)
    leg_nm = leg_nm or 150
    local course = {}
    local clat, clon = lat, lon
    for _ = 1, 50 do
        clat, clon = M._transit_waypoint_nm(clat, clon, heading, leg_nm)
        table.insert(course, { latitude = clat, longitude = clon })
        if M._point_outside_theater(clat, clon, theater) then
            clat, clon = M._transit_waypoint_nm(clat, clon, heading, leg_nm)
            table.insert(course, { latitude = clat, longitude = clon })
            break
        end
    end
    return course
end

function M._bearing_deg(lat1, lon1, lat2, lon2)
    local lat1r, lat2r = math.rad(lat1), math.rad(lat2)
    local dlon = math.rad(lon2 - lon1)
    local y = math.sin(dlon) * math.cos(lat2r)
    local x = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.deg(math.atan(y, x)) + 360) % 360
end

function M._heading_delta(from_deg, to_deg)
    return math.abs((to_deg - from_deg + 180) % 360 - 180)
end

function M._heading_course_nm(lat, lon, heading, distance_nm, leg_nm)
    leg_nm = leg_nm or 150
    if distance_nm <= 0 then
        return {}
    end
    local num_legs = math.max(1, math.ceil(distance_nm / leg_nm))
    local step = distance_nm / num_legs
    local course = {}
    local clat, clon = lat, lon
    for _ = 1, num_legs do
        clat, clon = M._transit_waypoint_nm(clat, clon, heading, step)
        table.insert(course, { latitude = clat, longitude = clon })
    end
    return course
end

function M._transit_course_capped(lat, lon, heading, theater, leg_nm, speed_kts, dbid)
    local exit_nm = M._theater_exit_distance_nm(lat, lon, heading, theater, leg_nm)
    local endurance_nm = speed_kts * M._civilian_endurance_hours(dbid)
    if exit_nm <= endurance_nm then
        return M._theater_exit_course(lat, lon, heading, theater, leg_nm)
    end
    return M._heading_course_nm(lat, lon, heading, endurance_nm, leg_nm)
end

function M._course_approach_airport(lat, lon, heading, dest_lat, dest_lon, leg_nm, lead_nm)
    leg_nm = leg_nm or 150
    lead_nm = lead_nm or 80
    local course = {}
    local clat, clon = lat, lon
    local lead_legs = math.max(1, math.ceil(lead_nm / leg_nm))
    local lead_step = lead_nm / lead_legs
    for _ = 1, lead_legs do
        clat, clon = M._transit_waypoint_nm(clat, clon, heading, lead_step)
        table.insert(course, { latitude = clat, longitude = clon })
    end
    local current_hdg = heading
    local target_bearing = M._bearing_deg(clat, clon, dest_lat, dest_lon)
    local turn_step = 15
    for _ = 1, 24 do
        local delta = M._heading_delta(current_hdg, target_bearing)
        if delta <= 5 then
            break
        end
        local step = math.min(turn_step, delta)
        if ((target_bearing - current_hdg + 360) % 360) > 180 then
            step = -step
        end
        current_hdg = (current_hdg + step + 360) % 360
        clat, clon = M._transit_waypoint_nm(clat, clon, current_hdg, leg_nm)
        table.insert(course, { latitude = clat, longitude = clon })
    end
    table.insert(course, { latitude = dest_lat, longitude = dest_lon })
    return course
end

function M._civilian_airport_by_guid(guid)
    for _, ap in ipairs(M.state.civilian_airports or {}) do
        if ap.guid == guid then
            return ap
        end
    end
    return nil
end

function M._airport_best_aligned(lat, lon, heading)
    local airports = M.state.civilian_airports or {}
    local best, best_delta = nil, math.huge
    for _, ap in ipairs(airports) do
        local brg = M._bearing_deg(lat, lon, ap.lat, ap.lon)
        local delta = M._heading_delta(heading, brg)
        if delta < best_delta then
            best, best_delta = ap, delta
        end
    end
    return best
end

function M._set_unit_max_fuel(guid)
    local u = ScenEdit_GetUnit({ guid = guid })
    if not u or not u.fuel then
        return
    end
    local fuel_updates = {}
    for _, f in pairs(u.fuel) do
        if f.max and f.max > 0 then
            table.insert(fuel_updates, { f.name or f.type, f.max })
        end
    end
    if #fuel_updates > 0 then
        ScenEdit_SetUnit({ guid = guid, fuel = fuel_updates })
    end
end

function M._civilian_endurance_hours(dbid)
    return M.CIVILIAN_ENDURANCE_H[dbid] or 8.0
end

function M._nearest_civilian_airport(lat, lon)
    local airports = M.state.civilian_airports or {}
    local best, best_d2 = nil, math.huge
    for _, ap in ipairs(airports) do
        local dlat = lat - ap.lat
        local dlon = (lon - ap.lon) * math.cos(math.rad(lat))
        local d2 = dlat * dlat + dlon * dlon
        if d2 < best_d2 then
            best, best_d2 = ap, d2
        end
    end
    return best
end

function M.configure_civilian_traffic(opts)
    opts = opts or {}
    if opts.theater then
        M.state.civilian_theater = opts.theater
    end
end

function M.register_civilian_airport(side, name, lat, lon)
    local base = M.place_base(side, name, lat, lon)
    if base then
        table.insert(M.state.civilian_airports, {
            guid = base.guid, lat = lat, lon = lon, name = name,
        })
    end
    return base
end

function M.add_civilian_airliner(side, unitname, dbid, loadoutid, lat, lon, alt_m, heading, speed_kts, opts)
    opts = opts or {}
    local theater = opts.theater or M.state.civilian_theater
    if not theater then
        M._abort_scenario_generation('add_civilian_airliner: set theater via configure_civilian_traffic or opts.theater')
    end
    local leg_nm = opts.leg_nm or 150
    local u = ScenEdit_AddUnit({
        type = 'Air', side = side, unitname = unitname, dbid = dbid,
        loadoutid = loadoutid, latitude = lat, longitude = lon,
        altitude = alt_m, heading = heading,
    })
    if not u or not u.guid then
        print('ERROR: could not place civilian airliner: ' .. unitname)
        return nil
    end
    M._set_unit_max_fuel(u.guid)

    local mode = opts.mode or 'auto'
    local set = { guid = u.guid, heading = heading, speed = speed_kts }
    local land_base = opts.base_guid

    if mode == 'land' or land_base then
        local ap = (land_base and M._civilian_airport_by_guid(land_base))
            or M._airport_best_aligned(lat, lon, heading)
            or M._nearest_civilian_airport(lat, lon)
        if not ap then
            print('ERROR: no civilian airport for landing approach: ' .. unitname)
            return u
        end
        set.course = opts.course or M._course_approach_airport(
            lat, lon, heading, ap.lat, ap.lon, leg_nm, opts.lead_nm)
        set.base = ap.guid
    elseif mode == 'transit' then
        set.course = opts.course or M._theater_exit_course(lat, lon, heading, theater, leg_nm)
    else
        set.course = opts.course or M._transit_course_capped(
            lat, lon, heading, theater, leg_nm, speed_kts, dbid)
    end

    ScenEdit_SetUnit(set)
    return u
end

function M.assert_db_series(scenario_year, expected)
    expected = expected or 'DB3K'
    local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
    M.state.db_series = db_series
    M.state.scenario_year = scenario_year
    if db_series ~= expected then
        M._abort_scenario_generation('Scenario year ' .. scenario_year .. ' expects database series ' .. expected)
    end
    return true
end

cmo = M
return M
