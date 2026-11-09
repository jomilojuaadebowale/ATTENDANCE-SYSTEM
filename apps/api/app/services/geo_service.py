"""Geofence maths. Pure functions, no I/O."""

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_000.0


def valid_coordinates(lat: float | None, lng: float | None) -> bool:
    return (
        lat is not None
        and lng is not None
        and math.isfinite(lat)
        and math.isfinite(lng)
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    )


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True)
class GeoResult:
    distance_m: float
    within: bool


def check_geofence(
    scan_lat: float,
    scan_lng: float,
    anchor_lat: float,
    anchor_lng: float,
    radius_m: float,
    accuracy_m: float | None,
) -> GeoResult:
    """Accuracy-aware radius check.

    A phone reporting "within 30 m of this point" may really be up to 30 m closer to the
    anchor than the reported point. We therefore accept when `distance - accuracy <= radius`.
    """
    distance = haversine_m(scan_lat, scan_lng, anchor_lat, anchor_lng)
    slack = max(accuracy_m or 0.0, 0.0)
    return GeoResult(distance_m=distance, within=(distance - slack) <= radius_m)
