"""Sorties et simulateur (A4). Bouchon T00 : exemples versionnés."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import load_example
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


@router.post("/api/eva", response_model=Eva, status_code=201)
def start_eva(body: EvaCreate) -> Eva:
    return Eva.model_validate(load_example("eva"))


@router.get("/api/eva/{eva_id}", response_model=Eva)
def get_eva(eva_id: str) -> Eva:
    return Eva.model_validate(load_example("eva"))


@router.post("/api/eva/{eva_id}/position", response_model=Eva)
def report_position(eva_id: str, body: PositionReport) -> Eva:
    return Eva.model_validate(load_example("eva"))


@router.post("/api/eva/{eva_id}/observations", response_model=Observation, status_code=201)
def add_observation(eva_id: str, body: ObservationCreate) -> Observation:
    return Observation.model_validate(load_example("observation"))


@router.post("/api/eva/{eva_id}/obstacles", response_model=ObstacleResponse)
def report_obstacle(eva_id: str, body: ObstacleReport) -> ObstacleResponse:
    return ObstacleResponse.model_validate(load_example("obstacle_response"))


@router.post("/api/eva/{eva_id}/simulate", response_model=SimulationState)
def simulate(eva_id: str, body: SimulateRequest) -> SimulationState:
    return SimulationState.model_validate(load_example("simulation_state"))
