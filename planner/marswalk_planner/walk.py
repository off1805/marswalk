"""Modèle de marche, profil et budgets par tronçon (P3).

Vitesse de type Tobler adaptée à 0,38 g et à une combinaison rigide xEMU.
Chaque paramètre est sourcé dans docs/science/hypotheses-marche.md.

Signatures gelées (taches-agents.md §7) :
- ``walking_speed(slope_deg, soil_class, suit) -> float``  (m/s)
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

# ---------------------------------------------------------------------------
# Modèle Tobler adapté à Mars 0,38 g
# ---------------------------------------------------------------------------
# Tobler terrestre : W(s) = 6·exp(−3.5·|tan(s)+0.05|) km/h (Tobler 1993).
# Adaptation martienne :
#   – La gravité réduite diminue l'asymétrie montée/descente :
#     offset 0.025 (au lieu de 0.05 sur Terre), calé sur Jansen et al. 2024.
#   – La normalisation assure que walking_speed(0°, roche, suit) == base_speed_mps
#     et que le maximum (à ~−1.4°) vaut max_speed_mps.

_TOBLER_OFFSET: float = 0.025  # tan(optimal_slope) ≈ −0.025, soit ~−1.4° de descente
_TOBLER_SCALE: float = 3.5  # pente de décroissance (conservée de Tobler 1993)

# Noyau à pente nulle : exp(−3.5 × 0.025)
_KERNEL_AT_ZERO: float = math.exp(-_TOBLER_SCALE * _TOBLER_OFFSET)  # ≈ 0.9161
# Noyau à la pente optimale (tan(s) = −offset → |tan+offset| = 0) : exp(0) = 1.0
_KERNEL_MAX: float = 1.0


def _tobler_kernel(slope_deg: float) -> float:
    """Noyau de Tobler martien ∈ (0, 1]. Maximum à tan(s) = −0.025 (≈ −1.4°)."""
    slope_rad = math.radians(slope_deg)
    return math.exp(-_TOBLER_SCALE * abs(math.tan(slope_rad) + _TOBLER_OFFSET))


def walking_speed(slope_deg: float, soil_class: int, suit: SuitModel) -> float:
    """Vitesse de marche en m/s.

    Modèle Tobler adapté Mars 0,38 g + facteur de sol.
    - Maximum autour de 0 à −5° de descente (≈ suit.max_speed_mps).
    - Décroissant symétriquement aux pentes fortes.
    - À pente nulle sur roche : retourne suit.base_speed_mps.

    Sources : Tobler 1993 ; Waligora & Horrigan 1975 (NASA SP-368) ;
              Jansen et al. 2024 (NPJ Microgravity 10, 7).
    """
    kernel = _tobler_kernel(slope_deg)
    # Normalisation : v(0°, roche) = base_speed_mps
    #   base_speed = max_speed × (kernel_at_zero / kernel_max)
    #   → max_speed = base_speed / (kernel_at_zero / kernel_max)
    #   → v(s) = max_speed × kernel(s)
    max_v = suit.base_speed_mps / _KERNEL_AT_ZERO  # vitesse à la pente optimale
    v = max_v * kernel

    # Facteur de sol (clamp à l'intervalle valide)
    factors = suit.soil_speed_factor
    idx = max(0, min(len(factors) - 1, int(soil_class)))
    v *= factors[idx]

    # Clamp : vitesse minimale 0.1 m/s, maximale suit.max_speed_mps
    return float(max(0.1, min(suit.max_speed_mps, v)))


# ---------------------------------------------------------------------------
# Utilitaires internes
# ---------------------------------------------------------------------------


def _lerp(a: LonLat, b: LonLat, t: float) -> LonLat:
    return LonLat(a.lon + (b.lon - a.lon) * t, a.lat + (b.lat - a.lat) * t)


def _effort_factor(v_actual: float, suit: SuitModel) -> float:
    """Facteur d'effort ∈ [1.0, 1.5] pour l'O₂ et l'eau.

    Effort croît linéairement de 1.0 (vitesse de base) à 1.5 (vitesse max).
    Source : Waligora & Horrigan 1975 (métabolisme EVA Apollo).
    """
    span = suit.max_speed_mps - suit.base_speed_mps
    if span <= 0.0:
        return 1.0
    factor = 1.0 + 0.5 * max(0.0, v_actual - suit.base_speed_mps) / span
    return min(1.5, factor)


# ---------------------------------------------------------------------------
# Estimation du profil et des budgets
# ---------------------------------------------------------------------------


def estimate_route(
    site: Site,
    geometry: RouteGeometry,
    targets: list[Target],
    suit: SuitModel,
    conditions: Conditions | None,
) -> RouteEstimate:
    """Profil échantillonné tous les PROFILE_STEP_M mètres et budgets par tronçon.

    ``targets`` : cible d'arrivée de chaque tronçon, dans l'ordre.
    Le dernier tronçon revient à l'habitat et n'a pas de cible.

    La vitesse de chaque sous-segment est calculée avec ``walking_speed``
    à partir de la pente et de la classe de sol lues dans le paquet de site.
    La consommation d'O₂ et d'eau intègre le facteur d'effort.
    La dose est proportionnelle à la durée (conditions.dose_rate_usv_h ou 10 µSv/h).
    """
    dose_rate = (conditions.dose_rate_usv_h if conditions else None) or 10.0

    coords = geometry.coordinates
    # breaks[i] = index du premier point du tronçon i dans coords
    breaks = [*geometry.segment_breaks, len(coords) - 1]

    est = RouteEstimate(
        segments=[],
        samples_distance_m=[],
        samples_position=[],
        samples_elevation_m=[],
        samples_slope_deg=[],
        samples_time_s=[],
        samples_segment=[],
    )

    total_d = 0.0  # distance cumulée (m)
    total_t = 0.0  # temps cumulé, marche + travail (s)

    for seg_index in range(len(breaks) - 1):
        seg_pts = coords[breaks[seg_index] : breaks[seg_index + 1] + 1]

        seg_d = 0.0
        seg_walk_t = 0.0
        ascent = descent = max_slope = 0.0
        oxygen_kg = battery_wh = water_l = dose_usv = 0.0
        prev_elev: float | None = None

        # Emit first sample at the start of the segment (before iterating pairs)
        p0 = seg_pts[0]
        elev0 = site.sample("dem", p0.lon, p0.lat)
        slope0 = site.sample("slope", p0.lon, p0.lat)
        est.samples_distance_m.append(total_d)
        est.samples_position.append(p0)
        est.samples_elevation_m.append(elev0)
        est.samples_slope_deg.append(slope0)
        est.samples_time_s.append(total_t)
        est.samples_segment.append(seg_index)
        prev_elev = elev0

        for a, b in itertools.pairwise(seg_pts):
            leg = distance_m(a, b)
            if leg < 1e-9:
                continue
            # Number of sub-steps along this leg
            n_steps = max(1, math.ceil(leg / PROFILE_STEP_M))
            step_d = leg / n_steps

            for k in range(n_steps):
                t_start = k / n_steps
                t_end = (k + 1) / n_steps
                _lerp(a, b, t_start)
                p_end = _lerp(a, b, t_end)

                # Sample terrain at mid-point of sub-step for best accuracy
                p_mid = _lerp(a, b, (t_start + t_end) / 2.0)
                slope_v = site.sample("slope", p_mid.lon, p_mid.lat)
                slope_here = slope_v if slope_v is not None else 0.0
                soil_v = site.sample("loose_soil", p_mid.lon, p_mid.lat)
                soil_class = round(soil_v) if soil_v is not None else 0

                elev_end = site.sample("dem", p_end.lon, p_end.lat)
                if elev_end is not None and prev_elev is not None:
                    dh = elev_end - prev_elev
                    ascent += max(0.0, dh)
                    descent += max(0.0, -dh)
                prev_elev = elev_end if elev_end is not None else prev_elev
                max_slope = max(max_slope, slope_here)

                # Walking speed for this sub-step
                v = walking_speed(slope_here, soil_class, suit)
                dt = step_d / v
                seg_walk_t += dt
                seg_d += step_d

                # Consumables for this sub-step
                ef = _effort_factor(v, suit)
                hours = dt / 3600.0
                oxygen_kg += suit.oxygen_rate_kg_h * ef * hours
                battery_wh += suit.battery_rate_w * hours
                water_l += suit.water_rate_l_h * ef * hours
                dose_usv += dose_rate * hours

                # Profile sample at end of sub-step
                slope_end = site.sample("slope", p_end.lon, p_end.lat)
                est.samples_distance_m.append(total_d + seg_d)
                est.samples_position.append(p_end)
                est.samples_elevation_m.append(elev_end)
                est.samples_slope_deg.append(slope_end)
                est.samples_time_s.append(total_t + seg_walk_t)
                est.samples_segment.append(seg_index)

        target = targets[seg_index] if seg_index < len(targets) else None
        work_t = target.work_time_s if target else 0.0

        est.segments.append(
            SegmentEstimate(
                distance_m=seg_d,
                walk_time_s=seg_walk_t,
                work_time_s=work_t,
                ascent_m=ascent,
                descent_m=descent,
                max_slope_deg=max_slope,
                oxygen_kg=oxygen_kg,
                battery_wh=battery_wh,
                water_l=water_l,
                dose_usv=dose_usv,
            )
        )
        total_d += seg_d
        total_t += seg_walk_t + work_t

    return est
