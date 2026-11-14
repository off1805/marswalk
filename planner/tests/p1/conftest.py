"""Fixtures partagées pour les tests P1.

Les tests P1 s'appuient sur des sites synthétiques construits en mémoire
(``make_site``) ainsi que sur le site fictif standard (``fictif_site``).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from affine import Affine

from marswalk_core.schemas import (
    LayerInfo,
    LayerKind,
    LayerSource,
    LayerStatus,
    SafetySettings,
    SiteManifest,
)
from marswalk_core.site_package import Site, clear_cache, load_site

# ---------------------------------------------------------------------------
# Helpers pour construire un site synthétique
# ---------------------------------------------------------------------------

NODATA = -9999.0
_DEFAULT_SOURCE = LayerSource(instrument="SYNTHETIC", mission="test", product_id="TEST")

RESOLUTION = 2.0  # mètres
GRID_SIZE = 100   # 100 × 100 = 200 m × 200 m (petit pour rapidité)


def _write_cog(root: Path, name: str, data: np.ndarray) -> None:
    """Écrit un GeoTIFF simple (un seul band float32) dans ``root/cog/``."""
    cog_dir = root / "cog"
    cog_dir.mkdir(exist_ok=True)
    transform = Affine(RESOLUTION, 0.0, -GRID_SIZE * RESOLUTION / 2,
                       0.0, -RESOLUTION, GRID_SIZE * RESOLUTION / 2)
    path = cog_dir / f"{name}.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=GRID_SIZE,
        width=GRID_SIZE,
        count=1,
        dtype=np.float32,
        nodata=NODATA,
        transform=transform,
        crs=None,
    ) as ds:
        ds.write(data.astype(np.float32), 1)


def _layer_info(
    layer_id: str,
    kind: LayerKind = LayerKind.derived,
    status: LayerStatus = LayerStatus.ok,
) -> LayerInfo:
    return LayerInfo(
        id=layer_id,
        title=layer_id,
        kind=kind,
        source=_DEFAULT_SOURCE,
        cog=f"cog/{layer_id}.tif",
        status=status,
    )


def make_site(
    layers: dict[str, np.ndarray],
    missing: list[str] | None = None,
    degraded: list[str] | None = None,
    resolution: float = RESOLUTION,
    grid_size: int = GRID_SIZE,
) -> tuple[Site, Path]:
    """Construit un site en mémoire dans un répertoire temporaire.

    Parameters
    ----------
    layers:
        Dict ``layer_id → ndarray float32``. Shape doit être (grid_size, grid_size).
    missing:
        Couches déclarées dans le manifeste avec status='missing' (sans fichier COG).
    degraded:
        Couches avec status='degraded'.
    """
    missing = missing or []
    degraded = degraded or []

    tmpdir = Path(tempfile.mkdtemp())

    # Écrire les fichiers COG
    for lid, data in layers.items():
        if lid not in missing:
            _write_cog(tmpdir, lid, data)

    # Construire le manifeste
    transform_tup = (
        resolution, 0.0, -grid_size * resolution / 2.0,
        0.0, -resolution, grid_size * resolution / 2.0,
    )

    layer_infos: list[dict[str, Any]] = []
    for lid in list(layers.keys()) + missing:
        st = "missing" if lid in missing else ("degraded" if lid in degraded else "ok")
        cog = None if lid in missing else f"cog/{lid}.tif"
        layer_infos.append({
            "id": lid,
            "title": lid,
            "kind": "derived",
            "source": {"instrument": "SYNTHETIC", "mission": "test", "product_id": "T"},
            "cog": cog,
            "status": st,
        })

    manifest_data = {
        "schema_version": "1.0",
        "site_id": "test_p1",
        "name": "Test P1",
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

    (tmpdir / "manifest.json").write_text(
        json.dumps(manifest_data), encoding="utf-8"
    )

    manifest = SiteManifest.model_validate(manifest_data)
    return Site(tmpdir, manifest), tmpdir


# ---------------------------------------------------------------------------
# Couches synthétiques standard
# ---------------------------------------------------------------------------

def make_layers(
    grid_size: int = GRID_SIZE,
    slope_val: float = 0.0,
    has_obstacle: bool = False,
    has_dune: bool = False,
    has_scarp: bool = False,
    radio: float = 1.0,
    illumination: float = 0.5,
) -> dict[str, np.ndarray]:
    """Couches uniformes pour tests unitaires.

    slope_val et les flags s'appliquent à la première moitié de la grille
    (lignes 0..grid_size//2−1). La seconde moitié est à 0° / libre.
    """
    half = grid_size // 2
    slope = np.full((grid_size, grid_size), slope_val, dtype=np.float32)
    obstacles = np.zeros((grid_size, grid_size), dtype=np.float32)
    scarps = np.zeros((grid_size, grid_size), dtype=np.float32)
    loose_soil = np.zeros((grid_size, grid_size), dtype=np.float32)  # roche

    if has_obstacle:
        obstacles[:half, :half] = 1.0
    if has_dune:
        loose_soil[:half, :half] = 3.0  # classe dune
    if has_scarp:
        scarps[half, :] = 1.0  # ligne de falaise

    radio_cov = np.full((grid_size, grid_size), radio, dtype=np.float32)
    illum = np.full((grid_size, grid_size), illumination, dtype=np.float32)
    roughness = np.full((grid_size, grid_size), 0.1, dtype=np.float32)
    crism = np.zeros((grid_size, grid_size), dtype=np.float32)
    thermal = np.full((grid_size, grid_size), 300.0, dtype=np.float32)

    return {
        "slope": slope,
        "obstacles": obstacles,
        "scarps": scarps,
        "loose_soil": loose_soil,
        "thermal_inertia": thermal,
        "radio_coverage": radio_cov,
        "illumination": illum,
        "roughness": roughness,
        "crism_minerals": crism,
    }


# ---------------------------------------------------------------------------
# Fixtures pytest
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def fictif_site() -> Site:
    """Site fictif standard (2 km × 2 km, 1000 × 1000 cases à 2 m)."""
    clear_cache()
    return load_site("fictif")


@pytest.fixture(scope="session")
def standard_settings() -> SafetySettings:
    """Préréglage 'standard' de config/safety.yaml."""
    from marswalk_core.config import load_safety_settings
    return load_safety_settings("standard")


@pytest.fixture(scope="session")
def prudent_settings() -> SafetySettings:
    """Préréglage 'prudent' de config/safety.yaml."""
    from marswalk_core.config import load_safety_settings
    return load_safety_settings("prudent")
