"""Catalogue par défaut des couches d'un paquet (D3).

Pour chaque identifiant de la section 5.3 de ``taches-agents.md`` : titre, nature, unité,
plage, légende et règles d'affichage des tuiles. Les métadonnées propres à un site (source,
date, résolution, incertitude, statut) viennent du fichier ``layers/<id>.json`` écrit par
la tâche qui produit la couche ; ses champs l'emportent sur ce catalogue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from marswalk_core.schemas import LayerKind, Legend, LegendStop

Resample = Literal["lanczos", "average", "nearest"]

VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]
CIVIDIS = ["#00224e", "#35456c", "#666970", "#948e77", "#c8b866", "#fee838"]
GRAY = ["#000000", "#ffffff"]


def ramp(lo: float, hi: float, colors: list[str]) -> Legend:
    n = len(colors) - 1
    return Legend(
        type="continuous",
        stops=[LegendStop(value=lo + (hi - lo) * i / n, color=c) for i, c in enumerate(colors)],
    )


def categories(items: list[tuple[float, str, str]]) -> Legend:
    return Legend(
        type="categorical",
        stops=[LegendStop(value=v, color=c, label=label) for v, c, label in items],
    )


@dataclass(frozen=True)
class Display:
    """Règles de rendu des tuiles d'une couche (section 4, « Netteté de l'imagerie »)."""

    resample: Resample
    """Passage d'un zoom au zoom inférieur : Lanczos (imagerie), moyenne ou plus proche voisin."""
    stretch: tuple[float, float] | None = None
    """Étirement du contraste sur ces centiles de l'emprise (imagerie)."""
    transparent: tuple[float, ...] = ()
    """Classes laissées transparentes (couches catégorielles)."""
    quality: int = 90
    """Qualité WebP des couches continues ; les couches catégorielles sont sans perte."""


@dataclass(frozen=True)
class LayerDefaults:
    title: str
    kind: LayerKind
    unit: str | None
    value_range: tuple[float, float] | None
    legend: Legend | None
    display: Display = field(default_factory=lambda: Display("average"))


IMAGERY = Display("lanczos", stretch=(0.5, 99.5), quality=92)
CONTINUOUS = Display("average")


def _cat(transparent: tuple[float, ...] = ()) -> Display:
    return Display("nearest", transparent=transparent)


CATALOG: dict[str, LayerDefaults] = {
    "hirise_vis": LayerDefaults(
        "Imagerie HiRISE", LayerKind.imagery, "DN", (0, 255), ramp(0, 255, GRAY), IMAGERY
    ),
    "ctx_vis": LayerDefaults(
        "Contexte CTX", LayerKind.imagery, "DN", (0, 255), ramp(0, 255, GRAY), IMAGERY
    ),
    "dem": LayerDefaults(
        "Altitude (MNT)",
        LayerKind.dem,
        "m",
        (-2630, -2550),
        ramp(-2630, -2550, CIVIDIS),
        CONTINUOUS,
    ),
    "dem_mola": LayerDefaults(
        "Altitude MOLA",
        LayerKind.dem,
        "m",
        (-2630, -2550),
        ramp(-2630, -2550, CIVIDIS),
        CONTINUOUS,
    ),
    "slope": LayerDefaults(
        "Pente", LayerKind.derived, "deg", (0, 60), ramp(0, 60, VIRIDIS), CONTINUOUS
    ),
    "roughness": LayerDefaults(
        "Rugosité", LayerKind.derived, "m", (0, 1), ramp(0, 1, VIRIDIS), CONTINUOUS
    ),
    "hillshade": LayerDefaults(
        "Ombrage", LayerKind.derived, None, (0, 255), ramp(0, 255, GRAY), Display("lanczos")
    ),
    "obstacles": LayerDefaults(
        "Obstacles (avec tampon)",
        LayerKind.derived,
        None,
        (0, 1),
        categories([(0, "#000000", "libre"), (1, "#cc79a7", "obstacle")]),
        _cat((0,)),
    ),
    "scarps": LayerDefaults(
        "Ruptures de pente",
        LayerKind.derived,
        None,
        (0, 1),
        categories([(0, "#000000", "aucune"), (1, "#e69f00", "falaise ou bord")]),
        _cat((0,)),
    ),
    "thermal_inertia": LayerDefaults(
        "Inertie thermique",
        LayerKind.thermal,
        "J m-2 K-1 s-1/2",
        (100, 800),
        ramp(100, 800, VIRIDIS),
        CONTINUOUS,
    ),
    "loose_soil": LayerDefaults(
        "Classe de sol",
        LayerKind.derived,
        None,
        (0, 3),
        categories(
            [
                (0, "#7f7f7f", "roche"),
                (1, "#c9a66b", "mixte"),
                (2, "#e8c77a", "meuble"),
                (3, "#f5e6a8", "dune"),
            ]
        ),
        _cat(),
    ),
    "crism_minerals": LayerDefaults(
        "Minéralogie",
        LayerKind.spectral,
        None,
        (0, 2),
        categories(
            [
                (0, "#000000", "non détecté"),
                (1, "#56b4e9", "argiles et carbonates"),
                (2, "#009e73", "olivine"),
            ]
        ),
        _cat((0,)),
    ),
    "radio_coverage": LayerDefaults(
        "Couverture radio",
        LayerKind.derived,
        None,
        (0, 1),
        categories([(0, "#0072b2", "hors couverture"), (1, "#000000", "couvert")]),
        _cat((1,)),
    ),
    "illumination": LayerDefaults(
        "Éclairement", LayerKind.derived, None, (0, 1), ramp(0, 1, GRAY), CONTINUOUS
    ),
    "return_time": LayerDefaults(
        "Temps de retour", LayerKind.derived, "s", (0, 2000), ramp(0, 2000, VIRIDIS), CONTINUOUS
    ),
    "rover_traverse": LayerDefaults("Trajet du rover", LayerKind.vector, None, None, None),
    "ground_images": LayerDefaults("Images au sol", LayerKind.ground, None, None, None),
}

VECTOR_LAYERS = frozenset({"rover_traverse", "ground_images"})
