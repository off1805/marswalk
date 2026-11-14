"""Alertes et temps réel (A3) : règles, moteur d'alertes, diffusion WebSocket, scénarios.

Point d'entrée : ``get_service()`` (voir ``service.py``).
"""

from .service import A3Service, ScenarioNotFoundError, get_service

__all__ = ["A3Service", "ScenarioNotFoundError", "get_service"]
