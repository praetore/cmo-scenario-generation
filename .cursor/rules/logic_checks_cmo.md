# CMO Scenario Logica & Validatie Checks

Dit document bevat de conceptuele spelregels en logica uit de CMO manual. Gebruik deze checks om te verifiëren of een gegenereerd scenario functioneel en realistisch is.

## 1. Logistiek & Brandstof (Fuel Management)
- **Bingo Fuel**: Eenheden keren om naar de basis als ze net genoeg brandstof hebben om veilig te landen.
  - *Check*: Is de afstand tot het doelwit binnen de actieradius van de eenheid? Zo niet, voeg tankers (`AAR`) toe aan de missie.
- **Air-to-Air Refueling (AAR)**: Tankers moeten op de juiste plek en hoogte vliegen.
  - *Check*: Hebben de aanvalsvliegtuigen een 'Refuel' doctrine die tankers toestaat?
  - *Check (Bomber strike — alleen indien nodig)*: **CALCM/JASSM-standoff** vanaf redelijk nabije landbasis (bijv. Florida → Cuba) → **geen** tanker verplicht. **Penetratie/LDGP** of extreem bereik → KC-missie **of** gerichte `use_refuel_unrep`. Zet **niet** `Yes_Yes` op een strike met **20+ carrier-fighters**: CMO stuurt iedereen naar 1–2 tankers (queue, mid-air crashes); beter `No_No` + `Bingo` RTB.
- **Magazines & Stores**: Eenheden zonder munitie in hun magazines kunnen niet herbewapenen.
  - *Check (Aircraft)*: Heeft de basis/carrier de juiste `Loadouts` in de voorraad (Magazines) voor de eenheden die er gestationeerd zijn? Gebruik `scripts/db_search.py --loadouts [ID] --type DataAircraft` om compatible loadouts te vinden. **Cruciaal**: Verifieer altijd dat de `LoadoutID` in de geautoriseerde lijst staat voor het specifieke `AircraftID`.
  - *Check (Loadout Compatibility)*: Zorg dat de gekozen `LoadoutID` daadwerkelijk gekoppeld is aan het toestel in de database (tabel `DataAircraftLoadouts`). Een loadout van een ander land of een andere versie van hetzelfde toestel werkt mogelijk niet.
  - *Check (Non-Air Vehicles)*: Voor `DataShip`, `DataSubmarine`, `DataFacility` en `DataGroundUnit` controleer je de effectieve "loadout" via mounts + magazines met `scripts/db_search.py --loadouts [ID] --type [Type]`.
  - *Check (Legacy alternatief)*: `scripts/db_search.py --weapons [ID] --type [Type]` geeft dezelfde interne bewapeningscontrole.
  - *Check (Scenario Preflight - verplicht)*: Draai altijd `python scripts/db_search.py --validate-scenario generated/<scenario.lua> --series <DB3K|CWDB> --version <versie>` voordat je een script oplevert (scenario’s staan in `generated/`). Controleert ook **wrapper-colon-syntax** (`mission:updateWPtimes()`, niet `mission.updateWPtimes()`). Met series+version valideert dit tegen de bijbehorende bron-`.db3` (pad via `cmo_config.json` → game `DB/`, of lokale repo-`DB/`); gebruik `CMO_Master.db` alleen voor verkenning of met `--master`.
  - *Check (Mission/Loadout Fit - verplicht)*: Een loadout die technisch op een toestel past, hoeft niet bij de missierol te passen. Controleer per missie of de loadoutrol overeenkomt met het missietype:
    - `AAW/CAP/Escort` -> A/A-loadout (of SEAD-capable escort zoals Wild Weasel).
    - `SEAD` -> **Patrol**-missie met `type='SEAD'` (geen Strike); ARM/SEAD-loadout op die missie; geen anti-ship-only of strike-only loadouts. Strike-targetlijst dekt **niet** SEAD-vuur — alleen emitters in de patrol-zone.
    - `Strike` -> strike-loadout (bommen/AG); geen A/A-only loadouts.
    - `Support/AEW` -> AEW/early-warning loadout.
    - Gebruik dezelfde `--validate-scenario` run: die rapporteert nu ook mission/loadout mismatches naast DB-compatibiliteit.
  - *Check (Strike package escort — verplicht)*: **Niet-stealth bommenwerpers** op een **Strike**-missie en elke **SEAD**-missie moeten ondersteund worden door **jager-escort** (CAP/AAW met A/A-loadout op dezelfde zijde). SEAD-vluchten hebben óók eigen escort nodig (niet alleen de strike-golf).
    - **Stealth-bommenwerpers** (o.a. B-2, F-117, B-21 in de DB-naam) vallen buiten deze harde eis; documenteer desgewenst alsnog begeleiding als scenario-doctrine dat vereist.
    - **Standoff-bommenwerpers**: Alleen **CALCM/ALCM/JASSM**-achtige loadouts op Strike (geen penetratie met LDGP) → **geen** verplichte jager-escort in preflight, maar **wel** AAR/bereik controleren; waarschuwing in `--validate-scenario`.
    - **Heuristiek in `scripts/db_search.py`**: classificatie op `DataAircraft.Name` (o.a. B-52, B-1, Tu-95, Tu-22, Su-24, F-111, …); stealth-markers sluiten uit. Ontbreekt escort, dan faalt `--validate-scenario`. Gebruik expliciete Lua-side als eerste argument van `add_air_unit_checked` / `spawn_air_wing`, anders kan de check niet per zijde worden afgedwongen.
  - *Check (Strike flight profile vs munitie — verplicht)*: **Standoff**-loadouts (CALCM, JSOW, JASSM, …) horen niet bij **penetration**-vluchtpaden (ingress over het doel als bij dumb bombs). Zet `-- @strike_package mission=<StrikeName> profile=standoff|penetration time=HH:MM:SS date=YYYY/MM/DD max_spread=N` en `-- @strike_wave id=... role=naval_strike|air_strike|air_standoff offset=<minuten t.o.v. TOT>` in het Lua-script; roep `ScenEdit_CreateMissionFlightPlan` aan met dezelfde `TIMEONTARGET` voor alle lucht-strikers. Doctrine: `ShotgunOneEngagementBVR` / `ShotgunBVR` bij standoff, niet `Shotgun50_ToO` (penetratie-gedrag). Preflight vergelijkt loadout-klassen, annotaties, flight-plan-aanroepen en wave-spread.
  - *Check (Strike TOT-synchronisatie — verplicht)*: TLAM (schepen op Strike), carrier-ordnance en B-52 CALCM moeten hetzelfde **impact-venster** hebben (`offset`-spread ≤ `max_spread`, typisch 0–15 min). Tomahawks die veel vóór JDAM/JSOW inslaan → offsets of events aanpassen. Geen meerdere `TIMEONTARGET`-waarden op één strike-missie.
  - *Check (Naval TLAM timing — verplicht)*: **Schepen op dezelfde Strike als `CreateMissionFlightPlan` lanceren Tomahawks bij scenario-start** — zet de CG/DDG op een **aparte** Strike-missie met `starttime` + `TimeOnTargetStation` (~20–35 min vóór TOT), niet op de lucht-strike-missie. Documenteer `-- @naval_package mission=<NavalStrikeName> launch=HH:MM:SS minutes_before_strike_tot=N`. Preflight faalt bij gedeelde missie of ontbrekende schedule.
  - *Check (Overige assets — waarschuwing)*: CAP/AEW/ISR-patrols zonder `starttime` terwijl de lucht-strike een flight plan heeft → waarschuwing (kunnen vroeg opstijgen); SEAD en naval hebben eigen harde checks.
  - *Check (Geen nucleaire wapens — tenzij `@scenario_policy nuclear=true`)*: Conventionele scenario's gebruiken **geen** nucleaire loadouts (ALCM/TLAM-N/ACM) en zetten `use_nuclear_weapons='No'` in `ScenEdit_SetDoctrine` per zijde. Na `place_ship` op CSG/escorts: `strip_nuclear_from_unit()` (mounts/magazines). Preflight: loadoutnaam + verplichte wapens in `DataLoadoutWeapons` (Optional=0); waarschuwing bij nucleaire DB-defaults op schepen.
  - *Check (Mission assignment — verplicht)*: Elke `place_ship` / `place_sub` / `place_sam` moet `ScenEdit_AssignUnitToMission` krijgen (direct of `for _, u in pairs(tabel)`). **Vliegtuigen**: `spawn_air_wing` → bestaande missie; zet `mission=` op `ScenEdit_AddUnit` (niet voor strike-escort) én `assign_air_to_mission` (guid/naam × missienaam/guid, `SetUnit`-fallback). Na `CreateMissionFlightPlan` kan CMO *Unassigned* tonen — **pre-flight-plan refresh**, **post-refresh**, `sync_strike_package_tot()` (geen tweede `createFlightPlans`; die wist toewijzingen). Mission-TOT via `mission_schedule_datetime()` → `YYYY.MM.DD` (match `ScenEdit_SetTime`). Strike-escort: `AssignUnitToMission(..., true)`. Preflight: **`Mission assignment`** + **`Aircraft mission assignment`**. Landbases → waarschuwing indien zonder missie.
  - *Check (Carrier strike flight-size — verplicht bij grote CSG-strike)*: Bij **≥6 carrier-strikers** of **≥6 carrier-escorts** op één Strike-missie moet CMO **niet** alles als singles lanceren. Zet via `ScenEdit_SetMission`:
    - `StrikeUseFlightSize = true`, `StrikeFlightSize = 4` (of 2/6/8), optioneel `StrikeMinAircraftReq` (bijv. 8) zodat de eerste golf wacht op voldoende toestellen;
    - `EscortUseFlightSize = true`, `EscortFlightSizeShooter = 4`, optioneel `EscortMinShooter`.
    - Documenteer in `-- @strike_package ... flight_size=4 use_flight_size=true min_aircraft=8 escort_flight_size=4 escort_use_flight_size=true`.
    - **Niet** `UseFlightSize=false` / `useflightsize=false` op die missie — dat forceert stuk-voor-stuk launch. Preflight (`scripts/db_search.py --validate-scenario`) telt `spawn_air_wing` op `carrier.guid` en faalt bij ontbrekende instellingen.
  - *Check (Tijdgeest / era-appropriate OOB — verplicht)*: Zet in elk scenario `local scenario_year = YYYY` (en `db_series`). Preflight vergelijkt **geen vaste DBID-lijst**, maar:
    - **Platform**: `YearCommissioned` / `YearDecommissioned` uit de DB vs `scenario_year` (toestel/scheep nog niet in dienst → **fout**; DB markeert uit dienst vóór scenariojaar → **waarschuwing**).
    - **Strike-munitie** (jaar ≥ 2000): loadout-**naam**-heuristiek — geen strike die **alleen** unguided is (`LDGP`, `Mk84 LDGP`, …); precisie/standoff (`JDAM`, `JSOW`, `GBU-`, `CALCM`, `JASSM`, …) is OK. **Fout** vanaf jaar ≥ 2010; **waarschuwing** 2000–2009.
    - **Rol-fit** (geen verplicht type): F-35A/B/C en carrier-type via **naam** in de DB; bommenwerper-escort via **naam**-patronen — niet “gebruik toestel X”.
    - **Bewuste uitzondering** (bijv. verouderde verdediger): documenteer in scenario-header; validator kan opzet niet raden.
  - *Check (Strike escort slot — verplicht)*: Jager-escort voor een **Strike**-missie hoort in de **escort-laag van die Strike-missie**, niet op een losse patrol met "Escort" in de naam. Gebruik `ScenEdit_AssignUnitToMission(unit, '<StrikeMission>', true)` — 3e parameter `escort=True` (zie `cmo_api_reference.md`). Strikers op dezelfde Strike-missie: 2 parameters of `false`. `--validate-scenario` faalt bij patrol-missies zoals `Strike Escort CAP` voor strike-escorts, of bij Strike zonder minstens één `escort=true`-toewijzing.
  - *Check (SEAD missie — verplicht)*: In CMO is **SEAD altijd `ScenEdit_AddMission(..., 'Patrol', {type='SEAD', zone={...}})`**, nooit `Strike`. SEAD-patrouilles vuren op **radar/emitter-contacts binnen de zone**; SAMs op de strike-targetlijst worden daar niet automatisch mee onderdrukt.
    - **Zones**: Elke `place_sam` / IADS-locatie moet binnen de bounding box van minstens één SEAD-patrolzone vallen (meerdere zones bij gespreide SAM-gordels: west/oost).
    - **Shooters**: Alleen toestellen met **ARM/SEAD-loadout** op de Patrol/SEAD-missie; **niet** A/A-only escort op dezelfde SEAD-missie (`SEAD Escort CAP` = aparte AAW-patrol).
    - **Aantallen**: Minimaal `ceil(aantal_SAM_sites / 2)` SEAD-shooters per aanvallende zijde; **waarschuwing** als shooters `<` aantal SAM-sites.
    - **Escort**: SEAD-sorties hebben nog steeds **AAW/CAP-escort** op een andere missie (zie strike-package check); Growlers op SEAD tellen niet als escort.
    - **WCS land**: Bij side-wide `WCS TIGHT` op land: zet op SEAD-missies vaak `weapon_control_status_land=0` (FREE) via `ScenEdit_SetDoctrine({side=..., mission=...})`, anders vuren HARMs tegen passieve SAMs vaak niet.
    - **Timing t.o.v. strike (verplicht bij grote carrier-SEAD)**: Laat **Wild Weasel SEAD** en **`SEAD Escort CAP`** niet bij scenario-start opstijgen als de strike-golf nog op het dek staat — Growlers/escort-Hornets gaan anders MiGs engageren vóór strike-escorts/strikers in de lucht zijn. Zet `ScenEdit_SetMission` met `starttime` + `TakeOffTime` (bijv. ~15–20 min vóór `@strike_package` TOT, ná verwachte strike-takeoff), optioneel `UseFlightSize`/`FlightSize` op de SEAD-patrols. Documenteer met `-- @sead_package missions=...,SEAD Escort CAP date=YYYY/MM/DD takeoff=HH:MM:SS minutes_before_strike_tot=N`. Zet scenario-start (`ScenEdit_SetTime`) vóór die takeoff. **Let op**: 18 min vóór TOT is vaak **niet genoeg transit** naar de SEAD-box (~270 nm van CSG) — preflight waarschuwt; bedoeling is SEAD *start* kort vóór strike, niet volledige suppressie bij TOT.
    - **Preflight**: `scripts/db_search.py --validate-scenario` controleert ook: `ScenEdit_SetTime` vóór SEAD-takeoff; `@sead_package minutes_before_strike_tot` vs berekende delta; SEAD niet te vroeg vóór TOT (vóór strike-escort-launch); `@strike_package date` vs `DATEONTARGET`.
  - *Check (Sustainability)*: Is er genoeg voorraad voor herhaalde sorties of langdurige gevechten?
- **Magazine Capaciteit**:
  - *Check*: Is het magazine niet te vol? (CMO simuleert ruimtegebruik in magazines).
  - *Check*: Zijn de magazines toegewezen aan de juiste wapensystemen (Mounts)?

## 2. Sensoren & Detectie (The OODA Loop)
- **Radar Horizon**: Sensoren op lage hoogte hebben een beperkt bereik door de kromming van de aarde.
  - *Check*: Als eenheden laag vliegen (Sea-skimming), kunnen ze pas op korte afstand gedetecteerd worden. Is dit de bedoeling voor een verrassingsaanval?
- **EMCON (Emission Control)**: Radars die aan staan verklappen de positie van de eenheid.
  - *Check*: Moeten de aanvallers 'Silent' (Passive sensors only) naderen om detectie te voorkomen?
- **Weer & Tijdstip**: Mist, regen en nacht beïnvloeden visuele en IR-sensoren.
  - *Check*: Hebben de eenheden in een nachtscenario de juiste sensoren (FLIR, IR) om doelen te vinden?

## 3. Doctrine & Rules of Engagement (ROE)
- **Weapon Control Status (WCS)**:
  - `FREE`: Schiet op alles wat niet als vriendelijk is geïdentificeerd.
  - `TIGHT`: Schiet alleen op eenheden die als vijandig zijn geïdentificeerd.
  - `HOLD`: Schiet alleen uit zelfverdediging.
  - *Check*: Past de WCS bij de politieke situatie van het scenario?
- **Proficiency Levels**: Beïnvloedt reactiesnelheid, schietvaardigheid en schadeherstel.
  - *Levels*: `Novice`, `Cadet`, `Regular`, `Veteran`, `Ace`.
  - *Check*: Is het Proficiency level van beide zijden in balans voor de gewenste moeilijkheidsgraad?

### Side-Specific Doctrine & Proficiency Profielen
- **Doel**: Definieer per zijde een "karakterprofiel" (Proficiency + WCS + doctrinegedrag), zodat scenario's direct tactisch consistent starten.
- **Profielvoorbeeld (Israël)**:
  - `Proficiency`: `Ace`
  - `WCS`: `TIGHT`
  - Doctrine-focus: conservatief BVR-gebruik, `Winchester`/`Joker` discipline, gecontroleerde engagements.
- **Profielvoorbeeld (Syrië)**:
  - `Proficiency`: `Regular`
  - `WCS`: `FREE`
  - Doctrine-focus: agressievere salvo-inzet, `Shotgun`-achtig gedrag, minder brandstof-/munitiebehoud.
- **Check**: Leg deze profielen expliciet vast bij scenario-opzet en pas ze alleen bewust aan als onderdeel van het scenario-design (niet willekeurig per prompt).

## 4. Carrier Strike Group (CSG) — niet alleen CVN
- **Realiteit**: Een **CVN/CV** zet zelden alleen uit. Normale **Carrier Strike Group** bevat o.a. de carrier, **1× cruiser (CG)** en **2×+ destroyers (DDG)** voor AAW/ASW/ASuW, plus vaak onzichtbare ondersteuning (onderzeeër, olieerder) buiten het Lua-OOB.
- **Waarom scripts soms wél solo-CVN hadden**: vereenvoudigd lucht-scenario (alleen carrier-air wing + landbasis), minder DB-zoekwerk; dat is **niet** representatief voor maritieme opbouw.
- *Check (verplicht in preflight)*: Heeft elke zijde met **vliegdek + air wing op carrier** (`spawn_air_wing` / `add_air_unit_checked` met `carrier.guid`) minstens **2 nabije oppervlakte-escorts** (DDG/CG binnen ~0,55° van de carrier)? **Waarschuwing** bij precies 2 escorts; **LHA/LHD** minstens 1 escort.
- *Check*: Groepeer escorts rond de carrier-coördinaten; losse DDG honderden km weg telt niet mee.
- **Formatie (verplicht)**: CVN + DDGs in **één groep** (`form_csg_group`, lead = CVN). **CG/DDG niet allebei** op losse patrouille. **TLAM**: **CG-shooter** op aparte Strike `Caribbean TLAM Salvo` met `assign_ship_to_mission` / `assign_tlam_shooter` — **CG niet in `form_csg_group`** (CMO wist anders de strike-toewijzing); herhaal na `sync_strike_package_tot()`. Geen `TakeOffTime` op scheeps-strike. **MH-60R** op `CSG ASW Screen` / `CSG ASuW Patrol` als **vliegtuig**. Preflight: `assign_csg_group_missions`, geen CG in group members, post-sync `assign_tlam_shooter`.
- **TOT-sync (verplicht)**: `local strike_package_tot` is de enige impacttijd voor **lucht** (`CreateMissionFlightPlan` TIMEONTARGET `YYYY/MM/DD`) en **TLAM** (`TimeOnTargetStation` via `mission_schedule_datetime` → `YYYY.MM.DD`). `sync_strike_package_tot()` zet beide strikes na flight plan opnieuw. `@strike_package time=` en `@naval_package tot=` moeten overeenkomen. `@strike_wave offset=0` voor naval + air. Preflight: **Strike TOT sync**.
- **TOT-reachability (verplicht)**: Heuristiek op afstand CSG/Florida-staging → Cubaanse doelen: TLAM-launch ≥ Tomahawk-cruise, carrier `StartTime`→TOT ≥ transit+deck-overhead, B-52 CALCM ≥ bomber-transit, SEAD-takeoff vs afstand SEAD-zone. Preflight: **Strike TOT reachability** (ERROR/WARNING). Scenario-start moet vóór impliciete B-52-takeoff liggen.
- *Preflight*: `scripts/db_search.py --validate-scenario` (heuristiek op `place_ship` + DB-`DataShip`-naam/type).
- **Helikopters (SH-60 e.d.)**: Zitten in de **DB** op CVN/CG/DDG; spawn expliciet als `Air` met `base=ddg.guid` op **`Patrol` ASW** (torpedo-loadout) en **`Patrol` naval** (Hellfire/ASuW) wanneer de tegenstander **FAC/OPV/sub** heeft. Meestal vanaf **DDG/CG**, niet CVN. **DDG 51** heeft doorgaans **2** helovakken; meer toestellen op één schip → CMO **`Unable to host unit`**. Preflight telt `spawn_air_wing` / `add_air_unit_checked` op `*.guid` tegen `DataShipAircraftFacilities` + `DataAircraftFacility` (helos: pad/hangar/deck, geen katapult). Zet `starttime`/`TakeOffTime` vóór de CSG de Cubaanse kust nadert.
- **Patrol-zones bij de CSG (verplicht in preflight)**: **Carrier CAP**, **Carrier AEW Orbit**, **CSG ASW Screen** en **CSG ASuW Patrol** moeten boven/nabij de carrier staan — niet een vast theater-raster (bv. 22.5°N terwijl de CSG op 19°N ligt). Declareer `local csg_lat, csg_lon = …` en zet reference points op `csg_lat ± offset` / `csg_lon ± offset`. Preflight (`Patrol zone proximity`) faalt als het zone-centroid **>1,5°** van `csg_lat/csg_lon` ligt. **Helo-patrouilles** (`spawn_air_wing` op `ddg51` / `bunker_hill` e.d.): zone-centroid binnen **~2°** van het host-schip. Theater-boxen (**SEAD Escort CAP**, **Wild Weasel**, **ISR Orbit**, Cubaanse CAP) zijn uitgesloten.
- **Cubaanse / blauwe oppervlakte-dreiging**: Voor nuttige ASW/ASuW-helos een **MGR-achtige mix** (Wikipedia: Rio Damuji, Pauk II, Osa II, Sonya/Yevgenya, Zhuk, Stenka, Delfin) in open water. Gebruik **OperatorCountry Cuba** in de DB — geen Sovjet-export-hulls op side `Cuba`. Preflight: **`Operator country`** + **`Era fit`**.
- **Kruisraketten (TLAM)**: CG/DDG hebben Tomahawk in VLS via de database. Voor een openingsalvo: wijs minstens één **CG/DDG** toe aan dezelfde **Strike (Land)**-missie als de luchtaanval (`ScenEdit_AssignUnitToMission(cruiser.guid, '<Strike>')`). Preflight **waarschuwt** als CSG-warships geen strike-toewijzing hebben.
- **F-35-varianten**:
  - **F-35C** → **CVN** (catapult-carrier), strike/CAP na SEAD; mag naast F/A-18 op dezelfde strike-missie (risico-gelaagd: stealth eerst, massa Hornet).
  - **F-35B** → **LHA/LHD** (STOVL), **niet** op Nimitz/CVN in Lua.
  - **F-35A** → landbases; niet op carrier spawnen.
  - Preflight **fout** bij F-35A/B op `carrier.guid` in `spawn_air_wing` / `add_air_unit_checked`.
- **Strike-munitie (tijdgeest)**: Geen vaste loadout-IDs — preflight classificeert loadout-**namen**. Vanaf ~2000 geen dumb-only strike; standoff (CALCM/JASSM-achtig) → geen verplichte jager-escort, wel AAR/bereik.
- **Bommenwerpers op Strike**: escort/AAR-regels gelden op **type** (naam/heuristiek), niet op één specifiek toestel of loadout-ID.

## 5. Eenheid Plaatsing (Land vs Water)
- **Schepen & onderzeeërs**: Mogen **niet** op land geplaatst worden (`cannot place ship over land`). Gebruik open zee (positieve diepte / elevation ≤ 0).
  - *Check (verplicht)*: Vóór `ScenEdit_AddUnit` voor `Ship`/`Sub`: `World_GetElevation({latitude=..., longitude=...})`. Als elevation **> 0** → locatie is land; kies andere coördinaten of verifieer op de kaart (bijv. zuidelijke Caraïbische Zee i.p.v. boven Cuba).
  - *Check*: Onderzeeërs niet te ondiep (stranding) en niet te diep voor de database-unit; zie ook §6 bathymetry.
- **Faciliteiten (vliegvelden, SAM)**: Meestal op **land**; niet in open oceaan tenzij de DB-unit een maritieme faciliteit is (haven/platform).
  - *Check*: Zie `skills_cmo.md` — land-gebaseerde faciliteiten in water geven vaak `Placement aborted`.
- **Preflight tooling**: `scripts/db_search.py --validate-scenario` controleert **geen** geo/elevation; plaatsingschecks blijven handmatig of via Lua `World_GetElevation` bij script-load.

## 6. Landingsfaciliteiten & Bases
- **Runway & Pad Compatibility**: Niet elk vliegtuig kan op elke baan landen.
  - *Check*: Is de landingsbaan lang genoeg voor de zware bommenwerpers? (Grote bases vs kleine airstrips).
- **Carrier Operations**: Alleen vliegdekschip-geschikte vliegtuigen kunnen op carriers opereren.
  - *Check*: Is het vliegtuig geclassificeerd als **Fixed Wing, Carrier Capable** (`Category = 2002`)?
  - *Check*: **F-35C** / F/A-18 / E-2 / EA-18 op CVN; **F-35B** alleen op LHA/LHD — zie §4.
  - *Check (Technical)*: Heeft het schip een **Carrier Catapult** (`DataAircraftFacility Type 2005`) en **Carrier Arresting Gear** (`Type 2007`) voor standaard carrier-vliegtuigen?
  - *Check (verplicht in preflight)*: **Host-capaciteit** — per `place_ship` / `place_base` met `spawn_air_wing(..., N, ..., host.guid)` of `table.field.guid`: totaal **N** mag de som van geschikte **hangar/pad**-slots niet overschrijden (`scripts/db_search.py` → `Air host`). **Runway-only** placeholder-bases (`BASE_FACILITY_DBID`, bv. 1995) worden niet op slot-telling gecontroleerd (CMO beperkt daar niet zoals op DDG-pads). `for _, k in ipairs({...}) do ... base.guid` wordt per basissleutel gecontroleerd.
  - *Check (STOVL/VTOL)*: Voor schepen zonder katapult (bijv. LHA/LHD): Is het vliegtuig **VTOL** (`RunwayLength 2001`) of **STOVL** (`RunwayLength 3005`)? Heeft het schip een **Ski Jump** (`Type 2006`) of **Flat-Top Deck** (`Type 6001/6002`)?
  - *Check*: Probeer je geen land-gebaseerde F-15's (`Category 2001`) op een vliegdekschip te stationeren? Dit veroorzaakt fouten bij het toevoegen van eenheden via Lua.

## 7. Wapens & WRA (Weapon Release Authority)
- **Salvo Size**: Hoeveel raketten worden er op één doel afgevuurd?
  - *Check*: Voorkom "overkill" (bijv. 8 raketten op 1 kleine vissersboot) door de WRA correct in te stellen in de doctrine.
- **Engagement Range**: Wapens hebben een minimale en maximale range.
  - *Check*: Bevindt het doelwit zich binnen de effectieve zone van de gekozen bewapening?

## 8. Onderzeebootoorlogvoering (Submarine Operations & ASW)
- **Thermocline (Layer)**: Temperatuurverschillen in het water kunnen sonar-signalen buigen.
  - *Check*: Onderzeeërs kunnen zich onder de 'Layer' verstoppen om detectie door oppervlakteschepen te vermijden. Is de diepte van de onderzeeër correct ingesteld t.o.v. de thermocline?
- **Convergence Zones (CZ)**: Geluid kan over grote afstanden reizen via diep water.
  - *Check*: In diep water kunnen sensoren contacten oppikken op specifieke CZ-afstanden (bijv. 30 of 60 nm). Houd hier rekening mee bij de plaatsing van eenheden.
- **Cavitation**: Snelle onderzeeërs maken veel lawaai door luchtbellen bij de schroef.
  - *Check*: Als een onderzeeër sneller gaat dan ~5-10 knopen (afhankelijk van diepte), wordt hij veel makkelijker gedetecteerd.
- **Batterij & Voortstuwing (Diesel-Electrisch vs Nuclear)**:
  - *Check (SSK)*: Hebben diesel-electrische onderzeeërs (zoals de Khalid of Kalvari klasse) genoeg batterijcapaciteit voor hun operatie? Moeten ze regelmatig 'snorkelen' om op te laden? (Snorkelen verhoogt de detectiekans aanzienlijk).
  - *Check (AIP)*: Beschikt de onderzeeër over Air-Independent Propulsion (AIP) voor langere onderwaterduur?
- **Diepte-instellingen**:
  - *Check*: Staat de onderzeeër op een veilige diepte voor de lokale zeebodem (Bathymetry)? Gebruik `World_GetElevation` om de diepte te checken.
- **Sonar Handtekening (Signature)**:
  - *Check*: Is de onderzeeër 'Silent' (Low speed, minimal emissions)? Gebruik de EMCON settings om onnodige actieve sonar-emissies te vermijden.

## 9. Elektronische Oorlogsvoering (EW)
- **OECM vs DECM**: Offensive ECM (Jammers) stoort vijandelijke radars, maar verraadt ook de positie (Home-on-Jam). Defensive ECM helpt bij het misleiden van inkomende raketten.
  - *Check*: Heeft de aanvalsmacht speciale EW-vliegtuigen (bijv. EA-18G Growler) ter ondersteuning? Is de 'Jamming' doctrine ingeschakeld?
- **ELINT (Electronic Intelligence)**: Passieve sensoren kunnen vijandelijke radars detecteren en identificeren zonder zelf ontdekt te worden.
  - *Check*: Gebruik ELINT-eenheden om de 'Electronic Order of Battle' (EOB) van de vijand in kaart te brengen voordat de aanval begint.

## 10. Communicatie & Satellieten
- **Comms Disruption**: Eenheden kunnen buiten bereik van hun hoofdkwartier raken of gestoord worden.
  - *Check*: Is 'Comms Jamming' een factor in het scenario? Hebben eenheden alternatieve communicatielijnen (bijv. Satelliet)?
- **Satellite Pass**: Satellieten vliegen in vaste banen en zijn niet constant boven het doelgebied.
  - *Check*: Als het scenario afhankelijk is van satelliet-reconnaissance, komen er dan daadwerkelijk satellieten over tijdens het scenario?

## 11. Civiel Verkeer & Neutrale Partijen
- **Collateral Damage**: Het raken van burgers kan strafpunten opleveren of escalatie veroorzaken.
  - *Check*: Is er civiel scheepvaart- of luchtverkeer aanwezig om de identificatie van doelen lastiger te maken?
- **Identification**: Zorg dat neutrale eenheden niet per ongeluk als vijandig worden gemarkeerd (WCS Tight/Hold).

## 12. Terrein & Omgeving (Land Operations)
- **Line of Sight (LOS)**: Bergen en gebouwen blokkeren radars en wapensystemen op land.
  - *Check*: Staan de SAM-sites op strategische hoogtes? Worden ze niet geblokkeerd door nabijgelegen heuvels?
- **Mobility**: Verschillende terreintypes (moeras, bos, stad) beïnvloeden de snelheid van landeenheden.
  - *Check*: Is het pad van de landeenheden realistisch gezien het terrein?

## 13. Logistiek & Cargo Operations
- **Cargo Transfers**: Eenheden kunnen lading (troepen, voorraden) overdragen tussen bases en schepen.
  - *Check*: Gebruik `ScenEdit_TransferCargo` om items te verplaatsen. Is de ontvangende unit (`Facility`, `Ship`) groot genoeg voor de lading?
- **Unloading**: Het lossen van cargo kost tijd.
  - *Check*: Plan je scenario zo dat troepen niet direct na aankomst inzetbaar zijn als ze nog moeten uitladen (`ScenEdit_UnloadCargo`).

## 14. Mijnenoorlogvoering
- **Minefields**: Mijnen kunnen passief gebieden afsluiten.
  - *Check*: Gebruik `ScenEdit_AddMinefield` om velden te leggen. Zijn er mijnenvegers aanwezig voor de tegenpartij om een pad vrij te maken?
- **Detectie**: Mijnen zijn erg lastig te detecteren zonder gespecialiseerde sonar.
  - *Check*: Heeft het scenario de juiste balans tussen 'onzichtbare' dreiging en detectiemogelijkheden?

## 15. Tijdgeest & era-appropriate OOB (geen vaste unit-lijst)

- **Principe**: Het scenariojaar bepaalt wat **realistisch** is — niet een hardcoded “gebruik F-35C id 824”-lijst. Kies units via `scripts/db_search.py` binnen de juiste `db_series`/`version`, dan valideert preflight of ze bij `scenario_year` passen.
- **Verplicht in Lua**: `local scenario_year = YYYY` (bijv. 1989, 2026) naast `db_series` / DB-lock.
- **Wat `--validate-scenario` wél doet (generiek)**:
  - DB **in-/uitdienst** vs scenariojaar voor elk uniek vliegtuig en schip in het script.
  - **Munitie-era**: strike-loadouts met alleen unguided namen in moderne jaren (zie §1).
  - **Rol-fit**: carrier-capable varianten, CSG-samenstelling, SEAD=Patrol, tanker bij langeafstands-strike — op **categorie/naam**, niet op één nationale inventaris.
- **Wat het níet doet**: geen eis “minstens 4× stealth” of “alleen Super Hornet”; geen vervanging van scenario-design. Oude tegenstanders (MiG-21, SA-2) in 2026 mogen **bewust** — verwacht dan waarschuwingen op uit-dienst-data tenzij je dat in comments uitlegt.
- **Workflow**: jaar → DB-serie (§16) → zoek passende units → loadouts met precisie/standoff voor dat jaar → preflight.

## 16. Database Series Mapping (DB3K vs CWDB)
- **Harde Jaarregel**:
  - Als `Jaar > 1980` -> gebruik `DB3K`.
  - Als `Jaar < 1980` -> gebruik `CWDB`.
- **Check**: Kies eerst de database-serie op basis van scenariojaar, en zoek daarna pas alle DBIDs/Loadouts/Weapons binnen diezelfde serie.
- **Kritieke waarschuwing**: Mix nooit ID's uit `DB3K` en `CWDB` in hetzelfde script of scenario-objectmodel; dit kan leiden tot fatale fouten/crashes in de CMO-engine.

---
*Gebruik deze checks als een pre-flight checklist voordat je het definitieve Lua-script oplevert.*
