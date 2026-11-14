"""Cibles et points de passage (A2, EF-04). Bouchon T00 : exemples versionnés."""

from __future__ import annotations

from fastapi import APIRouter, Response

from marswalk_api.deps import SiteDep, load_example
from marswalk_core.schemas import Target, TargetCreate, TargetUpdate

router = APIRouter(tags=["targets"])


@router.get("/api/sites/{site_id}/targets", response_model=list[Target])
def list_targets(site: SiteDep) -> list[Target]:
    return [Target.model_validate(t) for t in load_example("targets")]


@router.post("/api/sites/{site_id}/targets", response_model=Target, status_code=201)
def create_target(site: SiteDep, body: TargetCreate) -> Target:
    return Target.model_validate(load_example("target"))


@router.patch("/api/targets/{target_id}", response_model=Target)
def update_target(target_id: str, body: TargetUpdate) -> Target:
    return Target.model_validate(load_example("target"))


@router.delete("/api/targets/{target_id}", status_code=204, response_class=Response)
def delete_target(target_id: str) -> Response:
    return Response(status_code=204)
