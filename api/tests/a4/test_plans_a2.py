"""Une sortie démarre sur un plan calculé par A2 (étape 10 du scénario de démo).

Avant ce branchement, ``POST /api/eva`` ne connaissait que ``plan-demo`` et répondait
« Plan inconnu » pour tout plan de ``POST /api/sites/{site_id}/plans`` : l'interface ne
pouvait lancer aucune sortie. Voir ``tasks/change-requests/A4-source-des-plans.md``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from marswalk_api.main import app
from marswalk_api.services.a4 import A4Service


def test_eva_starts_on_a_plan_computed_by_a2(sim: A4Service) -> None:
    with TestClient(app) as client:
        res = client.post(
            "/api/sites/fictif/plans",
            json={"target_ids": ["T2", "T3"], "optimize_order": True, "variants": ["safest"]},
        )
        assert res.status_code == 201, res.text
        plan = res.json()

        res = client.post("/api/eva", json={"plan_id": plan["id"], "route_id": "route-safest"})
        assert res.status_code == 201, res.text
        assert res.json()["plan_id"] == plan["id"]

        # L'export GeoJSON du plan (X1) lit la même source.
        res = client.get(f"/api/plans/{plan['id']}/export.geojson")
        assert res.status_code == 200, res.text


def test_demo_plan_still_starts(sim: A4Service) -> None:
    with TestClient(app) as client:
        res = client.post("/api/eva", json={"plan_id": "plan-demo", "route_id": "route-safest"})
        assert res.status_code == 201, res.text
