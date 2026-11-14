"""Conditions et scénarios (A3, EF-11). Bouchon T00 : exemples versionnés."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import SiteDep, load_example
from marswalk_core.schemas import Conditions, Forecast, Scenario, ScenarioState

router = APIRouter(tags=["conditions"])


@router.get("/api/sites/{site_id}/conditions/current", response_model=Conditions)
def current_conditions(site: SiteDep) -> Conditions:
    return Conditions.model_validate(load_example("conditions_current"))


@router.get("/api/sites/{site_id}/conditions/forecast", response_model=Forecast)
def forecast_conditions(site: SiteDep, hours: int = 12) -> Forecast:
    return Forecast.model_validate(load_example("conditions_forecast"))


@router.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return [Scenario.model_validate(s) for s in load_example("scenarios")]


@router.post("/api/scenarios/{scenario_id}/start", response_model=ScenarioState)
def start_scenario(scenario_id: str, speed: float = 1.0) -> ScenarioState:
    return ScenarioState.model_validate(load_example("scenario_state"))


@router.post("/api/scenarios/{scenario_id}/stop", response_model=ScenarioState)
def stop_scenario(scenario_id: str) -> ScenarioState:
    state = ScenarioState.model_validate(load_example("scenario_state"))
    return state.model_copy(update={"running": False})
