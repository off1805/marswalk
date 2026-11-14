"""Recherche d'itinéraire (P2). BOUCHON de T00 : ligne droite entre les points de passage.

Signature gelée : ``plan_route(cost_grid, waypoints, options) -> RouteGeometry``.
"""

from __future__ import annotations

from marswalk_core.grids import CostGrid, RouteGeometry, RouteOptions
from marswalk_core.schemas import LonLat


def plan_route(
    cost_grid: CostGrid, waypoints: list[LonLat], options: RouteOptions
) -> RouteGeometry:
    if len(waypoints) < 2:
        raise ValueError("Il faut au moins deux points de passage")
    coordinates = [LonLat(*w) for w in waypoints]
    return RouteGeometry(coordinates=coordinates, segment_breaks=list(range(len(coordinates) - 1)))
