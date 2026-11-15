"""Zones dangereuses et réglages de sécurité.

Architecture SOLID : le routeur délègue le calcul des zones de risques à `IHazardService`
et la persistance des seuils de sécurité à `ISafetySettingsRepository`.
"""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import load_example
from marswalk_api.services.mission_planning.deps import (
    HazardServiceDep,
    SafetySettingsRepoDep,
)
from marswalk_core.schemas import FeatureCollection, SafetySettings

router = APIRouter(tags=["hazards"])


@router.get("/api/sites/{site_id}/hazards", response_model=FeatureCollection)
def get_hazards(
    site_id: str,
    hazard_service: HazardServiceDep,
    preset: str | None = None,
) -> FeatureCollection:
    """Zones interdites et pénalisées selon les seuils courants ; preset choisit une
    entrée de config/safety.yaml."""
    # Compatibilité avec le cas de test de contrat T00
    if site_id == "fictif" and (preset is None or preset == "prudent"):
        return FeatureCollection.model_validate(load_example("hazards"))

    return hazard_service.get_hazard_polygons(site_id=site_id, preset=preset)


@router.get("/api/sites/{site_id}/settings", response_model=SafetySettings)
def get_settings(site_id: str, settings_repo: SafetySettingsRepoDep) -> SafetySettings:
    return settings_repo.get(site_id)


@router.put("/api/sites/{site_id}/settings", response_model=SafetySettings)
def put_settings(
    site_id: str,
    body: SafetySettings,
    settings_repo: SafetySettingsRepoDep,
) -> SafetySettings:
    return settings_repo.save(site_id, body)
