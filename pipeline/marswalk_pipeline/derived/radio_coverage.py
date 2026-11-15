"""Couche dérivée : couverture radio (viewshed radial scan vectorisé)."""

from __future__ import annotations

import numpy as np


def compute_radio_coverage(
    dem: np.ndarray,
    habitat_px: tuple[int, int],
    antenna_height_m: float,
    resolution_m: float,
    nodata: float = -9999.0,
    n_angles: int | None = None,
    observer_eye_height_m: float = 1.8,
) -> np.ndarray:
    """Calcule le viewshed depuis l'habitat par balayage angulaire (R2V).

    Pour chaque direction angulaire, marche pixel par pixel depuis l'habitat
    en maintenant l'angle d'élévation max vu. Un pixel est visible si son
    angle d'élévation ≥ angle max au moment de son passage.

    Cette implémentation vectorise le balayage de chaque rayon en travaillant
    sur tous les pas d'un rayon à la fois.

    Parameters
    ----------
    dem:
        Tableau 2D float32 élévations en mètres.
    habitat_px:
        Position de l'habitat (row, col).
    antenna_height_m:
        Hauteur de l'antenne en mètres.
    resolution_m:
        Résolution spatiale en mètres par pixel.
    nodata:
        Valeur nodata.
    n_angles:
        Nombre de directions angulaires.
    observer_eye_height_m:
        Hauteur des yeux de l'observateur cible.

    Returns
    -------
    np.ndarray
        Tableau 2D float32 : 0.0 (hors vue), 1.0 (visible).
    """
    dem = dem.astype(np.float32)
    nodata_mask = np.isclose(dem, nodata, rtol=0, atol=1.0)
    rows, cols = dem.shape

    hab_r, hab_c = int(habitat_px[0]), int(habitat_px[1])

    # Vérifier que l'habitat est dans la grille
    if not (0 <= hab_r < rows and 0 <= hab_c < cols):
        result = np.zeros((rows, cols), dtype=np.float32)
        result[nodata_mask] = nodata
        return result

    if nodata_mask[hab_r, hab_c]:
        result = np.full(dem.shape, nodata, dtype=np.float32)
        return result

    hab_elev = float(dem[hab_r, hab_c]) + antenna_height_m

    # Tableau de visibilité
    visible = np.zeros((rows, cols), dtype=np.float32)
    visible[hab_r, hab_c] = 1.0

    # Nombre maximal de pas
    max_dist = int(np.ceil(np.sqrt(rows**2 + cols**2))) + 2

    # Directions angulaires : assez de rayons pour qu'à la distance maximale deux rayons
    # voisins restent à moins d'un pixel l'un de l'autre (sinon la couverture est mitée).
    if n_angles is None:
        n_angles = max(360, int(np.ceil(2.0 * np.pi * max_dist)))
    angles = np.linspace(0.0, 2.0 * np.pi, n_angles, endpoint=False)
    sin_a = np.sin(angles)
    cos_a = np.cos(angles)

    # On traite tous les angles en parallèle pour chaque "distance"
    # À chaque pas, on a n_angles positions, et on met à jour le max_angle

    max_elev_angle = np.full(n_angles, -np.inf, dtype=np.float64)

    dem_d = dem.astype(np.float64)

    for step in range(1, max_dist):
        dist_m = step * resolution_m

        # Positions fractionnaires pour tous les angles
        r_frac = hab_r + (-cos_a) * step  # -cos pour convention Nord (row décroissante)
        c_frac = hab_c + sin_a * step

        r_int = np.round(r_frac).astype(np.int32)
        c_int = np.round(c_frac).astype(np.int32)

        # Masque des positions dans la grille
        in_bounds = (r_int >= 0) & (r_int < rows) & (c_int >= 0) & (c_int < cols)

        # Si plus aucun rayon est dans la grille, on peut arrêter
        if not np.any(in_bounds):
            break

        # Récupérer les élévations (clamp pour éviter les accès hors grille)
        r_safe = np.clip(r_int, 0, rows - 1)
        c_safe = np.clip(c_int, 0, cols - 1)
        elevs = dem_d[r_safe, c_safe]  # (n_angles,)
        is_nd = nodata_mask[r_safe, c_safe]

        # Angle d'élévation vu depuis l'habitat
        target_elev = elevs + observer_eye_height_m
        elev_angle = (target_elev - hab_elev) / dist_m

        # Un pixel est visible si son angle ≥ max_angle actuel ET dans la grille ET non nodata
        is_visible = in_bounds & ~is_nd & (elev_angle >= max_elev_angle)

        # Mettre à jour les pixels visibles
        # Dédupliquer les pixels (plusieurs angles peuvent pointer sur le même pixel)
        vis_r = r_int[is_visible]
        vis_c = c_int[is_visible]
        if len(vis_r) > 0:
            visible[vis_r, vis_c] = 1.0

        # Mettre à jour max_elev_angle (que pour les rayons dans la grille et non-nodata)
        # L'horizon se calcule sur le sol, pas sur la tête de l'observateur.
        active = in_bounds & ~is_nd
        ground_angle = (elevs - hab_elev) / dist_m
        max_elev_angle = np.where(active, np.maximum(max_elev_angle, ground_angle), max_elev_angle)

    visible[nodata_mask] = nodata
    return visible
