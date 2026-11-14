"""Tests de order_targets.

Couvre :
- Ordre imposé (optimize_order=False).
- Ordre optimisé exact jusqu'à 8 cibles.
- Ordre optimisé heuristique pour > 8 cibles.
- Cas dégénérés (0, 1 cible).
- Vérification que le coût optimisé est ≤ coût de l'ordre initial.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import LonLat, SafetySettings, Target, TargetKind
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.order import order_targets
from tests.p2.conftest import flat_layers, make_site, make_target, make_target_at, grid_lonlat


def _cost_of_order(grid, start, ordered, end):
    """Estimation du coût total d'un ordre donné (distance euclidienne pondérée)."""
    from marswalk_planner._p2.tsp import _euclid_cost
    nodes = [start, *[t.position for t in ordered], end]
    total = 0.0
    for i in range(len(nodes) - 1):
        total += _euclid_cost(grid, nodes[i], nodes[i + 1])
    return total


class TestOrderImposed:
    def test_imposed_order_preserved(self, flat_site, standard_settings):
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        targets = [make_target_at(i, 0.5, 0.1 * (i + 1)) for i in range(5)]
        opts = RouteOptions(optimize_order=False)
        result = order_targets(grid, grid_lonlat(0.5, 0.0), targets, opts)
        assert [t.id for t in result] == [t.id for t in targets]

    def test_imposed_order_single_target(self, flat_site, standard_settings):
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        target = make_target_at(0, 0.3, 0.7)
        opts = RouteOptions(optimize_order=False)
        result = order_targets(grid, grid_lonlat(0.1, 0.1), [target], opts)
        assert len(result) == 1
        assert result[0].id == target.id

    def test_imposed_order_empty(self, flat_site, standard_settings):
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        opts = RouteOptions(optimize_order=False)
        result = order_targets(grid, grid_lonlat(0.5, 0.5), [], opts)
        assert result == []


class TestOrderOptimized:
    def test_single_target_no_change(self, flat_site, standard_settings):
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        target = make_target_at(0, 0.3, 0.7)
        opts = RouteOptions(optimize_order=True)
        result = order_targets(grid, grid_lonlat(0.1, 0.1), [target], opts)
        assert len(result) == 1

    def test_two_targets_optimal_order(self, flat_site, standard_settings):
        """Avec deux cibles, l'ordre optimal est vérifiable analytiquement."""
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.5, 0.05)   # gauche
        end = grid_lonlat(0.5, 0.95)     # droite
        # Cible A proche du départ (gauche), cible B proche de l'arrivée (droite)
        t_a = make_target_at(0, 0.5, 0.2)   # col 0.2 = proche départ
        t_b = make_target_at(1, 0.5, 0.8)   # col 0.8 = proche arrivée
        opts = RouteOptions(optimize_order=True, return_to=end)
        result = order_targets(grid, start, [t_b, t_a], opts)
        # L'ordre optimal devrait être [A, B]
        assert result[0].id == t_a.id
        assert result[1].id == t_b.id

    def test_optimized_cost_le_original(self, flat_site, standard_settings):
        """L'ordre optimisé ne doit pas coûter plus que l'ordre initial."""
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.5, 0.05)
        end = grid_lonlat(0.5, 0.95)
        # Ordre sous-optimal : cibles en zigzag
        targets = [
            make_target_at(0, 0.5, 0.9),
            make_target_at(1, 0.5, 0.2),
            make_target_at(2, 0.5, 0.7),
            make_target_at(3, 0.5, 0.4),
        ]
        opts = RouteOptions(optimize_order=True, return_to=end)
        result = order_targets(grid, start, targets, opts)
        cost_original = _cost_of_order(grid, start, targets, end)
        cost_optimized = _cost_of_order(grid, start, result, end)
        assert cost_optimized <= cost_original + 1e-6

    def test_exact_tsp_up_to_8_targets(self, flat_site, standard_settings):
        """Avec 8 cibles sur une ligne, l'ordre optimal est de gauche à droite."""
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.5, 0.05)
        end = grid_lonlat(0.5, 0.95)
        # 8 cibles réparties de gauche à droite
        targets = [make_target_at(i, 0.5, 0.1 + i * 0.1) for i in range(8)]
        # Mélanger l'ordre
        import random
        shuffled = list(targets)
        random.seed(42)
        random.shuffle(shuffled)
        opts = RouteOptions(optimize_order=True, return_to=end)
        result = order_targets(grid, start, shuffled, opts)
        assert len(result) == 8
        # L'ordre optimal doit aller de gauche (petite col_frac) à droite
        cols = [t.position.lon for t in result]
        assert cols == sorted(cols)

    def test_heuristic_tsp_above_8_targets(self, flat_site, standard_settings):
        """Avec 9 cibles, l'heuristique doit fonctionner."""
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.5, 0.05)
        end = grid_lonlat(0.5, 0.95)
        targets = [make_target_at(i, 0.5, 0.05 + i * 0.1) for i in range(9)]
        opts = RouteOptions(optimize_order=True, return_to=end)
        result = order_targets(grid, start, targets, opts)
        assert len(result) == 9
        cost_optimized = _cost_of_order(grid, start, result, end)
        cost_original = _cost_of_order(grid, start, targets, end)
        assert cost_optimized <= cost_original * 1.5

    def test_empty_targets(self, flat_site, standard_settings):
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        opts = RouteOptions(optimize_order=True)
        result = order_targets(grid, grid_lonlat(0.5, 0.5), [], opts)
        assert result == []
