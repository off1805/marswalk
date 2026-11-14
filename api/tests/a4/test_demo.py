"""Acceptation A4 par l'API : la sortie de démo en accéléré, de bout en bout.

Étapes 10 à 14 de ``docs/scenario-demo.md`` : lancer la sortie et l'astronaute virtuel,
signaler un obstacle et noter une observation, éruption solaire (``solar-event``), retour
forcé vers l'habitat. Tout passe par les routes REST et le WebSocket de la sortie.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi.testclient import TestClient

from marswalk_api.main import app
from marswalk_api.services.a3 import A3Service
from marswalk_api.services.a4 import A4Service
from marswalk_core.schemas import WsEnvelope

SPEED = 300.0
"""Le pic de dose (1 200 s de scénario) arrive 4 s après le départ."""


def receive_until(ws: Any, kind: str, deadline: float, **match: str) -> dict[str, Any]:
    while time.monotonic() < deadline:
        msg: dict[str, Any] = ws.receive_json()
        WsEnvelope.model_validate({"message": msg})
        if msg["type"] == kind and all(
            str(msg["payload"].get(k, "")).startswith(v) for k, v in match.items()
        ):
            return msg
    raise AssertionError(f"pas de message {kind} {match}")


def test_demo_eva_runs_in_under_three_minutes(sim: A4Service, a3: A3Service) -> None:
    t_start = time.monotonic()
    deadline = t_start + 180.0
    with TestClient(app) as client:
        res = client.post("/api/eva", json={"plan_id": "plan-demo", "route_id": "route-safest"})
        assert res.status_code == 201, res.text
        eva = res.json()
        assert eva["status"] == "active"
        with client.websocket_connect(f"/ws/eva/{eva['id']}") as ws:
            sim_res = client.post(
                f"/api/eva/{eva['id']}/simulate",
                json={"speed": SPEED, "scenario_id": "solar-event"},
            )
            assert sim_res.status_code == 200 and sim_res.json()["running"] is True

            # Étape 10 : la position et les consommables avancent par WebSocket.
            first = receive_until(ws, "telemetry", deadline)
            receive_until(ws, "budget", deadline)
            later = receive_until(ws, "telemetry", deadline)
            assert later["payload"]["elapsed_s"] > first["payload"]["elapsed_s"]

            # Étape 11 : obstacle sur le tracé, recalcul local en moins de 2 s.
            route = client.get("/api/plans/plan-demo").json()["routes"][0]
            done_m = client.get(f"/api/eva/{eva['id']}").json()["distance_done_m"]
            point = next(p for p in route["profile"] if p["distance_m"] > done_m + 150)
            obst = client.post(
                f"/api/eva/{eva['id']}/obstacles",
                json={"position": point["position"], "radius_m": 6},
            )
            assert obst.status_code == 200, obst.text
            assert obst.json()["route"] is not None
            assert obst.json()["compute_time_ms"] < 2000
            receive_until(ws, "route_updated", deadline, reason="Obstacle")
            obs = client.post(
                f"/api/eva/{eva['id']}/observations",
                json={"position": point["position"], "note": "Litage oblique"},
            )
            assert obs.status_code == 201 and obs.json()["lmst"]

            # Étapes 12 et 14 : alerte danger, puis retour forcé vers l'habitat.
            receive_until(ws, "alert", deadline, level="danger", cause="radiation")
            back = receive_until(ws, "route_updated", deadline, reason="Retour forcé")
            assert back["payload"]["route"]["segments"][-1]["to_target_id"] is None

        while time.monotonic() < deadline:
            state = client.get(f"/api/eva/{eva['id']}").json()
            if state["status"] == "completed":
                break
            time.sleep(0.1)
        assert state["status"] == "completed", state
        assert client.post(f"/api/eva/{eva['id']}/simulate", json={}).json()["running"] is False
    assert time.monotonic() - t_start < 180.0


def test_unknown_eva_plan_route_and_scenario_are_404(sim: A4Service, a3: A3Service) -> None:
    with TestClient(app) as client:
        assert client.get("/api/eva/eva-inconnue").status_code == 404
        assert client.post("/api/eva", json={"plan_id": "x", "route_id": "y"}).status_code == 404
        bad_route = {"plan_id": "plan-demo", "route_id": "route-inconnue"}
        assert client.post("/api/eva", json=bad_route).status_code == 404
        res = client.post("/api/eva/eva-demo/simulate", json={"scenario_id": "inconnu"})
        assert res.status_code == 404


def test_demo_eva_exists_on_demand(sim: A4Service, a3: A3Service) -> None:
    with TestClient(app) as client:
        eva = client.get("/api/eva/eva-demo").json()
        assert eva["plan_id"] == "plan-demo" and eva["route_id"] == "route-safest"
