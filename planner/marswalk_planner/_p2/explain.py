"""Explication des tronçons en clair (P2, écart E6).

Pour chaque tronçon, on compare le tracé retenu à la ligne droite entre ses deux
extrémités : ce que la ligne droite traverse et que le tracé évite est la raison du
détour (« contourne une pente de 24° »). Un tronçon presque droit le dit, avec la pente
la plus forte rencontrée. Les termes du coût d'une case (Tobler, R, S) restent
disponibles par ``explain_cell`` mais ne sont plus montrés à l'astronaute.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from marswalk_core.geodesy import distance_m, to_analysis
from marswalk_core.grids import CostGrid
from marswalk_core.schemas import LonLat
from marswalk_planner._p2.smooth import _line_cells

# En dessous de ce rapport longueur du tracé / ligne droite, le tronçon est « direct ».
_DIRECT_RATIO = 1.03
# Part minimale (en cases de la ligne droite) pour qu'une zone compte comme évitée.
_MIN_CELLS = 2

# Cause → (texte quand le tracé l'évite). Les pentes ont leur propre phrase, chiffrée.
_FORBIDDEN_TEXT: dict[str, str] = {
    "cause_scarp": "évite le bord de la falaise",
    "cause_obstacle": "contourne un champ de blocs",
    "cause_dune": "évite les dunes actives",
}
_PENALIZED_TEXT: dict[str, str] = {
    "cause_loose_soil": "évite le sol meuble",
    "cause_no_radio": "reste en couverture radio",
    "cause_shadow": "évite les zones d'ombre",
    "cause_roughness": "évite le terrain rugueux",
}


@dataclass
class _LineStats:
    length_m: float
    cells: int
    max_slope_deg: float
    science_mean: float
    causes: dict[str, int] = field(default_factory=dict)
    max_slope_by_cause: dict[str, float] = field(default_factory=dict)


def _to_cell_coords(cost_grid: CostGrid, p: LonLat) -> tuple[int, int] | None:
    x, y = to_analysis(cost_grid.site, p.lon, p.lat)
    return cost_grid.site.xy_to_cell(x, y)


def _cells_of(cost_grid: CostGrid, pts: list[LonLat]) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    rows: list[NDArray[np.intp]] = []
    cols: list[NDArray[np.intp]] = []
    h, w = cost_grid.cost.shape
    for a, b in itertools.pairwise(pts):
        ca = _to_cell_coords(cost_grid, a)
        cb = _to_cell_coords(cost_grid, b)
        if ca is None or cb is None:
            continue
        r, c, _ = _line_cells(ca[0], ca[1], cb[0], cb[1])
        keep = (r >= 0) & (r < h) & (c >= 0) & (c < w)
        rows.append(r[keep])
        cols.append(c[keep])
    if not rows:
        empty = np.zeros(0, dtype=np.intp)
        return empty, empty
    return np.concatenate(rows), np.concatenate(cols)


def _stats(cost_grid: CostGrid, pts: list[LonLat]) -> _LineStats:
    rows, cols = _cells_of(cost_grid, pts)
    length = sum(distance_m(a, b) for a, b in itertools.pairwise(pts))
    stats = _LineStats(length_m=length, cells=int(rows.size), max_slope_deg=0.0, science_mean=0.0)
    if rows.size == 0:
        return stats
    slope = cost_grid.terms.get("slope")
    slopes = slope[rows, cols] if isinstance(slope, np.ndarray) else None
    if slopes is not None:
        stats.max_slope_deg = float(np.nanmax(slopes))
    science = cost_grid.terms.get("science")
    if isinstance(science, np.ndarray):
        stats.science_mean = float(np.mean(science[rows, cols]))
    for key, arr in cost_grid.terms.items():
        if not key.startswith("cause_") or not isinstance(arr, np.ndarray):
            continue
        hit = arr[rows, cols] > 0.5
        n = int(hit.sum())
        if n:
            stats.causes[key] = n
            if slopes is not None:
                stats.max_slope_by_cause[key] = float(np.nanmax(slopes[hit]))
    return stats


def _avoided(direct: _LineStats, route: _LineStats, key: str) -> bool:
    """La ligne droite traverse la zone ``key`` et le tracé nettement moins."""
    on_direct = direct.causes.get(key, 0)
    return on_direct >= _MIN_CELLS and route.causes.get(key, 0) < on_direct / 2


def _deg(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "°"


def explain_segment(
    cost_grid: CostGrid,
    pts: list[LonLat],
    *,
    fallback: bool = False,
    science_variant: bool = False,
    max_slope_deg: float | None = None,
) -> str:
    """Une phrase qui dit pourquoi le tronçon ``pts`` passe par là.

    ``fallback`` : le tronçon est une ligne droite de secours (aucun passage trouvé).
    ``science_variant`` : la variante cherche l'intérêt scientifique ; le passage par
    une unité minérale n'est cité comme raison que pour elle.
    ``max_slope_deg`` : pente max mesurée le long du tracé (celle du tableau des
    tronçons) ; à défaut, celle des cases traversées.
    """
    if len(pts) < 2:
        return "Tronçon nul : départ et arrivée confondus."
    direct = _stats(cost_grid, [pts[0], pts[-1]])
    if fallback:
        return (
            f"Aucun passage praticable : la ligne droite franchit une pente de "
            f"{direct.max_slope_deg:.0f}°. Ce tronçon n'est pas à suivre."
        )
    route = _stats(cost_grid, pts)
    ratio = route.length_m / direct.length_m if direct.length_m > 0 else 1.0
    measured = route.max_slope_deg if max_slope_deg is None else max_slope_deg
    tail = f"pente max {_deg(measured)} sur le tracé"

    if ratio < _DIRECT_RATIO:
        crossed = [
            txt.replace("évite ", "").replace("reste en couverture radio", "hors couverture radio")
            for key, txt in _PENALIZED_TEXT.items()
            if route.causes.get(key, 0) >= _MIN_CELLS
        ]
        if route.causes.get("cause_slope_penalized", 0) >= _MIN_CELLS:
            crossed.insert(0, "une pente intermédiaire")
        extra = f", traverse {', '.join(crossed)}" if crossed else ""
        return f"Va en ligne droite ({tail}{extra})."

    reasons: list[str] = []
    if _avoided(direct, route, "cause_slope_forbidden"):
        deg = direct.max_slope_by_cause.get("cause_slope_forbidden", direct.max_slope_deg)
        reasons.append(f"contourne une pente de {deg:.0f}°")
    for key, txt in _FORBIDDEN_TEXT.items():
        if _avoided(direct, route, key) and not (
            key == "cause_scarp" and reasons  # falaise et pente : une seule phrase
        ):
            reasons.append(txt)
    if not reasons and _avoided(direct, route, "cause_slope_penalized"):
        deg = direct.max_slope_by_cause.get("cause_slope_penalized", direct.max_slope_deg)
        reasons.append(f"évite une pente de {deg:.0f}°")
    for key, txt in _PENALIZED_TEXT.items():
        if _avoided(direct, route, key):
            reasons.append(txt)
    if science_variant and route.science_mean > direct.science_mean + 0.1:
        reasons.append("passe par une unité minérale d'intérêt (CRISM)")
    if not reasons:
        reasons.append("suit le terrain le plus facile")

    detour = route.length_m - direct.length_m
    sentence = " et ".join([", ".join(reasons[:-1]), reasons[-1]] if len(reasons) > 1 else reasons)
    return f"{sentence[0].upper()}{sentence[1:]} : +{detour:.0f} m ({tail})."


def describe_slope(cost_grid: CostGrid, a: LonLat, b: LonLat) -> float:
    """Pente la plus forte sur la ligne droite a→b (degrés, 0 si inconnue)."""
    return _stats(cost_grid, [a, b]).max_slope_deg
