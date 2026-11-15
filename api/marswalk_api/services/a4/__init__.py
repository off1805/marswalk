"""Simulateur de sortie (A4) : astronaute virtuel, recalcul local, retour forcé.

Point d'entrée : ``get_simulator()`` (voir ``simulator.py``).
"""

from .plans import DEMO_PLAN_ID, PlanRegistry, PlanSource
from .simulator import (
    DEMO_EVA_ID,
    A4Service,
    EvaNotFoundError,
    PlanNotFoundError,
    get_simulator,
)

__all__ = [
    "DEMO_EVA_ID",
    "DEMO_PLAN_ID",
    "A4Service",
    "EvaNotFoundError",
    "PlanNotFoundError",
    "PlanRegistry",
    "PlanSource",
    "get_simulator",
]
