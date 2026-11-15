"""Recalcul local d'itinéraire pendant une sortie (A4).

Le simulateur ne cherche pas lui-même de chemin : il appelle les fonctions gelées du
planificateur (``build_cost_grid`` de P1, ``plan_route`` de P2, ``estimate_route``,
``return_field`` et ``return_check`` de P3) et ajoute ce qui est propre à la sortie :

- les obstacles signalés, interdits sur une copie de la grille de coût ;
- un contournement géométrique de chaque obstacle que le tracé rendu traverserait encore
  (utile tant que P2 est un bouchon en ligne droite, sans effet ensuite) ;
- l'assemblage d'un ``Route`` complet (tronçons, profil, totaux, retour garanti).
"""

from __future__ import annotations

import itertools
import math
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import numpy as np

from marswalk_core.geodesy import to_analysis, to_lonlat
from marswalk_core.grids import CostGrid, ReturnField, RouteGeometry, RouteOptions
from marswalk_core.schemas import (
    Conditions,
    Consumption,
    LineStringGeometry,
    LonLat,
    ProfileSample,
    Route,
    RouteSegment,
    RouteTotals,
    RouteVariant,
    SafetySettings,
    SegmentExplanation,
    SuitModel,
    Target,
)
from marswalk_core.site_package import Site
from marswalk_planner.budget import return_check
from marswalk_planner.cost import build_cost_grid, explain_cell
from marswalk_planner.return_field import return_field
from marswalk_planner.route import plan_route
from marswalk_planner.walk import estimate_route

DETOUR_STEP_DEG = 30.0
"""Pas angulaire des points de contournement autour d'un obstacle."""


@dataclass(frozen=True)
class Obstacle:
    id: str
    position: LonLat
    radius_m: float
    note: str | None = None


# -- grilles en cache -------------------------------------------------------------


class GridCache:
    """Grille de coût et champ de retour par site et réglages (calculés une fois)."""

    def __init__(self) -> None:
        self._grids: dict[tuple[str, str], CostGrid] = {}
        self._fields: dict[tuple[str, str], ReturnField] = {}
        self._lock = threading.Lock()

    def grid(self, site: Site, settings: SafetySettings) -> CostGrid:
        key = (site.site_id, settings.model_dump_json())
        with self._lock:
            if key not in self._grids:
                self._grids[key] = build_cost_grid(site, settings, None)
            return self._grids[key]

    def field(self, site: Site, settings: SafetySettings, suit: SuitModel) -> ReturnField:
        key = (site.site_id, settings.model_dump_json() + suit.model_dump_json())
        grid = self.grid(site, settings)
        with self._lock:
            if key not in self._fields:
                self._fields[key] = return_field(grid, LonLat(*site.manifest.habitat), suit)
            return self._fields[key]

    def clear(self) -> None:
        with self._lock:
            self._grids.clear()
            self._fields.clear()


def with_obstacles(grid: CostGrid, obstacles: list[Obstacle], buffer_m: float) -> CostGrid:
    """Copie de la grille où chaque obstacle (rayon + marge) est interdit."""
    if not obstacles:
        return grid
    cost = grid.cost.copy()
    forbidden = grid.forbidden.copy()
    a, _, c, _, e, f = grid.transform
    height, width = cost.shape
    for ob in obstacles:
        x, y = to_analysis(grid.site, ob.position[0], ob.position[1])
        r = ob.radius_m + buffer_m
        c0 = max(0, math.floor((x - r - c) / a))
        c1 = min(width, math.ceil((x + r - c) / a) + 1)
        r0 = max(0, math.floor((y + r - f) / e))
        r1 = min(height, math.ceil((y - r - f) / e) + 1)
        if c0 >= c1 or r0 >= r1:
            continue
        xs = c + a * (np.arange(c0, c1) + 0.5)
        ys = f + e * (np.arange(r0, r1) + 0.5)
        disc = np.hypot(xs[None, :] - x, ys[:, None] - y) <= r
        forbidden[r0:r1, c0:c1] |= disc
        cost[r0:r1, c0:c1][disc] = np.inf
    return replace(grid, cost=cost, forbidden=forbidden)


def return_time_s(field: ReturnField, position: LonLat) -> float | None:
    """Temps de retour vers l'habitat depuis ``position`` (``None`` hors grille)."""
    x, y = to_analysis(field.site, position[0], position[1])
    a, _, c, _, e, f = field.transform
    col = math.floor((x - c) / a)
    row = math.floor((y - f) / e)
    height, width = field.seconds.shape
    if not (0 <= row < height and 0 <= col < width):
        return None
    value = float(field.seconds[row, col])
    return value if math.isfinite(value) else None


# -- contournement géométrique ------------------------------------------------------


def _xy(site: Site, p: LonLat) -> tuple[float, float]:
    return to_analysis(site, p[0], p[1])


def _crossing(
    a: tuple[float, float], b: tuple[float, float], center: tuple[float, float], r: float
) -> tuple[float, float] | None:
    """Paramètres (t_entrée, t_sortie) où le segment ab coupe le disque, ou ``None``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - center[0], a[1] - center[1]
    qa = dx * dx + dy * dy
    qb = 2 * (fx * dx + fy * dy)
    qc = fx * fx + fy * fy - r * r
    if qa == 0:
        return (0.0, 0.0) if qc < 0 else None
    disc = qb * qb - 4 * qa * qc
    if disc <= 0:
        return None
    s = math.sqrt(disc)
    t0, t1 = (-qb - s) / (2 * qa), (-qb + s) / (2 * qa)
    if t1 <= 0 or t0 >= 1:
        return None
    return max(t0, 0.0), min(t1, 1.0)


def _arc(
    a: tuple[float, float],
    b: tuple[float, float],
    center: tuple[float, float],
    r: float,
    t: tuple[float, float],
) -> list[tuple[float, float]]:
    """Points autour du disque, du côté le plus court, entre l'entrée et la sortie."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    p_in = (a[0] + dx * t[0], a[1] + dy * t[0])
    p_out = (a[0] + dx * t[1], a[1] + dy * t[1])
    ang_in = math.atan2(p_in[1] - center[1], p_in[0] - center[0])
    ang_out = math.atan2(p_out[1] - center[1], p_out[0] - center[0])
    # Côté du contournement : celui où passe déjà le segment (point le plus proche du centre).
    tm = (t[0] + t[1]) / 2
    mid = (a[0] + dx * tm - center[0], a[1] + dy * tm - center[1])
    side = math.atan2(mid[1], mid[0]) if math.hypot(*mid) > 1e-6 else ang_in + math.pi / 2
    ccw = (ang_out - ang_in) % (2 * math.pi)

    def off_side(s: float) -> float:
        return abs((ang_in + s / 2 - side + math.pi) % (2 * math.pi) - math.pi)

    sweep = min((ccw, ccw - 2 * math.pi), key=off_side)
    step = math.radians(DETOUR_STEP_DEG)
    n = max(2, math.ceil(abs(sweep) / step))
    radius = r / math.cos(abs(sweep) / n / 2) * 1.02
    return [
        (
            center[0] + radius * math.cos(ang_in + sweep * k / n),
            center[1] + radius * math.sin(ang_in + sweep * k / n),
        )
        for k in range(n + 1)
    ]


def avoid_obstacles(
    site: Site, geom: RouteGeometry, obstacles: list[Obstacle], buffer_m: float
) -> RouteGeometry:
    """Insère un contournement là où le tracé traverse encore un obstacle."""
    if not obstacles:
        return geom
    coords = list(geom.coordinates)
    breaks = set(geom.segment_breaks)
    for ob in obstacles:
        center = _xy(site, ob.position)
        r = ob.radius_m + buffer_m
        out: list[LonLat] = []
        new_breaks: set[int] = set()
        for i, p in enumerate(coords):
            if i in breaks:
                new_breaks.add(len(out))
            out.append(p)
            if i + 1 >= len(coords):
                break
            a, b = _xy(site, p), _xy(site, coords[i + 1])
            t = _crossing(a, b, center, r)
            if t is None or t[0] == t[1]:
                continue
            for x, y in _arc(a, b, center, r, t):
                out.append(LonLat(*to_lonlat(site, x, y)))
        coords = out
        breaks = new_breaks
    return RouteGeometry(coordinates=coords, segment_breaks=sorted(breaks), cost=geom.cost)


def touches(site: Site, coords: list[LonLat], ob: Obstacle, buffer_m: float) -> bool:
    """Vrai si le tracé passe à moins de rayon + marge de l'obstacle."""
    center = _xy(site, ob.position)
    r = ob.radius_m + buffer_m
    pts = [_xy(site, p) for p in coords]
    if len(pts) == 1:
        return math.dist(pts[0], center) < r
    return any(_crossing(a, b, center, r) is not None for a, b in itertools.pairwise(pts))


def distance_to_line_m(site: Site, coords: list[LonLat], p: LonLat) -> float:
    """Distance de ``p`` au tracé, en mètres."""
    q = _xy(site, p)
    pts = [_xy(site, c) for c in coords]
    if len(pts) == 1:
        return math.dist(pts[0], q)
    best = math.inf
    for a, b in itertools.pairwise(pts):
        dx, dy = b[0] - a[0], b[1] - a[1]
        qa = dx * dx + dy * dy
        t = 0.0 if qa == 0 else max(0.0, min(1.0, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / qa))
        best = min(best, math.hypot(a[0] + dx * t - q[0], a[1] + dy * t - q[1]))
    return best


# -- assemblage d'un itinéraire --------------------------------------------------------


def stop_target(target_id: str, site_id: str, position: LonLat, work_time_s: float) -> Target:
    """Cible minimale reconstituée depuis un tronçon (A4 ne lit pas la base de A2)."""
    epoch = datetime(2000, 1, 1, tzinfo=UTC)
    return Target(
        id=target_id,
        site_id=site_id,
        name=target_id,
        position=position,
        work_time_s=work_time_s,
        created_at=epoch,
        updated_at=epoch,
    )


@dataclass(frozen=True)
class LocalPlan:
    site: Site
    settings: SafetySettings
    suit: SuitModel
    conditions: Conditions | None
    variant: RouteVariant
    obstacles: list[Obstacle]


def compute_route(
    lp: LocalPlan,
    cache: GridCache,
    start: LonLat,
    targets: list[Target],
    end: LonLat,
    route_id: str,
    reason: str,
) -> Route:
    """Itinéraire de ``start`` à ``end`` par ``targets`` en évitant les obstacles signalés."""
    site = lp.site
    grid = with_obstacles(
        cache.grid(site, lp.settings), lp.obstacles, lp.settings.obstacle_buffer_m
    )
    options = RouteOptions(
        variant=lp.variant,
        variants=[lp.variant],
        return_to=end,
        optimize_order=False,
        suit=lp.suit,
        conditions=lp.conditions,
    )
    waypoints = [LonLat(*start), *[LonLat(*t.position) for t in targets], LonLat(*end)]
    geom = plan_route(grid, waypoints, options)
    geom = avoid_obstacles(site, geom, lp.obstacles, lp.settings.obstacle_buffer_m)
    est = estimate_route(site, geom, targets, lp.suit, lp.conditions)
    field = cache.field(site, lp.settings, lp.suit)
    breaks = [*geom.segment_breaks, len(geom.coordinates) - 1]
    segments: list[RouteSegment] = []
    explanation: list[SegmentExplanation] = []
    for i, s in enumerate(est.segments):
        a = geom.coordinates[breaks[i]]
        b = geom.coordinates[breaks[i + 1]]
        segments.append(
            RouteSegment(
                index=i,
                from_point=a,
                to_point=b,
                from_target_id=targets[i - 1].id if 0 < i <= len(targets) else None,
                to_target_id=targets[i].id if i < len(targets) else None,
                distance_m=round(s.distance_m, 2),
                duration_s=round(s.walk_time_s, 1),
                ascent_m=round(s.ascent_m, 2),
                descent_m=round(s.descent_m, 2),
                max_slope_deg=round(s.max_slope_deg, 2),
                consumption=Consumption(
                    oxygen_kg=round(s.oxygen_kg, 4),
                    battery_wh=round(s.battery_wh, 2),
                    water_l=round(s.water_l, 3),
                    dose_usv=round(s.dose_usv, 2),
                ),
                work_time_s=s.work_time_s,
            )
        )
        mid = LonLat((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        terms = explain_cell(grid, *to_analysis(site, mid[0], mid[1]))
        explanation.append(
            SegmentExplanation(segment_index=i, reasons=[reason, *[t.reason for t in terms]])
        )
    profile = [
        ProfileSample(
            distance_m=round(d, 2),
            position=p,
            elevation_m=None if el is None else round(el, 2),
            slope_deg=None if sl is None else round(sl, 2),
            time_s=round(t, 1),
            segment_index=si,
        )
        for d, p, el, sl, t, si in zip(
            est.samples_distance_m,
            est.samples_position,
            est.samples_elevation_m,
            est.samples_slope_deg,
            est.samples_time_s,
            est.samples_segment,
            strict=True,
        )
    ]
    totals = RouteTotals(
        distance_m=round(sum(s.distance_m for s in segments), 2),
        walk_time_s=round(sum(s.duration_s for s in segments), 1),
        work_time_s=sum(s.work_time_s for s in segments),
        duration_s=round(sum(s.duration_s + s.work_time_s for s in segments), 1),
        ascent_m=round(sum(s.ascent_m for s in segments), 2),
        descent_m=round(sum(s.descent_m for s in segments), 2),
        max_slope_deg=max((s.max_slope_deg for s in segments), default=0.0),
        consumption=Consumption(
            oxygen_kg=round(sum(s.consumption.oxygen_kg for s in segments), 4),
            battery_wh=round(sum(s.consumption.battery_wh for s in segments), 2),
            water_l=round(sum(s.consumption.water_l for s in segments), 3),
            dose_usv=round(sum(s.consumption.dose_usv for s in segments), 2),
        ),
    )
    warnings = list(grid.warnings)
    if any(touches(site, list(geom.coordinates), ob, 0.0) for ob in lp.obstacles):
        warnings.append("le tracé recalculé passe encore près d'un obstacle signalé")
    return Route(
        id=route_id,
        variant=lp.variant,
        geometry=LineStringGeometry(coordinates=list(geom.coordinates)),
        segments=segments,
        profile=profile,
        totals=totals,
        return_check=return_check(est, field, lp.suit),
        explanation=explanation,
        warnings=warnings,
    )
