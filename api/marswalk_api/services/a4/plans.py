"""Source des plans pour le simulateur (A4).

Les plans appartiennent à A2. En attendant que A2 les expose, le simulateur lit :

1. les plans enregistrés par ``PlanRegistry.register`` (appel prévu côté A2 après un calcul,
   voir ``tasks/change-requests/A4-source-des-plans.md``) ;
2. le plan de démonstration ``plan-demo`` des exemples versionnés.

``A4Service`` accepte n'importe quel ``PlanSource`` : il suffira d'y brancher le dépôt de A2.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from marswalk_api.deps import load_example
from marswalk_core.schemas import Plan

PlanSource = Callable[[str], Plan | None]

DEMO_PLAN_ID = "plan-demo"


class PlanRegistry:
    def __init__(self) -> None:
        self._plans: dict[str, Plan] = {}
        self._lock = threading.Lock()

    def register(self, plan: Plan) -> None:
        with self._lock:
            self._plans[plan.id] = plan

    def __call__(self, plan_id: str) -> Plan | None:
        with self._lock:
            plan = self._plans.get(plan_id)
        if plan is not None:
            return plan
        if plan_id == DEMO_PLAN_ID:
            return Plan.model_validate(load_example("plan"))
        return None

    def clear(self) -> None:
        with self._lock:
            self._plans.clear()
