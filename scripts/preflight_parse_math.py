"""Distance, time, and bbox math helpers."""

import math
import re
from pathlib import Path

from preflight_constants import *

def _approx_deg_distance(lat1, lon1, lat2, lon2):
    return math.hypot(lat2 - lat1, lon2 - lon1)

def _haversine_nm(lat1, lon1, lat2, lon2):
    """Great-circle distance in nautical miles."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3440.065 * 2 * math.asin(math.sqrt(min(1.0, a)))

def _flight_minutes_for_nm(distance_nm, speed_kts, overhead_min=0):
    if distance_nm <= 0 or speed_kts <= 0:
        return overhead_min
    return int(math.ceil(distance_nm / speed_kts * 60.0)) + overhead_min

def _max_distance_nm(origin, targets):
    if not targets:
        return None, None
    best_nm = -1.0
    best = None
    for t in targets:
        nm = _haversine_nm(origin[0], origin[1], t["lat"], t["lon"])
        if nm > best_nm:
            best_nm = nm
            best = t
    return best_nm, best

def _time_to_minutes(hhmmss):
    parts = hhmmss.strip().split(":")
    if len(parts) < 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return h * 60 + m + (1 if s >= 30 else 0)
    except ValueError:
        return None

def _minutes_to_hhmmss(total_minutes):
    """Clock time on same calendar day (wraps at 24h)."""
    if total_minutes is None:
        return None
    minutes = int(total_minutes) % (24 * 60)
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}:00"

def _normalize_date_key(date_str):
    """Normalize scenario dates to YYYYMMDD for comparison."""
    if not date_str:
        return None
    digits = re.sub(r"\D", "", str(date_str))
    if len(digits) != 8:
        return digits or None
    if int(digits[:4]) > 1900:
        return digits
    # MMDDYYYY (public CMO default)
    return digits[4:8] + digits[0:4]

def _normalize_date_slash_key(date_str):
    """Canonical YYYY/MM/DD from slash, dot, compact, or CMO SetTime YYYYMMDD."""
    if not date_str:
        return None
    s = str(date_str).strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}/{s[4:6]}/{s[6:8]}"
    s = s.replace(".", "/").replace("-", "/")
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        return f"{m.group(1)}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"
    return None

def _bbox_for_zone(rp_names, ref_points, margin=0.02):
    lats = []
    lons = []
    for name in rp_names:
        if name not in ref_points:
            return None
        lat, lon = ref_points[name]
        lats.append(lat)
        lons.append(lon)
    if not lats:
        return None
    return (
        min(lats) - margin,
        max(lats) + margin,
        min(lons) - margin,
        max(lons) + margin,
    )

def _point_in_bbox(lat, lon, bbox):
    min_lat, max_lat, min_lon, max_lon = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

def _zone_centroid(point_names, point_map):
    coords = [point_map[name] for name in point_names if name in point_map]
    if not coords:
        return None
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return lat, lon

__all__ = ['_approx_deg_distance', '_bbox_for_zone', '_flight_minutes_for_nm', '_haversine_nm', '_max_distance_nm', '_minutes_to_hhmmss', '_normalize_date_key', '_normalize_date_slash_key', '_point_in_bbox', '_time_to_minutes', '_zone_centroid']
