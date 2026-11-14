"""Tests de D3 : paquet de site (taches-agents.md, fiche D3)."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from PIL import Image
from rasterio.crs import CRS
from rasterio.transform import Affine

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root
from marswalk_core.schemas import SiteManifest
from marswalk_core.site_package import open_package
from marswalk_pipeline.package import PackageTooLargeError, build_package
from marswalk_pipeline.package.catalog import CATALOG
from marswalk_pipeline.package.fixture import export_work_dir
from marswalk_pipeline.package.tiling import (
    decode_terrain_rgb,
    max_zoom_for,
    pixel_centers,
    tile_pixel_size_m,
    tile_range,
)

FICTIF = repo_root() / "fixtures" / "sites" / "fictif"
STAMP = datetime(2026, 11, 14, tzinfo=UTC)
R = 3396190.0


@pytest.fixture(scope="module")
def work(tmp_path_factory: pytest.TempPathFactory) -> Path:
    w = tmp_path_factory.mktemp("work") / "fictif"
    export_work_dir(FICTIF, w)
    return w


@pytest.fixture(scope="module")
def rebuilt(work: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("packages") / "fictif"
    build_package("fictif", work, out, generated_at=STAMP)
    return out


def _manifest(root: Path) -> SiteManifest:
    return SiteManifest.model_validate_json((root / "manifest.json").read_text("utf-8"))


def _rgba(path: Path) -> np.ndarray[Any, np.dtype[np.uint8]]:
    return np.asarray(Image.open(path).convert("RGBA"))


# -- Zooms -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("resolution_m", "expected"),
    [(0.25, 19), (1.0, 17), (2.0, 16), (6.0, 14), (18.0, 13), (100.0, 12), (463.0, 12)],
)
def test_max_zoom_follows_resolution(resolution_m: float, expected: int) -> None:
    assert max_zoom_for(resolution_m, 18.4, R, 12) == expected


def test_pixel_size_at_jezero() -> None:
    assert tile_pixel_size_m(18, 18.4, R) == pytest.approx(0.302, abs=1e-3)
    assert tile_pixel_size_m(19, 18.4, R) == pytest.approx(0.151, abs=1e-3)


# -- Site fictif régénéré ----------------------------------------------------


def test_rebuilt_fictif_is_valid_and_matches_t00(rebuilt: Path) -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("v", repo_root() / "tools" / "validate_site_package.py")
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.validate(rebuilt) == []

    old, new = _manifest(FICTIF), _manifest(rebuilt)
    assert [layer.id for layer in new.layers] == [layer.id for layer in old.layers]
    assert new.bbox == pytest.approx(old.bbox, abs=1e-7)
    assert new.grid == old.grid
    assert new.habitat == pytest.approx(old.habitat, abs=1e-7)
    for a, b in zip(old.layers, new.layers, strict=True):
        assert (a.source, a.legend, a.resolution_m, a.status) == (
            b.source,
            b.legend,
            b.resolution_m,
            b.status,
        )
        if a.cog:
            with rasterio.open(FICTIF / a.cog) as x, rasterio.open(rebuilt / str(b.cog)) as y:
                assert np.array_equal(x.read(1), y.read(1)), a.id
        if a.tiles:
            assert b.tiles is not None
            assert (b.tiles.minzoom, b.tiles.maxzoom) == (a.tiles.minzoom, a.tiles.maxzoom)

    def tile_set(root: Path) -> set[str]:
        return {str(p.relative_to(root / "tiles")) for p in (root / "tiles").rglob("*.*")}

    assert tile_set(rebuilt) == tile_set(FICTIF)


@pytest.mark.parametrize("layer_id", ["loose_soil", "obstacles", "scarps", "crism_minerals"])
def test_categorical_tiles_identical_to_t00_at_max_zoom(rebuilt: Path, layer_id: str) -> None:
    for path in (FICTIF / "tiles" / layer_id / "16").rglob("*.webp"):
        other = rebuilt / "tiles" / layer_id / path.relative_to(FICTIF / "tiles" / layer_id)
        assert np.array_equal(_rgba(path), _rgba(other)), path


@pytest.mark.parametrize("layer_id", ["loose_soil", "crism_minerals", "obstacles"])
def test_tile_pixels_align_with_cog_values(rebuilt: Path, layer_id: str) -> None:
    """Une valeur interrogée dans le COG correspond au pixel affiché (fiche D3)."""
    site = open_package(rebuilt)
    info = site.layer(layer_id)
    assert info.tiles is not None and info.legend is not None
    colors = {
        tuple(int(s.color[i : i + 2], 16) for i in (1, 3, 5)): s.value for s in info.legend.stops
    }
    transparent = set(CATALOG[layer_id].display.transparent)
    z = info.tiles.maxzoom
    rng = np.random.default_rng(7)
    x0, y0, x1, y1 = tile_range(site.manifest.bbox, z)
    checked = 0
    for _ in range(40):
        tx, ty = int(rng.integers(x0, x1 + 1)), int(rng.integers(y0, y1 + 1))
        path = rebuilt / "tiles" / layer_id / str(z) / str(tx) / f"{ty}.webp"
        if not path.is_file():
            continue
        rgba = _rgba(path)
        lons, lats = pixel_centers(z, tx, ty)
        for _ in range(25):
            i, j = int(rng.integers(0, 256)), int(rng.integers(0, 256))
            value = site.sample(layer_id, float(lons[j]), float(lats[i]))
            if value is None or rgba[i, j, 3] == 0:
                # hors emprise, ou classe laissée transparente
                assert value is None or value in transparent
            else:
                assert colors[tuple(int(c) for c in rgba[i, j, :3])] == value
            checked += 1
    assert checked > 100


def test_terrain_rgb_matches_dem(rebuilt: Path) -> None:
    site = open_package(rebuilt)
    terrain = site.manifest.terrain
    assert terrain is not None
    z = terrain.maxzoom
    x0, y0, x1, y1 = tile_range(site.manifest.bbox, z)
    tx, ty = (x0 + x1) // 2, (y0 + y1) // 2
    heights = decode_terrain_rgb(
        _rgba(rebuilt / "tiles" / "terrain_rgb" / str(z) / str(tx) / f"{ty}.png")
    )
    lons, lats = pixel_centers(z, tx, ty)
    errors = [
        abs(heights[i, j] - (site.sample("dem", float(lons[j]), float(lats[i])) or math.nan))
        for i in range(0, 256, 16)
        for j in range(0, 256, 16)
    ]
    # Bilinéaire contre plus proche voisin : l'écart reste celui d'une demi-case en pente.
    assert np.nanmax(errors) < 1.5


def test_imagery_quality_and_stretch(rebuilt: Path) -> None:
    """WebP avec perte de qualité ≥ 90 pour l'imagerie, contraste étiré sur l'emprise."""
    tiles = list((rebuilt / "tiles" / "hirise_vis" / "16").rglob("*.webp"))
    values = np.concatenate([_rgba(p)[..., 0][_rgba(p)[..., 3] > 0] for p in tiles])
    lo, hi = np.percentile(values, [0.5, 99.5])
    assert lo <= 10 and hi >= 245


# -- Limite de taille et reproductibilité --------------------------------------


def _small_config() -> dict[str, Any]:
    cfg = dict(load_site_config("fictif"))
    cfg["layers"] = ["hirise_vis", "dem", "loose_soil", "rover_traverse"]
    return cfg


def _digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_build_is_reproducible(work: Path, tmp_path: Path) -> None:
    a, b = tmp_path / "a" / "fictif", tmp_path / "b" / "fictif"
    for out in (a, b):
        build_package("fictif", work, out, config=_small_config(), generated_at=STAMP)
    assert _digest(a) == _digest(b)


def test_too_large_package_is_refused_and_previous_kept(work: Path, tmp_path: Path) -> None:
    out = tmp_path / "fictif"
    build_package("fictif", work, out, config=_small_config(), generated_at=STAMP)
    before = _digest(out)
    with pytest.raises(PackageTooLargeError):
        build_package(
            "fictif", work, out, config=_small_config(), generated_at=STAMP, max_bytes=100_000
        )
    assert _digest(out) == before
    assert not (tmp_path / ".build-fictif").exists()


def test_missing_layers_are_declared_missing(work: Path, tmp_path: Path) -> None:
    cfg = _small_config()
    cfg["layers"] = [*cfg["layers"], "slope"]
    (work / "derived" / "slope.tif").rename(tmp_path / "slope.tif")
    try:
        out = tmp_path / "fictif"
        build_package("fictif", work, out, config=cfg, generated_at=STAMP)
    finally:
        (tmp_path / "slope.tif").rename(work / "derived" / "slope.tif")
    slope = next(layer for layer in _manifest(out).layers if layer.id == "slope")
    assert slope.status == "missing" and slope.cog is None


# -- Imagerie pleine résolution (display/) --------------------------------------


def _write(path: Path, data: np.ndarray[Any, Any], transform: Affine, crs: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype="float32",
        crs=CRS.from_string(crs),
        transform=transform,
        nodata=-9999.0,
    ) as ds:
        ds.write(data.astype("float32"), 1)


def test_display_raster_keeps_full_resolution_tiles(tmp_path: Path) -> None:
    """HiRISE à 0,25 m : COG sur la grille du MNT, tuiles jusqu'au zoom 19."""
    crs = "+proj=eqc +lat_ts=18.44 +lon_0=77.45 +R=3396190 +units=m +no_defs"
    yc = round(R * math.radians(18.44))
    work = tmp_path / "work"
    _write(
        work / "aligned" / "dem.tif",
        np.linspace(-2600, -2580, 40 * 40).reshape(40, 40),
        Affine(2.0, 0, -40.0, 0, -2.0, yc + 40.0),
        crs,
    )
    rng = np.random.default_rng(3)
    _write(
        work / "display" / "hirise_vis.tif",
        rng.uniform(40, 200, (320, 320)),
        Affine(0.25, 0, -40.0, 0, -0.25, yc + 40.0),
        crs,
    )
    (work / "layers").mkdir()
    (work / "layers" / "hirise_vis.json").write_text(
        json.dumps({"resolution_m": 0.25, "source": {"instrument": "HiRISE", "mission": "MRO"}})
    )
    cfg = {
        "name": "Essai",
        "analysis_crs": crs,
        "layers": ["hirise_vis", "dem"],
        "habitat": {"x": 0, "y": 0},
        "mission_epoch_utc": "2026-11-01T00:00:00Z",
    }
    out = tmp_path / "packages" / "essai"
    build_package("essai", work, out, config=cfg, generated_at=STAMP)
    m = _manifest(out)
    hirise = next(layer for layer in m.layers if layer.id == "hirise_vis")
    dem = next(layer for layer in m.layers if layer.id == "dem")
    assert hirise.tiles is not None and hirise.tiles.maxzoom == 19
    assert dem.tiles is not None and dem.tiles.maxzoom == 16
    assert m.terrain is not None and m.terrain.maxzoom == 16
    with rasterio.open(out / "cog" / "hirise_vis.tif") as ds:
        assert (ds.width, ds.height) == (40, 40)
        assert ds.dtypes[0] == "float32" and ds.nodata == -9999.0
    assert any((out / "tiles" / "hirise_vis" / "19").rglob("*.webp"))
