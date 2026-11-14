"""Grille de coût (P1). BOUCHON de T00 : temps de traversée à 1 m/s, interdit au-delà du seuil.

Signatures gelées :
- ``build_cost_grid(site, settings, conditions) -> CostGrid``
- ``explain_cell(cost_grid, x, y) -> list[CostTerm]`` (x, y en mètres du système d'analyse)
"""

from __future__ import annotations

import numpy as np

from marswalk_core.grids import CostGrid, CostTerm
from marswalk_core.schemas import Conditions, SafetySettings
from marswalk_core.site_package import Site
from marswalk_planner.hazards import hazard_masks


def build_cost_grid(
    site: Site, settings: SafetySettings, conditions: Conditions | None = None
) -> CostGrid:
    masks = hazard_masks(site, settings)
    resolution = site.manifest.grid.resolution_m
    time_s = np.full(site.shape, resolution / 1.0, dtype=np.float32)
    cost = np.where(masks.forbidden, np.inf, time_s).astype(np.float32)
    return CostGrid(
        site=site,
        transform=site.transform,
        resolution_m=resolution,
        cost=cost,
        forbidden=masks.forbidden,
        terms={"time": time_s},
        warnings=list(masks.warnings),
    )


def explain_cell(cost_grid: CostGrid, x: float, y: float) -> list[CostTerm]:
    cell = cost_grid.site.xy_to_cell(x, y)
    if cell is None:
        return []
    if bool(cost_grid.forbidden[cell]):
        return [CostTerm("slope", float("inf"), 1.0, "case interdite : pente au-delà du seuil")]
    value = float(cost_grid.terms["time"][cell])
    return [CostTerm("time", value, 1.0, "temps de traversée à 1 m/s")]
