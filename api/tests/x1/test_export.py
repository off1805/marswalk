"""Acceptation X1 : export GeoJSON du plan et carnet d'une sortie simulée."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from marswalk_api.main import app
from marswalk_api.services.a4 import A4Service
from marswalk_core.geodesy import distance_m
from marswalk_core.schemas import (
    EvaCreate,
    EvaStatus,
    FeatureCollection,
    LonLat,
    ObservationCreate,
    ObstacleReport,
    Plan,
)
from marswalk_core.site_package import load_site

client = TestClient(app)


def geojson() -> dict[str, Any]:
    res = client.get("/api/plans/plan-demo/export.geojson")
    assert res.status_code == 200, res.text
    data: dict[str, Any] = res.json()
    return data


def test_plan_geojson_is_valid_and_reopens_in_place(sim: A4Service) -> None:
    data = geojson()
    FeatureCollection.model_validate(data)
    # Relisible tel quel : texte JSON pur, pas de NaN, une géométrie par entité.
    json.loads(json.dumps(data, allow_nan=False))
    site = load_site("fictif")
    west, south, east, north = site.manifest.bbox
    ids = [f["id"] for f in data["features"]]
    assert len(ids) == len(set(ids)), "identifiants d'entité en double"
    for f in data["features"]:
        geom = f["geometry"]
        assert geom["type"] in ("Point", "LineString")
        points = [geom["coordinates"]] if geom["type"] == "Point" else geom["coordinates"]
        for lon, lat in points:
            assert west <= lon <= east and south <= lat <= north, (f["id"], lon, lat)
        # Propriétés plates : la table attributaire de QGIS n'a que des scalaires.
        for value in f["properties"].values():
            assert value is None or isinstance(value, (str, int, float, bool))
    assert "IAU_2015:49900" in data["crs_note"]


def test_plan_geojson_matches_the_selected_route(sim: A4Service) -> None:
    plan = Plan.model_validate(client.get("/api/plans/plan-demo").json())
    route = next(r for r in plan.routes if r.id == plan.selected_route_id)
    data = geojson()
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for f in data["features"]:
        by_kind.setdefault(f["properties"]["kind"], []).append(f)

    (line,) = by_kind["route"]
    assert line["id"] == route.id and line["properties"]["selected"] is True
    assert line["properties"]["distance_m"] == route.totals.distance_m
    assert [tuple(c) for c in line["geometry"]["coordinates"]] == [
        (round(c[0], 7), round(c[1], 7)) for c in route.geometry.coordinates
    ]

    segments = by_kind["segment"]
    assert [s["properties"]["index"] for s in segments] == [s.index for s in route.segments]
    total = sum(s["properties"]["distance_m"] for s in segments)
    assert abs(total - route.totals.distance_m) < 0.1
    for s, seg in zip(segments, route.segments, strict=True):
        first, last = s["geometry"]["coordinates"][0], s["geometry"]["coordinates"][-1]
        assert distance_m(LonLat(*first), LonLat(*seg.from_point)) < 0.01
        assert distance_m(LonLat(*last), LonLat(*seg.to_point)) < 0.01

    targets = by_kind["target"]
    assert [t["id"] for t in targets] == ["T1", "T3", "T2"]
    assert [t["properties"]["order"] for t in targets] == [1, 2, 3]
    assert targets[0]["properties"]["name"] == "Front du delta"
    (habitat,) = by_kind["habitat"]
    assert habitat["geometry"]["coordinates"] == list(plan.start)


def test_registered_plan_is_exported(sim: A4Service) -> None:
    plan = Plan.model_validate(client.get("/api/plans/plan-demo").json())
    other = plan.model_copy(update={"id": "plan-2", "selected_route_id": "route-science"})
    sim.plans.register(other)
    data = client.get("/api/plans/plan-2/export.geojson").json()
    assert data["features"][0]["id"] == "route-science"


def test_logbook_of_a_simulated_eva_lists_every_observation(sim: A4Service) -> None:
    eva = sim.start(EvaCreate(plan_id="plan-demo", route_id="route-safest"))
    notes = ["Litage oblique", "Bloc à olivine", "Ride de sable active"]
    obs_ids = []
    for i, note in enumerate(notes):
        sim.step(eva.id, 400.0)
        here = sim.get(eva.id).position
        photo = "https://example.org/obs.jpg" if i == 1 else None
        obs = sim.add_observation(
            eva.id, ObservationCreate(position=here, note=note, photo_url=photo)
        )
        obs_ids.append(obs.id)
    ahead = next(
        p.position
        for p in sim.current_route(eva.id).profile
        if p.time_s > sim.get(eva.id).elapsed_s + 120
    )
    sim.report_obstacle(eva.id, ObstacleReport(position=ahead, radius_m=5.0))
    for _ in range(2000):
        if sim.step(eva.id, 20.0).status == EvaStatus.completed:
            break

    res = client.get(f"/api/eva/{eva.id}/logbook")
    assert res.status_code == 200, res.text
    book = res.json()
    entries = book["entries"]
    assert book["eva_id"] == eva.id and book["site_id"] == "fictif"
    assert entries[0]["kind"] == "start" and entries[-1]["kind"] == "end"
    observed = [e for e in entries if e["kind"] == "observation"]
    assert [e["ref_id"] for e in observed] == obs_ids
    assert [e["text"].split(" (photo")[0] for e in observed] == notes
    assert "photo : https://example.org/obs.jpg" in observed[1]["text"]
    for e in observed:
        assert e["position"] is not None and e["sol"] == 14 and len(e["lmst"]) == 8
    kinds = {e["kind"] for e in entries}
    assert {"target", "obstacle", "reroute"} <= kinds
    times = [e["utc"] for e in entries]
    assert times == sorted(times)


def test_unknown_plan_and_eva_are_404(sim: A4Service) -> None:
    assert client.get("/api/plans/plan-inconnu/export.geojson").status_code == 404
    assert client.get("/api/eva/eva-inconnue/logbook").status_code == 404
