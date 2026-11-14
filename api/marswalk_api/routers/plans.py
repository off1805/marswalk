"""Plans et itinéraires (A2, EF-05, EF-06). Bouchon T00 : exemple versionné."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import SiteDep, load_example
from marswalk_core.schemas import Plan, PlanCreate, PlanUpdate

router = APIRouter(tags=["plans"])


@router.post("/api/sites/{site_id}/plans", response_model=Plan, status_code=201)
def create_plan(site: SiteDep, body: PlanCreate) -> Plan:
    return Plan.model_validate(load_example("plan"))


@router.get("/api/plans/{plan_id}", response_model=Plan)
def get_plan(plan_id: str) -> Plan:
    return Plan.model_validate(load_example("plan"))


@router.patch("/api/plans/{plan_id}", response_model=Plan)
def update_plan(plan_id: str, body: PlanUpdate) -> Plan:
    return Plan.model_validate(load_example("plan"))
