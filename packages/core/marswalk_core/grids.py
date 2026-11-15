"""Types internes des bibliothèques (grilles NumPy). Contrat gelé avec contrats-v1.

Ces structures circulent entre ``marswalk_planner`` et l'API sans passer sur le réseau.
Toutes les grilles sont alignées sur la grille de planification (règle R1) :
``transform`` est l'affine rasterio de la grille, en mètres du système d'analyse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from marswalk_core.schemas import Conditions, LonLat, RouteVariant, SuitModel

if TYPE_CHECKING:
    from marswalk_core.site_package import Site

FloatGrid = NDArray[np.float32]
BoolGrid = NDArray[np.bool_]
Transform = tuple[float, float, float, float, float, float]


@dataclass
class HazardMasks:
    """Masques booléens par cause (``slope``, ``obstacles``...) et synthèse."""

    transform: Transform
    forbidden: BoolGrid
    penalized: BoolGrid
    by_cause: dict[str, BoolGrid] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class CostTerm:
    """Un terme du coût d'une case, pour l'explication (ENF-12)."""

    name: str
    value: float
    weight: float
    reason: str


@dataclass
class CostGrid:
    """Grille de coût : secondes de traversée pondérées par case, ``inf`` si interdite."""

    site: Site
    transform: Transform
    resolution_m: float
    cost: FloatGrid
    forbidden: BoolGrid
    terms: dict[str, FloatGrid] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    margin_pct: float = 0.0


@dataclass
class RouteOptions:
    variant: RouteVariant = RouteVariant.safest
    variants: list[RouteVariant] = field(
        default_factory=lambda: [RouteVariant.safest, RouteVariant.fastest, RouteVariant.science]
    )
    return_to: LonLat | None = None
    """Point d'arrivée ; ``None`` pour revenir au départ."""
    optimize_order: bool = True
    window_margin_m: float = 200.0
    suit: SuitModel | None = None
    conditions: Conditions | None = None


@dataclass
class RouteGeometry:
    """Tracé en degrés, découpé par tronçon (un tronçon entre deux points de passage)."""

    coordinates: list[LonLat]
    segment_breaks: list[int]
    """Indice, dans ``coordinates``, du premier point de chaque tronçon."""
    cost: float = 0.0
    fallback_segments: list[int] = field(default_factory=list)
    """Tronçons sans passage praticable, tracés en ligne droite de secours."""


@dataclass
class SegmentEstimate:
    distance_m: float
    walk_time_s: float
    work_time_s: float
    ascent_m: float
    descent_m: float
    max_slope_deg: float
    oxygen_kg: float
    battery_wh: float
    water_l: float
    dose_usv: float


@dataclass
class RouteEstimate:
    segments: list[SegmentEstimate]
    samples_distance_m: list[float]
    samples_position: list[LonLat]
    samples_elevation_m: list[float | None]
    samples_slope_deg: list[float | None]
    samples_time_s: list[float]
    samples_segment: list[int]


@dataclass
class ReturnField:
    """Temps de retour le plus court vers l'habitat depuis chaque case, en secondes."""

    site: Site
    transform: Transform
    resolution_m: float
    seconds: FloatGrid
    habitat: LonLat
