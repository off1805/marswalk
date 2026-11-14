"""Zones dangereuses (P1). BOUCHON de T00 : interdit au-delà de ``max_slope_deg`` de pente.

Signatures gelées :
- ``hazard_masks(site, settings) -> HazardMasks``
- ``hazard_polygons(site, settings) -> FeatureCollection`` (degrés, règle R2)
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


def hazard_masks(site: Site, settings: SafetySettings) -> HazardMasks:
    slope = site.read_layer("slope").values
    forbidden = np.nan_to_num(slope, nan=90.0) > settings.max_slope_deg
    penalized = (~forbidden) & (np.nan_to_num(slope) > settings.penalty_slope_deg)
    return HazardMasks(
        transform=site.transform,
        forbidden=forbidden,
        penalized=penalized,
        by_cause={"slope": forbidden},
    )


def _coarsen(mask: np.ndarray, factor: int) -> np.ndarray:
    h, w = (mask.shape[0] // factor) * factor, (mask.shape[1] // factor) * factor
    blocks = mask[:h, :w].reshape(h // factor, factor, w // factor, factor)
    return np.asarray(blocks.mean(axis=(1, 3)) >= 0.5)


def hazard_polygons(site: Site, settings: SafetySettings) -> FeatureCollection:
    """Bouchon : polygones sur une grille grossie à environ 10 m, petites zones ignorées."""
    masks = hazard_masks(site, settings)
    res = site.manifest.grid.resolution_m
    factor = max(1, round(10.0 / res))
    a, b, c, d, e, f = site.transform
    transform = Affine(a * factor, b, c, d, e * factor, f)
    features: list[Feature] = []
    for kind, full in (("forbidden", masks.forbidden), ("penalized", masks.penalized)):
        mask = _coarsen(full, factor)
        shapes = rasterio.features.shapes(
            mask.astype(np.uint8), mask=mask, transform=transform, connectivity=4
        )
        for i, (geom, _value) in enumerate(shapes):
            if len(geom["coordinates"][0]) < 6:
                continue
            rings = [
                [LonLat(*to_lonlat(site, float(x), float(y))) for x, y in ring]
                for ring in geom["coordinates"]
            ]
            features.append(
                Feature(
                    id=f"{kind}-{i}",
                    geometry=PolygonGeometry(coordinates=rings),
                    properties={
                        "kind": kind,
                        "cause": "slope",
                        "threshold": settings.max_slope_deg
                        if kind == "forbidden"
                        else settings.penalty_slope_deg,
                        "unit": "deg",
                    },
                )
            )
    return FeatureCollection(features=features)
