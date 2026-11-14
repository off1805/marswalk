"""Valide un paquet de site contre le contrat (section 5 de taches-agents.md).

Contrôles : schéma JSON du manifeste (contracts/site-manifest.schema.json) et modèle
Pydantic ; identifiants de couches ; présence des COG, tuiles et GeoJSON annoncés ; COG en
Float32, nodata -9999, sur la grille du manifeste ; niveaux de zoom ; taille totale
inférieure à 2 Go (ENF-10), ou à ``--max-mb`` si précisé.

Usage : ``uv run python tools/validate_site_package.py fixtures/sites/fictif [--max-mb 30]``
Code de sortie 0 si le paquet est valide, 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema
import rasterio

from marswalk_core.paths import repo_root
from marswalk_core.schemas import KNOWN_LAYER_IDS, LayerStatus, SiteManifest

MAX_BYTES = 2 * 1024**3
NODATA = -9999.0


def validate(root: Path, max_bytes: int = MAX_BYTES) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return [f"manifest.json absent de {root}"]
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (repo_root() / "contracts" / "site-manifest.schema.json").read_text(encoding="utf-8")
    )
    for err in jsonschema.Draft202012Validator(schema).iter_errors(raw):
        errors.append(f"schéma : {'/'.join(map(str, err.path))} : {err.message}")
    if errors:
        return errors
    m = SiteManifest.model_validate(raw)

    if root.name != m.site_id:
        warnings.append(f"le dossier {root.name} ne porte pas le nom du site {m.site_id}")
    west, south, east, north = m.bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        errors.append(f"bbox invalide : {m.bbox} (longitudes est de -180 à 180)")
    if "+proj=eqc" not in m.analysis_crs or "+R=3396190" not in m.analysis_crs:
        errors.append("analysis_crs doit être une eqc sur la sphère Mars 2000 (règle R1)")

    ids = [layer.id for layer in m.layers]
    if len(ids) != len(set(ids)):
        errors.append("identifiants de couches en double")
    for missing in sorted(set(KNOWN_LAYER_IDS) - set(ids)):
        warnings.append(f"couche du catalogue absente du manifeste : {missing}")

    for layer in m.layers:
        where = f"couche {layer.id}"
        if layer.status == LayerStatus.missing:
            continue
        if not (layer.cog or layer.vector or layer.tiles):
            errors.append(f"{where} : ni cog, ni tuiles, ni vecteur")
        if layer.cog:
            path = root / layer.cog
            if not path.is_file():
                errors.append(f"{where} : COG absent ({layer.cog})")
            else:
                with rasterio.open(path) as ds:
                    if ds.dtypes[0] != "float32":
                        errors.append(f"{where} : COG en {ds.dtypes[0]}, Float32 attendu")
                    if ds.nodata != NODATA:
                        errors.append(f"{where} : nodata {ds.nodata}, -9999 attendu")
                    if (ds.width, ds.height) != (m.grid.width, m.grid.height):
                        errors.append(f"{where} : taille {ds.width}x{ds.height} hors grille")
                    if tuple(round(v, 6) for v in tuple(ds.transform)[:6]) != tuple(
                        round(v, 6) for v in m.grid.transform
                    ):
                        errors.append(f"{where} : transformation différente de la grille")
                    block_h, block_w = ds.block_shapes[0]
                    if ds.driver != "GTiff" or block_h == 1 or block_w != block_h:
                        errors.append(f"{where} : le COG doit être un GeoTIFF tuilé")
        if layer.tiles:
            if layer.tiles.minzoom > layer.tiles.maxzoom:
                errors.append(f"{where} : minzoom supérieur à maxzoom")
            if layer.tiles.minzoom > 12:
                warnings.append(f"{where} : minzoom {layer.tiles.minzoom} (12 attendu)")
            tile_dir = root / layer.tiles.path.split("/{z}")[0]
            if not any(tile_dir.rglob(f"*.{layer.tiles.format}")):
                errors.append(f"{where} : aucune tuile dans {tile_dir.relative_to(root)}")
        if layer.vector:
            vpath = root / layer.vector
            if not vpath.is_file():
                errors.append(f"{where} : GeoJSON absent ({layer.vector})")
            elif json.loads(vpath.read_text()).get("type") != "FeatureCollection":
                errors.append(f"{where} : le GeoJSON doit être une FeatureCollection")
        if layer.legend is None and layer.cog:
            errors.append(f"{where} : légende manquante")

    if m.terrain:
        tdir = root / m.terrain.path.split("/{z}")[0]
        if not any(tdir.rglob("*.png")):
            errors.append("tuiles terrain-RGB annoncées mais absentes")

    size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    if size > max_bytes:
        errors.append(f"taille {size / 1e6:.1f} Mo au-delà de la limite {max_bytes / 1e6:.0f} Mo")

    for w in warnings:
        print(f"avertissement : {w}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--max-mb", type=float, default=None)
    args = parser.parse_args()
    limit = int(args.max_mb * 1e6) if args.max_mb else MAX_BYTES
    errors = validate(args.package, limit)
    for e in errors:
        print(f"ERREUR : {e}")
    print("paquet valide" if not errors else f"{len(errors)} erreur(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
