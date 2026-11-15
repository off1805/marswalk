"""Implémentation en mémoire (Mock) des dépôts mission_planning (SOLID - LSP).

Ces classes implémentent ITargetRepository, IPlanRepository et ISafetySettingsRepository.
Elles garantissent le fonctionnement découplé de l'application tant que la base PostGIS
réelle n'est pas connectée. La bascule vers PostGIS se fera par simple substitution
de ces classes d'implémentation sans toucher au reste de l'API.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime

from marswalk_api.deps import load_example
from marswalk_api.services.mission_planning.interfaces import (
    IPlanRepository,
    ISafetySettingsRepository,
    ITargetRepository,
)
from marswalk_core.config import load_safety_settings
from marswalk_core.paths import config_dir
from marswalk_core.schemas import (
    Plan,
    PlanUpdate,
    SafetySettings,
    Target,
    TargetCreate,
    TargetUpdate,
)


class InMemoryTargetRepository(ITargetRepository):
    """Dépôt en mémoire pour les cibles, pré-rempli avec les données mock d'exemple."""

    def __init__(self, seed: bool = True) -> None:
        self._lock = threading.Lock()
        self._targets: dict[str, Target] = {}
        if seed:
            self._seed_data()

    def _seed_data(self) -> None:
        try:
            raw_list = load_example("targets")
            for item in raw_list:
                t = Target.model_validate(item)
                self._targets[t.id] = t
        except Exception:
            pass
        # Sites réels : cibles proposées de config/sites/<site_id>/targets-seed.geojson
        # (Jezero : J1 à J4, de S1). Le site fictif garde les exemples des contrats.
        for path in sorted(config_dir().glob("sites/*/targets-seed.geojson")):
            site_id = path.parent.name
            if site_id == "fictif":
                continue
            try:
                for t in _targets_from_seed(site_id, path.read_text(encoding="utf-8")):
                    self._targets.setdefault(t.id, t)
            except Exception:
                continue

    def list_by_site(self, site_id: str) -> list[Target]:
        with self._lock:
            return [t for t in self._targets.values() if t.site_id == site_id]

    def get(self, target_id: str) -> Target | None:
        with self._lock:
            return self._targets.get(target_id)

    def create(self, site_id: str, data: TargetCreate) -> Target:
        with self._lock:
            target_id = f"target-{uuid.uuid4().hex[:8]}"
            now = datetime.now(UTC)
            target = Target(
                id=target_id,
                site_id=site_id,
                created_at=now,
                updated_at=now,
                **data.model_dump(),
            )
            self._targets[target_id] = target
            return target

    def update(self, target_id: str, data: TargetUpdate) -> Target | None:
        with self._lock:
            existing = self._targets.get(target_id)
            if existing is None:
                return None
            updates = data.model_dump(exclude_unset=True)
            updated_dict = existing.model_dump()
            updated_dict.update(updates)
            updated_dict["updated_at"] = datetime.now(UTC)
            updated = Target.model_validate(updated_dict)
            self._targets[target_id] = updated
            return updated

    def delete(self, target_id: str) -> bool:
        with self._lock:
            return self._targets.pop(target_id, None) is not None


def _targets_from_seed(site_id: str, text: str) -> list[Target]:
    now = datetime.now(UTC)
    out: list[Target] = []
    for feature in json.loads(text).get("features", []):
        props = feature.get("properties") or {}
        lon, lat = feature["geometry"]["coordinates"][:2]
        out.append(
            Target.model_validate(
                {
                    "id": str(feature["id"]),
                    "site_id": site_id,
                    "created_at": now,
                    "updated_at": now,
                    "position": [lon, lat],
                    **{
                        k: props[k]
                        for k in (
                            "name",
                            "kind",
                            "objective",
                            "measurement",
                            "work_time_s",
                            "priority",
                        )
                        if k in props
                    },
                }
            )
        )
    return out


class InMemoryPlanRepository(IPlanRepository):
    """Dépôt en mémoire pour les plans calculés."""

    def __init__(self, seed: bool = True) -> None:
        self._lock = threading.Lock()
        self._plans: dict[str, Plan] = {}
        if seed:
            self._seed_data()

    def _seed_data(self) -> None:
        try:
            raw_plan = load_example("plan")
            plan = Plan.model_validate(raw_plan)
            self._plans[plan.id] = plan
        except Exception:
            pass

    def get(self, plan_id: str) -> Plan | None:
        with self._lock:
            return self._plans.get(plan_id)

    def save(self, plan: Plan) -> Plan:
        with self._lock:
            self._plans[plan.id] = plan
            return plan

    def update(self, plan_id: str, data: PlanUpdate) -> Plan | None:
        with self._lock:
            existing = self._plans.get(plan_id)
            if existing is None:
                return None
            updates = data.model_dump(exclude_unset=True)
            plan_dict = existing.model_dump()
            plan_dict.update(updates)
            updated = Plan.model_validate(plan_dict)
            self._plans[plan_id] = updated
            return updated


class InMemorySafetySettingsRepository(ISafetySettingsRepository):
    """Dépôt en mémoire pour les réglages de sécurité par site."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._settings_by_site: dict[str, SafetySettings] = {}

    def get(self, site_id: str) -> SafetySettings:
        with self._lock:
            if site_id not in self._settings_by_site:
                try:
                    if site_id != "fictif":
                        # Sites réels : préréglage par défaut de config/safety.yaml (I1).
                        self._settings_by_site[site_id] = load_safety_settings()
                        return self._settings_by_site[site_id]
                    raw = load_example("settings")
                    self._settings_by_site[site_id] = SafetySettings.model_validate(raw)
                except Exception:
                    self._settings_by_site[site_id] = SafetySettings()
            return self._settings_by_site[site_id]

    def save(self, site_id: str, settings: SafetySettings) -> SafetySettings:
        with self._lock:
            self._settings_by_site[site_id] = settings
            return settings
