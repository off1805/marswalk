"""Champ de temps de retour (P3). BOUCHON de T00 : distance droite à 1 m/s.

Signature gelée : ``return_field(cost_grid, habitat, suit) -> ReturnField``.
"""

from __future__ import annotations

import numpy as np

from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import CostGrid, ReturnField
from marswalk_core.schemas import LonLat, SuitModel


def return_field(cost_grid: CostGrid, habitat: LonLat, suit: SuitModel) -> ReturnField:
    site = cost_grid.site
    hx, hy = to_analysis(site, habitat[0], habitat[1])
    a, _, c, _, e, f = cost_grid.transform
    height, width = cost_grid.cost.shape
    xs = c + a * (np.arange(width) + 0.5)
    ys = f + e * (np.arange(height) + 0.5)
    dist = np.hypot(xs[None, :] - hx, ys[:, None] - hy).astype(np.float32)
    return ReturnField(
        site=site,
        transform=cost_grid.transform,
        resolution_m=cost_grid.resolution_m,
        seconds=dist / np.float32(1.0),
        habitat=LonLat(*habitat),
    )


def return_time_at(field: ReturnField, lon: float, lat: float) -> float | None:
    """Temps de retour au point, ou None hors grille."""
    x, y = to_analysis(field.site, lon, lat)
    cell = field.site.xy_to_cell(x, y)
    return None if cell is None else float(field.seconds[cell])
