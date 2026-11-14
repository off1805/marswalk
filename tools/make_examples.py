"""Génère ``contracts/examples/`` à partir du site fictif et des bouchons (T00).

Les exemples sont les réponses des routes en bouchon et les données du faux serveur du
front (MSW). Ils sont gelés avec contrats-v1 : on ne relance ce script que dans une PR
de changement de contrat. ``api/tests`` vérifie que chaque exemple respecte son modèle.

Usage : ``uv run python tools/make_examples.py``
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from marswalk_conditions import get_provider, list_scenarios
from marswalk_core.config import load_safety_settings, load_suit
from marswalk_core.geodesy import to_analysis
from marswalk_core.grids import RouteOptions
from marswalk_core.marstime import mars_time
from marswalk_core.paths import list_package_ids, repo_root
from marswalk_core.schemas import (
    CONTRACTS_VERSION,
    Alert,
    AlertCause,
    AlertClearedPayload,
    AlertLevel,
    BudgetPayload,
    ConsumablesState,
    Eva,
    EvaStatus,
    Feature,
    FeatureCollection,
    Forecast,
    Health,
    LayerStatus,
    LineStringGeometry,
    Logbook,
    LogbookEntry,
    LonLat,
    Observation,
    ObstacleResponse,
    Plan,
    PlanStatus,
    PointGeometry,
    PointQuery,
    PointValue,
    RouteUpdatedPayload,
    ScenarioState,
    SimulationState,
    SiteSummary,
    Target,
    TargetKind,
    TelemetryPayload,
    TimeInfo,
    WsAlert,
    WsAlertCleared,
    WsBudget,
    WsConditions,
    WsRouteUpdated,
    WsTelemetry,
)
from marswalk_core.site_package import load_site
from marswalk_planner.cost import build_cost_grid
from marswalk_planner.hazards import hazard_polygons
from marswalk_planner.return_field import return_field, return_time_at
from marswalk_planner.variants import plan_variants

NOW = datetime(2026, 11, 14, 10, 0, 0, tzinfo=UTC)
OUT = repo_root() / "contracts" / "examples"


def dump(name: str, obj: Any) -> None:
    data: Any
    if isinstance(obj, BaseModel):
        data = obj.model_dump(mode="json")
    elif isinstance(obj, list):
        data = [o.model_dump(mode="json") if isinstance(o, BaseModel) else o for o in obj]
    else:
        data = obj
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def round_coords(fc: FeatureCollection, ndigits: int = 6) -> FeatureCollection:
    data = json.loads(fc.model_dump_json())

    def walk(x: Any) -> Any:
        if isinstance(x, float):
            return round(x, ndigits)
        if isinstance(x, list):
            return [walk(i) for i in x]
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        return x

    return FeatureCollection.model_validate(walk(data))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    site = load_site("fictif")
    m = site.manifest
    lon_c = (m.bbox[0] + m.bbox[2]) / 2
    mt = mars_time(NOW, lon_c, m.mission_epoch_utc)
    stamp = {"utc": NOW, "sol": mt.sol, "lmst": mt.lmst}

    dump(
        "health",
        Health(
            status="ok",
            version="0.1.0",
            contracts=CONTRACTS_VERSION,
            database="ok",
            sites=list_package_ids(),
        ),
    )
    dump("sites", [SiteSummary(site_id=m.site_id, name=m.name, bbox=m.bbox, habitat=m.habitat)])
    dump("site_manifest", m)
    dump("time", TimeInfo(**mt.model_dump(), site_id=m.site_id, lon_east=lon_c))

    # Cibles du site fictif.
    seed = json.loads((repo_root() / "config/sites/fictif/targets-seed.geojson").read_text())
    targets = [
        Target(
            id=f["id"],
            site_id="fictif",
            name=f["properties"]["name"],
            kind=TargetKind(f["properties"]["kind"]),
            position=LonLat(*f["geometry"]["coordinates"]),
            objective=f["properties"]["objective"],
            measurement=f["properties"]["measurement"],
            work_time_s=f["properties"]["work_time_s"],
            priority=f["properties"]["priority"],
            created_at=NOW,
            updated_at=NOW,
        )
        for f in seed["features"]
    ]
    dump("targets", targets)
    dump("target", targets[0])

    # Interrogation de point : cible T2, au bord des dunes.
    settings = load_safety_settings()
    suit = load_suit()
    grid = build_cost_grid(site, settings, None)
    field = return_field(grid, LonLat(*m.habitat), suit)
    p = targets[1].position
    values = []
    for info in m.layers:
        if not info.cog:
            continue
        v = site.sample(info.id, p.lon, p.lat)
        label = None
        if info.legend and info.legend.type == "categorical" and v is not None:
            label = next((s.label for s in info.legend.stops if s.value == v), None)
        values.append(
            PointValue(
                layer_id=info.id,
                title=info.title,
                value=v,
                unit=info.unit,
                label=label,
                status=info.status,
                source=info.source,
                uncertainty=info.uncertainty,
                acquired=info.acquired,
                resolution_m=info.resolution_m,
            )
        )
    values.append(
        PointValue(
            layer_id="crism_minerals_hr",
            title="Minéralogie haute résolution (absente)",
            value=None,
            status=LayerStatus.missing,
            source=values[0].source.model_copy(update={"note": "exemple de couche manquante"}),
        )
    )
    xy = to_analysis(site, p.lon, p.lat)
    rt = return_time_at(field, p.lon, p.lat)
    dump(
        "query",
        PointQuery(
            site_id="fictif",
            position=p,
            analysis_xy=(round(xy[0], 2), round(xy[1], 2)),
            values=values,
            return_time_s=None if rt is None else round(rt, 1),
        ),
    )

    dump("hazards", round_coords(hazard_polygons(site, settings)))
    dump("settings", settings)

    # Plan de trois cibles.
    provider = get_provider("scenario", "solar-event")
    cond = provider.current(NOW).model_copy(update={"sol": mt.sol, "lmst": mt.lmst})
    chosen = [targets[0], targets[2], targets[1]]
    routes = plan_variants(
        site, settings, LonLat(*m.habitat), chosen, RouteOptions(suit=suit, conditions=cond)
    )
    plan = Plan(
        id="plan-demo",
        site_id="fictif",
        name="Sortie de démonstration",
        status=PlanStatus.computed,
        created_at=NOW,
        departure_utc=NOW + timedelta(hours=1),
        start=LonLat(*m.habitat),
        return_to=LonLat(*m.habitat),
        target_ids=[t.id for t in chosen],
        settings=settings,
        suit=suit,
        routes=routes,
        selected_route_id=routes[0].id,
        compute_time_ms=120.0,
    )
    dump("plan", plan)

    dump("conditions_current", cond)
    dump(
        "conditions_forecast",
        Forecast(site_id="fictif", generated_at=NOW, items=provider.forecast(NOW, 6)),
    )
    dump("scenarios", list_scenarios())
    dump(
        "scenario_state",
        ScenarioState(
            scenario_id="solar-event", running=True, started_at=NOW, elapsed_s=0.0, speed=10.0
        ),
    )

    route = routes[0]
    pos = route.profile[len(route.profile) // 4].position
    alert = Alert(
        id="alert-1",
        eva_id="eva-demo",
        level=AlertLevel.danger,
        cause=AlertCause.solar_event,
        title="Événement à particules solaires",
        message="Débit de dose en forte hausse (RAD). Abri nécessaire.",
        action="Retour à l'abri",
        value=250.0,
        threshold=50.0,
        unit="µSv/h",
        position=pos,
        **stamp,
    )
    caution = Alert(
        id="alert-2",
        eva_id="eva-demo",
        level=AlertLevel.caution,
        cause=AlertCause.slope,
        title="Pente soutenue",
        message="Pente de 14° sur les 50 prochains mètres.",
        action="Ralentir",
        value=14.0,
        threshold=10.0,
        unit="deg",
        position=pos,
        **stamp,
    )
    dump("alerts", [alert, caution])

    consumables = ConsumablesState(oxygen_pct=82.0, battery_pct=85.0, water_pct=88.0)
    eva = Eva(
        id="eva-demo",
        site_id="fictif",
        plan_id=plan.id,
        route_id=route.id,
        crew=["EV1"],
        status=EvaStatus.active,
        started_at=NOW,
        position=pos,
        heading_deg=35.0,
        speed_mps=0.9,
        distance_done_m=route.profile[len(route.profile) // 4].distance_m,
        elapsed_s=900.0,
        consumables=consumables,
        dose_usv=4.2,
        next_target_id=chosen[0].id,
        reserve_pct=62.0,
        time_to_pnr_s=5400.0,
        return_time_s=600.0,
        active_alert_ids=["alert-1"],
    )
    dump("eva", eva)
    dump(
        "observation",
        Observation(
            id="obs-1",
            eva_id=eva.id,
            position=pos,
            note="Litage oblique visible sur le bloc",
            target_id=None,
            photo_url=None,
            **stamp,
        ),
    )
    dump(
        "obstacle_response",
        ObstacleResponse(obstacle_id="obst-1", route=route, compute_time_ms=80.0),
    )
    dump(
        "simulation_state",
        SimulationState(eva_id=eva.id, running=True, speed=10.0, scenario_id="solar-event"),
    )

    images = FeatureCollection.model_validate_json(
        (site.root / "vector" / "ground_images.geojson").read_text()
    )
    dump("ground_images", images)

    export = FeatureCollection(
        features=[
            Feature(
                id=route.id,
                geometry=LineStringGeometry(coordinates=route.geometry.coordinates),
                properties={
                    "plan_id": plan.id,
                    "variant": route.variant.value,
                    "distance_m": route.totals.distance_m,
                    "duration_s": route.totals.duration_s,
                },
            ),
            *[
                Feature(
                    id=t.id,
                    geometry=PointGeometry(coordinates=t.position),
                    properties={"name": t.name, "objective": t.objective},
                )
                for t in chosen
            ],
        ]
    )
    dump("export_plan", export)
    dump(
        "logbook",
        Logbook(
            eva_id=eva.id,
            site_id="fictif",
            entries=[
                LogbookEntry(
                    kind="start", text="Départ de l'habitat", position=LonLat(*m.habitat), **stamp
                ),
                LogbookEntry(
                    kind="observation",
                    text="Litage oblique visible sur le bloc",
                    position=pos,
                    ref_id="obs-1",
                    **stamp,
                ),
                LogbookEntry(
                    kind="alert",
                    text="Événement à particules solaires : retour à l'abri",
                    position=pos,
                    ref_id="alert-1",
                    **stamp,
                ),
            ],
        ),
    )

    # Messages WebSocket.
    dump(
        "ws_telemetry",
        WsTelemetry(
            payload=TelemetryPayload(
                position=pos,
                heading_deg=35.0,
                speed_mps=0.9,
                consumables=consumables,
                dose_usv=4.2,
                distance_done_m=eva.distance_done_m,
                elapsed_s=900.0,
            ),
            **stamp,
        ),
    )
    dump("ws_alert", WsAlert(payload=alert, **stamp))
    dump(
        "ws_alert_cleared",
        WsAlertCleared(
            payload=AlertClearedPayload(alert_id="alert-2", reason="Pente redevenue faible"),
            **stamp,
        ),
    )
    dump("ws_conditions", WsConditions(payload=cond, **stamp))
    dump(
        "ws_route_updated",
        WsRouteUpdated(
            payload=RouteUpdatedPayload(reason="Retour forcé vers l'habitat", route=route), **stamp
        ),
    )
    dump(
        "ws_budget",
        WsBudget(
            payload=BudgetPayload(
                reserve_pct=62.0,
                time_to_pnr_s=5400.0,
                return_time_s=600.0,
                limiting_consumable="oxygen",
            ),
            **stamp,
        ),
    )

    sizes = sorted((p.stat().st_size, p.name) for p in Path(OUT).glob("*.json"))
    for size, name in sizes:
        print(f"{size / 1024:8.1f} Ko  {name}")


if __name__ == "__main__":
    main()
