"""Les bouchons de T00 tiennent leur signature et produisent des objets conformes."""

import json

from marswalk_core.config import load_safety_settings, load_suit
from marswalk_core.grids import RouteOptions
from marswalk_core.paths import repo_root
from marswalk_core.schemas import LonLat, Route, Target
from marswalk_core.site_package import load_site
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.hazards import hazard_masks, hazard_polygons
from marswalk_planner.return_field import return_field
from marswalk_planner.variants import plan_variants
from marswalk_planner.walk import walking_speed


def _targets() -> list[Target]:
    data = json.loads((repo_root() / "contracts/examples/targets.json").read_text())
    return [Target.model_validate(t) for t in data]


def test_hazards_forbid_steep_cells() -> None:
    site = load_site("fictif")
    settings = load_safety_settings()
    masks = hazard_masks(site, settings)
    assert masks.forbidden.any()
    assert hazard_polygons(site, settings).features


def test_cost_and_return_field_shapes() -> None:
    site = load_site("fictif")
    grid = build_cost_grid(site, load_safety_settings(), None)
    assert grid.cost.shape == site.shape
    field = return_field(grid, LonLat(*site.manifest.habitat), load_suit())
    assert field.seconds.shape == site.shape
    assert float(field.seconds.min()) < 2.0


def test_plan_variants_returns_three_routes() -> None:
    site = load_site("fictif")
    routes = plan_variants(
        site, load_safety_settings(), LonLat(*site.manifest.habitat), _targets()[:3], RouteOptions()
    )
    assert [r.variant.value for r in routes] == ["safest", "fastest", "science"]
    for r in routes:
        Route.model_validate(r.model_dump())
        assert len(r.segments) == 4
        assert (
            r.profile[-1].distance_m == r.totals.distance_m
            or abs(r.profile[-1].distance_m - r.totals.distance_m) < 1.0
        )


def test_walking_speed_stub() -> None:
    assert walking_speed(0.0, 0, load_suit()) == 1.0
