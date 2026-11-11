import pytest

from api.geo import CELL_DEG, cells_around, distance_km, encode

NAKHLA = (25.3797, 49.5867)
MUBARRAZ = (25.4086, 49.5823)


def test_cells_around_is_3x3_including_own_cell():
    cells = cells_around(*NAKHLA)
    assert len(cells) == 9
    assert len(set(cells)) == 9
    assert encode(*NAKHLA) in cells
    assert encode(*MUBARRAZ) in cells  # GEO#the28 is a neighbour of GEO#the22


def test_cell_size_matches_precision_5():
    assert CELL_DEG == pytest.approx(0.0439, abs=1e-4)


def test_distance_nakhla_to_mubarraz():
    assert distance_km(*NAKHLA, *MUBARRAZ) == pytest.approx(3.2, abs=0.2)


def test_distance_zero_and_symmetric():
    assert distance_km(*NAKHLA, *NAKHLA) == 0
    assert distance_km(*NAKHLA, *MUBARRAZ) == pytest.approx(distance_km(*MUBARRAZ, *NAKHLA))


@pytest.mark.parametrize("bearing_lat, bearing_lng", [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)])
def test_any_point_within_4_4_km_is_in_the_block(bearing_lat, bearing_lng):
    """The guarantee behind MAX_RADIUS_KM: anything ≤ 4.4 km away lands in one of the 9 cells."""
    import math

    # Try many starting points across a cell, and push a target 4.4 km out in each direction.
    for i in range(10):
        for j in range(10):
            lat = 25.3 + i * CELL_DEG / 10
            lng = 49.5 + j * CELL_DEG / 10
            km_per_deg_lat = 111.2
            km_per_deg_lng = 111.32 * math.cos(math.radians(lat))
            norm = math.hypot(bearing_lat, bearing_lng)
            tlat = lat + 4.4 * bearing_lat / norm / km_per_deg_lat
            tlng = lng + 4.4 * bearing_lng / norm / km_per_deg_lng
            assert encode(tlat, tlng) in cells_around(lat, lng)
