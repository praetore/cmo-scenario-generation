# CMO Scenario Generatie Skills & Instructies

Dit document dient als de primaire handleiding voor het genereren van Lua-scripts voor **Command: Modern Operations (CMO)**. Gebruik deze instructies om syntactisch correcte en functioneel rijke scenario's te bouwen.

**Outputpad**: Schrijf nieuwe scenario-scripts naar `generated/<scenario_naam>.lua` (niet in de repository-root).

## 1. Kernbronnen (AI Single Source of Truth)
Raadpleeg EXCLUSIEF de volgende Markdown-bestanden voor het genereren van code. Deze bestanden bevatten alle benodigde informatie uit de oorspronkelijke PDF, Excel en HTML bronnen in een voor AI geoptimaliseerd formaat:

- **`.junie\cmo_api_reference.md`**: De **enig noodzakelijke** technische referentie (Agent Skills). Bevat alle actuele functies, wrappers en datatypes. Functies die hier NIET in staan, zijn verouderd (deprecated) en mogen niet gebruikt worden.
- **`.junie\logic_checks_cmo.md`**: De conceptuele "spelregels". Gebruik dit voor validatie van scenario-logica (bijv. brandstof, sensoren, doctrine) in plaats van de PDF manual.

## 2. Essentiële Lua API Regels (CMO Specifiek)

### Unit Creatie (`ScenEdit_AddUnit`)
- **Verplichte Velden**: `side`, `type`, `unitname`, `dbid`.
- **Location**: `latitude` en `longitude` are verplicht, tenzij een `base` is opgegeven.
- **Land vs Water**:
  - **`Facility`**: Meeste land-gebaseerde faciliteiten (vliegvelden, SAM) niet in open zee — `Placement aborted`. Maritieme faciliteiten (haven/platform) wel op water indien de DB-unit dat toestaat.
  - **`Ship` / `Sub`**: Alleen op **water** (niet op land). CMO geeft anders o.a. `cannot place ship over land`. Controleer coördinaten op de scenario-kaart of met `World_GetElevation`: elevation **> 0** = land.
  - **Best practice**: Gebruik Google Maps/satellietbeeld of de CMO-kaartcursor; bij twijfel elevation checken vóór spawn.
  - **Lua helper** (aanbevolen bij `place_ship` / `place_sub`):
  ```lua
  local elev = World_GetElevation({latitude=lat, longitude=lon})
  if elev and elev > 0 then
      print('ERROR: Ship/Sub placement over land at '..lat..','..lon)
      return nil
  end
  ```
- **Hoogte (`altitude`)**: 
    - **AIR**: Verplicht. Ontbreken hiervan leidt tot de fout: `Missing 'Altitude'`. Als een `base` is opgegeven, neemt het toestel de hoogte van de basis over, maar het is veiliger om het expliciet te definiëren.
    - **Overige types**: Hoewel vaak 0, kan het ontbreken van `altitude` (of het meegeven van `nil`) leiden tot de .NET error: `Object waarvoor null is toegestaan, moet een waarde hebben`. **Best practice**: Geef altijd `altitude=0` mee voor schepen, subs en faciliteiten.
- **Parameter Namen**: Gebruik `unitname` (niet `name`), `latitude` (niet `lat`), en `longitude` (niet `long`).
- **Unit Types**: `'Air'`, `'Ship'`, `'Sub'`, `'Facility'`, `'Satellite'`.
- **Base Assignment**: Gebruik `base = 'GUID'` om vliegtuigen direct op een vliegveld of carrier te plaatsen. Gebruik altijd de `.guid` van het base-object en controleer of dit object niet `nil` is.

### Database & ID Verificatie
Een cruciale les is dat DBID's (Database IDs) **niet universeel** zijn en kunnen verschillen per database-versie (bijv. DB3K v515 vs CWDB).
- **Bron vs master**: Met `--series` en `--version` gebruikt `scripts/db_search.py` standaard de bijbehorende bron-`.db3` (pad via `cmo_config.json` of lokale `DB/`). Gebruik `CMO_Master.db` (gebouwd met `scripts/merge_db.py`) voor verkenning over meerdere versies; forceer die met `--master`.
- **Master bouwen**: `python scripts/merge_db.py` neemt alle bron-DB's mee. Beperk de merge met `--series`, `--versions` of `--latest N` (bijv. `python scripts/merge_db.py --series DB3K --latest 3`).
- **Wapen Verificatie**: SAM-systemen en andere faciliteiten kunnen soms "lege" of incorrecte DBID's hebben in samengestelde databases (bijv. een SAM-unit zonder munitie of radar).
    - **Check**: Gebruik `scripts/db_search.py --weapons [ID] --type DataFacility` om te controleren of een eenheid daadwerkelijk de verwachte wapens/mounts heeft.
    - **Lege Units**: Als een `DataFacility` unit geen mounts of magazines toont in de zoekresultaten, zal deze in het spel niet kunnen vuren. Zoek dan naar een alternatieve DBID die wel bewapend is (bijv. een "Battery" of "Section" unit in plaats van een generieke "SAM Site").
    - **Nationaliteit Verificatie (`OperatorCountry`)**: Elke eenheid in de database heeft een `OperatorCountry` ID. Het is essentieel om te verifiëren dat de eenheid daadwerkelijk door het land in het scenario wordt gebruikt. **`scripts/db_search.py --validate-scenario`** faalt als `place_ship` / `place_sub` / `spawn_air_wing` een andere operator heeft dan de Lua-`side` (bv. Sovjet Osa op side `Cuba`).
        - **Valkuil**: Een generieke naam als "F-35A Lightning II" kan meerdere DBIDs hebben voor verschillende landen. Het gebruik van het verkeerde ID kan leiden tot incorrecte loadouts, sensoren of nationale markeringen.
- **Loadout/Weapon Config Matching**:
    - Voor **vliegtuigen**: Een `LoadoutID` is vaak specifiek voor een `AircraftID`. Gebruik ALTIJD `--loadouts` (of een SQL query op `DataAircraftLoadouts`) om te bevestigen dat de loadout geldig is voor de gekozen eenheid. Gebruik geen loadouts van een ander `AircraftID`, zelfs als het hetzelfde type vliegtuig lijkt.
    - Voor **niet-air units** (`DataShip`, `DataSubmarine`, `DataFacility`, `DataGroundUnit`): Gebruik `--loadouts --type [Type]` om de wapenconfiguratie (mounts + magazines) te valideren.
        - **Check**: Gebruik `python scripts/db_search.py "UnitNaam"` en controleer de `Op` kolom.
        - **Bekende Operator IDs**:
            - `2061`: Nederland (Netherlands)
            - `2011`: België (Belgium)
            - `2101`: Verenigde Staten (United States)
            - `2032`: Frankrijk (France)
            - `2035`: Duitsland (Germany)
            - `2006`: Australië (Australia)
        - **Workflow**: Als je een eenheid zoekt, filter dan altijd op het land-ID om de meest accurate versie voor je scenario te vinden.
    - **Zoektool (`scripts/db_search.py`)**: Gebruik het zoekscript om snel IDs te vinden:
  ```bash
  python scripts/db_search.py "F-14D" --series DB3K --version 515
  ```
- **Loadout/Wapenconfiguratie Zoeken**:
  - Voor vliegtuigen: gebruik `--loadouts` om alle beschikbare loadouts voor een specifiek vliegtuig-ID te zien:
  ```bash
  python scripts/db_search.py --loadouts 1179 --series DB3K --version 515
  ```
  - Voor andere voertuigtypes: gebruik `--loadouts` met `--type` om de wapenconfiguratie (magazines + mounts) te controleren:
  ```bash
  python scripts/db_search.py --loadouts 129 --type DataSubmarine --series DB3K --version 515
  ```
- **Wapens, Magazines & Onderzeeërs Zoeken**: Voor schepen, faciliteiten en onderzeeërs kun je de interne bewapening controleren:
  ```bash
  python scripts/db_search.py --weapons 129 --type DataSubmarine --series DB3K --version 515
  ```
  *(Opmerking: Dit toont welke Magazines (torpedo opslag) en Mounts (torpedobuizen) een unit heeft. Voor onderzeeërs is dit essentieel om te zien of ze de juiste torpedo's en decoys aan boord hebben).*
- **Scenario Preflight Validatie (verplicht)**: Valideer vóór oplevering altijd alle air `dbid/loadoutid` koppels in het Lua-script tegen de DB-lock van het scenario (`<series>_<version>.db3` via `cmo_config.json` of lokale `DB/`):
  ```bash
  python scripts/db_search.py --validate-scenario generated/YOUR_SCENARIO.lua --series DB3K --version 515
  ```
  *(Doel: detecteer ontbrekende of incompatibele loadouts vroeg. **Geen vaste unit-lijst** — tijdgeest, strike **flight profile**, **TOT/wave-sync** (`strike_package_tot` = air + TLAM), **CSG group lead patrol** (`assign_csg_group_missions`), **carrier strike flight-size**, **SEAD launch** (`@sead_package`), **naval TLAM timing** (`@naval_package`, aparte Strike-missie), waarschuwing CAP/AEW/ISR zonder starttime, plus mission-fit, SEAD, CSG, **patrol-zone proximity**, **nuclear policy**, F-35, AAR, escort slot. Zie `logic_checks_cmo.md` §1 en §4. Exit: `0` / `1` / `2`.)*
- **Handmatige SQL Queries**: Je kunt ook direct queries uitvoeren op de master database:
  ```bash
  sqlite3 CMO_Master.db "SELECT ID, Name, db_version FROM DataAircraft WHERE Name LIKE '%F/A-18E%' AND db_series = 'DB3K' ORDER BY db_version DESC LIMIT 5;"
  ```
- **Valkuil**: Vertrouw niet op oude tekstlijsten; ID #2748 in DB3K v515 is een MiG-21R, geen F-18.

### Robuustheid & Foutpreventie
- **Nil Checks & Error Logging**: Controleer altijd of een eenheid succesvol is aangemaakt voordat je de GUID gebruikt in vervolgfuncties. Gebruik duidelijke `print` statements om fouten te loggen als een unit niet geplaatst kan worden.
  ```lua
  local unit = ScenEdit_AddUnit(...)
  if not unit then
      print('ERROR: Unit [Naam] kon niet worden geplaatst!')
  else
      ScenEdit_AssignUnitToMission(unit.guid, 'MissieNaam')
  end
  ```
- **Conditionele Toewijzing**: Bij het aanmaken van grote groepen eenheden (bijv. in een loop), controleer of de thuisbasis (`base`) succesvol is aangemaakt om crashes te voorkomen.
  ```lua
  for i=1, 12 do
      if base_unit then
          local u = ScenEdit_AddUnit({..., base=base_unit.guid, ...})
          if u then ScenEdit_AssignUnitToMission(u.guid, 'CAP') end
      end
  end
  ```
- **Foutmelding: "null is toegestaan, moet een waarde hebben"**: Dit wijst op een ontbrekende parameter die de .NET engine verwacht.
  - **Vliegtuigen op basis**: Gebruik `altitude = '0'` (string) wanneer je een toestel op een basis of carrier plaatst (`base`). De string-format wordt vaak robuuster verwerkt dan een numerieke `0` die in conflict kan komen met Nullable types.
  - **Overige types**: Gebruik altijd `altitude = 0` voor schepen en faciliteiten.
  - **Validatie**: Check of `dbid` en `loadoutid` correct zijn voor het type eenheid.
- **Type Verificatie bij Loops**: Wanneer je over een lijst met units itereert (bijv. van `side.units`), controleer dan altijd het type van de GUID/waarde voordat je `ScenEdit_GetUnit` aanroept.
  ```lua
  for k, v in pairs(side.units) do
      if type(v) == 'string' then
          local u = ScenEdit_GetUnit({guid=v})
          -- Verwerk unit
      end
  end
  ```

### Missie Beheer (`ScenEdit_AddMission`)
- **Syntax**: `ScenEdit_AddMission(Side, Name, Type, {Options})`.
- **Type**: Bijv. `'Patrol'`, `'Strike'`, `'Support'`, `'Cargo'`, `'Ferry'`.
- **Opties**: Bijv. `{type='AAW'}` voor een luchtpatrouille; **`{type='SEAD'}` alleen op `Patrol`** — geen Strike-SEAD in CMO.
- **SEAD (Wild Weasel)**: `ScenEdit_AddMission(Side, 'Wild Weasel SEAD West', 'Patrol', {type='SEAD', zone={'RP1', ...}})`. Leg de zone over vijandelijke SAM-coördinaten; wijs EA-18G/ARM-loadouts toe. Escortjagers op een **aparte** AAW-patrol (`SEAD Escort CAP`). Bij `WCS TIGHT` op zijde: overweeg `weapon_control_status_land=0` op de SEAD-missie zelf.
- **Volgorde van Executie**: Missies **moeten** zijn aangemaakt voordat eenheden eraan kunnen worden toegewezen via `ScenEdit_AssignUnitToMission`.
- **Assigning Units vs Targets**:
    - Gebruik `ScenEdit_AssignUnitToMission(unitGuid, missionName)` om eenheden (vliegtuigen/schepen) aan een missie toe te wijzen.
    - **Strike escort (3e parameter)**: `ScenEdit_AssignUnitToMission(unitGuid, strikeMissionName, true)` wijst eenheden toe aan de **escort**-laag van een Strike-missie. Zonder `true` komen ze in de hoofdgolf. Strikers: `ScenEdit_AssignUnitToMission(guid, 'My Strike')` of met `false`.
    - Gebruik `ScenEdit_AssignUnitAsTarget(targetGuid, missionName)` om **doelen** (faciliteiten/vijandelijke eenheden) aan een Strike-missie toe te voegen. Het gebruik van `AssignUnitToMission` voor een doelwit zal falen met de error: "Couldn't find the mission".
  - **Helper in scenario-scripts** (aanbevolen):
  ```lua
  -- add_air_unit_checked(..., mission_name, strike_escort)
  -- spawn_air_wing(..., mission_name, base_guid, strike_escort)
  if strike_escort then
      ScenEdit_AssignUnitToMission(u.guid, mission_name, true)
  else
      ScenEdit_AssignUnitToMission(u.guid, mission_name)
  end
  ```
- **Best Practice**: Wijs eenheden direct bij creatie toe aan hun missie als deze al bekend is. Dit is robuuster dan achteraf loops draaien.
- **Validatie**: Gebruik `ScenEdit_GetMission(Side, Name)` na creatie/configuratie om te verifiëren of de missie bestaat. Let op bij het uitlezen van eigenschappen:
    - Gebruik de correcte casing: `mission.targetlist` (kleine letters) voor targets.
    - Controleer altijd of de lijst bestaat voordat je de lengte opvraagt: `if mission.targetlist then ... #mission.targetlist ... end`.
- **Strike- en SEAD-packages (doctrine)**: Zet voor **niet-stealth bommenwerpers** op Strike altijd aparte **jager-escort** (CAP/AAW). Zet voor **SEAD** óók **escortjagers** (los van de strike-escort als doctrine dat vereist). `scripts/db_search.py --validate-scenario` controleert minimaal of er op dezelfde Lua-`side` een AAW/CAP-toewijzing met A/A-loadout bestaat wanneer de heuristiek bommenwerpers/SEAD detecteert.

### Side Informatie (`VP_GetSide`)
- **Syntax**: Gebruik altijd een selector table: `VP_GetSide({side='SideName'})`. Een directe string `VP_GetSide('SideName')` resulteert in een "Invalid arguments" error.

### Houding en Relaties (Stance/Posture)
Gebruik de volgende lettercodes voor `ScenEdit_SetSidePosture`:
- `'H'` = Hostile (3)
- `'F'` = Friendly (1)
- `'N'` = Neutral (0)
- `'U'` = Unfriendly (2)

## 3. Werken met Wrappers & Objecten
Wrappers zijn objecten die door CMO worden geretourneerd (bijv. door `ScenEdit_GetUnit`).

- **Eigenschappen benaderen**: `unit.altitude`, `unit.course`, `unit.fuel` (punt `.`).
- **Instance-methodes**: `mission:updateWPtimes()`, `mission:createFlightPlans({...})`, `flight:refreshWaypoints()` — **dubbele punt `:`**, niet `mission.updateWPtimes()` (zie `cmo_api_reference.md` → Wrapper-aanroep).
- **Fields opvragen**: Gebruik `print(unit.fields)` om alle beschikbare eigenschappen van een object in de console te zien.
- **GUID's**: Gebruik altijd de `.guid` eigenschap voor betrouwbare verwijzingen in andere functies.

## 4. Scenario Design Workflow
0.  **OOB in file header (verplicht)**: Zet aan het begin van elk scenario Lua-script een commentblok met de Order of Battle (OOB): scenariojaar/DB-serie, sides en posture, missies per side, force composition (bases, types, aantallen, missie-toewijzing), en primaire doelen. Werk dit blok bij wanneer de orbat verandert.
1.  **Sides & Posture**: Maak zijden aan en stel relaties in.
2.  **Infrastructuur**: Plaats bases (`Facility`) en carriers (`Ship`). **CVN/CV**: plaats een **CSG** (carrier + nabijgelegen CG/DDG), niet alleen het vliegdekschip — zie `logic_checks_cmo.md` §4; `--validate-scenario` controleert dit. **Mission assignment**: elke `place_ship` / `place_sub` / `place_sam` krijgt `ScenEdit_AssignUnitToMission` (of `for _, u in pairs(tabel)` / `pairs({tabel.veld, ...})`). **Host-capaciteit**: preflight telt `spawn_air_wing` op hosts tegen DB-vliegdekslots.
3.  **Units**: Voeg vliegtuigen, schepen en onderzeeërs toe. Koppel vliegtuigen aan bases.
4.  **Missions**: Maak missies aan en wijs eenheden toe via `ScenEdit_AssignUnitToMission`.
5.  **Events**: Voeg triggers en acties toe voor dynamiek.
    - `level` codes: 1 = triggers, 2 = conditions, 3 = actions, 4 = event details. (Gebruikt in `ScenEdit_GetEvent`)
    - **Waypoint Events**: Voor waypoint triggers wordt een lokale tabel `wpAction` aangemaakt met `guid` (eenheid) en `index` (waypoint nummer). Dit kan gebruikt worden in de Lua code van de actie.

## 5. Datum & Tijd Tools
Sinds maart 2026 zijn er krachtige functies beschikbaar voor tijdconversies:
- `Tool_DateTimeToSeconds("2026-05-08 14:00:00")`: Handig voor het berekenen van offsets voor events.
- `Tool_SecondsToDateTime(seconds)`: Om tijdstippen terug te vertalen naar leesbaar format.

## 6. Debugging & Best Practices
- **Console Output**: Gebruik `print()` ruimschoot om de voortgang van het script te volgen.
- **Return Values**: Sla de resultaten van `AddUnit` op: `local u = ScenEdit_AddUnit(...)`.
- **Database ID's (DBID)**: Zorg dat je de juiste DBID gebruikt uit de actieve database van het scenario.
- **Hoofdlettergevoeligheid**: Let op: de API is meestal hoofdlettergevoelig voor parameter namen in tabellen.
- **Pro vs Standard**: In `.junie\cmo_api_reference.md` zijn functies of velden die exclusief voor de Professional Edition zijn, gemarkeerd met `PRO ONLY`. Gebruik deze alleen als je weet dat de gebruiker de Professional Edition heeft.
- **Verplichte Parameters**:
    - Velden gemarkeerd met `(verplicht)` zijn strikt noodzakelijk.
    - Velden gemarkeerd met `(optioneel)` kunnen worden weggelaten.
    - Bij velden **zonder label** in de referentie: neem het zekere voor het onzekere en raadpleeg de `Signature` of de functiebeschrijving. Als een veld essentieel lijkt voor de operatie (zoals `side` bij het toevoegen van iets), behandel het dan als verplicht.
- **Deprecated Functies**: Gebruik alleen de functies die aanwezig zijn in `.junie\cmo_api_reference.md`. Oude functies zoals `ScenEdit_AddAircraft` (vervangen door `ScenEdit_AddUnit`) staan niet meer in de referentie en mogen niet gebruikt worden.

## 6. Handige Snippets
**Alle units van een zijde ophalen:**
```lua
local side = VP_GetSide('USA')
for k,v in pairs(side.units) do
    print(v.name .. " (" .. v.guid .. ")")
end
```

**Snelheid en Hoogte instellen:**
```lua
ScenEdit_SetUnit({guid='GUID', manualSpeed=350, manualAltitude=5000})
```
