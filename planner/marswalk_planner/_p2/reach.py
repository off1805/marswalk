"""Cibles atteignables depuis le départ (P2, écart E4).

Quand aucune suite de cases praticables ne relie une cible au départ, la recherche
revenait à la ligne droite « de secours » et le tracé franchissait la falaise sans le
dire. On repère ces cibles avant la recherche, par composantes connexes des cases
libres, pour les refuser et l'annoncer.

Connexité : ``astar`` ne coupe pas les coins des cases interdites, donc deux cases
libres ne communiquent que par un côté ; la 4-connexité donne les mêmes composantes.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import CostGrid
from marswalk_core.schemas import LonLat
from marswalk_planner._p2.astar import Cell, _nearest_free

# Dernier étiquetage : les trois variantes d'un plan ne diffèrent que par leurs poids,
# leurs cases libres sont les mêmes, on n'étiquette qu'une fois (2500 × 2500 sur Jezero).
_LAST: tuple[NDArray[np.bool_], NDArray[np.int32]] | None = None


def _labels_for(free: NDArray[np.bool_]) -> NDArray[np.int32]:
    global _LAST
    if _LAST is not None and _LAST[0].shape == free.shape and np.array_equal(_LAST[0], free):
        return _LAST[1]
    labels: NDArray[np.int32] = np.asarray(ndimage.label(free)[0], dtype=np.int32)
    _LAST = (free, labels)
    return labels


class Reachability:
    """Composantes connexes des cases libres d'une grille de coût."""

    def __init__(self, cost_grid: CostGrid) -> None:
        self._grid = cost_grid
        self._labels: NDArray[np.int32] = _labels_for(np.isfinite(cost_grid.cost))

    def _cell(self, p: LonLat) -> Cell | None:
        x, y = to_analysis(self._grid.site, p.lon, p.lat)
        rc = self._grid.site.xy_to_cell(x, y)
        if rc is None:
            return None
        cell = Cell(rc[0], rc[1])
        if np.isinf(self._grid.cost[cell.row, cell.col]):
            # Même relocalisation que ``astar_grid`` pour un point sur une case interdite
            return _nearest_free(self._grid.cost, cell.row, cell.col)
        return cell

    def component(self, p: LonLat) -> int:
        """Numéro de la composante du point (0 : hors grille ou sans case libre proche)."""
        cell = self._cell(p)
        return 0 if cell is None else int(self._labels[cell.row, cell.col])

    def connected(self, a: LonLat, b: LonLat) -> bool:
        ca = self.component(a)
        return ca != 0 and ca == self.component(b)
