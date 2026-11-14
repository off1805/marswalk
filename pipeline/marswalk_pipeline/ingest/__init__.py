"""Ingestion des données brutes de Jezero (D1).

Commande : ``marswalk ingest <site_id>``

Entrées : ``data/raw/<site_id>/`` avec ``sources.yaml`` (identifiant PDS, URL, date).
Sortie  : ``data/work/<site_id>/aligned/<layer_id>.tif`` (COG Float32 sur la grille
          d'analyse) + ``data/work/<site_id>/coreg_report.md``.

Règles :
- R1 : toutes les opérations en mètres dans ``analysis_crs`` (eqc martiennes).
- R2 : bbox et métadonnées en degrés (lon, lat) planétocentriques.
- R7 (ENF-07) : si le MNT HiRISE ne couvre pas l'emprise, repli sur CTX puis MOLA,
  marqué ``degraded`` dans le rapport.

Le recalage (coreg) est délégué à ``marswalk_pipeline.coreg``.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import rasterio.crs
import rasterio.enums
import rasterio.transform
import rasterio.warp
import yaml

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root

NODATA: float = -9999.0

# Résolutions cibles par couche (m/px)
_TARGET_RES: dict[str, float] = {
    "hirise_vis": 1.0,
    "ctx_vis": 6.0,
    "dem": 1.0,
    "dem_mola": 463.0,
    "thermal_inertia": 100.0,
    "crism_minerals": 18.0,
}

# Mapping nom-couche → clé dans sources.yaml
_SOURCE_KEYS: dict[str, list[str]] = {
    "hirise_vis": ["hirise_vis"],
    "ctx_vis": ["ctx_vis"],
    "dem": ["hirise_dem", "ctx_dem", "dem_mola"],  # ordre de repli
    "dem_mola": ["dem_mola"],
    "thermal_inertia": ["thermal_inertia"],
    "crism_minerals": ["crism_minerals"],
}


def _analysis_crs(cfg: dict[str, Any]) -> str:
    """Chaîne PROJ du système d'analyse depuis la config du site."""
    return str(cfg.get("analysis_crs", ""))


def _analysis_bbox_m(cfg: dict[str, Any]) -> tuple[float, float, float, float]:
    """Emprise de la grille d'analyse en mètres (xmin, ymin, xmax, ymax) depuis center+size."""
    center = cfg["center"]
    lon0, lat0 = float(center["lon"]), float(center["lat"])
    half = float(cfg.get("size_m", 5000)) / 2.0 + float(
        cfg.get("ingest", {}).get("bbox_buffer_m", 500)
    )
    # Convertit les mètres en degrés approximatifs (pour la bbox géographique initiale)
    r = 3_396_190.0
    k = math.cos(math.radians(lat0))
    dlon = math.degrees(half / (r * k))
    dlat = math.degrees(half / r)
    return (lon0 - dlon, lat0 - dlat, lon0 + dlon, lat0 + dlat)


def _make_analysis_transform(
    cfg: dict[str, Any],
) -> tuple[rasterio.transform.Affine, int, int]:
    """Transformation affine et dimensions (width, height) de la grille d'analyse."""
    res_m = float(cfg.get("resolution_m", 1.0))
    size_m = float(cfg.get("size_m", 5000))
    n = round(size_m / res_m)
    # Coin supérieur-gauche en mètres dans le système d'analyse (eqc centré sur le site)
    half = size_m / 2.0
    transform = rasterio.transform.Affine(res_m, 0.0, -half, 0.0, -res_m, half)
    return transform, n, n


def _analysis_crs_obj(crs_str: str) -> rasterio.crs.CRS:
    """Crée un objet CRS rasterio depuis une chaîne PROJ."""
    return rasterio.crs.CRS.from_proj4(crs_str)


def reproject_to_analysis(
    src_path: Path,
    dst_path: Path,
    crs_str: str,
    transform: rasterio.transform.Affine,
    width: int,
    height: int,
    resampling: rasterio.enums.Resampling = rasterio.enums.Resampling.bilinear,
    nodata: float = NODATA,
    dtype: str = "float32",
) -> None:
    """Reprojette un raster source vers la grille d'analyse et l'écrit en COG Float32.

    Paramètres
    ----------
    src_path : fichier source (GeoTIFF, IMG, etc.)
    dst_path : fichier de sortie (COG Float32)
    crs_str  : chaîne PROJ de l'analyse (R1)
    transform, width, height : grille cible
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_crs = _analysis_crs_obj(crs_str)

    with rasterio.open(src_path) as src:
        dst_data = np.full((height, width), nodata, dtype=np.float32)
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=dst_data,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=resampling,
            dst_nodata=nodata,
        )

    with rasterio.open(
        dst_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=dst_crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(dst_data, 1)


def _load_sources(site_id: str) -> dict[str, Any]:
    """Charge ``config/sites/<site_id>/sources.yaml``."""
    path = repo_root() / "config" / "sites" / site_id / "sources.yaml"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return dict(data.get("layers", {}))


def _raw_dir(site_id: str) -> Path:
    """Dossier des données brutes téléchargées : ``data/raw/<site_id>/``."""
    return repo_root() / "data" / "raw" / site_id


def _work_dir(site_id: str) -> Path:
    """Dossier de travail : ``data/work/<site_id>/``."""
    return repo_root() / "data" / "work" / site_id


class IngestResult:
    """Résultat de l'ingestion d'une couche."""

    def __init__(
        self,
        layer_id: str,
        out_path: Path,
        source_key: str,
        resolution_m: float,
        status: str,
        note: str = "",
    ) -> None:
        self.layer_id = layer_id
        self.out_path = out_path
        self.source_key = source_key
        self.resolution_m = resolution_m
        self.status = status  # "ok", "degraded", "missing"
        self.note = note


def ingest_layer(
    layer_id: str,
    cfg: dict[str, Any],
    sources: dict[str, Any],
    raw_dir: Path,
    work_aligned_dir: Path,
    crs_str: str,
    transform: rasterio.transform.Affine,
    width: int,
    height: int,
) -> IngestResult:
    """Ingeste une couche : trouve le fichier source, reprojette, écrit aligned/<layer_id>.tif.

    Applique le repli automatique (DEM : HiRISE → CTX → MOLA) et marque ``degraded``
    si un repli est utilisé.
    """
    source_keys = _SOURCE_KEYS.get(layer_id, [layer_id])
    out_path = work_aligned_dir / f"{layer_id}.tif"

    for key in source_keys:
        src_info = sources.get(key)
        if src_info is None:
            continue
        src_file = raw_dir / str(src_info.get("file", f"{key}.tif"))
        if not src_file.exists():
            # Essayer les extensions alternatives
            for ext in (".img", ".tif", ".tiff", ".fits"):
                alt = src_file.with_suffix(ext)
                if alt.exists():
                    src_file = alt
                    break
            else:
                continue

        # Reprojette
        try:
            reproject_to_analysis(src_file, out_path, crs_str, transform, width, height)
            status = "ok" if key == source_keys[0] else "degraded"
            note = "" if key == source_keys[0] else f"repli sur '{key}' (fichier préféré manquant)"
            return IngestResult(
                layer_id=layer_id,
                out_path=out_path,
                source_key=key,
                resolution_m=float(src_info.get("resolution_m", _TARGET_RES.get(layer_id, 1.0))),
                status=status,
                note=note,
            )
        except Exception:
            continue  # essayer la source suivante

    # Aucune source disponible
    return IngestResult(
        layer_id=layer_id,
        out_path=out_path,
        source_key="none",
        resolution_m=0.0,
        status="missing",
        note="Aucun fichier source disponible. Télécharger via D0.",
    )


def ingest(
    site_id: str,
    raw_dir: Path | None = None,
    work_dir: Path | None = None,
) -> list[IngestResult]:
    """Ingeste toutes les couches d'un site.

    Paramètres
    ----------
    site_id  : identifiant du site (ex. ``jezero``, ``fictif``).
    raw_dir  : dossier des bruts (défaut ``data/raw/<site_id>``).
    work_dir : dossier de travail (défaut ``data/work/<site_id>``).

    Retourne la liste des résultats par couche.
    La commande CLI ``marswalk ingest <site_id>`` appelle cette fonction puis
    ``marswalk_pipeline.coreg.coregister`` sur les résultats.
    """
    cfg = load_site_config(site_id)
    crs_str = _analysis_crs(cfg)
    transform, width, height = _make_analysis_transform(cfg)
    sources = _load_sources(site_id)

    if raw_dir is None:
        raw_dir = _raw_dir(site_id)
    if work_dir is None:
        work_dir = _work_dir(site_id)

    work_aligned_dir = work_dir / "aligned"
    work_aligned_dir.mkdir(parents=True, exist_ok=True)

    layers: list[str] = list(cfg.get("layers", list(_SOURCE_KEYS.keys())))
    # Filtrer aux couches ingérables (ayant une source définie)
    ingestable = [lid for lid in layers if lid in _SOURCE_KEYS]

    results: list[IngestResult] = []
    for layer_id in ingestable:
        result = ingest_layer(
            layer_id=layer_id,
            cfg=cfg,
            sources=sources,
            raw_dir=raw_dir,
            work_aligned_dir=work_aligned_dir,
            crs_str=crs_str,
            transform=transform,
            width=width,
            height=height,
        )
        results.append(result)
        print(f"[D1] {layer_id:25s} {result.status:9s} {result.note}")

    return results


def ingest_from_package(
    site_id: str,
    package_root: Path,
    work_dir: Path | None = None,
) -> list[IngestResult]:
    """Variante de ``ingest`` qui utilise les COG d'un paquet existant comme sources.

    Utile pour tester D1 sur le site fictif sans données réelles.
    Reprojette les COG du paquet vers la grille d'analyse du site_id cible.
    """
    from marswalk_core.site_package import open_package

    src_site = open_package(package_root)
    cfg = load_site_config(site_id)
    crs_str = _analysis_crs(cfg)
    transform, width, height = _make_analysis_transform(cfg)

    if work_dir is None:
        work_dir = _work_dir(site_id)
    work_aligned_dir = work_dir / "aligned"
    work_aligned_dir.mkdir(parents=True, exist_ok=True)

    results: list[IngestResult] = []
    for layer_id in _SOURCE_KEYS:
        # Trouver la couche source dans le paquet fictif
        src_layer_key = layer_id if layer_id != "dem" else "dem"
        if not src_site.has_layer(src_layer_key):
            results.append(
                IngestResult(
                    layer_id=layer_id,
                    out_path=work_aligned_dir / f"{layer_id}.tif",
                    source_key="none",
                    resolution_m=0.0,
                    status="missing",
                    note="Couche absente du paquet source",
                )
            )
            continue

        src_cog = package_root / str(src_site.layer(src_layer_key).cog)
        out_path = work_aligned_dir / f"{layer_id}.tif"

        try:
            reproject_to_analysis(src_cog, out_path, crs_str, transform, width, height)
            results.append(
                IngestResult(
                    layer_id=layer_id,
                    out_path=out_path,
                    source_key=src_layer_key,
                    resolution_m=float(src_site.layer(src_layer_key).resolution_m or 1.0),
                    status="ok",
                    note="source: paquet fictif (SYNTHETIC)",
                )
            )
        except Exception as exc:
            results.append(
                IngestResult(
                    layer_id=layer_id,
                    out_path=out_path,
                    source_key=src_layer_key,
                    resolution_m=0.0,
                    status="missing",
                    note=f"Erreur reprojection : {exc}",
                )
            )

    return results
