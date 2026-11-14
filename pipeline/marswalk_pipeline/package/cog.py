"""Écriture des COG du paquet : Float32, nodata -9999, sur la grille d'analyse (section 5.1)."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import rasterio.shutil
import rasterio.windows
from numpy.typing import NDArray
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT

NODATA = -9999.0


@dataclass(frozen=True)
class GridSpec:
    """Grille d'analyse du site, prise sur le MNT."""

    crs: str
    transform: tuple[float, float, float, float, float, float]
    width: int
    height: int

    @property
    def resolution_m(self) -> float:
        return abs(self.transform[0])

    @classmethod
    def from_raster(cls, path: Path, crs: str) -> GridSpec:
        with rasterio.open(path) as ds:
            t = tuple(float(v) for v in tuple(ds.transform)[:6])
            return cls(crs, (t[0], t[1], t[2], t[3], t[4], t[5]), ds.width, ds.height)

    def matches(self, path: Path) -> bool:
        with rasterio.open(path) as ds:
            same_t = all(
                abs(a - b) < 1e-6
                for a, b in zip(tuple(ds.transform)[:6], self.transform, strict=True)
            )
            return same_t and (ds.width, ds.height) == (self.width, self.height)


def _source_crs(ds: rasterio.io.DatasetReader, fallback: str) -> CRS:
    return ds.crs if ds.crs else CRS.from_string(fallback)


def write_cog(src: Path, dst: Path, grid: GridSpec, categorical: bool) -> None:
    """Copie ``src`` en COG sur ``grid``, en le rééchantillonnant si sa grille diffère.

    Rééchantillonnage : moyenne pour les valeurs continues, mode pour les catégories (une
    image HiRISE à 0,25 m donne ainsi son COG à la résolution de la grille, tandis que ses
    tuiles gardent la pleine résolution).
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    resampling = Resampling.mode if categorical else Resampling.average
    with tempfile.TemporaryDirectory(dir=dst.parent) as tmp:
        staging = Path(tmp) / "staging.tif"
        with rasterio.open(src) as ds:
            src_nodata = ds.nodata
            profile = {
                "driver": "GTiff",
                "width": grid.width,
                "height": grid.height,
                "count": 1,
                "dtype": "float32",
                "crs": CRS.from_string(grid.crs),
                "transform": Affine(*grid.transform),
                "nodata": NODATA,
                "tiled": True,
                "blockxsize": 256,
                "blockysize": 256,
                "compress": "DEFLATE",
                "BIGTIFF": "IF_SAFER",
            }
            on_grid = grid.matches(src)
            reader = (
                ds
                if on_grid
                else WarpedVRT(
                    ds,
                    crs=CRS.from_string(grid.crs),
                    src_crs=_source_crs(ds, grid.crs),
                    transform=Affine(*grid.transform),
                    width=grid.width,
                    height=grid.height,
                    resampling=resampling,
                    nodata=src_nodata if src_nodata is not None else NODATA,
                )
            )
            try:
                with rasterio.open(staging, "w", **profile) as out:
                    for _, win in out.block_windows(1):
                        block = reader.read(1, window=win, masked=True)
                        out.write(_to_float32(block, src_nodata), 1, window=win)
            finally:
                if reader is not ds:
                    reader.close()
        rasterio.shutil.copy(
            staging,
            dst,
            driver="COG",
            compress="DEFLATE",
            predictor=3,
            blocksize=256,
            overview_resampling="nearest" if categorical else "average",
            BIGTIFF="IF_SAFER",
        )


def _to_float32(block: np.ma.MaskedArray, src_nodata: float | None) -> NDArray[np.float32]:
    data = np.ma.filled(block.astype(np.float64), np.nan)
    if src_nodata is not None:
        data[data == src_nodata] = np.nan
    data[~np.isfinite(data)] = NODATA
    return data.astype(np.float32)
