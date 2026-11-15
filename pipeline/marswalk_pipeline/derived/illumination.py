"""Couche dérivée : éclairement solaire (shadow casting vectorisé)."""

from __future__ import annotations

import numpy as np


def compute_illumination(
    dem: np.ndarray,
    resolution_m: float,
    sun_azimuth_deg: float,
    sun_altitude_deg: float,
    nodata: float = -9999.0,
) -> np.ndarray:
    """Calcule l'éclairement par ray-casting vectorisé.

    Algorithme : élévation normalisée.

    Pour chaque rayon parallèle à la direction solaire, on calcule :
      norm_elev(c) = dem(c) + sun_slope * dist_from_sunny_edge(c)

    Un pixel est en ombre si norm_elev(c) < max(norm_elev(c')) pour tout c' entre c
    et le bord ensoleillé.

    On scanne FROM le bord ensoleillé vers le bord ombragé, en maintenant le maximum
    de norm_elev rencontré. Un pixel est en ombre si sa norm_elev < max courant.

    Parameters
    ----------
    dem:
        Tableau 2D float32 élévations en mètres.
    resolution_m:
        Résolution spatiale en mètres par pixel.
    sun_azimuth_deg:
        Azimut solaire (0=Nord, 90=Est, convention cartographique).
    sun_altitude_deg:
        Élévation solaire en degrés.
    nodata:
        Valeur nodata.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 : 0.0 (ombre), 1.0 (éclairé).
    """
    dem = dem.astype(np.float32)
    nodata_mask = np.isclose(dem, nodata, rtol=0, atol=1.0)
    rows, cols = dem.shape

    sun_slope = float(np.tan(np.radians(max(float(sun_altitude_deg), 0.001))))

    az_rad = np.radians(float(sun_azimuth_deg))
    # Direction du soleil (d'où vient la lumière) en coords image
    # Azimut 0=Nord, 90=Est => vecteur "depuis soleil" : col = sin(az), row = -cos(az)
    sun_dc = float(np.sin(az_rad))   # col : est = positif
    sun_dr = float(-np.cos(az_rad))  # row : nord = négatif (row 0 = haut)

    result = np.ones((rows, cols), dtype=np.float32)

    abs_dc = abs(sun_dc)
    abs_dr = abs(sun_dr)
    dem_d = dem.astype(np.float64)

    if abs_dc >= abs_dr:
        # Axe principal : colonnes.
        if abs_dc < 1e-9:
            result[nodata_mask] = nodata
            return result

        step_row = sun_dr / abs_dc  # déplacement en ligne pour 1 pas en colonne
        step_m = resolution_m * float(np.sqrt(1.0 + step_row**2))

        # On scanne depuis le bord ensoleillé vers l'ombre.
        # Le bord ensoleillé est celui d'où vient la lumière.
        # sun_dc > 0 : soleil est à l'est → le bord EST (col=cols-1) est ensoleillé
        #   → on scanne de droite à gauche (de cols-1 vers 0)
        # sun_dc < 0 : soleil est à l'ouest → le bord OUEST (col=0) est ensoleillé
        #   → on scanne de gauche à droite (de 0 vers cols-1)
        if sun_dc > 0:
            col_order = range(cols - 1, -1, -1)
        else:
            col_order = range(cols)

        # max_norm[r] = max de norm_elev pour les pixels précédents du rayon
        # norm_elev = elev + sun_slope * dist_from_start
        max_norm = np.full(rows, -np.inf, dtype=np.float64)

        for step, ci in enumerate(col_order):
            dist_m = step * step_m  # distance depuis le bord ensoleillé

            col_dem = dem_d[:, ci]
            col_nd = nodata_mask[:, ci]

            # Chaque rayon à la ligne ri vient du pixel (ri - step_row, ci_prev)
            # On interpole max_norm à la position (ri - step_row)
            ri_prev = np.arange(rows, dtype=np.float64) - step_row
            ri_prev_lo = np.floor(ri_prev).astype(np.int32)
            ri_prev_hi = ri_prev_lo + 1
            frac = ri_prev - ri_prev_lo

            valid_lo = (ri_prev_lo >= 0) & (ri_prev_lo < rows)
            valid_hi = (ri_prev_hi >= 0) & (ri_prev_hi < rows)

            h_lo = np.where(valid_lo, max_norm[np.clip(ri_prev_lo, 0, rows - 1)], -np.inf)
            h_hi = np.where(valid_hi, max_norm[np.clip(ri_prev_hi, 0, rows - 1)], -np.inf)

            both_valid = (h_lo > -np.inf) & (h_hi > -np.inf)
            lo_only = (h_lo > -np.inf) & (h_hi <= -np.inf)
            hi_only = (h_lo <= -np.inf) & (h_hi > -np.inf)

            prev_max = np.full(rows, -np.inf, dtype=np.float64)
            prev_max[both_valid] = h_lo[both_valid] * (1.0 - frac[both_valid]) + h_hi[both_valid] * frac[both_valid]
            prev_max[lo_only] = h_lo[lo_only]
            prev_max[hi_only] = h_hi[hi_only]

            elev = col_dem
            norm_elev = elev + sun_slope * dist_m
            valid_px = ~col_nd
            has_prev = prev_max > -np.inf

            # En ombre : norm_elev < prev_max (un obstacle plus proche bloque le rayon)
            case_shadow = valid_px & has_prev & (norm_elev < prev_max)
            result[case_shadow, ci] = 0.0

            # Mettre à jour max_norm : max(prev_max, norm_elev) pour pixels valides
            new_max = np.where(valid_px, np.maximum(prev_max, norm_elev), prev_max)
            # Pour le premier pixel (prev_max=-inf), initialiser avec norm_elev
            new_max = np.where(valid_px & ~has_prev, norm_elev, new_max)
            max_norm = new_max

    else:
        # Axe principal : lignes
        if abs_dr < 1e-9:
            result[nodata_mask] = nodata
            return result

        step_col = sun_dc / abs_dr
        step_m = resolution_m * float(np.sqrt(1.0 + step_col**2))

        # sun_dr > 0 : soleil est au sud (bas) → le bord SUD (row=rows-1) est ensoleillé
        #   → scan bottom to top (rows-1 to 0)
        # sun_dr < 0 : soleil est au nord (haut) → le bord NORD (row=0) est ensoleillé
        #   → scan top to bottom (0 to rows-1)
        if sun_dr > 0:
            row_order = range(rows - 1, -1, -1)
        else:
            row_order = range(rows)

        max_norm = np.full(cols, -np.inf, dtype=np.float64)

        for step, ri in enumerate(row_order):
            dist_m = step * step_m

            row_dem = dem_d[ri, :]
            row_nd = nodata_mask[ri, :]

            ci_prev = np.arange(cols, dtype=np.float64) - step_col
            ci_prev_lo = np.floor(ci_prev).astype(np.int32)
            ci_prev_hi = ci_prev_lo + 1
            frac = ci_prev - ci_prev_lo

            valid_lo = (ci_prev_lo >= 0) & (ci_prev_lo < cols)
            valid_hi = (ci_prev_hi >= 0) & (ci_prev_hi < cols)

            h_lo = np.where(valid_lo, max_norm[np.clip(ci_prev_lo, 0, cols - 1)], -np.inf)
            h_hi = np.where(valid_hi, max_norm[np.clip(ci_prev_hi, 0, cols - 1)], -np.inf)

            both_valid = (h_lo > -np.inf) & (h_hi > -np.inf)
            lo_only = (h_lo > -np.inf) & (h_hi <= -np.inf)
            hi_only = (h_lo <= -np.inf) & (h_hi > -np.inf)

            prev_max = np.full(cols, -np.inf, dtype=np.float64)
            prev_max[both_valid] = h_lo[both_valid] * (1.0 - frac[both_valid]) + h_hi[both_valid] * frac[both_valid]
            prev_max[lo_only] = h_lo[lo_only]
            prev_max[hi_only] = h_hi[hi_only]

            elev = row_dem
            norm_elev = elev + sun_slope * dist_m
            valid_px = ~row_nd
            has_prev = prev_max > -np.inf

            case_shadow = valid_px & has_prev & (norm_elev < prev_max)
            result[ri, case_shadow] = 0.0

            new_max = np.where(valid_px, np.maximum(prev_max, norm_elev), prev_max)
            new_max = np.where(valid_px & ~has_prev, norm_elev, new_max)
            max_norm = new_max

    result[nodata_mask] = nodata
    return result
