"""Construction vectorisée des masques de zones interdites et pénalisées (P1-B, P1-C).

Zones interdites (``forbidden``) — règle : une cellule interdite ne peut jamais être
traversée ; P2 doit l'éviter absolument.

  slope_forbidden   : pente ≥ max_slope_deg
  obstacle_forbidden: obstacles == 1
  dune_forbidden    : loose_soil ≥ avoid_loose_soil_class  (par défaut classe 3 = dune)
  scarp_forbidden   : scarps == 1 dilatés d'un tampon scarp_buffer_m

Le tampon de falaise tient compte de l'incertitude de recalage de la couche
(``uncertainty.coreg_m`` dans le manifeste) et de la résolution des données.
Le tampon total en cases = ceil((scarp_buffer_m + coreg_m + resolution_m) / resolution_m).

Zones pénalisées (``penalized``) — règle : zones où circuler est possible mais coûteux ;
elles ne se recoupent pas avec ``forbidden``.

  slope_penalized   : penalty_slope_deg ≤ pente < max_slope_deg
  loose_soil_penal  : loose_soil == avoid_loose_soil_class − 1  (meuble mais pas dune)
  radio_penalized   : radio_coverage == 0
  shadow_penalized  : illumination < min_illumination
  roughness_penal   : roughness > max_roughness_m  (rugosité élevée mais pas obstacle)

Dégradation gracieuse : quand une couche est absente, les masques correspondants
appliquent le côté sûr (pire cas), sauf si la couche n'a que des effets de pénalité
(dans ce cas la pénalité n'est simplement pas ajoutée).
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from marswalk_core.grids import HazardMasks
from marswalk_core.schemas import SafetySettings
from marswalk_core.site_package import LayerUnavailableError, Site

from .layers import LayerBundle

BoolGrid = NDArray[np.bool_]


# ---------------------------------------------------------------------------
# Tampon de falaise
# ---------------------------------------------------------------------------


def _scarp_buffer_cells(
    site: Site,
    settings: SafetySettings,
) -> int:
    """Nombre de cellules pour le tampon de falaise.

    Tampon = scarp_buffer_m + incertitude_de_recalage + 1 résolution (arrondi au-dessus).
    """
    res = site.manifest.grid.resolution_m

    # Lire l'incertitude de recalage de la couche scarps si disponible
    coreg_m = 0.0
    try:
        info = site.layer("scarps")
        if info.uncertainty and info.uncertainty.coreg_m is not None:
            coreg_m = float(info.uncertainty.coreg_m)
    except LayerUnavailableError:
        pass

    total_m = settings.scarp_buffer_m + coreg_m + res
    return max(1, math.ceil(total_m / res))


def _dilate_mask(mask: BoolGrid, radius_cells: int) -> BoolGrid:
    """Dilation morphologique par un carré 2r+1 (deux passes 1D, rapide et conservative).

    Un carré est légèrement plus grand qu'un disque de même rayon, ce qui est
    acceptable pour un tampon de sécurité (conservatisme voulu).
    Performance : O(n) en deux passes maximum_filter1d, nettement plus rapide que
    la dilation binaire 2D avec un élément structurant en disque.
    """
    if radius_cells <= 0:
        return mask
    from scipy.ndimage import maximum_filter1d  # type: ignore[import-untyped]

    size = 2 * radius_cells + 1
    dilated = maximum_filter1d(mask.astype(np.uint8), size=size, axis=0)
    dilated = maximum_filter1d(dilated, size=size, axis=1)
    return np.asarray(dilated, dtype=bool)


# ---------------------------------------------------------------------------
# Masques principaux
# ---------------------------------------------------------------------------


def build_masks(
    layers: LayerBundle,
    settings: SafetySettings,
    site: Site,
) -> tuple[BoolGrid, BoolGrid, dict[str, BoolGrid]]:
    """Construit les masques interdit et pénalisé, plus un dict par cause.

    Retourne ``(forbidden, penalized, by_cause)`` où ``by_cause`` contient les
    masques individuels avant union, utiles pour les polygones et explications.
    """
    shape = layers.slope.shape

    # ------------------------------------------------------------------
    # Zones interdites
    # ------------------------------------------------------------------

    # 1. Pente au-dessus du seuil
    slope_forbidden: BoolGrid = layers.slope >= settings.max_slope_deg

    # 2. Obstacles
    obstacle_forbidden: BoolGrid = layers.obstacles >= 0.5

    # 3. Dunes actives : loose_soil ≥ avoid_loose_soil_class
    dune_forbidden: BoolGrid = layers.loose_soil >= float(settings.avoid_loose_soil_class)

    # 4. Bords de falaise + tampon
    radius = _scarp_buffer_cells(site, settings)
    scarp_base: BoolGrid = layers.scarps >= 0.5
    scarp_forbidden: BoolGrid = _dilate_mask(scarp_base, radius)

    # Union des interdictions
    forbidden: BoolGrid = slope_forbidden | obstacle_forbidden | dune_forbidden | scarp_forbidden

    # ------------------------------------------------------------------
    # Zones pénalisées (exclusives des interdites)
    # ------------------------------------------------------------------

    # 1. Pente intermédiaire
    slope_pen: BoolGrid = (layers.slope >= settings.penalty_slope_deg) & ~slope_forbidden

    # 2. Sol meuble (classe avoid_loose_soil_class − 1 = meuble mais pas dune)
    soil_pen_class = settings.avoid_loose_soil_class - 1
    if soil_pen_class >= 1:
        loose_pen: BoolGrid = (layers.loose_soil == float(soil_pen_class)) & ~dune_forbidden
    else:
        loose_pen = np.zeros(shape, dtype=bool)

    # 3. Hors couverture radio
    if layers.radio_coverage is not None:
        radio_pen: BoolGrid = layers.radio_coverage < 0.5
    else:
        radio_pen = np.zeros(shape, dtype=bool)

    # 4. Zones ombragées (en-dessous du seuil d'illumination minimal)
    if layers.illumination is not None:
        shadow_pen: BoolGrid = layers.illumination <= settings.min_illumination
    else:
        shadow_pen = np.zeros(shape, dtype=bool)

    # 5. Rugosité excessive (pas obstacle, mais sol difficile)
    if layers.roughness is not None:
        roughness_pen: BoolGrid = (
            layers.roughness > settings.max_roughness_m
        ) & ~obstacle_forbidden
    else:
        roughness_pen = np.zeros(shape, dtype=bool)

    penalized_raw: BoolGrid = slope_pen | loose_pen | radio_pen | shadow_pen | roughness_pen
    # Les cellules interdites ne sont jamais aussi pénalisées (catégories distinctes)
    penalized: BoolGrid = penalized_raw & ~forbidden

    by_cause: dict[str, BoolGrid] = {
        # interdit
        "slope_forbidden": slope_forbidden,
        "obstacle": obstacle_forbidden,
        "dune": dune_forbidden,
        "scarp": scarp_forbidden,
        # pénalisé
        "slope_penalized": slope_pen & ~forbidden,
        "loose_soil": loose_pen & ~forbidden,
        "no_radio": radio_pen & ~forbidden,
        "shadow": shadow_pen & ~forbidden,
        "roughness": roughness_pen & ~forbidden,
    }

    return forbidden, penalized, by_cause


def build_hazard_masks(
    layers: LayerBundle,
    settings: SafetySettings,
    site: Site,
) -> HazardMasks:
    """Point d'entrée public du sous-module : produit un ``HazardMasks``."""
    forbidden, penalized, by_cause = build_masks(layers, settings, site)
    return HazardMasks(
        transform=site.transform,
        forbidden=forbidden,
        penalized=penalized,
        by_cause=by_cause,
        warnings=list(layers.warnings),
    )
