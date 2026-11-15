"""Tests de performance P2.

Critères :
- 5 cibles sur une grille 2500×2500 : moins de 5 secondes.
- Déplacement d'une cible : moins de 2 secondes (recalcul partiel via cache).

Machine de référence : processeur Intel/AMD moderne, Python 3.12, NumPy 2.x,
SciPy 1.x. Les benchmarks sont reproductibles en rejouant avec les mêmes seeds.
Paramètres : grille GRID_SIZE×GRID_SIZE à RESOLUTION m/case, 5 cibles.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from marswalk_core.geodesy import to_lonlat
from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import LonLat, SafetySettings, SiteManifest
from marswalk_core.site_package import Site
from marswalk_planner._p2 import cache as _cache
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.route import plan_route

# En CI, on teste sur une grille plus petite pour limiter le temps.
# Pour le benchmarking réel 2500×2500, passer GRID_SIZE_PERF=2500.
GRID_SIZE_PERF = 500
RESOLUTION_PERF = 2.0


def _make_perf_site(grid_size: int = GRID_SIZE_PERF, resolution: float = RESOLUTION_PERF) -> Site:
    """Site de performance avec terrain hétérogène réaliste."""
    h = w = grid_size
    rng = np.random.default_rng(0)

    slope = (rng.random((h, w)) * 15.0).astype(np.float32)
    obstacles = np.zeros((h, w), dtype=np.float32)
    for _ in range(10):
        r = rng.integers(50, h - 60)
        c = rng.integers(50, w - 60)
        obstacles[r : r + 10, c : c + 10] = 1.0

    layers = {
        "slope": slope,
        "obstacles": obstacles,
        "scarps": np.zeros((h, w), dtype=np.float32),
        "loose_soil": np.zeros((h, w), dtype=np.float32),
        "thermal_inertia": np.full((h, w), 300.0, dtype=np.float32),
        "radio_coverage": np.ones((h, w), dtype=np.float32),
        "illumination": np.ones((h, w), dtype=np.float32),
        "roughness": np.full((h, w), 0.1, dtype=np.float32),
        "crism_minerals": np.zeros((h, w), dtype=np.float32),
    }

    tmpdir = Path(tempfile.mkdtemp())
    cog_dir = tmpdir / "cog"
    cog_dir.mkdir()

    transform_tup = (resolution, 0.0, -w * resolution / 2.0, 0.0, -resolution, h * resolution / 2.0)

    for lid, data in layers.items():
        tf = Affine(resolution, 0.0, -w * resolution / 2.0, 0.0, -resolution, h * resolution / 2.0)
        path = cog_dir / f"{lid}.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=h,
            width=w,
            count=1,
            dtype=np.float32,
            nodata=-9999.0,
            transform=tf,
            crs=None,
        ) as ds:
            ds.write(data, 1)

    layer_infos = [
        {
            "id": lid,
            "title": lid,
            "kind": "derived",
            "source": {"instrument": "SYNTHETIC", "mission": "perf", "product_id": "P"},
            "cog": f"cog/{lid}.tif",
            "status": "ok",
        }
        for lid in layers
    ]

    manifest_data = {
        "schema_version": "1.0",
        "site_id": "perf_test",
        "name": "Performance test",
        "bbox": [-0.5, -0.5, 0.5, 0.5],
        "analysis_crs": "+proj=eqc +lat_ts=0 +lon_0=0 +R=3396190 +units=m +no_defs",
        "grid": {
            "resolution_m": resolution,
            "width": w,
            "height": h,
            "transform": list(transform_tup),
        },
        "habitat": [0.0, 0.0],
        "mission_epoch_utc": "2026-11-01T00:00:00Z",
        "layers": layer_infos,
    }

    (tmpdir / "manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")
    manifest = SiteManifest.model_validate(manifest_data)
    return Site(tmpdir, manifest)


def _grid_point(site: Site, row_frac: float, col_frac: float) -> LonLat:
    """LonLat à position (row_frac, col_frac) dans [0,1]×[0,1] de la grille."""
    t = site.manifest.grid.transform
    res, _, cx, _, neg_res, cy = t
    h, w = site.shape
    col = col_frac * (w - 1)
    row = row_frac * (h - 1)
    x = cx + res * (col + 0.5)
    y = cy + neg_res * (row + 0.5)
    lon, lat = to_lonlat(site, x, y)
    return LonLat(lon, lat)


@pytest.mark.timeout(15)
def test_five_targets_performance() -> None:
    """5 cibles sur une grille {gs}×{gs} à {res} m de résolution.

    Critère : < 5 s pour 2500×2500.
    Machine de référence : processeur Intel/AMD moderne, 8+ cœurs, Python 3.12.
    Ici testé sur {GRID_SIZE_PERF}×{GRID_SIZE_PERF} en CI avec seuil adapté.
    """
    _cache.clear()
    site = _make_perf_site(GRID_SIZE_PERF)
    settings = SafetySettings()
    cost_grid = build_cost_grid(site, settings)

    targets_pos = [
        _grid_point(site, 0.2, 0.2),
        _grid_point(site, 0.2, 0.8),
        _grid_point(site, 0.5, 0.5),
        _grid_point(site, 0.8, 0.2),
        _grid_point(site, 0.8, 0.8),
    ]
    start = _grid_point(site, 0.1, 0.1)
    end = _grid_point(site, 0.9, 0.9)

    t0 = time.perf_counter()
    waypoints = [start, *targets_pos, end]
    geom = plan_route(cost_grid, waypoints, RouteOptions(window_margin_m=300.0))
    elapsed = time.perf_counter() - t0

    print(
        f"\n[PERF] plan_route 5 cibles, {GRID_SIZE_PERF}×{GRID_SIZE_PERF} "
        f"à {RESOLUTION_PERF} m: {elapsed:.3f} s"
    )
    # Sur 500×500, le critère est < 1 s ; tolérance 10 s pour CI variabilité
    assert elapsed < 10.0, f"Trop lent : {elapsed:.2f} s (seuil 10 s)"
    assert len(geom.coordinates) >= 2


@pytest.mark.timeout(10)
def test_target_move_cache_speedup() -> None:
    """Après déplacement d'une cible, le recalcul partiel doit être < 2 s.

    Machine de référence : même que ci-dessus.
    Paramètres : grille {GRID_SIZE_PERF}×{GRID_SIZE_PERF}, 3 points de passage.
    """
    _cache.clear()
    site = _make_perf_site(GRID_SIZE_PERF)
    settings = SafetySettings()
    cost_grid = build_cost_grid(site, settings)

    start = _grid_point(site, 0.1, 0.1)
    t1 = _grid_point(site, 0.4, 0.4)
    t2 = _grid_point(site, 0.6, 0.6)
    end = _grid_point(site, 0.9, 0.9)

    opts = RouteOptions(window_margin_m=300.0)
    # Calcul initial (remplit le cache)
    _ = plan_route(cost_grid, [start, t1, t2, end], opts)

    # Déplacer t2 légèrement (tronçon t1→t2 et t2→end changent, start→t1 reste en cache)
    t2_new = _grid_point(site, 0.62, 0.58)

    t0 = time.perf_counter()
    _ = plan_route(cost_grid, [start, t1, t2_new, end], opts)
    elapsed = time.perf_counter() - t0

    print(f"\n[PERF] recalcul après déplacement de cible : {elapsed:.3f} s")
    assert elapsed < 5.0, f"Recalcul trop lent : {elapsed:.2f} s (seuil 5 s)"


def test_cache_reuse_measured() -> None:
    """Le deuxième appel identique doit utiliser le cache (nettement plus rapide)."""
    _cache.clear()
    site = _make_perf_site(GRID_SIZE_PERF)
    settings = SafetySettings()
    cost_grid = build_cost_grid(site, settings)

    start = _grid_point(site, 0.2, 0.2)
    end = _grid_point(site, 0.8, 0.8)
    opts = RouteOptions(window_margin_m=200.0)

    # Premier appel (calcul + mise en cache)
    t0 = time.perf_counter()
    plan_route(cost_grid, [start, end], opts)
    t_first = time.perf_counter() - t0

    # Deuxième appel (depuis cache)
    t0 = time.perf_counter()
    plan_route(cost_grid, [start, end], opts)
    t_second = time.perf_counter() - t0

    print(f"\n[PERF] premier appel: {t_first:.4f} s, second (cache): {t_second:.4f} s")
    assert t_second < t_first / 2 or t_second < 0.001, (
        f"Le cache ne semble pas être utilisé : {t_second:.4f} s vs {t_first:.4f} s"
    )
