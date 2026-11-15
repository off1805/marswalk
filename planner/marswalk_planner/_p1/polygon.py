"""Vectorisation des masques en polygones GeoJSON (P1-F).

Algorithme :
1. Les masques sont d'abord regroupés par cause (slope_forbidden, obstacle, etc.).
2. Chaque couche est grossie par un facteur ``factor`` tel que la résolution finale
   soit ≈ 10 m (réduction du nombre de polygones tout en restant précis).
3. ``rasterio.features.shapes`` extrait les polygones des blocs positifs.
4. Les petits polygones (< 6 sommets ou surface < seuil) sont filtrés.
5. Les coordonnées sont converties en degrés planétocentriques (règle R2).

Propriétés de chaque Feature :
  kind       : "forbidden" ou "penalized"
  cause      : identifiant de la cause (ex. "slope_forbidden", "obstacle", …)
  severity   : "danger" pour interdit, "caution" pour pénalisé (ENF-06)
  threshold  : valeur du seuil déclencheur (ex. max_slope_deg pour slope)
  unit       : unité du seuil (ex. "deg")
  color      : couleur d'affichage (rouge pour danger, orange pour caution)
  label      : libellé lisible
"""

from __future__ import annotations

import numpy as np
import rasterio.features
from affine import Affine

from marswalk_core.geodesy import to_lonlat
from marswalk_core.grids import HazardMasks
from marswalk_core.schemas import (
    Feature,
    FeatureCollection,
    LonLat,
    PolygonGeometry,
    SafetySettings,
)
from marswalk_core.site_package import Site

# Résolution cible des polygones en mètres (compromis précision/taille GeoJSON)
_POLYGON_RESOLUTION_M = 10.0

# Surface minimale d'un polygone en cases grossies pour être inclus
_MIN_POLYGON_CELLS = 2

# Configuration de chaque cause
_CAUSE_META: dict[str, dict[str, str]] = {
    # --- interdits ---
    "slope_forbidden": {
        "kind": "forbidden",
        "severity": "danger",
        "color": "#d62728",
        "label": "Pente excessive",
        "threshold_key": "max_slope_deg",
        "unit": "deg",
    },
    "obstacle": {
        "kind": "forbidden",
        "severity": "danger",
        "color": "#d62728",
        "label": "Obstacle",
        "threshold_key": "obstacle_buffer_m",
        "unit": "m",
    },
    "dune": {
        "kind": "forbidden",
        "severity": "danger",
        "color": "#9467bd",
        "label": "Dune active",
        "threshold_key": "avoid_loose_soil_class",
        "unit": "class",
    },
    "scarp": {
        "kind": "forbidden",
        "severity": "danger",
        "color": "#e377c2",
        "label": "Bord de falaise (tampon)",
        "threshold_key": "scarp_buffer_m",
        "unit": "m",
    },
    # --- pénalisés ---
    "slope_penalized": {
        "kind": "penalized",
        "severity": "caution",
        "color": "#ff7f0e",
        "label": "Pente modérée",
        "threshold_key": "penalty_slope_deg",
        "unit": "deg",
    },
    "loose_soil": {
        "kind": "penalized",
        "severity": "caution",
        "color": "#bcbd22",
        "label": "Sol meuble",
        "threshold_key": "avoid_loose_soil_class",
        "unit": "class",
    },
    "no_radio": {
        "kind": "penalized",
        "severity": "caution",
        "color": "#17becf",
        "label": "Hors couverture radio",
        "threshold_key": "radio_penalty",
        "unit": "",
    },
    "shadow": {
        "kind": "penalized",
        "severity": "caution",
        "color": "#7f7f7f",
        "label": "Zone ombragée",
        "threshold_key": "min_illumination",
        "unit": "",
    },
    "roughness": {
        "kind": "penalized",
        "severity": "caution",
        "color": "#8c564b",
        "label": "Rugosité élevée",
        "threshold_key": "max_roughness_m",
        "unit": "m",
    },
}


def _coarsen(mask: np.ndarray, factor: int) -> np.ndarray:
    """Réduit le masque par un facteur ``factor`` (vote majoritaire)."""
    h = (mask.shape[0] // factor) * factor
    w = (mask.shape[1] // factor) * factor
    if h == 0 or w == 0:
        return mask
    blocks = mask[:h, :w].reshape(h // factor, factor, w // factor, factor)
    return np.asarray(blocks.mean(axis=(1, 3)) >= 0.5, dtype=np.uint8)


def _coarsen_transform(transform: tuple[float, ...], factor: int) -> Affine:
    a, b, c, d, e, f = transform
    return Affine(a * factor, b, c, d, e * factor, f)


def _rings_to_lonlat(
    rings: list[list[list[float]]],
    site: Site,
) -> list[list[LonLat]]:
    """Convertit les anneaux de coordonnées analyse (m) en degrés planétocentriques."""
    result: list[list[LonLat]] = []
    for ring in rings:
        pts = [LonLat(*to_lonlat(site, float(x), float(y))) for x, y in ring]
        result.append(pts)
    return result


def build_hazard_polygons(
    masks: HazardMasks,
    settings: SafetySettings,
    site: Site,
) -> FeatureCollection:
    """Produit les polygones GeoJSON des zones dangereuses à partir des masques."""
    res = site.manifest.grid.resolution_m
    factor = max(1, round(_POLYGON_RESOLUTION_M / res))
    coarse_transform = _coarsen_transform(masks.transform, factor)

    features: list[Feature] = []
    feature_id = 0

    for cause_key, meta in _CAUSE_META.items():
        if cause_key == "no_radio" and not settings.require_radio:
            # Radio non exigée (préréglage standard) : la pénalité reste dans le coût, mais
            # on ne la dessine pas comme zone de danger. Sur Jezero elle couvre plus de la
            # moitié de l'emprise et noyait la carte en orange ; la couche
            # radio_coverage la montre déjà.
            continue
        full_mask = masks.by_cause.get(cause_key)
        if full_mask is None or not bool(np.any(full_mask)):
            continue

        coarse = _coarsen(full_mask.astype(np.uint8), factor)
        if not bool(np.any(coarse)):
            continue

        shapes = rasterio.features.shapes(
            coarse,
            mask=coarse,
            transform=coarse_transform,
            connectivity=4,
        )

        threshold_val = getattr(settings, meta["threshold_key"], None)
        kind = meta["kind"]
        severity = meta["severity"]

        for geom_dict, _val in shapes:
            coords = geom_dict["coordinates"]
            # Filtrer uniquement les polygones dégénérés (< 4 sommets = impossible en GeoJSON)
            if len(coords[0]) < 4:
                continue

            rings = _rings_to_lonlat(coords, site)
            features.append(
                Feature(
                    id=f"{cause_key}-{feature_id}",
                    geometry=PolygonGeometry(coordinates=rings),
                    properties={
                        "kind": kind,
                        "cause": cause_key,
                        "severity": severity,
                        "label": meta["label"],
                        "color": meta["color"],
                        "threshold": threshold_val,
                        "unit": meta["unit"],
                    },
                )
            )
            feature_id += 1

    return FeatureCollection(features=features)
