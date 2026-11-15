"""Inspection complète de tous les rasters dans data/raw/jezero/.

Usage : uv run scripts/inspect_all_rasters.py
Produit un résumé tabulaire et signale les anomalies.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import rasterio
except ImportError:
    print("ERREUR : rasterio non disponible. Lancer via 'uv run'.")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "jezero"

# Fichiers attendus et leur nature documentée
EXPECTED: dict[str, str] = {
    "JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first_dd.tif": "HiRISE ortho (25 cm)",
    "JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif": "CTX ortho (6 m)",
    "JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif": "HiRISE DTM (1 m)",
    "M20_JezeroCrater_CTXDEM_20m.tif": "CTX DEM (20 m)",
    "Mars_MGS_MOLA_DEM_mosaic_global_463m.tif": "MOLA DEM (463 m)",
    "Mars_MGS_MOLA_ClrShade_merge_global_463m.tif": "MOLA Hillshade (463 m) — PAS un DEM",
    "Jezero_Thermal_Inertia_v1.tiff": "THEMIS Thermal Inertia (100 m)",
    "jezeroFinal.tif": "CRISM minerals (catégoriel)",
    "ESP_046060_1985_RED.JP2": "HiRISE image individuelle",
    "ESP_045994_1985_RED.JP2": "HiRISE image individuelle",
}


def inspect_one(path: Path) -> dict:
    size_mb = round(path.stat().st_size / 1024 / 1024, 2)
    result: dict = {"name": path.name, "size_mb": size_mb, "error": None}
    try:
        with rasterio.open(path) as src:
            result.update(
                {
                    "driver": src.driver,
                    "crs_wkt": str(src.crs) if src.crs else "ABSENT",
                    "crs_proj4": src.crs.to_proj4() if src.crs else "ABSENT",
                    "crs_authority": src.crs.to_authority() if src.crs else ("", ""),
                    "width": src.width,
                    "height": src.height,
                    "bands": src.count,
                    "dtypes": list(src.dtypes),
                    "nodata": src.nodata,
                    "bounds": src.bounds,
                    "res_x": src.res[0],
                    "res_y": src.res[1],
                    "transform": src.transform,
                }
            )
    except Exception as exc:
        result["error"] = str(exc)
    return result


def flag_issues(r: dict) -> list[str]:
    """Retourne la liste des anomalies détectées pour un raster."""
    issues: list[str] = []
    if r.get("error"):
        issues.append(f"ERREUR OUVERTURE : {r['error']}")
        return issues

    name = r["name"]

    # CRS absent
    if r["crs_wkt"] == "ABSENT":
        issues.append("CRS ABSENT")

    # NoData absent sur des fichiers où il devrait être défini
    if r["nodata"] is None and "MOLA" not in name and "ClrShade" not in name:
        issues.append("NODATA non défini")

    # NoData = 0 sur thermal inertia → risque de confusion avec vraies valeurs nulles
    if "Thermal" in name and r.get("nodata") == 0.0:
        issues.append(
            "NODATA=0 sur données de thermal inertia — risque de confusion avec valeurs réelles"
        )

    # jezeroFinal multi-bande (catégoriel attendu en 1 bande ou palette)
    if "jezeroFinal" in name and r.get("bands", 1) == 3 and r.get("dtypes", [""])[0] == "uint8":
        issues.append(
            "CRISM : 3 bandes uint8 — carte de couleurs RGB, "
            "pas un raster de classes entières ; "
            "rééchantillonnage nearest neighbour sur bandes séparées"
        )

    # Hillshade confondu avec DEM
    if "ClrShade" in name:
        issues.append("HILLSHADE — ne pas utiliser comme DEM")

    # Coordonnées géographiques vs projetées
    bounds = r.get("bounds")
    if bounds:
        if abs(bounds.left) <= 400 and abs(bounds.bottom) <= 100:
            # probablement des degrés
            if abs(bounds.left) < 360 and abs(bounds.bottom) < 90:
                issues.append(
                    "Coordonnées en DEGRÉS (géographiques) "
                    "— reprojection en mètres nécessaire"
                )
        else:
            # Coordonnées métriques
            pass

    return issues


def main() -> None:
    print(f"\n{'='*80}")
    print("INSPECTION DES RASTERS — data/raw/jezero/")
    print(f"{'='*80}\n")

    actual_files = sorted(DATA_DIR.iterdir())
    actual_names = {f.name for f in actual_files}

    # Fichiers attendus mais absents
    missing = set(EXPECTED.keys()) - actual_names
    # Fichiers présents mais non documentés
    unexpected = actual_names - set(EXPECTED.keys())

    if missing:
        print("FICHIERS ATTENDUS ABSENTS :")
        for m in sorted(missing):
            print(f"  ✗ {m}")
        print()

    if unexpected:
        print("FICHIERS NON DOCUMENTÉS PRÉSENTS :")
        for u in sorted(unexpected):
            print(f"  ? {u}")
        print()

    results = []
    for f in actual_files:
        print(f"Inspection : {f.name}  ({round(f.stat().st_size/1e6, 1)} MB)...")
        r = inspect_one(f)
        r["nature"] = EXPECTED.get(f.name, "inconnu")
        r["issues"] = flag_issues(r)
        results.append(r)

    # -------------------------------------------------------------------------
    # Tableau récapitulatif
    # -------------------------------------------------------------------------
    print(f"\n{'='*80}")
    print("TABLEAU RÉCAPITULATIF")
    print(f"{'='*80}\n")

    col_w = 42
    sep = "-" * 160

    header = (
        f"{'Fichier':<{col_w}} "
        f"{'MB':>8} "
        f"{'Driver':<8} "
        f"{'Dims (W×H)':<18} "
        f"{'Bands':<6} "
        f"{'Dtype':<10} "
        f"{'NoData':<12} "
        f"{'Rés (m ou °)':<18} "
        f"{'CRS (autorité)':<20}"
    )
    print(header)
    print(sep)

    for r in results:
        if r.get("error"):
            print(f"{'  ' + r['name']:<{col_w}} {'ERR':>8}  {r['error'][:60]}")
            continue
        auth = r.get("crs_authority") or ("", "")
        auth_str = f"{auth[0]}:{auth[1]}" if auth[0] else "custom PROJ"
        # Résolution : adapter selon unité
        bounds = r.get("bounds")
        res_x = r.get("res_x", 0)
        if bounds and abs(bounds.left) < 500:
            res_str = f"~{res_x:.6f}°"
        else:
            res_str = f"{res_x:.2f} m"
        dims = f"{r.get('width',0)} × {r.get('height',0)}"
        dtype = r.get("dtypes", ["?"])[0]
        nodata = str(r.get("nodata"))[:10]
        print(
            f"  {r['name']:<{col_w-2}} "
            f"{r['size_mb']:>8.1f} "
            f"{r.get('driver','?'):<8} "
            f"{dims:<18} "
            f"{r.get('bands',0):<6} "
            f"{dtype:<10} "
            f"{nodata:<12} "
            f"{res_str:<18} "
            f"{auth_str:<20}"
        )

    # -------------------------------------------------------------------------
    # CRS détaillés
    # -------------------------------------------------------------------------
    print(f"\n{'='*80}")
    print("CRS PROJ4 PAR FICHIER")
    print(f"{'='*80}\n")
    for r in results:
        if r.get("error"):
            continue
        print(f"  {r['name']}")
        print(f"    PROJ4   : {r.get('crs_proj4','?')}")
        print(f"    Auth    : {r.get('crs_authority')}")
        b = r.get("bounds")
        if b:
            print(
                f"    Bounds  : L={b.left:.4f}  B={b.bottom:.4f}  "
                f"R={b.right:.4f}  T={b.top:.4f}"
            )
        print(f"    NoData  : {r.get('nodata')}")
        print()

    # -------------------------------------------------------------------------
    # Anomalies
    # -------------------------------------------------------------------------
    print(f"{'='*80}")
    print("ANOMALIES ET POINTS D'ATTENTION")
    print(f"{'='*80}\n")

    any_issue = False
    for r in results:
        if r.get("issues") or r.get("error"):
            any_issue = True
            print(f"  [{r['name']}]")
            if r.get("error"):
                print(f"    ✗ {r['error']}")
            for issue in r.get("issues", []):
                print(f"    !! {issue}")
            print()

    if not any_issue:
        print("  Aucune anomalie détectée.\n")

    print(f"{'='*80}")
    print(f"Total : {len(results)} fichiers inspectés")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
