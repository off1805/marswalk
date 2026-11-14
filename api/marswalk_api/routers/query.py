"""Interrogation de point (A1, EF-07). Bouchon T00 : exemple versionné."""

from __future__ import annotations

from fastapi import APIRouter, Query

from marswalk_api.deps import SiteDep, load_example
from marswalk_core.schemas import PointQuery

router = APIRouter(tags=["sites"])


@router.get("/api/sites/{site_id}/query", response_model=PointQuery)
def query_point(
    site: SiteDep,
    lon: float = Query(ge=-180, le=180),
    lat: float = Query(ge=-90, le=90),
) -> PointQuery:
    return PointQuery.model_validate(load_example("query"))
