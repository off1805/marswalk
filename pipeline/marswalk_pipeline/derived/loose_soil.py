"""Couche dérivée : classes de sol (loose_soil)."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter


def compute_loose_soil(
    thermal_inertia: np.ndarray,
    hirise_vis: np.ndarray,
    nodata: float = -9999.0,
    ti_dune: float = 170.0,
    ti_loose: float = 200.0,
    ti_mixed: float = 270.0,
    texture_window_px: int = 5,
    texture_dune_threshold: float = 5.0,
) -> np.ndarray:
    """Calcule les classes de sol depuis l'inertie thermique et l'imagerie HiRISE.

    Classes : 0=roche, 1=mixte, 2=meuble, 3=dune.

    Algorithme :
    1. texture = écart-type local de hirise_vis sur fenêtre texture_window_px.
    2. Dune (3)   : TI < ti_dune ET texture < texture_dune_threshold.
    3. Meuble (2) : TI < ti_loose (et pas dune).
    4. Mixte (1)  : TI < ti_mixed (et pas meuble ni dune).
    5. Roche (0)  : TI >= ti_mixed.

    Les pixels nodata TI ou nodata hirise_vis → nodata en sortie.

    Parameters
    ----------
    thermal_inertia:
        Tableau 2D float32 d'inertie thermique.
    hirise_vis:
        Tableau 2D float32 d'imagerie HiRISE (valeurs DN).
    nodata:
        Valeur nodata.
    ti_dune:
        Seuil TI pour dune.
    ti_loose:
        Seuil TI pour sol meuble.
    ti_mixed:
        Seuil TI pour sol mixte.
    texture_window_px:
        Taille de la fenêtre de texture en pixels (impaire).
    texture_dune_threshold:
        Seuil de texture pour classification dune.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 avec valeurs 0, 1, 2, 3 ou nodata.
    """
    thermal_inertia = thermal_inertia.astype(np.float32)
    hirise_vis = hirise_vis.astype(np.float32)

    nodata_ti = np.isclose(thermal_inertia, nodata, rtol=0, atol=1.0)
    nodata_hi = np.isclose(hirise_vis, nodata, rtol=0, atol=1.0)
    nodata_mask = nodata_ti | nodata_hi

    # Assurer la fenêtre impaire
    win = texture_window_px
    if win < 1:
        win = 1
    if win % 2 == 0:
        win += 1

    # Calculer texture = écart-type local de hirise_vis
    # Méthode efficace : sqrt(E[x²] - E[x]²)
    hi_filled = np.where(nodata_hi, 0.0, hirise_vis)
    valid_hi = (~nodata_hi).astype(np.float32)

    n = win * win
    sum_x = uniform_filter(hi_filled, size=win, mode="reflect") * n
    sum_x2 = uniform_filter(hi_filled**2, size=win, mode="reflect") * n
    count = uniform_filter(valid_hi, size=win, mode="reflect") * n

    with np.errstate(invalid="ignore", divide="ignore"):
        mean_x = np.where(count > 0, sum_x / count, 0.0)
        mean_x2 = np.where(count > 0, sum_x2 / count, 0.0)
        variance = np.maximum(mean_x2 - mean_x**2, 0.0)
        texture = np.sqrt(variance).astype(np.float32)

    # Classification
    result = np.zeros(thermal_inertia.shape, dtype=np.float32)

    # Roche (0) : TI >= ti_mixed — c'est la valeur par défaut 0
    # Mixte (1) : TI < ti_mixed
    result[thermal_inertia < ti_mixed] = 1.0
    # Meuble (2) : TI < ti_loose
    result[thermal_inertia < ti_loose] = 2.0
    # Dune (3) : TI < ti_dune ET texture faible
    dune_mask = (thermal_inertia < ti_dune) & (texture < texture_dune_threshold)
    result[dune_mask] = 3.0

    result[nodata_mask] = nodata

    return result
