"""Couche dérivée : ombrage (hillshade)."""

from __future__ import annotations

import numpy as np


def compute_hillshade(
    dem: np.ndarray,
    resolution_m: float,
    sun_azimuth_deg: float,
    sun_altitude_deg: float,
    nodata: float = -9999.0,
) -> np.ndarray:
    """Calcule l'ombrage selon la position du soleil.

    Algorithme standard : normales de surface via gradient, dot product avec vecteur solaire.

    Convention azimut : 0=Nord, 90=Est, 180=Sud, 270=Ouest (convention cartographique).
    sun_altitude_deg : angle d'élévation au-dessus de l'horizon.

    Résultat dans [0, 255] (float32).

    Parameters
    ----------
    dem:
        Tableau 2D float32 élévations en mètres.
    resolution_m:
        Résolution spatiale en mètres par pixel.
    sun_azimuth_deg:
        Azimut solaire en degrés (0=Nord, 90=Est).
    sun_altitude_deg:
        Élévation solaire en degrés.
    nodata:
        Valeur nodata.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 de valeurs d'ombrage dans [0, 255].
    """
    dem = dem.astype(np.float32)
    nodata_mask = np.isclose(dem, nodata, rtol=0, atol=1.0)

    work = dem.copy()
    work[nodata_mask] = np.nan

    # Gradient : dz/dy (axe 0 = lignes), dz/dx (axe 1 = colonnes)
    dz_dy, dz_dx = np.gradient(work, resolution_m)

    # Angle zénithal et azimut en convention mathématique
    zen = np.radians(90.0 - sun_altitude_deg)
    # Convention cartographique → mathématique
    az = np.radians(360.0 - sun_azimuth_deg + 90.0)

    # Vecteur normal de surface normalisé (non unitaire, mais divisé par norme)
    # normal_z = 1 / sqrt(dzdx² + dzdy² + 1)
    # La normale pointe vers le haut (z positif)
    with np.errstate(invalid="ignore"):
        denom = np.sqrt(dz_dx**2 + dz_dy**2 + 1.0)
        normal_z = 1.0 / denom

        # Dot product avec le vecteur solaire
        # Soleil : (sin(zen)*cos(az), sin(zen)*sin(az), cos(zen))
        # Normal surface : (-dzdx/denom, -dzdy/denom, 1/denom)
        hs = (
            np.cos(zen) * normal_z
            + np.sin(zen) * (np.cos(az) * (-dz_dx) + np.sin(az) * (-dz_dy)) * normal_z
        )

        hillshade = (255.0 * np.maximum(0.0, hs)).astype(np.float32)

    # Propager nodata
    nan_mask = nodata_mask | ~np.isfinite(hillshade)
    hillshade[nan_mask] = nodata

    return np.asarray(hillshade, dtype=np.float32)
