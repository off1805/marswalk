"""Couche dérivée : rugosité (roughness)."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter


def compute_roughness(
    dem: np.ndarray,
    window_m: float,
    resolution_m: float,
    nodata: float = -9999.0,
) -> np.ndarray:
    """Calcule la rugosité comme l'écart-type local par fenêtre glissante carrée.

    Algorithme efficace : sqrt(E[x²] - E[x]²) via uniform_filter.
    Les pixels nodata en entrée → nodata en sortie, et propagation aux voisins.

    Parameters
    ----------
    dem:
        Tableau 2D float32 élévations en mètres.
    window_m:
        Taille de la fenêtre en mètres.
    resolution_m:
        Résolution spatiale en mètres par pixel.
    nodata:
        Valeur nodata.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 de rugosité en mètres.
    """
    dem = dem.astype(np.float32)
    nodata_mask = np.isclose(dem, nodata, rtol=0, atol=1.0)

    # Taille de fenêtre en pixels, impaire
    win_px = round(window_m / resolution_m)
    if win_px < 1:
        win_px = 1
    if win_px % 2 == 0:
        win_px += 1

    # Travailler avec une copie en remplaçant nodata par nan
    work = dem.copy()
    work[nodata_mask] = np.nan

    # Approche : mask-based E[x] et E[x²]
    # On remplace nan par 0 et on utilise un masque de comptage
    valid = (~nodata_mask).astype(np.float32)
    work_filled = np.where(nodata_mask, 0.0, work)

    # Somme de x et x² dans la fenêtre, et nombre de valides
    sum_x = uniform_filter(work_filled, size=win_px, mode="reflect") * (win_px * win_px)
    sum_x2 = uniform_filter(work_filled**2, size=win_px, mode="reflect") * (win_px * win_px)
    count = uniform_filter(valid, size=win_px, mode="reflect") * (win_px * win_px)

    # Éviter division par zéro
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_x = np.where(count > 0, sum_x / count, 0.0)
        mean_x2 = np.where(count > 0, sum_x2 / count, 0.0)
        variance = mean_x2 - mean_x**2
        # Clamp numérique pour éviter sqrt de valeurs négatives minuscules
        variance = np.maximum(variance, 0.0)
        roughness = np.sqrt(variance).astype(np.float32)

    # Propager nodata : un pixel nodata en entrée → nodata en sortie
    # + propager aux voisins (toute fenêtre contenant un nodata → nodata)
    nodata_count = uniform_filter(nodata_mask.astype(np.float32), size=win_px, mode="reflect") * (
        win_px * win_px
    )
    propagated_mask = nodata_mask | (nodata_count > 0)
    roughness[propagated_mask] = nodata

    return roughness
