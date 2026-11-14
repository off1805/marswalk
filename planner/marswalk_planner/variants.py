"""Variantes d'itinéraire (P2). BOUCHON de T00 : trois variantes en ligne droite.

Signature gelée : ``plan_variants(site, settings, start, targets, options) -> list[Route]``.
"""

from __future__ import annotations

from marswalk_core.config import load_suit
from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import (
    Consumption,
    LineStringGeometry,
    LonLat,
    ProfileSample,
    Route,
    RouteSegment,
    RouteTotals,
    SafetySettings,
    SegmentExplanation,
    Target,
)
from marswalk_core.site_package import Site
from marswalk_planner.budget import return_check
from marswalk_planner.cost import build_cost_grid, explain_cell
from marswalk_planner.order import order_targets
from marswalk_planner.return_field import return_field
from marswalk_planner.route import plan_route
from marswalk_planner.walk import estimate_route


def plan_variants(
    site: Site,
    settings: SafetySettings,
    start: LonLat,
    targets: list[Target],
    options: RouteOptions,
) -> list[Route]:
    suit = options.suit or load_suit()
    grid = build_cost_grid(site, settings, options.conditions)
    end = options.return_to or start
    ordered = order_targets(grid, start, targets, options) if options.optimize_order else targets
    field = return_field(grid, LonLat(*site.manifest.habitat), suit)
    routes: list[Route] = []
    for variant in options.variants:
        waypoints = [LonLat(*start), *[t.position for t in ordered], LonLat(*end)]
        geom = plan_route(grid, waypoints, options)
        est = estimate_route(site, geom, ordered, suit, options.conditions)
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
            terms = explain_cell(grid, *to_analysis(site, mid.lon, mid.lat))
            reasons = ["bouchon T00 : ligne droite"] + [t.reason for t in terms]
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
        routes.append(
            Route(
                id=f"route-{variant.value}",
                variant=variant,
                geometry=LineStringGeometry(coordinates=list(geom.coordinates)),
                segments=segments,
                profile=profile,
                totals=totals,
                return_check=return_check(est, field, suit),
                explanation=explanation,
                warnings=[*grid.warnings, "bouchon T00 : les trois variantes sont identiques"],
            )
        )
    return routes
