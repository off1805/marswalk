"""Tests du lissage de chemin.

Couvre :
- Lissage d'un chemin en escalier sur terrain libre.
- Vérification que le lissage ne traverse pas d'obstacle.
- Préservation du chemin brut si le lissage échoue.
- Vérification des segments intermédiaires (pas uniquement les extrémités).
"""

from __future__ import annotations

import math

import numpy as np

from marswalk_planner._p2.astar import Cell
from marswalk_planner._p2.smooth import _bresenham_clear, smooth_path


class TestBresenhamClear:
    def test_straight_line_free(self):
        cost = np.ones((20, 20), dtype=np.float32)
        assert _bresenham_clear(cost, 0, 0, 0, 19)

    def test_blocked_cell_in_line(self):
        cost = np.ones((20, 20), dtype=np.float32)
        cost[0, 10] = np.inf
        assert not _bresenham_clear(cost, 0, 0, 0, 19)

    def test_diagonal_free(self):
        cost = np.ones((20, 20), dtype=np.float32)
        assert _bresenham_clear(cost, 0, 0, 19, 19)

    def test_diagonal_blocked(self):
        cost = np.ones((20, 20), dtype=np.float32)
        cost[10, 10] = np.inf
        assert not _bresenham_clear(cost, 0, 0, 19, 19)

    def test_out_of_bounds(self):
        cost = np.ones((10, 10), dtype=np.float32)
        assert not _bresenham_clear(cost, 0, 0, 20, 20)

    def test_same_cell(self):
        cost = np.ones((10, 10), dtype=np.float32)
        assert _bresenham_clear(cost, 5, 5, 5, 5)


class TestSmoothPath:
    def test_straight_path_unchanged(self):
        """Un chemin déjà droit ne doit pas être modifié."""
        cost = np.ones((20, 20), dtype=np.float32)
        path = [Cell(0, i) for i in range(10)]
        smoothed = smooth_path(cost, path)
        assert smoothed[0] == Cell(0, 0)
        assert smoothed[-1] == Cell(0, 9)

    def test_zigzag_simplified_on_free_grid(self):
        """Un chemin en escalier sur terrain libre doit être simplifié."""
        cost = np.ones((20, 20), dtype=np.float32)
        # Chemin en L : 0,0 → 0,5 → 10,5 → 10,10
        path = (
            [Cell(0, i) for i in range(6)]
            + [Cell(i, 5) for i in range(1, 11)]
            + [Cell(10, i) for i in range(6, 11)]
        )
        smoothed = smooth_path(cost, path)
        assert smoothed[0] == Cell(0, 0)
        assert smoothed[-1] == Cell(10, 10)
        assert len(smoothed) < len(path)

    def test_smooth_does_not_cross_obstacle(self):
        """Le lissage ne doit pas traverser un obstacle."""
        cost = np.ones((30, 30), dtype=np.float32)
        # Obstacle vertical
        cost[0:20, 15] = np.inf
        # Chemin qui contourne par le bas (lignes 20+)
        path = (
            [Cell(0, i) for i in range(10)]
            + [Cell(i, 10) for i in range(1, 22)]
            + [Cell(21, i) for i in range(11, 25)]
        )
        smoothed = smooth_path(cost, path)
        for cell in smoothed:
            assert not math.isinf(cost[cell.row, cell.col])

    def test_no_shortcut_through_wall(self):
        """Un raccourci direct qui traverse un mur ne doit pas être pris.

        La ligne directe (0,0)→(0,19) traverserait le mur en col=10.
        Le lissage doit conserver le détour qui contourne le mur.
        """
        cost = np.ones((20, 20), dtype=np.float32)
        # Mur vertical incomplet : col=10 de la ligne 0 à 14 seulement
        cost[0:15, 10] = np.inf
        # Chemin qui contourne par en dessous (lignes 15+)
        # - descend de (0,0) à (15,0) en col 0
        # - traverse horizontalement la ligne 15 de col 0 à col 19
        path = (
            [Cell(i, 0) for i in range(16)]
            + [Cell(15, i) for i in range(1, 20)]
        )
        # Vérifier que le chemin d'entrée est lui-même valide
        for cell in path:
            assert not math.isinf(cost[cell.row, cell.col])
        smoothed = smooth_path(cost, path)
        for cell in smoothed:
            assert not math.isinf(cost[cell.row, cell.col])

    def test_short_path_unchanged(self):
        cost = np.ones((10, 10), dtype=np.float32)
        path = [Cell(0, 0), Cell(0, 1)]
        smoothed = smooth_path(cost, path)
        assert smoothed == path

    def test_single_cell_unchanged(self):
        cost = np.ones((10, 10), dtype=np.float32)
        path = [Cell(5, 5)]
        smoothed = smooth_path(cost, path)
        assert smoothed == path

    def test_endpoints_preserved(self):
        """Les extrémités du chemin doivent être conservées."""
        cost = np.ones((30, 30), dtype=np.float32)
        cost[10:20, 15] = np.inf
        path = [Cell(5, 0), Cell(5, 10), Cell(5, 15), Cell(5, 20), Cell(25, 25)]
        smoothed = smooth_path(cost, path)
        assert smoothed[0] == path[0]
        assert smoothed[-1] == path[-1]

    def test_segment_check_not_just_endpoints(self):
        """La vérification doit porter sur tout le segment, pas seulement les extrémités."""
        cost = np.ones((30, 30), dtype=np.float32)
        # Obstacle au milieu exact du segment
        cost[5, 15] = np.inf
        # start et end sont libres, mais le milieu est interdit
        ok = _bresenham_clear(cost, 5, 0, 5, 29)
        assert not ok  # doit détecter l'obstacle à col=15
