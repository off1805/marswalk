"""Zones dangereuses et réglages de sécurité (A2). Bouchon T00 : exemples versionnés."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import SiteDep, load_example
from marswalk_core.schemas import FeatureCollection, SafetySettings

router = APIRouter(tags=["hazards"])


@router.get("/api/sites/{site_id}/hazards", response_model=FeatureCollection)
def get_hazards(site: SiteDep, preset: str | None = None) -> FeatureCollection:
    """Zones interdites et pénalisées selon les seuils courants ; preset choisit une
    entrée de config/safety.yaml."""
    return FeatureCollection.model_validate(load_example("hazards"))


@router.get("/api/sites/{site_id}/settings", response_model=SafetySettings)
def get_settings(site: SiteDep) -> SafetySettings:
    return SafetySettings.model_validate(load_example("settings"))


@router.put("/api/sites/{site_id}/settings", response_model=SafetySettings)
def put_settings(site: SiteDep, body: SafetySettings) -> SafetySettings:
    return body
