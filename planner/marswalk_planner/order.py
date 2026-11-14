"""Ordre de visite des cibles (P2). BOUCHON de T00 : ordre reçu.

Signature gelée : ``order_targets(cost_grid, start, targets, options) -> list[Target]``.
"""

from __future__ import annotations

from marswalk_core.grids import CostGrid, RouteOptions
from marswalk_core.schemas import LonLat, Target


def order_targets(
    cost_grid: CostGrid, start: LonLat, targets: list[Target], options: RouteOptions
) -> list[Target]:
    return list(targets)
