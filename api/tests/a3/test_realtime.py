"""Acceptation A3 : solar-event, acquittement, horodatage martien des messages."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient

from marswalk_api.main import app
from marswalk_api.services.a3 import A3Service
from marswalk_core.marstime import mars_time
from marswalk_core.schemas import WsEnvelope

from .conftest import SPIKE_AT_S

SPEED = 6000.0  # le pic de dose arrive 0,2 s après le départ


def assert_stamped(msg: dict[str, Any]) -> None:
    """Chaque message porte UTC, sol et heure locale (ENF-11), et respecte le contrat."""
    WsEnvelope.model_validate({"message": msg})
    assert msg["utc"] and isinstance(msg["sol"], int) and len(msg["lmst"]) == 8


def test_solar_event_raises_danger_within_one_second(service: A3Service) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws/eva/eva-1") as ws:
        first = ws.receive_json()
        assert first["type"] == "conditions"
        assert_stamped(first)
        t0 = time.monotonic()
        res = client.post(f"/api/scenarios/solar-event/start?speed={SPEED}")
        assert res.status_code == 200 and res.json()["running"] is True
        while True:
            msg = ws.receive_json()
            assert_stamped(msg)
            if msg["type"] == "alert" and msg["payload"]["level"] == "danger":
                break
        latency = time.monotonic() - t0 - SPIKE_AT_S / SPEED
        alert = msg["payload"]
        assert alert["action"] == "Retour à l'abri" and alert["cause"] == "radiation"
        assert latency < 1.0, f"alerte reçue {latency:.2f} s après le pic"

        # Acquittement en une action, diffusé par le WebSocket.
        ack = client.post(f"/api/alerts/{alert['id']}/ack")
        assert ack.status_code == 200 and ack.json()["acknowledged"] is True
        while True:
            msg = ws.receive_json()
            if msg["type"] == "alert" and msg["payload"]["id"] == alert["id"]:
                assert msg["payload"]["acknowledged"] is True
                break
        active = client.get("/api/alerts?eva_id=eva-1").json()
        assert active[0]["id"] == alert["id"] and active[0]["acknowledged"] is True
        assert client.post("/api/scenarios/solar-event/stop").json()["running"] is False


def test_ack_over_websocket(service: A3Service) -> None:
    with TestClient(app) as client, client.websocket_connect("/ws/eva/eva-2") as ws:
        ws.receive_json()
        client.post(f"/api/scenarios/solar-event/start?speed={SPEED}")
        while (msg := ws.receive_json())["type"] != "alert":
            pass
        ws.send_json({"type": "ack", "alert_id": msg["payload"]["id"]})
        while True:
            m = ws.receive_json()
            if m["type"] == "alert" and m["payload"]["acknowledged"]:
                break
        client.post("/api/scenarios/solar-event/stop")


def test_unknown_alert_and_scenario_are_404(service: A3Service) -> None:
    with TestClient(app) as client:
        assert client.post("/api/alerts/inconnue/ack").status_code == 404
        assert client.post("/api/scenarios/inconnu/start").status_code == 404


def test_time_comes_from_mars24(service: A3Service) -> None:
    with TestClient(app) as client:
        info = client.get("/api/time?site_id=fictif").json()
    site = service.site()
    expected = mars_time(
        datetime.fromisoformat(info["utc"]), info["lon_east"], site.manifest.mission_epoch_utc
    )
    assert info["sol"] == expected.sol and info["lmst"] == expected.lmst
    assert info["site_id"] == "fictif"


def test_conditions_follow_running_scenario(service: A3Service) -> None:
    with TestClient(app) as client:
        calm = client.get("/api/sites/fictif/conditions/current").json()
        assert calm["mode"] == "historical" and calm["sol"] is not None and calm["lmst"]
        client.post(f"/api/scenarios/solar-event/start?speed={SPEED}")
        time.sleep(0.4)
        storm = client.get("/api/sites/fictif/conditions/current").json()
        assert storm["mode"] == "scenario" and storm["dose_rate_usv_h"] == 250.0
        forecast = client.get("/api/sites/fictif/conditions/forecast?hours=3").json()
        assert len(forecast["items"]) == 3
        client.post("/api/scenarios/solar-event/stop")


def test_eva_telemetry_publishes_budget_and_alerts(service: A3Service) -> None:
    """Interface pour A4 : une sortie à faible réserve lève une alerte danger."""
    from marswalk_api.deps import load_example
    from marswalk_core.schemas import Eva

    eva = Eva.model_validate(load_example("eva")).model_copy(
        update={"id": "eva-3", "reserve_pct": 5.0}
    )
    with TestClient(app) as client, client.websocket_connect("/ws/eva/eva-3") as ws:
        ws.receive_json()
        client.portal.call(lambda: service.ingest_eva(eva))  # type: ignore[union-attr]
        types = []
        while "alert" not in types:
            msg = ws.receive_json()
            assert_stamped(msg)
            types.append(msg["type"])
            if msg["type"] == "alert":
                assert msg["payload"]["cause"] == "return_reserve"
                assert msg["payload"]["level"] == "danger"
        assert types[:2] == ["telemetry", "budget"]
