"""Chaque exemple de contracts/examples/ respecte son modèle Pydantic."""

from __future__ import annotations

import itertools
import json
from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter

from marswalk_api.deps import examples_dir
from marswalk_core import schemas as s

MODELS: dict[str, object] = {
    "health": s.Health,
    "sites": list[s.SiteSummary],
    "site_manifest": s.SiteManifest,
    "time": s.TimeInfo,
    "targets": list[s.Target],
    "target": s.Target,
    "query": s.PointQuery,
    "hazards": s.FeatureCollection,
    "settings": s.SafetySettings,
    "plan": s.Plan,
    "conditions_current": s.Conditions,
    "conditions_forecast": s.Forecast,
    "scenarios": list[s.Scenario],
    "scenario_state": s.ScenarioState,
    "alerts": list[s.Alert],
    "eva": s.Eva,
    "observation": s.Observation,
    "obstacle_response": s.ObstacleResponse,
    "simulation_state": s.SimulationState,
    "ground_images": s.FeatureCollection,
    "export_plan": s.FeatureCollection,
    "logbook": s.Logbook,
    "ws_telemetry": s.WsTelemetry,
    "ws_alert": s.WsAlert,
    "ws_alert_cleared": s.WsAlertCleared,
    "ws_conditions": s.WsConditions,
    "ws_route_updated": s.WsRouteUpdated,
    "ws_budget": s.WsBudget,
}


def test_every_example_file_is_covered() -> None:
    files = {p.stem for p in examples_dir().glob("*.json")}
    assert files == set(MODELS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_example_matches_model(name: str) -> None:
    data = json.loads((examples_dir() / f"{name}.json").read_text(encoding="utf-8"))
    model = MODELS[name]
    if isinstance(model, type) and issubclass(model, BaseModel):
        model.model_validate(data)
    else:
        TypeAdapter[Any](model).validate_python(data)  # type: ignore[arg-type]


def test_plan_example_respects_route_contract() -> None:
    plan = s.Plan.model_validate_json((examples_dir() / "plan.json").read_text())
    assert {r.variant for r in plan.routes} == set(s.RouteVariant)
    for route in plan.routes:
        steps = [b.distance_m - a.distance_m for a, b in itertools.pairwise(route.profile)]
        assert max(steps) <= 5.01
