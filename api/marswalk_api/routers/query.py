"""Interrogation de point (EF-07).

Architecture SOLID : le routeur délègue l'interrogation multicouche et le calcul
du temps de retour au service `IPointQueryService` (module `site_layers`).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from marswalk_api.services.site_layers.deps import PointQueryDep
from marswalk_core.schemas import PointQuery

router = APIRouter(tags=["sites"])


@router.get("/api/sites/{site_id}/query", response_model=PointQuery)
def query_point(
    site_id: str,
    query_service: PointQueryDep,
    lon: float = Query(ge=-180, le=180, description="Longitude planétocentrique est en degrés"),
    lat: float = Query(ge=-90, le=90, description="Latitude planétocentrique en degrés"),
) -> PointQuery:
    """Interroge la valeur de toutes les couches du site en un point (lon, lat).

    Renvoie pour chaque couche sa valeur, son unité, sa source, son incertitude,
    son statut et le temps de retour vers l'habitat le plus court.
    """
    return query_service.query_point(site_id=site_id, lon=lon, lat=lat)
