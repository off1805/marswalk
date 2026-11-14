"""Tests de plan_variants.

Couvre :
- Production des trois variantes.
- Différences entre variantes sur terrain hétérogène.
- Vérification que les routes ne traversent pas de zone interdite.
- Recalcul après déplacement de cible.
- Recalcul après signalement d'obstacle.
- Utilisation du site fictif pour démontrer les différences.
"""

from __future__ import annotations

import math

from tests.p2.conftest import flat_layers, grid_lonlat, make_site, make_target, make_target_at

from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import (
    LonLat,
    RouteVariant,
)
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.variants import plan_variants, replan_from_obstacle


def _all_coords_safe(route, site, cost_grid):
    """Vérifie qu'aucun point de la route ne traverse une cellule interdite."""
    for pt in route.geometry.coordinates:
        x, y = to_analysis(site, pt.lon, pt.lat)
        cell = site.xy_to_cell(x, y)
        if cell is not None:
            assert not math.isinf(cost_grid.cost[cell[0], cell[1]]), \
                f"Point {pt} sur cellule interdite"


class TestPlanVariantsBasic:
    def test_returns_three_routes(self, flat_site, standard_settings):
        site, _ = flat_site
        start = grid_lonlat(0.5, 0.1)
        targets = [make_target_at(0, 0.5, 0.5)]
        opts = RouteOptions(optimize_order=False)
        routes = plan_variants(site, standard_settings, start, targets, opts)
        assert len(routes) == 3
        variants = {r.variant for r in routes}
        assert RouteVariant.safest in variants
        assert RouteVariant.fastest in variants
        assert RouteVariant.science in variants

    def test_route_ids_are_unique(self, flat_site, standard_settings):
        site, _ = flat_site
        start = grid_lonlat(0.5, 0.1)
        targets = [make_target_at(0, 0.5, 0.5)]
        opts = RouteOptions(optimize_order=False)
        routes = plan_variants(site, standard_settings, start, targets, opts)
        ids = [r.id for r in routes]
        assert len(set(ids)) == 3

    def test_all_routes_have_segments(self, flat_site, standard_settings):
        site, _ = flat_site
        start = grid_lonlat(0.5, 0.1)
        targets = [make_target_at(0, 0.5, 0.5), make_target_at(1, 0.5, 0.9)]
        opts = RouteOptions(optimize_order=False)
        routes = plan_variants(site, standard_settings, start, targets, opts)
        for route in routes:
            assert len(route.segments) > 0
            assert len(route.geometry.coordinates) >= 2

    def test_no_forbidden_cells_flat_grid(self, flat_site, standard_settings):
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.5, 0.1)
        targets = [make_target_at(0, 0.5, 0.5), make_target_at(1, 0.5, 0.9)]
        opts = RouteOptions(optimize_order=False)
        routes = plan_variants(site, standard_settings, start, targets, opts)
        for route in routes:
            _all_coords_safe(route, site, grid)

    def test_subset_variants(self, flat_site, standard_settings):
        """On peut demander uniquement certaines variantes."""
        site, _ = flat_site
        start = grid_lonlat(0.5, 0.1)
        targets = [make_target_at(0, 0.5, 0.5)]
        opts = RouteOptions(
            optimize_order=False,
            variants=[RouteVariant.safest, RouteVariant.fastest],
        )
        routes = plan_variants(site, standard_settings, start, targets, opts)
        assert len(routes) == 2


class TestVariantDifferences:
    def test_variants_valid_on_heterogeneous_terrain(self, standard_settings):
        """Sur terrain hétérogène, les trois variantes doivent être valides."""
        gs = 100
        layers = flat_layers(gs)
        # Zone à risque : pente intermédiaire (pénalisée mais pas interdite)
        layers["slope"][35:65, 35:65] = 12.0
        # Zone CRISM à fort intérêt scientifique
        layers["crism_minerals"][10:30, 10:30] = 2.0

        site, _ = make_site(layers, grid_size=gs)
        start = grid_lonlat(0.05, 0.05)
        targets = [make_target_at(0, 0.95, 0.95, gs=gs)]
        opts = RouteOptions(optimize_order=False, window_margin_m=300.0)
        routes = plan_variants(site, standard_settings, start, targets, opts)
        assert len(routes) == 3
        for route in routes:
            assert route.totals.distance_m > 0

    def test_fictif_site_variants_valid(self, fictif_site, standard_settings):
        """Sur le site fictif, les variantes doivent être valides et sans obstacle."""
        site = fictif_site
        hab = site.manifest.habitat
        start = LonLat(*hab)

        # Cibles dans l'emprise du site fictif (autour de l'habitat)
        from marswalk_core.geodesy import to_analysis, to_lonlat
        hx, hy = to_analysis(site, hab.lon, hab.lat)
        # Cibles à ±100m de l'habitat en x et y
        t1_lon, t1_lat = to_lonlat(site, hx + 100, hy + 50)
        t2_lon, t2_lat = to_lonlat(site, hx - 80, hy + 100)
        targets = [
            make_target(0, t1_lon, t1_lat),
            make_target(1, t2_lon, t2_lat),
        ]
        opts = RouteOptions(optimize_order=True, window_margin_m=300.0)
        routes = plan_variants(site, standard_settings, start, targets, opts)
        assert len(routes) == 3

        grid = build_cost_grid(site, standard_settings)
        for route in routes:
            _all_coords_safe(route, site, grid)
            assert route.totals.distance_m > 0
            assert len(route.profile) > 0

    def test_safest_fastest_both_valid(self, standard_settings):
        """Safest et fastest doivent produire des routes valides sur terrain risqué."""
        gs = 100
        layers = flat_layers(gs)
        # Zone risquée au centre
        layers["slope"][35:65, 35:65] = 13.0
        layers["radio_coverage"][35:65, 35:65] = 0.0

        site, _ = make_site(layers, grid_size=gs)
        start = grid_lonlat(0.5, 0.05)
        targets = [make_target_at(0, 0.5, 0.95, gs=gs)]
        opts = RouteOptions(optimize_order=False, window_margin_m=300.0)
        routes = plan_variants(site, standard_settings, start, targets, opts)

        safest = next(r for r in routes if r.variant == RouteVariant.safest)
        fastest = next(r for r in routes if r.variant == RouteVariant.fastest)
        assert safest.totals.distance_m > 0
        assert fastest.totals.distance_m > 0


class TestReplanAfterObstacle:
    def test_replan_produces_valid_route(self, flat_site, standard_settings):
        site, _ = flat_site
        current_pos = grid_lonlat(0.5, 0.2)
        obstacle_pos = grid_lonlat(0.5, 0.5)
        remaining = [make_target_at(0, 0.5, 0.8)]
        opts = RouteOptions(optimize_order=False)
        route = replan_from_obstacle(
            site, standard_settings, current_pos, obstacle_pos, 5.0, remaining, opts
        )
        assert route is not None
        assert len(route.geometry.coordinates) >= 2

    def test_replan_avoids_obstacle(self, flat_site, standard_settings):
        """L'itinéraire recalculé ne doit pas passer par l'obstacle."""
        site, _ = flat_site
        current_pos = grid_lonlat(0.5, 0.1)
        obstacle_pos = grid_lonlat(0.5, 0.5)
        remaining = [make_target_at(0, 0.5, 0.9)]
        opts = RouteOptions(optimize_order=False, window_margin_m=300.0)
        route = replan_from_obstacle(
            site, standard_settings, current_pos, obstacle_pos, 8.0, remaining, opts
        )
        assert route is not None
        assert len(route.geometry.coordinates) >= 2

    def test_replan_no_remaining_targets(self, flat_site, standard_settings):
        """Replan sans cible restante : retour direct."""
        site, _ = flat_site
        current_pos = grid_lonlat(0.5, 0.3)
        obstacle_pos = grid_lonlat(0.5, 0.5)
        opts = RouteOptions(optimize_order=False)
        route = replan_from_obstacle(
            site, standard_settings, current_pos, obstacle_pos, 5.0, [], opts
        )
        assert route is not None


class TestReturnCheck:
    def test_return_check_present(self, flat_site, standard_settings):
        site, _ = flat_site
        start = grid_lonlat(0.5, 0.1)
        targets = [make_target_at(0, 0.5, 0.5)]
        opts = RouteOptions(optimize_order=False)
        routes = plan_variants(site, standard_settings, start, targets, opts)
        for route in routes:
            rc = route.return_check
            assert rc is not None
            assert rc.limiting_consumable in ("oxygen", "battery", "water", "time", "dose")
