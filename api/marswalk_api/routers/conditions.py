"""Conditions, prévisions et scénarios (A3, EF-11), sur les données de K1."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from marswalk_api.deps import SiteDep
from marswalk_api.services.a3 import ScenarioNotFoundError, get_service
from marswalk_core.schemas import Conditions, Forecast, Scenario, ScenarioState

router = APIRouter(tags=["conditions"])


@router.get("/api/sites/{site_id}/conditions/current", response_model=Conditions)
def current_conditions(site: SiteDep) -> Conditions:
    # À l'instant présent, ou à l'instant simulé si un scénario est en cours.
    return get_service().current_conditions()


@router.get("/api/sites/{site_id}/conditions/forecast", response_model=Forecast)
def forecast_conditions(site: SiteDep, hours: int = 12) -> Forecast:
    hours = min(max(hours, 1), 72)
    service = get_service()
    return Forecast(
        site_id=site.site_id, generated_at=service.scenario_utc(), items=service.forecast(hours)
    )


@router.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return get_service().scenarios()


@router.post("/api/scenarios/{scenario_id}/start", response_model=ScenarioState)
async def start_scenario(scenario_id: str, speed: float = 1.0) -> ScenarioState:
    # Rejeu accéléré : speed secondes simulées par seconde réelle.
    if not 0 < speed <= 10000:
        raise HTTPException(status_code=422, detail="speed doit être entre 0 et 10 000")
    try:
        return await get_service().start_scenario(scenario_id, speed)
    except ScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Scénario inconnu : {scenario_id}") from exc


@router.post("/api/scenarios/{scenario_id}/stop", response_model=ScenarioState)
async def stop_scenario(scenario_id: str) -> ScenarioState:
    return await get_service().stop_scenario()
