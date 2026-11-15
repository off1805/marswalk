"""Vue du site sur la grille de planification (2 m).

Les couches d'un paquet réel sont à 1 m (Jezero : 5 000 × 5 000 cases), mais la
planification se fait à 2 m (taches-agents.md, règle R1). À 1 m, la grille de coût prend
plus de 7 s et le champ de retour dépasse la mémoire disponible. ``planning_site`` renvoie
donc une vue du site dont la grille est agrégée par blocs, avec une règle prudente par
couche : une case de 2 m prend le pire de ses quatre cases de 1 m (pente, obstacles,
falaises, sol meuble et rugosité au maximum, radio et éclairement au minimum), pour ne
jamais faire passer un danger entre les mailles. Sur un site déjà à 2 m ou plus (le site
fictif), le site est renvoyé tel quel.
"""

from __future__ import annotations

import math
import warnings
from functools import cache

import numpy as np
import xarray as xr

from marswalk_core.site_package import Site

PLANNING_RESOLUTION_M = 2.0

_MIN_LAYERS = frozenset({"radio_coverage", "illumination"})
_MEAN_LAYERS = frozenset({"dem", "dem_mola", "hillshade", "thermal_inertia", "return_time"})


class PlanningSite(Site):
    """Site dont la grille d'analyse est agrégée d'un facteur entier ``factor``."""

    def __init__(self, base: Site, factor: int) -> None:
        grid = base.manifest.grid
        a, b, c, d, e, f = grid.transform
        coarse = grid.model_copy(
            update={
                "resolution_m": grid.resolution_m * factor,
                "width": grid.width // factor,
                "height": grid.height // factor,
                "transform": (a * factor, b, c, d, e * factor, f),
            }
        )
        super().__init__(base.root, base.manifest.model_copy(update={"grid": coarse}))
        self.base = base
        self.factor = factor

    def _read_full(self, layer_id: str) -> xr.DataArray:
        fine = self.base.read_layer(layer_id)
        k = self.factor
        height, width = self.shape
        blocks = fine.values[: height * k, : width * k].reshape(height, k, width, k)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # blocs entièrement NaN
            if layer_id in _MIN_LAYERS:
                reduced = np.nanmin(blocks, axis=(1, 3))
            elif layer_id in _MEAN_LAYERS:
                reduced = np.nanmean(blocks, axis=(1, 3))
            else:
                reduced = np.nanmax(blocks, axis=(1, 3))
        data = np.asarray(reduced, dtype=np.float32)
        a, _, c, _, e, f = self.transform
        xs = c + a * (np.arange(width) + 0.5)
        ys = f + e * (np.arange(height) + 0.5)
        return xr.DataArray(
            data, dims=("y", "x"), coords={"y": ys, "x": xs}, name=layer_id, attrs=fine.attrs
        )

    def sample(self, layer_id: str, lon: float, lat: float) -> float | None:
        # Les valeurs interrogées restent celles de la grille fine.
        return self.base.sample(layer_id, lon, lat)


@cache
def planning_site(site: Site) -> Site:
    """Le site sur la grille de planification, mis en cache par site ouvert."""
    if isinstance(site, PlanningSite):
        return site
    factor = math.floor(PLANNING_RESOLUTION_M / site.manifest.grid.resolution_m + 1e-9)
    if factor <= 1:
        return site
    return PlanningSite(site, factor)
