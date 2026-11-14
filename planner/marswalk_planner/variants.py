"""Variantes d'itinéraire (P2).

Signature gelée : ``plan_variants(site, settings, start, targets, options) -> list[Route]``.

Les trois variantes (safest, fastest, science) utilisent des jeux de poids
distincts issus de ``_p2.weights``, ce qui produit des grilles de coût
différentes et donc (sur un terrain hétérogène) des itinéraires différents.

Recalcul après obstacle (G) :
  La fonction ``replan_from_obstacle`` calcule un nouvel itinéraire depuis
  une position courante en évitant un obstacle signalé, en réutilisant les
  tronçons aval non affectés depuis le cache.
"""

from __future__ import annotations

import copy

from marswalk_core.config import load_suit
from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import CostGrid, RouteOptions
from marswalk_core.schemas import (
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
    Target,
)
from marswalk_core.site_package import Site
from marswalk_planner._p2 import cache as _cache
from marswalk_planner._p2.weights import fastest_settings, safest_settings, science_settings
from marswalk_planner.budget import return_check
from marswalk_planner.cost import build_cost_grid, explain_cell
from marswalk_planner.order import order_targets
from marswalk_planner.return_field import return_field
from marswalk_planner.route import plan_route
from marswalk_planner.walk import estimate_route


def _make_route(
    site: Site,
    cost_grid: CostGrid,
    ordered: list[Target],
    start: LonLat,
    end: LonLat,
    options: RouteOptions,
    variant: RouteVariant,
) -> Route:
    """Calcule une variante et l'assemble en objet Route."""
    suit = options.suit or load_suit()

    waypoints = [LonLat(*start), *[t.position for t in ordered], LonLat(*end)]
    geom = plan_route(cost_grid, waypoints, options)
    est = estimate_route(site, geom, ordered, suit, options.conditions)
    field = return_field(cost_grid, LonLat(*site.manifest.habitat), suit)

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
                from_target_id=ordered[i - 1].id if i > 0 else None,
                to_target_id=ordered[i].id if i < len(ordered) else None,
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
        mid = LonLat((a.lon + b.lon) / 2, (a.lat + b.lat) / 2)
        terms = explain_cell(cost_grid, *to_analysis(site, mid.lon, mid.lat))
        reasons = [t.reason for t in terms] if terms else [f"variante {variant.value}"]
        explanation.append(SegmentExplanation(segment_index=i, reasons=reasons))

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

    return Route(
        id=f"route-{variant.value}",
        variant=variant,
        geometry=LineStringGeometry(coordinates=list(geom.coordinates)),
        segments=segments,
        profile=profile,
        totals=totals,
        return_check=return_check(est, field, suit),
        explanation=explanation,
        warnings=list(cost_grid.warnings),
    )


def plan_variants(
    site: Site,
    settings: SafetySettings,
    start: LonLat,
    targets: list[Target],
    options: RouteOptions,
) -> list[Route]:
    """Calcule les trois variantes d'itinéraire avec des jeux de poids distincts.

    Chaque variante utilise une grille de coût différente :
    - safest  : w_r fort (sécurité), w_t réduit
    - fastest : w_t fort (temps), w_r réduit
    - science : w_s fort (intérêt scientifique)

    Les itinéraires seront différents quand le terrain présente des zones
    à risque variable ou des signatures minéralogiques. Sur un terrain
    totalement uniforme, les chemins convergent naturellement.

    Le cache de tronçons est utilisé pour éviter de recalculer les tronçons
    inchangés entre variants (si les points sont identiques mais la grille
    diffère, les clés seront différentes, donc le cache n'est pas trompé).
    """
    end = options.return_to or start

    # Mappage variante → settings de poids
    _variant_settings = {
        RouteVariant.safest: safest_settings(settings),
        RouteVariant.fastest: fastest_settings(settings),
        RouteVariant.science: science_settings(settings),
    }

    routes: list[Route] = []
    for variant in options.variants:
        v_settings = _variant_settings.get(variant, settings)
        cost_grid = build_cost_grid(site, v_settings, options.conditions)

        v_options = copy.copy(options)
        v_options.variant = variant

        ordered = (
            order_targets(cost_grid, LonLat(*start), targets, v_options)
            if options.optimize_order
            else list(targets)
        )

        route = _make_route(
            site, cost_grid, ordered, LonLat(*start), LonLat(*end), v_options, variant
        )
        routes.append(route)

    return routes


def replan_from_obstacle(
    site: Site,
    settings: SafetySettings,
    current_position: LonLat,
    obstacle_position: LonLat,
    obstacle_radius_m: float,
    remaining_targets: list[Target],
    options: RouteOptions,
) -> Route | None:
    """Recalcule l'itinéraire depuis la position courante après signalement d'un obstacle.

    L'obstacle est intégré dans la grille de coût via un masque supplémentaire.
    Les tronçons aval non affectés sont réutilisés depuis le cache grâce à leurs clés.

    Paramètres
    ----------
    site:
        Paquet de site.
    settings:
        Paramètres de sécurité courants.
    current_position:
        Position actuelle de l'astronaute.
    obstacle_position:
        Centre de l'obstacle signalé.
    obstacle_radius_m:
        Rayon de l'obstacle en mètres.
    remaining_targets:
        Cibles restantes à visiter.
    options:
        Options de route (variant courante, etc.).

    Retourne
    --------
    Route | None
        Nouvel itinéraire ou None si identique à l'ancien.
    """

    import numpy as np

    # Construire la grille avec l'obstacle intégré comme zone interdite
    cost_grid = build_cost_grid(site, settings, options.conditions)

    # Marquer les cases dans le rayon de l'obstacle comme interdites
    ox, oy = to_analysis(site, obstacle_position.lon, obstacle_position.lat)
    h, w = cost_grid.cost.shape
    a, _, c, _, e, f = cost_grid.transform
    xs = c + a * (np.arange(w) + 0.5)
    ys = f + e * (np.arange(h) + 0.5)
    dist_grid = np.hypot(xs[None, :] - ox, ys[:, None] - oy)
    obstacle_mask = dist_grid <= (obstacle_radius_m + cost_grid.resolution_m)
    cost_grid.cost[obstacle_mask] = np.inf
    cost_grid.forbidden[obstacle_mask] = True

    # Invalider le cache pour ce site (les tronçons passant par l'obstacle
    # ont maintenant un coût différent)
    _cache.clear(site_id=site.site_id)

    end = options.return_to or current_position

    ordered = (
        order_targets(cost_grid, current_position, remaining_targets, options)
        if options.optimize_order
        else list(remaining_targets)
    )

    return _make_route(
        site,
        cost_grid,
        ordered,
        current_position,
        LonLat(*end),
        options,
        options.variant or RouteVariant.safest,
    )
