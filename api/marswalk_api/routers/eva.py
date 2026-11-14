"""Sorties et simulateur (A4) : astronaute virtuel, recalcul local et retour forcé."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from marswalk_api.services.a3 import ScenarioNotFoundError
from marswalk_api.services.a4 import EvaNotFoundError, PlanNotFoundError, get_simulator
from marswalk_core.schemas import (
    Eva,
    EvaCreate,
    Observation,
    ObservationCreate,
    ObstacleReport,
    ObstacleResponse,
    PositionReport,
    SimulateRequest,
    SimulationState,
)

router = APIRouter(tags=["eva"])


def _unknown(eva_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Sortie inconnue : {eva_id}")


@router.post("/api/eva", response_model=Eva, status_code=201)
def start_eva(body: EvaCreate) -> Eva:
    try:
        return get_simulator().start(body)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/eva/{eva_id}", response_model=Eva)
def get_eva(eva_id: str) -> Eva:
    try:
        return get_simulator().get(eva_id)
    except EvaNotFoundError as exc:
        raise _unknown(eva_id) from exc


@router.post("/api/eva/{eva_id}/position", response_model=Eva)
def report_position(eva_id: str, body: PositionReport) -> Eva:
    try:
        return get_simulator().report_position(eva_id, body)
    except EvaNotFoundError as exc:
        raise _unknown(eva_id) from exc


@router.post("/api/eva/{eva_id}/observations", response_model=Observation, status_code=201)
def add_observation(eva_id: str, body: ObservationCreate) -> Observation:
    try:
        return get_simulator().add_observation(eva_id, body)
    except EvaNotFoundError as exc:
        raise _unknown(eva_id) from exc


@router.post("/api/eva/{eva_id}/obstacles", response_model=ObstacleResponse)
def report_obstacle(eva_id: str, body: ObstacleReport) -> ObstacleResponse:
    try:
        return get_simulator().report_obstacle(eva_id, body)
    except EvaNotFoundError as exc:
        raise _unknown(eva_id) from exc


@router.post("/api/eva/{eva_id}/simulate", response_model=SimulationState)
async def simulate(eva_id: str, body: SimulateRequest) -> SimulationState:
    try:
        return await get_simulator().simulate(eva_id, body.speed, body.scenario_id)
    except EvaNotFoundError as exc:
        raise _unknown(eva_id) from exc
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Scénario inconnu : {body.scenario_id}"
        ) from exc
