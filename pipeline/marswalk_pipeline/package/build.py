"""Assemblage d'un paquet de site (D3) : COG, tuiles, terrain-RGB, vecteurs et manifeste.

Entrées, dans ``data/work/<site_id>/`` (voir ``README.md`` de ce dossier) :

- ``aligned/<id>.tif`` (D1) et ``derived/<id>.tif`` (D2) sur la grille d'analyse ;
- ``display/<id>.tif`` (facultatif) en pleine résolution pour les tuiles (HiRISE à 0,25 m) ;
- ``layers/<id>.json`` : provenance et métadonnées de la couche ;
- ``vector/<id>.geojson`` et ``thumbs/`` (G1).

Le paquet est écrit dans un dossier temporaire, validé, puis mis en place : un paquet
invalide ou trop gros ne remplace jamais le précédent.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root
from marswalk_core.schemas import (
    KNOWN_LAYER_IDS,
    FeatureCollection,
    GridInfo,
    LayerInfo,
    LayerStatus,
    Legend,
    LonLat,
    SiteManifest,
    TileInfo,
)
from marswalk_core.site_package import parse_proj

from .catalog import CATALOG, VECTOR_LAYERS, Display
from .cog import GridSpec, write_cog
from .tiling import (
    Arr,
    Encoder,
    Eqc,
    RasterSampler,
    build_pyramid_auto,
    max_zoom_for,
    render_categorical,
    render_continuous,
    render_terrain_rgb,
    stretch,
)

GENERATOR = "marswalk_pipeline.package (D3)"
MAX_BYTES = 2 * 1024**3
DEFAULT_MINZOOM = 12


class PackageError(RuntimeError):
    """Entrées incomplètes ou incohérentes."""


class PackageTooLargeError(PackageError):
    """Le paquet dépasse la taille autorisée (ENF-10)."""


class PackageInvalidError(PackageError):
    """Le paquet ne passe pas ``tools/validate_site_package.py``."""


@dataclass
class LayerReport:
    id: str
    status: str
    maxzoom: int | None = None
    tiles: int = 0
    bytes: int = 0
    note: str | None = None


@dataclass
class PackageReport:
    site_id: str
    out: Path
    size_bytes: int = 0
    layers: list[LayerReport] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Paquet {self.site_id} : {self.out} ({self.size_bytes / 1e6:.1f} Mo)"]
        for lr in self.layers:
            zoom = f"z≤{lr.maxzoom}" if lr.maxzoom is not None else "-"
            extra = f" — {lr.note}" if lr.note else ""
            lines.append(
                f"  {lr.id:<16} {lr.status:<9} {zoom:<5} {lr.tiles:>6} tuiles "
                f"{lr.bytes / 1e6:8.1f} Mo{extra}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrées
# ---------------------------------------------------------------------------


def default_work_dir(site_id: str) -> Path:
    return repo_root() / "data" / "work" / site_id


def default_out_dir(site_id: str) -> Path:
    return repo_root() / "data" / "packages" / site_id


@dataclass
class LayerInput:
    id: str
    grid_path: Path | None
    display_path: Path | None
    vector_path: Path | None
    meta: dict[str, Any]

    @property
    def tile_source(self) -> Path | None:
        return self.display_path or self.grid_path


def _read_meta(work: Path, layer_id: str) -> dict[str, Any]:
    path = work / "layers" / f"{layer_id}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PackageError(f"{path} doit contenir un objet JSON")
    return data


def find_inputs(work: Path, layer_ids: list[str]) -> list[LayerInput]:
    inputs: list[LayerInput] = []
    for lid in layer_ids:
        grid = next(
            (p for d in ("aligned", "derived") if (p := work / d / f"{lid}.tif").is_file()), None
        )
        display = work / "display" / f"{lid}.tif"
        vector = work / "vector" / f"{lid}.geojson"
        inputs.append(
            LayerInput(
                id=lid,
                grid_path=grid,
                display_path=display if display.is_file() else None,
                vector_path=vector if vector.is_file() else None,
                meta=_read_meta(work, lid),
            )
        )
    return inputs


# ---------------------------------------------------------------------------
# Métadonnées d'une couche
# ---------------------------------------------------------------------------


def _display(meta: dict[str, Any], default: Display, legend: Legend | None) -> Display:
    over: dict[str, Any] = meta.get("display") or {}
    d = default
    if "resample" in over:
        if over["resample"] not in ("lanczos", "average", "nearest"):
            raise PackageError(f"rééchantillonnage inconnu : {over['resample']}")
        d = replace(d, resample=over["resample"])
    if "stretch" in over:
        s = over["stretch"]
        d = replace(d, stretch=None if s is None else (float(s[0]), float(s[1])))
    if "transparent" in over:
        d = replace(d, transparent=tuple(float(v) for v in over["transparent"]))
    if "quality" in over:
        d = replace(d, quality=int(over["quality"]))
    if legend is not None and legend.type == "categorical" and d.resample != "nearest":
        d = replace(d, resample="nearest")
    return d


def _layer_info(inp: LayerInput) -> tuple[LayerInfo, Display]:
    defaults = CATALOG[inp.id]
    meta = {k: v for k, v in inp.meta.items() if k != "display"}
    base: dict[str, Any] = {
        "id": inp.id,
        "title": defaults.title,
        "kind": defaults.kind,
        "unit": defaults.unit,
        "value_range": defaults.value_range,
        "legend": defaults.legend.model_dump() if defaults.legend else None,
        "source": {"instrument": "INCONNU", "mission": "inconnue", "note": "provenance absente"},
    }
    base.update(meta)
    for key in ("cog", "tiles", "vector"):
        base.pop(key, None)
    info = LayerInfo.model_validate(base)
    return info, _display(inp.meta, defaults.display, info.legend)


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------


def _percentiles(path: Path, lo: float, hi: float) -> tuple[float, float]:
    with rasterio.open(path) as ds:
        scale = max(1, math.ceil(max(ds.width, ds.height) / 2048))
        shape = (max(1, ds.height // scale), max(1, ds.width // scale))
        block = ds.read(1, out_shape=shape, masked=True).astype(np.float64)
        data = np.ma.filled(block, np.nan)
        if ds.nodata is not None:
            data[data == ds.nodata] = np.nan
    valid = data[np.isfinite(data)]
    if valid.size == 0:
        return 0.0, 255.0
    p = np.percentile(valid, [lo, hi])
    return float(p[0]), float(p[1])


def _renderer(info: LayerInfo, display: Display, source: Path) -> Callable[[Arr], Any]:
    legend = info.legend
    if legend is None:
        raise PackageError(f"couche {info.id} : légende manquante")
    if legend.type == "categorical":
        transparent = set(display.transparent)
        return lambda v: render_categorical(v, legend, transparent)
    if display.stretch is not None:
        lo, hi = _percentiles(source, *display.stretch)
        return lambda v: render_continuous(stretch(v, lo, hi), legend)
    return lambda v: render_continuous(v, legend)


def _tile_layer(
    info: LayerInfo,
    display: Display,
    source: Path,
    tiles_root: Path,
    eqc: Eqc,
    bbox: tuple[float, float, float, float],
    minzoom: int,
    lat_c: float,
    log: Callable[[str], None] = lambda _: None,
) -> tuple[TileInfo, int, int]:
    categorical = info.legend is not None and info.legend.type == "categorical"
    sampler = RasterSampler(source, eqc, nearest=categorical)
    try:
        maxzoom = max_zoom_for(sampler.resolution_m, lat_c, eqc.radius_m, minzoom)
        encoder = Encoder("webp", lossless=categorical, quality=display.quality)
        stats = build_pyramid_auto(
            tiles_root / info.id,
            sampler,
            _renderer(info, display, source),
            encoder,
            bbox,
            minzoom,
            maxzoom,
            display.resample,
            log=log,
        )
    finally:
        sampler.close()
    tiles = TileInfo(
        path=f"tiles/{info.id}/{{z}}/{{x}}/{{y}}.webp",
        minzoom=minzoom,
        maxzoom=maxzoom,
        format="webp",
    )
    return tiles, stats.tiles, stats.bytes


# ---------------------------------------------------------------------------
# Paquet
# ---------------------------------------------------------------------------


def _point(cfg_point: dict[str, Any] | None, eqc: Eqc, cx: float, cy: float) -> LonLat | None:
    """Point de ``site.yaml`` : ``{lon, lat}`` ou ``{x, y}`` en mètres depuis le centre."""
    if not cfg_point:
        return None
    if "lon" in cfg_point:
        return LonLat(float(cfg_point["lon"]), float(cfg_point["lat"]))
    lon, lat = eqc.inverse(cx + float(cfg_point["x"]), cy + float(cfg_point["y"]))
    return LonLat(round(lon, 7), round(lat, 7))


def _generated_at(value: datetime | None) -> datetime:
    if value is not None:
        return value
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=UTC)
    return datetime.now(UTC).replace(microsecond=0)


def _dir_size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _validator() -> Callable[[Path, int], list[str]]:
    path = repo_root() / "tools" / "validate_site_package.py"
    spec = importlib.util.spec_from_file_location("validate_site_package", path)
    if spec is None or spec.loader is None:
        raise PackageError(f"validateur introuvable : {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validate: Callable[[Path, int], list[str]] = module.validate
    return validate


def build_package(
    site_id: str,
    work: Path | None = None,
    out: Path | None = None,
    *,
    config: dict[str, Any] | None = None,
    max_bytes: int = MAX_BYTES,
    generated_at: datetime | None = None,
    validate: bool = True,
    log: Callable[[str], None] = lambda _msg: None,
) -> PackageReport:
    """Construit ``out`` (par défaut ``data/packages/<site_id>``) depuis ``work``."""
    work = work or default_work_dir(site_id)
    out = out or default_out_dir(site_id)
    cfg = config if config is not None else load_site_config(site_id)
    crs = str(cfg["analysis_crs"])
    params = parse_proj(crs)
    eqc = Eqc(float(params["lon_0"]), float(params["lat_ts"]), float(params.get("R", 3396190)))
    minzoom = int((cfg.get("tiles") or {}).get("minzoom", DEFAULT_MINZOOM))
    layer_ids = [str(x) for x in cfg.get("layers", KNOWN_LAYER_IDS)]
    unknown = sorted(set(layer_ids) - set(CATALOG))
    if unknown:
        raise PackageError(f"couches inconnues dans site.yaml : {', '.join(unknown)}")

    inputs = find_inputs(work, layer_ids)
    dem = next((i for i in inputs if i.id == "dem"), None)
    if dem is None or dem.grid_path is None:
        raise PackageError(f"MNT absent : {work}/aligned/dem.tif fixe la grille d'analyse")
    grid = GridSpec.from_raster(dem.grid_path, crs)
    a, _, c, _, e, f = grid.transform
    x_west, y_north = c, f
    x_east, y_south = c + a * grid.width, f + e * grid.height
    west, north = eqc.inverse(x_west, y_north)
    east, south = eqc.inverse(x_east, y_south)
    bbox = (round(west, 7), round(south, 7), round(east, 7), round(north, 7))
    cx, cy = (x_west + x_east) / 2, (y_north + y_south) / 2
    lat_c = eqc.inverse(cx, cy)[1]

    out.parent.mkdir(parents=True, exist_ok=True)
    staging_parent = out.parent / f".build-{site_id}"
    if staging_parent.exists():
        shutil.rmtree(staging_parent, ignore_errors=True)
        # Sur Windows, shutil.rmtree peut échouer silencieusement sur des arborescences
        # profondes ; on vérifie et on force si nécessaire.
        if staging_parent.exists():
            import subprocess

            subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(staging_parent)], check=False)
    staging = staging_parent / site_id
    staging.mkdir(parents=True)
    report = PackageReport(site_id, out)
    try:
        layers: list[LayerInfo] = []
        for inp in inputs:
            info, display = _layer_info(inp)
            lr = LayerReport(inp.id, info.status.value)
            if inp.id in VECTOR_LAYERS:
                if inp.vector_path is None:
                    info = info.model_copy(
                        update={"status": LayerStatus.missing, "status_note": "absente des entrées"}
                    )
                    lr.status, lr.note = "missing", "vector/ absent"
                else:
                    fc = FeatureCollection.model_validate_json(inp.vector_path.read_text("utf-8"))
                    dst = staging / "vector" / f"{inp.id}.geojson"
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_text(fc.model_dump_json(indent=1), encoding="utf-8")
                    info = info.model_copy(update={"vector": f"vector/{inp.id}.geojson"})
                layers.append(info)
                report.layers.append(lr)
                continue

            source = inp.tile_source
            cog_src = inp.grid_path or inp.display_path
            if source is None or cog_src is None:
                info = info.model_copy(
                    update={"status": LayerStatus.missing, "status_note": "absente des entrées"}
                )
                layers.append(info)
                report.layers.append(LayerReport(inp.id, "missing", note="raster absent"))
                continue
            categorical = info.legend is not None and info.legend.type == "categorical"
            log(f"{inp.id} : COG")
            write_cog(cog_src, staging / "cog" / f"{inp.id}.tif", grid, categorical)
            log(f"{inp.id} : tuiles depuis {source.name} ({source.parent.name}/)")
            tiles, count, size = _tile_layer(
                info,
                display,
                source,
                staging / "tiles",
                eqc,
                bbox,
                minzoom,
                lat_c,
                log=lambda m: log(f"  {m}"),
            )
            update: dict[str, Any] = {"cog": f"cog/{inp.id}.tif", "tiles": tiles}
            if info.resolution_m is None:
                with rasterio.open(source) as ds:
                    update["resolution_m"] = float(abs(ds.transform.a))
            info = info.model_copy(update=update)
            layers.append(info)
            lr.maxzoom, lr.tiles, lr.bytes = tiles.maxzoom, count, size
            report.layers.append(lr)

        log("terrain-RGB")
        dem_source = dem.tile_source
        assert dem_source is not None
        sampler = RasterSampler(dem_source, eqc, nearest=False)
        try:
            tz = max_zoom_for(sampler.resolution_m, lat_c, eqc.radius_m, minzoom)
            build_pyramid_auto(
                staging / "tiles" / "terrain_rgb",
                sampler,
                render_terrain_rgb,
                Encoder("png"),
                bbox,
                minzoom,
                tz,
                "average",
                log=lambda m: log(f"  {m}"),
            )
        finally:
            sampler.close()
        terrain = TileInfo(
            path="tiles/terrain_rgb/{z}/{x}/{y}.png", minzoom=minzoom, maxzoom=tz, format="png"
        )

        thumbs = work / "thumbs"
        if thumbs.is_dir():
            shutil.copytree(thumbs, staging / "thumbs")

        epoch = cfg.get("mission_epoch_utc")
        manifest = SiteManifest(
            site_id=site_id,
            name=str(cfg.get("name", site_id)),
            bbox=bbox,
            analysis_crs=crs,
            grid=GridInfo(
                resolution_m=grid.resolution_m,
                width=grid.width,
                height=grid.height,
                transform=grid.transform,
            ),
            habitat=_point(cfg.get("habitat"), eqc, cx, cy) or LonLat(*eqc.inverse(cx, cy)),
            rover=_point(cfg.get("rover"), eqc, cx, cy),
            mission_epoch_utc=(
                epoch
                if isinstance(epoch, datetime)
                else datetime.fromisoformat(str(epoch or "2026-11-01T00:00:00Z"))
            ),
            default_preset=str(cfg.get("default_preset", "safety")),
            layers=layers,
            terrain=terrain,
            generated_at=_generated_at(generated_at),
            generator=GENERATOR,
        )
        manifest.size_bytes = _dir_size(staging)
        (staging / "manifest.json").write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        report.size_bytes = _dir_size(staging)
        if report.size_bytes > max_bytes:
            raise PackageTooLargeError(
                f"paquet de {report.size_bytes / 1e6:.1f} Mo, au-delà de la limite de "
                f"{max_bytes / 1e6:.0f} Mo (ENF-10)\n{report.summary()}"
            )
        if validate:
            errors = _validator()(staging, max_bytes)
            if errors:
                raise PackageInvalidError("paquet invalide :\n  " + "\n  ".join(errors))
        if out.exists():
            shutil.rmtree(out)
        staging.rename(out)
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)
    return report
