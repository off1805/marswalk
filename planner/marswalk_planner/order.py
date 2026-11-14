"""Ordre de visite des cibles (P2).

Signature gelée : ``order_targets(cost_grid, start, targets, options) -> list[Target]``.

Deux modes :
1. ``options.optimize_order = False`` : ordre fourni conservé exactement.
2. ``options.optimize_order = True``  : minimisation du coût total par TSP.
   - ≤ 8 cibles : résolution exacte (permutations).
   - > 8 cibles : heuristique nearest-neighbor avec redémarrages.

Le coût entre deux points est estimé via la distance euclidienne pondérée
par le coût moyen de la grille (approximation rapide mais cohérente avec P1).
Le coût euclidien n'est pas utilisé comme substitut brut : il intègre la
résolution et le coût moyen de la grille pour être homogène avec les coûts
de déplacement martien.
"""

from __future__ import annotations

from marswalk_core.grids import CostGrid, RouteOptions
from marswalk_core.schemas import LonLat, Target
from marswalk_planner._p2.tsp import optimize_order as _optimize_order


def order_targets(
    cost_grid: CostGrid,
    start: LonLat,
    targets: list[Target],
    options: RouteOptions,
) -> list[Target]:
    """Ordonne les cibles selon le mode demandé.

    Paramètres
    ----------
    cost_grid:
        Grille de coût issue de P1.
    start:
        Position de départ de l'astronaute.
    targets:
        Cibles à visiter.
    options:
        ``optimize_order`` : True pour minimiser le coût, False pour conserver l'ordre.
        ``return_to`` : point d'arrivée (habitat si None).

    Retourne
    --------
    list[Target]
        Cibles dans l'ordre de visite retenu.
    """
    if not targets:
        return []
    if not options.optimize_order or len(targets) <= 1:
        return list(targets)

    end = options.return_to or start
    return _optimize_order(cost_grid, LonLat(*start), targets, LonLat(*end))
