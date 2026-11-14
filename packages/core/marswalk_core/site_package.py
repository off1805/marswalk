"""Lecture d'un paquet de site : manifeste et COG (T00, réel dès le départ).

Interface gelée (``taches-agents.md`` section 7) :

- ``load_site(site_id) -> Site``
- ``Site.read_layer(layer_id, window=None) -> xarray.DataArray`` sur la grille d'analyse
- ``Site.sample(layer_id, lon, lat) -> float | None``
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

import numpy as np
import rasterio
import rasterio.windows
import xarray as xr

from marswalk_core.paths import find_package
from marswalk_core.schemas import LayerInfo, LayerStatus, SiteManifest

NODATA = -9999.0
_PROJ_PARAM = re.compile(r"\+(\w+)=([^\s]+)")

Window = tuple[int, int, int, int]
"""Fenêtre en cases : (colonne, ligne, largeur, hauteur)."""


class LayerUnavailableError(LookupError):
    """La couche n'existe pas dans le paquet, ou son statut est ``missing``."""


def parse_proj(proj: str) -> dict[str, str]:
    return dict(_PROJ_PARAM.findall(proj))


class Site:
    """Paquet de site ouvert. Les rasters lus sont gardés en mémoire."""

    def __init__(self, root: Path, manifest: SiteManifest) -> None:
        self.root = root
        self.manifest = manifest
        params = parse_proj(manifest.analysis_crs)
        self.lon0 = float(params.get("lon_0", "0"))
        self.lat_ts = float(params.get("lat_ts", "0"))
        self.radius_m = float(params.get("R", "3396190"))
        self._cache: dict[str, xr.DataArray] = {}

    # -- métadonnées ------------------------------------------------------
    @property
    def site_id(self) -> str:
        return self.manifest.site_id

    @property
    def transform(self) -> tuple[float, float, float, float, float, float]:
        return self.manifest.grid.transform

    @property
    def shape(self) -> tuple[int, int]:
        """(hauteur, largeur) de la grille d'analyse."""
        return (self.manifest.grid.height, self.manifest.grid.width)

    def layer(self, layer_id: str) -> LayerInfo:
        for info in self.manifest.layers:
            if info.id == layer_id:
                return info
        raise LayerUnavailableError(f"Couche absente du manifeste : {layer_id}")

    def has_layer(self, layer_id: str) -> bool:
        try:
            info = self.layer(layer_id)
        except LayerUnavailableError:
            return False
        return info.status != LayerStatus.missing and info.cog is not None

    def raster_layer_ids(self) -> list[str]:
        return [info.id for info in self.manifest.layers if info.cog]

    # -- rasters ----------------------------------------------------------
    def read_layer(self, layer_id: str, window: Window | None = None) -> xr.DataArray:
        """Couche sur la grille d'analyse, en Float32, nodata remplacé par NaN.

        Les coordonnées ``x`` et ``y`` sont les centres de case en mètres (règle R1).
        """
        full = self._cache.get(layer_id)
        if full is None:
            full = self._read_full(layer_id)
            self._cache[layer_id] = full
        if window is None:
            return full
        col, row, width, height = window
        return full.isel(y=slice(row, row + height), x=slice(col, col + width))

    def _read_full(self, layer_id: str) -> xr.DataArray:
        info = self.layer(layer_id)
        if info.status == LayerStatus.missing or not info.cog:
            raise LayerUnavailableError(f"Couche indisponible : {layer_id} ({info.status})")
        path = self.root / info.cog
        with rasterio.open(path) as ds:
            data = ds.read(1).astype(np.float32)
            nodata = ds.nodata if ds.nodata is not None else NODATA
        data[data == nodata] = np.nan
        a, _, c, _, e, f = self.transform
        height, width = data.shape
        xs = c + a * (np.arange(width) + 0.5)
        ys = f + e * (np.arange(height) + 0.5)
        return xr.DataArray(
            data,
            dims=("y", "x"),
            coords={"y": ys, "x": xs},
            name=layer_id,
            attrs={"unit": info.unit or "", "title": info.title},
        )

    # -- interrogation ----------------------------------------------------
    def xy_to_cell(self, x: float, y: float) -> tuple[int, int] | None:
        """(ligne, colonne) de la case qui contient (x, y), ou None hors grille."""
        a, _, c, _, e, f = self.transform
        col = int(np.floor((x - c) / a))
        row = int(np.floor((y - f) / e))
        height, width = self.shape
        if 0 <= row < height and 0 <= col < width:
            return row, col
        return None

    def contains(self, lon: float, lat: float) -> bool:
        west, south, east, north = self.manifest.bbox
        return west <= lon <= east and south <= lat <= north

    def sample(self, layer_id: str, lon: float, lat: float) -> float | None:
        """Valeur de la couche au point (lon, lat), ou None hors emprise, nodata ou absente."""
        from marswalk_core.geodesy import to_analysis

        if not self.has_layer(layer_id):
            return None
        x, y = to_analysis(self, lon, lat)
        cell = self.xy_to_cell(x, y)
        if cell is None:
            return None
        value = float(self.read_layer(layer_id).values[cell])
        return None if np.isnan(value) else value


@cache
def _load(root: str) -> Site:
    path = Path(root)
    manifest = SiteManifest.model_validate(
        json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    )
    return Site(path, manifest)


def load_site(site_id: str) -> Site:
    """Ouvre le paquet ``site_id`` (voir ``marswalk_core.paths.package_search_path``)."""
    return _load(str(find_package(site_id).resolve()))


def open_package(root: Path) -> Site:
    """Ouvre un paquet à partir de son dossier, sans passer par le chemin de recherche."""
    return _load(str(root.resolve()))


def clear_cache() -> None:
    _load.cache_clear()
