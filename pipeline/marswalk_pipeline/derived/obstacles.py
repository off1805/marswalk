"""Couche dérivée : obstacles."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_dilation


def _make_disk(radius_px: float) -> np.ndarray:
    """Crée un élément structurant disque de rayon radius_px."""
    r = int(np.ceil(radius_px))
    size = 2 * r + 1
    y, x = np.ogrid[-r : r + 1, -r : r + 1]
    disk = (x**2 + y**2) <= radius_px**2
    return disk


def compute_obstacles(
    roughness: np.ndarray,
    threshold_m: float,
    buffer_m: float,
    resolution_m: float,
    nodata: float = -9999.0,
) -> np.ndarray:
    """Calcule la couche d'obstacles (binaire) depuis la rugosité.

    1. Seuillage : roughness > threshold_m → 1, sinon 0.
    2. Dilatation avec un disque de rayon buffer_m / resolution_m.
    3. Les pixels nodata de roughness → nodata en sortie.

    Parameters
    ----------
    roughness:
        Tableau 2D float32 de rugosité.
    threshold_m:
        Seuil de rugosité en mètres.
    buffer_m:
        Rayon du tampon en mètres.
    resolution_m:
        Résolution spatiale en mètres par pixel.
    nodata:
        Valeur nodata.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 : 0.0 (libre), 1.0 (obstacle), nodata.
    """
    roughness = roughness.astype(np.float32)
    nodata_mask = np.isclose(roughness, nodata, rtol=0, atol=1.0)

    # Seuillage sur les pixels valides
    obstacle = np.zeros(roughness.shape, dtype=bool)
    valid = ~nodata_mask
    obstacle[valid] = roughness[valid] > threshold_m

    # Dilatation
    if buffer_m > 0:
        radius_px = buffer_m / resolution_m
        struct = _make_disk(radius_px)
        obstacle = binary_dilation(obstacle, structure=struct)

    result = obstacle.astype(np.float32)
    result[nodata_mask] = nodata

    return result
