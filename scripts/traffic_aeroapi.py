"""Reusable FlightAware AeroAPI v4 client (stdlib only).

Auth is via the ``x-apikey`` header. The key is resolved through
``cmo_config.resolve_aeroapi_key`` (env ``AEROAPI_API_KEY`` or ``cmo_config.ini``
``[aeroapi] api_key``). When no key is configured the higher-level tooling
(``traffic_flights_to_cmo.py``) skips AeroAPI features instead of failing.

Reference: .cursor/rules/aeroapi_reference.md

CLI quick checks (no live call needed for ``key-status``):
    python scripts/traffic_aeroapi.py key-status
    python scripts/traffic_aeroapi.py count   --query "-latlong \"52.6 3.3 50.7 7.2\""
    python scripts/traffic_aeroapi.py search  --query "-latlong \"52.6 3.3 50.7 7.2\"" --max-pages 1
    python scripts/traffic_aeroapi.py positions --query "{range alt 50 400}" --unique
    python scripts/traffic_aeroapi.py flight  UAL4
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from cmo_config import (
    aeroapi_key_source_label,
    resolve_aeroapi_ca_bundle,
    resolve_aeroapi_key,
    resolve_aeroapi_verify_ssl,
)

DEFAULT_BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
DEFAULT_TIMEOUT = 30


class AeroAPIError(RuntimeError):
    """Raised for transport or HTTP errors talking to AeroAPI."""

    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class AeroAPIClient:
    """Thin AeroAPI v4 wrapper with cursor pagination support."""

    def __init__(self, api_key, base_url=DEFAULT_BASE_URL, timeout=DEFAULT_TIMEOUT,
                 verify_ssl=True, ca_bundle=None):
        if not api_key:
            raise ValueError("AeroAPIClient requires a non-empty api_key.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.ca_bundle = ca_bundle
        if not verify_ssl:
            self._ssl_context = ssl._create_unverified_context()
        elif ca_bundle:
            self._ssl_context = ssl.create_default_context(cafile=ca_bundle)
        else:
            self._ssl_context = ssl.create_default_context()

    @classmethod
    def from_config(cls, explicit_key=None, verify_ssl=None, ca_bundle=None, **kwargs):
        """Build a client from configured key, or None when no key is set."""
        key = resolve_aeroapi_key(explicit_key)
        if not key:
            return None
        return cls(
            key,
            verify_ssl=resolve_aeroapi_verify_ssl(verify_ssl),
            ca_bundle=resolve_aeroapi_ca_bundle(ca_bundle),
            **kwargs,
        )

    # -- low level ---------------------------------------------------------
    def _request(self, url):
        req = urllib.request.Request(
            url,
            headers={
                "x-apikey": self.api_key,
                "Accept": "application/json; charset=UTF-8",
                "User-Agent": "cmo-scenario-generation/aeroapi-client",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout,
                                        context=self._ssl_context) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:  # noqa: BLE001 - best-effort error body
                pass
            raise AeroAPIError(
                f"AeroAPI HTTP {exc.code} for {url}: {body[:500]}",
                status=exc.code,
                body=body,
            ) from exc
        except urllib.error.URLError as exc:
            raise AeroAPIError(f"AeroAPI connection error for {url}: {exc.reason}") from exc

        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AeroAPIError(f"AeroAPI returned non-JSON body for {url}: {raw[:200]}") from exc

    def get(self, path, params=None):
        """Single GET. ``path`` is relative to the base URL (e.g. ``/flights/search``)."""
        url = self.base_url + "/" + path.lstrip("/")
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url = url + "?" + urllib.parse.urlencode(clean, doseq=True)
        return self._request(url)

    def paginate(self, path, params=None, data_key=None, max_pages=1, page_pause=0.0):
        """Follow ``links.next`` up to ``max_pages``.

        Yields the value at ``data_key`` (a list) from each page when provided,
        otherwise yields the full page dict.
        """
        params = dict(params or {})
        url = self.base_url + "/" + path.lstrip("/")
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url = url + "?" + urllib.parse.urlencode(clean, doseq=True)

        pages = 0
        while url and pages < max_pages:
            page = self._request(url)
            pages += 1
            if data_key is not None:
                yield page.get(data_key, []) or []
            else:
                yield page
            nxt = (page.get("links") or {}).get("next")
            if not nxt:
                break
            url = self._next_url(nxt)
            if page_pause:
                time.sleep(page_pause)

    def _next_url(self, nxt):
        """Resolve a ``links.next`` value to an absolute URL.

        AeroAPI returns next as a path relative to the /aeroapi base
        (e.g. ``/flights/search?cursor=...``), so it must be appended to
        ``base_url`` rather than the host root.
        """
        if nxt.startswith("http://") or nxt.startswith("https://"):
            return nxt
        path = nxt
        if path.startswith("/aeroapi/"):
            path = path[len("/aeroapi"):]
        return self.base_url + "/" + path.lstrip("/")

    def collect(self, path, data_key, params=None, max_pages=1):
        """Concatenate a paged list resource into a single list."""
        out = []
        for chunk in self.paginate(path, params=params, data_key=data_key, max_pages=max_pages):
            out.extend(chunk)
        return out

    # -- flights -----------------------------------------------------------
    def flight_info(self, ident, **params):
        return self.get(f"/flights/{urllib.parse.quote(ident)}", params)

    def flight_position(self, fa_flight_id):
        return self.get(f"/flights/{urllib.parse.quote(fa_flight_id)}/position")

    def flight_track(self, fa_flight_id, include_estimated_positions=None,
                     include_surface_positions=None):
        return self.get(
            f"/flights/{urllib.parse.quote(fa_flight_id)}/track",
            {
                "include_estimated_positions": _b(include_estimated_positions),
                "include_surface_positions": _b(include_surface_positions),
            },
        )

    def flight_route(self, fa_flight_id):
        return self.get(f"/flights/{urllib.parse.quote(fa_flight_id)}/route")

    def search(self, query, max_pages=1):
        """Simplified-syntax flight search → list of flight dicts."""
        return self.collect("/flights/search", "flights", {"query": query}, max_pages)

    def search_advanced(self, query, max_pages=1):
        """Advanced-syntax flight search → list of flight dicts."""
        return self.collect("/flights/search/advanced", "flights", {"query": query}, max_pages)

    def search_positions(self, query, unique_flights=False, max_pages=1):
        """Position search → list of position dicts."""
        return self.collect(
            "/flights/search/positions",
            "positions",
            {"query": query, "unique_flights": _b(unique_flights)},
            max_pages,
        )

    def search_count(self, query):
        """Count of flights matching a simplified-syntax query."""
        return self.get("/flights/search/count", {"query": query}).get("count", 0)

    # -- airports ----------------------------------------------------------
    def airport(self, code):
        return self.get(f"/airports/{urllib.parse.quote(code)}")

    def airports_nearby(self, latitude, longitude, radius, only_iap=None, max_pages=1):
        return self.collect(
            "/airports/nearby",
            "airports",
            {
                "latitude": latitude,
                "longitude": longitude,
                "radius": radius,
                "only_iap": _b(only_iap),
            },
            max_pages,
        )


def _b(value):
    """Render a Python bool as the lowercase string AeroAPI expects, or None."""
    if value is None:
        return None
    return "true" if value else "false"


def latlong_box_query(min_lat, min_lon, max_lat, max_lon):
    """Build a simplified-syntax ``-latlong`` clause for /flights/search.

    AeroAPI expects "MINLAT MINLON MAXLAT MAXLON".
    """
    return f'-latlong "{min_lat} {min_lon} {max_lat} {max_lon}"'


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_json(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description="FlightAware AeroAPI client / quick CLI")
    parser.add_argument("--api-key", help="Override the configured AeroAPI key")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--insecure", action="store_true",
                        help="Disable TLS verification (corporate MITM proxies). Use with care.")
    parser.add_argument("--ca-bundle", help="Path to a CA bundle (PEM) for TLS verification")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("key-status", help="Report whether an AeroAPI key is configured")

    p_search = sub.add_parser("search", help="GET /flights/search (simplified syntax)")
    p_search.add_argument("--query", required=True)

    p_adv = sub.add_parser("advanced", help="GET /flights/search/advanced")
    p_adv.add_argument("--query", required=True)

    p_pos = sub.add_parser("positions", help="GET /flights/search/positions")
    p_pos.add_argument("--query", required=True)
    p_pos.add_argument("--unique", action="store_true")

    p_count = sub.add_parser("count", help="GET /flights/search/count")
    p_count.add_argument("--query", required=True)

    p_flight = sub.add_parser("flight", help="GET /flights/{ident}")
    p_flight.add_argument("ident")

    args = parser.parse_args(argv)

    if args.command == "key-status":
        key = resolve_aeroapi_key(args.api_key)
        if key:
            masked = key[:4] + "…" + key[-2:] if len(key) > 6 else "set"
            print(f"AeroAPI key: CONFIGURED ({masked}) via {aeroapi_key_source_label()}")
            return 0
        print(f"AeroAPI key: NOT configured ({aeroapi_key_source_label()})")
        print("Set AEROAPI_API_KEY or cmo_config.ini [aeroapi] api_key to enable.")
        return 1

    client = AeroAPIClient.from_config(
        args.api_key,
        verify_ssl=False if args.insecure else None,
        ca_bundle=args.ca_bundle,
    )
    if client is None:
        print("ERROR: No AeroAPI key configured; cannot make live calls.", file=sys.stderr)
        return 1

    try:
        if args.command == "search":
            _print_json(client.search(args.query, max_pages=args.max_pages))
        elif args.command == "advanced":
            _print_json(client.search_advanced(args.query, max_pages=args.max_pages))
        elif args.command == "positions":
            _print_json(client.search_positions(args.query, unique_flights=args.unique,
                                                 max_pages=args.max_pages))
        elif args.command == "count":
            print(client.search_count(args.query))
        elif args.command == "flight":
            _print_json(client.flight_info(args.ident))
    except AeroAPIError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
