"""Services métier pour mission_planning : Planification et analyse des risques.

Respecte les principes SOLID (SRP & DIP).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException

from marswalk_api.deps import load_example
from marswalk_api.services.mission_planning.interfaces import (
    IHazardService,
    IPlanComputationService,
    IPlanRepository,
    ISafetySettingsRepository,
    ITargetRepository,
)
from marswalk_core.config import load_suit
from marswalk_core.grids import RouteOptions
from marswalk_core.schemas import (
    FeatureCollection,
    LonLat,
    Plan,
    PlanCreate,
    PlanStatus,
    Target,
)
from marswalk_core.site_package import load_site
from marswalk_planner.hazards import hazard_polygons
from marswalk_planner.variants import plan_variants


class PlanComputationService(IPlanComputationService):
    """Service d'orchestration de la planification d'itinéraire multi-variantes (EF-05)."""

    def __init__(
        self,
        target_repo: ITargetRepository,
        plan_repo: IPlanRepository,
        settings_repo: ISafetySettingsRepository,
    ) -> None:
        self._target_repo = target_repo
        self._plan_repo = plan_repo
        self._settings_repo = settings_repo

    def compute_plan(self, site_id: str, plan_create: PlanCreate) -> Plan:
        t0 = time.perf_counter()
        try:
            site = load_site(site_id)
        except Exception as exc:
            raise HTTPException(404, f"Site inconnu : {site_id}") from exc

        resolved_targets: list[Target] = []
        for tid in plan_create.target_ids:
            target = self._target_repo.get(tid)
            if target is None:
                example_targets = [Target.model_validate(t) for t in load_example("targets")]
                match = next((t for t in example_targets if t.id == tid), None)
                if match:
                    target = match
                else:
                    raise HTTPException(404, f"Cible introuvable : {tid}")
            resolved_targets.append(target)

        start = plan_create.start or LonLat(*site.manifest.habitat)
        return_to = plan_create.return_to or LonLat(*site.manifest.habitat)

        settings = self._settings_repo.get(site_id)
        suit = load_suit()

        options = RouteOptions(
            variants=plan_create.variants,
            return_to=return_to,
            optimize_order=plan_create.optimize_order,
            suit=suit,
        )

        routes = plan_variants(
            site=site,
            settings=settings,
            start=start,
            targets=resolved_targets,
            options=options,
        )

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

        plan = Plan(
            id=f"plan-{uuid.uuid4().hex[:8]}",
            site_id=site_id,
            name=f"Sortie {site.manifest.name}",
            status=PlanStatus.computed,
            created_at=datetime.now(UTC),
            departure_utc=plan_create.departure_utc,
            start=start,
            return_to=return_to,
            target_ids=[t.id for t in resolved_targets],
            settings=settings,
            suit=suit,
            routes=routes,
            selected_route_id=routes[0].id if routes else None,
            compute_time_ms=elapsed_ms,
        )

        return self._plan_repo.save(plan)


class HazardService(IHazardService):
    """Service de génération des zones de danger et polygones de sécurité."""

    def __init__(self, settings_repo: ISafetySettingsRepository) -> None:
        self._settings_repo = settings_repo

    def get_hazard_polygons(self, site_id: str, preset: str | None = None) -> FeatureCollection:
        try:
            site = load_site(site_id)
        except Exception as exc:
            raise HTTPException(404, f"Site inconnu : {site_id}") from exc

        settings = self._settings_repo.get(site_id)
        if preset and preset != settings.preset:
            settings_copy = settings.model_copy(update={"preset": preset})
            return hazard_polygons(site, settings_copy)

        return hazard_polygons(site, settings)
