-- CMO Scenario: WARNO - Cold War Escalation 1989
-- NATO vs Warsaw Pact
-- Large-scale defensive NATO air battle against a Warsaw Pact offensive.
--
-- OOB (Order of Battle)
-- Jaar/DB: 1989 | DB3K v515 (geen mixed DB3K/CWDB ID's)
-- Posture: NATO <-> Warsaw Pact = Hostile (beide kanten)
--
-- NATO (defensief)
-- Bases (9): Ramstein, Spangdahlem, Bitburg, Geilenkirchen, Hahn, Sembach, Buechel, RAF Bruggen, Zweibrucken
-- Missies: NATO Fighter CAP, NATO Northern CAP, NATO Base Defense CAP, AWACS Orbit, AWACS North Orbit
-- Lucht (~243): 3x E-3A (3186/8076), 120x F-15C (211/1404), 96x F-16C Blk 30 (198/7856), 24x F-4G (228/1633)
-- IADS (8): 5x Patriot (33), 3x I-HAWK (65)
-- Doctrine: Veteran, WCS TIGHT (air/surface/subsurface/land)
--
-- Warsaw Pact (offensief)
-- Bases (6): Falkenberg, Wittstock, Finsterwalde, Rechlin, Templin, Gross Doelln
-- Missies: Red Air CAP, Red Air CAP Forward, Mainstay AEW, Red Hammer Escort (AAW), Red Hammer SEAD (Patrol/SEAD over NATO IADS), Red Thunder Strike (+ escort slot)
-- Lucht (~230): 2x A-50 (711/8060), 96x MiG-29 (7397/5262), 12x MiG-25BM SEAD (466/1182), 12x Su-22 SEAD (352/24735),
--               48x MiG-23 strike (3087/10835), 36x Su-24M strike (470/241), 24x Su-22 strike (352/7558)
-- IADS (7): 2x SA-10b (475), 2x SA-11 (547), 3x SA-6a (4630)
-- Doctrine: Regular, WCS FREE (air/surface/subsurface/land)
--
-- Primaire strike-doelen (WP): Ramstein, Spangdahlem, Bitburg, Geilenkirchen, Hahn, Buechel
-- Preflight: python scripts/db_search.py --validate-scenario generated/warno_air_strike.lua --series DB3K --version 515
--   (DB-compatibiliteit + mission/loadout-fit + strike/SEAD escort-package heuristiek)
local scenario_year = 1989
local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
if db_series ~= 'DB3K' then
    print('ERROR: WARNO 1989 verwacht DB3K. Controleer scenariojaar/database.')
    return
end

local BASE_FACILITY_DBID = 1995

ScenEdit_AddSide({side='NATO', weighting=0})
ScenEdit_AddSide({side='Warsaw Pact', weighting=0})
ScenEdit_SetSidePosture('NATO', 'Warsaw Pact', 'H')
ScenEdit_SetSidePosture('Warsaw Pact', 'NATO', 'H')

local function add_air_unit_checked(side, unitname, dbid, base_guid, loadoutid, mission_name, strike_escort)
    if loadoutid == nil then
        print('ERROR: Missing LoadoutID voor '..unitname..' (DBID '..dbid..')')
        return nil
    end
    if not base_guid then
        print('ERROR: Geen basis voor '..unitname)
        return nil
    end

    local u = ScenEdit_AddUnit({
        type='Air',
        unitname=unitname,
        side=side,
        dbid=dbid,
        base=base_guid,
        loadoutid=loadoutid,
        altitude='0'
    })

    if not u then
        print('ERROR: Air unit spawn mislukt: '..unitname..' (DBID '..dbid..', Loadout '..tostring(loadoutid)..')')
        return nil
    end

    local created = ScenEdit_GetUnit({guid=u.guid})
    if created and created.loadoutdbid ~= nil and tonumber(created.loadoutdbid) ~= tonumber(loadoutid) then
        print('WARNING: Loadout afwijking voor '..unitname..' | preferred='..loadoutid..' actief='..tostring(created.loadoutdbid))
    end

    if mission_name then
        if strike_escort then
            ScenEdit_AssignUnitToMission(u.guid, mission_name, true)
        else
            ScenEdit_AssignUnitToMission(u.guid, mission_name)
        end
    end
    return u
end

local function spawn_air_wing(side, prefix, count, dbid, loadoutid, mission_name, base_guid, strike_escort)
    for i=1, count do
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

-- NATO missions
ScenEdit_AddReferencePoint({side='NATO', name='NATO_CAP_1', latitude=52.5, longitude=12.0})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_CAP_2', latitude=52.5, longitude=13.0})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_CAP_3', latitude=51.5, longitude=13.0})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_CAP_4', latitude=51.5, longitude=12.0})
ScenEdit_AddMission('NATO', 'NATO Fighter CAP', 'Patrol', {type='AAW', zone={'NATO_CAP_1', 'NATO_CAP_2', 'NATO_CAP_3', 'NATO_CAP_4'}})

ScenEdit_AddReferencePoint({side='NATO', name='NATO_NORTH_1', latitude=53.8, longitude=11.5})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_NORTH_2', latitude=53.8, longitude=13.5})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_NORTH_3', latitude=52.8, longitude=13.5})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_NORTH_4', latitude=52.8, longitude=11.5})
ScenEdit_AddMission('NATO', 'NATO Northern CAP', 'Patrol', {type='AAW', zone={'NATO_NORTH_1', 'NATO_NORTH_2', 'NATO_NORTH_3', 'NATO_NORTH_4'}})

ScenEdit_AddReferencePoint({side='NATO', name='NATO_INNER_1', latitude=50.8, longitude=6.0})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_INNER_2', latitude=50.8, longitude=8.2})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_INNER_3', latitude=49.3, longitude=8.2})
ScenEdit_AddReferencePoint({side='NATO', name='NATO_INNER_4', latitude=49.3, longitude=6.0})
ScenEdit_AddMission('NATO', 'NATO Base Defense CAP', 'Patrol', {type='AAW', zone={'NATO_INNER_1', 'NATO_INNER_2', 'NATO_INNER_3', 'NATO_INNER_4'}})

ScenEdit_AddReferencePoint({side='NATO', name='AWACS_1', latitude=51.5, longitude=9.0})
ScenEdit_AddReferencePoint({side='NATO', name='AWACS_2', latitude=50.5, longitude=9.0})
ScenEdit_AddMission('NATO', 'AWACS Orbit', 'Support', {zone={'AWACS_1', 'AWACS_2'}})

ScenEdit_AddReferencePoint({side='NATO', name='AWACS_N1', latitude=52.8, longitude=10.5})
ScenEdit_AddReferencePoint({side='NATO', name='AWACS_N2', latitude=52.0, longitude=10.5})
ScenEdit_AddMission('NATO', 'AWACS North Orbit', 'Support', {zone={'AWACS_N1', 'AWACS_N2'}})

-- Warsaw Pact missions
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_1', latitude=53.0, longitude=14.0})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_2', latitude=53.0, longitude=15.5})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_3', latitude=52.0, longitude=15.5})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_4', latitude=52.0, longitude=14.0})
ScenEdit_AddMission('Warsaw Pact', 'Red Air CAP', 'Patrol', {type='AAW', zone={'WP_CAP_1', 'WP_CAP_2', 'WP_CAP_3', 'WP_CAP_4'}})

ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_F1', latitude=52.6, longitude=12.8})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_F2', latitude=52.6, longitude=14.2})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_F3', latitude=51.7, longitude=14.2})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_CAP_F4', latitude=51.7, longitude=12.8})
ScenEdit_AddMission('Warsaw Pact', 'Red Air CAP Forward', 'Patrol', {type='AAW', zone={'WP_CAP_F1', 'WP_CAP_F2', 'WP_CAP_F3', 'WP_CAP_F4'}})

ScenEdit_AddReferencePoint({side='Warsaw Pact', name='Mainstay_1', latitude=53.0, longitude=16.0})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='Mainstay_2', latitude=52.0, longitude=16.0})
ScenEdit_AddMission('Warsaw Pact', 'Mainstay AEW', 'Support', {zone={'Mainstay_1', 'Mainstay_2'}})

ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_ESC_1', latitude=52.3, longitude=5.9})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_ESC_2', latitude=52.3, longitude=14.5})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_ESC_3', latitude=51.1, longitude=14.5})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_ESC_4', latitude=51.1, longitude=5.9})
ScenEdit_AddMission('Warsaw Pact', 'Red Hammer Escort', 'Patrol', {type='AAW', zone={'WP_SEAD_ESC_1', 'WP_SEAD_ESC_2', 'WP_SEAD_ESC_3', 'WP_SEAD_ESC_4'}})

-- Patrol/SEAD over NATO Patriot/I-HAWK-gordel (strike-targetlijst onderdrukt dit niet automatisch)
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_N1', latitude=51.4, longitude=5.9})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_N2', latitude=51.4, longitude=8.2})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_N3', latitude=49.3, longitude=8.2})
ScenEdit_AddReferencePoint({side='Warsaw Pact', name='WP_SEAD_N4', latitude=49.3, longitude=5.9})
ScenEdit_AddMission('Warsaw Pact', 'Red Hammer SEAD', 'Patrol', {type='SEAD', zone={'WP_SEAD_N1', 'WP_SEAD_N2', 'WP_SEAD_N3', 'WP_SEAD_N4'}})

ScenEdit_AddMission('Warsaw Pact', 'Red Thunder Strike', 'Strike', {type='Land'})

local nato_bases = {
    ramstein = place_base('NATO', 'Ramstein AB', 49.4, 7.6),
    spangdahlem = place_base('NATO', 'Spangdahlem AB', 49.9, 6.7),
    bitburg = place_base('NATO', 'Bitburg AB', 49.94, 6.56),
    geilenkirchen = place_base('NATO', 'Geilenkirchen AB', 50.96, 6.04),
    hahn = place_base('NATO', 'Hahn AB', 49.95, 7.27),
    sembach = place_base('NATO', 'Sembach AB', 49.51, 7.87),
    buechel = place_base('NATO', 'Buechel AB', 50.17, 7.06),
    bruggen = place_base('NATO', 'RAF Bruggen', 51.2, 6.13),
    zweibrucken = place_base('NATO', 'Zweibrucken AB', 49.21, 7.4)
}

if nato_bases.geilenkirchen then
    spawn_air_wing('NATO', 'Magic (E-3A)', 2, 3186, 8076, 'AWACS Orbit', nato_bases.geilenkirchen.guid)
end
if nato_bases.bruggen then
    spawn_air_wing('NATO', 'Magic North (E-3A)', 1, 3186, 8076, 'AWACS North Orbit', nato_bases.bruggen.guid)
end

for _, base_key in ipairs({'bitburg', 'hahn', 'bruggen', 'zweibrucken'}) do
    local base = nato_bases[base_key]
    if base then
        spawn_air_wing('NATO', 'Eagle '..base_key, 24, 211, 1404, 'NATO Fighter CAP', base.guid)
    end
end

for _, base_key in ipairs({'bruggen', 'hahn'}) do
    local base = nato_bases[base_key]
    if base then
        spawn_air_wing('NATO', 'Eagle North '..base_key, 12, 211, 1404, 'NATO Northern CAP', base.guid)
    end
end

for _, base_key in ipairs({'spangdahlem', 'sembach', 'buechel', 'ramstein'}) do
    local base = nato_bases[base_key]
    if base then
        spawn_air_wing('NATO', 'Falcon '..base_key, 24, 198, 7856, 'NATO Base Defense CAP', base.guid)
    end
end

for _, base_key in ipairs({'spangdahlem', 'ramstein'}) do
    local base = nato_bases[base_key]
    if base then
        spawn_air_wing('NATO', 'Wild Weasel '..base_key, 12, 228, 1633, 'NATO Base Defense CAP', base.guid)
    end
end

local wp_bases = {
    falkenberg = place_base('Warsaw Pact', 'Falkenberg Airbase', 52.3, 14.1),
    wittstock = place_base('Warsaw Pact', 'Wittstock Airbase', 53.2, 12.5),
    finsterwalde = place_base('Warsaw Pact', 'Finsterwalde Airbase', 51.6, 13.7),
    rechlin = place_base('Warsaw Pact', 'Rechlin Airbase', 53.3, 12.75),
    templin = place_base('Warsaw Pact', 'Templin Airbase', 53.1, 13.5),
    gross_doelln = place_base('Warsaw Pact', 'Gross Doelln Airbase', 53.0, 13.05)
}

if wp_bases.wittstock then
    spawn_air_wing('Warsaw Pact', 'Mainstay', 2, 711, 8060, 'Mainstay AEW', wp_bases.wittstock.guid)
end

for _, base_key in ipairs({'falkenberg', 'finsterwalde', 'templin'}) do
    local base = wp_bases[base_key]
    if base then
        spawn_air_wing('Warsaw Pact', 'Fulcrum Strike Escort '..base_key, 12, 7397, 5262, 'Red Thunder Strike', base.guid, true)
        spawn_air_wing('Warsaw Pact', 'Fulcrum SEAD Escort '..base_key, 4, 7397, 5262, 'Red Hammer Escort', base.guid)
        spawn_air_wing('Warsaw Pact', 'Fulcrum CAP '..base_key, 8, 7397, 5262, 'Red Air CAP', base.guid)
    end
end

for _, base_key in ipairs({'rechlin', 'gross_doelln'}) do
    local base = wp_bases[base_key]
    if base then
        spawn_air_wing('Warsaw Pact', 'Fulcrum Forward '..base_key, 12, 7397, 5262, 'Red Air CAP Forward', base.guid)
    end
end

for _, base_key in ipairs({'wittstock', 'rechlin', 'gross_doelln'}) do
    local base = wp_bases[base_key]
    if base then
        spawn_air_wing('Warsaw Pact', 'Foxbat SEAD '..base_key, 4, 466, 1182, 'Red Hammer SEAD', base.guid)
    end
end

for _, base_key in ipairs({'finsterwalde', 'falkenberg', 'templin'}) do
    local base = wp_bases[base_key]
    if base then
        spawn_air_wing('Warsaw Pact', 'Fitter SEAD '..base_key, 4, 352, 24735, 'Red Hammer SEAD', base.guid)
    end
end

for _, base_key in ipairs({'wittstock', 'finsterwalde', 'rechlin'}) do
    local base = wp_bases[base_key]
    if base then
        spawn_air_wing('Warsaw Pact', 'Flogger '..base_key, 16, 3087, 10835, 'Red Thunder Strike', base.guid)
    end
end

for _, base_key in ipairs({'falkenberg', 'templin', 'gross_doelln'}) do
    local base = wp_bases[base_key]
    if base then
        spawn_air_wing('Warsaw Pact', 'Fencer '..base_key, 12, 470, 241, 'Red Thunder Strike', base.guid)
    end
end

for _, base_key in ipairs({'finsterwalde', 'rechlin'}) do
    local base = wp_bases[base_key]
    if base then
        spawn_air_wing('Warsaw Pact', 'Fitter Strike '..base_key, 12, 352, 7558, 'Red Thunder Strike', base.guid)
    end
end

place_sam('Warsaw Pact', 'SA-10b Battery (North)', 475, 52.8, 13.5)
place_sam('Warsaw Pact', 'SA-10b Battery (East)', 475, 52.4, 14.4)
place_sam('Warsaw Pact', 'SA-11 Battery (Falkenberg)', 547, 52.28, 14.05)
place_sam('Warsaw Pact', 'SA-11 Battery (Wittstock)', 547, 53.15, 12.6)
place_sam('Warsaw Pact', 'SA-6a Battery (Center)', 4630, 52.5, 13.8)
place_sam('Warsaw Pact', 'SA-6a Battery (South)', 4630, 51.8, 13.4)
place_sam('Warsaw Pact', 'SA-6a Battery (Forward)', 4630, 52.0, 12.9)

place_sam('NATO', 'Patriot Battery (Ramstein)', 33, 49.55, 7.75)
place_sam('NATO', 'Patriot Battery (Spangdahlem)', 33, 50.05, 6.85)
place_sam('NATO', 'Patriot Battery (Bitburg)', 33, 50.0, 6.45)
place_sam('NATO', 'Patriot Battery (Hahn)', 33, 49.98, 7.35)
place_sam('NATO', 'Patriot Battery (Bruggen)', 33, 51.15, 6.2)
place_sam('NATO', 'I-HAWK Battery (Geilenkirchen)', 65, 50.9, 6.15)
place_sam('NATO', 'I-HAWK Battery (Sembach)', 65, 49.55, 7.95)
place_sam('NATO', 'I-HAWK Battery (Buechel)', 65, 50.2, 7.15)

for _, target_key in ipairs({'ramstein', 'spangdahlem', 'bitburg', 'geilenkirchen', 'hahn', 'buechel'}) do
    local target = nato_bases[target_key]
    if target then
        ScenEdit_AssignUnitAsTarget(target.guid, 'Red Thunder Strike')
    end
end

ScenEdit_SetSideOptions({side='NATO', proficiency=3})
ScenEdit_SetDoctrine({side='NATO'}, {
    weapon_control_status_air=1,
    weapon_control_status_surface=1,
    weapon_control_status_subsurface=1,
    weapon_control_status_land=1
})

ScenEdit_SetSideOptions({side='Warsaw Pact', proficiency=2})
ScenEdit_SetDoctrine({side='Warsaw Pact'}, {
    weapon_control_status_air=0,
    weapon_control_status_surface=0,
    weapon_control_status_subsurface=0,
    weapon_control_status_land=0
})

ScenEdit_SetDoctrine({side='NATO', mission='NATO Fighter CAP'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun50_ToO',
    weapon_state_rtb='Winchester'
})

ScenEdit_SetDoctrine({side='NATO', mission='NATO Northern CAP'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun50_ToO',
    weapon_state_rtb='Winchester'
})

ScenEdit_SetDoctrine({side='NATO', mission='NATO Base Defense CAP'}, {
    fuel_state_planned='Joker20Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun75_ToO',
    weapon_state_rtb='Winchester'
})

ScenEdit_SetDoctrine({side='Warsaw Pact', mission='Red Hammer Escort'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='ShotgunOneEngagementBVR_And_WVR',
    weapon_state_rtb='Winchester'
})

ScenEdit_SetDoctrine({side='Warsaw Pact', mission='Red Hammer SEAD'}, {
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun50_ToO',
    weapon_state_rtb='Winchester',
    weapon_control_status_land=0
})

ScenEdit_SetDoctrine({side='Warsaw Pact', mission='Red Thunder Strike'}, {
    fuel_state_planned='Joker25Percent',
    fuel_state_rtb='Bingo',
    weapon_state_planned='Shotgun50_ToO',
    weapon_state_rtb='Winchester'
})

local ds_mission = ScenEdit_GetMission('Warsaw Pact', 'Red Thunder Strike')
if ds_mission and ds_mission.targetlist then
    print('Mission Red Thunder Strike found with '..#ds_mission.targetlist..' targets.')
else
    print('WARNING: Mission Red Thunder Strike NOT found or has no targets!')
end

print('WARNO - Cold War Escalation Scenario Initialized')
print('DB-serie lock: '..db_series..' | Jaar: '..scenario_year)