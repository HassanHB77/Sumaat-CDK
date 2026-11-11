"""Tiny geohash encoder (no dependency).

A geohash turns (lat, lng) into a short string; nearby points share a prefix.
We store a 5-character cell (~4.9 km x 4.9 km) in GSI1PK as GEO#<geohash5>
so "restaurants near me" is a Query on a handful of cells.
"""

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
