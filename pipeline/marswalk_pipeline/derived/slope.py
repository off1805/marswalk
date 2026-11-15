"""Couche dérivée : pente (slope)."""

from __future__ import annotations

import numpy as np


def compute_slope(
    dem: np.ndarray,
    resolution_m: float,
    nodata: float = -9999.0,
) -> np.ndarray:
    """Calcule la pente en degrés depuis un DEM.

    Algorithme : gradient central (np.gradient), arctan du module du gradient.
    Les pixels nodata en entrée → nodata en sortie.
    Résultat dans [0, 90].

    Parameters
    ----------
    dem:
        Tableau 2D float32 élévations en mètres.
    resolution_m:
        Résolution spatiale en mètres par pixel.
    nodata:
        Valeur nodata.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 de pentes en degrés.
    """
    dem = dem.astype(np.float32)
    nodata_mask = np.isclose(dem, nodata, rtol=0, atol=1.0)

    # Remplacer nodata par nan pour que le gradient l'ignore aux bords
    work = dem.copy()
    work[nodata_mask] = np.nan

    # np.gradient : axe 0 = ligne (Y, Nord-Sud), axe 1 = colonne (X, Est-Ouest)
    # Les pixels nan propagent nan aux voisins via le gradient
    dz_dy, dz_dx = np.gradient(work, resolution_m)

    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
    slope_deg = np.degrees(slope_rad).astype(np.float32)

    # Propager nodata : tout pixel nan dans le gradient ou dans dem → nodata
    nan_mask = nodata_mask | ~np.isfinite(slope_deg)
    slope_deg[nan_mask] = nodata

    return np.asarray(slope_deg, dtype=np.float32)
