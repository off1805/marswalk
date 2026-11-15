"""Grille de planification à 2 m sur un paquet à 1 m (correctif I1)."""

from __future__ import annotations

import numpy as np
from tests.p2.conftest import flat_layers, make_site

from marswalk_core.config import load_safety_settings
from marswalk_planner._p1.planning_site import planning_site
from marswalk_planner.cost import build_cost_grid


def test_one_metre_site_is_planned_at_two_metres() -> None:
    layers = flat_layers(100)
    layers["slope"][10, 11] = 30.0  # une seule case de 1 m trop raide
    site, _ = make_site(layers, resolution=1.0, grid_size=100, site_id="p1_1m")
    grid = build_cost_grid(site, load_safety_settings("standard"))
    assert grid.cost.shape == (50, 50)
    assert grid.resolution_m == 2.0
    # La case de 2 m qui la contient est interdite (pire des quatre cases).
    assert bool(grid.forbidden[5, 5])
    assert grid.site.xy_to_cell(*_center(site, 10, 11)) == (5, 5)


def test_two_metre_site_is_unchanged() -> None:
    site, _ = make_site(flat_layers(50), resolution=2.0, grid_size=50, site_id="p1_2m")
    assert planning_site(site) is site


def test_cached_grid_is_returned_as_a_copy() -> None:
    site, _ = make_site(flat_layers(50), resolution=2.0, grid_size=50, site_id="p1_copy")
    settings = load_safety_settings("standard")
    a = build_cost_grid(site, settings)
    a.cost[0, 0] = np.inf
    b = build_cost_grid(site, settings)
    assert np.isfinite(b.cost[0, 0])


def _center(site, row: int, col: int) -> tuple[float, float]:  # type: ignore[no-untyped-def]
    a, _, c, _, e, f = site.transform
    return c + a * (col + 0.5), f + e * (row + 0.5)
