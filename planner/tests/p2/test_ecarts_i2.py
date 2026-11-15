"""Écarts E4, E5 et E6 du scénario de démo (e2e/ECARTS.md).

- E4 : une cible qu'aucun passage praticable ne relie au départ est écartée et
  annoncée ; aucun tracé ne franchit une zone interdite en silence.
- E5 : le lissage ne redresse pas les détours voulus par le coût, donc les trois
  variantes diffèrent quand le terrain le justifie (site fictif).
- E6 : chaque tronçon est expliqué par une phrase (« contourne une pente de 65° »).
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from tests.p2.conftest import (
    flat_layers,
    grid_lonlat,
    make_site,
    make_target_at,
)

from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import LonLat, ReturnStatus, SafetySettings, Target
from marswalk_core.site_package import Site
from marswalk_planner._p2.astar import Cell, astar_grid
from marswalk_planner._p2.smooth import _line_cost, smooth_path
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.variants import plan_variants

# ---------------------------------------------------------------------------
# Lissage et recherche
# ---------------------------------------------------------------------------


def test_smoothing_keeps_a_cost_detour() -> None:
    """Une bande chère mais praticable : le chemin la contourne, le lissage aussi."""
    cost = np.ones((40, 40), dtype=np.float32)
    cost[5:35, 20] = 50.0  # bande chère, ouverte en haut et en bas
    path = astar_grid(cost, Cell(20, 2), Cell(20, 38), window_margin_cells=40)
    assert path is not None
    smoothed = smooth_path(cost, path)
    rows = [c.row for c in smoothed]
    assert min(rows) < 5 or max(rows) >= 35, "le lissage a redressé le détour"
    # Le tracé lissé ne coûte pas plus que le chemin brut
    lissé = sum(_line_cost(cost, a, b) for a, b in itertools.pairwise(smoothed))
    brut = sum(
        math.hypot(b.row - a.row, b.col - a.col) * (cost[a] + cost[b]) / 2
        for a, b in itertools.pairwise(path)
    )
    assert lissé <= brut * 1.011


def test_smoothing_rejects_corner_contact() -> None:
    """Un segment qui passe exactement par le coin d'une case interdite est refusé."""
    cost = np.ones((10, 10), dtype=np.float32)
    cost[0, 1] = np.inf  # touche le segment (0,0)→(1,1) par son coin
    assert math.isinf(_line_cost(cost, Cell(0, 0), Cell(1, 1)))
    assert math.isfinite(_line_cost(cost, Cell(2, 0), Cell(3, 1)))


def test_astar_does_not_cut_corners() -> None:
    """Deux cases interdites en diagonale ne laissent pas passer entre elles."""
    cost = np.ones((3, 3), dtype=np.float32)
    cost[0, 1] = np.inf
    cost[1, 0] = np.inf
    cost[1, 2] = np.inf
    cost[2, 1] = np.inf
    assert astar_grid(cost, Cell(0, 0), Cell(2, 2), window_margin_cells=10) is None


# ---------------------------------------------------------------------------
# E4 : cible inaccessible
# ---------------------------------------------------------------------------


def _cliff_site() -> Site:
    """Falaise (pente 60°) sur toute la largeur, sans passage."""
    layers = flat_layers()
    layers["slope"][48:52, :] = 60.0
    site, _ = make_site(layers)
    return site


def test_unreachable_target_is_refused_and_announced(standard_settings: SafetySettings) -> None:
    site = _cliff_site()
    start = grid_lonlat(0.8, 0.5)
    near = make_target_at(1, 0.7, 0.3)
    far = make_target_at(2, 0.2, 0.5)  # derrière la falaise
    routes = plan_variants(site, standard_settings, start, [near, far], RouteOptions())
    grid = build_cost_grid(site, standard_settings)
    for r in routes:
        assert [s.to_target_id for s in r.segments] == ["t1", None]
        assert any("Cible 2" in w and "écartée" in w and "60°" in w for w in r.warnings)
        assert r.totals.max_slope_deg < standard_settings.max_slope_deg
        for p in r.geometry.coordinates:
            cell = site.xy_to_cell(*to_analysis(site, p.lon, p.lat))
            assert cell is not None and not grid.forbidden[cell]


def test_all_targets_unreachable_still_plans(standard_settings: SafetySettings) -> None:
    site = _cliff_site()
    start = grid_lonlat(0.8, 0.5)
    routes = plan_variants(
        site, standard_settings, start, [make_target_at(1, 0.2, 0.5)], RouteOptions()
    )
    assert len(routes) == 3
    for r in routes:
        assert r.warnings and "écartée" in r.warnings[0]
        assert all(s.to_target_id is None for s in r.segments)


def test_fallback_segment_is_flagged(standard_settings: SafetySettings) -> None:
    """Filet de sécurité : un tronçon en ligne droite de secours est signalé et le
    retour n'est pas garanti (ici, un point d'arrivée de l'autre côté de la falaise)."""
    site = _cliff_site()
    start = grid_lonlat(0.8, 0.5)
    opts = RouteOptions(return_to=grid_lonlat(0.2, 0.5))
    routes = plan_variants(site, standard_settings, start, [make_target_at(1, 0.7, 0.3)], opts)
    for r in routes:
        assert r.return_check.status == ReturnStatus.fail
        assert any("sans passage praticable" in w for w in r.warnings)
        assert "Aucun passage praticable" in r.explanation[-1].reasons[0]


# ---------------------------------------------------------------------------
# E5 et E6 sur le site fictif (scénario de démo)
# ---------------------------------------------------------------------------

_DEMO = ("Front du delta", "Unité à olivine", "Bord des dunes")


def _demo_targets() -> list[Target]:
    """Les trois cibles du scénario, lues dans les cibles proposées du site fictif."""
    import json
    from datetime import datetime

    from marswalk_core.paths import repo_root
    from marswalk_core.schemas import TargetKind

    seed = repo_root() / "config" / "sites" / "fictif" / "targets-seed.geojson"
    features = json.loads(seed.read_text(encoding="utf-8"))["features"]
    return [
        Target(
            id=f["id"],
            site_id="fictif",
            name=f["properties"]["name"],
            kind=TargetKind.science,
            position=LonLat(*f["geometry"]["coordinates"]),
            work_time_s=f["properties"]["work_time_s"],
            created_at=datetime(2026, 11, 1),
            updated_at=datetime(2026, 11, 1),
        )
        for f in features
        if f["properties"]["name"] in _DEMO
    ]


def test_fictif_demo_variants(fictif_site: Site, standard_settings: SafetySettings) -> None:
    site = fictif_site
    start = LonLat(*site.manifest.habitat)
    routes = plan_variants(site, standard_settings, start, _demo_targets(), RouteOptions())
    # E4 : le plateau est atteint par la rampe, sans franchir la falaise
    for r in routes:
        assert r.totals.max_slope_deg < standard_settings.max_slope_deg, r.variant
        assert not r.warnings, r.warnings
        assert len([s for s in r.segments if s.to_target_id]) == 3
    # E5 : trois tracés différents
    distances = {round(r.totals.distance_m) for r in routes}
    assert len(distances) == 3, distances
    # E6 : la raison du détour en clair, sans termes du coût
    reasons = [e.reasons[0] for r in routes for e in r.explanation]
    assert any(x.startswith("Contourne une pente de") for x in reasons), reasons
    assert not any("Tobler" in x or "contribution" in x for x in reasons)
