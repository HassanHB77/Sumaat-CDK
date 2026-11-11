import pytest

from api.geo import encode


def test_known_reference_value():
    # Classic example from the geohash spec (Jutland, Denmark).
    assert encode(57.64911, 10.40744, 11) == "u4pruydqqvj"


def test_default_precision_is_5():
    assert len(encode(25.38, 49.58)) == 5


def test_nearby_points_share_cell():
    # Two points ~300 m apart in Al-Hofuf land in the same 5-char cell.
    assert encode(25.3797, 49.5867) == encode(25.3770, 49.5850)


@pytest.mark.parametrize(("lat", "lng"), [(91, 0), (0, 181), (-91, 0)])
def test_rejects_out_of_range(lat, lng):
    with pytest.raises(ValueError):
        encode(lat, lng)
