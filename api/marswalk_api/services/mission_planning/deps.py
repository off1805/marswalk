"""Fournisseurs de dépendances FastAPI pour mission_planning (SOLID - DIP)."""

from __future__ import annotations

from functools import cache
from typing import Annotated

from fastapi import Depends

from marswalk_api.services.mission_planning.interfaces import (
    IHazardService,
    IPlanComputationService,
    IPlanRepository,
    ISafetySettingsRepository,
    ITargetRepository,
)
from marswalk_api.services.mission_planning.memory_repo import (
    InMemoryPlanRepository,
    InMemorySafetySettingsRepository,
    InMemoryTargetRepository,
)
from marswalk_api.services.mission_planning.services import (
    HazardService,
    PlanComputationService,
)

# Singletons en mémoire pour le partage d'état au sein du processus
_target_repo = InMemoryTargetRepository()
_plan_repo = InMemoryPlanRepository()
_settings_repo = InMemorySafetySettingsRepository()


@cache
def get_target_repository() -> ITargetRepository:
    return _target_repo


@cache
def get_plan_repository() -> IPlanRepository:
    return _plan_repo


@cache
def get_safety_settings_repository() -> ISafetySettingsRepository:
    return _settings_repo


def get_hazard_service(
    settings_repo: Annotated[ISafetySettingsRepository, Depends(get_safety_settings_repository)],
) -> IHazardService:
    return HazardService(settings_repo)


def get_plan_computation_service(
    target_repo: Annotated[ITargetRepository, Depends(get_target_repository)],
    plan_repo: Annotated[IPlanRepository, Depends(get_plan_repository)],
    settings_repo: Annotated[ISafetySettingsRepository, Depends(get_safety_settings_repository)],
) -> IPlanComputationService:
    return PlanComputationService(target_repo, plan_repo, settings_repo)


TargetRepoDep = Annotated[ITargetRepository, Depends(get_target_repository)]
PlanRepoDep = Annotated[IPlanRepository, Depends(get_plan_repository)]
SafetySettingsRepoDep = Annotated[
    ISafetySettingsRepository, Depends(get_safety_settings_repository)
]
HazardServiceDep = Annotated[IHazardService, Depends(get_hazard_service)]
PlanComputationDep = Annotated[IPlanComputationService, Depends(get_plan_computation_service)]
