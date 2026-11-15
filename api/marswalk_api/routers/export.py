"""Export GeoJSON et carnet de terrain (X1, EF-15)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from marswalk_api.services.a4 import EvaNotFoundError, get_simulator
from marswalk_api.services.x1 import PlanNotFoundError, example_targets, logbook, plan_geojson
from marswalk_core.schemas import FeatureCollection, Logbook

router = APIRouter(tags=["export"])


@router.get("/api/plans/{plan_id}/export.geojson", response_model=FeatureCollection)
def export_plan(plan_id: str) -> FeatureCollection:
    try:
        return plan_geojson(plan_id, get_simulator().plan_source, example_targets)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/eva/{eva_id}/logbook", response_model=Logbook)
def get_logbook(eva_id: str) -> Logbook:
    try:
        return logbook(get_simulator(), eva_id)
    except EvaNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Sortie inconnue : {eva_id}") from exc
