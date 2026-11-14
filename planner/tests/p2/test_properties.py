"""Tests de propriétés sur grilles aléatoires.

Démontre qu'aucun point du tracé ne traverse une cellule interdite,
quelle que soit la configuration du terrain.

Utilise des grilles générées aléatoirement pour couvrir des configurations
que les tests déterministes ne peuvent pas anticiper.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from tests.p2.conftest import make_site

from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import LonLat, SafetySettings
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.route import plan_route


def _random_layers(rng: np.random.Generator, grid_size: int = 50) -> dict[str, np.ndarray]:
    """Couches aléatoires avec obstacles, pentes et sol variable."""
    slope = (rng.random((grid_size, grid_size)) * 25.0).astype(np.float32)
    obstacles = (rng.random((grid_size, grid_size)) < 0.08).astype(np.float32)
    loose_soil = (rng.integers(0, 4, (grid_size, grid_size))).astype(np.float32)
    scarps = np.zeros((grid_size, grid_size), dtype=np.float32)

    # S'assurer que start (coin haut-gauche) et end (coin bas-droit) sont libres
    slope[0, 0] = 0.0
    obstacles[0, 0] = 0.0
    loose_soil[0, 0] = 0.0
    slope[-1, -1] = 0.0
    obstacles[-1, -1] = 0.0
    loose_soil[-1, -1] = 0.0

    return {
        "slope": slope,
        "obstacles": obstacles,
        "scarps": scarps,
        "loose_soil": loose_soil,
        "thermal_inertia": np.full((grid_size, grid_size), 300.0, dtype=np.float32),
        "radio_coverage": np.ones((grid_size, grid_size), dtype=np.float32),
        "illumination": np.ones((grid_size, grid_size), dtype=np.float32),
        "roughness": np.full((grid_size, grid_size), 0.1, dtype=np.float32),
        "crism_minerals": np.zeros((grid_size, grid_size), dtype=np.float32),
    }


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 7, 13, 42, 99, 137])
def test_no_forbidden_cell_in_path(seed: int):
    """Propriété : aucun point du tracé ne traverse une cellule interdite.

    Testé sur 10 grilles aléatoires différentes.
    """
    rng = np.random.default_rng(seed)
    gs = 50
    layers = _random_layers(rng, gs)
    site, _ = make_site(layers, grid_size=gs, resolution=2.0)
    settings = SafetySettings()
    cost_grid = build_cost_grid(site, settings)

    # Points dans les coins opposés de la grille (libres par construction)
    from marswalk_core.geodesy import to_lonlat

    a_tup = site.manifest.grid.transform
    res = a_tup[0]
    c0, f0 = a_tup[2], a_tup[5]
    e = a_tup[4]  # négatif

    # Coin haut-gauche : col=0, row=0
    x_start = c0 + res * 0.5
    y_start = f0 + e * 0.5
    # Coin bas-droit : col=gs-1, row=gs-1
    x_end = c0 + res * (gs - 0.5)
    y_end = f0 + e * (gs - 0.5)

    start_lon, start_lat = to_lonlat(site, x_start, y_start)
    end_lon, end_lat = to_lonlat(site, x_end, y_end)

    start = LonLat(start_lon, start_lat)
    end = LonLat(end_lon, end_lat)

    opts = RouteOptions(window_margin_m=200.0)
    geom = plan_route(cost_grid, [start, end], opts)

    for pt in geom.coordinates:
        x, y = to_analysis(site, pt.lon, pt.lat)
        cell = site.xy_to_cell(x, y)
        if cell is not None:
            assert not math.isinf(cost_grid.cost[cell[0], cell[1]]), (
                f"seed={seed}: point {pt} traverse une cellule interdite "
                f"à la case ({cell[0]}, {cell[1]})"
            )


@pytest.mark.parametrize("seed", [0, 5, 10, 20, 30])
def test_smooth_does_not_introduce_forbidden(seed: int):
    """Le lissage ne doit pas introduire de cellules interdites dans le tracé."""
    rng = np.random.default_rng(seed)
    gs = 40
    layers = _random_layers(rng, gs)
    site, _ = make_site(layers, grid_size=gs, resolution=2.0)
    settings = SafetySettings()
    cost_grid = build_cost_grid(site, settings)

    from marswalk_planner._p2.astar import Cell, astar_grid
    from marswalk_planner._p2.smooth import smooth_path

    start_cell = Cell(0, 0)
    end_cell = Cell(gs - 1, gs - 1)

    if math.isinf(cost_grid.cost[0, 0]):
        return  # skip si start interdit (géré par _nearest_free)

    path = astar_grid(cost_grid.cost, start_cell, end_cell, window_margin_cells=50)
    if path is None:
        return  # pas de chemin possible

    smoothed = smooth_path(cost_grid.cost, path)
    for cell in smoothed:
        assert not math.isinf(cost_grid.cost[cell.row, cell.col]), (
            f"seed={seed}: cellule lissée ({cell}) est interdite"
        )
