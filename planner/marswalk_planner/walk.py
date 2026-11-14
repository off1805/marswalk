"""Modèle de marche (P3). BOUCHON de T00 : 1 m/s, consommation constante.

Signatures gelées :
- ``walking_speed(slope_deg, soil_class, suit) -> float`` (m/s)
- ``estimate_route(site, geometry, targets, suit, conditions) -> RouteEstimate``
  (profil échantillonné tous les 5 m)
"""

from __future__ import annotations

import itertools
import math

from marswalk_core.geodesy import distance_m
from marswalk_core.grids import RouteEstimate, RouteGeometry, SegmentEstimate
from marswalk_core.schemas import Conditions, LonLat, SuitModel, Target
from marswalk_core.site_package import Site

PROFILE_STEP_M = 5.0


def walking_speed(slope_deg: float, soil_class: int, suit: SuitModel) -> float:
    return 1.0


def _lerp(a: LonLat, b: LonLat, t: float) -> LonLat:
    return LonLat(a.lon + (b.lon - a.lon) * t, a.lat + (b.lat - a.lat) * t)


def estimate_route(
    site: Site,
    geometry: RouteGeometry,
    targets: list[Target],
    suit: SuitModel,
    conditions: Conditions | None,
) -> RouteEstimate:
    """``targets`` : cible d'arrivée de chaque tronçon, dans l'ordre (le dernier tronçon
    revient à l'habitat et n'a pas de cible)."""
    dose_rate = (conditions.dose_rate_usv_h if conditions else None) or 10.0
    coords = geometry.coordinates
    breaks = [*geometry.segment_breaks, len(coords) - 1]
    est = RouteEstimate([], [], [], [], [], [], [])
    total_d = 0.0
    total_t = 0.0
    for seg_index in range(len(breaks) - 1):
        seg_pts = coords[breaks[seg_index] : breaks[seg_index + 1] + 1]
        seg_d = 0.0
        ascent = descent = max_slope = 0.0
        prev_elev: float | None = None
        for a, b in itertools.pairwise(seg_pts):
            leg = distance_m(a, b)
            n = max(1, math.ceil(leg / PROFILE_STEP_M))
            for k in range(n + (1 if b == seg_pts[-1] else 0)):
                p = _lerp(a, b, min(1.0, k / n))
                d = total_d + seg_d + leg * min(1.0, k / n)
                elev = site.sample("dem", p.lon, p.lat)
                slope = site.sample("slope", p.lon, p.lat)
                if elev is not None and prev_elev is not None:
                    ascent += max(0.0, elev - prev_elev)
                    descent += max(0.0, prev_elev - elev)
                prev_elev = elev if elev is not None else prev_elev
                max_slope = max(max_slope, slope or 0.0)
                est.samples_distance_m.append(d)
                est.samples_position.append(p)
                est.samples_elevation_m.append(elev)
                est.samples_slope_deg.append(slope)
                est.samples_time_s.append(total_t + (d - total_d) / 1.0)
                est.samples_segment.append(seg_index)
            seg_d += leg
        walk_t = seg_d / walking_speed(0.0, 0, suit)
        target = targets[seg_index] if seg_index < len(targets) else None
        work_t = target.work_time_s if target else 0.0
        hours = (walk_t + work_t) / 3600.0
        est.segments.append(
            SegmentEstimate(
                distance_m=seg_d,
                walk_time_s=walk_t,
                work_time_s=work_t,
                ascent_m=ascent,
                descent_m=descent,
                max_slope_deg=max_slope,
                oxygen_kg=suit.oxygen_rate_kg_h * hours,
                battery_wh=suit.battery_rate_w * hours,
                water_l=suit.water_rate_l_h * hours,
                dose_usv=dose_rate * hours,
            )
        )
        total_d += seg_d
        total_t += walk_t + work_t
    return est
