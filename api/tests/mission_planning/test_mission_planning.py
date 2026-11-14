"""Tests unitaires et d'intégration pour mission_planning (Cibles, Itinéraires, Risques)."""

import pytest
from fastapi.testclient import TestClient

from marswalk_api.main import app
from marswalk_api.services.mission_planning.memory_repo import (
    InMemoryPlanRepository,
    InMemorySafetySettingsRepository,
    InMemoryTargetRepository,
)
from marswalk_api.services.mission_planning.services import HazardService, PlanComputationService
from marswalk_core.schemas import PlanCreate, SafetySettings, TargetCreate, TargetUpdate

client = TestClient(app)


def test_target_crud_lifecycle() -> None:
    create_payload = {
        "name": "Cratère secondaire",
        "kind": "science",
        "position": [77.581, 18.382],
        "objective": "Analyse géologique des éjectas",
        "measurement": "Spectrométrie",
        "work_time_s": 600.0,
        "priority": 2,
    }
    res_create = client.post("/api/sites/fictif/targets", json=create_payload)
    assert res_create.status_code == 201
    created = res_create.json()
    target_id = created["id"]
    assert target_id.startswith("target-")
    assert created["name"] == "Cratère secondaire"
    assert created["site_id"] == "fictif"

    res_list = client.get("/api/sites/fictif/targets")
    assert res_list.status_code == 200
    targets = res_list.json()
    assert any(t["id"] == target_id for t in targets)

    update_payload = {"work_time_s": 900.0, "priority": 1}
    res_patch = client.patch(f"/api/targets/{target_id}", json=update_payload)
    assert res_patch.status_code == 200
    patched = res_patch.json()
    assert patched["work_time_s"] == 900.0
    assert patched["priority"] == 1
    assert patched["name"] == "Cratère secondaire"

    res_del = client.delete(f"/api/targets/{target_id}")
    assert res_del.status_code == 204

    res_del_again = client.delete(f"/api/targets/{target_id}")
    assert res_del_again.status_code == 404


def test_compute_plan_dynamic() -> None:
    res_target = client.post(
        "/api/sites/fictif/targets",
        json={"name": "Point d'intérêt A", "position": [77.575, 18.375], "work_time_s": 300.0},
    )
    assert res_target.status_code == 201
    tid = res_target.json()["id"]

    plan_req = {
        "target_ids": [tid],
        "variants": ["safest", "fastest"],
        "optimize_order": True,
        "departure_utc": "2026-11-14T14:00:00Z",
    }
    res_plan = client.post("/api/sites/fictif/plans", json=plan_req)
    assert res_plan.status_code == 201
    plan = res_plan.json()
    assert plan["site_id"] == "fictif"
    assert plan["status"] == "computed"
    assert len(plan["routes"]) >= 1
    assert "compute_time_ms" in plan

    plan_id = plan["id"]
    res_get = client.get(f"/api/plans/{plan_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == plan_id


def test_hazards_polygons_dynamic() -> None:
    res = client.get("/api/sites/fictif/hazards?preset=custom_preset")
    assert res.status_code == 200
    fc = res.json()
    assert fc["type"] == "FeatureCollection"
    assert "features" in fc


def test_safety_settings_roundtrip() -> None:
    res_get = client.get("/api/sites/fictif/settings")
    assert res_get.status_code == 200
    initial = res_get.json()

    updated_settings = {**initial, "max_slope_deg": 22.5, "min_reserve_pct": 35.0}
    res_put = client.put("/api/sites/fictif/settings", json=updated_settings)
    assert res_put.status_code == 200
    put_result = res_put.json()
    assert put_result["max_slope_deg"] == 22.5
    assert put_result["min_reserve_pct"] == 35.0

    res_get2 = client.get("/api/sites/fictif/settings")
    assert res_get2.json()["max_slope_deg"] == 22.5


def test_repositories_direct_unit() -> None:
    repo = InMemoryTargetRepository(seed=False)
    assert len(repo.list_by_site("fictif")) == 0
    t = repo.create("fictif", TargetCreate(name="Target 1", position=(77.58, 18.38)))
    assert t.id is not None
    assert len(repo.list_by_site("fictif")) == 1

    updated = repo.update(t.id, TargetUpdate(name="Target 1 Modified"))
    assert updated is not None
    assert updated.name == "Target 1 Modified"

    deleted = repo.delete(t.id)
    assert deleted is True
    assert repo.get(t.id) is None
