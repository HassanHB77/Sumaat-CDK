"""Tiny geohash encoder (no dependency).

A geohash turns (lat, lng) into a short string; nearby points share a prefix.
We store a 5-character cell (~4.9 km x 4.9 km) in GSI1PK as GEO#<geohash5>
so "restaurants near me" is a Query on a handful of cells.
"""

import math

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

GEO_PRECISION = 5


def encode(lat: float, lng: float, precision: int = GEO_PRECISION) -> str:
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError("lat must be in [-90, 90] and lng in [-180, 180]")

    lat_lo, lat_hi = -90.0, 90.0
    lng_lo, lng_hi = -180.0, 180.0
    out, bits, ch, even = [], 0, 0, True  # even bit -> longitude

    while len(out) < precision:
        if even:
            mid = (lng_lo + lng_hi) / 2
            ch = (ch << 1) | (lng >= mid)
            lng_lo, lng_hi = (mid, lng_hi) if lng >= mid else (lng_lo, mid)
        else:
            mid = (lat_lo + lat_hi) / 2
            ch = (ch << 1) | (lat >= mid)
            lat_lo, lat_hi = (mid, lat_hi) if lat >= mid else (lat_lo, mid)
        even = not even
        bits += 1
        if bits == 5:
            out.append(_BASE32[ch])
            bits, ch = 0, 0
    return "".join(out)


# One precision-5 cell: 25 bits = 13 for longitude, 12 for latitude -> 0.0439 degrees each way.
CELL_DEG = 360 / 2**13  # == 180 / 2**12

EARTH_RADIUS_KM = 6371.0088


def cells_around(lat: float, lng: float) -> list[str]:
    """Your cell plus its 8 neighbours (the 3x3 block), as precision-5 geohashes.

    Shifting the point by exactly one cell size always lands in the adjacent cell, so no decoding
    is needed. The block always reaches at least one full cell (~4.4 km E-W in Al-Ahsa) past you,
    which is why the API caps the radius at a round 4 km.
    """
    cells: list[str] = []
    for dlat in (-CELL_DEG, 0, CELL_DEG):
        for dlng in (-CELL_DEG, 0, CELL_DEG):
            la = max(-90.0, min(90.0, lat + dlat))
            ln = (lng + dlng + 180) % 360 - 180  # wrap around the date line
            gh = encode(la, ln)
            if gh not in cells:
                cells.append(gh)
    return cells


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle (haversine) distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
