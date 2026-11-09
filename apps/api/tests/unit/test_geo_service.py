import math

import pytest

from app.services import geo_service as g


def test_zero_distance():
    assert g.haversine_m(7.5, 4.5, 7.5, 4.5) == pytest.approx(0, abs=1e-6)


def test_one_degree_of_latitude_is_about_111km():
    assert g.haversine_m(0, 0, 1, 0) == pytest.approx(111_195, rel=0.001)


def test_known_short_distance():
    # ~0.0009 degrees of latitude is ~100 m
    assert g.haversine_m(7.5186, 4.5213, 7.5186 + 0.0009, 4.5213) == pytest.approx(100, abs=1)


def test_symmetry():
    a = g.haversine_m(7.5, 4.5, 6.5, 3.4)
    b = g.haversine_m(6.5, 3.4, 7.5, 4.5)
    assert a == pytest.approx(b)


def test_inside_and_outside_radius():
    near = g.check_geofence(7.5186 + 0.0003, 4.5213, 7.5186, 4.5213, 75, accuracy_m=5)
    far = g.check_geofence(7.5186 + 0.0020, 4.5213, 7.5186, 4.5213, 75, accuracy_m=5)
    assert near.within and 30 < near.distance_m < 36
    assert not far.within and far.distance_m > 200


def test_accuracy_gives_benefit_of_the_doubt_but_not_unlimited():
    # 100 m away with 30 m accuracy: could really be 70 m away -> inside a 75 m radius
    lat = 7.5186 + 0.0009
    assert g.check_geofence(lat, 4.5213, 7.5186, 4.5213, 75, accuracy_m=30).within
    assert not g.check_geofence(lat, 4.5213, 7.5186, 4.5213, 75, accuracy_m=10).within


def test_negative_accuracy_is_ignored():
    lat = 7.5186 + 0.0009
    assert not g.check_geofence(lat, 4.5213, 7.5186, 4.5213, 75, accuracy_m=-500).within


@pytest.mark.parametrize(
    "lat,lng,ok",
    [
        (0, 0, True),
        (90, 180, True),
        (-90, -180, True),
        (90.0001, 0, False),
        (0, 180.1, False),
        (None, 1, False),
        (1, None, False),
        (math.nan, 1, False),
        (1, math.inf, False),
    ],
)
def test_coordinate_validation(lat, lng, ok):
    assert g.valid_coordinates(lat, lng) is ok
