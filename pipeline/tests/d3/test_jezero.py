"""Tests spécifiques au site Jezero pour D3 (taches-agents.md, fiche D3).

Ces tests s'appuient sur le paquet Jezero produit dans ``data/packages/jezero/``.
Ils sont marqués ``jezero`` pour être sautés si le paquet n'est pas disponible.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from PIL import Image

from marswalk_core.paths import repo_root
from marswalk_core.schemas import SiteManifest
from marswalk_core.site_package import open_package
from marswalk_pipeline.package.tiling import (
    decode_terrain_rgb,
    pixel_centers,
    tile_pixel_size_m,
    tile_range,
)

JEZERO = repo_root() / "data" / "packages" / "jezero"
R = 3396190.0
LAT_JEZERO = 18.4446


@pytest.fixture(scope="module")
def jezero_manifest() -> SiteManifest:
    if not (JEZERO / "manifest.json").is_file():
        pytest.skip("Paquet Jezero absent de data/packages/jezero/")
    return SiteManifest.model_validate_json((JEZERO / "manifest.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def jezero_site() -> Any:
    if not (JEZERO / "manifest.json").is_file():
        pytest.skip("Paquet Jezero absent de data/packages/jezero/")
    return open_package(JEZERO)


def _rgba(path: Path) -> np.ndarray[Any, np.dtype[np.uint8]]:
    return np.asarray(Image.open(path).convert("RGBA"))


# ---------------------------------------------------------------------------
# Validation structurelle
# ---------------------------------------------------------------------------


@pytest.mark.jezero
def test_jezero_package_passes_validator() -> None:
    """Le paquet Jezero passe le validateur T00."""
    if not (JEZERO / "manifest.json").is_file():
        pytest.skip("Paquet Jezero absent")
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("v", repo_root() / "tools" / "validate_site_package.py")
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    errors = mod.validate(JEZERO)
    assert errors == [], f"Erreurs de validation : {errors}"


@pytest.mark.jezero
def test_jezero_manifest_crs(jezero_manifest: SiteManifest) -> None:
    """analysis_crs conforme à la règle R1 (EQC Mars 2000, lat_ts=18.4446)."""
    crs = jezero_manifest.analysis_crs
    assert "+proj=eqc" in crs
    assert "+R=3396190" in crs
    assert "18.4446" in crs or "18.44" in crs


@pytest.mark.jezero
def test_jezero_grid_dimensions(jezero_manifest: SiteManifest) -> None:
    """Grille 5000x5000 à 1 m/px."""
    assert jezero_manifest.grid.width == 5000
    assert jezero_manifest.grid.height == 5000
    assert jezero_manifest.grid.resolution_m == pytest.approx(1.0, abs=0.01)


@pytest.mark.jezero
def test_jezero_bbox_covers_site(jezero_manifest: SiteManifest) -> None:
    """L'emprise couvre bien les 5x5 km autour du centre de Jezero."""
    west, south, east, north = jezero_manifest.bbox
    # Le centre est à lon=77.4502, lat=18.4446
    assert west < 77.4502 < east
    assert south < 18.4446 < north
    # Largeur d'au moins 0.08° (≈ 5 km à Jezero)
    assert east - west >= 0.08
    assert north - south >= 0.07


# ---------------------------------------------------------------------------
# Niveaux de zoom (critère d'acceptation D3)
# ---------------------------------------------------------------------------


@pytest.mark.jezero
def test_hirise_vis_tiles_reach_zoom_19(jezero_manifest: SiteManifest) -> None:
    """hirise_vis doit avoir des tuiles jusqu'au zoom 19 (section 4)."""
    hirise = next((lay for lay in jezero_manifest.layers if lay.id == "hirise_vis"), None)
    assert hirise is not None
    assert hirise.tiles is not None, "hirise_vis doit avoir des tuiles"
    assert hirise.tiles.maxzoom == 19, f"hirise_vis.maxzoom={hirise.tiles.maxzoom}, attendu 19"
    # Vérifier qu'il y a réellement des tuiles au zoom 19
    tile_dir = JEZERO / "tiles" / "hirise_vis" / "19"
    assert tile_dir.is_dir(), "Répertoire tiles/hirise_vis/19/ absent"
    tiles_z19 = list(tile_dir.rglob("*.webp"))
    assert len(tiles_z19) > 0, "Aucune tuile au zoom 19 pour hirise_vis"
    assert len(tiles_z19) >= 100, (
        f"Seulement {len(tiles_z19)} tuiles z19 pour hirise_vis, attendu >=100"
    )


@pytest.mark.jezero
@pytest.mark.parametrize(
    "layer_id",
    [
        "dem",
        "slope",
        "roughness",
        "hillshade",
        "obstacles",
        "scarps",
        "loose_soil",
        "radio_coverage",
        "illumination",
    ],
)
def test_1m_layers_reach_zoom_17(jezero_manifest: SiteManifest, layer_id: str) -> None:
    """Les couches à 1 m doivent avoir des tuiles jusqu'au zoom 17."""
    layer = next((lay for lay in jezero_manifest.layers if lay.id == layer_id), None)
    if layer is None or layer.status == "missing":
        pytest.skip(f"Couche {layer_id} absente ou manquante")
    assert layer.tiles is not None, f"{layer_id} doit avoir des tuiles"
    assert layer.tiles.maxzoom == 17, f"{layer_id}.maxzoom={layer.tiles.maxzoom}, attendu 17"
    tile_dir = JEZERO / "tiles" / layer_id / "17"
    assert tile_dir.is_dir(), f"Répertoire tiles/{layer_id}/17/ absent"
    assert any(tile_dir.rglob("*.webp")), f"Aucune tuile z17 pour {layer_id}"


@pytest.mark.jezero
def test_ctx_vis_max_zoom(jezero_manifest: SiteManifest) -> None:
    """CTX (6 m résolution native) → zoom max 14."""
    ctx = next((lay for lay in jezero_manifest.layers if lay.id == "ctx_vis"), None)
    assert ctx is not None and ctx.tiles is not None
    # La grille ctx_vis est rééchantillonnée à 1 m (grille D1), donc son COG est à 1 m.
    # Le tuilage est fait depuis le COG 1 m → zoom 17.
    # (Si un display/ctx_vis.tif à 6 m existait, ce serait zoom 14.)
    assert ctx.tiles.maxzoom in (14, 17), f"ctx_vis.maxzoom={ctx.tiles.maxzoom}, attendu 14 ou 17"


@pytest.mark.jezero
def test_minzoom_is_12_for_all_layers(jezero_manifest: SiteManifest) -> None:
    """Le zoom minimal de toutes les couches est 12 (section 4)."""
    for layer in jezero_manifest.layers:
        if layer.tiles is not None:
            assert layer.tiles.minzoom == 12, (
                f"{layer.id}.minzoom={layer.tiles.minzoom}, attendu 12"
            )


@pytest.mark.jezero
def test_pixel_size_at_zoom_19_covers_hirise_detail() -> None:
    """Au zoom 19 à Jezero, 1 pixel = ~0,15 m < 0,25 m HiRISE : tout le détail est restitué."""
    pixel_m = tile_pixel_size_m(19, LAT_JEZERO, R)
    assert pixel_m < 0.25, f"Pixel z19 = {pixel_m:.3f} m, doit etre < 0.25 m"
    assert pixel_m > 0.10, f"Pixel z19 = {pixel_m:.3f} m, valeur anormalement faible"


# ---------------------------------------------------------------------------
# Qualité du contenu des tuiles
# ---------------------------------------------------------------------------


@pytest.mark.jezero
def test_hirise_z19_tile_has_detail(jezero_manifest: SiteManifest) -> None:
    """Une tuile HiRISE au zoom 19 contient des niveaux de gris variés (pas monochrome)."""
    tile_dir = JEZERO / "tiles" / "hirise_vis" / "19"
    if not tile_dir.is_dir():
        pytest.skip("Répertoire z19 absent")
    tiles = list(tile_dir.rglob("*.webp"))
    assert len(tiles) > 0

    # Prendre une tuile du milieu
    mid = tiles[len(tiles) // 2]
    rgba = _rgba(mid)
    gray = rgba[..., 0][rgba[..., 3] > 0]  # canal R des pixels opaques
    if gray.size == 0:
        pytest.skip("Tuile entièrement transparente")
    std = float(gray.std())
    assert std > 5.0, (
        f"Tuile HiRISE z19 {mid.name} peu contrastée (std={std:.1f}), attendu > 5 (imagerie variée)"
    )


@pytest.mark.jezero
def test_hirise_z19_cog_coherence(jezero_site: Any) -> None:
    """Les valeurs des tuiles HiRISE z19 correspondent aux valeurs du COG."""
    if not (JEZERO / "cog" / "hirise_vis.tif").is_file():
        pytest.skip("COG hirise_vis absent")
    site = jezero_site
    bbox = site.manifest.bbox

    z = 19
    x0, y0, x1, y1 = tile_range(bbox, z)
    # Prendre une tuile centrale
    tx, ty = (x0 + x1) // 2, (y0 + y1) // 2
    tile_path = JEZERO / "tiles" / "hirise_vis" / str(z) / str(tx) / f"{ty}.webp"
    if not tile_path.is_file():
        pytest.skip(f"Tuile {z}/{tx}/{ty} absente")

    rgba = _rgba(tile_path)
    lons, lats = pixel_centers(z, tx, ty)

    # Vérifier que les pixels opaques correspondent aux valeurs COG
    # (tolérance large car le tuilage utilise bilinéaire, le COG est à 1 m)
    checked = 0
    errors = 0
    for i in range(0, 256, 32):
        for j in range(0, 256, 32):
            if rgba[i, j, 3] == 0:
                continue
            tile_val = float(rgba[i, j, 0])  # niveaux de gris dans le canal R
            cog_val = site.sample("hirise_vis", float(lons[j]), float(lats[i]))
            if cog_val is None:
                continue
            # La tuile vient du display 0.25 m, le COG est à 1 m : tolérance 50 DN
            if abs(tile_val - cog_val) > 50:
                errors += 1
            checked += 1
    assert checked > 10, "Pas assez de pixels à vérifier"
    # On accepte jusqu'à 20% d'écarts (artefacts de rééchantillonnage entre display et COG)
    assert errors / checked < 0.20, f"{errors}/{checked} pixels avec écart > 50 DN (seuil 20%)"


# ---------------------------------------------------------------------------
# COG Jezero
# ---------------------------------------------------------------------------


@pytest.mark.jezero
def test_jezero_cog_dem_properties(jezero_manifest: SiteManifest) -> None:
    """Le COG dem est Float32, nodata=-9999, grille 5000x5000."""
    cog_path = JEZERO / "cog" / "dem.tif"
    assert cog_path.is_file(), "COG dem absent"
    with rasterio.open(cog_path) as ds:
        assert ds.dtypes[0] == "float32"
        assert ds.nodata == pytest.approx(-9999.0)
        assert (ds.width, ds.height) == (5000, 5000)
        # Vérifier la plage altimétrique (D1 : [-2643, -2439])
        data = ds.read(1, masked=True)
        valid = data.compressed()
        assert len(valid) > 0
        assert float(valid.min()) > -3000  # pas de valeurs aberrantes
        assert float(valid.max()) < -2000


@pytest.mark.jezero
def test_jezero_cog_tiled_with_overviews(jezero_manifest: SiteManifest) -> None:
    """Les COG sont tuilés (blocs 256) et ont des overviews."""
    for layer in jezero_manifest.layers:
        if layer.cog is None or layer.status == "missing":
            continue
        with rasterio.open(JEZERO / layer.cog) as ds:
            assert ds.driver == "GTiff", f"{layer.id}: driver {ds.driver}"
            block_h, block_w = ds.block_shapes[0]
            assert block_w == block_h == 256, (
                f"{layer.id}: blocs {block_w}x{block_h}, attendu 256x256"
            )
            assert len(ds.overviews(1)) > 0, f"{layer.id}: pas d'overviews"


# ---------------------------------------------------------------------------
# Terrain-RGB
# ---------------------------------------------------------------------------


@pytest.mark.jezero
def test_jezero_terrain_rgb_present(jezero_manifest: SiteManifest) -> None:
    """Les tuiles terrain-RGB sont présentes."""
    assert jezero_manifest.terrain is not None, "Champ terrain absent du manifeste"
    terrain_dir = JEZERO / "tiles" / "terrain_rgb"
    assert terrain_dir.is_dir()
    pngs = list(terrain_dir.rglob("*.png"))
    assert len(pngs) > 50, f"Seulement {len(pngs)} tuiles terrain-RGB"


@pytest.mark.jezero
def test_jezero_terrain_rgb_matches_dem(jezero_site: Any) -> None:
    """Les valeurs terrain-RGB correspondent aux altitudes du DEM."""
    site = jezero_site
    terrain = site.manifest.terrain
    assert terrain is not None
    bbox = site.manifest.bbox
    z = terrain.maxzoom
    x0, y0, x1, y1 = tile_range(bbox, z)
    tx, ty = (x0 + x1) // 2, (y0 + y1) // 2
    tile_path = JEZERO / "tiles" / "terrain_rgb" / str(z) / str(tx) / f"{ty}.png"
    if not tile_path.is_file():
        pytest.skip(f"Tuile terrain_rgb {z}/{tx}/{ty} absente")

    heights = decode_terrain_rgb(_rgba(tile_path))
    lons, lats = pixel_centers(z, tx, ty)

    errors = []
    for i in range(0, 256, 16):
        for j in range(0, 256, 16):
            h = heights[i, j]
            if math.isnan(h):
                continue
            dem_val = site.sample("dem", float(lons[j]), float(lats[i]))
            if dem_val is None:
                continue
            errors.append(abs(h - dem_val))

    assert len(errors) > 50, "Pas assez de pixels valides pour le test"
    # Tolérance : bilinéaire vs plus proche voisin = 1 résolution max
    assert float(np.max(errors)) < 2.0, (
        f"Ecart terrain-RGB max = {float(np.max(errors)):.2f} m (seuil 2 m)"
    )


# ---------------------------------------------------------------------------
# Taille du package
# ---------------------------------------------------------------------------


@pytest.mark.jezero
def test_jezero_package_size_under_2gb(jezero_manifest: SiteManifest) -> None:
    """La taille totale du paquet est < 2 Go (ENF-10)."""
    total = sum(p.stat().st_size for p in JEZERO.rglob("*") if p.is_file())
    max_bytes = 2 * 1024**3
    assert total < max_bytes, f"Paquet {total / 1e9:.2f} Go > 2 Go"


@pytest.mark.jezero
def test_jezero_manifest_size_field(jezero_manifest: SiteManifest) -> None:
    """Le champ size_bytes du manifeste est cohérent avec la taille réelle."""
    if jezero_manifest.size_bytes is None:
        pytest.skip("size_bytes absent du manifeste")
    actual = sum(p.stat().st_size for p in JEZERO.rglob("*") if p.is_file())
    # Le size_bytes est calculé avant l'écriture du manifest.json lui-même
    # donc un léger écart est attendu
    assert abs(jezero_manifest.size_bytes - actual) < 10 * 1024 * 1024  # < 10 Mo d'écart
