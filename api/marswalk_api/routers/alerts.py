"""Alertes actives et acquittement (A3, EF-08)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from marswalk_api.services.a3 import get_service
from marswalk_core.schemas import Alert

router = APIRouter(tags=["alerts"])


@router.get("/api/alerts", response_model=list[Alert])
def list_alerts(eva_id: str | None = None, active: bool = True) -> list[Alert]:
    # Les plus graves en tête ; avec eva_id, celles de la sortie et celles du site.
    return get_service().engine.list(eva_id, active)


@router.post("/api/alerts/{alert_id}/ack", response_model=Alert)
def acknowledge_alert(alert_id: str) -> Alert:
    # Une seule action ; le changement est diffusé par le WebSocket.
    alert = get_service().acknowledge(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alerte inconnue : {alert_id}")
    return alert
