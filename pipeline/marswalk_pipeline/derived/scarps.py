"""Couche dérivée : ruptures de pente (scarps)."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation


def _make_disk(radius_px: float) -> np.ndarray:
    """Crée un élément structurant disque de rayon radius_px."""
    r = int(np.ceil(radius_px))
    y, x = np.ogrid[-r : r + 1, -r : r + 1]
    disk = (x**2 + y**2) <= radius_px**2
    return disk


def compute_scarps(
    slope: np.ndarray,
    threshold_deg: float,
    buffer_m: float,
    resolution_m: float,
    nodata: float = -9999.0,
) -> np.ndarray:
    """Calcule la couche de ruptures de pente (binaire) depuis la pente.

    1. Seuillage : slope > threshold_deg → 1.
    2. Dilatation avec un disque de rayon buffer_m / resolution_m.
    3. Les pixels nodata de slope → nodata en sortie.

    Parameters
    ----------
    slope:
        Tableau 2D float32 de pentes en degrés.
    threshold_deg:
        Seuil de pente en degrés.
    buffer_m:
        Rayon du tampon en mètres.
    resolution_m:
        Résolution spatiale en mètres par pixel.
    nodata:
        Valeur nodata.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 : 0.0 (aucune falaise), 1.0 (falaise/bord), nodata.
    """
    slope = slope.astype(np.float32)
    nodata_mask = np.isclose(slope, nodata, rtol=0, atol=1.0)

    scarp = np.zeros(slope.shape, dtype=bool)
    valid = ~nodata_mask
    scarp[valid] = slope[valid] > threshold_deg

    if buffer_m > 0:
        radius_px = buffer_m / resolution_m
        struct = _make_disk(radius_px)
        scarp = binary_dilation(scarp, structure=struct)

    result = scarp.astype(np.float32)
    result[nodata_mask] = nodata

    return result
