"""Géodésie martienne (C1). BOUCHON de T00 : formule sphérique simple.

Les signatures sont gelées ; C1 remplace les corps. Toute distance, surface ou échelle
se calcule ici avec le rayon martien, jamais avec MapLibre ou Turf (règle R3).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from marswalk_core.schemas import MARS_2000_RADIUS_M, LonLat

if TYPE_CHECKING:
    from marswalk_core.site_package import Site


def distance_m(a: LonLat, b: LonLat) -> float:
    """Distance orthodromique en mètres sur la sphère Mars 2000 (haversine)."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * MARS_2000_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: LonLat, b: LonLat) -> float:
    """Cap initial de a vers b, en degrés depuis le nord, de 0 à 360."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def to_analysis(site: Site, lon: float, lat: float) -> tuple[float, float]:
    """(lon, lat) en degrés vers (x, y) en mètres dans ``site.analysis_crs`` (eqc)."""
    k = math.cos(math.radians(site.lat_ts))
    x = site.radius_m * math.radians(lon - site.lon0) * k
    y = site.radius_m * math.radians(lat)
    return x, y


def to_lonlat(site: Site, x: float, y: float) -> tuple[float, float]:
    """(x, y) en mètres du système d'analyse vers (lon, lat) en degrés."""
    k = math.cos(math.radians(site.lat_ts))
    lon = site.lon0 + math.degrees(x / (site.radius_m * k))
    lat = math.degrees(y / site.radius_m)
    return lon, lat
