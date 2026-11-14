"""Toutes les routes répondent selon les exemples de contracts/examples/ (acceptation T00)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from marswalk_api.deps import examples_dir
from marswalk_api.main import app

client = TestClient(app)


def example(name: str) -> Any:
    return json.loads((examples_dir() / f"{name}.json").read_text(encoding="utf-8"))


TARGET_BODY = {"name": "Cible", "position": [77.58, 18.38]}
PLAN_BODY = {"target_ids": ["T1"]}
POS = {"position": [77.58, 18.38]}

CASES: list[tuple[str, str, dict[str, Any] | None, int, str | None]] = [
    ("GET", "/api/sites", None, 200, "sites"),
    ("GET", "/api/sites/fictif", None, 200, "site_manifest"),
    ("GET", "/api/sites/fictif/query?lon=77.57&lat=18.38", None, 200, "query"),
    ("GET", "/api/sites/fictif/hazards", None, 200, "hazards"),
    ("GET", "/api/sites/fictif/hazards?preset=prudent", None, 200, "hazards"),
    ("GET", "/api/sites/fictif/settings", None, 200, "settings"),
    ("PUT", "/api/sites/fictif/settings", example("settings"), 200, "settings"),
    ("GET", "/api/sites/fictif/targets", None, 200, "targets"),
    ("POST", "/api/sites/fictif/targets", TARGET_BODY, 201, "target"),
    ("PATCH", "/api/targets/T1", {"name": "Nouveau nom"}, 200, "target"),
    ("POST", "/api/sites/fictif/plans", PLAN_BODY, 201, "plan"),
    ("GET", "/api/plans/plan-demo", None, 200, "plan"),
    ("PATCH", "/api/plans/plan-demo", {"selected_route_id": "route-fastest"}, 200, "plan"),
    ("GET", "/api/sites/fictif/conditions/current", None, 200, "conditions_current"),
    ("GET", "/api/sites/fictif/conditions/forecast", None, 200, "conditions_forecast"),
    ("GET", "/api/scenarios", None, 200, "scenarios"),
    ("POST", "/api/scenarios/solar-event/start", None, 200, "scenario_state"),
    ("GET", "/api/alerts", None, 200, "alerts"),
    ("GET", "/api/time", None, 200, "time"),
    ("POST", "/api/eva", {"plan_id": "plan-demo", "route_id": "route-safest"}, 201, "eva"),
    ("GET", "/api/eva/eva-demo", None, 200, "eva"),
    ("POST", "/api/eva/eva-demo/position", POS, 200, "eva"),
    ("POST", "/api/eva/eva-demo/observations", {**POS, "note": "n"}, 201, "observation"),
    ("POST", "/api/eva/eva-demo/obstacles", POS, 200, "obstacle_response"),
    ("POST", "/api/eva/eva-demo/simulate", {"speed": 10}, 200, "simulation_state"),
    ("GET", "/api/sites/fictif/ground-images", None, 200, "ground_images"),
    ("GET", "/api/plans/plan-demo/export.geojson", None, 200, "export_plan"),
    ("GET", "/api/eva/eva-demo/logbook", None, 200, "logbook"),
]


@pytest.mark.parametrize(("method", "url", "body", "status", "name"), CASES)
def test_route_returns_example(
    method: str, url: str, body: dict[str, Any] | None, status: int, name: str | None
) -> None:
    res = client.request(method, url, json=body)
    assert res.status_code == status, res.text
    if name:
        assert res.json() == example(name)


def test_other_routes() -> None:
    assert client.delete("/api/targets/T1").status_code == 204
    assert client.post("/api/scenarios/solar-event/stop").json()["running"] is False
    ack = client.post("/api/alerts/alert-1/ack").json()
    assert ack["acknowledged"] is True
    health = client.get("/api/health").json()
    assert health["contracts"] == "contrats-v1" and "fictif" in health["sites"]
    assert client.get("/api/presets").status_code == 200
    vec = client.get("/api/sites/fictif/vector/rover_traverse").json()
    assert vec["type"] == "FeatureCollection"
    assert client.get("/api/_contracts/ws-message").status_code == 200


def test_unknown_site_is_a_clear_404() -> None:
    res = client.get("/api/sites/inconnu")
    assert res.status_code == 404
    assert "inconnu" in res.json()["detail"]


def test_tiles_are_served() -> None:
    manifest = example("site_manifest")
    tiles = examples_dir().parents[1] / "fixtures/sites/fictif/tiles/hirise_vis/16"
    x = sorted(p.name for p in tiles.iterdir())[0]
    y = sorted(p.stem for p in (tiles / x).iterdir())[0]
    res = client.get(f"/tiles/fictif/hirise_vis/16/{x}/{y}.webp")
    assert res.status_code == 200 and res.headers["content-type"] == "image/webp"
    assert manifest["terrain"]["format"] == "png"
    assert client.get("/tiles/fictif/hirise_vis/3/0/0.webp").status_code == 404


def test_websocket_replays_every_message_type() -> None:
    with client.websocket_connect("/ws/eva/eva-demo") as ws:
        types = [ws.receive_json()["type"] for _ in range(6)]
    assert types == ["telemetry", "alert", "alert_cleared", "conditions", "route_updated", "budget"]
