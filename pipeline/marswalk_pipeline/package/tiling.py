"""Tuiles d'affichage WebMercatorQuad (règle R3) et terrain-RGB (D3).

La pyramide se construit par quadrants : au zoom maximal d'une couche, chaque tuile est
échantillonnée dans le raster source (bilinéaire pour les valeurs continues, plus proche
voisin pour les catégories) ; chaque zoom inférieur est obtenu en réduisant de moitié la
mosaïque de ses quatre tuiles filles (Lanczos pour l'imagerie, moyenne, ou plus proche
voisin). Les réductions se font sur les valeurs, avant la palette, et ignorent le nodata.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import rasterio.windows
from numpy.typing import NDArray
from PIL import Image

from marswalk_core.schemas import Legend

from .catalog import Resample

Arr = NDArray[np.float64]
RGBA = NDArray[np.uint8]
TILE = 256
NODATA = -9999.0


# ---------------------------------------------------------------------------
# Géométrie
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Eqc:
    """Équirectangulaire de la règle R1 : ``x = R (λ - λ0) cos φts``, ``y = R φ``."""

    lon0: float
    lat_ts: float
    radius_m: float

    def forward(self, lon: Arr, lat: Arr) -> tuple[Arr, Arr]:
        k = math.cos(math.radians(self.lat_ts))
        x = self.radius_m * np.radians(lon - self.lon0) * k
        y = self.radius_m * np.radians(lat)
        return x, y

    def inverse(self, x: float, y: float) -> tuple[float, float]:
        k = math.cos(math.radians(self.lat_ts))
        return (
            self.lon0 + math.degrees(x / (self.radius_m * k)),
            math.degrees(y / self.radius_m),
        )


def tile_pixel_size_m(z: int, lat: float, radius_m: float) -> float:
    """Côté d'un pixel de tuile au zoom ``z``, en mètres martiens, à la latitude ``lat``."""
    return float(2 * math.pi * radius_m * math.cos(math.radians(lat)) / (TILE * 2**z))


def max_zoom_for(resolution_m: float, lat: float, radius_m: float, minzoom: int) -> int:
    """Plus petit zoom dont le pixel ne dépasse pas la résolution de la couche (section 4)."""
    z = minzoom
    while z < 24 and tile_pixel_size_m(z, lat, radius_m) > resolution_m:
        z += 1
    return z


def tile_range(bbox: tuple[float, float, float, float], z: int) -> tuple[int, int, int, int]:
    """Tuiles (x0, y0, x1, y1), bornes incluses, qui couvrent ``bbox`` au zoom ``z``."""
    west, south, east, north = bbox
    n = 2**z

    def tx(lon: float) -> int:
        return int(min(n - 1, int((lon + 180) / 360 * n)))

    def ty(lat: float) -> int:
        lr = math.radians(lat)
        return int(min(n - 1, int((1 - math.asinh(math.tan(lr)) / math.pi) / 2 * n)))

    return tx(west), ty(north), tx(east), ty(south)


def pixel_centers(z: int, x: int, y: int) -> tuple[Arr, Arr]:
    """Longitudes (colonnes) et latitudes (lignes) des centres de pixels d'une tuile."""
    n = 2**z
    px = (np.arange(TILE) + 0.5) / TILE
    lons = (x + px) / n * 360.0 - 180.0
    lats = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + px) / n))))
    return lons, lats


# ---------------------------------------------------------------------------
# Échantillonnage du raster source
# ---------------------------------------------------------------------------


class RasterSampler:
    """Lit les fenêtres d'un raster nord en haut pour remplir les tuiles du zoom maximal."""

    def __init__(self, path: Path, eqc: Eqc, nearest: bool) -> None:
        self.ds = rasterio.open(path)
        a, b, c, d, e, f = tuple(self.ds.transform)[:6]
        if b != 0 or d != 0 or e >= 0:
            raise ValueError(f"{path} : grille tournée ou retournée, non prise en charge")
        self.a, self.c, self.e, self.f = a, c, e, f
        self.eqc = eqc
        self.nearest = nearest
        self.nodata = self.ds.nodata

    @property
    def resolution_m(self) -> float:
        return float(abs(self.a))

    def close(self) -> None:
        self.ds.close()

    def sample(self, z: int, x: int, y: int) -> Arr:
        lons, lats = pixel_centers(z, x, y)
        xs, _ = self.eqc.forward(lons, np.full_like(lons, self.eqc.lat_ts))
        _, ys = self.eqc.forward(np.full_like(lats, self.eqc.lon0), lats)
        cols = (xs - self.c) / self.a
        rows = (ys - self.f) / self.e
        if self.nearest:
            ci = np.floor(cols).astype(np.int64)
            ri = np.floor(rows).astype(np.int64)
            c0, c1 = int(ci.min()), int(ci.max()) + 1
            r0, r1 = int(ri.min()), int(ri.max()) + 1
        else:
            cols, rows = cols - 0.5, rows - 0.5
            c0, c1 = int(np.floor(cols.min())), int(np.floor(cols.max())) + 2
            r0, r1 = int(np.floor(rows.min())), int(np.floor(rows.max())) + 2
        if c1 <= 0 or r1 <= 0 or c0 >= self.ds.width or r0 >= self.ds.height:
            return np.full((TILE, TILE), np.nan)
        win = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
        block = self.ds.read(1, window=win, boundless=True, masked=True).astype(np.float64)
        data = np.ma.filled(block, np.nan)
        if self.nodata is not None:
            data[data == self.nodata] = np.nan
        if self.nearest:
            return np.asarray(data[np.ix_(ri[:] - r0, ci[:] - c0)])
        return _bilinear(data, rows - r0, cols - c0)


def _bilinear(data: Arr, rows: Arr, cols: Arr) -> Arr:
    """Interpolation bilinéaire ; un voisin nodata est ignoré si un autre est valide."""
    r = np.floor(rows).astype(np.int64)
    c = np.floor(cols).astype(np.int64)
    fr = (rows - r)[:, None]
    fc = (cols - c)[None, :]
    h, w = data.shape
    r0, r1 = np.clip(r, 0, h - 1), np.clip(r + 1, 0, h - 1)
    c0, c1 = np.clip(c, 0, w - 1), np.clip(c + 1, 0, w - 1)
    acc = np.zeros((TILE, TILE))
    wsum = np.zeros((TILE, TILE))
    for rr, cc, wt in (
        (r0, c0, (1 - fr) * (1 - fc)),
        (r0, c1, (1 - fr) * fc),
        (r1, c0, fr * (1 - fc)),
        (r1, c1, fr * fc),
    ):
        v = data[np.ix_(rr, cc)]
        ok = ~np.isnan(v)
        acc += np.where(ok, v, 0.0) * wt
        wsum += np.where(ok, wt, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = acc / wsum
    return np.asarray(np.where(wsum > 1e-9, out, np.nan))


# ---------------------------------------------------------------------------
# Réduction d'un zoom au zoom inférieur
# ---------------------------------------------------------------------------

_FILTERS = {"lanczos": Image.Resampling.LANCZOS, "average": Image.Resampling.BOX}


def downsample(mosaic: Arr, method: Resample) -> Arr:
    """Réduit une mosaïque 512 x 512 de quatre tuiles filles en une tuile 256 x 256."""
    if method == "nearest":
        return np.asarray(mosaic[::2, ::2])
    valid = ~np.isnan(mosaic)
    filt = _FILTERS[method]
    num = Image.fromarray(np.where(valid, mosaic, 0.0).astype(np.float32), "F")
    den = Image.fromarray(valid.astype(np.float32), "F")
    n = np.asarray(num.resize((TILE, TILE), filt), dtype=np.float64)
    d = np.asarray(den.resize((TILE, TILE), filt), dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = n / d
    return np.asarray(np.where(d >= 0.5, out, np.nan))


# ---------------------------------------------------------------------------
# Palettes et encodage
# ---------------------------------------------------------------------------


def _hex(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def render_continuous(values: Arr, legend: Legend) -> RGBA:
    xs = np.array([s.value for s in legend.stops])
    out = np.zeros((*values.shape, 4), dtype=np.uint8)
    valid = ~np.isnan(values)
    v = np.where(valid, values, xs[0])
    for ch in range(3):
        ys = np.array([_hex(s.color)[ch] for s in legend.stops], dtype=np.float64)
        out[..., ch] = np.rint(np.interp(v, xs, ys)).astype(np.uint8)
    out[..., 3] = np.where(valid, 255, 0)
    return out


def render_categorical(values: Arr, legend: Legend, transparent: set[float]) -> RGBA:
    out = np.zeros((*values.shape, 4), dtype=np.uint8)
    for stop in legend.stops:
        if stop.value in transparent:
            continue
        m = values == stop.value
        out[m, :3] = _hex(stop.color)
        out[m, 3] = 255
    return out


def render_terrain_rgb(values: Arr) -> RGBA:
    """Encodage terrain-RGB : ``h = -10000 + (R * 65536 + G * 256 + B) * 0,1``."""
    valid = ~np.isnan(values)
    code = np.rint((np.where(valid, values, -10000.0) + 10000.0) * 10).astype(np.int64)
    code = np.clip(code, 0, 2**24 - 1)
    out = np.zeros((*values.shape, 4), dtype=np.uint8)
    out[..., 0] = (code >> 16) & 255
    out[..., 1] = (code >> 8) & 255
    out[..., 2] = code & 255
    out[..., 3] = np.where(valid, 255, 0)
    return out


def decode_terrain_rgb(rgba: RGBA) -> Arr:
    r, g, b = (rgba[..., i].astype(np.int64) for i in range(3))
    h = -10000.0 + (r * 65536 + g * 256 + b) * 0.1
    return np.asarray(np.where(rgba[..., 3] > 0, h, np.nan))


def stretch(values: Arr, lo: float, hi: float) -> Arr:
    """Étire ``[lo, hi]`` sur ``[0, 255]`` (imagerie), nodata conservé."""
    if hi <= lo:
        return values
    return np.asarray(np.clip((values - lo) / (hi - lo) * 255.0, 0.0, 255.0))


@dataclass(frozen=True)
class Encoder:
    fmt: str  # "webp" ou "png"
    lossless: bool = False
    quality: int = 90

    def save(self, rgba: RGBA, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.fromarray(rgba, "RGBA")
        if self.fmt == "webp":
            img.save(
                path, "WEBP", lossless=self.lossless, quality=self.quality, method=4, exact=True
            )
        else:
            img.save(path, "PNG", compress_level=6)


# ---------------------------------------------------------------------------
# Pyramide
# ---------------------------------------------------------------------------


@dataclass
class PyramidStats:
    tiles: int = 0
    bytes: int = 0


def build_pyramid(
    out_dir: Path,
    sample: Callable[[int, int, int], Arr],
    render: Callable[[Arr], RGBA],
    encoder: Encoder,
    bbox: tuple[float, float, float, float],
    minzoom: int,
    maxzoom: int,
    method: Resample,
) -> PyramidStats:
    """Écrit ``out_dir/{z}/{x}/{y}.<fmt>`` pour les zooms ``minzoom`` à ``maxzoom``."""
    stats = PyramidStats()
    ranges = {z: tile_range(bbox, z) for z in range(minzoom, maxzoom + 1)}

    def inside(z: int, x: int, y: int) -> bool:
        x0, y0, x1, y1 = ranges[z]
        return x0 <= x <= x1 and y0 <= y <= y1

    def visit(z: int, x: int, y: int) -> Arr:
        if not inside(z, x, y):
            return np.full((TILE, TILE), np.nan)
        if z == maxzoom:
            values = sample(z, x, y)
        else:
            mosaic = np.empty((2 * TILE, 2 * TILE))
            for dy in (0, 1):
                for dx in (0, 1):
                    child = visit(z + 1, 2 * x + dx, 2 * y + dy)
                    mosaic[dy * TILE : (dy + 1) * TILE, dx * TILE : (dx + 1) * TILE] = child
            values = downsample(mosaic, method)
        if not np.isnan(values).all():
            path = out_dir / str(z) / str(x) / f"{y}.{encoder.fmt}"
            encoder.save(render(values), path)
            stats.tiles += 1
            stats.bytes += path.stat().st_size
        return values

    x0, y0, x1, y1 = ranges[minzoom]
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            visit(minzoom, x, y)
    return stats


def iter_tiles(bbox: tuple[float, float, float, float], z: int) -> Iterator[tuple[int, int]]:
    x0, y0, x1, y1 = tile_range(bbox, z)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            yield x, y
