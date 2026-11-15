"""Tuiles d'affichage WebMercatorQuad (règle R3) et terrain-RGB (D3).

La pyramide se construit en deux variantes :

- ``build_pyramid`` : variante récursive descendante (zoom min → max), adaptée aux couches
  avec peu de tuiles (< 2 000 au total).
- ``build_pyramid_striped`` : variante en bandes descendantes (zoom max → min), adaptée aux
  couches haute résolution (HiRISE, > 10 000 tuiles au zoom max). Elle lit le raster source
  ligne par ligne au zoom maximal, réduit les paires de lignes immédiatement vers les zooms
  inférieurs, et ne garde en mémoire que 2 lignes de tuiles à la fois par niveau.

Dans les deux cas : au zoom maximal, chaque pixel de tuile est échantillonné dans le raster
source (bilinéaire pour les valeurs continues, plus proche voisin pour les catégories) ; les
zooms inférieurs sont obtenus en réduisant de moitié la mosaïque 512×512 des quatre tuiles
filles (Lanczos pour l'imagerie, moyenne, ou plus proche voisin pour les catégories). Les
réductions se font sur les valeurs, avant la palette, et ignorent le nodata.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import rasterio.enums
import rasterio.windows
from numpy.typing import NDArray
from PIL import Image

from marswalk_core.schemas import Legend

from .catalog import Resample

Arr = NDArray[np.float64]
RGBA = NDArray[np.uint8]
TILE = 256
NODATA = -9999.0

# Seuil à partir duquel on bascule automatiquement sur la variante en bandes.
STRIPED_THRESHOLD = 2000


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
        self.path = path
        self.ds = rasterio.open(path)
        a, b, c, d, e, f = tuple(self.ds.transform)[:6]
        if b != 0 or d != 0 or e >= 0:
            raise ValueError(f"{path} : grille tournée ou retournée, non prise en charge")
        self.a, self.c, self.e, self.f = a, c, e, f
        self.eqc = eqc
        self.nearest = nearest
        self.nodata = self.ds.nodata
        # Facteurs d'overview disponibles (1 = résolution native)
        self._overview_factors: list[int] = [1, *self.ds.overviews(1)]

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

    def sample_band(
        self, z: int, ty_min: int, ty_max: int, tx_min: int, tx_max: int
    ) -> dict[tuple[int, int], Arr]:
        """Lit une bande de lignes de tuiles en une seule opération I/O.

        Lit la région du raster source couvrant les tuiles (tx_min..tx_max, ty_min..ty_max)
        au zoom z, puis découpe en tuiles individuelles.  Beaucoup plus efficace que d'appeler
        ``sample`` pour chaque tuile quand les tuiles se touchent.
        """
        # Coin nord-ouest de la première tuile et sud-est de la dernière
        n = 2**z
        lon_w = (tx_min + 0.0) / n * 360.0 - 180.0
        lon_e = (tx_max + 1.0) / n * 360.0 - 180.0
        lat_n = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty_min / n))))
        lat_s = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (ty_max + 1) / n))))

        x_w, _ = self.eqc.forward(np.array([lon_w]), np.array([self.eqc.lat_ts]))
        x_e, _ = self.eqc.forward(np.array([lon_e]), np.array([self.eqc.lat_ts]))
        _, y_n = self.eqc.forward(np.array([self.eqc.lon0]), np.array([lat_n]))
        _, y_s = self.eqc.forward(np.array([self.eqc.lon0]), np.array([lat_s]))

        col_l = int(np.floor((float(x_w[0]) - self.c) / self.a - 0.5))
        col_r = int(np.floor((float(x_e[0]) - self.c) / self.a + 1.5))
        row_t = int(np.floor((float(y_n[0]) - self.f) / self.e - 0.5))
        row_b = int(np.floor((float(y_s[0]) - self.f) / self.e + 1.5))

        if col_r <= 0 or row_b <= 0 or col_l >= self.ds.width or row_t >= self.ds.height:
            return {}

        win = rasterio.windows.Window(col_l, row_t, col_r - col_l, row_b - row_t)
        block = self.ds.read(1, window=win, boundless=True, masked=True).astype(np.float64)
        data = np.ma.filled(block, np.nan)
        if self.nodata is not None:
            data[data == self.nodata] = np.nan

        # Découper chaque tuile depuis la bande
        result: dict[tuple[int, int], Arr] = {}
        for ty in range(ty_min, ty_max + 1):
            for tx in range(tx_min, tx_max + 1):
                lons_t, lats_t = pixel_centers(z, tx, ty)
                xs_t, _ = self.eqc.forward(lons_t, np.full_like(lons_t, self.eqc.lat_ts))
                _, ys_t = self.eqc.forward(np.full_like(lats_t, self.eqc.lon0), lats_t)
                cols_t = (xs_t - self.c) / self.a - col_l
                rows_t = (ys_t - self.f) / self.e - row_t
                if self.nearest:
                    ci = np.floor(cols_t).astype(np.int64)
                    ri = np.floor(rows_t).astype(np.int64)
                    ci = np.clip(ci, 0, data.shape[1] - 1)
                    ri = np.clip(ri, 0, data.shape[0] - 1)
                    result[(tx, ty)] = np.asarray(data[np.ix_(ri, ci)])
                else:
                    cols_t -= 0.5
                    rows_t -= 0.5
                    result[(tx, ty)] = _bilinear(data, rows_t, cols_t)
        return result


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
# Pyramide (variante récursive descendante)
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
    """Écrit ``out_dir/{z}/{x}/{y}.<fmt>`` pour les zooms ``minzoom`` à ``maxzoom``.

    Variante récursive : part du zoom min et descend récursivement jusqu'au zoom max.
    Adaptée aux couches avec peu de tuiles (< ``STRIPED_THRESHOLD``).
    """
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


# ---------------------------------------------------------------------------
# Pyramide en bandes (variante séquentielle descendante)
# ---------------------------------------------------------------------------


def _reduce_tile_row(
    z_child: int,
    child_ty: int,
    ranges: dict[int, tuple[int, int, int, int]],
    accumulate: dict[int, dict[tuple[int, int], Arr]],
    out_dir: Path,
    encoder: Encoder,
    render: Callable[[Arr], RGBA],
    method: Resample,
    stats: PyramidStats,
    minzoom: int,
) -> None:
    """Réduit les lignes cy=(child_ty-1, child_ty) au zoom z_child vers z_child-1.

    Appelée après avoir lu la ligne child_ty (paire depuis cy0) au zoom z_child.
    La paire (cy-1, cy) produit la ligne py correspondante au zoom z_parent.
    La ligne cy-1 est purgée de l'accumulateur après réduction.
    """
    if z_child <= minzoom:
        return
    z_parent = z_child - 1
    if z_parent not in ranges:
        return

    cx0, cy0, cx1, cy1 = ranges[z_child]
    px0, py0, px1, py1 = ranges[z_parent]

    # Index relatif de la ligne enfant courante depuis cy0
    rel = child_ty - cy0
    # Une ligne parente est produite quand on termine la 2e ligne d'une paire, c.-à-d.
    # rel impair (0-indexé), ou quand c'est la dernière ligne disponible.
    is_odd = rel % 2 == 1
    is_last = child_ty == cy1
    if not (is_odd or is_last):
        return

    # La paire (cy_a, cy_b) produit parent_ty
    cy_a = cy0 + 2 * (rel // 2)
    cy_b = cy_a + 1
    parent_ty = py0 + rel // 2

    if not (py0 <= parent_ty <= py1):
        return

    for px in range(px0, px1 + 1):
        mosaic = np.full((2 * TILE, 2 * TILE), np.nan)
        for dy, cy in enumerate((cy_a, cy_b)):
            if cy0 <= cy <= cy1:
                for dx in (0, 1):
                    cx = 2 * px + dx
                    if cx0 <= cx <= cx1:
                        child_vals = accumulate[z_child].get((cx, cy))
                        if child_vals is not None:
                            mosaic[
                                dy * TILE : (dy + 1) * TILE,
                                dx * TILE : (dx + 1) * TILE,
                            ] = child_vals
        values = downsample(mosaic, method)
        accumulate[z_parent][(px, parent_ty)] = values
        if not np.isnan(values).all():
            path = out_dir / str(z_parent) / str(px) / f"{parent_ty}.{encoder.fmt}"
            encoder.save(render(values), path)
            stats.tiles += 1
            stats.bytes += path.stat().st_size

    # Purger cy_a pour libérer la mémoire (cy_b sera purgé à la prochaine paire)
    for cx in range(cx0, cx1 + 1):
        accumulate[z_child].pop((cx, cy_a), None)

    # Propager récursivement vers les zooms encore inférieurs
    _reduce_tile_row(
        z_parent, parent_ty, ranges, accumulate, out_dir, encoder, render, method, stats, minzoom
    )


def build_pyramid_striped(
    out_dir: Path,
    sampler: RasterSampler,
    render: Callable[[Arr], RGBA],
    encoder: Encoder,
    bbox: tuple[float, float, float, float],
    minzoom: int,
    maxzoom: int,
    method: Resample,
    log: Callable[[str], None] = lambda _: None,
) -> PyramidStats:
    """Variante séquentielle de ``build_pyramid`` pour les couches haute résolution.

    Lit le raster source par rangées de tuiles (une lecture I/O par ligne de tuiles),
    réduit les paires de lignes immédiatement vers les zooms inférieurs, et ne garde en
    mémoire que quelques lignes de tuiles à la fois.

    À utiliser quand le nombre de tuiles au zoom maximal dépasse ``STRIPED_THRESHOLD``.
    """
    stats = PyramidStats()
    ranges = {z: tile_range(bbox, z) for z in range(minzoom, maxzoom + 1)}

    accumulate: dict[int, dict[tuple[int, int], Arr]] = {z: {} for z in range(minzoom, maxzoom + 1)}

    x0_max, y0_max, x1_max, y1_max = ranges[maxzoom]
    total_rows = y1_max - y0_max + 1

    for done_rows, abs_ty in enumerate(range(y0_max, y1_max + 1), start=1):
        # Lire toute la rangée de tuiles en une seule opération I/O
        row_tiles = sampler.sample_band(maxzoom, abs_ty, abs_ty, x0_max, x1_max)
        for abs_tx in range(x0_max, x1_max + 1):
            values = row_tiles.get((abs_tx, abs_ty), np.full((TILE, TILE), np.nan))
            accumulate[maxzoom][(abs_tx, abs_ty)] = values
            if not np.isnan(values).all():
                path = out_dir / str(maxzoom) / str(abs_tx) / f"{abs_ty}.{encoder.fmt}"
                encoder.save(render(values), path)
                stats.tiles += 1
                stats.bytes += path.stat().st_size
        if done_rows % 20 == 0 or abs_ty == y1_max:
            log(f"  z{maxzoom} ligne {done_rows}/{total_rows}")

        _reduce_tile_row(
            maxzoom, abs_ty, ranges, accumulate, out_dir, encoder, render, method, stats, minzoom
        )

    return stats


def build_pyramid_auto(
    out_dir: Path,
    sampler: RasterSampler,
    render: Callable[[Arr], RGBA],
    encoder: Encoder,
    bbox: tuple[float, float, float, float],
    minzoom: int,
    maxzoom: int,
    method: Resample,
    log: Callable[[str], None] = lambda _: None,
) -> PyramidStats:
    """Choisit automatiquement entre ``build_pyramid`` et ``build_pyramid_striped``.

    Utilise la variante en bandes si le nombre de tuiles au zoom maximal dépasse
    ``STRIPED_THRESHOLD`` (default 2 000).
    """
    x0, y0, x1, y1 = tile_range(bbox, maxzoom)
    n_tiles_max = (x1 - x0 + 1) * (y1 - y0 + 1)
    if n_tiles_max > STRIPED_THRESHOLD:
        log(f"({n_tiles_max} tuiles au z{maxzoom} -> variante en bandes)")
        return build_pyramid_striped(
            out_dir, sampler, render, encoder, bbox, minzoom, maxzoom, method, log
        )
    return build_pyramid(out_dir, sampler.sample, render, encoder, bbox, minzoom, maxzoom, method)
