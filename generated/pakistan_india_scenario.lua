-- Scenario: India vs Pakistan - Operation Trident II
-- Location: Arabian Sea / Northern Border
-- Date: 2026-05-08

-- 1. Sides & Posture
ScenEdit_AddSide({side='India'})
ScenEdit_AddSide({side='Pakistan'})
ScenEdit_SetSidePosture('India', 'Pakistan', 'H')
ScenEdit_SetSidePosture('Pakistan', 'India', 'H')

-- 2. Missions Setup (Must exist before units are assigned)
-- India: CAP over Fleet
ScenEdit_AddMission('India', 'Fleet CAP', 'Patrol', {type='AAW'})
ScenEdit_AddReferencePoint({side='India', name='RP-CAP-1', latitude='19.0', longitude='67.5'})
ScenEdit_AddReferencePoint({side='India', name='RP-CAP-2', latitude='19.0', longitude='68.5'})
ScenEdit_AddReferencePoint({side='India', name='RP-CAP-3', latitude='18.0', longitude='68.5'})
ScenEdit_AddReferencePoint({side='India', name='RP-CAP-4', latitude='18.0', longitude='67.5'})
ScenEdit_SetMission('India', 'Fleet CAP', {area={'RP-CAP-1', 'RP-CAP-2', 'RP-CAP-3', 'RP-CAP-4'}})

-- Pakistan: Anti-Carrier Strike
ScenEdit_AddMission('Pakistan', 'Anti-Carrier Strike', 'Strike', {type='Sea'})

-- 3. Infrastructure - India (Carrier & Bases)
-- INS Vikrant (ID 2515 in DB3K v515)
-- Positioned further into the Arabian Sea to avoid land
local vikrant = ScenEdit_AddUnit({type='Ship', unitname='INS Vikrant', side='India', dbid=2515, latitude='18.5', longitude='68.0', altitude=0})
if vikrant ~= nil then
    -- Escorts
    ScenEdit_AddUnit({type='Ship', unitname='INS Kolkata', side='India', dbid=2360, latitude='18.51', longitude='68.02', altitude=0})
    ScenEdit_AddUnit({type='Ship', unitname='INS Shivalik', side='India', dbid=1437, latitude='18.49', longitude='67.98', altitude=0})
    
    -- Aircraft on Vikrant (Rafale M - ID 1179)
    -- Loadout 11072: A/A: MICA, Standard CAP
    for i=1, 12 do
        local u = ScenEdit_AddUnit({type='Air', unitname='IN Rafale M #'..i, side='India', dbid=1179, base=vikrant.guid, loadoutid=11072, altitude='0'})
        if u then ScenEdit_AssignUnitToMission(u.guid, 'Fleet CAP') end
    end
else
    print('Warning: INS Vikrant not created.')
end

-- Airbase - Jamnagar
local jamnagar = ScenEdit_AddUnit({type='Facility', unitname='Jamnagar Air Base', side='India', dbid=430, latitude='22.48', longitude='70.01', altitude=0})
if jamnagar ~= nil then
    -- Su-30MKI (ID 853)
    -- Loadout 2368: A/A: AA-12 Adder A [R-77], Standard CAP
    for i=1, 8 do
        ScenEdit_AddUnit({type='Air', unitname='IAF Su-30MKI #'..i, side='India', dbid=853, base=jamnagar.guid, loadoutid=2368, altitude='0'})
    end
    -- AEW&C Phalcon (ID 1435 - Boeing 707 Phalcon AEW)
    -- Loadout 8060: Airborne Early Warning (AEW)
    ScenEdit_AddUnit({type='Air', unitname='IAF Phalcon #1', side='India', dbid=1435, base=jamnagar.guid, loadoutid=8060, altitude='0'})
end

-- 3. Infrastructure - Pakistan
-- Airbase - PAF Masroor
local masroor = ScenEdit_AddUnit({type='Facility', unitname='PAF Masroor', side='Pakistan', dbid=430, latitude='24.89', longitude='66.93', altitude=0})
if masroor ~= nil then
    -- JF-17 Block 3 (ID 4827)
    -- Loadout 17446: YJ-83K [C-802AK] (Anti-ship)
    for i=1, 12 do
        local u = ScenEdit_AddUnit({type='Air', unitname='PAF JF-17C #'..i, side='Pakistan', dbid=4827, base=masroor.guid, loadoutid=17446, altitude='0'})
        if u then ScenEdit_AssignUnitToMission(u.guid, 'Anti-Carrier Strike') end
    end
    -- ZDK-03 (ID 2914 - Y-8F-400 Cub)
    -- Loadout 15425: Airborne Early Warning (AEW)
    ScenEdit_AddUnit({type='Air', unitname='PAF ZDK-03 #1', side='Pakistan', dbid=2914, base=masroor.guid, loadoutid=15425, altitude='0'})
end

-- Pakistan Naval Group
-- Moved further offshore (south) from Karachi (24.8N)
local tughril = ScenEdit_AddUnit({type='Ship', unitname='PNS Tughril', side='Pakistan', dbid=3568, latitude='22.0', longitude='65.0', altitude=0})
if tughril ~= nil then
    -- PNS Zulfiquar (ID 2105 - F-22P Class)
    ScenEdit_AddUnit({type='Ship', unitname='PNS Zulfiquar', side='Pakistan', dbid=2105, latitude='22.01', longitude='65.02', altitude=0})
end

-- Submarines
-- Deep water positions
-- PNS Hamza (ID 129 - Agosta 90B)
ScenEdit_AddUnit({type='Sub', unitname='PNS Hamza', side='Pakistan', dbid=129, latitude='21.5', longitude='65.5', altitude=-50})
-- INS Kalvari (ID 108 - Scorpene)
ScenEdit_AddUnit({type='Sub', unitname='INS Kalvari', side='India', dbid=108, latitude='18.0', longitude='67.0', altitude=-50})

-- 5. Doctrine & ROE
ScenEdit_SetDoctrine({side='India'}, {weapon_control_status_air=1, weapon_control_status_surface=1}) -- Tight
ScenEdit_SetDoctrine({side='Pakistan'}, {weapon_control_status_air=0, weapon_control_status_surface=0}) -- Free

-- 6. Messages
ScenEdit_SpecialMessage('India', 'Operation Trident II has commenced. Defend the fleet and secure the Arabian Sea.')
ScenEdit_SpecialMessage('Pakistan', 'India is blockading our ports. Break the blockade at all costs.')

print('Scenario Pakistan vs India updated successfully.')
