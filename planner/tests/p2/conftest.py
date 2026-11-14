"""Fixtures partagées pour les tests P2.

Réutilise les helpers de P1 (make_site, make_layers) et en ajoute de nouveaux
adaptés à la navigation : grilles avec obstacles, couloirs, falaises.
"""

from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from affine import Affine

from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import (
    LayerSource,
    LonLat,
    SafetySettings,
    SiteManifest,
    Target,
    TargetKind,
)
from marswalk_core.site_package import Site, clear_cache, load_site

NODATA = -9999.0
_DEFAULT_SOURCE = LayerSource(instrument="SYNTHETIC", mission="test", product_id="TEST")

RESOLUTION = 2.0
GRID_SIZE = 100  # 100 × 100 = 200 m × 200 m

# Rayon Mars pour conversion mètres ↔ degrés
_MARS_R = 3_396_190.0

# Étendue en degrés d'une grille GRID_SIZE × GRID_SIZE à RESOLUTION m
# Pour +proj=eqc +lat_ts=0 +lon_0=0 : x = R * radians(lon) * cos(0) = R * radians(lon)
_HALF_EXTENT_DEG = (GRID_SIZE * RESOLUTION / 2.0) * 180.0 / (_MARS_R * math.pi)


def meters_to_deg(meters: float) -> float:
    """Conversion approximative mètres → degrés (lon ou lat) pour le CRS test."""
    return meters * 180.0 / (_MARS_R * math.pi)


def grid_lonlat(
    row_frac: float, col_frac: float, gs: int = GRID_SIZE, res: float = RESOLUTION
) -> LonLat:
    """LonLat correspondant à (row_frac, col_frac) dans [0,1]×[0,1] de la grille.

    row_frac=0 → haut de la grille (lat positive), row_frac=1 → bas.
    col_frac=0 → gauche (lon négative), col_frac=1 → droite.
    """
    half = gs * res / 2.0
    x = -half + col_frac * gs * res
    y = half - row_frac * gs * res
    lon = x * 180.0 / (_MARS_R * math.pi)
    lat = y * 180.0 / (_MARS_R * math.pi)
    return LonLat(lon, lat)


def _write_cog(root: Path, name: str, data: np.ndarray, resolution: float = RESOLUTION) -> None:
    cog_dir = root / "cog"
    cog_dir.mkdir(exist_ok=True)
    h, w = data.shape
    transform = Affine(
        resolution, 0.0, -w * resolution / 2, 0.0, -resolution, h * resolution / 2
    )
    path = cog_dir / f"{name}.tif"
    with rasterio.open(
        path, "w", driver="GTiff",
        height=h, width=w, count=1,
        dtype=np.float32, nodata=NODATA, transform=transform, crs=None,
    ) as ds:
        ds.write(data.astype(np.float32), 1)


def make_site(
    layers: dict[str, np.ndarray],
    missing: list[str] | None = None,
    degraded: list[str] | None = None,
    resolution: float = RESOLUTION,
    grid_size: int = GRID_SIZE,
    site_id: str = "test_p2",
) -> tuple[Site, Path]:
    """Construit un site en mémoire dans un répertoire temporaire."""
    missing = missing or []
    degraded = degraded or []
    tmpdir = Path(tempfile.mkdtemp())

    for lid, data in layers.items():
        if lid not in missing:
            _write_cog(tmpdir, lid, data, resolution)

    transform_tup = (
        resolution, 0.0, -grid_size * resolution / 2.0,
        0.0, -resolution, grid_size * resolution / 2.0,
    )

    layer_infos: list[dict[str, Any]] = []
    for lid in list(layers.keys()) + missing:
        st = "missing" if lid in missing else ("degraded" if lid in degraded else "ok")
        cog = None if lid in missing else f"cog/{lid}.tif"
        layer_infos.append({
            "id": lid, "title": lid, "kind": "derived",
            "source": {"instrument": "SYNTHETIC", "mission": "test", "product_id": "T"},
            "cog": cog, "status": st,
        })

    manifest_data = {
        "schema_version": "1.0",
        "site_id": site_id,
        "name": f"Test {site_id}",
        "bbox": [-0.1, -0.1, 0.1, 0.1],
        "analysis_crs": "+proj=eqc +lat_ts=0 +lon_0=0 +R=3396190 +units=m +no_defs",
        "grid": {
            "resolution_m": resolution,
            "width": grid_size,
            "height": grid_size,
            "transform": list(transform_tup),
        },
        "habitat": [0.0, 0.0],
        "mission_epoch_utc": "2026-11-01T00:00:00Z",
        "layers": layer_infos,
    }

    (tmpdir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    manifest = SiteManifest.model_validate(manifest_data)
    return Site(tmpdir, manifest), tmpdir


def flat_layers(grid_size: int = GRID_SIZE) -> dict[str, np.ndarray]:
    """Couches pour une grille plate sans obstacle."""
    return {
        "slope": np.zeros((grid_size, grid_size), dtype=np.float32),
        "obstacles": np.zeros((grid_size, grid_size), dtype=np.float32),
        "scarps": np.zeros((grid_size, grid_size), dtype=np.float32),
        "loose_soil": np.zeros((grid_size, grid_size), dtype=np.float32),
        "thermal_inertia": np.full((grid_size, grid_size), 300.0, dtype=np.float32),
        "radio_coverage": np.ones((grid_size, grid_size), dtype=np.float32),
        "illumination": np.ones((grid_size, grid_size), dtype=np.float32),
        "roughness": np.full((grid_size, grid_size), 0.1, dtype=np.float32),
        "crism_minerals": np.zeros((grid_size, grid_size), dtype=np.float32),
    }


def layers_with_obstacle(
    obs_row: int, obs_col: int, obs_size: int = 10, grid_size: int = GRID_SIZE
) -> dict[str, np.ndarray]:
    """Grille plate avec un obstacle rectangulaire centré."""
    layers = flat_layers(grid_size)
    r0 = max(0, obs_row - obs_size // 2)
    r1 = min(grid_size, obs_row + obs_size // 2)
    c0 = max(0, obs_col - obs_size // 2)
    c1 = min(grid_size, obs_col + obs_size // 2)
    layers["obstacles"][r0:r1, c0:c1] = 1.0
    return layers


def layers_with_wall(
    wall_row: int, gap_col: int, gap_size: int = 5, grid_size: int = GRID_SIZE
) -> dict[str, np.ndarray]:
    """Mur horizontal avec un couloir étroit."""
    layers = flat_layers(grid_size)
    layers["obstacles"][wall_row, :] = 1.0
    layers["obstacles"][wall_row, gap_col:gap_col + gap_size] = 0.0
    return layers


def make_target(
    idx: int, lon: float, lat: float, priority: int = 2, work_time_s: float = 300.0
) -> Target:
    """Crée une cible de test."""
    return Target(
        id=f"t{idx}",
        site_id="test_p2",
        name=f"Cible {idx}",
        kind=TargetKind.science,
        position=LonLat(lon, lat),
        priority=priority,
        work_time_s=work_time_s,
        created_at=datetime(2026, 11, 1),
        updated_at=datetime(2026, 11, 1),
    )


def make_target_at(idx: int, row_frac: float, col_frac: float, gs: int = GRID_SIZE, **kw) -> Target:
    """Crée une cible à une position exprimée en fraction de grille [0,1]."""
    pos = grid_lonlat(row_frac, col_frac, gs)
    return make_target(idx, pos.lon, pos.lat, **kw)


@pytest.fixture(scope="session")
def fictif_site() -> Site:
    clear_cache()
    return load_site("fictif")


@pytest.fixture(scope="session")
def standard_settings() -> SafetySettings:
    from marswalk_core.config import load_safety_settings
    return load_safety_settings("standard")


@pytest.fixture
def flat_site() -> tuple[Site, Path]:
    return make_site(flat_layers())


@pytest.fixture
def obstacle_site() -> tuple[Site, Path]:
    return make_site(layers_with_obstacle(obs_row=50, obs_col=50, obs_size=20))


@pytest.fixture
def wall_site() -> tuple[Site, Path]:
    return make_site(layers_with_wall(wall_row=50, gap_col=45, gap_size=10))


@pytest.fixture
def default_options() -> RouteOptions:
    return RouteOptions(window_margin_m=200.0, optimize_order=True)
