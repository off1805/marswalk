"""Génère le paquet du site fictif dans ``fixtures/sites/fictif/`` (T00).

Le site fait 2 x 2 km à 2 m, centré sur Jezero. Il contient un plateau limité par une
falaise (comme le front du delta), un petit cratère au bord abrupt, un champ de dunes à faible inertie thermique,
un chaos de blocs, deux unités minéralogiques, un habitat et quatre cibles. Toutes les
couches de la section 5.3 y existent, avec ``source.instrument = "SYNTHETIC"``.

Les couches dérivées sont calculées ici de façon simple : D2 et D3 les recalculent
proprement. La commande est déterministe (graine dans ``config/sites/fictif/site.yaml``).

Usage : ``uv run python tools/make_fictif.py [--out fixtures/sites/fictif]``
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from numpy.typing import NDArray
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import Affine

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root
from marswalk_core.schemas import (
    MARS_2000_RADIUS_M,
    Feature,
    FeatureCollection,
    GridInfo,
    LayerInfo,
    LayerKind,
    LayerSource,
    Legend,
    LegendStop,
    LineStringGeometry,
    LonLat,
    PointGeometry,
    SiteManifest,
    TileInfo,
    Uncertainty,
)

Arr = NDArray[np.float64]
NODATA = -9999.0
GENERATOR = "tools/make_fictif.py (T00)"
ACQUIRED = date(2026, 11, 1)


# ---------------------------------------------------------------------------
# Outils raster
# ---------------------------------------------------------------------------


def box_mean(a: Arr, size: int) -> Arr:
    """Moyenne glissante carrée de côté ``size`` (impair), bords répliqués."""
    r = size // 2
    p = np.pad(a, r + 1, mode="edge")
    c = p.cumsum(0).cumsum(1)
    s = c[size:, size:] - c[:-size, size:] - c[size:, :-size] + c[:-size, :-size]
    return np.asarray(s[: a.shape[0], : a.shape[1]] / (size * size))


def dilate(mask: NDArray[np.bool_], cells: int) -> NDArray[np.bool_]:
    return np.asarray(box_mean(mask.astype(np.float64), 2 * cells + 1) > 1e-9)


def smoothstep(x: Arr) -> Arr:
    x = np.clip(x, 0.0, 1.0)
    return np.asarray(x * x * (3 - 2 * x))


@dataclass
class Grid:
    size_m: float
    res: float
    x0: float  # bord ouest, m
    y0: float  # bord nord, m
    yc: float  # centre, m
    n: int

    @property
    def transform(self) -> tuple[float, float, float, float, float, float]:
        return (self.res, 0.0, self.x0, 0.0, -self.res, self.y0)


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------


@dataclass
class Terrain:
    dem: Arr
    plateau: NDArray[np.bool_]
    dunes: Arr
    crater_floor: NDArray[np.bool_]
    boulders: Arr
    clay: NDArray[np.bool_]


def make_terrain(u: Arr, v: Arr, rng: np.random.Generator) -> Terrain:
    dem = -2600.0 + 0.004 * v
    for _ in range(6):
        k = rng.uniform(1 / 900, 1 / 250, 2)
        ph = rng.uniform(0, 2 * math.pi, 2)
        dem += rng.uniform(0.3, 0.8) * np.sin(2 * math.pi * k[0] * u + ph[0]) * np.cos(
            2 * math.pi * k[1] * v + ph[1]
        )

    # Plateau au nord, limité par une falaise d'environ 22 m.
    v_scarp = 450.0 + 40.0 * np.sin(u / 180.0)
    rise = smoothstep((v - v_scarp) / 15.0)
    dem += 22.0 * rise
    plateau = rise > 0.5

    # Petit cratère au bord abrupt.
    cu, cv, radius = 520.0, -380.0, 260.0
    r = np.hypot(u - cu, v - cv)
    inside = r < radius
    dem += np.where(inside, -35.0 * (1 - (r / radius) ** 4), 0.0)
    dem += 12.0 * np.exp(-(((r - radius) / 40.0) ** 2))
    crater_floor = r < 0.8 * radius

    # Champ de dunes à l'ouest.
    du = smoothstep((-350.0 - u) / 80.0) * smoothstep((250.0 - v) / 80.0) * smoothstep(
        (v + 700.0) / 80.0
    )
    phase = 2 * math.pi * (u * math.cos(math.radians(30)) + v * math.sin(math.radians(30))) / 45.0
    dem += du * 2.5 * (0.5 + 0.5 * np.sin(phase))

    # Chaos de blocs.
    bu, bv, br = -150.0, -600.0, 170.0
    boulders = np.zeros_like(u)
    for _ in range(140):
        ang = rng.uniform(0, 2 * math.pi)
        dist = br * math.sqrt(rng.uniform(0, 1))
        pu, pv = bu + dist * math.cos(ang), bv + dist * math.sin(ang)
        rad = rng.uniform(2.0, 6.0)
        h = rng.uniform(1.0, 3.0)
        boulders = np.maximum(boulders, h * np.exp(-((u - pu) ** 2 + (v - pv) ** 2) / rad**2))
    dem += boulders

    dem += rng.normal(0.0, 0.03, u.shape)
    clay = (u > 200.0) & (v < 250.0) & ~inside & ~plateau
    return Terrain(dem, plateau, du, crater_floor, boulders, clay)


def slope_deg(dem: Arr, res: float) -> Arr:
    gy, gx = np.gradient(dem, res)
    return np.asarray(np.degrees(np.arctan(np.hypot(gx, gy))))


def hillshade(dem: Arr, res: float, az: float = 315.0, alt: float = 45.0) -> Arr:
    gy, gx = np.gradient(dem, res)
    # Lignes vers le sud : la dérivée nord est -gy.
    dzdx, dzdy = gx, -gy
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, -dzdy)
    zen = math.radians(90 - alt)
    azr = math.radians(az)
    shade = math.cos(zen) * np.cos(slope) + math.sin(zen) * np.sin(slope) * np.cos(azr - aspect)
    return np.asarray(np.clip(shade, 0, 1) * 255.0)


def line_of_sight(
    dem: Arr, grid: Grid, ou: float, ov: float, mast_m: float, target_m: float
) -> Arr:
    """1 si la case voit l'antenne placée en (ou, ov), 0 sinon."""
    n = grid.n
    col0 = int((ou - (-grid.size_m / 2)) / grid.res)
    row0 = int((grid.size_m / 2 - ov) / grid.res)
    z0 = dem[row0, col0] + mast_m
    rows, cols = np.mgrid[0:n, 0:n]
    out = np.ones((n, n), dtype=np.float64)
    steps = np.linspace(0.02, 0.98, 64)
    for r0 in range(0, n, 100):
        rr = rows[r0 : r0 + 100].astype(np.float64)
        cc = cols[r0 : r0 + 100].astype(np.float64)
        zt = dem[r0 : r0 + 100] + target_m
        visible = np.ones(rr.shape, dtype=bool)
        for t in steps:
            sr = np.clip(np.rint(row0 + (rr - row0) * t).astype(int), 0, n - 1)
            sc = np.clip(np.rint(col0 + (cc - col0) * t).astype(int), 0, n - 1)
            ray = z0 + (zt - z0) * t
            visible &= dem[sr, sc] <= ray + 0.05
        out[r0 : r0 + 100] = visible
    return out


def illumination(dem: Arr, res: float, az: float = 90.0, alt: float = 20.0) -> Arr:
    """Fraction éclairée à l'heure de référence (Soleil à l'est, 20° de hauteur)."""
    shade = hillshade(dem, res, az, alt) / 255.0
    lit = np.ones_like(dem, dtype=bool)
    du, dv = math.sin(math.radians(az)), math.cos(math.radians(az))
    tan_alt = math.tan(math.radians(alt))
    n = dem.shape[0]
    for k in range(1, 150):
        dist = k * res * 2
        dc, dr = round(du * dist / res), -round(dv * dist / res)
        shifted = np.full_like(dem, -1e9)
        rs = slice(max(0, -dr), min(n, n - dr))
        rd = slice(max(0, dr), min(n, n + dr))
        cs = slice(max(0, -dc), min(n, n - dc))
        cd = slice(max(0, dc), min(n, n + dc))
        shifted[rs, cs] = dem[rd, cd]
        lit &= shifted <= dem + dist * tan_alt
    return np.asarray(np.where(lit, shade, 0.0))


# ---------------------------------------------------------------------------
# Rendu des tuiles
# ---------------------------------------------------------------------------


def hex_rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def continuous_rgba(values: Arr, legend: Legend) -> NDArray[np.uint8]:
    stops = legend.stops
    xs = np.array([s.value for s in stops])
    out = np.zeros((*values.shape, 4), dtype=np.uint8)
    valid = ~np.isnan(values)
    v = np.where(valid, values, xs[0])
    for ch in range(3):
        ys = np.array([hex_rgb(s.color)[ch] for s in stops], dtype=np.float64)
        out[..., ch] = np.interp(v, xs, ys).astype(np.uint8)
    out[..., 3] = np.where(valid, 255, 0)
    return out


def categorical_rgba(
    values: Arr, legend: Legend, transparent: set[float]
) -> NDArray[np.uint8]:
    out = np.zeros((*values.shape, 4), dtype=np.uint8)
    for stop in legend.stops:
        if stop.value in transparent:
            continue
        m = values == stop.value
        out[m, :3] = hex_rgb(stop.color)
        out[m, 3] = 255
    return out


def terrain_rgb(values: Arr) -> NDArray[np.uint8]:
    """Encodage terrain-RGB : h = -10000 + (R*65536 + G*256 + B) * 0.1."""
    valid = ~np.isnan(values)
    code = np.rint((np.where(valid, values, -10000.0) + 10000.0) * 10).astype(np.int64)
    out = np.zeros((*values.shape, 4), dtype=np.uint8)
    out[..., 0] = (code >> 16) & 255
    out[..., 1] = (code >> 8) & 255
    out[..., 2] = code & 255
    out[..., 3] = np.where(valid, 255, 0)
    return out


def tile_range(bbox: tuple[float, float, float, float], z: int) -> tuple[int, int, int, int]:
    west, south, east, north = bbox
    n = 2**z

    def tx(lon: float) -> int:
        return int((lon + 180) / 360 * n)

    def ty(lat: float) -> int:
        lr = math.radians(lat)
        return int((1 - math.asinh(math.tan(lr)) / math.pi) / 2 * n)

    return tx(west), ty(north), tx(east), ty(south)


def sample_tile(
    grid_values: Arr, grid: Grid, lon0: float, lat_ts: float, z: int, x: int, y: int
) -> Arr:
    """Échantillonne la grille d'analyse (plus proche voisin) sur une tuile WebMercatorQuad."""
    n = 2**z
    px = (np.arange(256) + 0.5) / 256
    lons = (x + px) / n * 360.0 - 180.0
    lats = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + px) / n))))
    k = math.cos(math.radians(lat_ts))
    xs = MARS_2000_RADIUS_M * np.radians(lons - lon0) * k
    ys = MARS_2000_RADIUS_M * np.radians(lats)
    cols = np.floor((xs - grid.x0) / grid.res).astype(int)
    rows = np.floor((grid.y0 - ys) / grid.res).astype(int)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    inside = (rr >= 0) & (rr < grid.n) & (cc >= 0) & (cc < grid.n)
    out = np.full((256, 256), np.nan)
    out[inside] = grid_values[rr[inside], cc[inside]]
    return out


def write_tiles(
    out_dir: Path,
    values: Arr,
    grid: Grid,
    lon0: float,
    lat_ts: float,
    bbox: tuple[float, float, float, float],
    zooms: range,
    render: Callable[[Arr], NDArray[np.uint8]],
    fmt: str,
    lossless: bool,
) -> int:
    count = 0
    for z in zooms:
        x0, y0, x1, y1 = tile_range(bbox, z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                tile = sample_tile(values, grid, lon0, lat_ts, z, x, y)
                if np.isnan(tile).all():
                    continue
                rgba = render(tile)
                path = out_dir / str(z) / str(x) / f"{y}.{fmt}"
                path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.fromarray(rgba, "RGBA")
                if fmt == "webp":
                    img.save(path, "WEBP", lossless=lossless, quality=80, method=6)
                else:
                    img.save(path, "PNG", optimize=True)
                count += 1
    return count


# ---------------------------------------------------------------------------
# Catalogue des couches du site fictif
# ---------------------------------------------------------------------------

VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]
CIVIDIS = ["#00224e", "#35456c", "#666970", "#948e77", "#c8b866", "#fee838"]
GRAY = ["#000000", "#ffffff"]


def ramp(lo: float, hi: float, colors: list[str]) -> Legend:
    n = len(colors) - 1
    return Legend(
        type="continuous",
        stops=[LegendStop(value=lo + (hi - lo) * i / n, color=c) for i, c in enumerate(colors)],
    )


def cat(items: list[tuple[float, str, str]]) -> Legend:
    return Legend(
        type="categorical", stops=[LegendStop(value=v, color=c, label=lbl) for v, c, lbl in items]
    )


@dataclass
class LayerSpec:
    id: str
    title: str
    kind: LayerKind
    unit: str | None
    value_range: tuple[float, float]
    resolution_m: float
    legend: Legend
    instrument_note: str
    uncertainty: Uncertainty
    quantum: float
    transparent: tuple[float, ...] = ()


def layer_specs() -> list[LayerSpec]:
    def u(value: float | None = None, unit: str | None = None,
          coreg_m: float | None = None) -> Uncertainty:
        return Uncertainty(value=value, unit=unit, coreg_m=coreg_m)

    return [
        LayerSpec("hirise_vis", "Imagerie (type HiRISE)", LayerKind.imagery, "DN", (0, 255), 2.0,
                  ramp(0, 255, GRAY), "image synthétique", u(coreg_m=0.0), 1.0),
        LayerSpec("ctx_vis", "Contexte (type CTX)", LayerKind.imagery, "DN", (0, 255), 6.0,
                  ramp(0, 255, GRAY), "image floutée", u(coreg_m=0.0), 1.0),
        LayerSpec("dem", "Altitude (MNT)", LayerKind.dem, "m", (-2630, -2550), 2.0,
                  ramp(-2630, -2550, CIVIDIS), "MNT synthétique", u(0.3, "m", 0.0), 0.01),
        LayerSpec("dem_mola", "Altitude (type MOLA)", LayerKind.dem, "m", (-2630, -2550), 463.0,
                  ramp(-2630, -2550, CIVIDIS), "MNT lissé", u(3.0, "m", 0.0), 0.1),
        LayerSpec("slope", "Pente", LayerKind.derived, "deg", (0, 60), 2.0,
                  ramp(0, 60, VIRIDIS), "dérivée du MNT", u(0.5, "deg", 0.0), 0.01),
        LayerSpec("roughness", "Rugosité", LayerKind.derived, "m", (0, 1), 2.0,
                  ramp(0, 1, VIRIDIS), "écart type local sur 10 m", u(0.05, "m", 0.0), 0.001),
        LayerSpec("hillshade", "Ombrage", LayerKind.derived, None, (0, 255), 2.0,
                  ramp(0, 255, GRAY), "azimut 315°, hauteur 45°", u(), 1.0),
        LayerSpec("obstacles", "Obstacles (avec tampon)", LayerKind.derived, None, (0, 1), 2.0,
                  cat([(0, "#000000", "libre"), (1, "#cc79a7", "obstacle")]),
                  "blocs de plus de 0,4 m, tampon 2 m", u(), 1.0, (0,)),
        LayerSpec("scarps", "Ruptures de pente", LayerKind.derived, None, (0, 1), 2.0,
                  cat([(0, "#000000", "aucune"), (1, "#e69f00", "falaise ou bord")]),
                  "pente supérieure à 30°", u(), 1.0, (0,)),
        LayerSpec("thermal_inertia", "Inertie thermique", LayerKind.thermal, "J m-2 K-1 s-1/2",
                  (100, 800), 100.0, ramp(100, 800, VIRIDIS), "type THEMIS",
                  u(50.0, "J m-2 K-1 s-1/2", 0.0), 1.0),
        LayerSpec("loose_soil", "Classe de sol", LayerKind.derived, None, (0, 3), 2.0,
                  cat([(0, "#7f7f7f", "roche"), (1, "#c9a66b", "mixte"),
                       (2, "#e8c77a", "meuble"), (3, "#f5e6a8", "dune")]),
                  "classes synthétiques", u(), 1.0),
        LayerSpec("crism_minerals", "Minéralogie", LayerKind.spectral, None, (0, 2), 18.0,
                  cat([(0, "#000000", "non détecté"), (1, "#56b4e9", "argiles et carbonates"),
                       (2, "#009e73", "olivine")]),
                  "type CRISM", u(coreg_m=0.0), 1.0, (0,)),
        LayerSpec("radio_coverage", "Couverture radio", LayerKind.derived, None, (0, 1), 2.0,
                  cat([(0, "#0072b2", "hors couverture"), (1, "#000000", "couvert")]),
                  "visibilité depuis l'antenne de l'habitat (3 m)", u(), 1.0, (1,)),
        LayerSpec("illumination", "Éclairement", LayerKind.derived, None, (0, 1), 2.0,
                  ramp(0, 1, GRAY), "Soleil à l'est, 20° de hauteur", u(), 0.01),
        LayerSpec("return_time", "Temps de retour", LayerKind.derived, "s", (0, 2000), 2.0,
                  ramp(0, 2000, VIRIDIS), "ligne droite à 1 m/s (bouchon P3)", u(), 1.0),
    ]


# ---------------------------------------------------------------------------
# Génération
# ---------------------------------------------------------------------------


def write_cog(path: Path, values: Arr, grid: Grid, crs: str, quantum: float) -> None:
    data = np.where(np.isnan(values), NODATA, np.round(values / quantum) * quantum).astype(
        np.float32
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="COG",
        width=grid.n,
        height=grid.n,
        count=1,
        dtype="float32",
        crs=CRS.from_string(crs),
        transform=Affine(*grid.transform),
        nodata=NODATA,
        compress="DEFLATE",
        predictor=3,
        blocksize=256,
        overview_resampling="nearest",
    ) as ds:
        ds.write(data, 1)


def generate(out: Path) -> SiteManifest:
    cfg = load_site_config("fictif")
    rng = np.random.default_rng(int(cfg["seed"]))
    res = float(cfg["resolution_m"])
    size = float(cfg["size_m"])
    lon0 = float(cfg["center"]["lon"])
    lat_c = float(cfg["center"]["lat"])
    crs = str(cfg["analysis_crs"])
    yc = round(MARS_2000_RADIUS_M * math.radians(lat_c) / res) * res
    n = int(size / res)
    grid = Grid(size, res, -size / 2, yc + size / 2, yc, n)

    centers = (np.arange(n) + 0.5) * res
    u = np.broadcast_to(-size / 2 + centers, (n, n)).astype(np.float64)
    v = np.broadcast_to((size / 2 - centers)[:, None], (n, n)).astype(np.float64)

    def lonlat(du: float, dv: float) -> LonLat:
        k = math.cos(math.radians(lat_c))
        return LonLat(
            round(lon0 + math.degrees(du / (MARS_2000_RADIUS_M * k)), 7),
            round(math.degrees((yc + dv) / MARS_2000_RADIUS_M), 7),
        )

    t = make_terrain(u, v, rng)
    dem = t.dem
    slope = slope_deg(dem, res)
    detrended = dem - box_mean(dem, 5)
    roughness = np.sqrt(np.maximum(box_mean(detrended**2, 5), 0.0))
    shade = hillshade(dem, res)
    obstacles = dilate(t.boulders > 0.4, 1).astype(np.float64)
    scarps = (slope > 30.0).astype(np.float64)

    soil = np.ones_like(dem)
    soil[t.plateau] = 0
    soil[t.boulders > 0.2] = 0
    soil[t.crater_floor] = 2
    soil[t.dunes > 0.15] = 2
    soil[t.dunes > 0.6] = 3

    ti = np.full_like(dem, 330.0)
    ti[t.plateau] = 560.0
    ti[t.crater_floor] = 260.0
    ti = ti * (1 - t.dunes) + 150.0 * t.dunes
    ti = np.where(t.boulders > 0.2, 700.0, ti)
    ti = box_mean(ti, 25) + rng.normal(0, 8, dem.shape)

    minerals = np.zeros_like(dem)
    minerals[t.plateau] = 1
    minerals[t.clay] = 2

    hab_u, hab_v = float(cfg["habitat"]["x"]), float(cfg["habitat"]["y"])
    radio = line_of_sight(dem, grid, hab_u, hab_v, mast_m=3.0, target_m=1.8)
    illum = illumination(dem, res)
    ret = np.hypot(u - hab_u, v - hab_v) / 1.0

    albedo = 150 - 50 * t.dunes + 25 * t.plateau.astype(float) - 15 * t.crater_floor
    vis = np.clip(0.55 * shade + 0.45 * albedo + rng.normal(0, 6, dem.shape), 0, 255)
    ctx = box_mean(vis, 3)
    mola = box_mean(dem, 101)

    values: dict[str, Arr] = {
        "hirise_vis": vis, "ctx_vis": ctx, "dem": dem, "dem_mola": mola, "slope": slope,
        "roughness": roughness, "hillshade": shade, "obstacles": obstacles, "scarps": scarps,
        "thermal_inertia": ti, "loose_soil": soil, "crism_minerals": minerals,
        "radio_coverage": radio, "illumination": illum, "return_time": ret,
    }

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    corners = [lonlat(-size / 2, size / 2), lonlat(size / 2, -size / 2)]
    bbox = (corners[0].lon, corners[1].lat, corners[1].lon, corners[0].lat)
    zooms = range(int(cfg["tiles"]["minzoom"]), int(cfg["tiles"]["maxzoom"]) + 1)

    layers: list[LayerInfo] = []
    for spec in layer_specs():
        arr = values[spec.id]
        write_cog(out / "cog" / f"{spec.id}.tif", arr, grid, crs, spec.quantum)
        legend = spec.legend
        transparent = set(spec.transparent)
        render: Callable[[Arr], NDArray[np.uint8]]
        if legend.type == "continuous":
            def render(a: Arr, lg: Legend = legend) -> NDArray[np.uint8]:
                return continuous_rgba(a, lg)
        else:
            def render(a: Arr, lg: Legend = legend, tr: set[float] = transparent) -> NDArray[np.uint8]:
                return categorical_rgba(a, lg, tr)
        write_tiles(out / "tiles" / spec.id, arr, grid, lon0, lat_c, bbox, zooms, render, "webp",
                    lossless=legend.type == "categorical")
        layers.append(
            LayerInfo(
                id=spec.id, title=spec.title, kind=spec.kind, unit=spec.unit,
                value_range=spec.value_range, resolution_m=spec.resolution_m, acquired=ACQUIRED,
                source=LayerSource(instrument="SYNTHETIC", mission="Marswalk",
                                   product_id=f"FICTIF_{spec.id.upper()}", url=None,
                                   note=spec.instrument_note),
                uncertainty=spec.uncertainty, legend=legend, cog=f"cog/{spec.id}.tif",
                tiles=TileInfo(path=f"tiles/{spec.id}/{{z}}/{{x}}/{{y}}.webp",
                               minzoom=zooms.start, maxzoom=zooms.stop - 1, format="webp"),
            )
        )

    write_tiles(out / "tiles" / "terrain_rgb", dem, grid, lon0, lat_c, bbox, zooms, terrain_rgb,
                "png", lossless=True)

    # Couches vectorielles.
    vector_dir = out / "vector"
    vector_dir.mkdir()
    rover_u, rover_v = float(cfg["rover"]["x"]), float(cfg["rover"]["y"])
    traverse_pts = [(-900, -300), (-600, -250), (-300, -120), (rover_u, rover_v)]
    traverse = FeatureCollection(features=[Feature(
        id="traverse-1",
        geometry=LineStringGeometry(coordinates=[lonlat(a, b) for a, b in traverse_pts]),
        properties={"name": "Trajet de Perseverance (synthétique)", "sol_start": 1, "sol_end": 12},
    )])
    images = FeatureCollection(features=[
        Feature(id=f"img-{i}", geometry=PointGeometry(coordinates=lonlat(a, b)),
                properties={"image_id": f"FICTIF_IMG_{i:03d}", "sol": 2 + i,
                            "instrument": "SYNTHETIC", "camera": "Mastcam-Z (fictif)",
                            "thumb": None, "azimuth_deg": (40 * i) % 360})
        for i, (a, b) in enumerate([(-850, -290), (-620, -240), (-450, -180), (-310, -110),
                                    (-150, -40), (40, 30)])
    ])
    (vector_dir / "rover_traverse.geojson").write_text(traverse.model_dump_json(indent=1))
    (vector_dir / "ground_images.geojson").write_text(images.model_dump_json(indent=1))
    (out / "thumbs").mkdir()
    (out / "thumbs" / ".gitkeep").write_text("")
    for lid, title, path in (("rover_traverse", "Trajet du rover", "rover_traverse"),
                             ("ground_images", "Images au sol", "ground_images")):
        layers.append(LayerInfo(
            id=lid, title=title, kind=LayerKind.vector if lid == "rover_traverse" else LayerKind.ground,
            source=LayerSource(instrument="SYNTHETIC", mission="Marswalk",
                               product_id=f"FICTIF_{lid.upper()}"),
            acquired=ACQUIRED, vector=f"vector/{path}.geojson",
        ))

    manifest = SiteManifest(
        site_id="fictif",
        name=str(cfg["name"]),
        bbox=bbox,
        analysis_crs=crs,
        grid=GridInfo(resolution_m=res, width=n, height=n, transform=grid.transform),
        habitat=lonlat(hab_u, hab_v),
        rover=lonlat(rover_u, rover_v),
        mission_epoch_utc=datetime.fromisoformat(str(cfg["mission_epoch_utc"])),
        default_preset=str(cfg["default_preset"]),
        layers=layers,
        terrain=TileInfo(path="tiles/terrain_rgb/{z}/{x}/{y}.png", minzoom=zooms.start,
                         maxzoom=zooms.stop - 1, format="png"),
        generated_at=datetime(2026, 11, 14, tzinfo=UTC),
        generator=GENERATOR,
    )
    manifest.size_bytes = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    (out / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")

    write_targets_seed(lonlat)
    return manifest


def write_targets_seed(lonlat: Callable[[float, float], LonLat]) -> None:
    seeds: list[tuple[str, str, tuple[float, float], str, str, float, int]] = [
        ("T1", "Front du delta", (250, 720), "Argiles et carbonates du delta, au-dessus de la falaise",
         "Imagerie rapprochée et prélèvement", 1200, 1),
        ("T2", "Bord des dunes", (-420, -150), "Granulométrie du sable actif",
         "Prélèvement de sable", 600, 2),
        ("T3", "Unité à olivine", (300, 150), "Roches ignées à olivine altérée du plancher",
         "Spectre et carottage", 1500, 1),
        ("T4", "Chaos de blocs", (-60, -470), "Origine des blocs éjectés",
         "Imagerie des blocs", 900, 3),
    ]
    fc: dict[str, Any] = {
        "type": "FeatureCollection",
        "crs_note": "IAU_2015:49900 (Mars 2000, planétocentrique, longitudes est)",
        "features": [
            {
                "type": "Feature",
                "id": tid,
                "geometry": {"type": "Point", "coordinates": list(lonlat(*xy))},
                "properties": {"name": name, "kind": "science", "objective": obj,
                               "measurement": meas, "work_time_s": work, "priority": prio},
            }
            for tid, name, xy, obj, meas, work, prio in seeds
        ],
    }
    path = repo_root() / "config" / "sites" / "fictif" / "targets-seed.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=repo_root() / "fixtures" / "sites" / "fictif")
    args = parser.parse_args()
    manifest = generate(args.out)
    size_mb = (manifest.size_bytes or 0) / 1e6
    print(f"Paquet écrit dans {args.out} ({len(manifest.layers)} couches, {size_mb:.1f} Mo)")


if __name__ == "__main__":
    main()
