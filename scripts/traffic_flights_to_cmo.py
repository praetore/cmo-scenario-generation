"""Turn live FlightAware AeroAPI flights into a CMO Lua scenario of neutral
civilian air traffic.

The generated Lua is self-contained (only ScenEdit_* calls, no bootstrap /
embed step needed): it creates one neutral side and spawns each live flight as
an airborne Air unit at its last reported position, heading and speed. This is
useful for adding realistic ambient/civil traffic to a scenario (target ID,
collateral-damage and neutral-handling practice — see logic_checks_cmo.md §11).

KEY HANDLING
    If no AeroAPI key is configured (cmo_config.ini [aeroapi] api_key or the
    AEROAPI_API_KEY env var), generation is SKIPPED with a clear message and a
    success exit code, so this step can sit in a pipeline without a key.

USAGE
    # Live (box = MINLAT MINLON MAXLAT MAXLON):
    python scripts/traffic_flights_to_cmo.py --name nl_traffic --box "50.7 3.3 53.6 7.3"

    # Offline from a saved AeroAPI response (testable without a key):
    python scripts/traffic_flights_to_cmo.py --name nl_traffic --from-json sample.json

Altitudes from AeroAPI are in hundreds of feet (flight level); converted to
metres for CMO. Groundspeed is in knots; heading in degrees true.
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from traffic_aeroapi import AeroAPIClient, AeroAPIError, latlong_box_query
from traffic_aircraft_type_map import TypeResolver
from cmo_config import aeroapi_key_source_label, resolve_aeroapi_key

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = REPO_ROOT / "generated"

# Verified civilian airliner in DB3K v515 (Boeing 737-800, civilian operator).
# Used as a generic stand-in for ambient traffic; override with --dbid.
DEFAULT_AIRLINER_DBID = 3970
# Passenger loadout for the 737-800 (air units REQUIRE a LoadoutID); fallback only.
DEFAULT_AIRLINER_LOADOUT = 19902

FEET_PER_FL = 100.0
METERS_PER_FOOT = 0.3048


def _lua_str(value):
    """Escape a string for a single-quoted Lua literal."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _safe_name(flight, index):
    name = flight.get("ident") or flight.get("fa_flight_id") or f"FLT{index}"
    reg = flight.get("registration")
    if reg and reg not in name:
        name = f"{name} ({reg})"
    return name


def flight_to_unit(flight, fallback_dbid, min_alt_ft, max_alt_ft, resolver=None):
    """Map an AeroAPI flight dict to a CMO unit dict, or None if unusable.

    DBID is resolved from the ICAO aircraft type via ``resolver`` (local DB,
    no API cost); unmapped/unknown types use ``fallback_dbid``.
    """
    pos = flight.get("last_position") or {}
    lat = pos.get("latitude")
    lon = pos.get("longitude")
    if lat is None or lon is None:
        return None

    alt_fl = pos.get("altitude") or 0  # hundreds of feet
    alt_ft = alt_fl * FEET_PER_FL
    if min_alt_ft is not None and alt_ft < min_alt_ft:
        return None
    if max_alt_ft is not None and alt_ft > max_alt_ft:
        return None

    origin = (flight.get("origin") or {}).get("code_icao") or (flight.get("origin") or {}).get("code") or "?"
    dest = (flight.get("destination") or {}).get("code_icao") or (flight.get("destination") or {}).get("code") or "?"

    actype = flight.get("aircraft_type") or "UNKNOWN"
    dbid = resolver.dbid(actype) if resolver else None
    fell_back = dbid is None
    if fell_back:
        dbid = fallback_dbid
    if resolver:
        resolver.record(actype, dbid, fell_back)

    # Air units require a LoadoutID; resolve a passenger loadout for the DBID.
    loadout = resolver.loadout_for(dbid) if resolver else None
    if not loadout:
        loadout = DEFAULT_AIRLINER_LOADOUT

    return {
        "name": _safe_name(flight, 0),
        "dbid": dbid,
        "loadoutid": loadout,
        "matched": not fell_back,
        "latitude": round(float(lat), 5),
        "longitude": round(float(lon), 5),
        "altitude_m": round(alt_ft * METERS_PER_FOOT, 1),
        "heading": int(pos.get("heading") or 0),
        "speed_kts": int(pos.get("groundspeed") or 0),
        "aircraft_type": actype,
        "route": f"{origin}->{dest}",
        "fa_flight_id": flight.get("fa_flight_id") or "",
    }


def build_units(flights, fallback_dbid, min_alt_ft, max_alt_ft, max_flights, resolver=None):
    units = []
    seen = set()
    for i, fl in enumerate(flights, 1):
        u = flight_to_unit(fl, fallback_dbid, min_alt_ft, max_alt_ft, resolver)
        if not u:
            continue
        # De-duplicate names (CMO unit names should be unique).
        base = u["name"]
        name = base
        n = 2
        while name in seen:
            name = f"{base} #{n}"
            n += 1
        seen.add(name)
        u["name"] = name
        units.append(u)
        if max_flights and len(units) >= max_flights:
            break
    return units


def render_lua(units, side, posture, meta):
    lines = []
    a = lines.append
    a("-- CMO scenario: live civilian air traffic from FlightAware AeroAPI")
    a(f"-- Generated: {meta['generated']} | source: {meta['source']}")
    if meta.get("box"):
        a(f"-- Lat/long box (MINLAT MINLON MAXLAT MAXLON): {meta['box']}")
    matched = sum(1 for u in units if u.get("matched"))
    a(f"-- Flights rendered: {len(units)} | type-matched to DB: {matched} | "
      f"fallback DBID: {meta['dbid']} (override with --dbid)")
    a("-- Self-contained: only ScenEdit_* calls, no bootstrap/embed needed.")
    a("-- Altitudes converted from AeroAPI flight level (hundreds of ft) to metres.")
    a("-- DBID per flight is mapped from the ICAO aircraft type via the local CMO DB;")
    a("-- unmapped/unknown types use the fallback airframe above.")
    a("")
    a(f"ScenEdit_AddSide({{side='{_lua_str(side)}'}})")
    a("")
    a("local function add_traffic(unitname, dbid, loadoutid, lat, lon, alt_m, hdg, spd)")
    a("    local u = ScenEdit_AddUnit({")
    a(f"        type='Air', side='{_lua_str(side)}', unitname=unitname, dbid=dbid,")
    a("        loadoutid=loadoutid, latitude=lat, longitude=lon, altitude=alt_m, heading=hdg,")
    a("    })")
    a("    if not u or not u.guid then")
    a("        print('ERROR: could not place flight unit: '..unitname)")
    a("        return nil")
    a("    end")
    a("    ScenEdit_SetUnit({ guid=u.guid, heading=hdg, speed=spd })")
    a("    return u")
    a("end")
    a("")
    for u in units:
        a(
            "add_traffic('%s', %d, %d, %s, %s, %s, %d, %d)  -- %s %s"
            % (
                _lua_str(u["name"]),
                u["dbid"],
                u["loadoutid"],
                u["latitude"],
                u["longitude"],
                u["altitude_m"],
                u["heading"],
                u["speed_kts"],
                u["aircraft_type"],
                u["route"],
            )
        )
    a("")
    a("print('Civil air traffic loaded: %d unit(s) on side \\'%s\\'.')" % (len(units), _lua_str(side)))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a CMO Lua scenario of neutral civilian traffic from AeroAPI."
    )
    parser.add_argument("--name", required=True, help="Scenario base name (output: generated/<name>.lua)")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--box", help="Lat/long box: \"MINLAT MINLON MAXLAT MAXLON\"")
    src.add_argument("--query", help="Raw /flights/search simplified query")
    src.add_argument("--from-json", help="Generate offline from a saved AeroAPI /flights/search response")
    parser.add_argument("--side", default="Civilian Air Traffic", help="CMO side name for the traffic")
    parser.add_argument("--posture", default="N", help="Side posture code (default N=Neutral)")
    parser.add_argument("--dbid", type=int, default=DEFAULT_AIRLINER_DBID,
                        help="Fallback civilian airframe DBID for unmapped/unknown types")
    parser.add_argument("--series", default="DB3K", help="CMO DB series for type mapping (default DB3K)")
    parser.add_argument("--version", default="515", help="CMO DB version for type mapping (default 515)")
    parser.add_argument("--no-db-types", action="store_true",
                        help="Skip local-DB type mapping; use the fallback DBID for every flight")
    parser.add_argument("--max-pages", type=int, default=2,
                        help="AeroAPI pages to fetch (= billed /flights/search queries)")
    parser.add_argument("--max-flights", type=int, default=60, help="Cap rendered units")
    parser.add_argument("--min-alt-ft", type=float, default=None, help="Drop flights below this altitude (ft)")
    parser.add_argument("--max-alt-ft", type=float, default=None, help="Drop flights above this altitude (ft)")
    parser.add_argument("--out", help="Output Lua path (default generated/<name>.lua)")
    parser.add_argument("--save-json", help="Also write the raw flights list to this JSON path")
    parser.add_argument("--api-key", help="Override the configured AeroAPI key")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    parser.add_argument("--ca-bundle", help="CA bundle (PEM) for TLS verification")
    args = parser.parse_args(argv)

    # ---- Source the flights -------------------------------------------------
    meta_source = ""
    box = None
    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        flights = data.get("flights", data) if isinstance(data, dict) else data
        meta_source = f"offline JSON ({args.from_json})"
    else:
        key = resolve_aeroapi_key(args.api_key)
        if not key:
            print("NOTE: AeroAPI key not configured ({}). Skipping civilian-traffic generation.".format(
                aeroapi_key_source_label()))
            print("      Set cmo_config.ini [aeroapi] api_key or AEROAPI_API_KEY to enable.")
            return 0  # skip, not an error

        client = AeroAPIClient.from_config(
            args.api_key,
            verify_ssl=False if args.insecure else None,
            ca_bundle=args.ca_bundle,
        )
        if args.box:
            parts = args.box.split()
            if len(parts) != 4:
                print("ERROR: --box needs 4 numbers: \"MINLAT MINLON MAXLAT MAXLON\"", file=sys.stderr)
                return 2
            query = latlong_box_query(*parts)
            box = args.box
        elif args.query:
            query = args.query
        else:
            print("ERROR: provide --box, --query or --from-json.", file=sys.stderr)
            return 2
        try:
            flights = client.search(query, max_pages=args.max_pages)
        except AeroAPIError as exc:
            print(f"ERROR: AeroAPI request failed: {exc}", file=sys.stderr)
            return 2
        meta_source = f"AeroAPI /flights/search (query: {query})"

    if args.save_json:
        Path(args.save_json).write_text(json.dumps(flights, indent=2), encoding="utf-8")

    # ---- Type mapping (local DB only, no API cost) --------------------------
    resolver = None
    fallback_dbid = args.dbid
    if not args.no_db_types:
        resolver = TypeResolver(args.series, args.version)
        if resolver.db_available:
            # Resolve a version-correct fallback airframe so --dbid stays sane
            # across DB versions; only keep the numeric default if lookup fails.
            fb = resolver.dbid_by_name("Boeing 737-800")
            if fb:
                fallback_dbid = fb
        else:
            print(f"NOTE: local CMO DB unavailable ({resolver.db_error}); "
                  f"using fallback DBID {fallback_dbid} for all flights.")

    units = build_units(flights, fallback_dbid, args.min_alt_ft, args.max_alt_ft,
                        args.max_flights, resolver)
    if resolver:
        print(resolver.summary_line())
        resolver.close()
    if not units:
        print("WARNING: no usable flights with positions found; nothing generated.")
        return 0

    meta = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        "source": meta_source,
        "box": box,
        "dbid": fallback_dbid,
    }
    lua = render_lua(units, args.side, args.posture, meta)

    out_path = Path(args.out) if args.out else (GENERATED_DIR / f"{args.name}.lua")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(lua, encoding="utf-8")
    print(f"OK: wrote {out_path} ({len(units)} civilian flight unit(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
