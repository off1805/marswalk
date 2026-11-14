"""Export GeoJSON et carnet de terrain (X1, EF-15). Bouchon T00 : exemples versionnés."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import load_example
from marswalk_core.schemas import FeatureCollection, Logbook

router = APIRouter(tags=["export"])


@router.get("/api/plans/{plan_id}/export.geojson", response_model=FeatureCollection)
def export_plan(plan_id: str) -> FeatureCollection:
    return FeatureCollection.model_validate(load_example("export_plan"))


@router.get("/api/eva/{eva_id}/logbook", response_model=Logbook)
def get_logbook(eva_id: str) -> Logbook:
    return Logbook.model_validate(load_example("logbook"))
