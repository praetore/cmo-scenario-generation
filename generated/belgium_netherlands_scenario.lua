-- CMO Scenario: De Slag om de Lage Landen
-- België vs Nederland
-- Een fictief modern conflict over de territoriale wateren en luchtruim.

-- Database-serie mapping (logic_checks_cmo.md):
-- Jaar > 1980 => DB3K, Jaar < 1980 => CWDB
local scenario_year = 2026
local db_series = (scenario_year > 1980) and 'DB3K' or 'CWDB'
if db_series ~= 'DB3K' then
    print('ERROR: Dit scenario is modern en verwacht DB3K. Controleer scenariojaar/database.')
    return
end

-- 1. Zijden & Houding
ScenEdit_AddSide({side='België', weighting=0})
ScenEdit_AddSide({side='Nederland', weighting=0})

ScenEdit_SetSidePosture('België', 'Nederland', 'H')
ScenEdit_SetSidePosture('Nederland', 'België', 'H')

-- 2. Referentiepunten & Missies (Nederland)
-- CAP: Noordzee Luchtverdediging
ScenEdit_AddReferencePoint({side='Nederland', name='NL_CAP_1', latitude=53.5, longitude=3.5})
ScenEdit_AddReferencePoint({side='Nederland', name='NL_CAP_2', latitude=53.5, longitude=4.5})
ScenEdit_AddReferencePoint({side='Nederland', name='NL_CAP_3', latitude=52.5, longitude=4.5})
ScenEdit_AddReferencePoint({side='Nederland', name='NL_CAP_4', latitude=52.5, longitude=3.5})
ScenEdit_AddMission('Nederland', 'NL Fighter CAP', 'Patrol', {type='AAW', zone={'NL_CAP_1', 'NL_CAP_2', 'NL_CAP_3', 'NL_CAP_4'}})

-- ASW: Anti-Submarine Warfare Noordzee
ScenEdit_AddReferencePoint({side='Nederland', name='NL_ASW_1', latitude=54.0, longitude=3.0})
ScenEdit_AddReferencePoint({side='Nederland', name='NL_ASW_2', latitude=54.0, longitude=5.0})
ScenEdit_AddReferencePoint({side='Nederland', name='NL_ASW_3', latitude=53.0, longitude=5.0})
ScenEdit_AddReferencePoint({side='Nederland', name='NL_ASW_4', latitude=53.0, longitude=3.0})
ScenEdit_AddMission('Nederland', 'NL ASW Patrol', 'Patrol', {type='ASW', zone={'NL_ASW_1', 'NL_ASW_2', 'NL_ASW_3', 'NL_ASW_4'}})

-- 3. Referentiepunten & Missies (België)
-- CAP: Belgisch Luchtruim & Grens
ScenEdit_AddReferencePoint({side='België', name='BE_CAP_1', latitude=51.5, longitude=3.0})
ScenEdit_AddReferencePoint({side='België', name='BE_CAP_2', latitude=51.5, longitude=5.5})
ScenEdit_AddReferencePoint({side='België', name='BE_CAP_3', latitude=50.5, longitude=5.5})
ScenEdit_AddReferencePoint({side='België', name='BE_CAP_4', latitude=50.5, longitude=3.0})
ScenEdit_AddMission('België', 'BE Fighter CAP', 'Patrol', {type='AAW', zone={'BE_CAP_1', 'BE_CAP_2', 'BE_CAP_3', 'BE_CAP_4'}})

-- Strike: Aanval op Vliegbasis Volkel
ScenEdit_AddMission('België', 'Strike Volkel', 'Strike', {type='Land'})

-- 4. Nederlandse Infrastructuur & Eenheden
-- Bases
local volkel = ScenEdit_AddUnit({type='Facility', unitname='Vliegbasis Volkel', side='Nederland', dbid=1995, latitude=51.65, longitude=5.7, altitude=0})
if not volkel then 
    print('ERROR: Vliegbasis Volkel kon niet worden geplaatst!') 
else
    ScenEdit_AssignUnitAsTarget(volkel.guid, 'Strike Volkel')
end

local leeuwarden = ScenEdit_AddUnit({type='Facility', unitname='Vliegbasis Leeuwarden', side='Nederland', dbid=1995, latitude=53.22, longitude=5.75, altitude=0})
if not leeuwarden then print('ERROR: Vliegbasis Leeuwarden kon niet worden geplaatst!') end

local den_helder = ScenEdit_AddUnit({type='Facility', unitname='Marinebasis Den Helder', side='Nederland', dbid=1995, latitude=52.95, longitude=4.8, altitude=0})
if not den_helder then print('ERROR: Marinebasis Den Helder kon niet worden geplaatst!') end

-- Nederlandse Luchtmacht (KLu)
-- F-35A Lightning II
for i=1, 12 do
    if leeuwarden then
        local u = ScenEdit_AddUnit({type='Air', unitname='NL F-35 #'..i, side='Nederland', dbid=3902, base=leeuwarden.guid, loadoutid=19576, altitude='0'})
        if u then ScenEdit_AssignUnitToMission(u.guid, 'NL Fighter CAP') end
    end
end

-- NH-90 NFH (ASW)
for i=1, 4 do
    if den_helder then
        local u = ScenEdit_AddUnit({type='Air', unitname='NL NH-90 #'..i, side='Nederland', dbid=656, base=den_helder.guid, loadoutid=5764, altitude='0'})
        if u then ScenEdit_AssignUnitToMission(u.guid, 'NL ASW Patrol') end
    end
end

-- Nederlandse Marine (KM)
local karel_doorman = ScenEdit_AddUnit({type='Ship', unitname='Zr.Ms. Karel Doorman', side='Nederland', dbid=3887, latitude=53.5, longitude=4.0})
local zeven_provincien = ScenEdit_AddUnit({type='Ship', unitname='Zr.Ms. Zeven Provinciën', side='Nederland', dbid=4339, latitude=53.6, longitude=4.1})

-- 5. Belgische Infrastructuur & Eenheden
-- Bases
local kleine_brogel = ScenEdit_AddUnit({type='Facility', unitname='Vliegbasis Kleine-Brogel', side='België', dbid=1995, latitude=51.16, longitude=5.46, altitude=0})
if not kleine_brogel then print('ERROR: Vliegbasis Kleine-Brogel kon niet worden geplaatst!') end

local florennes = ScenEdit_AddUnit({type='Facility', unitname='Vliegbasis Florennes', side='België', dbid=1995, latitude=50.24, longitude=4.64, altitude=0})
if not florennes then print('ERROR: Vliegbasis Florennes kon niet worden geplaatst!') end

local zeebrugge = ScenEdit_AddUnit({type='Facility', unitname='Marinebasis Zeebrugge', side='België', dbid=1995, latitude=51.32, longitude=3.21, altitude=0})
if not zeebrugge then print('ERROR: Marinebasis Zeebrugge kon niet worden geplaatst!') end

-- Belgische Luchtmacht (Luchtcomponent)
-- F-16AM Fighting Falcon
for i=1, 16 do
    if kleine_brogel then
        local u = ScenEdit_AddUnit({type='Air', unitname='BE F-16 #'..i, side='België', dbid=731, base=kleine_brogel.guid, loadoutid=16791, altitude='0'})
        if u then ScenEdit_AssignUnitToMission(u.guid, 'BE Fighter CAP') end
    end
end

-- F-35A (België heeft deze besteld, in scenario al operationeel)
for i=1, 8 do
    if florennes then
        local u = ScenEdit_AddUnit({type='Air', unitname='BE F-35 #'..i, side='België', dbid=5776, base=florennes.guid, loadoutid=30797, altitude='0'})
        if u then ScenEdit_AssignUnitToMission(u.guid, 'Strike Volkel') end
    end
end

-- Belgische Marine (Marinecomponent)
local leopold_1 = ScenEdit_AddUnit({type='Ship', unitname='BNS Leopold I', side='België', dbid=3800, latitude=51.5, longitude=3.1})

-- 6. Doelen & Configuratie

-- Side-specifieke profielen (karakter per zijde)
-- Nederland: hoger trainingsniveau, gecontroleerde engagements
ScenEdit_SetSideOptions({side='Nederland', proficiency=3}) -- Veteran
ScenEdit_SetDoctrine({side='Nederland'}, {
    weapon_control_status_air=1,         -- TIGHT
    weapon_control_status_surface=1,     -- TIGHT
    weapon_control_status_subsurface=1,  -- TIGHT
    weapon_control_status_land=1,        -- TIGHT
    fuel_state_planned='Joker30Percent',
    fuel_state_rtb='Bingo'
})

-- België: regulier trainingsniveau, agressiever engagement-profiel
ScenEdit_SetSideOptions({side='België', proficiency=2}) -- Regular
ScenEdit_SetDoctrine({side='België'}, {
    weapon_control_status_air=0,         -- FREE
    weapon_control_status_surface=0,     -- FREE
    weapon_control_status_subsurface=0,  -- FREE
    weapon_control_status_land=0,        -- FREE
    weapon_state_planned='Shotgun',
    weapon_state_rtb='Winchester'
})

-- Luchtverdediging (Patriot voor NL)
local patriot = ScenEdit_AddUnit({type='Facility', unitname='NL Patriot Batterij', side='Nederland', dbid=2224, latitude=52.1, longitude=5.8, altitude=0})
if not patriot then 
    print('ERROR: NL Patriot Batterij kon niet worden geplaatst!') 
else
    print('INFO: NL Patriot Batterij geplaatst (DBID 2224, Operator 2061)')
end

-- Luchtverdediging (MISTRAL/SAM voor BE)
local mistral = ScenEdit_AddUnit({type='Facility', unitname='BE Mistral Sectie', side='België', dbid=1664, latitude=51.2, longitude=5.4, altitude=0})
if not mistral then 
    print('ERROR: BE Mistral Sectie kon niet worden geplaatst!') 
else
    print('INFO: BE Mistral Sectie geplaatst (DBID 1664, Operator 2011)')
end

-- Finale check
print('Scenario: De Slag om de Lage Landen Geïnitialiseerd')
print('België vs Nederland - Succes Commandant!')
print('DB-serie lock: '..db_series..' | Jaar: '..scenario_year)
