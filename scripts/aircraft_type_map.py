"""Resolve ICAO aircraft type designators (from AeroAPI ``aircraft_type``) to
CMO DataAircraft DBIDs, version-correctly, against the local CMO database.

This does **not** call AeroAPI — it only reads the local source ``.db3`` — so it
adds zero API cost. DBIDs are not universal across DB versions, so we resolve by
*name* at runtime for the requested series/version rather than hardcoding IDs.

DB3K v515 has a limited civilian airliner inventory (Boeing, Embraer, ATR, CRJ,
A310/A340, plus light GA). Modern Airbus narrowbodies (A320 family), 737 MAX,
A330/A350, Dash 8, etc. are absent, so those designators fall back to the caller's
default airframe.
"""

from cmo_db import open_db

# Civilian / generic operator pseudo-codes in the CMO DB (prefer these matches).
CIVIL_OPERATORS = {1101, 1102, 1103, 1104, 1105}

# ICAO type designator -> ordered candidate Name substrings (LIKE) in the CMO DB.
# Only designators that have a sensible match in DB3K are listed; anything else
# (or any miss) falls back to the caller's default DBID.
ICAO_TYPE_TO_NAME = {
    # Boeing 737 family (no MAX / -900 in DB3K v515 -> nearest -800/-700).
    "B732": ["Boeing 737-200"], "B733": ["Boeing 737-300"],
    "B735": ["Boeing 737-300"], "B736": ["Boeing 737-700"],
    "B737": ["Boeing 737-700"], "B738": ["Boeing 737-800"],
    "B739": ["Boeing 737-800"], "B37M": ["Boeing 737-800"],
    "B38M": ["Boeing 737-800"], "B39M": ["Boeing 737-800"],
    # Boeing widebodies.
    "B742": ["Boeing 747-200"], "B744": ["Boeing 747-200"], "B748": ["Boeing 747-200"],
    "B752": ["Boeing 777-200"], "B763": ["Boeing 777-200"],
    "B772": ["Boeing 777-200"], "B77L": ["Boeing 777-200"],
    "B77W": ["Boeing 777-200ER"], "B773": ["Boeing 777-200ER"],
    "B788": ["Boeing 787-8"], "B789": ["Boeing 787-9"], "B78X": ["Boeing 787-9"],
    # Airbus (only A310 / A340 present in DB3K v515).
    "A306": ["Airbus A.310"], "A310": ["Airbus A.310"],
    "A342": ["Airbus A.340"], "A343": ["Airbus A.340"],
    "A345": ["Airbus A.340-500"], "A346": ["Airbus A.340"],
    "A332": ["Airbus A.340"], "A333": ["Airbus A.340"], "A339": ["Airbus A.340"],
    "A359": ["Airbus A.340"], "A35K": ["Airbus A.340"],
    # Embraer E-Jets.
    "E170": ["Embraer E-170"], "E75L": ["Embraer E-175"], "E75S": ["Embraer E-175"],
    "E170L": ["Embraer E-170"], "E175": ["Embraer E-175"],
    "E190": ["Embraer E-190"], "E195": ["Embraer E-195"],
    "E290": ["Embraer E-190-E2"], "E295": ["Embraer E-190-E2"],
    "E275": ["Embraer E-175-E2"],
    # ATR turboprops.
    "AT72": ["ATR-72-500"], "AT75": ["ATR-72-500"], "AT76": ["ATR-72-500"],
    "AT43": ["ATR-42-500"], "AT45": ["ATR-42-500"], "AT46": ["ATR-42-500"],
    # Regional jets.
    "CRJ1": ["Bombardier CRJ100"], "CRJ2": ["Bombardier CRJ200"],
    "CRJ7": ["Bombardier CRJ700"], "CRJ9": ["Bombardier CRJ700"],
    "CRJX": ["Bombardier CRJ700"],
    # General aviation / turboprop / bizprop.
    "C172": ["Cessna 172"], "C72R": ["Cessna 172"],
    "PC12": ["Pilatus PC-12"],
    "LJ35": ["Learjet 35"], "LJ36": ["Learjet 36"],
    "BE9L": ["Beechcraft 1900"], "B190": ["Beechcraft 1900"], "B350": ["Beechcraft 1900"],
}


class TypeResolver:
    """Caches ICAO-type -> DBID resolution against a single open DB handle.

    Falls back gracefully: if the DB cannot be opened, ``dbid()`` always returns
    None so the caller uses its own default airframe.
    """

    def __init__(self, series, version, db_path=None):
        self.series = series
        self.version = version
        self._db = None
        self._cache = {}
        self.stats = {"matched": {}, "fallback": {}}
        try:
            self._db = open_db(db_path=db_path, series=series, version=version, prefer_source=True)
        except Exception as exc:  # noqa: BLE001 - degrade to fallback-only
            self.db_error = str(exc)
        else:
            self.db_error = None

    @property
    def db_available(self):
        return self._db is not None

    def _query_name(self, term):
        """Return a DBID for the first DataAircraft whose Name LIKE term.

        Prefers civilian operators; falls back to the first match otherwise.
        """
        sql = (
            "SELECT ID, OperatorCountry FROM DataAircraft "
            "WHERE Name LIKE ?"
        )
        params = [f"%{term}%"]
        sql, params = self._db.append_meta_filters(sql, params)
        try:
            self._db.cursor.execute(sql, params)
            rows = self._db.cursor.fetchall()
        except Exception:  # noqa: BLE001
            return None
        if not rows:
            return None
        for row in rows:
            try:
                if int(row[1]) in CIVIL_OPERATORS:
                    return int(row[0])
            except (TypeError, ValueError):
                continue
        return int(rows[0][0])

    def dbid(self, aircraft_type):
        """Resolve an ICAO type designator to a CMO DBID, or None to fall back."""
        if not aircraft_type or not self.db_available:
            return None
        key = aircraft_type.strip().upper()
        if key in self._cache:
            return self._cache[key]
        result = None
        for term in ICAO_TYPE_TO_NAME.get(key, []):
            result = self._query_name(term)
            if result:
                break
        self._cache[key] = result
        return result

    def dbid_by_name(self, name):
        """Resolve a direct Name substring to a DBID (e.g. the fallback airframe)."""
        if not self.db_available:
            return None
        return self._query_name(name)

    def loadout_for(self, dbid):
        """Return a sensible (passenger) LoadoutID for an aircraft DBID, or None.

        Air units added via ScenEdit_AddUnit require a LoadoutID. Prefers a
        'Passenger' loadout; otherwise the first real loadout (skipping
        Reserve/Maintenance/Ferry).
        """
        if not self.db_available or not dbid:
            return None
        cache = self.__dict__.setdefault("_loadout_cache", {})
        if dbid in cache:
            return cache[dbid]
        # Link table: DataAircraftLoadouts(ID=aircraft) -> ComponentID(loadout)
        link_sql = "SELECT ComponentID FROM DataAircraftLoadouts WHERE ID = ?"
        link_params = [dbid]
        link_sql, link_params = self._db.append_meta_filters(link_sql, link_params)
        try:
            self._db.cursor.execute(link_sql, link_params)
            comp_ids = [r[0] for r in self._db.cursor.fetchall()]
        except Exception:  # noqa: BLE001
            comp_ids = []
        result = None
        if comp_ids:
            placeholders = ",".join(["?"] * len(comp_ids))
            name_sql = f"SELECT ID, Name FROM DataLoadout WHERE ID IN ({placeholders})"
            name_params = list(comp_ids)
            name_sql, name_params = self._db.append_meta_filters(name_sql, name_params)
            try:
                self._db.cursor.execute(name_sql, name_params)
                rows = self._db.cursor.fetchall()
            except Exception:  # noqa: BLE001
                rows = []
            skip = ("reserve", "maintenance", "ferry")
            fallback = None
            for lid, name in rows:
                low = (name or "").lower()
                if fallback is None and not any(s in low for s in skip):
                    fallback = int(lid)
                if "passenger" in low:
                    result = int(lid)
                    break
            if result is None:
                result = fallback
        cache[dbid] = result
        return result

    def record(self, aircraft_type, dbid, fell_back):
        bucket = "fallback" if fell_back else "matched"
        key = (aircraft_type or "UNKNOWN").upper()
        self.stats[bucket][key] = self.stats[bucket].get(key, 0) + 1

    def summary_line(self):
        matched = sum(self.stats["matched"].values())
        fell = sum(self.stats["fallback"].values())
        fb_types = ", ".join(sorted(self.stats["fallback"])) or "-"
        return (f"Type mapping: {matched} matched to DB airframes, "
                f"{fell} fell back (types: {fb_types}).")

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None
