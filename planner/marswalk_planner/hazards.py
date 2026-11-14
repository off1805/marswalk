"""Zones dangereuses (P1).

Signatures gelées (taches-agents.md section 7) :
  ``hazard_masks(site, settings) -> HazardMasks``
  ``hazard_polygons(site, settings) -> FeatureCollection``

Implémentation complète : délègue à ``marswalk_planner._p1``.
"""

from __future__ import annotations

from marswalk_core.grids import HazardMasks
from marswalk_core.schemas import FeatureCollection, SafetySettings
from marswalk_core.site_package import Site

from marswalk_planner._p1.layers import load_layers
from marswalk_planner._p1.masks import build_hazard_masks
from marswalk_planner._p1.polygon import build_hazard_polygons


def hazard_masks(site: Site, settings: SafetySettings) -> HazardMasks:
    """Construit les masques de zones interdites et pénalisées.

    Zones interdites (``HazardMasks.forbidden``) :
      - pente ≥ ``settings.max_slope_deg``
      - obstacles == 1
      - loose_soil ≥ ``settings.avoid_loose_soil_class`` (dunes actives)
      - scarps == 1 dilatés du tampon ``settings.scarp_buffer_m``

    Zones pénalisées (``HazardMasks.penalized``) :
      - ``settings.penalty_slope_deg`` ≤ pente < ``settings.max_slope_deg``
      - loose_soil == ``settings.avoid_loose_soil_class`` − 1
      - radio_coverage == 0
      - illumination ≤ ``settings.min_illumination``
      - roughness > ``settings.max_roughness_m``

    Les deux catégories sont disjointes : ``penalized & forbidden == False``.

    Les couches manquantes ou dégradées déclenchent un avertissement et une
    marge de sécurité accrue (jamais une donnée inconnue traitée comme sûre).
    """
    layers = load_layers(site)
    return build_hazard_masks(layers, settings, site)


def hazard_polygons(site: Site, settings: SafetySettings) -> FeatureCollection:
    """Retourne les zones dangereuses sous forme de polygones GeoJSON.

    Chaque Feature contient :
      - ``kind``      : "forbidden" ou "penalized"
      - ``cause``     : identifiant de la règle déclenchée
      - ``severity``  : "danger" (interdit) ou "caution" (pénalisé)
      - ``label``     : libellé lisible
      - ``color``     : couleur d'affichage (accessible daltoniens)
      - ``threshold`` : valeur du seuil (ex. 20.0 pour la pente)
      - ``unit``      : unité du seuil (ex. "deg")

    Coordonnées en degrés planétocentriques, points [lon, lat] (règle R2).
    Les cellules adjacentes de même cause sont regroupées (~10 m de résolution)
    pour limiter la taille du GeoJSON.
    """
    layers = load_layers(site)
    masks = build_hazard_masks(layers, settings, site)
    return build_hazard_polygons(masks, settings, site)
