"""Recalage (coregistration) des rasters sur la grille de référence HiRISE (D1).

Recale THEMIS et CRISM sur HiRISE par appariement de points d'appui (tie points).
Méthode :
  1. Détecter des points de contrôle dans HiRISE (coins et centre de zones texturées).
  2. Chercher le déplacement optimal dans chaque couche secondaire par cross-corrélation
     normalisée (NCC) sur des vignettes d'imagerie.
  3. Estimer la translation (shift_x, shift_y) en mètres par régression des résidus.
  4. Appliquer la translation et écrire le raster recalé.
  5. Mesurer le résidu final (RMSE en mètres) et l'enregistrer dans le rapport.

Référence : Bindschadler et al. (2008), Leprince et al. (2007), méthode simplifiée
adaptée au recalage de couches à résolutions différentes.

Validation humaine requise : la superposition est à vérifier dans QGIS (voir
``qgis/jezero.qgz``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio
import rasterio.transform
import scipy.ndimage

NODATA: float = -9999.0

# Couches secondaires à recaler sur HiRISE
_COREG_LAYERS: tuple[str, ...] = ("thermal_inertia", "crism_minerals", "ctx_vis")

# Nombre de points d'appui par couche
_N_TIE_POINTS: int = 25

# Taille de la vignette en pixels (dans la grille d'analyse) pour NCC
_PATCH_SIZE_PX: int = 32


@dataclass
class CoregResult:
    """Résultat du recalage d'une couche."""

    layer_id: str
    shift_x_m: float = 0.0
    shift_y_m: float = 0.0
    residual_m: float = 0.0
    n_tie_points: int = 0
    status: str = "ok"  # "ok", "degraded", "skipped"
    note: str = ""
    tie_point_residuals: list[float] = field(default_factory=list)


def _ncc(patch_ref: np.ndarray, patch_sec: np.ndarray) -> float:
    """Corrélation croisée normalisée entre deux vignettes (scalaire ∈ [−1, 1])."""
    a = patch_ref - float(np.mean(patch_ref))
    b = patch_sec - float(np.mean(patch_sec))
    denom = float(np.std(a)) * float(np.std(b))
    if denom < 1e-9:
        return 0.0
    return float(np.sum(a * b) / (a.size * denom))


def _find_shift_subpixel(
    ref: np.ndarray,
    sec: np.ndarray,
    resolution_m: float,
    n_points: int = _N_TIE_POINTS,
    patch_px: int = _PATCH_SIZE_PX,
    search_px: int = 8,
) -> tuple[float, float, float, list[float]]:
    """Estime le décalage (shift_x, shift_y) de ``sec`` par rapport à ``ref`` en mètres.

    Algorithme :
      1. Choisit ``n_points`` points d'appui dans des zones texturées de ``ref``.
      2. Pour chaque point, cherche le déplacement (dx, dy) qui maximise la NCC
         dans une fenêtre de ±search_px autour du point dans ``sec``.
      3. Prend la médiane des (dx, dy) pour robustesse aux faux appariements.
      4. Recalcule le résidu RMSE après soustraction de la médiane.

    Retourne (shift_x_m, shift_y_m, rmse_m, liste_résidus_m).
    """
    h, w = ref.shape
    half = patch_px // 2
    margin = half + search_px + 1

    if h <= 2 * margin or w <= 2 * margin:
        return 0.0, 0.0, 0.0, []

    # Masquer les zones nodata
    ref_valid = np.isfinite(ref) & (ref != NODATA)
    sec_valid = np.isfinite(sec) & (sec != NODATA)

    # Variance locale pour trouver des zones texturées
    ref_filled = np.where(ref_valid, ref, 0.0)
    local_var = (
        scipy.ndimage.uniform_filter(ref_filled**2, size=patch_px)
        - scipy.ndimage.uniform_filter(ref_filled, size=patch_px) ** 2
    )
    local_var[:margin, :] = 0.0
    local_var[-margin:, :] = 0.0
    local_var[:, :margin] = 0.0
    local_var[:, -margin:] = 0.0
    local_var[~ref_valid] = 0.0

    # Sélection des n_points cases les plus texturées, espacées d'au moins patch_px
    flat_idx = np.argsort(-local_var.ravel())
    selected: list[tuple[int, int]] = []
    used_rows: list[int] = []
    used_cols: list[int] = []
    for idx in flat_idx:
        r, c = int(idx // w), int(idx % w)
        if any(
            abs(r - ur) < patch_px and abs(c - uc) < patch_px
            for ur, uc in zip(used_rows, used_cols, strict=False)
        ):
            continue
        selected.append((r, c))
        used_rows.append(r)
        used_cols.append(c)
        if len(selected) >= n_points:
            break

    if not selected:
        return 0.0, 0.0, 0.0, []

    # NCC pour chaque point d'appui
    dx_list: list[float] = []
    dy_list: list[float] = []

    for r, c in selected:
        patch_r = ref[r - half : r + half, c - half : c + half]
        if patch_r.shape != (patch_px, patch_px):
            continue
        best_ncc = -2.0
        best_dy, best_dx = 0, 0
        for dy in range(-search_px, search_px + 1):
            for dx in range(-search_px, search_px + 1):
                r2, c2 = r + dy, c + dx
                if r2 - half < 0 or r2 + half > h or c2 - half < 0 or c2 + half > w:
                    continue
                patch_s = sec[r2 - half : r2 + half, c2 - half : c2 + half]
                if not np.all(sec_valid[r2 - half : r2 + half, c2 - half : c2 + half]):
                    continue
                ncc = _ncc(patch_r, patch_s)
                if ncc > best_ncc:
                    best_ncc = ncc
                    best_dy, best_dx = dy, dx
        if best_ncc > 0.3:  # seuil de confiance minimal
            dx_list.append(float(best_dx))
            dy_list.append(float(best_dy))

    if not dx_list:
        return 0.0, 0.0, 0.0, []

    # Médiane robuste
    shift_x_px = float(np.median(dx_list))
    shift_y_px = float(np.median(dy_list))

    # Résidus (distance entre chaque appariement et la médiane)
    residuals_m = [
        math.sqrt((dx - shift_x_px) ** 2 + (dy - shift_y_px) ** 2) * resolution_m
        for dx, dy in zip(dx_list, dy_list, strict=False)
    ]
    rmse = math.sqrt(sum(r**2 for r in residuals_m) / len(residuals_m))

    return shift_x_px * resolution_m, shift_y_px * resolution_m, rmse, residuals_m


def apply_shift(
    path_in: Path,
    path_out: Path,
    shift_x_m: float,
    shift_y_m: float,
) -> None:
    """Applique une translation (shift_x_m, shift_y_m) à un raster et l'écrit.

    La translation est appliquée en modifiant la transformation affine :
    new_transform = old_transform * Affine.translation(shift_x_m, shift_y_m)
    Ce déplace les pixels dans le système de coordonnées d'analyse (mètres, R1).
    """
    with rasterio.open(path_in) as src:
        profile = src.profile.copy()
        data = src.read()
        old_tf = src.transform
        # Décalage de l'origine
        new_tf = rasterio.transform.Affine(
            old_tf.a,
            old_tf.b,
            old_tf.c + shift_x_m,
            old_tf.d,
            old_tf.e,
            old_tf.f + shift_y_m,
        )
        profile.update(transform=new_tf)

    path_out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path_out, "w", **profile) as dst:
        dst.write(data)


def coregister(
    work_aligned_dir: Path,
    reference_layer: str = "hirise_vis",
    layers_to_coreg: tuple[str, ...] = _COREG_LAYERS,
    resolution_m: float = 1.0,
) -> list[CoregResult]:
    """Recale les couches secondaires sur la couche de référence.

    Paramètres
    ----------
    work_aligned_dir : dossier contenant les rasters alignés sur la grille (sortie D1 ingest).
    reference_layer  : identifiant de la couche de référence (en général HiRISE).
    layers_to_coreg  : couches à recaler.
    resolution_m     : résolution de la grille d'analyse en m/px.

    Retourne
    --------
    Liste de ``CoregResult`` par couche.
    Les rasters recalés écrasent les fichiers d'entrée (un backup est conservé dans
    ``<layer_id>.tif.bak``).
    """
    ref_path = work_aligned_dir / f"{reference_layer}.tif"
    results: list[CoregResult] = []

    if not ref_path.exists():
        # Référence absente : pas de recalage possible
        for layer_id in layers_to_coreg:
            results.append(
                CoregResult(
                    layer_id=layer_id,
                    status="skipped",
                    note="Référence HiRISE absente, recalage impossible",
                )
            )
        return results

    # Lire la référence
    with rasterio.open(ref_path) as ref_ds:
        ref_data = ref_ds.read(1).astype(np.float32)
        ref_res = abs(float(ref_ds.transform.a))

    for layer_id in layers_to_coreg:
        sec_path = work_aligned_dir / f"{layer_id}.tif"
        if not sec_path.exists():
            results.append(
                CoregResult(
                    layer_id=layer_id,
                    status="skipped",
                    note="Fichier source absent, recalage sauté",
                )
            )
            continue

        with rasterio.open(sec_path) as sec_ds:
            sec_data = sec_ds.read(1).astype(np.float32)
            # Résolution de la couche secondaire (peut être plus grossière que la réf)
            sec_res = abs(float(sec_ds.transform.a))

        # Sous-échantillonner la référence à la résolution de la couche secondaire
        # pour que la NCC soit calculée à la même échelle
        factor = max(1, round(sec_res / ref_res))
        if factor > 1:
            ref_coarse = scipy.ndimage.zoom(ref_data, 1.0 / factor, order=1).astype(np.float32)
        else:
            ref_coarse = ref_data

        # S'assurer que les dimensions correspondent (recadrage au minimum commun)
        h = min(ref_coarse.shape[0], sec_data.shape[0])
        w = min(ref_coarse.shape[1], sec_data.shape[1])
        ref_crop = ref_coarse[:h, :w]
        sec_crop = sec_data[:h, :w]

        shift_x, shift_y, rmse, tie_residuals = _find_shift_subpixel(
            ref_crop, sec_crop, resolution_m=sec_res
        )

        if abs(shift_x) < 1e-3 and abs(shift_y) < 1e-3:
            results.append(
                CoregResult(
                    layer_id=layer_id,
                    shift_x_m=0.0,
                    shift_y_m=0.0,
                    residual_m=rmse,
                    n_tie_points=len(tie_residuals),
                    status="ok",
                    note="Pas de décalage détecté",
                    tie_point_residuals=tie_residuals,
                )
            )
            continue

        # Appliquer la correction
        backup = sec_path.with_suffix(".tif.bak")
        sec_path.rename(backup)
        apply_shift(backup, sec_path, shift_x, shift_y)

        # Résidu maximal en fraction de pixel de la couche la plus grossière
        max_res_m = max(ref_res, sec_res)
        residual_px = rmse / max_res_m if max_res_m > 0 else rmse

        status = "ok" if residual_px < 1.0 else "degraded"
        note = f"shift ({shift_x:.2f}, {shift_y:.2f}) m; RMSE={rmse:.2f} m ({residual_px:.2f} px)"

        results.append(
            CoregResult(
                layer_id=layer_id,
                shift_x_m=shift_x,
                shift_y_m=shift_y,
                residual_m=rmse,
                n_tie_points=len(tie_residuals),
                status=status,
                note=note,
                tie_point_residuals=tie_residuals,
            )
        )
        print(f"[D1-coreg] {layer_id:25s} {status:9s} {note}")

    return results


def write_coreg_report(
    work_dir: Path,
    ingest_results: Sequence[object],
    coreg_results: list[CoregResult],
    site_id: str,
) -> Path:
    """Écrit ``data/work/<site_id>/coreg_report.md``.

    Format :
    - Résumé de l'ingestion (source, statut, note).
    - Résultats du recalage (décalage, résidu, nombre de points d'appui).
    - Critère de validation : décalage résiduel < 1 pixel de la couche la plus grossière.
    """
    report_path = work_dir / "coreg_report.md"
    lines: list[str] = [
        f"# Rapport de recalage — site `{site_id}`\n",
        "",
        "## 1. Ingestion\n",
        "",
        "| Couche | Source | Statut | Note |",
        "|--------|--------|--------|------|",
    ]
    for r in ingest_results:
        from marswalk_pipeline.ingest import IngestResult

        if isinstance(r, IngestResult):
            lines.append(f"| `{r.layer_id}` | `{r.source_key}` | {r.status} | {r.note} |")

    lines += [
        "",
        "## 2. Recalage\n",
        "",
        "Référence : imagerie HiRISE (`hirise_vis`).",
        "",
        "| Couche | Shift X (m) | Shift Y (m) | RMSE (m) | RMSE (px) | Points | Statut |",
        "|--------|-------------|-------------|----------|-----------|--------|--------|",
    ]
    for r in coreg_results:
        lines.append(
            f"| `{r.layer_id}` | {r.shift_x_m:.2f} | {r.shift_y_m:.2f} | "
            f"{r.residual_m:.2f} | — | {r.n_tie_points} | {r.status} |"
        )

    lines += [
        "",
        "## 3. Validation\n",
        "",
        "- **Critère :** décalage résiduel < 1 pixel de la couche la plus grossière "
        "(THEMIS = 100 m).",
        "- **Validation humaine :** vérifier la superposition dans `qgis/jezero.qgz`.",
        "",
        "### Résidus par point d'appui\n",
    ]
    for r in coreg_results:
        if r.tie_point_residuals:
            vals = ", ".join(f"{v:.1f}" for v in r.tie_point_residuals[:10])
            lines.append(f"- `{r.layer_id}` : {vals} m (affichés max 10 sur {r.n_tie_points})")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[D1] Rapport écrit : {report_path}")
    return report_path
