-- CMO Scenario: Caribbean Pressure 2026 (fictief)
-- United States vs Cuba — fase 1: luchtoperatie (ISR, SEAD, strike op bases/IADS)
-- Geïnspireerd op publieke berichtgeving over VS-militaire opbouw rond Cuba (2026); geen politieke claim.
--
-- OOB (Order of Battle)
-- Jaar/DB: 2026 | DB3K v515 (geen mixed DB3K/CWDB ID's)
-- Posture: United States <-> Cuba = Hostile
--
-- United States (offensief)
-- Zee (CSG): CVN 68 (429) + CG 52 (547, TLAM + 2× MH-60R ASuW) + 2× DDG 51 (112, US operator; 2+1 MH-60R ASW)
-- Helos: 3× MH-60R ASW + 2× MH-60R Hellfire — DDG heeft maar 2 vliegdekplekken; verdeeld over DDG/CG
-- Land: Florida Forward Staging (B-52 CALCM, MQ-4C, KC-46 tankers)
-- Missies: AEW, ISR, CAP, SEAD×2, CSG Station Keeping (formatie), helo ASW/ASuW, Caribbean Thunder Strike (+ escort)
-- Lucht (~75): 2× E-2D (690/14629), 8× EA-18G (343/2954), 6× F/A-18E SEAD escort (342/12040),
--               12× F/A-18E strike escort (342/12040), 18× CAP (342/12040),
--               4× F-35C strike (824/6945 JDAM), 4× F/A-18E JDAM (342/985), 4× F/A-18E JSOW (342/3727),
--               4× B-52H CALCM (567/678), 3× MQ-4C (2846/13986) — geen KC: CSG/CALCM binnen bereik zonder AAR
-- Doctrine: Veteran, WCS TIGHT (SEAD-missies: land FREE)
--
-- Cuba (defensief)
-- Bases (2): San Antonio de los Baños, Santiago de Cuba
-- Zee (MGR, Wikipedia ca. 2020s): 2× Rio Damuji, 1× Pauk II, 3× Osa II (205ER), 1× Sonya, 1× Yevgenya,
--   2× Zhuk, 2× Stenka, 1× Delfin — alle OperatorCountry Cuba (DB3K); geen Sovjet-hulls
-- Missies: Havana CAP, Eastern CAP, Coastal Defense Patrol
-- Lucht (~48): 36x MiG-29 (845/5252), 12x MiG-23ML (2059/7164)
-- IADS (4): 2x SA-2b (1296), 2x SA-3b (1297)
-- Doctrine: Regular, WCS FREE
--
-- Strike-doelen (VS): Cubaanse bases + SAM-batterijen
-- Preflight: python scripts/db_search.py --validate-scenario generated/cuba_pressure_2026.lua --series DB3K --version 515
-- @strike_package mission=Caribbean Thunder Strike profile=standoff date=2026/06/01 time=06:30:00 max_spread=15 flight_size=4 use_flight_size=true min_aircraft=8 escort_flight_size=4 escort_use_flight_size=true
-- @strike_wave id=tlam role=naval_strike offset=0 mission=Caribbean TLAM Salvo
-- @naval_package mission=Caribbean TLAM Salvo launch=05:54:00 tot=06:30:00 minutes_before_strike_tot=36
-- @strike_wave id=carrier_strike role=air_strike offset=0
-- @strike_wave id=buff_calcm role=air_standoff offset=0
-- @sead_package missions=Wild Weasel SEAD West,Wild Weasel SEAD East,SEAD Escort CAP date=2026/06/01 takeoff=06:12:00 minutes_before_strike_tot=18
-- @scenario_policy nuclear=false
local scenario_year = 2026
local strike_package_date = '2026/06/01'
local strike_package_tot = '06:30:00'
-- SEAD + SEAD-escort pas opstijgen kort vóór TOT, zodat strike-escorts/strikers eerst in de lucht zijn.
local sead_package_takeoff = '06:12:00'
-- TLAM van CSG (~250–285 nm): ~33 min cruise vóór impact op verst doel; niet op de lucht-strike-missie.
local tlam_launch_time = '05:54:00'
local csg_helo_takeoff = '05:35:00'
-- ScenEdit_SetMission gebruikt YYYY.MM.DD (zelfde als ScenEdit_SetTime dateformat=YYYYMMDD).
-- CreateMissionFlightPlan gebruikt DATEONTARGET YYYY/MM/DD — niet door elkaar halen.
local function mission_schedule_date(date_slash)
    return date_slash:gsub('/', '.')
end

local function mission_schedule_datetime(date_slash, time_hms)
    return mission_schedule_date(date_slash)..' '..time_hms
end

local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
if db_series ~= 'DB3K' then
    print('ERROR: Caribbean Pressure 2026 verwacht DB3K. Controleer scenariojaar/database.')
    return
end

local BASE_FACILITY_DBID = 1995

ScenEdit_AddSide({side='United States', weighting=0})
ScenEdit_AddSide({side='Cuba', weighting=0})
ScenEdit_SetSidePosture('United States', 'Cuba', 'H')
ScenEdit_SetSidePosture('Cuba', 'United States', 'H')

-- Start 04:30: B-52 CALCM van Florida (~430–690 nm) heeft ~75–110 min transit; carrier/TLAM passen in 60 min.
ScenEdit_SetTime({
    dateformat = 'YYYYMMDD',
    date = '2026.06.01',
    time = '04:30:00',
    StartDate = '2026.06.01',
    StartTime = '04:30:00',
})

-- Bijhouden voor eindtoewijzing (flight plan kan strike-units tijdelijk loskoppelen).
local spawned_air_missions = {}
local mission_guid_cache = {}

local function resolve_mission_guid(side, mission_name)
    if not mission_name or mission_name == '' then
        return nil
    end
    local key = side..'|'..mission_name
    if mission_guid_cache[key] then
        return mission_guid_cache[key]
    end
    local m = ScenEdit_GetMission(side, mission_name)
    if m and m.guid then
        mission_guid_cache[key] = m.guid
        return m.guid
    end
    return nil
end

local function assign_air_to_mission(side, unit_guid, unit_name, mission_name, strike_escort)
    if not unit_guid or not mission_name then
        return false
    end
    local mission_guid = resolve_mission_guid(side, mission_name)
    local unit_refs = {unit_guid}
    if unit_name and unit_name ~= '' then
        table.insert(unit_refs, unit_name)
    end
    local mission_refs = {}
    if mission_guid then
        table.insert(mission_refs, mission_guid)
    end
    table.insert(mission_refs, mission_name)

    for _, uref in ipairs(unit_refs) do
        for _, mref in ipairs(mission_refs) do
            local assigned
            if strike_escort then
                assigned = ScenEdit_AssignUnitToMission(uref, mref, true)
            else
                assigned = ScenEdit_AssignUnitToMission(uref, mref)
            end
            if assigned then
                return true
            end
        end
    end

    local u_check = ScenEdit_GetUnit({guid=unit_guid})
    if u_check then
        local on_mission = u_check.assignedMission or u_check.mission or ''
        if on_mission ~= '' then
            if on_mission == mission_name or on_mission == (mission_guid or '') then
                return true
            end
            if string.find(string.lower(on_mission), string.lower(mission_name), 1, true) then
                return true
            end
        end
    end

    -- Strike-escort hoort in de escort-laag; SetUnit kent geen escort-flag.
    if not strike_escort then
        ScenEdit_SetUnit({guid=unit_guid, side=side, mission=mission_name})
        if mission_guid then
            ScenEdit_SetUnit({guid=unit_guid, side=side, mission=mission_guid})
        end
        local u = ScenEdit_GetUnit({guid=unit_guid})
        if u then
            if u.assignedMission and u.assignedMission ~= '' then
                return true
            end
            if u.mission and u.mission ~= '' then
                return true
            end
        end
    end
    return false
end

-- Schepen in een CSG-groep verliezen vaak hun missie bij SetUnit(group=…) of SetMission; herhaal toewijzing.
local function assign_ship_to_mission(side, ship_unit, mission_name)
    if not ship_unit or not ship_unit.guid or not mission_name then
        return false
    end
    local mission_guid = resolve_mission_guid(side, mission_name)
    local unit_refs = {ship_unit.guid}
    if ship_unit.name and ship_unit.name ~= '' then
        table.insert(unit_refs, ship_unit.name)
    end
    local mission_refs = {}
    if mission_guid then
        table.insert(mission_refs, mission_guid)
    end
    table.insert(mission_refs, mission_name)

    for _, uref in ipairs(unit_refs) do
        for _, mref in ipairs(mission_refs) do
            if ScenEdit_AssignUnitToMission(uref, mref) then
                return true
            end
        end
    end

    ScenEdit_SetUnit({guid=ship_unit.guid, side=side, mission=mission_name})
    if mission_guid then
        ScenEdit_SetUnit({guid=ship_unit.guid, side=side, mission=mission_guid})
    end
    local u = ScenEdit_GetUnit({guid=ship_unit.guid})
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
    return false
end

local function refresh_spawned_air_assignments(mission_filter)
    local ok_n, fail_n = 0, 0
    for _, entry in ipairs(spawned_air_missions) do
        if not mission_filter or entry.mission == mission_filter then
            if assign_air_to_mission(entry.side, entry.guid, entry.name, entry.mission, entry.escort) then
                ok_n = ok_n + 1
            else
                fail_n = fail_n + 1
            end
        end
    end
    return ok_n, fail_n
end

local function sync_strike_package_tot()
    ScenEdit_SetMission('United States', 'Caribbean Thunder Strike', {
        TimeOnTargetStation = strike_tot_dt,
        OnDeactivateUassign = false,
    })
    ScenEdit_SetMission('United States', 'Caribbean TLAM Salvo', {
        starttime = tlam_launch_dt,
        TimeOnTargetStation = strike_tot_dt,
        OnDeactivateUassign = false,
    })
end

local TLAM_STRIKE_MISSION = 'Caribbean TLAM Salvo'

local function assign_tlam_shooter(ship_unit)
    if not ship_unit then
        return false
    end
    return assign_ship_to_mission('United States', ship_unit, TLAM_STRIKE_MISSION)
end

local function verify_tlam_mission_has_shooter(ship_unit)
    if not ship_unit or not ship_unit.guid then
        print('WARNING: TLAM salvo — geen CG-shooter geplaatst')
        return false
    end
    local m = ScenEdit_GetMission('United States', TLAM_STRIKE_MISSION)
    if not m then
        print('WARNING: Mission '..TLAM_STRIKE_MISSION..' NOT found')
        return false
    end
    if m.unitlist then
        for _, ug in ipairs(m.unitlist) do
            if ug == ship_unit.guid then
                print('OK: '..TLAM_STRIKE_MISSION..' has shooter on unitlist ('..tostring(ship_unit.name)..')')
                return true
            end
        end
    end
    local u = ScenEdit_GetUnit({guid=ship_unit.guid})
    local on_mission = ''
    if u then
        on_mission = tostring(u.assignedMission or u.mission or '')
    end
    if on_mission ~= '' and string.find(string.lower(on_mission), 'tlam', 1, true) then
        print('OK: '..tostring(ship_unit.name)..' assigned to '..on_mission..' (unitlist check inconclusive)')
        return true
    end
    print('WARNING: '..TLAM_STRIKE_MISSION..' has no shooter on unitlist — '..tostring(ship_unit.name)..
        ' shows mission="'..on_mission..'"')
    return false
end

local function add_air_unit_checked(side, unitname, dbid, base_guid, loadoutid, mission_name, strike_escort)
    if loadoutid == nil then
        print('ERROR: Missing LoadoutID voor '..unitname..' (DBID '..dbid..')')
        return nil
    end
    if not base_guid then
        print('ERROR: Geen basis voor '..unitname)
        return nil
    end

    local host = ScenEdit_GetUnit({guid=base_guid})
    local base_ref = tostring(base_guid)
    if host and host.name then
        base_ref = host.name
    end

    local add_params = {
        type='Air',
        unitname=unitname,
        side=side,
        dbid=dbid,
        base=base_ref,
        loadoutid=loadoutid,
        altitude='0',
    }
    if mission_name and not strike_escort then
        add_params.mission = mission_name
    end
    if host and host.latitude and host.longitude then
        add_params.latitude = host.latitude
        add_params.longitude = host.longitude
    end
    local u = ScenEdit_AddUnit(add_params)

    if not u then
        print('ERROR: ScenEdit_AddUnit mislukt: '..unitname..' side='..side..' dbid='..dbid..
            ' loadout='..tostring(loadoutid)..' base='..tostring(base_guid))
        return nil
    end
    if not u.guid then
        print('ERROR: ScenEdit_AddUnit returned no guid for: '..unitname)
        return nil
    end

    local created = ScenEdit_GetUnit({guid=u.guid})
    if created and created.loadoutdbid ~= nil and tonumber(created.loadoutdbid) ~= tonumber(loadoutid) then
        print('WARNING: Loadout afwijking voor '..unitname..' | preferred='..loadoutid..' actief='..tostring(created.loadoutdbid))
    end

    if mission_name then
        ScenEdit_SetUnit({guid=u.guid, timetoready_minutes=0})
        table.insert(spawned_air_missions, {
            guid = u.guid,
            name = unitname,
            side = side,
            mission = mission_name,
            escort = strike_escort,
        })
        local assigned = assign_air_to_mission(side, u.guid, unitname, mission_name, strike_escort)
        if not assigned then
            print('ERROR: AssignUnitToMission mislukt: '..unitname..' -> '..mission_name)
        end
    else
        print('WARNING: Geen missie voor vliegtuig '..unitname)
    end
    return u
end

local function spawn_air_wing(side, prefix, count, dbid, loadoutid, mission_name, base_guid, strike_escort)
    for i = 1, count do
        add_air_unit_checked(side, prefix..' #'..i, dbid, base_guid, loadoutid, mission_name, strike_escort)
    end
end

local function place_base(side, unitname, latitude, longitude)
    local base = ScenEdit_AddUnit({
        type='Facility',
        unitname=unitname,
        side=side,
        dbid=BASE_FACILITY_DBID,
        latitude=latitude,
        longitude=longitude,
        altitude=0
    })
    if not base then
        print('ERROR: Basis kon niet worden geplaatst: '..unitname)
    end
    return base
end

local function place_sam(side, unitname, dbid, latitude, longitude)
    local sam = ScenEdit_AddUnit({
        type='Facility',
        unitname=unitname,
        side=side,
        dbid=dbid,
        latitude=latitude,
        longitude=longitude,
        altitude=0
    })
    if not sam then
        print('ERROR: SAM kon niet worden geplaatst: '..unitname)
    end
    return sam
end

local function place_sub(side, unitname, dbid, latitude, longitude)
    local elev = World_GetElevation({latitude=latitude, longitude=longitude})
    if elev and elev > 0 then
        print('ERROR: Submarine placement over land: '..unitname..' at '..latitude..','..longitude)
        return nil
    end

    -- CMO verwacht type 'Sub' (niet 'Submarine'); zie generated/pakistan_india_scenario.lua
    local sub = ScenEdit_AddUnit({
        type='Sub',
        unitname=unitname,
        side=side,
        dbid=dbid,
        latitude=latitude,
        longitude=longitude,
        altitude=-50,
    })
    if not sub then
        print('ERROR: Onderzeeër kon niet worden geplaatst: '..unitname)
    end
    return sub
end

local function place_ship(side, unitname, dbid, latitude, longitude)
    local elev = World_GetElevation({latitude=latitude, longitude=longitude})
    if elev and elev > 0 then
        print('ERROR: Cannot place ship over land: '..unitname..' at '..latitude..','..longitude..' (elevation='..tostring(elev)..'m)')
        return nil
    end

    local ship = ScenEdit_AddUnit({
        type='Ship',
        unitname=unitname,
        side=side,
        dbid=dbid,
        latitude=latitude,
        longitude=longitude,
        altitude=0
    })
    if not ship then
        print('ERROR: Schip kon niet worden geplaatst: '..unitname)
    end
    return ship
end

local function weapon_name_is_nuclear(name)
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

-- Verwijder nucleaire wapens uit magazines/mounts (TLAM-N, ALCM, enz.) na spawn.
local function strip_nuclear_from_unit(unit)
    if not unit or not unit.guid then
        return 0
    end
    local u = ScenEdit_GetUnit({guid=unit.guid})
    if not u then
        return 0
    end
    local removed = 0
    if u.mounts then
        for _, mount in ipairs(u.mounts) do
            if mount.weapons and mount.guid then
                for _, w in ipairs(mount.weapons) do
                    local wname = w.name
                    local dbid = w.wpn_dbid or w.dbid
                    if weapon_name_is_nuclear(wname) and dbid then
                        ScenEdit_AddReloadsToUnit({
                            guid=u.guid,
                            wpn_dbid=dbid,
                            mount_guid=mount.guid,
                            remove=true,
                            number=999,
                        })
                        removed = removed + 1
                    end
                end
            end
        end
    end
    if u.magazines then
        for _, mag in ipairs(u.magazines) do
            if mag.weapons and mag.guid then
                for _, w in ipairs(mag.weapons) do
                    local wname = w.name
                    local dbid = w.wpn_dbid or w.dbid
                    if weapon_name_is_nuclear(wname) and dbid then
                        ScenEdit_AddWeaponToUnitMagazine({
                            guid=u.guid,
                            wpn_dbid=dbid,
                            mag_guid=mag.guid,
                            remove=true,
                            number=999,
                        })
                        removed = removed + 1
                    end
                end
            end
        end
    end
    return removed
end

-- CSG-beweging: alleen groepsleider op patrouille (escorts volgen in formatie).
-- TLAM: alleen de CG-shooter op de aparte Strike-missie (zelfde TOT als luchtstrike).
local function assign_csg_group_missions(group_name, lead_unit, patrol_mission, strike_unit, strike_mission)
    if lead_unit and lead_unit.guid and patrol_mission then
        ScenEdit_AssignUnitToMission(lead_unit.guid, patrol_mission)
        if group_name and group_name ~= '' then
            local ok = ScenEdit_AssignUnitToMission(group_name, patrol_mission)
            if not ok then
                print('NOTE: AssignUnitToMission op groep '..group_name..' mislukt — lead '..tostring(lead_unit.name)..' stuurt formatie.')
            end
        end
    end
    if strike_unit and strike_mission then
        if not assign_ship_to_mission('United States', strike_unit, strike_mission) then
            print('ERROR: TLAM shooter niet op missie: '..tostring(strike_unit.name or strike_unit.guid)..
                ' -> '..tostring(strike_mission))
        end
    end
end

-- Groepeer CSG-schepen; alleen de groepsleider bepaalt de koers (escorts volgen in formatie).
-- CG met eigen Strike (TLAM) niet in de groep zetten — CMO wist anders de missie-toewijzing.
local function form_csg_group(group_name, lead, members)
    if not lead or not lead.guid then
        print('ERROR: CSG group zonder lead')
        return
    end
    ScenEdit_SetUnit({guid=lead.guid, group=group_name, groupLead=lead.guid})
    for _, u in ipairs(members) do
        if u and u.guid then
            ScenEdit_SetUnit({guid=u.guid, group=group_name})
        end
    end
    local lead_u = ScenEdit_GetUnit({guid=lead.guid})
    if lead_u then
        lead_u.formation = {
            name = 'Column',
            spacing = 2000,
            spacing_unit = 'm',
            transpose = true,
        }
    end
end

-- United States missions (Carrier CAP zone wordt na CSG-coördinaten gezet)
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_ESC_1', latitude=23.5, longitude=-82.8})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_ESC_2', latitude=23.5, longitude=-74.5})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_ESC_3', latitude=19.5, longitude=-74.5})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_ESC_4', latitude=19.5, longitude=-82.8})
ScenEdit_AddMission('United States', 'SEAD Escort CAP', 'Patrol', {type='AAW', zone={'US_SEAD_ESC_1', 'US_SEAD_ESC_2', 'US_SEAD_ESC_3', 'US_SEAD_ESC_4'}})

-- Patrol/SEAD zones over bekende SAM-gordels (niet Strike — SEAD vuurt op emitters in zone)
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_W1', latitude=23.45, longitude=-82.75})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_W2', latitude=23.45, longitude=-82.05})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_W3', latitude=22.65, longitude=-82.05})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_W4', latitude=22.65, longitude=-82.75})
ScenEdit_AddMission('United States', 'Wild Weasel SEAD West', 'Patrol', {type='SEAD', zone={'US_SEAD_W1', 'US_SEAD_W2', 'US_SEAD_W3', 'US_SEAD_W4'}})

ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_E1', latitude=20.55, longitude=-76.25})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_E2', latitude=20.55, longitude=-74.65})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_E3', latitude=19.85, longitude=-74.65})
ScenEdit_AddReferencePoint({side='United States', name='US_SEAD_E4', latitude=19.85, longitude=-76.25})
ScenEdit_AddMission('United States', 'Wild Weasel SEAD East', 'Patrol', {type='SEAD', zone={'US_SEAD_E1', 'US_SEAD_E2', 'US_SEAD_E3', 'US_SEAD_E4'}})

ScenEdit_AddReferencePoint({side='United States', name='ISR_1', latitude=23.5, longitude=-79.0})
ScenEdit_AddReferencePoint({side='United States', name='ISR_2', latitude=22.0, longitude=-79.0})
ScenEdit_AddMission('United States', 'Caribbean ISR Orbit', 'Support', {zone={'ISR_1', 'ISR_2'}})

ScenEdit_AddMission('United States', 'Caribbean Thunder Strike', 'Strike', {type='Land'})
ScenEdit_AddMission('United States', 'Caribbean TLAM Salvo', 'Strike', {type='Land'})

-- Cuba missions
ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_W1', latitude=23.2, longitude=-82.8})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_W2', latitude=23.2, longitude=-81.6})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_W3', latitude=22.4, longitude=-81.6})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_W4', latitude=22.4, longitude=-82.8})
ScenEdit_AddMission('Cuba', 'Havana CAP', 'Patrol', {type='AAW', zone={'CU_CAP_W1', 'CU_CAP_W2', 'CU_CAP_W3', 'CU_CAP_W4'}})

ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_E1', latitude=20.5, longitude=-76.5})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_E2', latitude=20.5, longitude=-75.2})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_E3', latitude=19.6, longitude=-75.2})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_CAP_E4', latitude=19.6, longitude=-76.5})
ScenEdit_AddMission('Cuba', 'Eastern CAP', 'Patrol', {type='AAW', zone={'CU_CAP_E1', 'CU_CAP_E2', 'CU_CAP_E3', 'CU_CAP_E4'}})

ScenEdit_AddReferencePoint({side='Cuba', name='CU_COAST_1', latitude=23.2, longitude=-82.5})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_COAST_2', latitude=23.2, longitude=-81.0})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_COAST_3', latitude=19.0, longitude=-81.0})
ScenEdit_AddReferencePoint({side='Cuba', name='CU_COAST_4', latitude=19.0, longitude=-82.5})
ScenEdit_AddMission('Cuba', 'Coastal Defense Patrol', 'Patrol', {type='naval', zone={'CU_COAST_1', 'CU_COAST_2', 'CU_COAST_3', 'CU_COAST_4'}})

-- Zuidelijke Caraïbische Zee (open water); 21.5N 77W ligt op Cubaans grondgebied.
local csg_lat, csg_lon = 19.25, -79.75

-- Carrier CAP-station boven de CSG (~60–90 nm); niet bij 22.5N (oude positie, ~200 nm te noord).
ScenEdit_AddReferencePoint({side='United States', name='US_CAP_1', latitude=csg_lat + 1.0, longitude=csg_lon - 1.0})
ScenEdit_AddReferencePoint({side='United States', name='US_CAP_2', latitude=csg_lat + 1.0, longitude=csg_lon + 1.0})
ScenEdit_AddReferencePoint({side='United States', name='US_CAP_3', latitude=csg_lat - 0.5, longitude=csg_lon + 1.0})
ScenEdit_AddReferencePoint({side='United States', name='US_CAP_4', latitude=csg_lat - 0.5, longitude=csg_lon - 1.0})
ScenEdit_AddMission('United States', 'Carrier CAP', 'Patrol', {type='AAW', zone={'US_CAP_1', 'US_CAP_2', 'US_CAP_3', 'US_CAP_4'}})

ScenEdit_AddReferencePoint({side='United States', name='AEW_1', latitude=csg_lat + 0.8, longitude=csg_lon - 0.5})
ScenEdit_AddReferencePoint({side='United States', name='AEW_2', latitude=csg_lat - 0.3, longitude=csg_lon - 0.5})
ScenEdit_AddMission('United States', 'Carrier AEW Orbit', 'Support', {zone={'AEW_1', 'AEW_2'}})

ScenEdit_AddReferencePoint({side='United States', name='US_ASW_1', latitude=csg_lat + 1.25, longitude=csg_lon - 1.45})
ScenEdit_AddReferencePoint({side='United States', name='US_ASW_2', latitude=csg_lat + 1.25, longitude=csg_lon + 1.45})
ScenEdit_AddReferencePoint({side='United States', name='US_ASW_3', latitude=csg_lat - 1.05, longitude=csg_lon + 1.45})
ScenEdit_AddReferencePoint({side='United States', name='US_ASW_4', latitude=csg_lat - 1.05, longitude=csg_lon - 1.45})
ScenEdit_AddMission('United States', 'CSG ASW Screen', 'Patrol', {type='ASW', zone={'US_ASW_1', 'US_ASW_2', 'US_ASW_3', 'US_ASW_4'}})
ScenEdit_AddMission('United States', 'CSG ASuW Patrol', 'Patrol', {type='naval', zone={'US_ASW_1', 'US_ASW_2', 'US_ASW_3', 'US_ASW_4'}})
-- Oppervlakte-CSG: één patrouillebox; escorts niet op losse schip-ASW-patrouilles (breekt formatie).
ScenEdit_AddMission('United States', 'CSG Station Keeping', 'Patrol', {type='naval', zone={'US_ASW_1', 'US_ASW_2', 'US_ASW_3', 'US_ASW_4'}})

local CSG_GROUP = 'CVN 68 Caribbean CSG'
local nimitz = place_ship('United States', 'CVN 68 Nimitz', 429, csg_lat, csg_lon)
local bunker_hill = nil
local ddg51 = nil
local ddg51_escort = nil
if nimitz then
    bunker_hill = place_ship('United States', 'CG 52 Bunker Hill', 547, csg_lat + 0.08, csg_lon - 0.10)
    ddg51 = place_ship('United States', 'DDG 51 Arleigh Burke', 112, csg_lat - 0.06, csg_lon - 0.12)
    ddg51_escort = place_ship('United States', 'DDG 51 Arleigh Burke Escort', 112, csg_lat + 0.04, csg_lon + 0.14)
end

local us_staging = place_base('United States', 'Florida Forward Staging', 30.2, -81.5)

local cuba_bases = {
    san_antonio = place_base('Cuba', 'San Antonio de los Baños AB', 22.99, -82.41),
    santiago = place_base('Cuba', 'Santiago de Cuba AB', 20.02, -75.84)
}

if nimitz then
    spawn_air_wing('United States', 'Hawkeye', 2, 690, 14629, 'Carrier AEW Orbit', nimitz.guid)
    spawn_air_wing('United States', 'Growler SEAD West', 4, 343, 2954, 'Wild Weasel SEAD West', nimitz.guid)
    spawn_air_wing('United States', 'Growler SEAD East', 4, 343, 2954, 'Wild Weasel SEAD East', nimitz.guid)
    spawn_air_wing('United States', 'Hornet SEAD Escort', 6, 342, 12040, 'SEAD Escort CAP', nimitz.guid)
    spawn_air_wing('United States', 'Hornet Strike Escort', 12, 342, 12040, 'Caribbean Thunder Strike', nimitz.guid, true)
    spawn_air_wing('United States', 'Hornet CAP', 18, 342, 12040, 'Carrier CAP', nimitz.guid)
    spawn_air_wing('United States', 'Lightning Strike', 4, 824, 6945, 'Caribbean Thunder Strike', nimitz.guid)
    spawn_air_wing('United States', 'Hornet Strike JDAM', 4, 342, 985, 'Caribbean Thunder Strike', nimitz.guid)
    spawn_air_wing('United States', 'Hornet Strike JSOW', 4, 342, 3727, 'Caribbean Thunder Strike', nimitz.guid)
end

if us_staging then
    spawn_air_wing('United States', 'BUFF CALCM', 4, 567, 678, 'Caribbean Thunder Strike', us_staging.guid)
    spawn_air_wing('United States', 'Triton', 3, 2846, 13986, 'Caribbean ISR Orbit', us_staging.guid)
end

-- DDG 51 Flight I: 2× helovak (pad + open parking); CG 52: 3× medium. Meer dan 2 op één DDG → "Unable to host unit".
if ddg51 then
    spawn_air_wing('United States', 'Seahawk ASW', 2, 2006, 13418, 'CSG ASW Screen', ddg51.guid)
end
if ddg51_escort then
    spawn_air_wing('United States', 'Seahawk ASW', 1, 2006, 13418, 'CSG ASW Screen', ddg51_escort.guid)
end
if bunker_hill then
    spawn_air_wing('United States', 'Seahawk ASuW', 2, 2006, 34471, 'CSG ASuW Patrol', bunker_hill.guid)
end

-- Open water: noordkust Cuba ~23.1N — FAC/Osa in Straat van Florida (hogere breedtegraad = zee).
-- Oostkust Santiago ~20N/-76W is land; zuidkust ~19–21N, -77 tot -79.
-- Orbat: https://en.wikipedia.org/wiki/Cuban_Revolutionary_Navy (ingekort voor speelbaarheid vs CSG)
local cuba_naval = {
    damuji_west = place_ship('Cuba', 'BP 390 Rio Damuji', 3802, 23.05, -82.85),
    damuji_east = place_ship('Cuba', 'BP 391 Rio Jatibonico', 3803, 19.30, -75.55),
    pauk_corvette = place_ship('Cuba', '321 Pauk II', 3494, 23.52, -81.05),
    osa_212 = place_ship('Cuba', '212 Osa II', 2175, 23.58, -82.35),
    osa_213 = place_ship('Cuba', '213 Osa II', 2175, 23.56, -81.55),
    osa_214 = place_ship('Cuba', '214 Osa II', 2175, 23.54, -80.75),
    sonya_ms = place_ship('Cuba', '570 Sonya MS', 3501, 19.85, -77.45),
    yevgenya_ms = place_ship('Cuba', '510 Yevgenya MS', 3509, 20.05, -78.55),
    zhuk_west = place_ship('Cuba', '508 Zhuk', 1544, 23.60, -82.55),
    zhuk_sw = place_ship('Cuba', '531 Zhuk', 3720, 21.55, -84.05),
    stenka_1 = place_ship('Cuba', 'PSKR Stenka', 2212, 19.45, -74.90),
    stenka_2 = place_ship('Cuba', 'PSKR Stenka 2', 2212, 19.60, -75.25),
    delfin = place_sub('Cuba', 'SS Delfin', 697, 20.50, -79.20),
}

for _, unit in pairs(cuba_naval) do
    if unit then
        ScenEdit_AssignUnitToMission(unit.guid, 'Coastal Defense Patrol')
    end
end

if nimitz then
    form_csg_group(CSG_GROUP, nimitz, {ddg51, ddg51_escort})
    assign_csg_group_missions(
        CSG_GROUP,
        nimitz,
        'CSG Station Keeping',
        bunker_hill,
        TLAM_STRIKE_MISSION
    )
end

local nuclear_stripped = 0
for _, ship in ipairs({nimitz, bunker_hill, ddg51, ddg51_escort}) do
    if ship then
        nuclear_stripped = nuclear_stripped + strip_nuclear_from_unit(ship)
    end
end
if nuclear_stripped > 0 then
    print('Nuclear strip: removed '..nuclear_stripped..' nuclear store record(s) from CSG ships.')
end

if cuba_bases.san_antonio then
    spawn_air_wing('Cuba', 'Fulcrum Havana', 24, 845, 5252, 'Havana CAP', cuba_bases.san_antonio.guid)
    spawn_air_wing('Cuba', 'Flogger Havana', 6, 2059, 7164, 'Havana CAP', cuba_bases.san_antonio.guid)
end

if cuba_bases.santiago then
    spawn_air_wing('Cuba', 'Fulcrum East', 12, 845, 5252, 'Eastern CAP', cuba_bases.santiago.guid)
    spawn_air_wing('Cuba', 'Flogger East', 6, 2059, 7164, 'Eastern CAP', cuba_bases.santiago.guid)
end

local cuba_sams = {
    sam_west_1 = place_sam('Cuba', 'SA-2b Havana North', 1296, 23.15, -82.35),
    sam_west_2 = place_sam('Cuba', 'SA-3b Havana South', 1297, 22.85, -82.55),
    sam_east_1 = place_sam('Cuba', 'SA-2b Santiago', 1296, 20.10, -75.90),
    sam_east_2 = place_sam('Cuba', 'SA-3b Guantanamo Belt', 1297, 20.35, -74.95)
}

for _, sam in pairs({cuba_sams.sam_west_1, cuba_sams.sam_west_2}) do
    if sam then
        ScenEdit_AssignUnitToMission(sam.guid, 'Havana CAP')
    end
end
for _, sam in pairs({cuba_sams.sam_east_1, cuba_sams.sam_east_2}) do
    if sam then
        ScenEdit_AssignUnitToMission(sam.guid, 'Eastern CAP')
    end
end

for _, target in pairs(cuba_bases) do
    if target then
        ScenEdit_AssignUnitAsTarget(target.guid, 'Caribbean Thunder Strike')
        ScenEdit_AssignUnitAsTarget(target.guid, 'Caribbean TLAM Salvo')
    end
end

for _, target in pairs(cuba_sams) do
    if target then
        ScenEdit_AssignUnitAsTarget(target.guid, 'Caribbean Thunder Strike')
        ScenEdit_AssignUnitAsTarget(target.guid, 'Caribbean TLAM Salvo')
    end
end

ScenEdit_SetSideOptions({side='United States', proficiency=3})
ScenEdit_SetDoctrine({side='United States'}, {
    weapon_control_status_air=1,
    weapon_control_status_surface=1,
    weapon_control_status_subsurface=1,
    weapon_control_status_land=1,
    use_nuclear_weapons='No',
})

ScenEdit_SetSideOptions({side='Cuba', proficiency=2})
ScenEdit_SetDoctrine({side='Cuba'}, {
    weapon_control_status_air=0,
    weapon_control_status_surface=0,
    weapon_control_status_subsurface=0,
    weapon_control_status_land=0,
    use_nuclear_weapons='No',
})

ScenEdit_SetDoctrine({side='United States', mission='Carrier CAP'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun50_ToO',
    weapon_state_rtb='Winchester'
})

ScenEdit_SetDoctrine({side='United States', mission='SEAD Escort CAP'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='ShotgunOneEngagementBVR_And_WVR',
    weapon_state_rtb='Winchester'
})

ScenEdit_SetDoctrine({side='United States', mission='Wild Weasel SEAD West'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun50_ToO',
    weapon_state_rtb='Winchester',
    weapon_control_status_land=0
})

ScenEdit_SetDoctrine({side='United States', mission='Wild Weasel SEAD East'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun50_ToO',
    weapon_state_rtb='Winchester',
    weapon_control_status_land=0
})

-- SEAD niet bij scenario-start: anders gaan Growlers + SEAD-escort MiGs najagen vóór strike/escorts opstijgen.
local sead_launch_dt = mission_schedule_datetime(strike_package_date, sead_package_takeoff)
local sead_timed_missions = {
    'Wild Weasel SEAD West',
    'Wild Weasel SEAD East',
    'SEAD Escort CAP',
}
for _, sead_mission in ipairs(sead_timed_missions) do
    ScenEdit_SetMission('United States', sead_mission, {
        starttime = sead_launch_dt,
        TakeOffTime = sead_launch_dt,
        UseFlightSize = true,
        FlightSize = 2,
        MinAircraftReq = 4,
    })
end

local tlam_launch_dt = mission_schedule_datetime(strike_package_date, tlam_launch_time)
local strike_tot_dt = mission_schedule_datetime(strike_package_date, strike_package_tot)
sync_strike_package_tot()
if bunker_hill then
    assign_tlam_shooter(bunker_hill)
end

local csg_helo_launch_dt = mission_schedule_datetime(strike_package_date, csg_helo_takeoff)
ScenEdit_SetMission('United States', 'CSG Station Keeping', {starttime = csg_helo_launch_dt})
for _, helo_mission in ipairs({'CSG ASW Screen', 'CSG ASuW Patrol'}) do
    ScenEdit_SetMission('United States', helo_mission, {
        starttime = csg_helo_launch_dt,
        TakeOffTime = csg_helo_launch_dt,
        UseFlightSize = true,
        FlightSize = 2,
    })
end

-- Geen use_refuel_unrep: carrier ~200–350 nm van Cuba; CALCM/JSOW standoff. Yes_Yes stuurde ~30+ jets
-- naar 2× KC-46 (tanker-queue, mid-air crashes). Bij Joker/Bingo gewoon RTB naar carrier/Florida.
ScenEdit_SetDoctrine({side='United States', mission='Caribbean Thunder Strike'}, {
    fuel_state_planned='Joker10Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='ShotgunOneEngagementBVR',
    weapon_state_rtb='Winchester',
    use_refuel_unrep='No_No'
})

ScenEdit_SetDoctrine({side='Cuba', mission='Havana CAP'}, {
    fuel_state_planned='Joker20Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun75_ToO',
    weapon_state_rtb='Winchester'
})

-- Carrier strike package: wait for multi-ship flights before launch (not piecemeal singles).
ScenEdit_SetMission('United States', 'Caribbean Thunder Strike', {
    StrikeUseFlightSize = true,
    StrikeFlightSize = 4,
    StrikeMinAircraftReq = 8,
    EscortUseFlightSize = true,
    EscortFlightSizeShooter = 4,
    EscortMinShooter = 4,
})

-- Strike-toestellen eerst op missie (flight plan pakt alleen toegewezen toestellen).
local refresh_pre, refresh_pre_failed = refresh_spawned_air_assignments(nil)
print('Air mission pre-flight-plan: '..refresh_pre..' OK, '..refresh_pre_failed..' failed')

sync_strike_package_tot()
-- Eén TOT voor TLAM + carrier-strike + B-52 CALCM (strike_package_tot).
ScenEdit_CreateMissionFlightPlan('United States', 'Caribbean Thunder Strike', {
    DATEONTARGET = strike_package_date,
    TIMEONTARGET = strike_package_tot,
})

local strike_mission = ScenEdit_GetMission('United States', 'Caribbean Thunder Strike')
if strike_mission then
    if strike_mission.targetlist then
        print('Mission Caribbean Thunder Strike found with '..#strike_mission.targetlist..' targets.')
    else
        print('WARNING: Mission Caribbean Thunder Strike has no targets!')
    end
    if strike_mission.updateWPtimes then
        local ok, err = pcall(function()
            strike_mission:updateWPtimes()
        end)
        if not ok then
            print('WARNING: updateWPtimes failed: '..tostring(err))
        end
    end
else
    print('WARNING: Mission Caribbean Thunder Strike NOT found!')
end

-- Herbevestig na flight plan (CreateMissionFlightPlan wist vaak toewijzingen; geen tweede createFlightPlans).
local refresh_assigned, refresh_failed = refresh_spawned_air_assignments(nil)
print('Air mission refresh: '..refresh_assigned..' OK, '..refresh_failed..' failed (of '..#spawned_air_missions..')')
if refresh_failed > 0 then
    for _, entry in ipairs(spawned_air_missions) do
        if not assign_air_to_mission(entry.side, entry.guid, entry.name, entry.mission, entry.escort) then
            print('ERROR: Her-toewijzing mislukt: '..tostring(entry.name or entry.guid)..' -> '..entry.mission)
        end
    end
end

local refresh_post_strike, refresh_post_strike_failed = refresh_spawned_air_assignments('Caribbean Thunder Strike')
if refresh_post_strike + refresh_post_strike_failed > 0 then
    print('Strike mission re-assign after flight plan: '..refresh_post_strike..' OK, '..refresh_post_strike_failed..' failed')
end

sync_strike_package_tot()
if strike_mission and strike_mission.updateWPtimes then
    local ok_wp, err_wp = pcall(function()
        strike_mission:updateWPtimes()
    end)
    if not ok_wp then
        print('WARNING: strike updateWPtimes (post-assign) failed: '..tostring(err_wp))
    end
end

local strike_still_unassigned = 0
for _, entry in ipairs(spawned_air_missions) do
    if entry.mission == 'Caribbean Thunder Strike' then
        local u = ScenEdit_GetUnit({guid=entry.guid})
        if u then
            local on_mission = u.assignedMission or u.mission or ''
            if on_mission == '' then
                strike_still_unassigned = strike_still_unassigned + 1
            end
        end
    end
end
if strike_still_unassigned > 0 then
    print('WARNING: '..strike_still_unassigned..' Caribbean Thunder Strike aircraft still unassigned in ORBAT')
else
    print('OK: All Caribbean Thunder Strike aircraft remain assigned after flight plan')
end

-- SetMission op TLAM wist vaak de CG-toewijzing; herhaal na laatste sync.
sync_strike_package_tot()
if bunker_hill then
    if assign_tlam_shooter(bunker_hill) then
        print('TLAM shooter re-assigned: '..tostring(bunker_hill.name))
    else
        print('ERROR: TLAM shooter re-assign failed: '..tostring(bunker_hill.name))
    end
    verify_tlam_mission_has_shooter(bunker_hill)
end

local tlam_mission = ScenEdit_GetMission('United States', TLAM_STRIKE_MISSION)
if tlam_mission and tlam_mission.TimeOnTargetStation and strike_mission and strike_mission.TimeOnTargetStation then
    print('Strike TOT sync: TLAM='..tostring(tlam_mission.TimeOnTargetStation)..
        ' | Air='..tostring(strike_mission.TimeOnTargetStation))
end

print('Caribbean Pressure 2026 Scenario Initialized')
print('DB-serie lock: '..db_series..' | Jaar: '..scenario_year)
