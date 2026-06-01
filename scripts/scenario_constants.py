"""Constants for scenario preflight checks."""

import re

SEARCH_TABLES = [
    "DataAircraft",
    "DataShip",
    "DataSubmarine",
    "DataFacility",
    "DataWeapon",
    "DataGroundUnit",
]

_CARRIER_NAME_MARKERS = (
    "CVN ",
    "CV ",
    "CVA ",
    "CVB ",
    "CVL ",
    "CVH ",
)

_LHA_CARRIER_MARKERS = ("LHA ", "LHD ", "LPH ")

_ESCORT_NAME_MARKERS = (
    "DDG ",
    "CG ",
    "FFG ",
    "FF ",
    "GP ",
    "DESTROYER",
    "CRUISER",
    "FRIGATE",
    "CORVETTE",
)

_CSG_MIN_ESCORTS_ERROR = 2

_CSG_MIN_ESCORTS_WARN = 3

_CSG_ESCORT_MAX_DEG_DISTANCE = 0.55

_CSG_FORMATION_VARS = ("nimitz", "bunker_hill", "ddg51", "ddg51_escort")

_CSG_GROUP_MEMBER_VARS = ("nimitz", "ddg51", "ddg51_escort")

_CSG_GROUP_LEAD_VAR = "nimitz"

_CSG_STRIKE_SHIP_VAR = "bunker_hill"

_CSG_ESCORT_VARS = ("ddg51", "ddg51_escort")

_CSG_PATROL_MISSION = "csg station keeping"

_CSG_ALLOWED_SHIP_STRIKE_MISSIONS = ("caribbean tlam salvo",)

_CSG_SHIP_MISSIONS_BREAKING_FORMATION = (
    "csg asw screen",
    "carrier cap",
)

_CSG_LOCAL_PATROL_MAX_DEG = 1.5

_CSG_HELO_PATROL_MAX_DEG = 2.0

_CSG_LOCAL_MISSION_HINTS = (
    "carrier cap",
    "carrier aew",
    "csg asw",
    "csg asuw",
)

_THEATER_PATROL_ZONE_EXEMPT = (
    "sead escort",
    "wild weasel",
    "isr orbit",
    "havana cap",
    "eastern cap",
    "coastal defense",
)

_TOMAHAWK_CRUISE_KTS = 478

_CARRIER_STRIKER_CRUISE_KTS = 480

_BOMBER_TRANSIT_KTS = 420

_SEAD_TRANSIT_KTS = 500

_CARRIER_STRIKE_OVERHEAD_MIN = 22

_BOMBER_STARTUP_OVERHEAD_MIN = 12

_TOT_REACH_MARGIN_WARN_MIN = 8

_TOT_REACH_MARGIN_ERROR_MIN = 0

_NUCLEAR_LOADOUT_NAME_MARKERS = (
    "NUCLEAR",
    "TLAM-N",
    "TLAM N",
    "AGM-86B",
    "AGM-129",
    "BGM-109G",
    "SRAM",
    "B61",
    "B83",
    "W80",
    "W87",
    "W78",
    "B28 ",
    "B57 ",
)

_HELO_HOST_FACILITY_TYPES = frozenset({3001, 3002, 4001, 4002, 6001, 6002})

_BERTH_HOST_FACILITY_TYPES = frozenset({3001, 3002, 4001, 4002, 6001, 6002})

_RUNWAY_HOST_FACILITY_TYPES = frozenset({2001, 2002, 2003, 2004})

_AIRCRAFT_CATEGORY_HELICOPTER = 2003

_HOST_CAPACITY_RUNWAY_UNLIMITED = None

_PLACE_UNIT_CALLS = ("place_ship", "place_sub", "place_sam")

_FACILITY_PLACE_CALLS = ("place_base",)

_WRAPPER_INSTANCE_METHODS = (
    "updateWPtimes",
    "createFlightPlans",
    "refreshWaypoints",
    "insertWaypoint",
    "deleteWaypoint",
    "setExactWeaponQuantity",
    "addAssignedCargo",
    "removeAssignedCargo",
    "addAssignedCargoMount",
    "removeAssignedCargoMount",
    "DropContact",
    "ReplenishUnit",
    "RTB",
    "Launch",
    "updateorbit",
    "deployDippingSonar",
    "dropSonobuoy",
    "createUnitCargo",
    "deleteUnitCargo",
    "getUnitCargo",
    "inArea",
    "rangetotarget",
    "filterOnComponent",
    "getwaypoint",
    "ResetLossExp",
    "ResetScore",
    "ToTableWrapper",
    "FromTableWrapper",
)

_WRONG_WRAPPER_DOT_CALL = re.compile(
    r"\b\w+\.(" + "|".join(_WRAPPER_INSTANCE_METHODS) + r")\s*\(",
    re.IGNORECASE,
)

_STANDOFF_WEAPON_STATE_MARKERS = (
    "SHOTGUNBVR",
    "SHOTGUN_ONEENGAGEMENTBVR",
    "ONEENGAGEMENTBVR",
)

_STRIKE_MIN_CARRIER_STRIKERS_GROUPING = 6

_STRIKE_MIN_CARRIER_ESCORTS_GROUPING = 6

_FLIGHT_SIZE_NAME_TO_INT = {
    "single": 1,
    "singleaircraft": 1,
    "two": 2,
    "twoaircraft": 2,
    "three": 3,
    "threeaircraft": 3,
    "four": 4,
    "fouraircraft": 4,
    "six": 6,
    "sixaircraft": 6,
    "eight": 8,
    "eightaircraft": 8,
    "twelve": 12,
    "twelveaircraft": 12,
}

_TLAM_LAUNCH_MIN_BEFORE_TOT = 15

_TLAM_LAUNCH_MAX_BEFORE_TOT = 45

_STRIKE_ESCORT_TYPICAL_LAUNCH_MIN_BEFORE_TOT = 28

_STEALTH_BOMBER_NAME_MARKERS = (
    "B-2",
    "B2 ",
    "F-117",
    "F117",
    "SPIRIT",
    "NIGHTHAWK",
    "B-21",
    "RAIDER",
)

_NON_STEALTH_BOMBER_NAME_MARKERS = (
    "B-52",
    "B-1",
    "B-47",
    "B-58",
    "TU-95",
    "TU-160",
    "TU-22",
    "TU-16",
    "IL-28",
    "H-6",
    "VULCAN",
    "VICTOR",
    "VALIANT",
    "MIRAGE IV",
    "F-111",
    "SU-24",
    "SU-34",
    "BEAR",
    "BACKFIRE",
    "BLINDER",
    "BADGER",
)

__all__ = sorted(name for name in globals() if not name.startswith("__") and name != "re")

