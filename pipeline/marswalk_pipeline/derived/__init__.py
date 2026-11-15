"""Couches dérivées (D2) : slope, roughness, hillshade, obstacles, scarps, loose_soil, radio_coverage, illumination."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import rasterio.crs
import rasterio.transform

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root

from .hillshade import compute_hillshade
from .illumination import compute_illumination
from .loose_soil import compute_loose_soil
from .obstacles import compute_obstacles
from .radio_coverage import compute_radio_coverage
from .roughness import compute_roughness
from .scarps import compute_scarps
from .slope import compute_slope

__all__ = [
    "compute_slope",
    "compute_roughness",
    "compute_hillshade",
    "compute_obstacles",
    "compute_scarps",
    "compute_loose_soil",
    "compute_radio_coverage",
    "compute_illumination",
    "run_derive",
]

NODATA: float = -9999.0

# Paramètres par défaut (repris de Jezero)
_DEFAULTS: dict[str, Any] = {
    "roughness_window_m": 10.0,
    "obstacle_roughness_threshold_m": 0.4,
    "obstacle_buffer_m": 2.0,
    "scarp_threshold_deg": 30.0,
    "scarp_buffer_m": 10.0,
    "antenna_height_m": 3.0,
    "sun_azimuth_deg": 90.0,
    "sun_altitude_deg": 20.0,
    "ti_dune_threshold": 170.0,
    "ti_loose_threshold": 200.0,
    "ti_mixed_threshold": 270.0,
    "texture_window_px": 5,
    "texture_dune_threshold": 5.0,
}


def _read_dem(path: Path) -> tuple[np.ndarray, rasterio.transform.Affine, rasterio.crs.CRS, float]:
    """Lit dem.tif et retourne (data, transform, crs, resolution_m)."""
    with rasterio.open(path) as ds:
        data = ds.read(1).astype(np.float32)
        transform = ds.transform
        crs = ds.crs
        resolution_m = float(abs(transform.a))
    return data, transform, crs, resolution_m


def _read_layer(path: Path, nodata: float = NODATA) -> np.ndarray:
    """Lit un raster mono-bande et retourne un float32."""
    if not path.exists():
        return np.array([])
    with rasterio.open(path) as ds:
        data = ds.read(1).astype(np.float32)
        nd = ds.nodata
        if nd is not None and not np.isclose(nd, nodata):
            mask = np.isclose(data, float(nd), rtol=0, atol=1.0)
            data[mask] = nodata
    return data


def _write_derived(
    data: np.ndarray,
    path: Path,
    like_path: Path,
    nodata: float = NODATA,
) -> None:
    """Écrit data comme raster dérivé avec les mêmes métadonnées que like_path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(like_path) as ref:
        transform = ref.transform
        crs = ref.crs
        height, width = data.shape

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(data.astype(np.float32), 1)


def _find_aligned_dir(site_id: str, aligned_dir: Path | None) -> Path:
    """Résout le répertoire aligned/ pour un site_id."""
    if aligned_dir is not None:
        return aligned_dir

    # Chercher d'abord dans fixtures/sites/<site_id>/cog/
    root = repo_root()
    fixture_cog = root / "fixtures" / "sites" / site_id / "cog"
    if (fixture_cog / "dem.tif").exists():
        return fixture_cog

    # Sinon data/work/<site_id>/aligned/
    return root / "data" / "work" / site_id / "aligned"


def _get_habitat_px(
    cfg: dict[str, Any],
    dem_transform: rasterio.transform.Affine,
    resolution_m: float,
) -> tuple[int, int]:
    """Calcule la position en pixels de l'habitat depuis la config.

    La config site.yaml peut exprimer l'habitat de deux façons :
    - ``{x: float, y: float}`` : coordonnées en mètres dans le CRS d'analyse (EQC absolu).
      Attention : pour le site Jezero avant I1, x=0 y=0 est un placeholder non calibré
      (le centre de la grille est à x≈0, y≈y_center ≈ 1 093 298 m).
    - ``[lon, lat]`` : longitude/latitude en degrés Mars, converties via pyproj.

    Si la position calculée est hors de la grille (placeholder non calibré), on revient
    au centre géométrique de la grille (comportement sûr avant la calibration I1).
    """
    hab = cfg.get("habitat", {})
    rows = int(round((dem_transform.f - (dem_transform.f + dem_transform.e * 5000)) / resolution_m))
    # Centre de grille par défaut : milieu de width × height
    # On n'a pas la taille ici, donc on utilise un fallback symbolique (0,0) ; sera clampé
    default_col = 0
    default_row = 0

    if isinstance(hab, dict) and "x" in hab:
        hab_x_m = float(hab.get("x", 0.0))
        hab_y_m = float(hab.get("y", 0.0))
        # Coordonnées absolues dans le CRS d'analyse (EQC en mètres).
        # col = (x_abs - x_origin) / res
        # row = (y_origin - y_abs) / res   (y décroît vers le bas)
        col = int(round((hab_x_m - dem_transform.c) / resolution_m))
        row = int(round((dem_transform.f - hab_y_m) / resolution_m))

    elif isinstance(hab, list) and len(hab) == 2:
        # Format [lon, lat] en degrés
        import math
        import rasterio.crs
        crs_str = cfg.get("analysis_crs", "")
        try:
            # Conversion lon/lat → x/y en mètres dans le CRS d'analyse
            # On utilise la formule EQC directement (évite une dépendance pyproj)
            # EQC: x = (lon - lon_0) * cos(lat_ts) * R
            #      y = lat * pi/180 * R
            lon_deg = float(hab[0])
            lat_deg = float(hab[1])
            R = 3_396_190.0
            lat_ts = 0.0
            lon_0 = 0.0
            for token in crs_str.split():
                if token.startswith("+lat_ts="):
                    lat_ts = float(token[8:])
                elif token.startswith("+lon_0="):
                    lon_0 = float(token[7:])
                elif token.startswith("+R="):
                    R = float(token[3:])
            x_m = (lon_deg - lon_0) * math.pi / 180.0 * math.cos(math.radians(lat_ts)) * R
            y_m = lat_deg * math.pi / 180.0 * R
            col = int(round((x_m - dem_transform.c) / resolution_m))
            row = int(round((dem_transform.f - y_m) / resolution_m))
        except Exception:
            col = default_col
            row = default_row
    else:
        col = default_col
        row = default_row

    return row, col


def _clamp_to_grid(row: int, col: int, dem: np.ndarray) -> tuple[int, int]:
    """Clamp la position habitat dans les limites de la grille.

    Si la position est hors-grille (placeholder non calibré), retourne le centre.
    """
    h, w = dem.shape
    if 0 <= row < h and 0 <= col < w:
        return row, col
    # Position hors grille : fallback sur le centre de la grille
    return h // 2, w // 2


def run_derive(
    site_id: str,
    aligned_dir: Path | None = None,
    derived_dir: Path | None = None,
) -> dict[str, str]:
    """Calcule toutes les couches dérivées pour site_id.

    Parameters
    ----------
    site_id:
        Identifiant du site (ex: "fictif", "jezero").
    aligned_dir:
        Répertoire des rasters sources alignés. Si None, cherche automatiquement.
    derived_dir:
        Répertoire de sortie des couches dérivées. Si None, utilise
        data/work/<site_id>/derived/.

    Returns
    -------
    dict[str, str]
        {layer_id: status} avec status "ok" ou message d'erreur.
    """
    root = repo_root()
    status: dict[str, str] = {}

    # Charger la config du site (peut ne pas avoir de section derive)
    try:
        cfg = load_site_config(site_id)
    except Exception:
        # Site fictif sans config derive → utiliser les defaults
        cfg = {}

    derive_cfg: dict[str, Any] = dict(_DEFAULTS)
    derive_cfg.update(cfg.get("derive", {}))

    # Résoudre les répertoires
    src_dir = _find_aligned_dir(site_id, aligned_dir)

    if derived_dir is None:
        derived_dir = root / "data" / "work" / site_id / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    # Lecture DEM
    dem_path = src_dir / "dem.tif"
    if not dem_path.exists():
        return {"error": f"DEM introuvable : {dem_path}"}

    dem, dem_transform, dem_crs, resolution_m = _read_dem(dem_path)

    # Résolution (depuis config si disponible, sinon depuis le raster)
    if cfg.get("resolution_m"):
        resolution_m = float(cfg["resolution_m"])

    # --- 1. Slope ---
    try:
        slope = compute_slope(dem, resolution_m, nodata=NODATA)
        _write_derived(slope, derived_dir / "slope.tif", dem_path)
        status["slope"] = "ok"
    except Exception as exc:
        status["slope"] = f"error: {exc}"
        slope = np.full_like(dem, NODATA)

    # --- 2. Roughness ---
    try:
        roughness = compute_roughness(
            dem,
            window_m=derive_cfg["roughness_window_m"],
            resolution_m=resolution_m,
            nodata=NODATA,
        )
        _write_derived(roughness, derived_dir / "roughness.tif", dem_path)
        status["roughness"] = "ok"
    except Exception as exc:
        status["roughness"] = f"error: {exc}"
        roughness = np.full_like(dem, NODATA)

    # --- 3. Hillshade ---
    try:
        hillshade = compute_hillshade(
            dem,
            resolution_m=resolution_m,
            sun_azimuth_deg=derive_cfg["sun_azimuth_deg"],
            sun_altitude_deg=derive_cfg["sun_altitude_deg"],
            nodata=NODATA,
        )
        _write_derived(hillshade, derived_dir / "hillshade.tif", dem_path)
        status["hillshade"] = "ok"
    except Exception as exc:
        status["hillshade"] = f"error: {exc}"

    # --- 4. Obstacles ---
    try:
        obstacles = compute_obstacles(
            roughness,
            threshold_m=derive_cfg["obstacle_roughness_threshold_m"],
            buffer_m=derive_cfg["obstacle_buffer_m"],
            resolution_m=resolution_m,
            nodata=NODATA,
        )
        _write_derived(obstacles, derived_dir / "obstacles.tif", dem_path)
        status["obstacles"] = "ok"
    except Exception as exc:
        status["obstacles"] = f"error: {exc}"

    # --- 5. Scarps ---
    try:
        scarps = compute_scarps(
            slope,
            threshold_deg=derive_cfg["scarp_threshold_deg"],
            buffer_m=derive_cfg["scarp_buffer_m"],
            resolution_m=resolution_m,
            nodata=NODATA,
        )
        _write_derived(scarps, derived_dir / "scarps.tif", dem_path)
        status["scarps"] = "ok"
    except Exception as exc:
        status["scarps"] = f"error: {exc}"

    # --- 6. Loose soil ---
    try:
        ti_path = src_dir / "thermal_inertia.tif"
        hi_path = src_dir / "hirise_vis.tif"
        if ti_path.exists() and hi_path.exists():
            thermal_inertia = _read_layer(ti_path)
            hirise_vis = _read_layer(hi_path)
            # Redimensionner thermal_inertia si nécessaire pour qu'elle corresponde au DEM
            if thermal_inertia.shape != dem.shape:
                thermal_inertia = _resample_to_dem(thermal_inertia, ti_path, dem_path)
            if hirise_vis.shape != dem.shape:
                hirise_vis = _resample_to_dem(hirise_vis, hi_path, dem_path)
            loose = compute_loose_soil(
                thermal_inertia,
                hirise_vis,
                nodata=NODATA,
                ti_dune=derive_cfg["ti_dune_threshold"],
                ti_loose=derive_cfg["ti_loose_threshold"],
                ti_mixed=derive_cfg["ti_mixed_threshold"],
                texture_window_px=int(derive_cfg["texture_window_px"]),
                texture_dune_threshold=derive_cfg["texture_dune_threshold"],
            )
            _write_derived(loose, derived_dir / "loose_soil.tif", dem_path)
            status["loose_soil"] = "ok"
        else:
            status["loose_soil"] = "skipped: thermal_inertia or hirise_vis missing"
    except Exception as exc:
        status["loose_soil"] = f"error: {exc}"

    # --- 7. Radio coverage ---
    try:
        hab_px = _get_habitat_px(cfg, dem_transform, resolution_m)
        hab_r, hab_c = _clamp_to_grid(hab_px[0], hab_px[1], dem)
        radio = compute_radio_coverage(
            dem,
            habitat_px=(hab_r, hab_c),
            antenna_height_m=derive_cfg["antenna_height_m"],
            resolution_m=resolution_m,
            nodata=NODATA,
        )
        _write_derived(radio, derived_dir / "radio_coverage.tif", dem_path)
        status["radio_coverage"] = "ok"
    except Exception as exc:
        status["radio_coverage"] = f"error: {exc}"

    # --- 8. Illumination ---
    try:
        illum = compute_illumination(
            dem,
            resolution_m=resolution_m,
            sun_azimuth_deg=derive_cfg["sun_azimuth_deg"],
            sun_altitude_deg=derive_cfg["sun_altitude_deg"],
            nodata=NODATA,
        )
        _write_derived(illum, derived_dir / "illumination.tif", dem_path)
        status["illumination"] = "ok"
    except Exception as exc:
        status["illumination"] = f"error: {exc}"

    return status


def _resample_to_dem(
    data: np.ndarray,
    src_path: Path,
    dem_path: Path,
) -> np.ndarray:
    """Reprojette un raster vers la grille du DEM si les tailles diffèrent."""
    import rasterio.warp
    import rasterio.enums

    with rasterio.open(dem_path) as dem_ds:
        dem_transform = dem_ds.transform
        dem_crs = dem_ds.crs
        dem_width = dem_ds.width
        dem_height = dem_ds.height

    with rasterio.open(src_path) as src:
        dst = np.full((dem_height, dem_width), NODATA, dtype=np.float32)
        rasterio.warp.reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dem_transform,
            dst_crs=dem_crs,
            resampling=rasterio.enums.Resampling.bilinear,
            dst_nodata=NODATA,
        )
    return dst
