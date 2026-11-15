"""Fixtures pytest réutilisables pour les tests D2."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def flat_dem():
    """DEM plat à -2500m, 100×100 px."""
    size = 100
    return np.full((size, size), -2500.0, dtype=np.float32)


@pytest.fixture
def tilted_dem():
    """Plan incliné de 15° dans la direction Est (colonnes = est).

    slope_deg = 15, size = 100×100 px, résolution = 1m/px.
    dz/dx = tan(15°) ≈ 0.2679 m/m → chaque colonne monte de ~0.2679m.
    """
    size = 100
    slope_deg = 15.0
    slope_m_per_m = np.tan(np.radians(slope_deg))
    cols = np.arange(size, dtype=np.float32)
    # Répéter sur 100 lignes pour obtenir un tableau 100×100
    dem = np.broadcast_to(-2500.0 + cols * slope_m_per_m, (size, size)).copy()
    return dem.astype(np.float32)


@pytest.fixture
def dem_with_cliff():
    """DEM 100×100 avec une falaise abrupte (saut de 50m sur 2 pixels au milieu)."""
    size = 100
    dem = np.full((size, size), -2500.0, dtype=np.float32)
    # Falaise verticale à la colonne 50 : tout ce qui est à droite monte de 50m
    dem[:, 50:] = -2450.0
    return dem


@pytest.fixture
def dem_with_pit():
    """DEM 100×100 avec une dépression rugueuse (zone irrégulière)."""
    rng = np.random.default_rng(42)
    size = 100
    dem = np.full((size, size), -2500.0, dtype=np.float32)
    # Zone rugueuse au centre (20×20 pixels avec bruit fort)
    dem[40:60, 40:60] += rng.normal(0, 2.0, (20, 20)).astype(np.float32)
    return dem


@pytest.fixture
def synthetic_ti():
    """Inertie thermique synthétique 100×100 avec zones dune/roche/mixte."""
    size = 100
    ti = np.full((size, size), 300.0, dtype=np.float32)  # roche par défaut
    ti[:25, :] = 150.0  # zone dune (TI < 170)
    ti[25:50, :] = 180.0  # zone meuble (TI < 200)
    ti[50:75, :] = 230.0  # zone mixte (TI < 270)
    # ti[75:, :] = 300.0  # zone roche (TI >= 270)
    return ti
