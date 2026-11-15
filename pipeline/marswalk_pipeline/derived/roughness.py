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
    """Calcule la rugosité : écart quadratique moyen, dans une fenêtre carrée, du relief
    autour de sa moyenne locale (la pente régionale ne compte pas).

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

    # Calcul en float64 et sur l'écart au relief moyen local : en float32, E[x²] - E[x]²
    # sur des altitudes de l'ordre de -2 500 m perd toute précision (rugosité quantifiée
    # à 0 ou 1 m sur Jezero), et l'écart type brut compte la pente régionale comme de la
    # rugosité (un plan à 10° donne déjà 0,5 m sur 10 m). On retire donc d'abord la
    # moyenne locale (un plan est alors exactement nul), puis on prend l'écart quadratique
    # moyen du résidu dans la fenêtre.
    valid = (~nodata_mask).astype(np.float64)
    ref = float(np.mean(dem[~nodata_mask])) if np.any(~nodata_mask) else 0.0
    work_filled = np.where(nodata_mask, 0.0, dem.astype(np.float64) - ref)

    count = uniform_filter(valid, size=win_px, mode="reflect")
    with np.errstate(invalid="ignore", divide="ignore"):
        local_mean = np.where(
            count > 0, uniform_filter(work_filled, size=win_px, mode="reflect") / count, 0.0
        )
        residual = np.where(nodata_mask, 0.0, work_filled - local_mean)
        mean_r2 = np.where(
            count > 0, uniform_filter(residual**2, size=win_px, mode="reflect") / count, 0.0
        )
        roughness = np.sqrt(np.maximum(mean_r2, 0.0)).astype(np.float32)

    # Propager nodata : un pixel nodata en entrée → nodata en sortie
    # + propager aux voisins (toute fenêtre contenant un nodata → nodata)
    nodata_count = uniform_filter(nodata_mask.astype(np.float32), size=win_px, mode="reflect") * (
        win_px * win_px
    )
    propagated_mask = nodata_mask | (nodata_count > 0)
    roughness[propagated_mask] = nodata

    return np.asarray(roughness, dtype=np.float32)
