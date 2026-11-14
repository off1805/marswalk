"""Tests de la géodésie martienne (C1) — Python.

Vérifie les formules sphériques haversine et les projections d'analyse,
avec le rayon de la sphère Mars 2000 (3 396 190 m).
"""

from __future__ import annotations

import math

import pytest

from marswalk_core.geodesy import bearing_deg, distance_m, to_analysis, to_lonlat
from marswalk_core.schemas import MARS_2000_RADIUS_M, LonLat
from marswalk_core.site_package import load_site

# ---------------------------------------------------------------------------
# Tests distance_m
# ---------------------------------------------------------------------------


def test_one_degree_longitude_at_equator() -> None:
    """1° de longitude à l'équateur ≈ 59 274 m = 2π R / 360."""
    expected = 2 * math.pi * MARS_2000_RADIUS_M / 360.0
    d = distance_m(LonLat(0, 0), LonLat(1, 0))
    assert abs(d - expected) < 1.0  # < 1 m
    assert 59_200 < d < 59_300  # sanity range


def test_one_degree_latitude_at_equator() -> None:
    """1° de latitude ≈ même valeur que longitude à l'équateur."""
    expected = 2 * math.pi * MARS_2000_RADIUS_M / 360.0
    d = distance_m(LonLat(0, 0), LonLat(0, 1))
    assert abs(d - expected) < 1.0


def test_distance_symmetry() -> None:
    """Distance A→B = B→A."""
    a = LonLat(77.5, 18.3)
    b = LonLat(77.6, 18.4)
    assert abs(distance_m(a, b) - distance_m(b, a)) < 1e-9


def test_distance_zero() -> None:
    """Distance d'un point à lui-même est 0."""
    p = LonLat(77.58, 18.38)
    assert distance_m(p, p) == pytest.approx(0.0, abs=1e-6)


def test_distance_half_circumference() -> None:
    """Points antipodaux : distance = π × R."""
    expected = math.pi * MARS_2000_RADIUS_M
    d = distance_m(LonLat(0, 0), LonLat(180, 0))
    assert abs(d - expected) < 10.0  # < 10 m sur ~10 000 km


def test_distance_jezero_to_jezero() -> None:
    """2 km sur la grille du site fictif correspondent à environ 2 000 m."""
    # Habitat fictif et point ~1 km à l'est
    hab = LonLat(77.5782222, 18.3816712)
    # 1 km en longitude à Jezero ≈ 1000 / (59274 * cos(18.38°)) degrés
    offset = 1000.0 / (59_274.0 * math.cos(math.radians(18.38)))
    east = LonLat(hab.lon + offset, hab.lat)
    d = distance_m(hab, east)
    assert abs(d - 1000.0) < 5.0  # < 5 m


def test_distance_uses_mars_radius_not_earth() -> None:
    """Le résultat utilise le rayon martien, pas terrestre (6 371 km)."""
    # À l'équateur 1° ≈ 111 km sur Terre, 59.3 km sur Mars
    d = distance_m(LonLat(0, 0), LonLat(1, 0))
    assert d < 70_000  # clairement pas terrestre
    assert d > 55_000  # clairement martien


# ---------------------------------------------------------------------------
# Tests bearing_deg
# ---------------------------------------------------------------------------


def test_bearing_east() -> None:
    """Cap vers l'est = 90°."""
    b = bearing_deg(LonLat(0, 0), LonLat(1, 0))
    assert abs(b - 90.0) < 0.5


def test_bearing_north() -> None:
    """Cap vers le nord = 0°."""
    b = bearing_deg(LonLat(0, 0), LonLat(0, 1))
    assert abs(b - 0.0) < 0.5


def test_bearing_south() -> None:
    """Cap vers le sud = 180°."""
    b = bearing_deg(LonLat(0, 1), LonLat(0, 0))
    assert abs(b - 180.0) < 0.5


def test_bearing_west() -> None:
    """Cap vers l'ouest = 270°."""
    b = bearing_deg(LonLat(1, 0), LonLat(0, 0))
    assert abs(b - 270.0) < 0.5


def test_bearing_northeast() -> None:
    """Cap nord-est ≈ 45°."""
    b = bearing_deg(LonLat(0, 0), LonLat(1, 1))
    assert 40.0 < b < 50.0


def test_bearing_range() -> None:
    """Le cap est toujours dans [0, 360)."""
    pairs = [
        (LonLat(0, 0), LonLat(1, 1)),
        (LonLat(100, 50), LonLat(-100, -50)),
        (LonLat(0, 80), LonLat(180, -80)),
    ]
    for a, b in pairs:
        assert 0.0 <= bearing_deg(a, b) < 360.0


# ---------------------------------------------------------------------------
# Tests to_analysis / to_lonlat (aller-retour)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def site():  # type: ignore[no-untyped-def]
    return load_site("fictif")


def test_round_trip_habitat(site) -> None:  # type: ignore[no-untyped-def]
    """Aller-retour hab → (x, y) → (lon, lat) est exact."""
    hab = site.manifest.habitat
    x, y = to_analysis(site, hab.lon, hab.lat)
    lon, lat = to_lonlat(site, x, y)
    assert lon == pytest.approx(hab.lon, abs=1e-9)
    assert lat == pytest.approx(hab.lat, abs=1e-9)


def test_to_analysis_at_site_center(site) -> None:  # type: ignore[no-untyped-def]
    """Le centre du site (lon0, lat0) se projette sur (0, 0)."""
    # Le centre de la grille est à (lon0, lat_ts)
    x, _y = to_analysis(site, site.lon0, site.lat_ts)
    assert x == pytest.approx(0.0, abs=0.1)
    # Note : y ≈ lat_ts * R * π/180 (non nul pour lat_ts ≠ 0)


def test_to_analysis_distance_preserved(site) -> None:  # type: ignore[no-untyped-def]
    """La distance projetée entre deux points proches ≈ distance haversine."""
    hab = site.manifest.habitat
    # ~100 m au nord
    offset_lat = 100.0 / MARS_2000_RADIUS_M * (180.0 / math.pi)
    north = LonLat(hab.lon, hab.lat + offset_lat)
    xh, yh = to_analysis(site, hab.lon, hab.lat)
    xn, yn = to_analysis(site, north.lon, north.lat)
    proj_dist = math.hypot(xn - xh, yn - yh)
    # Doit être proche de 100 m (< 1 m d'erreur sur distances courtes)
    assert abs(proj_dist - 100.0) < 1.0


def test_grid_extent_is_1000x1000(site) -> None:  # type: ignore[no-untyped-def]
    """La grille 1000 × 1000 à 2 m fait 2 km × 2 km en mètres."""
    a, _, _c, _, e, _f = site.transform
    width_m = abs(a) * site.manifest.grid.width
    height_m = abs(e) * site.manifest.grid.height
    assert width_m == pytest.approx(2000.0, rel=1e-3)
    assert height_m == pytest.approx(2000.0, rel=1e-3)
