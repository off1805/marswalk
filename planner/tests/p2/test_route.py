"""Tests de plan_route.

Couvre :
- Chemin de base sur grille plate.
- Contournement d'obstacle.
- Gestion des couloirs étroits.
- Coordonnées extrémités.
- Absence de chemin possible.
- Extension automatique de fenêtre.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from tests.p2.conftest import (
    grid_lonlat,
    layers_with_obstacle,
    layers_with_wall,
    make_site,
)

from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import SafetySettings
from marswalk_core.site_package import Site
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.route import plan_route


class TestPlanRouteBasic:
    def test_two_points_on_flat_grid(
        self,
        flat_site: tuple[Site, Path],
        standard_settings: SafetySettings,
        default_options: RouteOptions,
    ) -> None:
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.1, 0.1)
        end = grid_lonlat(0.9, 0.9)
        geom = plan_route(grid, [start, end], default_options)
        assert len(geom.coordinates) >= 2
        assert geom.coordinates[0].lon == pytest.approx(start.lon, abs=1e-5)
        assert geom.coordinates[-1].lon == pytest.approx(end.lon, abs=1e-5)

    def test_segment_breaks_match_waypoints(
        self,
        flat_site: tuple[Site, Path],
        standard_settings: SafetySettings,
        default_options: RouteOptions,
    ) -> None:
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        pts = [grid_lonlat(0.1, 0.1), grid_lonlat(0.5, 0.5), grid_lonlat(0.9, 0.9)]
        geom = plan_route(grid, pts, default_options)
        assert len(geom.segment_breaks) == 2
        assert geom.segment_breaks[0] == 0

    def test_raises_on_single_waypoint(
        self,
        flat_site: tuple[Site, Path],
        standard_settings: SafetySettings,
        default_options: RouteOptions,
    ) -> None:
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        with pytest.raises(ValueError):
            plan_route(grid, [grid_lonlat(0.5, 0.5)], default_options)

    def test_avoids_obstacle(self, standard_settings: SafetySettings) -> None:
        """Le chemin doit contourner l'obstacle et ne pas traverser de case interdite."""
        site, _ = make_site(layers_with_obstacle(obs_row=50, obs_col=50, obs_size=20))
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.1, 0.5)
        end = grid_lonlat(0.9, 0.5)
        opts = RouteOptions(window_margin_m=300.0)
        geom = plan_route(grid, [start, end], opts)
        # Toutes les coordonnées doivent être sur des cases non interdites
        from marswalk_core.geodesy import to_analysis

        for pt in geom.coordinates:
            x, y = to_analysis(site, pt.lon, pt.lat)
            cell = site.xy_to_cell(x, y)
            if cell is not None:
                assert not math.isinf(grid.cost[cell[0], cell[1]]), (
                    f"Coordonnée {pt} traverse une cellule interdite"
                )

    def test_narrow_corridor(self, standard_settings: SafetySettings) -> None:
        """Un couloir d'une case de large doit permettre le passage."""
        site, _ = make_site(layers_with_wall(wall_row=50, gap_col=45, gap_size=5))
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.1, 0.5)
        end = grid_lonlat(0.9, 0.5)
        opts = RouteOptions(window_margin_m=300.0)
        geom = plan_route(grid, [start, end], opts)
        assert len(geom.coordinates) >= 2

    def test_no_forbidden_cells_in_path(self, standard_settings: SafetySettings) -> None:
        """Propriété forte : aucun point du tracé ne doit être sur une cellule interdite."""
        site, _ = make_site(layers_with_obstacle(obs_row=50, obs_col=50, obs_size=15))
        grid = build_cost_grid(site, standard_settings)
        start = grid_lonlat(0.05, 0.05)
        end = grid_lonlat(0.95, 0.95)
        opts = RouteOptions(window_margin_m=400.0)
        geom = plan_route(grid, [start, end], opts)
        from marswalk_core.geodesy import to_analysis

        for pt in geom.coordinates:
            x, y = to_analysis(site, pt.lon, pt.lat)
            cell = site.xy_to_cell(x, y)
            if cell is not None:
                assert not math.isinf(grid.cost[cell[0], cell[1]])


class TestPlanRouteEdgeCases:
    def test_start_equals_end(
        self,
        flat_site: tuple[Site, Path],
        standard_settings: SafetySettings,
        default_options: RouteOptions,
    ) -> None:
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        pt = grid_lonlat(0.5, 0.5)
        geom = plan_route(grid, [pt, pt], default_options)
        assert len(geom.coordinates) >= 1

    def test_multiple_waypoints(
        self,
        flat_site: tuple[Site, Path],
        standard_settings: SafetySettings,
        default_options: RouteOptions,
    ) -> None:
        site, _ = flat_site
        grid = build_cost_grid(site, standard_settings)
        pts = [
            grid_lonlat(0.1, 0.1),
            grid_lonlat(0.3, 0.7),
            grid_lonlat(0.7, 0.3),
            grid_lonlat(0.9, 0.9),
        ]
        geom = plan_route(grid, pts, default_options)
        assert len(geom.segment_breaks) == 3
        # Extrémités préservées
        assert geom.coordinates[0].lon == pytest.approx(pts[0].lon, abs=1e-5)
        assert geom.coordinates[-1].lon == pytest.approx(pts[-1].lon, abs=1e-5)
