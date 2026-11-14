"""Couches dérivées du MNT et des couches source (D2).

Commande : ``marswalk derive <site_id>``

Produit : slope, roughness, hillshade, obstacles, scarps, loose_soil,
          radio_coverage, illumination en COG Float32 (nodata -9999).

Toutes les couches sont calculées en coordonnées du système d'analyse du site
(règle R1 : mètres, +proj=eqc). Les COG sont écrits dans
``data/work/<site_id>/derived/<layer_id>.tif`` ; pour le site fictif, les
fichiers sont écrits directement dans ``fixtures/sites/fictif/cog/``.

Paramètres : lus dans ``config/sites/<site_id>/site.yaml``.
"""

from __future__ import annotations

import contextlib
import math
from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
import rasterio.transform
import scipy.ndimage

from marswalk_core.config import load_site_config
from marswalk_core.site_package import Site, open_package

NODATA: float = -9999.0


# ---------------------------------------------------------------------------
# Utilitaires raster
# ---------------------------------------------------------------------------


def _write_cog(path: Path, data: np.ndarray, transform: tuple[float, ...], crs: str) -> None:
    """Écrit un COG Float32 simple bande."""
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = data.shape
    out = data.copy().astype(np.float32)
    out[np.isnan(out)] = NODATA
    affine = rasterio.transform.Affine(
        transform[0],
        transform[1],
        transform[2],
        transform[3],
        transform[4],
        transform[5],
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float32",
        crs=crs,
        transform=affine,
        nodata=NODATA,
    ) as ds:
        ds.write(out, 1)


def _load_layer(site: Site, layer_id: str) -> np.ndarray | None:
    """Charge une couche COG en ndarray Float32, NaN là où nodata. None si absente."""
    if not site.has_layer(layer_id):
        return None
    return site.read_layer(layer_id).values.astype(np.float32)


# ---------------------------------------------------------------------------
# slope — pente en degrés (R1 : calcul en mètres)
# ---------------------------------------------------------------------------


def compute_slope(dem: np.ndarray, resolution_m: float) -> np.ndarray:
    """Pente en degrés à partir du MNT.

    Formule classique à différences finies centrées (Zevenbergen & Thorne 1987) :
      p = dz/dx = (z[i, j+1] - z[i, j-1]) / (2 × res)
      q = dz/dy = (z[i-1, j] - z[i+1, j]) / (2 × res)
      slope_rad = atan(sqrt(p² + q²))
    Les bords sont calculés par différences unilatérales.
    """
    dem_f = dem.astype(np.float64)
    nan_mask = np.isnan(dem_f)
    dem_filled = np.where(nan_mask, 0.0, dem_f)

    dzdx = np.gradient(dem_filled, resolution_m, axis=1)
    dzdy = np.gradient(dem_filled, resolution_m, axis=0)

    slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
    slope_deg = np.degrees(slope_rad).astype(np.float32)
    slope_deg[nan_mask] = np.nan
    return np.asarray(slope_deg, dtype=np.float32)


# ---------------------------------------------------------------------------
# roughness — écart type local du MNT (R1 : fenêtre en mètres)
# ---------------------------------------------------------------------------


def compute_roughness(dem: np.ndarray, resolution_m: float, window_m: float = 10.0) -> np.ndarray:
    """Rugosité = écart type local du MNT sur une fenêtre glissante de window_m.

    Paramètre window_m : taille de la fenêtre en mètres (défaut 10 m).
    Résolution en mètres pour convertir.
    """
    radius = max(1, round(window_m / resolution_m / 2))
    size = 2 * radius + 1
    nan_mask = np.isnan(dem)
    dem_f = dem.astype(np.float64)
    filled = np.where(nan_mask, 0.0, dem_f)

    kernel = np.ones((size, size), dtype=np.float64)
    n = size * size

    # mean = Σ(x) / n, var = Σ(x²)/n - mean²
    sum1 = scipy.ndimage.uniform_filter(filled, size=size, mode="reflect")
    sum2 = scipy.ndimage.uniform_filter(filled**2, size=size, mode="reflect")
    var = np.maximum(0.0, sum2 - sum1**2)
    roughness = np.sqrt(var).astype(np.float32)
    roughness[nan_mask] = np.nan
    del kernel, n  # silence unused
    return np.asarray(roughness, dtype=np.float32)


# ---------------------------------------------------------------------------
# hillshade — ombrage (azimut 315°, hauteur 45°)
# ---------------------------------------------------------------------------


def compute_hillshade(
    dem: np.ndarray,
    resolution_m: float,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
) -> np.ndarray:
    """Ombrage [0, 255] calculé selon ESRI/GDAL.

    Formule : hillshade = 255 × (cos(zen_light) × cos(normal_zen)
              + sin(zen_light) × sin(normal_zen) × cos(azimuth_light − aspect))
    """
    nan_mask = np.isnan(dem)
    dem_f = dem.astype(np.float64)
    filled = np.where(nan_mask, 0.0, dem_f)

    dzdx = np.gradient(filled, resolution_m, axis=1)
    dzdy = np.gradient(filled, resolution_m, axis=0)

    # Pente de la normale
    slope_rad = np.arctan(np.sqrt(dzdx**2 + dzdy**2))
    # Aspect (direction de la pente)
    aspect_rad = np.arctan2(-dzdy, dzdx)

    az_rad = math.radians(360.0 - azimuth_deg + 90.0)
    zen_light = math.radians(90.0 - altitude_deg)

    hs = math.cos(zen_light) * np.cos(slope_rad) + math.sin(zen_light) * np.sin(slope_rad) * np.cos(
        az_rad - aspect_rad
    )
    hs = np.clip(hs * 255.0, 0, 255).astype(np.float32)
    hs[nan_mask] = np.nan
    return np.asarray(hs, dtype=np.float32)


# ---------------------------------------------------------------------------
# obstacles — masque de blocs avec tampon
# ---------------------------------------------------------------------------


def compute_obstacles(
    roughness: np.ndarray,
    resolution_m: float,
    roughness_threshold_m: float = 0.4,
    buffer_m: float = 2.0,
) -> np.ndarray:
    """Masque binaire d'obstacles (blocs >roughness_threshold_m) avec tampon buffer_m.

    Renvoie 1.0 sur obstacle + zone tampon, 0.0 ailleurs.
    """
    nan_mask = np.isnan(roughness)
    mask = np.where(nan_mask, False, roughness > roughness_threshold_m)
    # Tampon par dilatation morphologique
    radius_cells = max(1, math.ceil(buffer_m / resolution_m))
    struct = np.ones((2 * radius_cells + 1, 2 * radius_cells + 1), dtype=bool)
    dilated = scipy.ndimage.binary_dilation(mask, structure=struct)
    result = np.asarray(dilated, dtype=np.float32)
    result[nan_mask] = np.nan
    return result


# ---------------------------------------------------------------------------
# scarps
# scarps — ruptures de pente / bords de falaise
# ---------------------------------------------------------------------------


def compute_scarps(
    slope: np.ndarray,
    resolution_m: float,
    scarp_threshold_deg: float = 30.0,
    buffer_m: float = 10.0,
) -> np.ndarray:
    """Masque binaire des ruptures de pente (pente > scarp_threshold_deg) + tampon.

    Renvoie 1.0 sur falaise + tampon, 0.0 ailleurs.
    """
    nan_mask = np.isnan(slope)
    steep = np.where(nan_mask, False, slope > scarp_threshold_deg)
    radius_cells = max(1, math.ceil(buffer_m / resolution_m))
    struct = np.ones((2 * radius_cells + 1, 2 * radius_cells + 1), dtype=bool)
    dilated = scipy.ndimage.binary_dilation(steep, structure=struct)
    result = np.asarray(dilated, dtype=np.float32)
    result[nan_mask] = np.nan
    return result


# ---------------------------------------------------------------------------
# loose_soil — classe de sol (inertie thermique + pente)
# ---------------------------------------------------------------------------


def compute_loose_soil(
    thermal_inertia: np.ndarray | None,
    slope: np.ndarray,
    resolution_m: float,
    dune_ti_max: float = 200.0,
    loose_ti_max: float = 350.0,
    dune_slope_max_deg: float = 15.0,
) -> np.ndarray:
    """Classe de sol : 0 roche, 1 mixte, 2 meuble, 3 dune.

    Heuristique combinant inertie thermique (TI) et pente :
    - TI faible (<dune_ti_max) ET pente douce (<dune_slope_max_deg) → dune (3)
    - TI faible (<dune_ti_max) ET pente quelconque → meuble (2)
    - TI modérée (<loose_ti_max) → mixte (1)
    - TI élevée → roche (0)
    Si TI absente : classification par pente uniquement (meuble sur pentes douces).
    """
    nan_mask = np.isnan(slope)
    soil = np.zeros(slope.shape, dtype=np.float32)

    if thermal_inertia is not None:
        ti = np.where(np.isnan(thermal_inertia), loose_ti_max, thermal_inertia)
        # Roche par défaut (class 0 déjà)
        # Mixte
        soil = np.where((ti < loose_ti_max) & (ti >= dune_ti_max), 1.0, soil)
        # Meuble (TI < dune_ti_max, pente quelconque)
        soil = np.where(ti < dune_ti_max, 2.0, soil)
        # Dune (TI très faible ET pente douce)
        dune_mask = (ti < dune_ti_max) & (np.nan_to_num(slope) < dune_slope_max_deg)
        soil = np.where(dune_mask, 3.0, soil)
    else:
        # Sans TI : mixte partout, meuble sur pentes douces
        soil[:] = 1.0
        soil = np.where(np.nan_to_num(slope) < dune_slope_max_deg, 2.0, soil)

    soil[nan_mask] = np.nan
    return soil.astype(np.float32)


# ---------------------------------------------------------------------------
# radio_coverage — visibilité LOS depuis l'habitat
# ---------------------------------------------------------------------------


def compute_radio_coverage(
    dem: np.ndarray,
    resolution_m: float,
    habitat_rc: tuple[int, int],
    antenna_height_m: float = 3.0,
) -> np.ndarray:
    """Visibilité radio (line-of-sight) depuis l'habitat vers chaque case.

    Algorithme de lancer de rayons simple (Bresenham) : pour chaque case,
    trace le segment vers l'habitat et vérifie qu'aucun pixel intermédiaire
    n'est plus haut que la ligne de vue.

    Renvoie 1.0 si visible, 0.0 sinon (NaN là où le MNT est NaN).
    """
    h_row, h_col = habitat_rc
    height, width = dem.shape
    nan_mask = np.isnan(dem)
    dem_f = np.where(nan_mask, -9999.0, dem.astype(np.float64))
    hab_elev = dem_f[h_row, h_col] + antenna_height_m

    visible = np.zeros((height, width), dtype=np.float32)

    for row in range(height):
        for col in range(width):
            if nan_mask[row, col]:
                visible[row, col] = np.nan
                continue
            if row == h_row and col == h_col:
                visible[row, col] = 1.0
                continue
            target_elev = dem_f[row, col] + antenna_height_m
            dist_cells = math.sqrt((row - h_row) ** 2 + (col - h_col) ** 2)
            # Échantillonnage le long de la ligne de vue (Bresenham simplifié)
            n = max(1, int(dist_cells * 2))
            los_ok = True
            for k in range(1, n):
                t = k / n
                r = round(h_row + t * (row - h_row))
                c = round(h_col + t * (col - h_col))
                r = max(0, min(height - 1, r))
                c = max(0, min(width - 1, c))
                elev_path = dem_f[r, c]
                # Hauteur attendue de la ligne de vue à cette fraction
                los_height = hab_elev + t * (target_elev - hab_elev)
                if elev_path > los_height:
                    los_ok = False
                    break
            visible[row, col] = 1.0 if los_ok else 0.0

    return visible


def _compute_radio_coverage_fast(
    dem: np.ndarray,
    resolution_m: float,
    habitat_rc: tuple[int, int],
    antenna_height_m: float = 3.0,
) -> np.ndarray:
    """Variante vectorisée de compute_radio_coverage pour les grandes grilles.

    Pour chaque case, compare la hauteur max du profil d'élévation interpolé
    à la ligne de vue. Utilise scipy.ndimage.map_coordinates.
    """
    h_row, h_col = habitat_rc
    height, width = dem.shape
    nan_mask = np.isnan(dem)
    dem_f = np.where(nan_mask, np.nanmin(dem) - 1.0, dem.astype(np.float64))
    hab_elev = float(dem_f[h_row, h_col]) + antenna_height_m

    rows_idx = np.arange(height)
    cols_idx = np.arange(width)
    rr, cc = np.meshgrid(rows_idx, cols_idx, indexing="ij")

    n_steps = 32  # échantillons le long du rayon
    visible = np.ones((height, width), dtype=bool)

    for k in range(1, n_steps):
        t = k / n_steps
        r_sample = h_row + t * (rr - h_row)
        c_sample = h_col + t * (cc - h_col)
        # Élévation interpolée du terrain à cet instant
        coords = np.array([r_sample.ravel(), c_sample.ravel()])
        elev_path = scipy.ndimage.map_coordinates(dem_f, coords, order=1, mode="nearest")
        elev_path = elev_path.reshape(height, width)
        # Élévation attendue de la ligne de vue
        target_elev = dem_f + antenna_height_m
        los_height = hab_elev + t * (target_elev - hab_elev)
        blocked = elev_path > los_height
        visible &= ~blocked

    result = visible.astype(np.float32)
    result[nan_mask] = np.nan
    return result


# ---------------------------------------------------------------------------
# illumination — fraction éclairée (ombres portées à une heure solaire donnée)
# ---------------------------------------------------------------------------


def compute_illumination(
    dem: np.ndarray,
    resolution_m: float,
    azimuth_deg: float = 90.0,
    altitude_deg: float = 20.0,
) -> np.ndarray:
    """Fraction d'éclairement solaire [0, 1] par algorithme d'horizon projeté.

    Pour chaque colonne de la grille projetée dans la direction du Soleil,
    parcourt les cases dans l'ordre croissant de distance au Soleil et
    maintient l'élévation maximale vue depuis le Soleil (horizon courant).
    Une case est à l'ombre si le terrain en amont dépasse la ligne de vue.

    azimuth_deg : azimut solaire (est = 90°, ouest = 270°, convention nord = 0°).
    altitude_deg : hauteur angulaire du Soleil.

    Complexité : O(H × W) — une seule passe par case.
    """
    nan_mask = np.isnan(dem)
    dem_min = float(np.nanmin(dem)) - 1.0
    dem_f = np.where(nan_mask, dem_min, dem.astype(np.float64))

    az_rad = math.radians(azimuth_deg)
    alt_rad = math.radians(altitude_deg)
    tan_alt = math.tan(alt_rad)

    # Direction de la lumière (vecteur unitaire en case)
    # Soleil à azimut az → lumière vient de cette direction
    # dc = sin(az), dr = -cos(az)  (est = col+)
    dc = math.sin(az_rad)
    dr = -math.cos(az_rad)

    height, width = dem.shape

    # Algorithme : on balaie la grille dans la direction *opposée* au Soleil
    # (depuis le côté d'arrivée de la lumière vers l'intérieur).
    # Pour chaque case, l'horizon est le maximum de dem[j] - dist_j * tan_alt
    # parmi tous les j déjà traités.

    illuminated = np.ones((height, width), dtype=bool)

    # On détermine l'ordre de balayage selon la direction du Soleil.
    # Si dc > 0 (Soleil à l'est), on balaie les colonnes de gauche à droite.
    # Si dc < 0 (Soleil à l'ouest), de droite à gauche.
    # Si dr > 0 (Soleil au sud), de bas en haut (lignes décroissantes).
    # Cas général : angle quelconque — on projette.

    # Pour chaque case (r, c), son numéro de "file" dans la direction du Soleil :
    # file = r * dr + c * dc  (produit scalaire avec la direction)
    # On trie par file croissant (du côté soleil vers l'ombre).

    # Construction de la liste triée des cases
    rows, cols = np.mgrid[0:height, 0:width]
    # files = projection dans la direction *vers le Soleil* (du bord soleil = max → ombre = min)
    # On veut balayer du côté soleil vers le côté ombre.
    # Côté soleil = cases avec dc*col + dr*row le plus grand.
    # Donc sort décroissant de (dc*col + dr*row).
    files = rows * dr + cols * dc  # grand = côté soleil
    order = np.argsort(-files.ravel())  # du côté soleil vers l'ombre (décroissant)

    flat_dem = dem_f.ravel()
    flat_illum = illuminated.ravel()

    # Pour chaque "bande" perpendiculaire au rayon, maintenir l'horizon.
    # Bande = cases ayant le même numéro de colonne perpendiculaire.
    # Perpendiculaire à (dr, dc) est (-dc, dr).
    # band_key = r * (-dc) + c * dr  (arrondi à l'entier)

    # For each band (a row of cells along the sun direction), scan from sun side to shadow side.
    # Maintain f_max = max(elev[j] - dist_j * tan_alt) for all j seen so far.
    # Case i is in shadow if f_i = elev[i] - dist_i * tan_alt < f_max.

    # Note: band_ref_dist[band] is the file value of the first (sun-side) case.
    # dist_i = (band_ref_dist[band] - file_val[i]) * resolution_m  (non-negative)

    rows_flat = rows.ravel()[order]
    cols_flat = cols.ravel()[order]
    files_flat = files.ravel()[order]  # descending: first = sun side

    band_f_max: dict[int, float] = {}  # f_max = max(elev[j] - dist_j*tan_alt) per band
    band_ref_dist: dict[int, float] = {}  # file value of the first (sun-side) case

    for idx in range(len(rows_flat)):
        r = int(rows_flat[idx])
        c = int(cols_flat[idx])
        flat_idx = r * width + c
        file_val = float(files_flat[idx])  # decreasing from sun side

        band = round(-dc * r + dr * c)

        if band not in band_ref_dist:
            # First case of the band (closest to sun): always lit
            band_ref_dist[band] = file_val
            g_i = flat_dem[flat_idx] + 0.0 * tan_alt  # dist=0 for first case
            band_f_max[band] = g_i
            flat_illum[flat_idx] = True
        else:
            dist = (band_ref_dist[band] - file_val) * resolution_m  # >= 0
            g_i = flat_dem[flat_idx] + dist * tan_alt
            if g_i < band_f_max[band]:
                # In shadow: some previous case casts a shadow here
                flat_illum[flat_idx] = False
            else:
                # Lit (and potentially a new horizon obstacle)
                flat_illum[flat_idx] = True
                if g_i > band_f_max[band]:
                    band_f_max[band] = g_i

    illuminated = flat_illum.reshape(height, width)
    result = illuminated.astype(np.float32)
    result[nan_mask] = np.nan
    return result


# ---------------------------------------------------------------------------
# Commande principale : marswalk derive <site_id>
# ---------------------------------------------------------------------------


def derive(site_package_root: Path, out_dir: Path | None = None) -> None:
    """Calcule toutes les couches dérivées pour un paquet de site.

    ``site_package_root`` : dossier du paquet (contient manifest.json).
    ``out_dir`` : dossier de sortie pour les COG. Défaut : site_package_root/cog/.
    """
    site = open_package(site_package_root)
    crs = site.manifest.analysis_crs
    transform = site.manifest.grid.transform
    res = site.manifest.grid.resolution_m
    if out_dir is None:
        out_dir = site_package_root / "cog"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Lire les couches source
    dem = _load_layer(site, "dem")
    if dem is None:
        raise RuntimeError("Couche 'dem' requise pour le calcul des couches dérivées.")
    thermal = _load_layer(site, "thermal_inertia")

    # Lire la config du site pour les paramètres optionnels
    cfg: dict[str, object] = {}
    with contextlib.suppress(FileNotFoundError, KeyError):
        cfg = load_site_config(site.site_id)

    derive_cfg = cfg.get("derive", {})
    if not isinstance(derive_cfg, dict):
        derive_cfg = {}

    # Paramètres réglables depuis site.yaml
    roughness_window_m = float(derive_cfg.get("roughness_window_m", 10.0))
    obstacle_roughness_threshold_m = float(derive_cfg.get("obstacle_roughness_threshold_m", 0.4))
    obstacle_buffer_m = float(derive_cfg.get("obstacle_buffer_m", 2.0))
    scarp_threshold_deg = float(derive_cfg.get("scarp_threshold_deg", 30.0))
    scarp_buffer_m = float(derive_cfg.get("scarp_buffer_m", 10.0))
    antenna_height_m = float(derive_cfg.get("antenna_height_m", 3.0))
    sun_azimuth_deg = float(derive_cfg.get("sun_azimuth_deg", 90.0))
    sun_altitude_deg = float(derive_cfg.get("sun_altitude_deg", 20.0))

    # Coordonnées de l'habitat en cases
    from marswalk_core.geodesy import to_analysis

    hab = site.manifest.habitat
    hx, hy = to_analysis(site, float(hab[0]), float(hab[1]))
    h_cell = site.xy_to_cell(hx, hy)
    habitat_rc: tuple[int, int] = h_cell if h_cell is not None else (0, 0)

    print(f"[D2] Site : {site.site_id}  ({dem.shape[0]}×{dem.shape[1]}, {res} m/case)")

    # --- slope ---
    slope = compute_slope(dem, res)
    _write_cog(out_dir / "slope.tif", slope, transform, crs)
    print(f"[D2] slope écrit ({out_dir / 'slope.tif'})")

    # --- roughness ---
    roughness = compute_roughness(dem, res, window_m=roughness_window_m)
    _write_cog(out_dir / "roughness.tif", roughness, transform, crs)
    print("[D2] roughness écrit")

    # --- hillshade ---
    hillshade = compute_hillshade(dem, res, azimuth_deg=315.0, altitude_deg=45.0)
    _write_cog(out_dir / "hillshade.tif", hillshade, transform, crs)
    print("[D2] hillshade écrit")

    # --- obstacles ---
    obstacles = compute_obstacles(
        roughness,
        res,
        roughness_threshold_m=obstacle_roughness_threshold_m,
        buffer_m=obstacle_buffer_m,
    )
    _write_cog(out_dir / "obstacles.tif", obstacles, transform, crs)
    print("[D2] obstacles écrit")

    # --- scarps ---
    scarps = compute_scarps(
        slope, res, scarp_threshold_deg=scarp_threshold_deg, buffer_m=scarp_buffer_m
    )
    _write_cog(out_dir / "scarps.tif", scarps, transform, crs)
    print("[D2] scarps écrit")

    # --- loose_soil ---
    loose_soil = compute_loose_soil(thermal, slope, res)
    _write_cog(out_dir / "loose_soil.tif", loose_soil, transform, crs)
    print("[D2] loose_soil écrit")

    # --- radio_coverage (vectorisé) ---
    radio = _compute_radio_coverage_fast(dem, res, habitat_rc, antenna_height_m=antenna_height_m)
    _write_cog(out_dir / "radio_coverage.tif", radio, transform, crs)
    print("[D2] radio_coverage écrit")

    # --- illumination ---
    illum = compute_illumination(
        dem, res, azimuth_deg=sun_azimuth_deg, altitude_deg=sun_altitude_deg
    )
    _write_cog(out_dir / "illumination.tif", illum, transform, crs)
    print("[D2] illumination écrit")

    print("[D2] Toutes les couches dérivées calculées.")
