# CMO Lua API Skills

This file contains the Command: Modern Operations Lua API in a format optimized for AI agents. Pair with `.cursor/rules/logic_checks_cmo.md` for scenario validation rules.

## Functions

### ScenEdit_EventX()
This function shows the current event that has been triggered. Note that EventX() can also be used as a shortcut for ScenEdit_EventX()

**Signature:** `ScenEdit_EventX ()`

**Returns:** `Event The triggering event as a wrapper, else a nil is returned.`

---

### ScenEdit_AddSpecialAction()
This function adds a new special action event to the side. The event will then show under the Special Events button.

**Signature:** `ScenEdit_AddSpecialAction(table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The name/GUID of the side for the action
- **ActionNameOrID =** (`string`): The name or ID of the special action
- **description =** (`string`): If specified, the new description for the action
- **IsActive =** (`True/False`): If the action is visible to the player
- **IsRepeatable =** (`True/False`): If the player can use the action multiple times
- **ScriptText =** (`string`): The Lua script for the SA. Note as the script is a multi line string, it requires a '\r\n' to be appended after each line so it is correctly interpreted/formated by the Editor.

**Returns:** `True/False Returns True if successful`

---

### ScenEdit_ExecuteEventAction()
This function executes an event action Lua script but does not show the results.

**Signature:** `ScenEdit_ExecuteEventAction (EventDescriptionOrID)`

**Parameters:**
- **EventDescriptionOrID** (`string`): The description/guid of the event action

**Returns:** `string "Ok" on execution or nothing.`

---

### ScenEdit_ExecuteSpecialAction()
This function executes a Lua Special action script but does not show results.

**Signature:** `ScenEdit_ExecuteSpecialAction (eventNameOrId)`

**Parameters:**
- **eventNameOrId** (`string`): The name/guid of the event action

**Returns:** `string "Ok" on execution or nothing.`

---

### ScenEdit_GetEvent()
This function returns the properties of an event; the full set of triggers, conditions and actions, or just limited to a subset. Level is optional and defaults to all details if not supplied. The event can be extracted in XML format by adding '10' to the level. The XML can then be used in ScenEdit_SetEvent() to import details into an event

**Signature:** `ScenEdit_GetEvent ( EventDescriptionOrID, level )`

**Parameters:**
- **EventDescriptionOrID** (`string`): The event name/guid to retrieve
- **level** (`number1 = triggers 2 = conditions 3 = actions 4 = event`): The detail to return from the function.

**Returns:** `Event The event wrapper containing the details`

---

### ScenEdit_GetEvents()
This function returns the properties of all event; the full set of triggers, conditions and actions, or just limited to a subset. Level is optional and defaults to all details if not supplied.

**Signature:** `ScenEdit_GetEvents (level)`

**Parameters:**
- **level** (`number1 = triggers 2 = conditions 3 = actions 4 = event`): The detail to return from the function.

**Returns:** `Table {} of Event Event wrappers`

---

### ScenEdit_GetSpecialAction()
This function retrieves the properties of special action

**Signature:** `ScenEdit_GetSpecialAction ( action_info )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): Side name/guid
- **mode = 'list'**: Extracts all special actions for all sides if 'side' not supplied, else filters just for 'side'
- **ActionNameOrID =** (`string`): Specific Special action event name/guid

---

### ScenEdit_SetAction()
This function Sets the attributes of an Event action. The available operation/modes available are:

**Signature:** `ScenEdit_SetAction (table)`

**Parameters:**
- **table** (`table`):
- **description =** (`string`): Action GUID or Description
- **mode =** (`string "add", "remove", "update", "list"`): Type of action to take on details
- **rename =** (`string`): New Description for the Action. Applicable to mode 'update' only
- **type =** (`string`): Type of Action. Applicable to mode 'add' only
- **scripttext =** (`string`): Script to be executed for a Lua Action
- **scriptfor =** (`number 0: EventAction, 1: WaypointAction`): Script for action or for waypoints selector

**Returns:** `table {} Table of action values (needs to be expanded )`

---

### ScenEdit_SetCondition()
This function Sets the attributes of an Event Condition.

**Signature:** `ScenEdit_SetCondition ( table )`

**Parameters:**
- **table** (`table`):
- **description =** (`string`): Condition GUID or Description
- **mode =** (`string "add", "remove", "update", "list"`): Type of action to take on details
- **rename =** (`string`): New Description for the Condition. Applicable to mode 'update' only
- **type =** (`string`): Type of Condition. Applicable to mode 'add' only

**Returns:** `table {} Table of condition values (needs to be expanded )`

---

### ScenEdit_SetEvent()
This function sets the attributes of an event. Use the SetEventAction/Trigger/Condition to associate those to the event.

**Signature:** `ScenEdit_SetEvent (EventDescriptionOrID, options)`

**Parameters:**
- **EventDescriptionOrID** (`string`): Event GUID or Description
- **options** (`table`):
- **mode =** (`string "add", "remove", "update"`): Mode to perform
- **description =** (`string`): Event description
- **newname =** (`string`): New name for event if renaming the event. Not suggested as it can cause issues if scripts are using event names to perform tasks on.
- **isActive =** (`True/False`): Event active
- **isShown =** (`True/False`): Event is shown
- **IsRepeatable =** (`True/False`): Event can repeat
- **Probability =** (`Number 0 -100`): Event can repeat

**Returns:** `Event The event wrapper containing the details`

---

### ScenEdit_SetEventAction()
This function Sets the action of a Event.

**Signature:** `ScenEdit_SetEventAction (EventDescriptionOrID, options)`

**Parameters:**
- **EventDescriptionOrID** (`string`): Event GUID or Description
- **options** (`table`):
- **mode =** (`string "add", "remove", "replace"`): Mode to perform
- **description =** (`string`): Action description/name or GUID

**Returns:** `actions{} of`

---

### ScenEdit_SetEventCondition()
This function Sets the Condition of an Event.

**Signature:** `ScenEdit_SetEventCondition (EventDescriptionOrID, options)`

**Parameters:**
- **EventDescriptionOrID** (`string`): Event GUID or Description
- **options** (`table`):
- **mode =** (`string "add", "remove", "replace"`): Mode to perform
- **description =** (`string`): Condition description/name or GUID

**Returns:** `conditions{} of`

---

### ScenEdit_SetEventTrigger()
This function Sets the Trigger of an Event.

**Signature:** `ScenEdit_SetEventTrigger (EventDescriptionOrID,options)`

**Parameters:**
- **EventDescriptionOrID** (`string`): Event GUID or Description
- **options** (`table`):
- **mode =** (`string "add", "remove", "replace"`): Mode to perform
- **description =** (`string`): Trigger description/name or GUID

**Returns:** `triggers{} of`

---

### ScenEdit_SetSpecialAction()
Sets the properties of an existing special action.

**Signature:** `ScenEdit_SetSpecialAction (options)`

**Parameters:**
- **options** (`table`):
- **ActionNameOrID =** (`string`): Special Action Event name/guid
- **side =** (`string`): Side for Special Action
- **description =** (`string`): Event description
- **newname =** (`string`): New name for event if renaming the event. Not suggested as it can cause issues if scripts are using event names to perform tasks on.
- **isActive =** (`True/False`): Event active
- **IsRepeatable =** (`True/False`): Event can repeat
- **ScriptText =** (`Lua script`): Lua script to run
- **mode =** (`string "remove"`): Mode to perform - only used for deleting the SA. Absent means it updates

**Returns:** `booleanTrue or NIL if error`

---

### ScenEdit_SetTrigger()
This function Sets the attributes of a trigger.

**Signature:** `ScenEdit_SetTrigger ( table )`

**Parameters:**
- **table** (`table`):
- **description =** (`string`): Trigger GUID or Description
- **mode =** (`string "add", "remove", "update", "list"`): Type of action to take on details
- **rename =** (`string`): New Description for the Trigger. Applicable to mode 'update' only
- **type =** (`string`): Type of Trigger. Applicable to mode 'add' only

---

### ScenEdit_UnitC()
Detected Contact ...from a Unit Detected event trigger.Otherwise, a nil is returned. Note that UnitC()can also be used as a shortcut for ScenEdit_UnitC()

**Signature:** `ScenEdit_UnitC ( )`

**Parameters:**
- **None**

---

### ScenEdit_UnitX()
This function returns the Activating Unit that triggered the current Event. Note that UnitX() can also be used as a shortcut for ScenEdit_UnitX()

**Signature:** `ScenEdit_UnitX ( )`

**Parameters:**
- **None**

---

### ScenEdit_UnitY()


**Signature:** `ScenEdit_UnitY ( )`

**Parameters:**
- **None**

---

### ScenEdit_AddMission()
This function adds a new mission to the side based on the supplied options It is suggested to make the mission name unique across the scenario to ensure there are no conflicts as to the side it is applicable to Once the core mission is added, the mission can be adjusted through a wrapper or ScenEdit_SetMission

**Signature:** `ScenEdit_AddMission (SideNameOrId, MissionNameOrId, MissionType, MissionOptions)`

**Parameters:**
- **SideNameOrId** (`string`): The mission side name/guid
- **MissionNameOrId** (`string`): The mission name as this is a new mission
- **MissionType** (`MissionType`): The type of mission which will control what is valid for the following options
- **MissionOptions** (`table`):
- **category =** (`MissionCategoryMission (0), Package (1), Taskpool (2)`): The category of mission being added. The default is 'Mission'.
- **destination =** (`string`): A mission destination location name/guid (This only applies to a 'Ferry' mission)
- **pool =** (`ParentTaskpool`): The name or GUID of the task pool this package draws from. (This only applies to mission category 'package')
- **type =** (`MissionSubType`): Mission sub-type (This only applies to mission types 'Patrol' and 'Strike')
- **zone =** (`table`):
- **string** (`The`): reference point guid/name

**Returns:** `Mission A mission wrapper for the new mission or nil otherwise. Retaining the mission guid for updating would be desirable rather than rely on the name itself.`

---

### ScenEdit_AssignUnitAsTarget()
This function assigns targets to a Strike mission target list. The target list can be (a) one single unit/contact name/guid, or (b) a table of unit/contact name/guid 'UnitX' as the triggering unit, can be used as the unit name. Contacts can also be assigned. Refer to the VP_ functions for details

**Signature:** `ScenEdit_AssignUnitAsTarget (AUNameOrIDOrTable, MissionNameOrID)`

**Parameters:**
- **AUNameOrIDOrTable** (`string`): or table {} The name/GUID of the unit, or a table of unit/contact name/GUID to add
- **MissionNameOrID** (`string`): The strike mission name/guid to be updated

**Returns:** `table {} of string A table of target GUIDs that were added`

---

### ScenEdit_AssignUnitToMission()
This function assign a unit to a mission. The 'UnitX' can be used as the unitname.

**Signature:** `ScenEdit_AssignUnitToMission (unitname, mission, escort)`

**Parameters:**
- **unitname** (`string`): The name/GUID of the unit to assign
- **mission** (`string`): The mission name/GUID to assign to
- **escort** (`True/False`) (optional): If the mission is a strike one, then assign unit to the 'Escort' for the strike [Default=False]

**Returns:** `True/False True if Successful`

**Practical note (repo):** Official Lua docs list **name/GUID** for both parameters ([Command Lua Docs — `ScenEdit_AssignUnitToMission`](https://commandlua.github.io/oldsite/index.html)). In generated scenarios we treat that as **asymmetric**:

| Parameter | Prefer | Why |
| :--- | :--- | :--- |
| **unitname** | **GUID** (from `ScenEdit_AddUnit` / `GetUnit`) | Avoids duplicate-name ambiguity; matches forum/community practice. |
| **mission** | **Mission name** (string from `ScenEdit_AddMission`) | Passing `GetMission().guid` often logs `Couldn't find the mission <guid>` and returns false, even when the same mission resolves by name. |

Same applies when setting **`unit.mission`** or **`ScenEdit_SetUnit({ mission = … })`** — that path calls `AssignUnitToMission` internally; use the mission **name**, not its guid.

`ScenEdit_SetMission` / `ScenEdit_GetMission` online docs describe the second argument as mission **name** only; local generated API text also allows guid — prefer **side + name** in scenario scripts. See `AGENTS.md` §6 (init log) and `scripts/scenario_bootstrap.lua` (`assign_air_to_mission`, `assign_ship_to_mission`).

---

### ScenEdit_CreateMissionFlightPlan()
This function creates flights for a mission.

**Signature:** `ScenEdit_CreateMissionFlightPlan (SideName, MissionName, options)`

**Parameters:**
- **SideName** (`string`): The mission side
- **MissionName** (`string`): The mission name/guid
- **options** (`table`):
- **DATEONTARGET =** (`string`): The mission time on target day, YYYY/MM/DD
- **TIMEONTARGET  =** (`string`): The mission time on target, HH:MM:SS
- **TAKEOFFDATE =** (`string`): The mission takeoff day, YYYY/MM/DD
- **TAKEOFFTIME  =** (`string`): The mission takeoff time, HH:MM:SS

**After creation:** fetch the mission wrapper and refresh waypoint times with **colon syntax** (see [Calling wrappers in Lua](#calling-wrappers-in-lua-required)):

```lua
ScenEdit_CreateMissionFlightPlan('United States', 'My Strike', {
    DATEONTARGET = '2026/06/01',
    TIMEONTARGET = '06:30:00',
})
local m = ScenEdit_GetMission('United States', 'My Strike')
if m then m:updateWPtimes() end
```

**Verify after assign:** re-fetch with [`ScenEdit_GetMission`](https://commandlua.github.io/assets/Function_ScenEdit_GetMission.html) and compare [Mission wrapper](https://commandlua.github.io/assets/Wrappers.html#wrapper_Mission) fields `TimeOnTargetStation` (TOT / on-station), `starttime`, `TakeOffTime`. Bootstrap: `cmo.verify_mission_schedule(side, mission, { tot_hms = '06:30:00', launch_dt = '2026.06.01 05:45:00' })` — **aborts scenario init** on mismatch (`error()`).

---

### ScenEdit_DeleteMission()
This function will delete a mission from the side and unassign any units attached to it.

**Signature:** `ScenEdit_DeleteMission (SideNameOrId, MissionNameOrId)`

**Parameters:**
- **SideNameOrId** (`string`): The side name/guid
- **MissionNameOrId** (`string`): The side's mission name/guid

**Returns:** `True/False True if successful`

---

### ScenEdit_ExportMission()
This function exports a mission's parameters as a XML file in folder Command_base/Defaults.

**Signature:** `ScenEdit_ExportMission (SideNameOrId, MissionNameOrId)`

**Parameters:**
- **SideNameOrId** (`string`): The mission side name/guid
- **MissionNameOrId** (`string`): The mission name/guid

**Returns:** `table {} of string A table of mission GUIDs that were exported.`

---

### ScenEdit_GetMission()
This function retrieves the specific mission details

**Signature:** `ScenEdit_GetMission ( SideNameOrId, MissionNameOrId)`

**Parameters:**
- **SideNameOrId** (`string`): The side name/guid
- **MissionNameOrId** (`string`): The mission name/guid

**Returns:** `Mission The mission wrapper if the it exists ornilotherwise.`

---

### ScenEdit_GetMissions()
This function retrieves the mission details of a side

**Signature:** `ScenEdit_GetMissions ( SideNameOrId)`

**Parameters:**
- **SideNameOrId** (`string`): The side name/guid

**Returns:** `{ } of multiple Mission The mission wrapper if the it exists ornilotherwise.`

---

### ScenEdit_ImportMission()
This function imports a mission's parameters as a XML file in folder Command_base/Defaults. [Experimental as this should really be treated like an attachment so can be imported with Scenario]

**Signature:** `ScenEdit_ImportMission (SideNameOrId,MissionNameOrId)`

**Parameters:**
- **SideNameOrId** (`string`): The side to import to
- **MissionNameOrId** (`string`): The mission name in the folder. The imported file will be 'MissionNameOrId.XML'.

**Returns:** `table {} string A table of mission GUIDs that were exported.`

---

### ScenEdit_SetMission()
This function Sets details for a mission.

**Signature:** `ScenEdit_SetMission (SideName, MissionNameOrId, MissionOptions)`

**Parameters:**
- **SideName** (`string`): The mission side
- **MissionNameOrId** (`string`): The mission name/guid
- **MissionOptions** (`table`): {} Refer to the Mission object Mission for the possible values Only the items to be updated need to be added as 'item = value'.

**Returns:** `Mission The mission object if the mission exists or nilotherwise.`

---

### ScenEdit_RemoveUnitAsTarget()
This function removes target(s) from a Strike mission. The value 'UnitX' can be used in an event for AUNameOrIDOrTable.

**Signature:** `ScenEdit_RemoveUnitAsTarget (AUNameOrIDOrTable,MissionNameOrID)`

**Parameters:**
- **AUNameOrIDOrTable** (`table`):
- **string** (`The`): name/GUID of the single unit
- {} of multiple string A table of name/GUID to remove from target list
- **MissionNameOrID** (`string`): The strike mission name/guid

**Returns:** `table {} of string A table of target GUIDs removed`

---

### ScenEdit_AddReferencePoint()
This function creates one or more reference point(s) as defined by the table. It can take a single new referrnce point, or a table of new reference points. The table must contain at least a side, and one set of latitude and longitude, or the side and an area defined by one or more latitude and longitude values. This is mainly because Reference Points are recorded by side; the same named RP might exist on more than one side which can lead to confusion. Points can also be relative to a specified unit based on bearing and distance. This applies to ALL the rp(s) in the function call, and the unit name/GUID that the RP(s) are relative to has to be on the same side.

**Signature:** `ScenEdit_AddReferencePoint (table)`

**Parameters:**
- **table** (`table`):
- **area =** (`table`):
- **bearing =** (`number (0-360)`): Bearing from the 'relative' unit
- **bearingtype =** (`bearingFixed (0) or Rotating (1)`): Bearing aspect of the reference point
- **color =** (`string`): The color name or HTML code to mark the new reference point
- **distance =** (`distance`): Distance from the 'relative' unit
- **highlighted =** (`True/False`): True if the reference point should be selected
- **latitude =** (`latitude`): The latitude of the new reference point
- **locked =** (`True/False`): True if the reference point is locked
- **longitude =** (`longitude`): The longitude of the new reference point
- **name =** (`string`): The name of the new reference point
- **bearing =** (`number (0-360)`): Bearing from the 'relative' unit
- **bearingtype =** (`bearingFixed (0) or Rotating (1)`): Bearing aspect of the reference point
- **color =** (`string`): The color name or HTML code to mark the new reference point
- **distance =** (`distance`): Distance from the 'relative' unit
- **highlighted =** (`True/False`): True if the reference point should be selected
- **latitude =** (`latitude`): The latitude of the new reference point
- **locked =** (`True/False`): True if the reference point is locked
- **longitude =** (`longitude`): The longitude of the new reference point
- **name =** (`string`): The name of the new reference point
- **relativeto =** (`string`) (required): The unit name/guid that all the RP(s) relate to, if required
- **relativeto_contact =** (`string`) (required): The contact name/guid that all the RP(s) relate to, if required
- **relativeto_rp =** (`string`) (required): The RP name/guid that all the RP(s) relate to, if required
- **side =** (`string`): The side the reference point is visible to

**Returns:** `ReferencePoint A reference point wrapper for the new reference point, or the last one in the area if supplied.`

---

### ScenEdit_AddZone()
This function creates a non-navigation or exclusion zone. The Reference Points are normally visible to the side. They can start out 'hidden' by adding 'hidden=1' to the table options.

**Signature:** `ScenEdit_AddZone (sideName, zoneType, table)`

**Parameters:**
- **table** (`table`):
- **sideName =** (`string`): The Side name/GUID. Custom environment zones are always added to the Nature side.
- **zoneType =** (`number0 = non-navigation, 1 = exclusion, 2 = custom environment, -925 = standard`): The type of zone to add
- **description =** (`string`): The Zone name
- **isactive =** (`True/False`): Is the zone active?
- **locked =** (`True/False`): Are Zone RPs locked?
- **hidden =** (`True/False`): Are Zone RPs hidden?
- **affects =** (`table {}list of core unit types ('SHIP', 'AIRCRAFT', etc) affected`): Zone applies to these core unit types
- **markAs =** (`posture`): Units entering the zone are treated as (posture towards them) [exclusion zone only]
- **relativeto =** (`string`) (required): The unit name/guid that all the RP(s) relate to, if required
- **area =** (`table`):
- **name =** (`string`): The name of the new reference point
- **latitude =** (`latitude`): The latitude of the new reference point
- **longitude =** (`longitude`): The longitude of the new reference point
- **highlighted =** (`True/False`): True if the reference point should be selected
- **locked =** (`True/False`): True if the reference point is locked
- **distance =** (`distance`): Distance from the 'relative' unit
- **bearing =** (`number (0-360)`): Bearing from the 'relative' unit
- **bearingtype =** (`bearingFixed (0) or Rotating (1)`): Bearing aspect of the reference point

**Returns:** `Zone The zone as a wrapper`

---

### ScenEdit_DeleteReferencePoint()
This function will delete a reference point. It will check the side's normal RPs, and then the Non_Nav and Exclusion Zones for a match. Note that there is no check to see if the RP is actively being used before removing.

**Signature:** `ScenEdit_DeleteReferencePoint (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/guid
- **name =** (`string`): The reference point name/guid to delete.

**Returns:** `True/FalseTrue if successful`

---

### ScenEdit_GetReferencePoint()
This function will return details for a specific reference point. The RP will be checked against normal side RPs and then against the non-navigation and exclusion zone RPs for a match.

**Signature:** `ScenEdit_GetReferencePoint ( table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): Side name/guid
- **name =** (`string`): The name/guid of the reference point

**Returns:** `ReferencePoint Reference point wrapper`

---

### ScenEdit_GetReferencePoints()
This function will return the details for a range of reference point. The RP will be checked against normal side RPs and then against the non-navigation and exclusion zone RPs for a match.

**Signature:** `ScenEdit_GetReferencePoints ( table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): Side name/guid
- **name =** (`string`): The name/guid of the reference point (for a single point)
- **area =** (`table`):
- **name =** (`string`): The name/guid of the reference point
- **string** (`The`): name/guid of the reference point

**Returns:** `table {} of multiple ReferencePoint Reference point wrappers`

---

### ScenEdit_RemoveZone()
This function removes a no-nav or exclusion zone. The RPs attached to the zone will also be removed as they are unique to the zone.

**Signature:** `ScenEdit_RemoveZone (sideName, zoneType, table)`

**Parameters:**
- **sideName** (`string`): The Side name/GUID that owes the zone. Custom environment zones always belong to the Nature side.
- **zoneType** (`number 0 = non-navigation, 1 = exclusion, 2 = custom environment, -925 = standard`): The Type of zone to remove
- **table** (`table`):
- **Description =** (`string`): The Zone GUID or Name or Description to identify it

**Returns:** `Zone A zone wrapper for the removed Zone`

---

### ScenEdit_SetReferencePoint()
This function Updates the values contained in the table. Values may be omitted if they are intended to remain unmodified. The 'area' parameter is useful for changing some common attribute, like locking or highlighting,in bulk. Don't include the 'area' parameter if only updating one RP.

**Signature:** `ScenEdit_SetReferencePoint (table)`

**Parameters:**
- **table** (`table`):
- **guid =** (`string`): The guid for the reference point
- **side =** (`string`): The side the reference point is visible to
- **name =** (`string`): The name of the reference point
- **newname =** (`string`): The new name of the reference point
- **latitude =** (`latitude`): The latitude of the reference point
- **longitude =** (`longitude`): The longitude of the reference point
- **highlighted =** (`True/False`): True if the point should be selected
- **locked =** (`True/False`): True if the point is locked
- **bearing =** (`number (0-360)`): Bearing from the 'relative' unit
- **bearingtype =** (`typeFixed (0) or Rotating (1)`): Type of bearing
- **relativeto =** (`string`) (required): The unit name/guid that all the RP(s) relate to, if required
- **relativeto_contact =** (`string`) (required): The contact name/guid that all the RP(s) relate to, if required
- **relativeto_rp =** (`string`) (required): The RP name/guid that all the RP(s) relate to, if required
- **clear =** (`True/False`): Remove the 'relative to' associated with the reference point(s)
- **area =** (`table`):
- **name =** (`string`): The name of the reference point
- **latitude =** (`latitude`): The latitude of the reference point
- **longitude =** (`longitude`): The longitude of the reference point
- **highlighted =** (`True/False`): True if the reference point should be selected
- **locked =** (`True/False`): True if the reference point is locked
- **distance =** (`distance`): Distance from the 'relative' unit
- **bearing =** (`number (0-360)`): Bearing from the 'relative' unit
- **bearingtype =** (`type Fixed (0) or Rotating (1)`): Bearing aspect of the reference point

**Returns:** `ReferencePointThe reference point object for the reference point or first one from the area list.`

---

### ScenEdit_SetZone()
This function updates a non-navigation or exclusion zone for a side. You only need to pass the parameters that need to be updated.

**Signature:** `ScenEdit_SetZone (sideName, zoneType, table)`

**Parameters:**
- **sideName** (`string`): Side name/GUID
- **zoneType** (`number 0 = non-navigation, 1 = exclusion, 2 = custom environment, -925 = standard`): The type of zone
- **table** (`table`):
- **description =** (`string`): The Zone name
- **isactive =** (`True/False`): Is the zone active?
- **locked =** (`True/False`): Are Zone RPs locked?
- **hidden =** (`True/False`): Are Zone RPs hidden?
- **affects =** (`table { } list of core unit types ('SHIP', 'AIRCRAFT', etc) affected`): Zone applies to these core unit types
- **markAs =** (`posture`): Units entering the zone are treated as (posture towards them) [exclusion zone only]
- **relativeto =** (`string`) (required): The unit name/guid that all the RP(s) relate to, if required
- **areaColor =** (`string`): The zone color to show as a HTML color code
- **rename =** (`string`): Description to change zone to
- **area =** (`table`):
- **name =** (`string`): The name of the new reference point
- **latitude =** (`latitude`): The latitude of the new reference point
- **longitude =** (`longitude`): The longitude of the new reference point
- **highlighted =** (`True/False`): True if the reference point should be selected
- **locked =** (`True/False`): True if the reference point is locked
- **distance =** (`distance`): Distance from the 'relative' unit
- **bearing =** (`number (0-360)`): Bearing from the 'relative' unit
- **bearingtype =** (`type Fixed (0) or Rotating (1)`): Bearing aspect of the reference point

---

### ScenEdit_TransformZone()
The function purpose is to convert a 'zone' from one type to another. The types of 'zone' as non-navigation, exclusion and standard. Once converted, some update may be required for any specifics related to the converted zone

**Signature:** `ScenEdit_TransformZone ( SideNameOrID, ZoneNameOrID, TargetType )`

**Parameters:**
- **SideNameOrID** (`string`): The side name/GUID containg the zone. Custom environment zones are always owned by the Nature side.
- **ZoneNameOrID** (`string`): The name/GUID of the zone
- **TargetType** (`string exclusion nonav standard customenvironment`): The type of zone to convert it to

---

### GetScenarioTitle()
This function returns the title of the currently loaded scenario.

**Signature:** `GetScenarioTitle ()`

**Parameters:**
- **None**

---

### ScenEdit_CurrentLocalTime()
This function returns the current scenario zulu time.

**Signature:** `ScenEdit_CurrentLocalTime ()`

**Parameters:**
- **None**

**Returns:** `Time The current time in-game as HH:MM:SS.`

---

### ScenEdit_CurrentTime()
This function returns the current scenario date/time. This can then be customised to show in various ways for the in-game messages

**Signature:** `ScenEdit_CurrentTime ()`

**Parameters:**
- **None**

**Returns:** `TimeStamp The UTC Unix timestamp of the current time in-game.`

---

### ScenEdit_EndScenario()
This function ends the current scenario and triggers any associated events.

**Signature:** `ScenEdit_EndScenario ()`

---

### ScenEdit_GetScenHasStarted()
This function indicates if the scenario has started?

**Signature:** `ScenEdit_GetScenHasStarted( )`

**Parameters:**
None

**Returns:** `True/False True if the scenario has started`

---

### ScenEdit_GetWeather()
This function Gets the current weather conditions.

**Signature:** `ScenEdit_GetWeather ()`

---

### ScenEdit_GetScore()
This function retrieves the current score on a side. 'PlayerSide' can be used for the side to access the current playing side.

**Signature:** `ScenEdit_GetScore( side )`

**Parameters:**
- **side** (`string`): The side name/guid

**Returns:** `number The side's score`

---

### ScenEdit_GetTimeOfDay()
This function retrieves the current time of day at a location The location can be an unit (guid or side/name) or a position (latitude,longitude). Only one pair is required to identify the location for the TimeOfDay.

**Signature:** `ScenEdit_GetTimeOfDay ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): Side name/guid
- **unitname =** (`string`): Unit name
- **guid =** (`string`): Unit guid
- **latitude =** (`string`): Unit guid
- **longitude =** (`string`): Unit guid

---

### ScenEdit_SetStartTime()
This function Sets the scenario start date/time. The default format of the date is MMDDYYYY. It can be changed by using the 'dateformat' parameter.

**Signature:** `ScenEdit_SetStartTime ( table )`

**Parameters:**
- **table** (`table`):

---

### ScenEdit_SetScore()
This function updates a given side's score.

**Signature:** `ScenEdit_SetScore (side, score, reason)`

**Parameters:**
- **side** (`string`): The name/GUID of the side
- **score** (`number`): The new score for the side
- **reason** (`string`): The reason for the score change

**Returns:** `numberThe new score for the side`

---

### ScenEdit_SetTime()
This function Sets the current scenario date/time, but allows the scenario start data to be updated as well. Note the default format ('MM.DD.YYYY') for the public release, differs from the default mode ('DD.MM.YYYY') in the professional release. If a scenario wants to be used between both releases, the new DATEFORMAT parameter should used to define the date passed.

**Signature:** `ScenEdit_SetTime ( table )`

**Parameters:**
- **table** (`table`):
- **dateformat =** (`string`): Formats are: 'DDMMYYYY' or 'MMDDYYYY' or 'YYYYMMDD' Note that they need to be uppercase . The default format for Public versions is 'MMDDYYYY', while the Professional versions use 'DDMMYYYY' if this parameter is not supplied.
- **date =** (`string`): Scenario current date as per the date format 'DD.MM.YYYY' or 'MM.DD.YYYY' or 'YYYY.MM.DD' The delimiter '.' can also be a ':'
- **time =** (`string`): Scenario current time as 'HH:MM:SS' or 'HH.MM.SS'
- **StartDate =** (`string`): Scenario start date as 'DD:MM:YYYY' or 'DD.MM.YYYY'.
- **StartTime =** (`string`): Sceanrio start time as 'HH:MM:SS' or 'HH.MM.SS'
- **Duration =** (`string`): Length of scenario as 'days:hours:minutes'

---

### ScenEdit_SetWeather()
This function Sets the current weather conditions. It takes four numbers that describe the desired weather conditions.These conditions are applied globally.

**Signature:** `ScenEdit_SetWeather (temperature, rainfall, undercloud, seastate)`

**Parameters:**
- **temperature** (`number`): The current baseline temperature (in deg C). Varies by latitude.
- **rainfall** (`number`): The rainfall rate, 0-50.
- **undercloud** (`number`): The amount of sky that is covered in cloud, 0.0-1.0
- **seastate** (`number`): The current sea state 0-9.

---

### VP_GetContact()
This function returns details about a contact unit

**Signature:** `VP_GetContact ( table )`

**Parameters:**
- **table** (`table`):
- **guid =** (`string`): The GUID of the contact

---

### VP_GetScenario()
This function returns the current scenario information.

**Signature:** `VP_GetScenario ()`

**Parameters:**
- **None**

---

### VP_GetSide()
This function returns the Side object from the perspective of the player.

**Signature:** `VP_GetSide ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The name of the side
- **guid =** (`string`): The GUID of the side

---

### VP_GetSides()
This function returns a list of the sides in the scenario.

**Signature:** `VP_GetSides ()`

**Parameters:**
- **None**

---

### VP_GetUnit()
This function returns information about an active unit or a contact's actual unit.

**Signature:** `VP_GetUnit ( table )`

**Parameters:**
- **table** (`table`):
- **unitname =** (`string`): The name of unit or contact
- **guid =** (`string`): The GUID of the unit or contact

---

### ScenEdit_AddReloadsToUnit()
This function adds, removes or fills out weapon reloads on a local mount of an unit, rather than be applied to the unit's magazine. You can specify a particular `mount` by the GUID, or omit it and the function will try to apply the request to any `available` mounts with the `weapon`.

**Signature:** `ScenEdit_AddReloadsToUnit (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **wpn_dbid =** (`number`) (required): The weapon database ID to be updated **MANDATORY**
- **mount_guid =** (`string`): The mount GUID on the unit to be updated
- **number =** (`number`): Number to be added or removed
- **remove =** (`True/False`): If true, this will debuct the number of weapons from the unit/mount
- **fillout =** (`True/False`): If true, this will fill out the weapon record to its maximum. The 'number' doesn't apply.
- **addascell =** (`True/False`): Default true. If false, add only one weapon to a cell

**Returns:** `number The number of items added or removed`

---

### SE_GetZone()
Returns a zone object based on side, name and type.
(Bron: WhatsNew.pdf March 2026)

**Signature:** `SE_GetZone (sideName, zoneName, zoneType)`

**Parameters:**
- **sideName** (`string`): The name of the side.
- **zoneName** (`string`): The name of the zone.
- **zoneType** (`number`): The type of zone.

---

### SetScenarioMessageLogPath()
Sets a custom path for the current scenario's message log.
(Bron: WhatsNew.pdf March 2026)

**Signature:** `SetScenarioMessageLogPath (fullpath)`

**Parameters:**
- **fullpath** (`string`): The full path to the log file.

---

### ScenEdit_AddUnit()
This function adds a new unit to a side based on the supplied table. As the function ScenEdit_SetUnit() is called at the end of this function, any options not listed below will be passed into the next function. There should be no need to call ScenEdit_SetUnit() seperately.

**Signature:** `ScenEdit_AddUnit (table)`

**Parameters:**
- **table** (`table`):
- **type =** (`UnitType`) (required): Unit type — use **`'Air'`**, **`'Ship'`**, **`'Sub'`** (not `'Submarine'`), **`'Facility'`**, etc.
- **unitname =** (`string`) (required): The name of the unit
- **side =** (`string`) (required): The side name/GUID to add the unit to
- **dbid =** (`number`) (required): The database id of the unit
- **base =** (`string`): Unit base name/GUID where the unit will be 'hosted' (applies to types AIR, SHIP, SUB)
- **latitude =** (`Latitude`) (optional): Not required if a base is defined as unit adopts that location
- **longitude =** (`Longitude`) (optional): Not required if a base is defined as adopts that location
- **altitude =** (`Altitude`) (required): Unit altitude (AIR). When `base` is set for AIR, use `altitude = '0'` (string) to avoid .NET wrapper errors. For SHIP, SUB, FACILITY use `altitude = 0` (number).
- **loadoutid =** (`number`): Aircraft database loadout id (applies to type AIR)
- **orbit =** (`number`): Orbit index (applies to type SATELLITE)
- **guid =** (`string`) (optional): Optional custom GUID to override the auto generated one

**Returns:** `Unit A wrapper defining the added unit. This will be nil if the function failed to add the unit.`

---

### ScenEdit_AddWeaponToUnitMagazine()
This function adds weapons to a unit magazine. Unlike ScenEdit_AddReloadsToUnit() this is adjusting the unit's magazine rather than the local mount. For example, adding more AIM-120 missiles to the carrier magazine for loadout refreshing. You can specify a particular `magazine` by the GUID, or omit it and the function will try to apply the request to any `available` magazines with the `weapon`.

**Signature:** `ScenEdit_AddWeaponToUnitMagazine (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **wpn_dbid =** (`number`) (required): The weapon database ID to be updated **MANDATORY**
- **mag_guid =** (`string`): The magazine GUID on the unit to be updated
- **maxcap =** (`number`): Use this as an override for the magazine's current maximum capacity for the weapon
- **new =** (`True/False`): If true, allows the weapon to be treated as a new item in the magazine if it doesn't exist
- **number =** (`number`): Number to be added or removed
- **remove =** (`True/False`): If true, this will debuct the number of weapons from the unit/mount
- **fillout =** (`True/False`): If true, this will fill out the weapon record to its maximum. The parameters 'number' and 'new' don't apply in this case.

**Returns:** `number Number of items added to the magazine`

---

### ScenEdit_DeleteUnit()
This function will delete a unit( and any attached units) and no event is triggered.

**Signature:** `ScenEdit_DeleteUnit (table, include)`

**Parameters:**
- **include** (`True/False`): If a group, delete the attached units
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The unit name/guid to delete.

**Returns:** `True/FalseTrue if successful`

---

### ScenEdit_GetDoctrine()
This function looks up the doctrine of the object selected, and throws an exception if the unit does not exist. There are various levels that affect the doctrine used; mainly SIDE, MISSION, GROUP, UNIT. Units will inherit from a higher level if there is no specific setting at the currect level. Passing a unit name/guid will indicate a UNIT/GROUP doctrine, while passing a mission name/guid will indicate a MISSION doctrine and just a side name/guid a SIDE doctrine. One parameter of side, mission, unitname or guid is mandatory. Only the non-inherited values are returned unless the option ACTUAL is used.

**Signature:** `ScenEdit_GetDoctrine ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/guid
- **unitname =** (`string`): The unit name/guid
- **guid =** (`string`): The unit name/guid
- **mission =** (`string`): The mission name/guid GUID
- **escort =** (`True/False`): If a strike mission, use the Escort mission doctrine
- **escort =** (`True/False`): If a strike mission, use the Escort mission doctrine
- **actual =** (`True/False`): Show the actual doctrine setting rather than just that it is 'inherit'
- **player_editable =** (`True/False`): Make the settings available to player to change

**Returns:** `Table {} A Table of doctrine values similar to the wrapper Doctrine or nil if an error.`

---

### ScenEdit_GetDoctrineWRA()
This function retrieves the WRA doctrine based on the target type and weapon. There are various levels that affect the doctrine used; mainly SIDE, MISSION, GROUP, UNIT. Units will inherit from a higher level if there is no specific setting at the currect level. Passing a unit name/guid will indicate a UNIT/GROUP doctrine, while passing a mission name/guid will indicate a MISSION doctrine and just a side name/guid a SIDE doctrine. One parameter of side, mission, unitname or guid is mandatory. One parameter for contact_id or target_type is mandatory If no weapon_id is supplied but just the target_type, then a WRA table (WRA_#) is returned for each weapon that can engage that target_type

**Signature:** `ScenEdit_GetDoctrineWRA ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/guid
- **mission =** (`string`): The mission name/guid
- **unitname =** (`string`): The unit name/guid
- **guid =** (`string`): The unit name/guid
- **weapon_id =** (`string`): The weapon database id
- **contact_id =** (`string`): A contact guid (infers the target_type)
- **target_type =** (`TargetType`): The target type
- **full_wra =** (`True/False`): Show the full WRA setting rather than just if there is a match

**Returns:** `Table {} A Table of WRA doctrine values similar to the wrapper DoctrineWRA, or nil if none. An empty table {} may be returned if there are no matching entries especially if doning a full WRA.`

---

### ScenEdit_GetFormation()
This function gets the properties of a groups formation.

**Signature:** `ScenEdit_GetFormation (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name of the unit
- **name =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit

---

### ScenEdit_GetLoadout()
This function retrieves the loadout details of an aircraft. For the aircraft current loadout, use a loadoutid =0 or omit it to get the current loadout status (e.g. number of weapons left) UnitX can be used as the unitname> if in a triggered event

**Signature:** `ScenEdit_GetLoadout ( loadoutinfo )`

**Parameters:**
- **table** (`table`):
- **unitname =** (`string`): The name/GUID of the unit
- **LoadoutID =** (`number`): The loadout database id; 0 = use the current loadout

**Returns:** `LoadoutLoadout wrapper`

---

### ScenEdit_GetUnit()
This function gets the properties of the Unit.

**Signature:** `ScenEdit_GetUnit (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit

---

### ScenEdit_FillMagsForLoadout()
This function adds to a unit's magazine(s) the aircraft stores in the loadout.

**Signature:** `ScenEdit_FillMagsForLoadout (table, loadoutid, quantity)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/guid of the unit
- **unitname =** (`string`): The unit name/guid with the magazine
- **guid =** (`string`): The unit name/guid with the magazine
- **loadoutid** (`number`): The database id of the loadout
- **quantity** (`number`): The number of 'packs' in the loadout to add

**Returns:** `Table {} of string A table of success/failure messages from adding the stores`

---

### ScenEdit_KillUnit()
This function kills an unit....and triggers any events.

**Signature:** `ScenEdit_KillUnit (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit

**Returns:** `True True if successful, or nil otherwise`

---

### ScenEdit_MergeUnits()
Merge the selected units in to the first one on the list

**Signature:** `Function ScenEdit_MergeUnits( )`

**Parameters:**
- **List** (`the`): parameters as in the Syntax line

---

### ScenEdit_RefuelUnit()
This function will make the unit attempt to refuel. The unit should follow it's AAR configuration.You can force it use a specific tanker or ones from a set of missions.

**Signature:** `ScenEdit_RefuelUnit ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **tanker =** (`string`): A specific tanker defined by its name (side is assumed to be the same as unit) or GUID.
- **missions =** (`table`): A table of mission names or mission GUIDs.

**Returns:** `string If successful, then it returns an empty string. Otherwise, a message showing why it failed to refuel is returned`

---

### ScenEdit_SetDoctrine()
This function Sets the doctrine of the designated object It modifies the doctrine of that object at the Side,Unit/Group or Mission level The doctrine level to be affected is determined by the parameters passed:

**Signature:** `ScenEdit_SetDoctrine (table, doctrine)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **mission =** (`string`): The mission guid/name
- **escort =** (`True/False`): If a mission, apply changes to Escort of Strike mission
- **doctrine** (`table`): {} Refer to the Doctrine object Doctrine for the possible values Only the items to be updated need to be added as 'doctrine_item = value'. The value of 'inherit' will reset that doctrine_item to inherit from its parent doctrine, otherwise the value is validated against its acceptable values.

**Returns:** `DoctrineReturns the updated doctrine object`

---

### ScenEdit_SetDoctrineWRA()
This function sets the WRA doctrine of the designated object against a specific weapon and target type. The values below can be used in the doctrine settings: 'inherit' = reverts to the parent level setting 'system' = reverts to the database level setting (does not apply to 'firing_range') 'max' = use the appropriate maximum setting 'none' = not to be used For the firing range doctrine, there are a few specicial values '25ofmax' = use 25% of the maximum range '50ofmax' = use 50% of the maximum range '75ofmax' = use 75% of the maximum range

**Signature:** `ScenEdit_SetDoctrineWRA (table, doctrine)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **mission =** (`string`): The mission guid/name
- **escort =** (`True/False`): If a mission, apply changes to Escort WRA of Strike mission
- **weapon_id =** (`string`): The database id of the desired weapon
- **contact_id =** (`string`): The contact GUID to determine target type (mutually exclusive with target_type)
- **target_type =** (`string`): The target type (mutually exclusive with contact_id)
- **doctrine** (`table`):
- **string** (`Number`): of Weapons per salvo ('Max','None' or a number)
- **string** (`Number`): of Shooters per salvo ('Max','None' or a number)
- **string** (`Firing`): range ('Max','None' or a number)
- **string** (`Self-defence`): range ('Max','None' or a number)

**Returns:** `DoctrineWRA Returns the WRA doctrine of the selected object`

---

### ScenEdit_SetEMCON()
This function Sets the EMCON Doctrine of the selected object. Select the object by specifying the type and the object's name. NOTE: To force a unit to immediately adopt the new EMCON Doctrine, use the Unit wrapper to set 'obeyEMCON' to true. Type is the type of object to set the EMCON on. It can be one of 4 values:

**Signature:** `ScenEdit_SetEMCON (type, name, emcon)`

**Parameters:**
- **type** (`string`): The type of the thing to set the EMCON on.
- **name** (`string`): The name or GUID of the object to select.
- **emcon** (`string`): The new EMCON for the object.

**Returns:** `?????`

---

### ScenEdit_SetLoadout()
This function Sets the loadout for a aircraft unit

**Signature:** `ScenEdit_SetLoadout (table)`

**Parameters:**
- **table** (`table`):
- **unitname =** (`string`): Unit description/name or GUID to update. Can use 'UnitX' here if in an Event Action
- **LoadoutID =** (`number`): The ID of the new loadout; 0 = use the current loadout
- **TimeToReady_Minutes =** (`number`) (optional): How many minutes until the loadout is ready (default = database loadout time) (_optional_)
- **IgnoreMagazines =** (`True/False`) (optional): If the new loadout should rely on the magazines having the right weapons ready (default = false) (_optional_)
- **ExcludeOptionalWeapons =** (`True/False`) (optional): Exclude optional weapons from loadout (default = false) (_optional_)
- **Wpn_DBID =** (`number`) (required): Weapon DB number - required if WPN_GUID is not supplied
- **Wpn_GUID =** (`string`) (optional): Actual weapon to update - DBID is not required as this take precedence (_optional_)
- **Number =** (`number`): Number to change current weapon load by (sign ignored)
- **Remove =** (`True/False`): Deduct 'number' rather than add

**Returns:** `booleanTrue`

---

### ScenEdit_SetUnit()
This function Sets the properties of an existing unit

**Signature:** `ScenEdit_SetUnit ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **newname =** (`string`): Rename the unit
- **group =** (`string`): Assign to a group name/guid
- **mission =** (`string`): Assign to a mission name/guid
- **speed =** (`number`): Set unit speed (mutally exclusive to 'throttle')
- **throttle =** (`string`): Set unit throttle (mutally exclusive to 'speed')
- **forceSpeed =** (`True/False`): Force speed (use an external throttle setting???)
- **launch =** (`True/False`): Launch unit from base
- **rtb =** (`True/False`): Return unit to base
- **jettison =** (`value "HEAVYONLY" = drop tanks, Air2Ground weapons "WEAPONSONLY" = AG and Air2Air weapons "ALLEXTERNAL" = drop tanks, all AG/AA, pods "ALL" = all external and internal loads "STORE_dbid = specific weapon DBID"`): Jettison stores
- **refuel =** (`True/False`): Unit attempts to refuel as per ROE
- **unassign =** (`True/False`): Unassign unit
- **moveto =** (`True/False`): Moves to alt/depth rather than jump to it
- **altitude =** (`number`): Altitude to set
- **depth =** (`number`): Depth to set
- **heading =** (`number`): Set to immediate heading
- **desiredHeading =** (`number`): Set to desired heading so unit turns towards it
- **longitude =** (`number`): Unit's location - longitude
- **latitude =** (`number`): Unit's location - latitude
- **autoDetectable =** (`True/False`): Unit is autodetectable
- **outOfComms =** (`True/False`): Unit is out of communications
- **holdPosition =** (`True/False`): Unit holds position
- **holdFire =** (`True/False`): Unit holds fire
- **proficiency =** (`string`): Unit proficiency
- **manualthrottle =** (`value FullStop = 0 Loiter = 1 Cruise = 2 Full = 3 Flank = 4`): Manaual setting
- **manualspeed =** (`string`): Manaual setting
- **manualaltitude =** (`string`): Manaual setting
- **fuel =** (`table`):
- **string** (`fuel`): type
- **number** (`quantity`)
- **base =** (`string`): Base name/guid to assign unit to
- **sprintDrift =** (`True/False`): Unit uses sprint and drift (ship, submarine)
- **avoidcavitation =** (`True/False`): Unit avoids cavitation (ship, submarine)
- **csar =** (`True/False`): The unit can be assigned as a target for SAR
- **timetoready_minutes =** (`number`): Number of minutes to ready (ship, submarine, aircraft)
- **course =** (`table`):
- **latitude =** (`latitude`): The latitude of the new reference point
- **longitude =** (`longitude`): The longitude of the new reference point

**Practical note (airborne at scenario start):** Setting `latitude`/`longitude`/`altitude` on aircraft that were spawned **with** `base=` does not reliably place them in flight — they stay on the carrier/ramp. For ISR/AEW already on-orbit at H-hour: spawn the first sortie with `ScenEdit_AddUnit` **without** `base` at orbit coordinates, or use `launch=true` (often via a Play-time event) together with position/throttle. See `AGENTS.md` §2 and `scenario_bootstrap_reference.md` recipe *Support already on-orbit at scenario start*.

---

### ScenEdit_SetUnitDamage()
This function Sets the unit damage for components

**Signature:** `ScenEdit_SetUnitDamage ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **fires =** (`Fire_level?`): Fire level
- **flood =** (`Flood_level?`): Flooding level
- **dp =** (`number`): Damage points left
- **components =** (`table`):
- **value** (`'rudder',`): 'cargo', 'cic', 'pressurehull' Standard component to damage
- **string** (`Damage`): level ('none', 'destroyed', or damage_severity_setting)
- **string** (`Specific`): component GUID to damage
- **string** (`Damage`): level ('none', 'destroyed', or damage_severity_setting)
- 'type' Fixed value to indicate a random component damage
- **type** (`'sensor',`): etc Random component type to damage
- **string** (`Damage`): level ('none', 'destroyed', or damage_severity_setting)

---

### ScenEdit_SplitUnit()
Split a unit in to units with each component mount

**Signature:** `Function ScenEdit_SplitUnit ( table )`

**Parameters:**
- **List** (`the`): parameters as in the Syntax line

---

### ScenEdit_TransferCargo()
This function Transfers a cargo list from a 'parent' to a 'child' unit

**Signature:** `ScenEdit_TransferCargo (fromUnit, toUnit, cargoList)`

**Parameters:**
- **fromUnit** (`string`): The unit name/guid with the cargo
- **toUnit** (`string`): The unit name/guid get the cargo
- **cargoList** (`table`):
- **string** (`Cargo`): GUID - treated as one unit to act on
- { } of number Cargo database id (DBID) and is treated as one unit to act on
- { } of Note the order of 'number to affect' and 'DBID'
- **number** (`Number`): to act on
- **number** (`Cargo`): DBID to affect

---

### ScenEdit_UnloadCargo()
This function Unloads all cargo from a unit. This is equivalent to the 'Unload cargo' unit order. The 'cargoList' parameter to this function has been deprecated but has been maintained for backward compatibility.

**Signature:** `ScenEdit_UnloadCargo (fromUnit) ScenEdit_UnloadCargo(fromUnit, cargoList)`

**Parameters:**
- **fromUnit** (`string`): The unit name/guid with cargo
- **cargoList** (`table`):
- **string** (`Cargo`): GUID - treated as one unit to act on
- { } of number Cargo database id (DBID) and is treated as one unit to act on
- { } of Note the order of 'number to affect' and 'DBID'
- **number** (`Number`): to act on
- **number** (`Cargo`): DBID to affect

---

### ScenEdit_UpdateUnit()
This function Updates the components of an unit. As this function also calls ScenEdit_SetUnit(), additional parameters for that function may also be passed to this function.

**Signature:** `ScenEdit_UpdateUnit ( table )`

**Parameters:**
- **table** (`table`):
- **guid =** (`string`): The GUID of the unit
- **mode =** (`value 'add_sensor', 'remove_sensor', 'update_sensor_arc', 'add_mount', 'remove_mount', 'update_mount_arc', 'add_weapon', 'remove_weapon', 'add_comms', 'remove_comms', 'add_fuel', 'remove_fuel', 'add_magazine', 'add_magazine_only', 'remove_magazine', 'add_dock_facility', 'remove_dock_facility', 'add_air_facility', 'remove_air_facility', 'delta'`): The action mode to perform
- **dbid =** (`number`): Component DBID to affect
- **file =** (`string`): The filename to upload update from (Applies to 'mode = delta' only)
- **arc_detect =** (`table`):
- **arc Arc code string (applies to 'mode** (`...sensor...')`)
- **arc_track =** (`table`):
- **arc Arc code string (applies to 'mode** (`...sensor...')`)
- **arc_mount =** (`table`):
- **arc Arc code string (applies to 'mode** (`...mount...')`)
- **sensorid =** (`string`): A specific sensor GUID to operate on (not applicable to adding sensor)
- **mountid =** (`string`): A specific mount GUID to operate on (not applicable to adding mount)
- **weaponid =** (`string`): A specific weapon GUID to operate on (not applicable to adding weapon)
- **commsid =** (`string`): A specific communication GUID to operate on (not applicable to adding comms)
- **magid =** (`string`): A specific magazine GUID to operate on (not applicable to adding magazine)
- **airfacid =** (`string`): A specific air facility GUID to operate on (not applicable to adding air facility)
- **dockfacid =** (`string`): A specific docking facility GUID to operate on (not applicable to adding docking facility)
- **fuel =** (`table`):
- **string** (`fuel`): type
- **number** (`quantity`)

---

### ScenEdit_UpdateUnitCargo()
This function Updates the cargo space on a unit. By default, this treats the cargo type as 'mount' as per the original cargo V1 specifications. As this function also calls ScenEdit_SetUnit(), additional parameters for that function may also be passed to this function.

**Signature:** `ScenEdit_UpdateUnitCargo ( table )`

**Parameters:**
- **table** (`table`):
- **guid =** (`string`): The GUID of the unit
- **mode =** (`value 'add_cargo', 'remove_cargo'`): The action mode to perform
- **cargo =** (`table`):
- **string** (`Unit/Container`): GUID - the specific unit/container to remove from cargo. This is not supported for ADD_CARGO
- { } of number Mount database id (DBID) and is treated as one mount to act on
- { } of Note the order of 'number to affect' and 'DBID'
- **number** (`Number`): to act on
- **number** (`Mount`): DBID to affect
- { } of
- **number** (`Number`): to act on
- **number** (`Unit/Container`): DBID to affect
- **value '1** (`Mount',`): '2 = Ground', '3 = Facility', '4 = Container' Type of cargo that DBID refers to

---

### ScenEdit_ClearAllSideUnitsEmconConfigs()
The function's purpose is clear all the unit Intermittent Emission configurations on a Side

**Signature:** `ScenEdit_ClearAllSideUnitsEmconConfigs ( SideNameOrID )`

**Parameters:**
- **SideNameOrID** (`string`): The name or GUID of the side to clear.

---

### ScenEdit_ClearUnitEmconConfigs()
The function's purpose is to clear any Intermittent Emission configuration for the unit.

**Signature:** `ScenEdit_ClearUnitEmconConfigs( AUNameOrID )`

**Parameters:**
- **AUNameOrID** (`string`): The name or GUID of the unit. As no Side is supplied, the unit name would need to be unique across the scenario.

---

### ScenEdit_DuplicateEmconConfigToSide()
The function's purpose is to duplicate an Alert setting from one side to another side.

**Signature:** `ScenEdit_DuplicateEmconConfigToSide ( PresetAlertID, SourceSideNameOrID, TargetSideNameOrID )`

**Parameters:**
- **SourceSideNameOrID** (`string`): The name or GUID of the side to copy Alert configuration from.
- **TargetSideNameOrID** (`string`): The name or GUID of the side to copy Alert configuration to.
- **PresetAlertID** (`value "GREEN" "BLUE" "YELLOW" "ORANGE" "RED" "CUSTOM" "ALL"`): The Alert level

---

### ScenEdit_DuplicateEmconConfigToUnit()
The function's purpose is to copy a unit's Alert configuration to another unit.

**Signature:** `ScenEdit_DuplicateEmconConfigToUnit ( PresetAlertID, SourceAUNameOrID, TargetAUNameOrID )`

**Parameters:**
- **SourceAUNameOrID** (`string`): The name or GUID of the unit to copy Alert configuration from. As no Side is supplied, the unit name would need to be unique across the scenario.
- **TargetAUNameOrID** (`string`): The name or GUID of the unit to copy Alert configuration to. As no Side is supplied, the unit name would need to be unique across the scenario.
- **PresetAlertID** (`value "GREEN" "BLUE" "YELLOW" "ORANGE" "RED" "CUSTOM" "ALL"`): The Alert level

---

### ScenEdit_GetUnitIntermittentEmissionConfig()
The function's purpose is to recall the configuation of the unit at the specified Alert.

**Signature:** `ScenEdit_GetUnitIntermittentEmissionConfig ( AUNameOrID,PresetAlertID )`

**Parameters:**
- **AUNameOrID** (`string`): The name or GUID of the unit. As no Side is supplied, the unit name would need to be unique across the scenario.
- **PresetAlertID** (`value "GREEN" "BLUE" "YELLOW" "ORANGE" "RED" "CUSTOM" "ALL"`): The Alert level

---

### ScenEdit_SetSideEmconAlertness()
The function's purpose is to set the Alert level for the side. This is used to determine which Alert level a unit will use with Intermittent Emissions.

**Signature:** `ScenEdit_SetSideEmconAlertness ( SideNameOrID, PresetAlertID )`

**Parameters:**
- True/False True if successful

---

### ScenEdit_SetUnitIntermittentEmissionConfig()
The function's purpose is to configure the specified Alert Level for Intermittent Emissions. There are several Alert levels availbale under the Intermittent Emissions view, and each one can have a different configuration.

**Signature:** `ScenEdit_SetUnitIntermittentEmissionConfig ( AUNameOrID,PresetAlertID,ConfigurationTable )`

**Parameters:**
- **AUNameOrID** (`string`): The name or GUID of the unit. As no Side is supplied, the unit name would need to be unique across the scenario.
- **PresetAlertID** (`value "GREEN" "BLUE" "YELLOW" "ORANGE" "RED" "CUSTOM" "ALL"`): The Alert level
- **ConfigurationTable** (`table`):
- **UseEmissionInterval =** (`number`): Use 0 to turn off or 1 to turn on the Intermittent Emission
- **EmissionDuration =** (`number`): Emission duration in seconds
- **EmissionInterval =** (`number`): Emission interval in seconds
- **EmissionIntervalVariation =** (`number`): Emission variation in seconds
- **SleepModeDelay =** (`number`): Time to sleep in seconds
- **FollowWRAforWakeBehavior =** (`number`): Use 0 to turn off or 1 to turn on to follow WRA behavior (UI ???)
- **WakeWhenDetectingThreat =** (`number`): Use 0 to turn off or 1 to turn on wake up on detecting threat
- **WakeID_UNKNOWN =** (`number`): Use 0 to turn off or 1 to turn on wake if unknown on detection
- **WwkeID_PRECISEID =** (`number`): Use 0 to turn off or 1 to turn on if precice ID
- **WakeID_KNWONTYPE =** (`number`): Use 0 to turn off or 1 to turn on if known type
- **WakeIDKNOWNDOMAIN =** (`number`): Use 0 to turn off or 1 to turn on if known domain
- **WakeIDKNOWNCLASS =** (`number`): Use 0 to turn off or 1 to turn on if known class
- **WakeStance_FRIENDLY =** (`number`): Use 0 to turn off or 1 to turn on if friendly
- **WakeStance_HOSTILE =** (`number`): Use 0 to turn off or 1 to turn on if hostile
- **WakeStance_NEUTRAL =** (`number`): Use 0 to turn off or 1 to turn on if neutral
- **WakeStance_UNFRIENDLY =** (`number`): Use 0 to turn off or 1 to turn on if unfriendly
- **WakeStance_UNKNOWN =** (`number`): Use 0 to turn off or 1 to turn on if unknown stance

---

### ScenEdit_SwitchUnitIntermittentEmission()
The function's purpose is to turn off/on the Intermittent Emission for the specified Alert Level

**Signature:** `ScenEdit_SwitchUnitIntermittentEmission( AUNameOrID,PresetAlertID,Switch )`

**Parameters:**
- **AUNameOrID** (`string`): The name or GUID of the unit. As no Side is supplied, the unit name would need to be unique across the scenario.
- **PresetAlertID** (`value "GREEN" "BLUE" "YELLOW" "ORANGE" "RED" "CUSTOM" "ALL"`): The Alert level
- **Switch** (`number`): Use 0 to turn off the Emission interval, 1 to turn on the Emission interval (USEEMISSIONINTERVAL)

---

### ScenEdit_AttackContact()
This function causes an attack on a contact as an auto-target or manual target, with weapon allocation. For a BOL attack, use "BOL" as the contactId. Note: The function will use the weapon from the aircraft loadout if applicable when no mount is supplied. If no 'mount' is supplied, the first available one with the 'weapon' will be used.

**Signature:** `ScenEdit_AttackContact (attackerID, contactId, options)`

**Parameters:**
- **attackerID** (`string`): The attacking unit name/guid
- **contactId** (`string`): The contact being attacked as a name/guid (GUID is better as the name can change as its classification changes)
- **options** (`table`):
- **mode =** (`TargetingMode0 = AutoTargeted, 1 = ManualWeaponAlloc, 2 = ManualTargeted`): The attack behaviour. 'ManualWeaponAlloc' requires supplying the weapon information to fire with.
- **mount =** (`number`): The mount dbid to fire from [Applies to manual weapon launch ]
- **weapon =** (`number`): The weapon dbid on the mount to fire [Applies to manual weapon launch ]
- **qty =** (`number`): The number of weapons to fire in this salvo [Applies to manual weapon launch ]
- **latitude =** (`latitude`): The latitude of the aimpoint
- **longitude =** (`longitude`): The longitude of the aimpoint
- **course =** (`table`):
- **latitude =** (`latitude`): The latitude of the waypoint
- **longitude =** (`longitude`): The longitude of the waypoint

**Returns:** `True/False True if attack successfully assigned`

---

### ScenEdit_GetContact()
This function retrieves a contact details This function is mostly similar toScenEdit_GetUnit except that it references contacts rather than units on a side. Using a contact name can cause confusion in what contact details would be returned as the name can change over time. Use ScenEdit_GetContacts() to get the side's contacts and use the GUID of the desired contact from there.

**Signature:** `ScenEdit_GetContact (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side to find the the contact on; the contact owner
- **unitname =** (`string`): The name of the contact
- **guid =** (`string`): The GUID of the contact

**Returns:** `Contact A contact wrapper if found or nil otherwise.`

---

### ScenEdit_GetContacts()
This function is similar to ScenEdit_GetContact() but it returns a table of contacts on the side

**Signature:** `ScenEdit_GetContacts (side)`

**Parameters:**
- **side** (`string`): The side name/guid.

**Returns:** `Table {} of Contact A Table of contact wrappers for the side or nil if no side found.`

---

### Command_SaveScen()
This function creates an instant save file. This could be triggered to be run at specific times after certain events as a checkpoint for recovery or an AAR,

**Signature:** `Command_SaveScen( saveFile )`

**Parameters:**
- **saveFile** (`string`): The full path to the location to create the save file.

---

### Exporter_SetSetting()
The function updates some of the settings used by the 'exporting' functions within Command. ThIs is mainly used by the Professional versions, with the 'Tacview' category being available in the Public version. The settings are stored in the configuration file 'Config\EventExport.ini'. These settings should not be changed unless you have some knowledge of what they do.

**Signature:** `Exporter_SetSetting(Category, Setting, Value)`

**Parameters:**
- **Category** (`string`): The type of the 'exporter'
- **Setting** (`string`): The parameter that can be changed
- **Value** (`string`): The value of the parameter

---

### GetBuildNumber()
This function returns the build number of the current game executable. This is useful if you know that a certain function is not available or has changed from a certain build so the Lua scripts can be made flexible to handle the change. For example, if the parameters to a certain function changed from a certain build number, then the script could check the executable build number, and call the function with the old parameters if the executable is before that build, and use new one parameters if after that build.

**Signature:** `GetBuildNumber ()`

**Parameters:**
- **None**

---

### ScenEdit_ClearKeyValue()
This function removes a key (and its value) from the persistent keystore. To clear the full keystore, use "" as the 'key'.

**Signature:** `ScenEdit_ClearKeyValue (key, forCampaign)`

**Parameters:**
- **key** (`string`): The key to clear or empty for all
- **forCampaign** (`True/False`) (optional): Use key store for passing data to next scenario in a campaign. [Experimental] [Optional, default = false]

**Returns:** `True/FalseTrue if Successful`

---

### ScenEdit_CreateBarkNotification_Geo()
The function's purpose is to show a 'bark' at a specific location. Barks are short text notifications that can be set to appear, briefly, anywhere on the map.

**Signature:** `ScenEdit_CreateBarkNotification_Geo (longitude, latitude, text, R, G, B [, moveUpward, fade, lifeTime, fontSize ] )`

**Parameters:**
- **longitude** (`longitude`):
- **latitude** (`latitude`):
- **text** (`string`): Text to show
- **R** (`number`): The 'Red' component of the color (0-255) to show the text in
- **G** (`number`): The 'Green' component of the color (0-255)
- **B** (`number`): The 'Blue' component of the color (0-255)
- **moveUpward** (`True/False`) (optional): [Optional] Default is True. This will move the text upwards
- **fade** (`True/False`) (optional): [Optional] Default is True. This controls the fading out of the text
- **lifeTime** (`number`) (optional): [Optional] Default is 1 second. This controls how long the text stays visible
- **fontSize** (`number`) (optional): [Optional] Default is 18. This controls the fonst size of the text

---

### ScenEdit_CreateBarkNotification_Geo_Bulk()
The function's purpose is to show a 'bark' at a specific location. The notifications are shown in sequence, one after another. Barks are short text notifications that can be set to appear, briefly, anywhere on the map.

**Signature:** `ScenEdit_CreateBarkNotification_Geo_Bulk (longitude, latitude, text, R, G, B [, moveUpward, fade, lifeTime, fontSize ] )`

**Parameters:**
- **longitude** (`longitude`):
- **latitude** (`latitude`):
- **text** (`table`):
- **string** (`Text`): to show
- **R** (`number`): The 'Red' component of the color (0-255) to show the text in
- **G** (`number`): The 'Green' component of the color (0-255)
- **B** (`number`): The 'Blue' component of the color (0-255)
- **moveUpward** (`True/False`) (optional): [Optional] Default is True. This will move the text upwards
- **fade** (`True/False`) (optional): [Optional] Default is True. This controls the fading out of the text
- **lifeTime** (`number`) (optional): [Optional] Default is 1 second. This controls how long the text stays visible
- **fontSize** (`number`) (optional): [Optional] Default is 18. This controls the fonst size of the text

---

### ScenEdit_CreateBarkNotification_Unit()
The function's purpose is to show a 'bark' anchored on a unit. Barks are short text notifications that can be set to appear, briefly, anywhere on the map.

**Signature:** `ScenEdit_CreateBarkNotification_Unit ( UnitNameOrID, text, R, G, B [, moveUpward, fade, lifeTime, fontSize ] )`

**Parameters:**
- **UnitNameOrID** (`string`): The unit name or GUID. As no side is specified, GUID is more reliable
- **text** (`string`): Text to show
- **R** (`number`): The 'Red' component of the color (0-255) to show the text in
- **G** (`number`): The 'Green' component of the color (0-255)
- **B** (`number`): The 'Blue' component of the color (0-255)
- **moveUpward** (`True/False`) (optional): [Optional] Default is True. This will move the text upwards
- **fade** (`True/False`) (optional): [Optional] Default is True. This controls the fading out of the text
- **lifeTime** (`number`) (optional): [Optional] Default is 1 second. This controls how long the text stays visible
- **fontSize** (`number`) (optional): [Optional] Default is 18. This controls the fonst size of the text

---

### ScenEdit_CreateBarkNotification_Unit_Bulk()
The function's purpose is to show a 'bark' at a specific location. The notifications are shown in sequence, one after another. Barks are short text notifications that can be set to appear, briefly, anywhere on the map.

**Signature:** `ScenEdit_CreateBarkNotification_Unit_Bulk (UnitNameOrID, text, R, G, B [, moveUpward, fade, lifeTime, fontSize ] )`

**Parameters:**
- **UnitNameOrID** (`string`): The unit name or GUID. As no side is specified, GUID is more reliable
- **text** (`table`):
- **string** (`Text`): to show
- **R** (`number`): The 'Red' component of the color (0-255) to show the text in
- **G** (`number`): The 'Green' component of the color (0-255)
- **B** (`number`): The 'Blue' component of the color (0-255)
- **moveUpward** (`True/False`) (optional): [Optional] Default is True. This will move the text upwards
- **fade** (`True/False`) (optional): [Optional] Default is True. This controls the fading out of the text
- **lifeTime** (`number`) (optional): [Optional] Default is 1 second. This controls how long the text stays visible
- **fontSize** (`number`) (optional): [Optional] Default is 18. This controls the fonst size of the text

---

### ScenEdit_ExportInst()
This function export unit(s) in XML format to an INST file in folder 'ImportExport'. If the unit to be exported is a group, then the units in the group are automatically included. If there are differences between the unit and the 'vanilla' unit in the database, a 'delta' is created as part of the export.

**Signature:** `ScenEdit_ExportInst (side, unitList, fileData)`

**Parameters:**
- **side** (`string`): The name/GUID of the side owning the exported units
- **unitList** (`table`):
- **string** (`The`): name/GUID of the units to be exported
- **fileData** (`table`):
- **filename =** (`string`) (required): The Filename is mandatory
- **name =** (`string`): The name to be displayed on the in-game list
- **comment =** (`string`):

**Returns:** `number The number of units exported to the file, else 0`

---

### ScenEdit_GetKeyValue()
This function retrieves a value put into the persistent key store by ScenEdit_SetKeyValue.The key name used must be identical.

**Signature:** `ScenEdit_GetKeyValue (key, forCampaign)`

**Parameters:**
- **key** (`string`): The key to fetch the value for
- **forCampaign** (`True/False`) (optional): Read from the key store being passed to the next scenario in campaign. Optional, default = false

**Returns:** `string The value associated with the key. "" if none exists.`

---

### ScenEdit_ImportInst()
This function imports unit(s) in XML format from an INST file in the folder 'ImportExport'.

**Signature:** `ScenEdit_ImportInst (side,filename)`

**Parameters:**
- **side** (`string`): The side to import the inst file as
- **filename** (`string`): The filename of the inst file

**Returns:** `number Number of units imported`

---

### ScenEdit_InputBox()
Open an input box with the passed prompt.

**Signature:** `ScenEdit_InputBox (string)`

**Parameters:**
- **string** (`string`): The string to display to the user

**Returns:** `string Data entered into the box`

---

### ScenEdit_MsgBox()
This function displays a message box with the passed string. The buttons to show are controlled by the 'style'.

**Signature:** `ScenEdit_MsgBox (string, style)`

**Parameters:**
- **string** (`string`): The string to display to the user
- **style** (`value 0 = OK 1 = OK and Cancel buttons 2 = Abort, Retry and Ignore buttons 3 = Yes, No and Cancel buttons 4 = Yes and No buttons 5 = Retry and Cancel buttons.`): The style of the message box

**Returns:** `number The button number pressed. None = 0, OK = 1, Cancel = 2, Abort = 3, Retry = 4, Ignore = 5, Yes = 6, No = 7`

---

### ScenEdit_PlaySound()
This function plays a local sound file from the Sounds\Effects folder.

**Signature:** `ScenEdit_PlaySound (string)`

**Parameters:**
- **string** (`string`): The name of the file

**Returns:** `True/False True if successful`

---

### ScenEdit_QueryDB()
This function queries the database. Use the wrapper_object_variable.fields to see what can be returned The objects currently supported are 'weapon', 'mount' and 'sensor'.

**Signature:** `ScenEdit_QueryDB (objectType, DBID)`

**Parameters:**
- **objectType** (`string`): The type of item to query
- **DBID** (`number`): The databse id of item to query

**Returns:** `objectObject wrapper`

---

### ScenEdit_RunScript()
This function runs a script from a file. The file scriptmust be inside the [Command base directory]/Lua directory, or else the game will not be able to load it. You can make the file point to files within a sub-directory of this, as in 'library/cklib.lua'The file to find will be of the form [Command base directory]/Lua/[script]. A file can also be loaded indirectly from an attachment ScenEdit_UseAttachment There is an optional parameter to use the full path of 'script' that overrides the above, but putting files outside of the Command folder would make installing a scenario extremely difficult - the user would need to do manual file copying, etc. This option is more for the Professional user where they make have dedicated scripts on their servers.

**Signature:** `ScenEdit_RunScript (script [,customPath] )`

**Parameters:**
- **script** (`string`): The file containing the script to run.
- **customPath** (`True/False`) (optional): Use the full path from 'script' name. Optional. Defaults to False.

**Returns:** `True/False True if successful. If result is nil, then the method failed.`

---

### ScenEdit_SelectedUnits()
This function returns a list (of name and guid) of the units (actual or contact) currently selected

**Signature:** `ScenEdit_SelectedUnits ()`

**Parameters:**
- **None**

**Returns:** `table {} of`

---

### ScenEdit_SetKeyValue()
This function Sets the value for a key in the persistent key store. This function allows you to add values,associated with keys,to a persistent store KeyStorethat is retained when the game is saved and resumed.Keys and values are both represented as non-nilstrings.The value is retrieved by ScenEdit_GetKeyValue.

**Signature:** `ScenEdit_SetKeyValue (key, value, forCampaign)`

**Parameters:**
- **key** (`string`): The key to associate with
- **value** (`string`): The value to associate
- **forCampaign** (`boolean`) (optional): Pass the store to next scenario in campaign. Optional, default = false

---

### ScenEdit_SpecialMessage()
This function will Display a special message consisting of the HTML text message to the side specified by side . Optional parameters location allows the player to jump to the specified map position by clicking a button in a pop-up window. The optional parameter forceMapRecenter will center the map on specified location.

**Signature:** `ScenEdit_SpecialMessage (side, message, [location, forceMapRecenter])`

**Parameters:**
- **side** (`string`): The side name/guid to display the message to, or 'playerside' (see Note below)
- **message** (`string`): The HTML text to display to the player. Plain text is also accepted.
- **location [optional]** (`table`):
- **latitude =** (`latitude`):
- **longitude =** (`longitude`):
- **forceMapRecenter [optional]** (`True/False`): The map will be centered on location if present.

---

### ScenEdit_UpdateRSetting()
This function enables/disables scenario realism settings

**Signature:** `ScenEdit_UpdateRSetting (RealismSettingString, boolean)`

**Parameters:**
- **RealismSettingString =** (`RealismSetting`): The scenario realism setting
- **boolean** (`True/False`): Enables or disables the specified realism setting

**Returns:** `True/False Returns True if the setting is valid`

---

### ScenEdit_UseAttachment()
This function import an attachment into the scenario.

**Signature:** `ScenEdit_UseAttachment (attachment)`

**Parameters:**
- **attachment** (`string`): Name of the attachment (as shown in the properties section when created/added) or more accurately the GUID of the attachment (as found in AttachmentRepo folders)

---

### ScenEdit_UseAttachmentOnSide()
This function uses an attachment on a side (used for .inst files as attachments).

**Signature:** `ScenEdit_UseAttachmentOnSide (attachment, sidename)`

**Parameters:**
- **attachment** (`string`): Name of the attachment (as shown in the properties section when created/added) or more accurately the GUID of the attachment (as found in AttachmentRepo folders)
- **sidename** (`string`): The name of the side to import the attachment into

---

### SetScenarioTitle()
This function sets or changes the scenario name

**Signature:** `SetScenarioTitle(newTitle)`

**Parameters:**
- **newTitle** (`string`): The scenario name

**Returns:** `True/False True if scenario name is valid`

---

### Tool_Bearing()
This function returns the bearing between two points, which can be a GUID of a unit/contact or a latitude/longitude point.

**Signature:** `Tool_Bearing ( fromHere, toHere)`

**Parameters:**
- **fromHere** (`table`): or { } of latitude = latitude longitude = longitude Unit/Contact guid or a location point
- **toHere** (`table`): or { } of latitude = latitude longitude = longitude Unit/Contact guid or a location point

---

### Tool_BuildBlankScenario()
The function purpose is to create a blank scenario based on the current DB or by supplying the DB file name a different DB.

**Signature:** `Tool_BuildBlankScenario ( useDBname )`

**Parameters:**
- **useDBname** (`string`) (optional): (Optional) file name from the DB folder

---

### Tool_DumpEvents()
This function dumps the scenario events to a file ('scenario filename' events.xml) in the scenario folder, which can be useful for checking that the events are correctly set up.

**Signature:** `Tool_DumpEvents ( )`

**Parameters:**
- **None**

---

### Tool_EmulateNoConsole()
This function allows other functions to behave as if there is no console attached by executing in the Lua console. This is useful examining how functions behave when running within Command as in Events by running the script in the console first. Some functions will 'die' if running in interactive mode.

**Signature:** `Tool_EmulateNoConsole ( mode )`

**Parameters:**
- **mode** (`True/False`): 'True' (which is the default mode if no parameter supplied) turns on the emulation mode, 'False' will turn it off.

---

### Tool_LOS()
This function can return (a) the distance to the radar horizon between mix of units and altitudes, or (b) a true/false if a LOS exists between a unit and a contact

**Signature:** `Tool_LOS ( table)`

**Parameters:**
- **table** (`table`):
- **mode =** (`number`): Distance to horizon (0) or LOS is clear (1)
- **horizon =** (`number`): Radar (0), Visual (1) or ESM (2)
- **useRangeLimits =** (`True/False`): If using a unit as the 'observer', use the min/max ranges of the sensor(s) in the unit to get the 'horizon'
- **observer =** (`table`):
- **altitude =** (`number or string`): Altitude of the observer.
- **guid =** (`number`): Observer unit GUID. The altitude of the unit and any mast height will be calculated. If performing a LOS check, then this must be supplied
- **location =** (`table`):
- **latitude =** (`number or string`): Latitude of the from location
- **longitude =** (`number or string`): Longitude of the from location
- **target =** (`table`):
- **altitude =** (`number or string`): Altitude of the target
- **guid =** (`number`): Target contact GUID. The altitude of the actual unit will be calculated. If performing a LOS check, then this must be supplied
- **location =** (`table`):
- **latitude =** (`number or string`): Latitude of the to location
- **longitude =** (`number or string`): Longitude of the to location

---

### Tool_LOS_Points()
This function returns the status of the LOS check between the points defined by 'from' and 'to'. The type of check can be for radar, EO/IR or ESM.

**Signature:** `Tool_LOS_Points ( from, to, type)`

**Parameters:**
- **from** (`table`):
- **altitude =** (`number or string`): Altitude of the from location. The keyword can be shortened to 'alt = '.
- **latitude =** (`number or string`): Latitude of the from location
- **longitude =** (`number or string`): Longitude of the from location
- **to** (`table`):
- **altitude =** (`number or string`): Altitude of the to location. The keyword can be shortened to 'alt = '.
- **latitude =** (`number or string`): Latitude of the to location
- **longitude =** (`number or string`): Longitude of the to location
- **type** (`valueRadar = 0 EO/IR = 1 ESM = 2`): The type of 'horizon'.

---

### Tool_DateTimeToSeconds()
Converts a date/time string to seconds since epoch.
(Bron: WhatsNew.pdf March 2026)

**Signature:** `Tool_DateTimeToSeconds (datetime_string)`

**Parameters:**
- **datetime_string** (`string`): The date/time string to convert.

---

### Tool_SecondsToDateTime()
Converts seconds since epoch to a date/time string.
(Bron: WhatsNew.pdf March 2026)

**Signature:** `Tool_SecondsToDateTime (seconds)`

**Parameters:**
- **seconds** (`number`): The seconds since epoch to convert.

---

### Tool_ConvertDecimalDegreesToDMS()
Converts decimal degrees to Degrees, Minutes, Seconds (DMS) format.
(Bron: WhatsNew.pdf March 2026)

**Signature:** `Tool_ConvertDecimalDegreesToDMS (decimal_degrees)`

**Parameters:**
- **decimal_degrees** (`number`): The decimal degrees to convert.

---

### Tool_Range()
This function returns the range between points, which can be a GUID of a unit/contact or a latitude/longitude (with optional altitude) point.

**Signature:** `Tool_Range (fromHere, toHere [,useSlant])`

**Parameters:**
- **fromHere** (`table`): or { } of latitude = latitude longitude = longitude altitude = altitude Unit/Contact guid or a location point
- **toHere** (`table`): or { } of latitude = latitude longitude = longitude altitude = altitude Unit/Contact guid or a location point
- **useSlant** (`true`) (optional): Optional - calculate the slant distance accounting for altitde instead of the default horizontal distance

---

### Tool_QueryRCS()
This function calculates and returns a numerical value representing the signature strength of a specified targetunitname from the perspective of a designated sensorunitname. The type of signature being queried is determined by the SIGNATURETYPE parameter. A higher returned value signifies a more easily detectable target in the specified signature spectrum

**Signature:** `Tool_QueryRCS ( table)`

**Parameters:**
- **table** (`table`):

---

### Tool_QuerySoundLevel()
Returns the sound SL of naval units

**Signature:** `Tool_QuerySoundLevel ( table)`

**Parameters:**
- **table** (`table`):

---

### World_GetCircleFromPoint()
This function returns a circle around point.

**Signature:** `World_GetCircleFromPoint ( table )`

**Parameters:**
- **table** (`table`):
- **latitude =** (`latitude`): The location of the central point
- **longitude =** (`longitude`): The location of the central point
- **numpoints =** (`number`) (required): The number of points to generate on the circle's arc. A minimum of 3 is required
- **radius =** (`number`): The radius (NM) around the central point

---

### World_GetElevation()
This function returns the elevation in meters of a given point

**Signature:** `World_GetElevation ( table )`

**Parameters:**
- **table** (`table`):
- **latitude =** (`latitude`): The latitude of the point
- **longitude =** (`longitude`): The longitude of the point

---

### World_GetLocation()
This function returns details of a given position. These details are similar to what is shown by the map cursor box.

**Signature:** `World_GetLocation ( table )`

**Parameters:**
- **table** (`table`):
- **latitude =** (`latitude`): The latitude of the point
- **longitude =** (`longitude`): The longitude of the point

---

### World_GetPointFromBearing()
This function returns a location (as a set of longitude/latitude) based on bearing and distance from a point.

**Signature:** `World_GetPointFromBearing ( table )`

**Parameters:**
- **table** (`table`):
- **latitude =** (`latitude`): The latitude of the start point
- **longitude =** (`longitude`): The longitude of the start point
- **distance =** (`number`): The distance from the start point (NM)
- **bearing =** (`number (0-360)`): The Bearing from the start point

---

### UI_CallAdvancedDialog()
The function allows you to create a dynamic dialog box from Lua script.

**Signature:** `UI_CallAdvancedDialog ( title, description, interactions )`

**Parameters:**
- **title** (`string`): The title that shows on the top of the dialog box
- **description** (`string`): The message to include in the dialog box
- **interactions** (`table`): One of more Button names

**Returns:** `string The Button pressed`

---

### UI_CallAdvancedHTMLDialog()
The function allows you to show a HTML form, from which variables will be returned to the Lua script.

**Signature:** `UI_CallAdvancedHTMLDialog ( title, form, interactions )`

**Parameters:**
- **title** (`string`): The title that shows on the top of the dialog box
- **form** (`string`): A HTML form from which data can be entered, The current input supported modes are text, select, and radio.
- **interactions** (`table`): One of more Button names

**Returns:** `Table {} of Form_name = value The variable name from the form and its value. The button pressed is returned in the table under ['pressed'].`

---

### UI_OpenNewDatabaseWindow()
This function opens the database page for the specified unit type and dbid

**Signature:** `UI_OpenNewDatabaseWindow (SelectedObjectType, SelectedObjectID)`

**Parameters:**
- **SelectedObjectType** (`typeAircraft, Ship, Submarine, Facility, Ground Unit, Satellite, Weapon, Sensor`): The unit type
- **SelectedObjectID** (`number`): The unit database ID

---

### UI_SelectUnitsPrompt_FromSides()
The function purpose

**Signature:** `Function Syntax ( ... )`

**Parameters:**
- **List** (`the`): parameters as in the Syntax line

---

### UI_SelectUnitsPrompt_OwnSide()
The function purpose

**Signature:** `Function Syntax ( ... )`

**Parameters:**
- **List** (`the`): parameters as in the Syntax line

---

### UI_SetCameraView()
This function sets the camera to the specified latitude, longitude, and altitude

**Signature:** `UI_SetCameraView (latitude, longitude, altitude)`

**Parameters:**
- **latitude** (`latitude`): The camera latitude. Must be decimal degrees. String of degree/minutes/seconds is currently not valid
- **longitude** (`longitude`): The camera longtitude. Must be decimal degrees. String of degree/minutes/seconds is currently not valid
- **altitude** (`altitude`): The camera altitude in meters

---

### Tool_ResetMessageLog()
This function clears the message log for all sides

**Signature:** `Tool_ResetMessageLog(resetMessageLogBoolean)`

**Parameters:**
- **resetMessageLogBoolean** (`True/False`): Resets the message log

**Returns:** `True/False Clears the message log if true`

---

### Tool_UIwindow()
This function opens or closes UI windows

**Signature:** `Tool_UIwindow (name, mode)`

**Parameters:**
- **name** (`UI Window`): The UI window
- **mode** (`True/False`): Open or close boolean

**Returns:** `True/False Opens the specified window if True, closes the window if False`

---

### ScenEdit_AddCustomLoss()
This function adds entries to the loss list so they can be reported. This allows adding non-play items (such as casualties) to the Loss & Expenditure view to enhance the experience. It will also show up in the wrapper for Side losses. Updating the entries replaces what was there before hand, so to remove an entry, just use a number of 0.

**Signature:** `ScenEdit_AddCustomLoss ( SideNameOrId, table )`

**Parameters:**
- **SideNameOrId** (`string`): The side name/guid to be affected
- **table** (`table`):
- **string** (`The`): reported name of the loss item
- **number** (`The`): new number to apply to it

---

### ScenEdit_AddExplosion()
This function creates a detonation of a warhead at a specific location. Useful for simulating explosions where no weapon is fired such as a bomb being detonated. *** Does not currently support under surface explosions ****

**Signature:** `ScenEdit_AddExplosion( table )`

**Parameters:**
- **table** (`table`):
- **altitude =** (`altitude`): The altitude of the detonation. If no 'altitude' is passed, or the value of the parameter is 'surface', the explosion will occur at 'ground zero' at that location.
- **latitude =** (`latitude`): The latitude of the detonation
- **longitude =** (`longitude`): The longitude of the detonation
- **warheadid =** (`number`): The database ID of the warhead to detonate

---

### ScenEdit_AddMinefield()
This function will attempt to lay a minefield for a Side consisting of the mine type, a number to lay, an arming delay and the area of the field to sow them in. Mines are laid within their depth settings, and there are proximity considerations. This is why the full number might not be laid in one execution of the command. Normal RPs are checked first, and then the No-nav/Exclusion zone RPs for the area to lay the mines in.

**Signature:** `ScenEdit_AddMinefield( table )`

**Parameters:**
- **table** (`table`):
- **area =** (`table`):
- **string** (`The`): reference point guid/name
- **dbid =** (`number`): The database id of the mine to use
- **delay =** (`number`): The arming delay in seconds
- **number =** (`number`): The number of mines to attempt to lay
- **side =** (`string`): The Side name/guid that owns the mines

**Returns:** `number number of mines actually laid`

---

### ScenEdit_AddSide()
This function adds a new side with the specified name. The new side can be used after this is done.

**Signature:** `ScenEdit_AddSide (table)`

**Parameters:**
- **table** (`string`):
- **side =** (`string`): The name of the new side

**Returns:** `Side A wrapper for the new side`

---

### ScenEdit_ClearAllAircraft()
The function removes ALL embarked aircraft from the unit. If the unit is a group, then all units in the group are also affected.

**Signature:** `ScenEdit_ClearAllAircraft ( table )`

---

### ScenEdit_ClearAllMagazines()
This function removes all weapons from the selected units magazines.

**Signature:** `ScenEdit_ClearAllMagazines ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name of the unit
- **name =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit

**Returns:** `True/False True if unit is valid`

---

### ScenEdit_DeleteMine()
This function deletes a specific mine from a side's minefield

**Signature:** `ScenEdit_DeleteMine (side, guid)`

**Parameters:**
- **side** (`string`): Side name/guid
- **guid** (`string`): Mine guid

**Returns:** `True/FalseTrue if successful`

---

### ScenEdit_DeleteMinefield()
This function will delete all the mines owned by the side in the minefield as defined by 'area'. The Reference Points are checked against the side's normal RPs, and then against the side's non-navigation/exclusion zone RPs. Note that the 'area' supports two methods of supplying the RPs; one with just a list of name/guids (the preferred simplier way), and the more complicated way with each one being another table. The second method would be useful if passing a returned 'area' table from some other function call. Both peform the same operation.

**Signature:** `ScenEdit_DeleteMinefield (side, area)`

**Parameters:**
- **side** (`string`): Side name/guid
- **area =** (`table`):
- **name =** (`string`): The name/guid of the reference point
- **string** (`The`): name/guid of the reference point

**Returns:** `number Number of mines removed`

---

### ScenEdit_DistributeWeaponAtAirbase()
The function's purpose is to distribute a number of weapons across the magazine(s) in a group (typically an airbase)

**Signature:** `ScenEdit_DistributeWeaponAtAirbase ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **wpn_dbid =** (`number`): The weapon database ID
- **number =** (`number`): Number to be added

---

### ScenEdit_GetDateTimeTicks()
The function's purpose is to get the number of time 'ticks' based on the current game time. This is a low level counter of time past

**Signature:** `ScenEdit_GetDateTimeTicks ( )`

**Parameters:**
- **None**

---

### ScenEdit_GetMinefield()
This function retrieves the mines in a minefield The Reference Points are checked against the side's normal RPs, and then against the side's non-navigation/exclusion zone RPs. Note that the 'area' supports two methods of supplying the RPs; one with just a list of name/guids (the preferred simplier way), and the more complicated way with each one being another table. The second method would be useful if passing a returned 'area' table from some other function call. Both peform the same operation.

**Signature:** `ScenEdit_GetMinefield( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): Side name/guid
- **area =** (`table`):
- **name =** (`string`): The name/guid of the reference point
- **string** (`The`): name/guid of the reference point

---

### ScenEdit_GetSideIsHuman()
This function indicates if side is played by a human player

**Signature:** `ScenEdit_GetSideIsHuman (sidename)`

**Parameters:**
- **sidename** (`string`): The side's name/guid

**Returns:** `True/False True if the side is human controlled`

---

### ScenEdit_GetSideOptions()
This function retrieves the side attributes ( guid, awareness, proficiency)

**Signature:** `ScenEdit_GetSideOptions (options)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): Side name/guid

---

### ScenEdit_GetSidePosture()
This function shows the posture of sideA towards sideB.

**Signature:** `ScenEdit_GetSidePosture ( sideA, sideB)`

**Parameters:**
- **sideA** (`string`): The first side name/guid
- **sideB** (`string`): The second side name/guid

**Returns:** `string The posture as 'N','F','H',or 'A'. If posture is unknown, then '' is returned.`

---

### ScenEdit_HostUnitToParent()
This function hosts (bases) a unit on another unit.

**Signature:** `ScenEdit_HostUnitToParent (table)`

**Parameters:**
- **table** (`table`):
- **HostedUnitNameOrID =** (`string`): The name or GUID of the unit to update. The alternate parameter HostedUnitNameOrID can be used instead.
- **SelectedHostNameOrID =** (`string`): The name or GUID of the host to move the unit into. The alternate parameter HostBaseNameOrID can be used instead.
- **SelectedBaseNameOrID =** (`string`): The name or GUID of the host to be the unit's assigned base. The alternate parameter AssignedBaseNameOrID can be used instead.

**Returns:** `True/False True if successful. OR if supplying both base parameters in same method. [0] = host base T/F, [1] = assigned base T/F True if successful.`

---

### ScenEdit_PlayerSide()
This function returns the current side, which is assumed to be the player's.

**Signature:** `ScenEdit_PlayerSide ()`

**Parameters:**
- **None**

**Returns:** `string The name of the current side`

---

### ScenEdit_RemoveSide()
This function remove a side from play. This removes ALL units and contacts for the side.

**Signature:** `ScenEdit_RemoveSide (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID to remove

**Returns:** `Side A wrapper for the side removed, or nil otherwise`

---

### ScenEdit_SetLoadoutAvailable()
This function sets the availability/visibility of aircraft loadouts on the Ready/Arm menu. This is not unit DBID specific, all aircraft that use the loadoutID will have the loadout hidden.

**Signature:** `ScenEdit_SetLoadoutAvailable(table)`

**Parameters:**
- **table** (`table`):
- **LoadoutDBID =** (`number`): The ID of the loadout
- **Available =** (`True/False`): Set the availability of the loadout. If set to False the loadout will be hidden on the Ready/Arm menu.

**Returns:** `booleanTrue/False`

---

### ScenEdit_SetSideOptions()
This function updates the side options

**Signature:** `ScenEdit_SetSideOptions (table)`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side guid/name
- **awareness =** (`Awareness`): The side awareness
- **AutoTrackCivillians =** (`True/False`): The side sbility to track civilians
- **collectiveResponsibility =** (`True/False`): The side collective resposibility
- **computerControlledOnly =** (`True/False`): The side is controlled by AI
- **proficiency =** (`Proficiency`): The side proficiency
- **switchto =** (`True/False`) (optional): [optional] Switch the current side to the 'side' parameter.

---

### ScenEdit_SetSidePosture()
This function Sets side A's posture towards side B to the specified posture.This is the same as Stance,but only the first character of the name is

**Signature:** `ScenEdit_SetSidePosture (sideA, sideB, posture)`

**Parameters:**
- **sideA** (`string`): Side A's name or GUID
- **sideB** (`string`): Side B's name or GUID
- **posture** (`value 'F' = Friendly 'H' = Hostile 'N' = Neutral 'U' = Unfriendly`): The posture of side A towards side B

**Returns:** `booleanTrue/False for Successful/Failure`

---

### ScenEdit_SetUnitSide()
This function Changes the side of a unit. Passing a group will change the attached units too

**Signature:** `ScenEdit_SetUnitSide ( table )`

**Parameters:**
- **table** (`table`):
- **side =** (`string`): The side name/GUID of the unit
- **unitname =** (`string`): The name of unit
- **guid =** (`string`): The GUID of the unit
- **newSide =** (`string`): The name/guid to change the 'unit' to

---

### ScenEdit_WeaponAllocation()
This function returns the type and number of weapons allocated by a unit or side

**Signature:** `ScenEdit_WeaponAllocation (attackerID, contactId, attackingSideID)`

**Parameters:**
- **attackerID** (`string`): The attacking unit guid
- **contactId** (`string`): The contact guid being attacked
- **attackingSideID** (`string`): The attacking side guid

---

### VP_SetTimeCompression()
The function changes the current time compression ( the 'x#' on the UI).

**Signature:** `VP_SetTimeCompression ( number )`

**Parameters:**
- **number** (`value 0 = One Second 1 = Two Seconds 2 = Five Seconds 3 = Fifteen Seconds 4 = Coarse One Sec Slice 5 = Coarse Five Sec Slice`):

---

## Wrappers & Objects

### Calling wrappers in Lua (required)

CMO returns **wrapper objects** (`ScenEdit_GetMission`, `ScenEdit_GetUnit`, `ScenEdit_AddUnit`, …). Distinction:

| Kind | Syntax | Example |
| :--- | :--- | :--- |
| **Field** | dot `.` | `mission.name`, `unit.guid` |
| **Instance method** (`method()` in tables below) | **colon `:`** | `mission:updateWPtimes()` |

Do **not** use `mission.updateWPtimes()` — that calls the .NET method **without** `self` and yields:

`instance method 'updateWPtimes' requires a non null target object`

**Correct:**

```lua
local mission = ScenEdit_GetMission('United States', 'My Strike')
if mission then
    mission:updateWPtimes()
    -- or: mission:createFlightPlans({ DATEONTARGET = '2026/06/01', TIMEONTARGET = '06:30:00' })
end
```

`if mission.updateWPtimes then` only tests that the function exists; the **call** must still use `:updateWPtimes()`. When unsure: `pcall(function() mission:updateWPtimes() end)`.

This applies to every wrapper `method(...)` row in this section (Mission, Flight, Loadout, Cargo, …).

### Cargo
| Field | Type | Description |
| :--- | :--- | :--- |
| guid | string |  |
| type | CargoObjectType | The type of cargo object |
| storageType | CargoStorageType | The type of cargo storage |
| dbid | number | The DBID of the cargo |
| name | number | The name of the cargo |
| requiredSize | CargoType | The size |
| requiredMass | number | The mass metric tons |
| requiredArea | number | The area sq m |
| requiredPAX | number | The PAX (Crew Space) |
| requiredAreaAsStored | number | The area |
| requiredPAXAsStored | number | The PAX |
| isParadropCapable | True/False | Can be dropped by parachute |
| unit | Unit | The unit holding cargo |
| containerCargo | { name, Type, dbid, guid, area,pax,mass, [contentType, [fuelType, fuelQuantity,] [weaponDBID, weaponQuantity]] } | Table of items held as cargo inside container |
| createContainerContentCustom | method(name, size, mass, area, volume) |  |
| createContainerContentFuel | method(fuelType, fuelLiters) |  |
| createContainerContentAmmunition | method(weaponDBID, quantity) |  |
| deleteContainerContents | method(contentGuid) |  |

### Contact
| Field | Type | Description |
| :--- | :--- | :--- |
| actualunitdbid | number | The Actual unit DB id based on detection classification, else 0 |
| actualunitid | string | The actual unit GUID of this contact, else "" |
| age | number | The number of seconds this contact has been detected for |
| altitude | number | The current Altitude of this contact if known, else nil |
| areaofuncertainty | { LatLon, ... } | Table of LatLon points defining the area of contact |
| BDA | { FIRES, FLOOD, STRUCTURAL } | Battle Damage Assessment on this contact, else nil |
| classificationlevel | ContactIdStatus | The Level of classification on this contact |
| detectedBySide | Side | The side who actually detected this contact (instead of having it shared by someone else) |
| detectionBy | { Visual, Infrared, Radar, ESM, SonarActive, SonarPassive } | How long ago was this contact detected by these sensor types |
| emissions | { Emissions, ... } | Table of detected emmissions from this contact, else nil if no detected emissions |
| FilterOut | True/False | Is this contact filtered out? |
| firedOn | { string, ... } | Table of unit guids that are firing on this contact, else nil if none |
| firingAt | { string, ... } | Table of contact guids that this contact is firing at, else nil if none |
| fromside | Side | The side who 'owns' this contact, else nil |
| guid | string | This contact identifying GUID |
| heading | number | This contact's Heading if known, else nil |
| lastDetections | { LastDetections, ... } | Table of recent detections on this contact, else nil if none |
| latitude | Latitude | The suspected latitude of this contact |
| longitude | Longitude | The suspected longitude of this contact |
| markedAsDecoy | True/False | Marked as a decoy contact for 'fromside' |
| missile_defence | number | Applicable to Facility and Ships. If the classification level is 'known class' or higher, show Missile Defence from database, else -1 for unknown contact |
| name | string | This contact name |
| observer | Side | The contact's original detecting side or nil if it is the same as requesting sideThis tells if the contact was shared from another side |
| observer_posture | Stance(letter) | The Posture from the perspective of the original detector of this contact |
| posture | Stance(letter) | The Posture from the perspective of the owner of this contact |
| potentialmatches | { EMmatch, ... } | Table of potential EMCON emission matches for this contact |
| side | Side | This Contact actual side if known, else nil |
| speed | number | This Contact Speed if known, else nil |
| targetedBy | { string, ... } | Table of unit guids that have this contact as a target but necessarily firing on it, else nil if none |
| type | ContactType | This Contact type string |
| type_description | string | This Contact description based on detection classification |
| typed | number | The ContactType of this contact as a number |
| weather | { Weather } | Table of weather parameters at this Contact location, else nil |
| DropContact | method() | Drops this contact from the perspective side (who is looking at this contact) |
| inArea | method({ area }) | Is this contact in the 'area' defined by a table of RPs |

### Doctrine
| Field | Type | Description |
| :--- | :--- | :--- |
| aaw_guidance | valueAlways Continue Guidance = 0 Drop Guidance = 1 | 'drop guidance' -> the firing platform will drop guidance when it becomes impossible for the guided missile to intercept the target. |
| aaw_rearward_fire | valueAlways Fire = 0 Fire vs Aircraft or Weapons ONLY if interception is between shooter and target = 1 Fire vs Aircraft Only if interception is between shoter and target = 2Fire vs Weapons Only if interception is between shoter and target = 3 | 'Rearward' is based on the heading of the target -- if the target is heading away from the firing platform then it is 'to the rear.You can imagine a line perpendicular to the heading of the incoming target -- if the target goes 'behind' this line OR if the intercept point is behind this line, then the firing platform will drop the target |
| aaw_wra_qty | valueFor All targets WRA is fullfilled Separatelly = 0 For Aircraft or Weapons, WRA is fullfilled by ANY guided weapon = 1 For Aircraft, WRA is fullfilled by ANY guided weapon = 2 For Weapons, WRA is fullfilled by ANY guided weapon = 3 | How many different weapons needs to be fired against Target Aircrafts or Target weapons or both. Fullfilled separately means if two different weapons from two different units can fire at the target, they will fire to allocate the weapon salvo. If the setting is by ANY guided weapon, only one weapon type will be used |
| air_operations_tempo | valueSurge = 0 Sustained = 1 | Tempo of operations |
| automatic_evasion | True/False | True if the unit should automatically evade |
| avoid_contact | valueNo = 0 Yes_ExceptSelfDefence = 1 Yes_Always = 2 | How should 'detection' be treated |
| bvr_logic | valueStraightIn = 0 Crank = 1 Drag = 2 | BVR (Beyond-visual-range) behaviour |
| deploy_on_attack | valueIgnore = 0 Exhausted = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 Percent100 = 5 LoadFullWeapons = 6 | Level of attacking weapons remaining to allow deployment |
| deploy_on_damage | valueIgnore = 0 Percent5 = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 | Level of damage remaining to allow deployment |
| deploy_on_defence | valueIgnore = 0 Exhausted = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 Percent100 = 5 LoadFullWeapons = 6 | Level of defending weapons remaining to allow deployment |
| deploy_on_fuel | valueIgnore = 0 Bingo = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 Percent100 = 5 | Level of fuel remaining to allow deployment |
| dipping_sonar | valueAutomatically_HoverAnd150ft = 0 ManualAndMissionOnly = 1 | Dipping sonar behaviour |
| dive_on_threat | valueYes = 0 Yes_ESM_Only = 1 Yes_Ships20nm_Aircraft30nm = 2 No = 3 | Should sub dive when threatened |
| emcon | { radar, sonar, oecm } | The EMCON status (acive [1]/passive [0]) |
| engage_non_hostile_targets | True/False | True if the unit should attempt hostile action against units that are not hostile |
| engage_opportunity_targets | True/False | True if the unit should take opportunistic shots |
| engaging_ambiguous_targets | AmbiguousTtargets | How is the ambiguosity of the target treated? Is the target location good enough to shoot at? |
| fuel_state_planned | JokerFuelLevel | Planned action when fuel is at ... |
| fuel_state_rtb | OnFuelRTB | Action to take when RTB initiated due to fuel |
| gun_strafing | valueNo = 0 Yes = 1 | Can gun straffing be used |
| ignore_emcon_while_under_attack | True/False | True if EMCON should be ignored and all systems should go active when engaged |
| ignore_plotted_course | True/False | True if the unit should ignore plotted course when attacking/investigating |
| jettison_ordnance | valueNo = 0 Yes = 1 | Can ordnance be jettison |
| kinematic_range_for_torpedoes | valueAutomaticAndManualFire = 0 ManualFireOnly = 1 No = 2 | Use the maximum range for torpedoes? |
| maintain_standoff | True/False | True if the unit should try to avoid approaching its target |
| quick_turnaround_for_aircraft | valueYes = 0 FightersAndASW = 1 No = 2 | Can aircraft be used for 'quick turnaround' |
| recharge_on_attack | BatteryRecharge | Level to recharge batteries while engaged |
| recharge_on_patrol | BatteryRecharge | Level to recharge batteries while on patrol |
| refuel_unrep_allied | UNREP Allies | Can Allied uniits be replenished |
| rtb_when_winchester | True/False | True if the unit should return to base when out of weapons |
| StrikeMemberFocus | value0 = Opportunity Scrambling 1 = Focus on mission targets | Mission focus |
| TargetPriority | { TargetPriority } | Target priority list |
| ThreatMaxDist | number | Maximum range at which an inbound weapon is considered a threat. Missiles beyond this distance are ignored for threat evaluation and defensive reactions |
| use_aip | valueNo = 0 Yes_AttackOnly = 1 Yes_Always = 2 | Use AIP (Air-independent propulsion) if present |
| use_nuclear_weapons | True/False | True if the unit should be able to employ nuclear weapons |
| use_refuel_unrep | UNREP | How is underway replenishment used |
| use_sams_in_anti_surface_mode | True/False | True if SAMs can be used to engage surface targets |
| use_wp_missile_in_anti_surface_mode | True/False | True if missile WP are used to engage surface targets |
| weapon_control_status_air | WCS | Weapon control for engaging air units |
| weapon_control_status_land | WCS | Weapon control for engaging land units |
| weapon_control_status_subsurface | WCS | Weapon control for engaging subsurface units |
| weapon_control_status_surface | WCS | Weapon control for engaging surface units |
| weapon_state_planned | WeaponDoctrine | Planned action when weapons are at ... |
| weapon_state_rtb | OnWeaponRTB | Action to take when RTB initiated due to weapons |
| withdraw_on_attack | valueIgnore = 0 Exhausted = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 Percent100 = 5 | Level of attacking weapons to cause withdrawal |
| withdraw_on_damage | valueIgnore = 0 Percent5 = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 | Level of damage to cause withdrawal |
| withdraw_on_defence | valueIgnore = 0 Exhausted = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 Percent100 = 5 | Level of defending weapons to cause withdrawal |
| withdraw_on_fuel | valueIgnore = 0 Bingo = 1 Percent25 = 2 Percent50 = 3 Percent75 = 4 Percent100 = 5 | Level of fuel to cause withdrawal |
| addTargetPriorityEntry | method(type, subtype, isfixedfacilitysubtype, dbid, listIndex) |  |
| deleteTargetPriorityEntry | method(listIndex) |  |

### DoctrineWRA
| Field | Type | Description |
| :--- | :--- | :--- |
| level | string | The doctrine selected (at unit/mission/side) - useful Is just using GUIDs [info] |
| target_type | TargetTypeWRA | Type of applicable target |
| wra_? | { WRA } | The WRA weapon settings for the various weapon systems |

### Event
| Field | Type | Description |
| :--- | :--- | :--- |
| actions | table | The details of the actions in event READ ONLY |
| conditions | table | The details of the conditions in event READ ONLY |
| description | string | The event description/name. |
| details | table | The complete details of the event in one table. The triggers/conditions/actions tables are repeated within this. READ ONLY |
| guid | string | The event GUID. READ ONLY |
| isActive | Yes/No | The event is active |
| isRepeatable | True/False | The event repeats |
| isShown | True/False | The event shows on log |
| name | string | The event name (currently not used). |
| probability | string | The event chance to occur (0-100) |
| triggers | table | The details of the triggers in event READ ONLY |

### Flight
Wrapper for mission flights (used in Mission Flight Plans).
(Bron: WhatsNew.pdf March 2026)

| Field | Type | Description |
| :--- | :--- | :--- |
| guid | string | GUID of the flight. |
| waypoints | { Waypoint, ... } | Table of waypoints for this flight. |
| refreshWaypoints | method() | Refreshes the waypoints from the flight plan. |
| insertWaypoint | method(table) | Inserts a new waypoint. Table should contain latitude, longitude, and optionally altitude, name, type. |
| deleteWaypoint | method(index) | Deletes the waypoint at the specified index. |

---

### Group
| Field | Type | Description |
| :--- | :--- | :--- |
| doctrine | Doctrine | READ ONLY |
| guid | string | READ ONLY |
| lead | string | Group leader guid |
| name | string | Group/unit name |
| side | string | Name of the group sideREAD ONLY |
| type | string | Type of group READ ONLY |
| unitlist | { string, ... } | A table of unit GUIDs assigned to group. READ ONLY |

### Loadout
| Field | Type | Description |
| :--- | :--- | :--- |
| additionalData | { AdditionalData } | Additional data for the loadout |
| dbid | string | ID from database |
| name | string | Name of loadout |
| quickTurnaround | { QuickTurnaround } | Quick turnaround settings for the loadout |
| roles | { role, TOD, weather } | Table of the loadout usage |
| weapons | { WeaponLoaded, ... } | Table of weapons in loadout |
| setExactWeaponQuantity | method( guid, quantity) | Sets the current load of the weapon defined by 'guid' to the value 'quantity' |

### Magazine
| Field | Type | Description |
| :--- | :--- | :--- |
| armor | number | Armor rating on magazine |
| capacity | number | Total capacity of magazine |
| dbid | number | Database ID |
| guid | string | GUID of magazine |
| isaviationmagazine | True/False | Is this an Aviation magazine? |
| name | string | Name of magazine |
| parentunitguid | string | Parent guid of unit supporting this magazine |
| rof | number | Magazine reload time |
| weapons | { WeaponLoaded, ... } | Table of weapon loads in magazine |
| setExactWeaponQuantity | method( guid, quantity) | Sets the current load of the weapon defined by 'guid' to the value 'quantity' |

### Mission
| Field | Type | Description |
| :--- | :--- | :--- |
| aar | { AAR } | A table of the air-to-air refueling options. READ ONLY |
| assignedCargo | { CargoItem, ... } | Table of CargoItems assigned to be moved by this mission. READ ONLY |
| doctrine | Doctrine | READ ONLY |
| endtime | DateTime | Time mission ends (assumes DDMMYYYY for ambiguous date) |
| guid | string | The GUID of the mission. READ ONLY |
| isactive | True/False | True if mission is currently active |
| name | string | Name of mission |
| OnDeactivateUassign | True/False | 'On mission deactivation unassign units' tick box |
| OnDeactivateRTB | True/False | 'On mission deactivation RTB units' tick box |
| OnDeactivateDelete | True/False | 'On mission deactivation delete mission' tick box |
| side | string | Mission belongs to side |
| starttime | DateTime | Time mission starts (assumes DDMMYYYY for ambiguous date) |
| SISH | True/False | 'Scrub if side human' tick box |
| targetlist | { string, ... } | A table of target GUIDs assigned to mission. READ ONLY |
| TakeOffTime | DateTime | Time mission flights take off (assumes DDMMYYYY for ambiguous date) |
| TimeOnTargetStation | DateTime | Time mission expects flights to be at target or on station (assumes DDMMYYYY for ambiguous date) |
| type | MissionClassNone = 0 Strike = 1 Patrol = 2 Support = 3 Ferry = 4 Mining = 5 MineClearing = 6 Escort = 7 Cargo = 8 | Mission class. READ ONLY |
| typeS | string | Mission class as a string |
| unitlist | { string, ... } | A table of unit GUIDs assigned to mission. READ ONLY |
| packagelist | table | A table with the missions in a task pool (only if wrapper is a taskpool) |
| parentTaskPool | string | GUID of the parent taskpool (only if wrapper is a package |
| cargomission | { CargoMission } | A table of the mission specific options. READ ONLY |
| ferrymission | { FerryMission } | A table of the mission specific options. READ ONLY |
| mineclearmission | { MineClearMission } | A table of the mission specific options. READ ONLY |
| minemission | { MineMission } | A table of the mission specific options. READ ONLY |
| strikemission | { StrikeMission } | A table of the mission specific options. READ ONLY |
| supportmission | { SupportMission } | A table of the mission specific options. READ ONLY |
| patrolmission | { PatrolMission } | A table of the mission specific options. READ ONLY |
| addAssignedCargo | method(CargoObjectType, dbid, guid) | Add a non-mount cargo item to assigned cargo |
| removeAssignedCargo | method(CargoObjectType, dbid, guid) | Remove a non-mount cargo item from assigned cargo |
| addAssignedCargoMount | method(dbid, quantity) | Add a mount cargo item to assigned cargo |
| removeAssignedCargoMount | method(dbid, quantity) | Remove a mount cargo item from assigned cargo |
| createFlightPlans | method({}) | Create mission flight plans — call: `mission:createFlightPlans({ DATEONTARGET=..., TIMEONTARGET=... })` |
| updateWPtimes | method() | Refresh the flight WP times — call: `mission:updateWPtimes()` (**not** `.updateWPtimes()`) |

### Mount
| Field | Type | Description |
| :--- | :--- | :--- |
| armor | number | Armor rating on mount |
| capacity | number | Total capacity of mount |
| dbid | number | Database ID |
| guid | string | GUID of mount |
| rof | number | Mount reload time |
| weapons | { WeaponLoaded, ... } | Table of weapon loads on mount |
| setExactWeaponQuantity | method( guid, quantity) | Sets the current load of the weapon defined by 'guid' to the value 'quantity' |

### Operation
| Field | Type | Description |
| :--- | :--- | :--- |
| LHourMission | Mission | The mission designated to start at L-Hour. As soon as the L-Hour is reached, the mission will change phase to “Running”. |
| HHourMission | Mission | The mission designated to start at H-Hour. As soon as the H-Hour is reached, the mission will change phase to “Running”. |
| HHour | string | The time set as H-Hour. |
| LHour | string | The time set as L-Hour. |
| HHourEffectiveStartTime | string | The effective time at which the H-Hour started counting. Sometimes the actual H-Hour can be different from the one planned initially, or in the past. READ ONLY |
| LHourEffectiveStartTime | string | The effective time at which the L-Hour started counting. Sometimes the actual L-Hour can be different from the one planned initially, or in the past. READ ONLY |
| H_LHourAreRelative | True/False | Whether or not the H-Hour and the L-Hour have a static time delta. With this option on TRUE, the H-hour and L-hour will always have the same time difference and will adjust automatically when changing either the H-Hour or the L-Hour |

### ReferencePoint
| Field | Type | Description |
| :--- | :--- | :--- |
| bearingtype | bearingTypefixed = 0 rotating = 1 | Type of bearing to 'relativeto' unit |
| color | string | The HTML color code expressed as a number - convert to hex to check against a HTML color chart |
| guid | string | The unique identifier for the reference point |
| highlighted | True/False | True if the point should be selected |
| latitude | Latitude | The latitude of the reference point |
| locked | True/False | True if the point is locked |
| longitude | Longitude | The longitude of the reference point |
| name | string | The name of the reference point |
| relativeDistance | number | Relative distance of RP to 'relativeto' unit |
| relativeBearing | number | Relative bearing ( 0 - 360) of RP to 'relativeto' unit |
| relativeto | Unit | The unit that the reference point is relative to |
| relativeto_type | UnitType | The type of unit being used for the relative to part (contact, rp, or type on actual unit) |
| side | string | The side the reference point is visible to |

### Scenario
| Field | Type | Description |
| :--- | :--- | :--- |
| CampaignID | string | Campaign guid |
| CampaignSessionID | string | Current campaign session id |
| CampaignScore | number | Current campaign score |
| Complexity | number | Complexity rating |
| CurrentTime | number | Current scenario time as a number (of seconds) equivalent |
| CurrentTime | string | Current scenario time |
| DBUsed | string | Name of database being used |
| Difficulty | number | Difficulty rating |
| Duration | string | Length of scenario as days:hours:minutes:seconds |
| DurationNum | number | Length of scenario as a number (of seconds) equivalent |
| FileName | string | Name of the scenario file (.scen/.save) |
| guid | string | Current scenario GUID |
| HasStarted | True/False | Scenario in play |
| InCampaignMode | True/False | Currently in campaign mode |
| PlayerSide | string | Current player side GUID |
| SaveVersion | string | Game version last saved under |
| ScenDate | number | Year of settings |
| ScenSetting | string | The setting of the scenario |
| Sides | number | Number of sides in scenario |
| StartTime | string | Starting time |
| StartTimeNum | number | Starting time as a number (of seconds) equivalent |
| Title | string | Title of the scenario |
| TimeCompression | number | Compression mode |
| ResetLossExp | method() | Clears the loss and expenditure logs in scenario |
| ResetScore | method() | Clears the score and log in scenario |

### Sensor
| Field | Type | Description |
| :--- | :--- | :--- |
| altitudes | { min, max } | Returns a table of altitudes |
| dbid | string | The DBID of the sensor. |
| guid | string | The GUID of the sensor. |
| MaxElevationAngle | number | The maximum elevation of the sensor (applicable to Satellite)PRO ONLY |
| MinElevationAngle | number | The minimum elevation of the sensor (applicable to Satellite)PRO ONLY |
| name | string | The name of the sensor. |
| role | string | The role of the sensor (e.g. 3D Air Search - Medium Range). |
| ranges | { min, max } | Returns a table of ranges |
| scaninterval | number | The scanning interval of the sensor. READ ONLY unless PRO ONLY |
| type | string | The high-level type of sensor. |
| IsPreciseCheck | method( detector, detected) | Returns True/False |
| RangeAgainstTarget | method( detector, detected) | Returns a table of { maxIR, MaxVisual } as max range between units for IR and Visual |

### Serial
| Field | Type | Description |
| :--- | :--- | :--- |
| ID | ID | The serial’s visible ID. |
| AssociatedMothership | string | The GUID of the mothership this chalk is associated to.READ ONLY |
| LargestCargoType | LargestCargoTypeNoCargo = 0 Personnel = 1000 SmallCargo = 2000 MediumCargo = 3000 LargeCargo = 4000 VLargeCargo = 5000 | Get the largest cargo this serial currently contains. READ ONLY |
| Mass | number | The total mass of the serial.READ ONLY |
| Area | number | The total area taken by the serial.READ ONLY |
| PAX | number | The total personnel this serial contains.READ ONLY |

### Side
| Field | Type | Description |
| :--- | :--- | :--- |
| canAutoTrackCivillians | True/False | Auto track civilians |
| Chalks | { Serial, ... } | Table of serials within the Chalk.READ ONLY |
| collectiveResponsibility | True/False | Collective Responsibility |
| computerControlledOnly | True/False | AI controlled only |
| contacts | { UnitList } | Table of current contacts for the designated side. The 'guid' in table are contact references READ ONLY |
| doctrine | Doctrine | READ ONLY |
| customenvironmentzones | { { giud, description, name }, ... } | Table of Zone identifiers for the designated side READ ONLY |
| exclusionzones | { { giud, description, name }, ... } | Table of Zone identifiers for the designated side READ ONLY |
| expenditures | { {type,dbid,name,number}, ... } | A table of expenditure to date |
| guid | string | The GUID of the side. |
| hasmines | True/False | READ ONLY |
| losses | { {type,dbid,name,number}, ... } | A table of losses to date |
| missions | { Mission, ... } | A table of missions on the side |
| name | string | The name of the side. |
| nonavzones | { { giud, description, name }, ... } | Table of Zone identifiers for the designated side READ ONLY |
| Operation | Operation | READ ONLY |
| rps | { RP, ... } | RPs for the designated side READ ONLY |
| units | { UnitList } | Table of units for the designated side. READ ONLY |
| standardzones | { { giud, description, name }, ... } | Table of Zone identifiers for the designated side READ ONLY |
| enablers | { Enablers } | Table of enablers for the designated side. |
| contactsBy | method(UnitType) | Returns table UnitList of current contacts filtered by type of unit or nil. |
| getcustomenvironmentzone | method(ZoneGUID|ZoneName|ZoneDescription) | Returns matching Zone or nil |
| getexclusionzone | method(ZoneGUID|ZoneName|ZoneDescription) | Returns matching Zone or nil |
| getnonavzone | method(ZoneGUID|ZoneName|ZoneDescription) | Returns matching Zone or nil |
| getstandardzone | method(ZoneGUID|ZoneName|ZoneDescription) | Returns matching Zone or nil |
| unitsBy | method(UnitType[[,Category],Subtype]) | Returns table UnitList of units , optionally filtered or nil. |
| unitsInArea | method({Area[,TargetFilter]}) | Returns table UnitList of units in area, optionally filtered |

### Special action
| Field | Type | Description |
| :--- | :--- | :--- |
| description | string | The event GUID. |
| guid | string | The event GUID. READ ONLY |
| isActive | True/False | The event is active |
| isRepeatable | True/False | The event repeats |
| name | string | The event name. |
| ScriptText | string | The Lua script |
| side | string | The side GUID |

### Unit
| Field | Type | Description |
| :--- | :--- | :--- |
| AI_EvaluateTargets_enabled | True/False | AI evaluates targets |
| AI_DeterminePrimaryTarget_enabled | True/False | AI determines primary target |
| airbornetime | datetime | how long aircraft has been flying as "days:hours:minutes:seconds". READ ONLY |
| airbornetime_v | number | how long aircraft has been flying in seconds. READ ONLY |
| AllowMultiMission | True/False | Is the mission allowed to have multiple missions assigned to it and will it be considered by the operation planner logic ? |
| altitude | number | The altitude of the unit in meters. |
| areaTriggersFired | { string, ... } | Table of active 'in area' triggers (GUID) that have fired for unit |
| ascontact | { {side, guid, name}, ... } | A table of how this unit is seen from the other sides (as contacts). READ ONLY |
| AssignedMissionsQueue | { mission_guid, ... } | The list of missions assigned to this unit. This is the missions the operation planner evaluate every tick. |
| assignedUnits | { Boats, Aircraft } | Table of boats and aircraft GUID assigned to the unit (base). |
| autodetectable | True/False | True if the unit is automatically detected. |
| avoidCavitation | True/False | Avoid cavitation 'True/False' |
| base | Unit | The unit's assigned base. |
| beingPickedUp | True/False | unit is marked to be pickedup |
| cargo | { Cargo, ... } | Unit's current cargo |
| category | String | The unit category code (as a string rather than a number) for the Aircraft, Facility, Ship, Submarine or Satellite. |
| classname | string | Unit class name READ ONLY |
| components | { Component, ... } | A table of components on the unit. READ ONLY |
| condition | string | Message on unit dock/air ops status. READ ONLY |
| condition_v | string | Docking/Air Ops condition value. READ ONLY |
| course | WayPoint | The unit's course, as a table of waypoints (latitude,longitude) |
| crew | number | crew size (nil if not defined) READ ONLY |
| damage | { DP, FLOOD, FIRES, STARTDP, DP_PERCENT, DP_PERCENT_NOW } | Table of start and current DP, flood and fire level, and the damage percentage of unit. READ ONLY |
| doctrine | Doctrine | READ ONLY |
| dbid | number | The database ID of the unit READ ONLY |
| desiredAltitude | number | unit desired altitude to go to |
| desiredSpeed | number | unit desired speed to go to |
| desiredHeading | number | unit desired heading to go to |
| desiredPitch | number | unit desired pitch to go to if is controlable else nil |
| desiredRoll | number | unit desired roll to go to |
| embarkedUnits | { Boats, Aircraft } | Table of boats and aircraft GUID docked/embarked on the unit |
| currentExhaustion | time | Number of seconds toward exhaustion limit |
| maxExhaustion | time | Maximum seconds before exhaustion. |
| firedOn | { string, ... } | Table of guids that are firing on this unit (Note that the starting idex of this table is '0' rather than '1' as normal Lua tables) |
| firingAt | { string, ... } | Table of contact guids that this unit is firing at (Note that the starting idex of this table is '0' rather than '1' as normal Lua tables) |
| formation | { Formation, ... } | Table of unit's formation info {bearing, type (of bearing), distance, sprint (and drift) |
| fuel | { Fuel, ... } | A table of fuel types used by unit based on the type of fuel as the index. |
| fuels | { Fuel, ... } | A table of fuels used by unit. |
| fuelstate | string | Message on unit fuel status. READ ONLY |
| groundSpeed | number | aircraft or missile speed READ ONLY |
| group | Group | The unit's group. If setting the group, use a text name of an existing group or a new name to create a group. To remove unit from a group, use "none" as the name. |
| groupLead | set: string or get: Unit wrapper | The group lead if a group. If setting the group lead, use the name or GUID of the new lead unit. |
| guid | string | The unit's unique ID. READ ONLY |
| heading | number | The unit's heading . |
| holdfire | {air, surface, subsurface, land} | Doctrine WCS setting READ ONLY |
| holdposition | True/False | True if the unit should hold. |
| hostFacility | Facility | Where unit is hosted |
| IsBallisticMissile | True/False | is weapon a Ballistic Weapon READ ONLY |
| IsDecoy | True/False | is weapon a decoy READ ONLY |
| IsDestroyed | True/False | is unit destroyed (present until object purged) READ ONLY |
| isEscort | True/False | is unit asssigned to escort in mission READ ONLY |
| IsLoadedAsCargo | True/False | is unit being transferred as cargo READ ONLY |
| IsMine | True/False | is weapon a mine READ ONLY |
| IsNuke | True/False | is weapon a nuke READ ONLY |
| isSinking | True/False | is ship is sinking (which means it will still show as an 'active' unit READ ONLY |
| isOperating | True/False | is unit is operational, not landed or docked READ ONLY |
| IsUnguidedBallisticWeapon | True/False | is weapon a Unguided Ballistic Weapon READ ONLY |
| jammed | True/False | unit is being jammed READ ONLY |
| jammer | True/False | unit is acting as a jammer READ ONLY |
| latitude | Latitude | The latitude of the unit. |
| loadout | Loadout | current aircraft loadout as a wrapper. READ ONLY |
| loadoutdbid | number | current aircraft loadout DBID. READ ONLY |
| longitude | Longitude | The longitude of the unit . |
| magazines | { Magazine, ... } | A table of magazines (with weapon loads) in the unit or group. Can be updated by ScenEdit_AddWeaponToUnitMagazine READ ONLY |
| manualAltitude | string or number | Desired altitude/depth or 'OFF' to turn off manual mode |
| manualSpeed | string or number | Desired speed or 'OFF' to turn off manual mode |
| mission | Mission | The unit's assigned mission. Can be changed by setting to the Mission name or guid (calls ScenEdit_AssignUnitToMission). **Repo:** set **name**, not guid — see `ScenEdit_AssignUnitToMission` practical note. |
| mounts | { Mount, ... } | A table of mounts (with weapon loads) in the unit or group. Can be updated by ScenEdit_AddReloadsToUnit READ ONLY |
| name | string | The unit's name. |
| newname | string | If changing existing unit, the unit's new name . |
| noiseLevel | { front, side, rear } | Table containing the unit current decibel values if applicable, else nil |
| obeyEMCON | True/False | Unit obeys EMCON. Turn off to manually set sensors |
| oldDamagePercent | single | changes the last damage percent used by damage trigger |
| OODA | { evasion, targeting, detection } | Table contain unit's "observe, orient, decide, act" values |
| outOfComms | True/False | is unit connected to side comms network (false = connected) READ ONLY |
| pickedUpBy | GUID | The unit GUID that has picked up this unit (useful to the destroyed Event) |
| pickUpTarget | Unit | The unit being picked up. |
| pitch | number | unit pitch if is controlable else nilREAD ONLY |
| proficiency | string | The unit proficiency, "Novice"|0, "Cadet"|1,"Regular"|2, "Veteran"|3, "Ace"|4. |
| quickTurnaround | { QuickTurnaround } | Current quick turnaround values if an aircraft with a loadout |
| readytime | string [READ] or number [SET] | how long aircraft/ship takes to be ready as "days:hours:minutes:seconds". Set the time in seconds Can use 'TimeToReady_Minutes=' in SetUnit() to set the ready time in minutes for aircraft and ship/sub. |
| readytime_v | number | how long aircraft/ship takes to be ready in seconds. READ ONLY |
| SatelliteData | table | Satellite specific data (e.g., launchDate). (Bron: WhatsNew.pdf March 2026) |
| SubTypeN | number | Numeric subtype of the unit. (Bron: WhatsNew.pdf March 2026) |
| roll | number | unit roll READ ONLY |
| SAR_enabled | True/False | unit can conduct SAR |
| sensors | { Sensor, ... } | Unit sensor information |
| side | string | The unit's side. READ ONLY |
| signature | { Signature } | Table containing the unit signature profile (for the current loadout if an aircraft) if applicable, else nil |
| speed | number | The unit's current speed. |
| sprintDrift | True/False | Sprint and drift 'True/False' |
| subtype | string | The unit's subtype (if applicable). READ ONLY |
| target | object | The primary taget of the unit. On reading, it will return the targeted contact Contact On setting, supply a table of the contact/actual unit GUID or 'BOL' and the activation point (see ScenEdit_AttackContact) { guid = value } |
| targetedBy | { string, ... } | Table of unit guids that have this unit as a target (Note that the starting idex of this table is '0' rather than '1' as normal Lua tables) |
| deployDippingSonar | method(true) | Send the unit to deploy the dipping sonar. Parameter should be true/false. (Bron: WhatsNew.pdf March 2026) |
| dropSonobuoy | method(type, depth, time) | Send the unit to drop a sonobuoy. (Bron: WhatsNew.pdf March 2026) |
| throttle | Throttle | The unit's current throttle setting. |
| type | string | The type of object, may be 'Facility', 'Ship', 'Submarine', or 'Aircraft'.READ ONLY |
| unassign | True/False | unassign unit (performs basic actions of hotkey 'u') |
| unitstate | string | Message on unit status. READ ONLY |
| UseCustomIntermittentEmissionOnly | True/False | Activate the custom intermittent emissions |
| WasPickedUp | True/False | Unit was picked up? Useful when unit is destroyed after a pickup |
| weapon | { shooter, contact, detonated } | Table of shooter unit, at contact unit and detonated (when destroyed) if a weapon READ ONLY |
| weaponstate | string | Message on unit weapon status. READ ONLY |
| weather | { Weather } | Table of weather parameters (temp, rainfall, underrain, seastate) |
| delete | method() | Immediately removes unit object |
| filterOnComponent | method(type) | Filters unit on type of component and returns a Component table. |
| getwaypoint | method(guid=string) | Returns a Waypoint based on the GUID of the waypoint passed. |
| inArea | method({area}) | Is unit in the 'area' defined by table of RPs - returns True/False |
| Launch | method(True/False) | Trigger the unit to launch from base (true) or abort launch (false) |
| rangetotarget | method('contactid') | Calculate flat distance to a contact location |
| RTB | method() | Trigger the unit to return to base, or cancel an RTB. |
| updateorbit | method({TLE=...}) | Update the orbit for a satellite by specifying a TLE |
| createUnitCargo | method(type, dbid [,customname]) | Create an item in cargo area. Returns cargo |
| deleteUnitCargo | method(guid) | Delete cargo item by it's guid. Returns True/False |
| deployDippingSonar | method(true) | Send the unit to deploy the dipping sonar. Parameter should be true |
| dropSonobuoy | method(active, shallow) | where active = true for active sonobuoy, false for passive and shallow = true for above layer, and false for below |
| getUnitCargo | method(guid) | Get an item in cargo area. Returns cargo or nil |
| getUnitMagazine | method(mag_guid) | Get specific magazine GUID details. Returns magazine or nil |
| getUnitMountMagazine | method(mount_guid) | Get magazine details of the specific mount GUID. Returns magazine or nil |
| ReplenishUnit | method([{ tanker = ..., mission = {...}}]) | Send the unit to replenish. Returns { success, reason } success = false if method call fails, reason = why replenishment failed where blank reason means unit is set to replenish. |

### Zone
| Field | Type | Description |
| :--- | :--- | :--- |
| affects | unitTypes | List of unit types (ship, submarine, aircraft, facility) affected by a No-nav or exclusion zone. |
| area | { ZoneMarker, ... } | A set of reference points marking the zone. |
| areacolor | string | The HTML color code expressed as a number - convert to hex to check against a HTML color chart |
| description | string | The description of the zone. |
| AltitudeEnvelopeMin | number | Minimum altitude envelope for the area. (Bron: WhatsNew.pdf March 2026) |
| AltitudeEnvelopeMax | number | Maximum altitude envelope for the area. (Bron: WhatsNew.pdf March 2026) |
| enablers | { Enablers } | Table of enablers for the designated side. |
| guid | string | The GUID of the zone. READ ONLY |
| isactive | True/False | Zone is currently active. |
| hascustomlandcoverheight | True/False | Custom environment zone has a custom land cover height set. |
| landcoverheight | integer | The height of the land cover within a custom environment zone. |
| landcovertype | LandCoverType | The land cover type override (if any) within a custom environment zone. |
| locked | True/False | Zone is locked. |
| markas | Posture | Posture of violator of exclusion zone. |
| noFire | True/False | NoNav-Zone: is a no Fire zone? |
| name | string | The name of the zone. |
| type | string | The type of the zone. READ ONLY |
| thermallayerceiling | integer | The depth of the thermal layer ceiling within a custom environment zone. |
| thermallayerfloor | integer | The depth of the thermal layer floor within a custom environment zone. |
| thermallayerstrength | single | The strength of the thermal layer within a custom environment zone. |
| convergencezoneinterval | single | The interval (in nm) between convergence zones within a custom environment zone. |
| weatherprofile | table | The weather profile within a custom environment zone. |

### WayPoint
| Field | Type | Description |
| :--- | :--- | :--- |
| actionId | string | The Event Action GUID that will execute when this waypoint is reached. Use the normal Event Editor to create these types of events which can be added under Waypoint editing |
| altitude | number | Location altitude/depth in meters |
| description | string | Description |
| desiredAltitude | number | Desired altitude/depth in meters |
| desiredSpeed | number | Desired speed |
| guid | string | GUID defining waypoint |
| latitude | latitude | Location latitude |
| longitude | longitude | Location longitude |
| name | string | Name |
| presetAltitude | PresetAltitude | Using preset |
| presetDepth | PresetDepth | Using preset |
| presetThrottle | PresetThrottle | Using preset |
| TF | True/False | Altitude using terrain following |
| type | WaypointType | Type of waypoint |
| ToTableWrapper | method() | Returns the waypoint as a Lua table. (Bron: WhatsNew.pdf March 2026) |
| FromTableWrapper | method(table) | Updates the waypoint from a Lua table. (Bron: WhatsNew.pdf March 2026) |

### Weapon
| Field | Type | Description |
| :--- | :--- | :--- |
| boost | number | Boost-coast property: boost phase duration. (Bron: WhatsNew.pdf March 2026) |
| endurance | number | Boost-coast property: total endurance. (Bron: WhatsNew.pdf March 2026) |
| classname | string | The class of weapon. |
| dbid | number | The database ID of the weapon. |
| directors | table | directors that can control weapon |
| guid | string | The GUID of this weapon. |
| guidance | number | Guidance device code |
| launchLimits | table | launch altitude limits of weapon at general target types. |
| name | string | The name of the weapon. |
| OODA | table | The OODA. |
| ranges | table | range of weapon at general target types. |
| sensors | table | sensors carried by weapon |
| subtype | string | Description of weapon subtype |
| subtypeN | number | Numeric value of weapon subtype |
| targetLimits | table | target altitude limits of weapon at general target types. |
| type | string | The type of weapon. |
| validTargetList | table | valid target list applicable |
| warheads | table | warheads carried by weapon |

## Enumerations & Constants

### Altitude
Altitude is the height or depth of a unit. The altitude is displayed in meters when accessing the
                    data. It can be set using either meters or feet by adding M or FT after it. The default is M if just
                    a number is used.
                    The short keyword 'alt' can be used in a Lua table parameter that allows 'altitude'. Arcs for sensor and mounts.

- 1001 = None
- 1005 = Armor_Handgun
- 1010 = Armor_Rifle
- 1015 = Armor_HMG
- 1020 = RHA_20mm
- 1025 = RHA_25mm
- 1030 = RHA_30mm
- 1035 = RHA_35mm
- 2001 = Light
- 2002 = Medium
- 2003 = Heavy
- 2004 = Special

---

### Arc
Arcs for sensor and mounts.

- 1001 = None
- 1005 = Armor_Handgun
- 1010 = Armor_Rifle
- 1015 = Armor_HMG
- 1020 = RHA_20mm
- 1025 = RHA_25mm
- 1030 = RHA_30mm
- 1035 = RHA_35mm
- 2001 = Light
- 2002 = Medium
- 2003 = Heavy
- 2004 = Special

---

### Armor rating
- 1001 = None
- 1005 = Armor_Handgun
- 1010 = Armor_Rifle
- 1015 = Armor_HMG
- 1020 = RHA_20mm
- 1025 = RHA_25mm
- 1030 = RHA_30mm
- 1035 = RHA_35mm
- 2001 = Light
- 2002 = Medium
- 2003 = Heavy
- 2004 = Special

---

### Autonomy Levels
- 6000 - Fully Autonomous
- 5000 - Battlespace Cognizant
- 4000 - Multi-Vehicle Coordination
- 3000 - Fault/Event Adaptive
- 2000 - Changeable Mission
- 1500 - Self - Recovering

---

### Awareness
- -1 = Blind
- 0 = Normal
- 1 = AutoSideID
- 2 = AutoSideAndUnitID
- 3 = Omniscient

---

### CargoObjectType
- 0 = None
- 1 = Mount
- 2 = Vehicle
- 3 = Facility
- 4 = CargoContainer
- 5 = CargoContainerContent

---

### CargoStorageType
- 0 = StoredInternal
- 1 = StoredExternal
- 2 = TowedExternal

---

### CargoType
- 0 = NoCargo
- 1000 = Personnel
- 2000 = SmallCargo
- 3000 = MediumCargo
- 4000 = LargeCargo
- 5000 = VLargeCargo

---

### ContactIdStatus
- 0 = Unknown
- 1 = KnownDomain
- 2 = KnownType
- 3 = KnownClass
- 4 = PreciseID

---

### ContactType
- 00 = Air
- 01 = Missile
- 02 = Surface
- 03 = Submarine
- 05 = Aimpoint
- 06 = Orbital
- 07 = Facility_Fixed
- 08 = Facility_Mobile
- 09 = Torpedo
- 10 = Mine
- 11 = Explosion
- 13 = Decoy_Air
- 14 = Decoy_Surface
- 15 = Decoy_Land
- 16 = Decoy_Sub
- 17 = Sonobuoy
- 18 = Installation
- 19 = AirBase
- 20 = NavalBase
- 21 = MobileGroup
- 22 = ActivationPoint

---

### DateTime
DateTime is displayed and changed as per LOCALE e.g. US would be 'MM/DD/YYYY HH:MM:SS AM/PM' eg
                    '8/13/2002 12:14 PM'

- 0 = Ignore
- 1 = Optimistic
- 2 = Pessimistic

---

### Doctrine/ROE
- 0 = Ignore
- 1 = Optimistic
- 2 = Pessimistic

---

### Fuel
The various types of fuel(s), and their state, carried by the unit. Use ScenEdit_SetUnit() to
                    set
                    the fuel
                    rather
                    than through the wrapper unit.fuel. 
                    Using ScenEdit_SetUnit({...,fuel={{'GasFuel',1500},{2001,8000}}..}) is easier
                    and
                    less prone
                    to
                    error; you can use the fuel name or the fuel number code. Unit fuel exists as Lua table with the 'type of fuel' as the index. There may be more than one type returned as in AO class ships.
                    Each element of the fuel table has the items:

- current
                            number
                            The current fuel level of the type
- max
                            number
                            How much can be stored for the type
- name
                            string
                            Name of the fuel type (which will relect the fuel type index)
- type
                            number
                            Type of fuel

---

### GUID
Each object in Command is uniquely identified by a GUID. A GUID is an acronyom that stands for Globally Unique Identifier. It is a 32 character reference id that is highly unlikely to repeat when generated. An example of the GUID is '3b28032f-446d-43a1-bc49-4f88f5fb1cc1'.
                    The GUID of an object will not change once it is created.
                    As such once created, the GUID can't be changed and thus will always be treated as READ ONLY. When adding some
                    objects, the designer can assign a custom GUID, and once assigned it will be treated as if generated by the system. The GUID is often used to identify objects to run functions and is not prone to errors if the unit name is changed. The simulation allows for user data to be stored within the save file. This is done by associating
                    keys with values. Key and value pairs added to
                    the persistent store are retained when the game is saved and resumed. Keys with
                    values are both represented as non-nil 
                        strings
                    .

- 0 = Water
- 1 = Evergreen needleleaf forest
- 2 = Evergreen broadleaf forest
- 3 = Deciduous needleleaf forest
- 4 = Deciduous broadleaf forest
- 5 = Mixed Forest
- 6 = Closed Shrublands
- 7 = Open Shrublands
- 8 = Woody savannas
- 9 = Savannas
- 10 = Grasslands
- 11 = Permanent Wetlands
- 12 = Croplands
- 13 = Urban and built up
- 14 = Croplands and natural vegetation mosaic
- 15 = Snow and ice
- 16 = Barren or sparsely vegetated
- 201 = Urban close inner city
- 202 = Urban spaced high rise
- 203 = Urban attached houses
- 204 = Urban close industrial
- 205 = Urban spaced apartments
- 206 = Urban detached houses
- 207 = Urban spaced industrial
- 208 = Urban shanty town
- 254 = Unclassified
- 255 = User underyling data (Custom Environmnet Zone does not override land cover.)

---

### KeyStore
The simulation allows for user data to be stored within the save file. This is done by associating
                    keys with values. Key and value pairs added to
                    the persistent store are retained when the game is saved and resumed. Keys with
                    values are both represented as non-nil 
                        strings
                    .

- 0 = Water
- 1 = Evergreen needleleaf forest
- 2 = Evergreen broadleaf forest
- 3 = Deciduous needleleaf forest
- 4 = Deciduous broadleaf forest
- 5 = Mixed Forest
- 6 = Closed Shrublands
- 7 = Open Shrublands
- 8 = Woody savannas
- 9 = Savannas
- 10 = Grasslands
- 11 = Permanent Wetlands
- 12 = Croplands
- 13 = Urban and built up
- 14 = Croplands and natural vegetation mosaic
- 15 = Snow and ice
- 16 = Barren or sparsely vegetated
- 201 = Urban close inner city
- 202 = Urban spaced high rise
- 203 = Urban attached houses
- 204 = Urban close industrial
- 205 = Urban spaced apartments
- 206 = Urban detached houses
- 207 = Urban spaced industrial
- 208 = Urban shanty town
- 254 = Unclassified
- 255 = User underyling data (Custom Environmnet Zone does not override land cover.)

---

### LandCover
- 0 = Water
- 1 = Evergreen needleleaf forest
- 2 = Evergreen broadleaf forest
- 3 = Deciduous needleleaf forest
- 4 = Deciduous broadleaf forest
- 5 = Mixed Forest
- 6 = Closed Shrublands
- 7 = Open Shrublands
- 8 = Woody savannas
- 9 = Savannas
- 10 = Grasslands
- 11 = Permanent Wetlands
- 12 = Croplands
- 13 = Urban and built up
- 14 = Croplands and natural vegetation mosaic
- 15 = Snow and ice
- 16 = Barren or sparsely vegetated
- 201 = Urban close inner city
- 202 = Urban spaced high rise
- 203 = Urban attached houses
- 204 = Urban close industrial
- 205 = Urban spaced apartments
- 206 = Urban detached houses
- 207 = Urban spaced industrial
- 208 = Urban shanty town
- 254 = Unclassified
- 255 = User underyling data (Custom Environmnet Zone does not override land cover.)

---

### Latitude
Latitude is degrees N or S of the equator as 'S 60.20.10' or as +/- as -60.336. The data in the
                    tables is held as a signed number.
                    The short keyword 'lat' can be used in a Lua table parameter that allows 'latitude'.

- 1001 = None
- 2001 = Intercept_BVR
- 2002 = Intercept_WVR
- 2003 = AirSuperiority_BVR
- 2004 = AirSuperiority_WVR
- 2005 = PointDefence_BVR
- 2006 = PointDefence_WVR
- 2007 = GunsOnly
- 2101 = AntiSatellite_Intercept
- 2102 = AirborneLaser
- 3001 = LandNaval_Strike
- 3002 = LandNaval_Standoff
- 3003 = LandNaval_SEAD_ARM
- 3004 = LandNaval_SEAD_TALD
- 3005 = LandNaval_DEAD
- 3101 = LandOnly_Strike
- 3102 = LandOnly_Standoff
- 3103 = LandOnly_SEAD_ARM
- 3104 = LandOnly_SEAD_TALD
- 3105 = LandOnly_DEAD
- 3201 = NavalOnly_Strike
- 3202 = NavalOnly_Standoff
- 3203 = NavalOnly_SEAD_ARM
- 3204 = NavalOnly_SEAD_TALD
- 3205 = NavalOnly_DEAD
- 3401 = BAI_CAS
- 3501 = Buddy_Illumination
- 4001 = OECM
- 4002 = AEW
- 4003 = CommandPost
- 4004 = ChaffLaying
- 4101 = SearchAndRescue
- 4102 = CombatSearchAndRescue
- 4201 = MineSweeping
- 4202 = MineRecon
- 4301 = NavalMineLaying
- 6001 = ASW_Patrol
- 6002 = ASW_Attack
- 7001 = Forward_Observer
- 7002 = Area_Surveillance
- 7003 = Armed_Recon
- 7004 = Unarmed_Recon
- 7005 = Maritime_Surveillance
- 7101 = Paratroopers
- 7102 = Troop_Transport
- 7201 = Cargo
- 8001 = AirRefueling
- 8101 = Training
- 8102 = TargetTow
- 8103 = TargetDrone
- 9001 = Ferry
- 9002 = Unavailable
- 9003 = Reserve
- 9004 = ArmedFerry

---

### LoadoutRole
- 1001 = None
- 2001 = Intercept_BVR
- 2002 = Intercept_WVR
- 2003 = AirSuperiority_BVR
- 2004 = AirSuperiority_WVR
- 2005 = PointDefence_BVR
- 2006 = PointDefence_WVR
- 2007 = GunsOnly
- 2101 = AntiSatellite_Intercept
- 2102 = AirborneLaser
- 3001 = LandNaval_Strike
- 3002 = LandNaval_Standoff
- 3003 = LandNaval_SEAD_ARM
- 3004 = LandNaval_SEAD_TALD
- 3005 = LandNaval_DEAD
- 3101 = LandOnly_Strike
- 3102 = LandOnly_Standoff
- 3103 = LandOnly_SEAD_ARM
- 3104 = LandOnly_SEAD_TALD
- 3105 = LandOnly_DEAD
- 3201 = NavalOnly_Strike
- 3202 = NavalOnly_Standoff
- 3203 = NavalOnly_SEAD_ARM
- 3204 = NavalOnly_SEAD_TALD
- 3205 = NavalOnly_DEAD
- 3401 = BAI_CAS
- 3501 = Buddy_Illumination
- 4001 = OECM
- 4002 = AEW
- 4003 = CommandPost
- 4004 = ChaffLaying
- 4101 = SearchAndRescue
- 4102 = CombatSearchAndRescue
- 4201 = MineSweeping
- 4202 = MineRecon
- 4301 = NavalMineLaying
- 6001 = ASW_Patrol
- 6002 = ASW_Attack
- 7001 = Forward_Observer
- 7002 = Area_Surveillance
- 7003 = Armed_Recon
- 7004 = Unarmed_Recon
- 7005 = Maritime_Surveillance
- 7101 = Paratroopers
- 7102 = Troop_Transport
- 7201 = Cargo
- 8001 = AirRefueling
- 8101 = Training
- 8102 = TargetTow
- 8103 = TargetDrone
- 9001 = Ferry
- 9002 = Unavailable
- 9003 = Reserve
- 9004 = ArmedFerry

---

### LoadoutTimeOfDay
- 1001 = None
- 2001 = DayNight
- 2002 = NightOnly
- 2003 = DayOnly

---

### LoadoutWeather
- 1001 = None
- 2001 = AllWeather
- 2002 = LimitedAllWeather
- 2003 = ClearWeather

---

### Longitude
Longitude is degrees E or W of Greenwich line as 'W 60.20.10' or as +/- as -60.336. The data in the
                    tables is held as a signed number.
                    The short keyword 'lon' can be used in a Lua table parameter that allows 'longitude'. Mission Type

- Strike
						
							Mission Subtype
							AIR  [, AAW, Air_Intercept ]
                            LAND [, SUR_LAND, Land_Strike ]
                            SEA  [, NAVAL, SUR_SEA, Maritime_Strike ]
                            SUB  [, ASW, Sub_Strike ]
- Mission Subtype
- AIR  [, AAW, Air_Intercept ]
- LAND [, SUR_LAND, Land_Strike ]
- SEA  [, NAVAL, SUR_SEA, Maritime_Strike ]
- SUB  [, ASW, Sub_Strike ]
- Patrol
						
							Mission Subtype
                            ASW   [, SUB ]
                            NAVAL [, SUR_SEA, ASuW_Naval ] 
                            AAW   [, AIR ]
                            LAND  [, SUR_LAND, ASuW_Land ]
                            MIXED [, SUR_MIXED, ASuW_Mixed ]
                            SEAD
                            SEA   [, SeaControl ]
- Mission Subtype
- ASW   [, SUB ]
- NAVAL [, SUR_SEA, ASuW_Naval ]
- AAW   [, AIR ]
- LAND  [, SUR_LAND, ASuW_Land ]
- MIXED [, SUR_MIXED, ASuW_Mixed ]
- SEAD
- SEA   [, SeaControl ]
- Support
- Ferry
- Mining
- Mineclearing
- Cargo

---

### Type of mission
Mission Type

- Strike
						
							Mission Subtype
							AIR  [, AAW, Air_Intercept ]
                            LAND [, SUR_LAND, Land_Strike ]
                            SEA  [, NAVAL, SUR_SEA, Maritime_Strike ]
                            SUB  [, ASW, Sub_Strike ]
- Mission Subtype
- AIR  [, AAW, Air_Intercept ]
- LAND [, SUR_LAND, Land_Strike ]
- SEA  [, NAVAL, SUR_SEA, Maritime_Strike ]
- SUB  [, ASW, Sub_Strike ]
- Patrol
						
							Mission Subtype
                            ASW   [, SUB ]
                            NAVAL [, SUR_SEA, ASuW_Naval ] 
                            AAW   [, AIR ]
                            LAND  [, SUR_LAND, ASuW_Land ]
                            MIXED [, SUR_MIXED, ASuW_Mixed ]
                            SEAD
                            SEA   [, SeaControl ]
- Mission Subtype
- ASW   [, SUB ]
- NAVAL [, SUR_SEA, ASuW_Naval ]
- AAW   [, AIR ]
- LAND  [, SUR_LAND, ASuW_Land ]
- MIXED [, SUR_MIXED, ASuW_Mixed ]
- SEAD
- SEA   [, SeaControl ]
- Support
- Ferry
- Mining
- Mineclearing
- Cargo

---

### Presets
- 0 = FullStop
- 1 = Loiter
- 2 = Cruise
- 3 = Full
- 4 = Flank
- 5 = None

---

### Proficiency
- 0 = Novice
- 1 = Cadet
- 2 = Regular
- 3 = Veteran
- 4 = Ace

---

### Scenario Realism Settings
- DetailedGunFireControl = Detailed gun fire-contorl
- UnlimitedBaseMagazines = Unlimited magazines at air/naval bases
- AircraftDamage = Aircraft Damage
- RealisticSubComms = Realistic Submarine Communications
- LandTypeEffects = Effects of Terrain Type
- LandTypeEffects_Advanced = Effects of Terrain Type - ADVANCED
- CommsDisruption = Communications Disruption
- WeatherAffectsShipSpeed = Weather affects ship speed
- AllowLandingPlannerInstantLoading = Allow instant load for the landing planner (Pro Only)
- ACS_NAW_Limitations = Weather and day/night affect aircraft sorties

---

### Sensor type and role
- 1001 = None
- 2001 = Radar
- 2002 = SemiActive
- 2003 = Visual
- 2004 = Infrared
- 2005 = TVM
- 3001 = ESM
- 3002 = ECM
- 3003 = EMP_Projector
- 3004 = PCLS
- 4001 = LaserDesignator
- 4002 = LaserSpotTracker
- 4003 = LaserRangefinder
- 5001 = HullSonar_PassiveOnly
- 5002 = HullSonar_ActivePassive
- 5003 = HullSonar_ActiveOnly
- 5011 = TowedArray_PassiveOnly
- 5012 = TowedArray_ActivePassive
- 5013 = TowedArray_ActiveOnly
- 5021 = VDS_PassiveOnly
- 5022 = VDS_ActivePassive
- 5023 = VDS_ActiveOnly
- 5031 = DippingSonar_PassiveOnly
- 5032 = DippingSonar_ActivePassive
- 5033 = DippingSonar_ActiveOnly
- 5041 = BottomFixedSonar_PassiveOnly
- 5101 = MAD
- 5901 = PingIntercept
- 6001 = MineSweep_MechanicalCableCutter
- 6002 = MineSweep_MagneticInfluence
- 6003 = MineSweep_AcousticInfluence
- 6004 = MineSweep_MultiInfluence
- 6011 = MineSweep_TwoShipMagneticInfluence
- 6021 = MineNeutralization_MooredMineCableCutter
- 6022 = MineNeutralization_ExplosiveChargeMineDisposal
- 6031 = MineNeutralization_DiverExplosiveCharge
- 8001 = NonDetectingEmitter
- 9001 = SensorGroup

---

### Size
Size various size attributes (eg flightsize in mission). When setting the value, either the number or the description (in quotes) can be used.

- 0 = None*
- 1 = SingleAircraft
- 2 = TwoAircraft
- 3 = ThreeAircraft
- 4 = FourAircraft
- 6 = SixAircraft
- 0   = None
- 1   = Flight_x1
- 2   = Flight_x2
- 3   = Flight_x3
- 4   = Flight_x4
- 6   = Flight_x6
- 8   = Flight_x8
- 12  = Flight_x12
- All = All
- 0 = None*
- 1 = SingleVessel
- 2 = TwoVessel
- 3 = ThreeVessel
- 4 = FourVessel
- 6 = SixVessel

---

### Stance
Stance/Posture: how one side sees another. When setting the value, either the number or the description (in quotes) can be used. 
                    In some cases, the single letter code must be used; this is indicated by "Stance(letter)"

- 0 = Neutral 	 (N)
- 1 = Friendly 	 (F)
- 2 = Unfriendly 	 (U)
- 3 = Hostile 	 (H)
- 4 = Unknown 	 (X)

---

### TargetingMode
How is contact targeted.

- 0 = AutoTargeted
- 1 = ManualWeaponAlloc

---

### TargetTypeWRA
Target type for Weapon Release Authority.

- 1001 = None
- 1002 = Decoy
- 1999 = Air_Contact_Unknown_Type
- 2000 = Aircraft_Unspecified
- 2001 = Aircraft_5th_Generation
- 2002 = Aircraft_4th_Generation
- 2003 = Aircraft_3rd_Generation
- 2004 = Aircraft_Less_Capable
- 2011 = Aircraft_High_Perf_Bombers
- 2012 = Aircraft_Medium_Perf_Bombers
- 2013 = Aircraft_Low_Perf_Bombers
- 2021 = Aircraft_High_Perf_Recon_EW
- 2022 = Aircraft_Medium_Perf_Recon_EW
- 2023 = Aircraft_Low_Perf_Recon_EW
- 2031 = Aircraft_AEW
- 2032 = Aircraft_Class1UAS
- 2033 = Aircraft_Tanker
- 2034 = Aircraft_Class2UAS
- 2100 = Helicopter_Unspecified
- 2200 = Guided_Weapon_Unspecified
- 2201 = Guided_Weapon_Supersonic_Sea_Skimming
- 2202 = Guided_Weapon_Subsonic_Sea_Skimming
- 2203 = Guided_Weapon_Supersonic
- 2204 = Guided_Weapon_Subsonic
- 2211 = Guided_Weapon_Ballistic
- 2300 = Satellite_Unspecified
- 2400 = C_RAM
- 2999 = Surface_Contact_Unknown_Type
- 3000 = Ship_Unspecified
- 3001 = Ship_Carrier_0_25000_tons
- 3002 = Ship_Carrier_25001_45000_tons
- 3003 = Ship_Carrier_45001_95000_tons
- 3004 = Ship_Carrier_95000_tons
- 3101 = Ship_Surface_Combatant_0_500_tons
- 3102 = Ship_Surface_Combatant_501_1500_tons
- 3103 = Ship_Surface_Combatant_1501_5000_tons
- 3104 = Ship_Surface_Combatant_5001_10000_tons
- 3105 = Ship_Surface_Combatant_10001_25000_tons
- 3106 = Ship_Surface_Combatant_25001_45000_tons
- 3107 = Ship_Surface_Combatant_45001_95000_tons
- 3108 = Ship_Surface_Combatant_95000_tons
- 3201 = Ship_Amphibious_0_500_tons
- 3202 = Ship_Amphibious_501_1500_tons
- 3203 = Ship_Amphibious_1501_5000_tons
- 3204 = Ship_Amphibious_5001_10000_tons
- 3205 = Ship_Amphibious_10001_25000_tons
- 3206 = Ship_Amphibious_25001_45000_tons
- 3207 = Ship_Amphibious_45001_95000_tons
- 3208 = Ship_Amphibious_95000_tons
- 3301 = Ship_Auxiliary_0_500_tons
- 3302 = Ship_Auxiliary_501_1500_tons
- 3303 = Ship_Auxiliary_1501_5000_tons
- 3304 = Ship_Auxiliary_5001_10000_tons
- 3305 = Ship_Auxiliary_10001_25000_tons
- 3306 = Ship_Auxiliary_25001_45000_tons
- 3307 = Ship_Auxiliary_45001_95000_tons
- 3308 = Ship_Auxiliary_95000_tons
- 3401 = Ship_Merchant_Civilian_0_500_tons
- 3402 = Ship_Merchant_Civilian_501_1500_tons
- 3403 = Ship_Merchant_Civilian_1501_5000_tons
- 3404 = Ship_Merchant_Civilian_5001_10000_tons
- 3405 = Ship_Merchant_Civilian_10001_25000_tons
- 3406 = Ship_Merchant_Civilian_25001_45000_tons
- 3407 = Ship_Merchant_Civilian_45001_95000_tons
- 3408 = Ship_Merchant_Civilian_95000_tons
- 3501 = Submarine_Surfaced
- 3999 = Subsurface_Contact_Unknown_Type
- 4000 = Submarine_Unspecified
- 4999 = Land_Contact_Unknown_Type
- 5000 = Land_Structure_Soft_Unspecified
- 5001 = Land_Structure_Soft_Building_Surface
- 5002 = Land_Structure_Soft_Building_Reveted
- 5005 = Land_Structure_Soft_Structure_Open
- 5006 = Land_Structure_Soft_Structure_Reveted
- 5011 = Land_Structure_Soft_Aerostat_Moring
- 5100 = Land_Structure_Hardened_Unspecified
- 5101 = Land_Structure_Hardened_Building_Surface
- 5102 = Land_Structure_Hardened_Building_Reveted
- 5103 = Land_Structure_Hardened_Building_Bunker
- 5104 = Land_Structure_Hardened_Building_Underground
- 5105 = Land_Structure_Hardened_Structure_Open
- 5106 = Land_Structure_Hardened_Structure_Reveted
- 5200 = Runway_Facility_Unspecified
- 5201 = Runway
- 5202 = Runway_Grade_Taxiway
- 5203 = Runway_Access_Point
- 5300 = Emitter_Unspecified
- 5310 = Emitter_Radar
- 5320 = Emitter_Jammer
- 5400 = Mobile_Target_Soft_Unspecified
- 5401 = Mobile_Target_Soft_Mobile_Vehicle
- 5402 = Mobile_Target_Soft_Mobile_Personnel
- 5500 = Mobile_Target_Hardened_Unspecified
- 5501 = Mobile_Target_Hardened_Mobile_Vehicle
- 5601 = Underwater_Structure
- 5801 = Air_Base_Single_Unit_Airfield

---

### TimeStamp
TimeStamp is a representation of time defined as the number of seconds that have elapsed since 00:00:00 Coordinated Universal Time (UTC), Thursday, 1 January 1970 True/Yes = 1  False/No = 0

- 1 = Aircraft
- 2 = Ship
- 3 = Submarine
- 4 = Facility
- 5 = Aimpoint
- 6 = Weapon
- 7 = Satellite
- 8 = Ground unit

---

### True/False
True/Yes = 1  False/No = 0

- 1 = Aircraft
- 2 = Ship
- 3 = Submarine
- 4 = Facility
- 5 = Aimpoint
- 6 = Weapon
- 7 = Satellite
- 8 = Ground unit

---

### Unit type
- 1 = Aircraft
- 2 = Ship
- 3 = Submarine
- 4 = Facility
- 5 = Aimpoint
- 6 = Weapon
- 7 = Satellite
- 8 = Ground unit

---

### UnitAircraft
The category and sub-type for aircraft.

- 1001 = None
- 2001 = Fixed Wing
- 2002 = Fixed Wing, Carrier Capable
- 2003 = Helicopter
- 2004 = Tiltrotor
- 2006 = Airship
- 2007 = Seaplane
- 2008 = Amphibian

---

### UnitFacility
The category and sub-type for the various facility types

- 1001 = None
- 2001 = Runway
- 2002 = Runway-Grade Taxiway
- 2003 = Runway Access Point
- 3001 = Building (Surface)
- 3002 = Building (Reveted)
- 3003 = Building (Bunker)
- 3004 = Building (Underground)
- 3005 = Structure (Open)
- 3006 = Structure (Reveted)
- 4001 = Underwater
- 5001 = Mobile Vehicle(s)
- 5002 = Mobile Personnel
- 6001 = Aerostat Mooring
- 9001 = Air Base

---

### UnitSatellite
The category and sub-type for Satellite.

- 1001 = None
- 2001 = Geo-Stationary
- 2002 = Something Else
- 2003 = Unmanned Test Vehicle

---

### UnitShip
The category and sub-type for Ship.

- 1001 = None
- 2001 = Carrier (Aviation Ship)
- 2002 = Surface Combatant
- 2003 = Amphibious
- 2004 = Auxiliary
- 2005 = Merchant
- 2006 = Civilian
- 2007 = Surface Combatant (Aviation Capable)
- 2008 = Mobile Offshore Base (Aviation Capable)

---

### UnitSubmarine
The category and sub-type for Submarine.

- 1001 = None
- 2001 = Submarine
- 2002 = Biologics
- 2003 = False Target

---

### UI Windows
- orbat = Order of Battle
- missioneditor = Mission Editor
- speedalt = Throttle & Altitude
- exclusionzoneswindow = Exclusion Zone Window/li>
- nonavzoneswindow = No-navigation Zone Window
- consolewindow2 = Lua Console

---

### Waypoint
The type of waypoints (not all codes are used)

- 00 = ManualPlottedCourseWaypoint
- 01 = PatrolStation
- 02 = TerminalPoint
- 03 = LocalizationRun
- 04 = PathfindingPoint
- 05 = Assemble
- 06 = TurningPoint
- 07 = InitialPoint
- 10 = Target
- 11 = LandingMarshal
- 12 = StrikeIngress
- 13 = StrikeEgress
- 14 = Refuel
- 15 = TakeOff
- 17 = WeaponLaunch
- 18 = Land
- 19 = WeaponTarget
- 20 = StationStart_Racetrack
- 21 = StationStart_FigureEight
- 22 = StationStart_Area
- 23 = StationStart_RaceTrackRandom
- 24 = StationEnd
- 25 = PickupPoint
- 26 = HoldStart
- 27 = HoldEnd
- 28 = Launch
- 29 = Activation
- 30 = Termination

---

### WeaponDoctrine
- 0000 = LoadoutSetting (use setting from database)
- 2001 = Winchester (Vanilla Winchester - Out of weapons)
- 2002 = Winchester_ToO  (Same as above, but engage nearby bogies with guns after we're out of missiles. Applies to air-to-air missile loadouts only. For guns-only air-to-air loadouts and all air-to-ground loadouts the behaviour is the same as above. PREFERRED OPTION!
- 3001 = ShotgunBVR ( Disengage after firing all Beyond Visual Range (BVR, air-to-air) or Stand-Off (SO, air-to-ground) weapons. This is a risky option as your fighter aircraft may only have one medium-range air-to-air missile (AAM) left, and attempt to engage 'fresh' flights of bogies. Use with caution.)
- 3002 = ShotgunBVR_WVR ( Same as above, but if easy targets or threats are nearby then shoot at them with remaining Within Visual Range (WVR, air-to-air) or SR (Short-Range, air-to-ground) weapons before disengaging.)
- 3003 = ShotgunBVR_WVR_Guns ( Same as above, but also engage bogies with guns. Applies to air-to-air (A/A) loadouts only. For air-to-ground (A/G) loadouts the behaviour is the same as above.)
- 4001 = Shotgun25 ( Disengage after 1/4 of mission-specific weapons have been expended.)
- 4002 = Shotgun25_ToO ( Same as above, but if easy targets or threats are nearby then shoot at those too. Also engage bogies with guns. Applies to air-to-air (A/A) loadouts only.)
- 4011 = Shotgun50 ( Disengage after half of mission-specific weapons have been expended.)
- 4012 = Shotgun50_ToO ( Same as above, but if easy targets or threats are nearby then shoot at those too. Also engage bogies with guns. Applies to air-to-air (A/A) loadouts only.)
- 4021 = Shotgun75 ( Disengage after 3/4 of mission-specific weapons have been expended.)
- 4022 = Shotgun75_ToO ( Same as above, but if easy targets or threats are nearby then shoot at those too. Also engage bogies with guns. Applies to air-to-air (A/A) loadouts only.)
- 5001 = ShotgunOneEngagementBVR ( Make one engagement with BVR or SO weapons. Continue fighting for as long as there are targets within easy reach and then disengage. This is a safe option as it ensures aircraft do not 'hang around' after they have expended their most potent weapons, and becoming easy targets when engaged by 'fresh' enemy units.)
- 5002 = ShotgunOneEngagementBVR_Opportunity_WVR ( Same as above, but if easy targets or threats are nearby, shoot at them with remaining WVR or Short-Range weapons before disengaging. A target is considered 'easy' when within 120% of the remaining WVR or Strike weapon's maximum range. In other words, the fighter won't spend much energy chasing down a target after the Shotgun weapon state has been reached, and will leave the target area as quickly as possible. PREFERRED OPTION!)
- 5003 = ShotgunOneEngagementBVR_Opportunity_WVR_Guns ( Same as above, but also engage bogies with guns. Applies to air-to-air (A/A) loadouts only. For air-to-ground (A/G) loadouts the behaviour is the same as above.)
- 5005 = ShotgunOneEngagementBVR_And_WVR ( Make one engagement with BVR and WVR, or SO and Strike Weapons. Do not disengage when out of BVR or SO weapons, but continue the engagement with WVR weapons.)
- 5006 = ShotgunOneEngagementBVR_And_WVR_Opportunity_Guns
- 5011 = ShotgunOneEngagementWVR ( Make one engagement with WVR or SR weapons. Continue fighting for as long as there are targets within easy reach and then disengage.)
- 5012 = ShotgunOneEngagementWVR_Guns ( Same as above but also engage bogies with guns. Applies to air-to-air (A/A) loadouts only. For air-to-ground (A/G) loadouts, the behaviour is the same as above. PREFERRED OPTION!)
- 5021 = ShotgunOneEngagementGun ( Make one engagement with guns. Continue fighting for as long as there are targets nearby and then disengage.)

---

### WeaponType
- 1001 = None
- 2001 = GuidedWeapon
- 2002 = Rocket
- 2003 = IronBomb
- 2004 = Gun
- 2005 = Decoy_Expendable
- 2006 = Decoy_Towed
- 2007 = Decoy_Vehicle
- 2008 = TrainingRound
- 2009 = Dispenser
- 2010 = ContactBomb_Suicide
- 2011 = ContactBomb_Sabotage
- 2012 = GuidedProjectile
- 2014 = UAV_Expendable
- 3001 = SensorPod
- 3002 = DropTank
- 3003 = BuddyStore
- 3004 = FerryTank
- 4001 = Torpedo
- 4002 = DepthCharge
- 4003 = Sonobuoy
- 4004 = BottomMine
- 4005 = MooredMine
- 4006 = FloatingMine
- 4007 = MovingMine
- 4008 = RisingMine
- 4009 = DriftingMine
- 4011 = DummyMine
- 4101 = HeliTowedPackage
- 5000 = BallisticMissile
- 5001 = RV
- 5002 = PalletWeapon
- 6001 = Laser
- 6002 = Microwave
- 6003 = LaserDazzler
- 8001 = HGV
- 8003 = HypersonicCruiseMissile
- 9001 = Cargo
- 9002 = Troops
- 9003 = Paratroops

---

