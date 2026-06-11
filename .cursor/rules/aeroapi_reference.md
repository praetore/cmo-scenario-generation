# FlightAware AeroAPI v4 — reference (for this repo)

Reference for the **FlightAware AeroAPI 4.x** REST API and how it is wired into
this CMO scenario tooling. Use it when fetching real-world flight data (e.g. to
inject neutral civilian air traffic into a scenario — see
`logic_checks_cmo.md` §11 *Civil Traffic & Neutral Parties*).

- **Base URL:** `https://aeroapi.flightaware.com/aeroapi`
- **Auth:** API key in the **`x-apikey`** request header (no username).
- **Format:** JSON (`application/json; charset=UTF-8`). All endpoints are `GET`
  except the alert/endpoint config and flight-intent `POST`/`PUT`/`DELETE`.
- **OpenAPI spec:** <https://static.flightaware.com/rsrc/aeroapi/aeroapi-openapi.yml>

## 1. Repo integration

| Piece | File | Role |
| :--- | :--- | :--- |
| Key/SSL config | `cmo_config.ini` `[aeroapi]` (gitignored) | `api_key`, optional `verify_ssl`, `ca_bundle` |
| Key resolver | `scripts/cmo_config.py` | `resolve_aeroapi_key()`, `resolve_aeroapi_verify_ssl()`, `resolve_aeroapi_ca_bundle()`, `aeroapi_key_source_label()` |
| Client | `scripts/traffic_aeroapi.py` | `AeroAPIClient` (stdlib `urllib`); cursor pagination; small CLI |
| Converter | `scripts/traffic_flights_to_cmo.py` | Live flights → self-contained CMO Lua of neutral civilian traffic |

**Key resolution priority:** explicit arg → `AEROAPI_API_KEY` env → `cmo_config.ini`
`[aeroapi] api_key`. The placeholder `YOUR_AEROAPI_KEY_HERE` counts as *unset*.
When unset, `traffic_flights_to_cmo.py` **skips** generation (exit 0, NOTE logged) — the
key is never required for the rest of the pipeline.

**TLS note:** behind a TLS-intercepting proxy (self-signed CA in the chain),
default verification fails. Prefer pointing `ca_bundle` at the corporate root CA;
otherwise set `verify_ssl = false` (env `AEROAPI_VERIFY_SSL=0`, or CLI
`--insecure`). Default is verification **on**.

### Client usage

```python
from aeroapi import AeroAPIClient, latlong_box_query
client = AeroAPIClient.from_config()      # None if no key configured
if client:
    q = latlong_box_query(50.7, 3.3, 53.6, 7.3)  # MINLAT MINLON MAXLAT MAXLON
    print(client.search_count(q))
    flights = client.search(q, max_pages=2)       # list of flight dicts
```

CLI quick checks:

```bash
python scripts/traffic_aeroapi.py key-status
python scripts/traffic_aeroapi.py count    --query '-latlong "50.7 3.3 53.6 7.3"'
python scripts/traffic_aeroapi.py search   --query '-latlong "50.7 3.3 53.6 7.3"' --max-pages 2
python scripts/traffic_aeroapi.py positions --query '{range alt 50 400}' --unique
python scripts/traffic_aeroapi.py flight    UAL4
```

### Converter usage

```bash
# Live (box = MINLAT MINLON MAXLAT MAXLON):
python scripts/traffic_flights_to_cmo.py --name nl_traffic --box "50.7 3.3 53.6 7.3" --max-flights 40
# Offline from a saved /flights/search response (no key needed):
python scripts/traffic_flights_to_cmo.py --name nl_traffic --from-json sample.json
```

Output `generated/<name>.lua` is **self-contained** (only `ScenEdit_*`, no
bootstrap/embed): one neutral side, each flight an airborne `Air` unit at its
last position/heading/speed.

**Aircraft-type mapping (`scripts/traffic_aircraft_type_map.py`):** each flight's ICAO
`aircraft_type` (e.g. `B738`, `E190`, `AT72`) is resolved to a real CMO
`DataAircraft` DBID against the **local** source `.db3` (no API cost), preferring
civilian operators. Because DBIDs are not stable across DB versions, mapping is
done **by name at runtime** for `--series/--version` (default `DB3K 515`).
Unmapped/unknown types (and anything absent from the DB — e.g. the A320 family,
737 MAX, Dash 8 are not in DB3K v515) fall back to `--dbid` (default `3970`,
Boeing 737-800). Use `--no-db-types` to force the fallback for every flight. The
run prints a summary, e.g. `Type mapping: 9 matched, 21 fell back (types: …)`.

**API cost:** the only billed calls are `/flights/search` pages — exactly
`--max-pages` queries per run (default `2`, ~15 flights/page). Type mapping is
purely local. Use `--from-json`/`--save-json` to iterate offline at zero cost.

## 2. Conventions & gotchas

- **Pagination:** responses include `links.next` (a path **relative to `/aeroapi`**,
  e.g. `/flights/search?cursor=…`) and `num_pages`. Append it to the base URL, not
  the host root (the client's `_next_url` handles this). `max_pages` caps fetches.
- **`cursor`:** opaque token; pass back to continue a paged collection.
- **Time format:** ISO-8601 (`2021-12-31T19:59:59Z`) for structured endpoints;
  the search query syntax uses **UNIX epoch seconds** for time keys.
- **Altitude:** in search/position data, altitude is in **hundreds of feet / flight
  level** (e.g. `350` = FL350 = 35,000 ft). Convert ×100 ft, then ×0.3048 → metres.
- **Speed:** knots. **Heading:** degrees true.
- **Identifiers:** prefer **ICAO** idents/airport codes over IATA to avoid ambiguity
  (set `ident_type` / `id_type` to disambiguate). `fa_flight_id` is FlightAware's
  unique per-flight id (e.g. `UAL1234-1234567890-airline-0123`).
- **History vs live:** live flight endpoints cover ~last 24–48h (10 days for
  map/route/track); older data needs the `/history/...` equivalents (back to
  2011-01-01). Pick the matching family.
- **Cost:** each call (and each **alert callback**) is billed and counts toward
  usage. Foresight endpoints are Premium-only. Keep `max_pages`/box size modest.
- **`predicted_*` / `foresight_predictions_available`:** non-Foresight endpoints
  expose the flag (and null predicted fields); the `/foresight/...` mirrors fill
  them in (Premium).

## 3. Endpoint catalog

### Flights (`/flights`)
| Method/Path | Purpose | Key params |
| :--- | :--- | :--- |
| `GET /flights/{ident}` | Flight status summary (registration, ident, or fa_flight_id) | `ident_type`, `start`, `end`, `max_pages`, `cursor` |
| `GET /flights/{ident}/canonical` | Resolve ambiguous ident → canonical code(s) | `ident_type`, `country_code` |
| `GET /flights/{id}/position` | Latest position (last 24–48h) | — |
| `GET /flights/{id}/route` | Filed route fixes (mostly CONUS) | — |
| `GET /flights/{id}/track` | Track as position array | `include_estimated_positions`, `include_surface_positions` |
| `GET /flights/{id}/map` | Base64 map image of track | `height`, `width`, `layer_on/off`, `show_airports`, `bounding_box`, … |
| `POST /flights/{ident}/intents` | Submit a flight intent (special auth + Global) | body: aircraft_type, origin, destination, intended_off/on, … |
| `GET /flights/search` | Airborne search, **simplified** `-key value` syntax | `query`, `max_pages`, `cursor` |
| `GET /flights/search/advanced` | Airborne search, **`{operator key value}`** syntax | `query`, `max_pages`, `cursor` |
| `GET /flights/search/count` | Count for a simplified query | `query` |
| `GET /flights/search/positions` | Position search (any position in ~24h) | `query`, `unique_flights`, `max_pages` |

### Foresight (`/foresight`, Premium)
`GET /foresight/flights/{id}/position`, `GET /foresight/flights/{ident}`,
`GET /foresight/flights/search/advanced` — mirror the above, adding
`predicted_out/off/on/in` (+ `_source`) and `predicted_taxi_out_duration`.

### Airports (`/airports`)
`GET /airports`, `GET /airports/{id}`, `GET /airports/{id}/canonical`,
`GET /airports/{id}/delays`, `GET /airports/{id}/flights` (+ `/arrivals`,
`/departures`, `/scheduled_arrivals`, `/scheduled_departures`, `/counts`,
`/to/{dest_id}`), `GET /airports/{id}/nearby`, `GET /airports/{id}/routes/{dest_id}`,
`GET /airports/{id}/weather/forecast` (decoded TAF), `GET /airports/{id}/weather/observations`
(decoded METAR), `GET /airports/delays`, `GET /airports/nearby` (`latitude`,
`longitude`, `radius`, `only_iap`). Airport `id`: ICAO preferred (IATA/LID ok).

### Operators (`/operators`)
`GET /operators`, `GET /operators/{id}`, `GET /operators/{id}/canonical`,
`GET /operators/{id}/flights` (+ `/arrivals`, `/enroute`, `/scheduled`, `/counts`).
`id`: ICAO preferred.

### Alerts (`/alerts`)
Set the account-wide delivery URL **first**: `PUT /alerts/endpoint` (also `GET`,
`DELETE`). Then `GET/POST /alerts`, `GET/PUT/DELETE /alerts/{id}`. Alert `events`:
`arrival, cancelled, departure, diverted, filed, out, off, on, in, hold_start,
hold_end`; optional per-alert `target_url`. Callbacks `POST` to your endpoint and
are **billed as queries**.

### History (`/history`, 2011-01-01 → now)
`GET /history/aircraft/{registration}/last_flight`,
`GET /history/airports/{id}/flights/{arrivals|departures|to/{dest_id}}` (start+end
required, ≤24h span, ≤40 pages), `GET /history/flights/{id}/{map|route|track}`,
`GET /history/flights/{ident}` (start+end, ≤7d span), `GET /history/operators/{id}/flights`.

### Miscellaneous & account
`GET /aircraft/{ident}/blocked`, `GET /aircraft/{ident}/owner`,
`GET /aircraft/types/{type}` (ICAO type designator → manufacturer/engines),
`GET /disruption_counts/{entity_type}[/{id}]` (`airline|origin|destination`,
`time_period`), `GET /schedules/{date_start}/{date_end}` (published airline
schedules; `origin`, `destination`, `airline`, `flight_number`),
`GET /account/usage` (`start`, `end`, `all_keys`).

## 4. Search query syntax

### Simplified (`/flights/search`, `/search/count`)
Single string of `-key value` pairs. Keys:
`-prefix -type -idents -identOrReg -airline -destination -origin
-originOrDestination -aboveAltitude -belowAltitude -aboveGroundspeed
-belowGroundspeed -latlong "MINLAT MINLON MAXLAT MAXLON" -filter {ga|airline}`.
Example: `-latlong "44.95 -111.05 40.96 -104.05" -belowAltitude 100`.

### Advanced (`/flights/search/advanced`)
Space-separated `{operator key value}` terms (implicit AND). Operators:
`true false null notnull = != < > <= >= match notmatch range in orig_or_dest
airline aircraftType ident ident_or_reg`. Keys include `aircraftType, alt,
altChange, arrived, cancelled, dest, orig, eta, ident, lat, lon, gs, speed,
heading, prefix, physClass, status (S/F/A/Z/X), updateType, waypoints, fixes,
hiLat/hiLon/lowLat/lowLon`, plus epoch-second times (`actualDepartureTime,
arrivalTime, clock, edt, eta, fdt, firstPositionTime, lastPositionTime`).
Example: `{orig_or_dest {KLAX KBUR KSNA KLGB}} {<= alt 8000} {match ident AAL*}`.

### Positions (`/flights/search/positions`)
`{operator key value}` over **all** positions in ~24h. Keys: `alt, altChange,
altMax, cid, cidfac, clock, fp, gs, lat, lon, preferred, recvd, updateType`.
Example: `{< alt 500} {range gs 10 100}` with `unique_flights=true`.

`updateType` codes: `P` projected, `O` oceanic, `Z` radar, `A` ADS-B,
`M` multilateration, `D` datalink, `X` surface/near-surface, `S` space-based,
`V` virtual event.
