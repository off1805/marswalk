"""Validation visuelle des tuiles HiRISE au zoom 19 (critère D3).

Usage :
    uv run python -m marswalk_pipeline.package.hirise_visual_check [--out OUTPUT_DIR]

Produit :
    - hirise_z19_mosaic.png : mosaïque de 4x4 tuiles au zoom 19
    - hirise_z19_detail.png : zoom sur une tuile centrale
    - hirise_z19_cog_comparison.png : comparaison tuile vs COG source
    - hirise_visual_report.md : rapport de qualite
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw

from marswalk_core.paths import repo_root
from marswalk_core.schemas import SiteManifest
from marswalk_pipeline.package.tiling import (
    pixel_centers,
    tile_range,
)

JEZERO = repo_root() / "data" / "packages" / "jezero"


def _rgba(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGBA"))


def _load_manifest() -> SiteManifest:
    return SiteManifest.model_validate_json((JEZERO / "manifest.json").read_text("utf-8"))


def build_z19_mosaic(manifest: SiteManifest, out_dir: Path, nx: int = 4, ny: int = 4) -> Path:
    """Mosaique nx x ny tuiles HiRISE au zoom 19."""
    bbox = manifest.bbox
    z = 19
    x0, y0, x1, y1 = tile_range(bbox, z)
    # Prendre les tuiles centrales
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    tx_start = cx - nx // 2
    ty_start = cy - ny // 2

    mosaic = Image.new("RGB", (256 * nx, 256 * ny), (128, 128, 128))
    found = 0
    for dy in range(ny):
        for dx in range(nx):
            tx = tx_start + dx
            ty = ty_start + dy
            path = JEZERO / "tiles" / "hirise_vis" / str(z) / str(tx) / f"{ty}.webp"
            if path.is_file():
                rgba = Image.open(path).convert("RGBA")
                # Fond gris pour les zones transparentes
                bg = Image.new("RGB", rgba.size, (100, 100, 100))
                bg.paste(rgba, mask=rgba.split()[3])
                mosaic.paste(bg, (dx * 256, dy * 256))
                found += 1

    out = out_dir / "hirise_z19_mosaic.png"
    mosaic.save(out)
    print(f"Mosaique z19 ({found}/{nx * ny} tuiles) : {out}")
    return out


def build_detail_comparison(manifest: SiteManifest, out_dir: Path) -> Path:
    """Comparaison cote a cote : tuile z19 vs extraction COG a la meme position."""
    bbox = manifest.bbox
    z = 19
    x0, y0, x1, y1 = tile_range(bbox, z)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2

    tile_path = JEZERO / "tiles" / "hirise_vis" / str(z) / str(cx) / f"{cy}.webp"
    cog_path = JEZERO / "cog" / "hirise_vis.tif"

    if not tile_path.is_file():
        print(f"Tuile z19 {cx}/{cy} absente")
        return out_dir / "hirise_z19_comparison.png"

    # Tuile WebP
    tile_img = Image.open(tile_path).convert("RGBA")
    tile_arr = np.asarray(tile_img)

    # Extraction du COG a la meme emprise
    lons, lats = pixel_centers(z, cx, cy)
    # Convertir la bbox de la tuile en coordonnees analytiques
    lon_min, lon_max = float(lons.min()), float(lons.max())
    lat_min, lat_max = float(lats.min()), float(lats.max())

    with rasterio.open(cog_path) as ds:
        # Trouver les indices raster correspondants
        a, _b, c, _d, e, f = tuple(ds.transform)[:6]
        # Coord analytiques depuis lon/lat (approximation pour le COG 1 m)
        # Le COG est dans le CRS d'analyse -> convertir via pyproj serait rigoureux,
        # mais comme lon/lat Jezero ≈ x/y EQC a cette latitude, on approxime.
        radius_m = 3396190.0
        lat_ts = 18.4446
        lon0 = 77.4502
        k = math.cos(math.radians(lat_ts))
        x_min = radius_m * math.radians(lon_min - lon0) * k
        x_max = radius_m * math.radians(lon_max - lon0) * k
        y_min = radius_m * math.radians(lat_min)
        y_max = radius_m * math.radians(lat_max)
        col0 = max(0, int((x_min - c) / a))
        col1 = min(ds.width, int((x_max - c) / a) + 1)
        row0 = max(0, int((y_max - f) / e))
        row1 = min(ds.height, int((y_min - f) / e) + 1)

        if col1 > col0 and row1 > row0:
            win = rasterio.windows.Window(col0, row0, col1 - col0, row1 - row0)
            cog_arr = ds.read(1, window=win, masked=True).astype(np.float32)
            cog_data = np.ma.filled(cog_arr, -9999.0)
        else:
            cog_data = np.zeros((256, 256), np.float32)

    # Normaliser le COG pour l'affichage
    valid = cog_data[cog_data > -9000]
    if valid.size > 0:
        lo, hi = np.percentile(valid, [0.5, 99.5])
        cog_norm = np.clip((cog_data - lo) / max(hi - lo, 1) * 255, 0, 255).astype(np.uint8)
    else:
        cog_norm = np.zeros_like(cog_data, dtype=np.uint8)

    # Redimensionner le COG a 256x256
    cog_img = Image.fromarray(cog_norm).resize((256, 256), Image.Resampling.LANCZOS)

    # Image de comparaison cote a cote
    comparison = Image.new("RGB", (256 * 2 + 20, 280), (200, 200, 200))
    # Tuile WebP (canal R = niveaux de gris)
    tile_gray = tile_arr[..., 0].copy()
    tile_gray[tile_arr[..., 3] == 0] = 128  # fond gris pour les transparents
    tile_display = Image.fromarray(tile_gray)
    comparison.paste(tile_display, (0, 24))
    comparison.paste(cog_img, (256 + 20, 24))

    # Labels
    draw = ImageDraw.Draw(comparison)
    draw.text((10, 5), f"Tuile WebP z{z} ({cx},{cy})", fill=(0, 0, 0))
    draw.text((266 + 20, 5), "COG 1m (meme emprise)", fill=(0, 0, 0))

    out = out_dir / "hirise_z19_detail_comparison.png"
    comparison.save(out)
    print(f"Comparaison tuile/COG : {out}")
    return out


def measure_tile_quality(manifest: SiteManifest) -> dict[str, float]:
    """Mesure la qualite des tuiles HiRISE au zoom 19."""
    bbox = manifest.bbox
    z = 19
    x0, y0, x1, y1 = tile_range(bbox, z)
    total_tiles = (x1 - x0 + 1) * (y1 - y0 + 1)

    tile_dir = JEZERO / "tiles" / "hirise_vis" / str(z)
    actual_tiles = list(tile_dir.rglob("*.webp")) if tile_dir.is_dir() else []

    # Statistiques sur un echantillon de tuiles
    stds = []
    sizes = []
    for t in actual_tiles[:50]:
        rgba = _rgba(t)
        gray = rgba[..., 0][rgba[..., 3] > 0]
        if gray.size > 0:
            stds.append(float(gray.std()))
            sizes.append(t.stat().st_size)

    # Verifier les transitions entre tuiles adjacentes (mesure pixel-a-pixel correcte)
    border_diffs = []
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    for tx, ty in [(cx, cy), (cx + 1, cy), (cx, cy + 1)]:
        p1 = tile_dir / str(tx) / f"{ty}.webp"
        p2 = tile_dir / str(tx + 1) / f"{ty}.webp"
        if p1.is_file() and p2.is_file():
            rgba1 = _rgba(p1)
            rgba2 = _rgba(p2)
            # Bord droit de p1 (colonne -1) vs bord gauche de p2 (colonne 0), ligne par ligne
            for row in range(0, 256, 4):
                if rgba1[row, -1, 3] > 0 and rgba2[row, 0, 3] > 0:
                    diff = abs(int(rgba1[row, -1, 0]) - int(rgba2[row, 0, 0]))
                    border_diffs.append(diff)

    return {
        "total_expected": total_tiles,
        "total_actual": len(actual_tiles),
        "coverage_pct": 100 * len(actual_tiles) / max(total_tiles, 1),
        "mean_std": float(np.mean(stds)) if stds else 0.0,
        "mean_size_kb": float(np.mean(sizes)) / 1024 if sizes else 0.0,
        "border_diff_mean": float(np.mean(border_diffs)) if border_diffs else 0.0,
    }


def write_report(manifest: SiteManifest, out_dir: Path) -> Path:
    """Ecrit hirise_visual_report.md."""
    q = measure_tile_quality(manifest)
    hirise_layer = next((lay for lay in manifest.layers if lay.id == "hirise_vis"), None)
    maxzoom = hirise_layer.tiles.maxzoom if hirise_layer and hirise_layer.tiles else "N/A"
    minzoom = hirise_layer.tiles.minzoom if hirise_layer and hirise_layer.tiles else "N/A"

    lines = [
        "# Rapport de validation visuelle HiRISE zoom 19",
        "",
        "## Parametres",
        f"- Site : {manifest.site_id} ({manifest.name})",
        "- Couche : hirise_vis",
        f"- Zoom max : {maxzoom}",
        f"- Minzoom : {minzoom}",
        "",
        "## Couverture au zoom 19",
        f"- Tuiles attendues : {q['total_expected']}",
        f"- Tuiles presentes : {q['total_actual']}",
        f"- Couverture : {q['coverage_pct']:.1f}%",
        "",
        "## Qualite des pixels",
        f"- Ecart-type moyen des niveaux de gris : {q['mean_std']:.1f} DN (attendu > 5)",
        f"- Taille moyenne des tuiles : {q['mean_size_kb']:.1f} Ko",
        f"- Difference aux bordures : {q['border_diff_mean']:.1f} DN (attendu < 15 : continuite)",
        "",
        "## Criteres d'acceptation",
        f"- [{'x' if q['total_actual'] >= 100 else ' '}] Plus de 100 tuiles au zoom 19",
        f"- [{'x' if q['mean_std'] > 5 else ' '}] Contraste > 5 DN (image non monochrome)",
        f"- [{'x' if q['border_diff_mean'] < 15 else ' '}] Continuite aux bordures < 15 DN",
        "",
        "## Captures",
        "- `hirise_z19_mosaic.png` : mosaique 4x4 tuiles centrales",
        "- `hirise_z19_detail_comparison.png` : comparaison tuile WebP vs extraction COG",
    ]

    out = out_dir / "hirise_visual_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Rapport : {out}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=JEZERO / "validation",
        help="Repertoire de sortie (defaut: data/packages/jezero/validation/)",
    )
    args = parser.parse_args(argv)
    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if not (JEZERO / "manifest.json").is_file():
        print("ERREUR: Paquet Jezero absent de data/packages/jezero/", file=sys.stderr)
        return 1

    manifest = _load_manifest()
    hirise = next((lay for lay in manifest.layers if lay.id == "hirise_vis"), None)
    if hirise is None or hirise.tiles is None:
        print("ERREUR: couche hirise_vis absente du manifeste", file=sys.stderr)
        return 1

    print(f"Validation visuelle HiRISE zoom {hirise.tiles.maxzoom}")
    build_z19_mosaic(manifest, out_dir)
    build_detail_comparison(manifest, out_dir)
    report_path = write_report(manifest, out_dir)

    # Lire et afficher le rapport
    print("\n" + report_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
