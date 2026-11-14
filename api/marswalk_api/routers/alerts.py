"""Alertes (A3, EF-08). Bouchon T00 : exemples versionnés."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import load_example
from marswalk_core.schemas import Alert

router = APIRouter(tags=["alerts"])


@router.get("/api/alerts", response_model=list[Alert])
def list_alerts(eva_id: str | None = None, active: bool = True) -> list[Alert]:
    return [Alert.model_validate(a) for a in load_example("alerts")]


@router.post("/api/alerts/{alert_id}/ack", response_model=Alert)
def acknowledge_alert(alert_id: str) -> Alert:
    alert = Alert.model_validate(load_example("alerts")[0])
    return alert.model_copy(update={"acknowledged": True})
