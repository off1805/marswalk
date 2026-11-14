"""Simulateur (A4) piloté pas à pas : avance, budgets, recalcul local, retour forcé."""

from __future__ import annotations

import time
from datetime import datetime

from marswalk_api.services.a3 import A3Service
from marswalk_api.services.a4 import A4Service
from marswalk_api.services.a4.routing import distance_to_line_m
from marswalk_core.geodesy import distance_m
from marswalk_core.schemas import (
    Conditions,
    EvaCreate,
    EvaStatus,
    LonLat,
    ObservationCreate,
    ObstacleReport,
    PositionReport,
    SpaceWeather,
)
from marswalk_core.site_package import load_site

DEMO = EvaCreate(plan_id="plan-demo", route_id="route-safest")


def run_until_done(sim: A4Service, eva_id: str, dt: float = 10.0, limit: int = 5000) -> None:
    for _ in range(limit):
        if sim.step(eva_id, dt).status in (EvaStatus.completed, EvaStatus.aborted):
            return
    raise AssertionError("la sortie ne se termine pas")


def ahead(sim: A4Service, eva_id: str, seconds: float) -> LonLat:
    """Point du tracé que l'astronaute atteindra dans ``seconds`` secondes de marche."""
    eva = sim.get(eva_id)
    route = sim.current_route(eva_id)
    return next(LonLat(*p.position) for p in route.profile if p.time_s >= eva.elapsed_s + seconds)


def test_walks_the_whole_route_and_comes_home(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    assert eva.status == EvaStatus.active and eva.next_target_id == "T1"
    route = sim.current_route(eva.id)
    sim.step(eva.id, 300.0)
    moving = sim.get(eva.id)
    assert 0 < moving.distance_done_m < route.totals.distance_m
    assert moving.speed_mps > 0
    assert moving.consumables.oxygen_pct < 100 and moving.dose_usv > 0
    assert moving.reserve_pct is not None and moving.time_to_pnr_s is not None
    assert moving.return_time_s is not None and moving.return_time_s > 0

    run_until_done(sim, eva.id)
    done = sim.get(eva.id)
    assert done.status == EvaStatus.completed and done.ended_at is not None
    assert distance_m(LonLat(*done.position), LonLat(*route.geometry.coordinates[-1])) < 1.0
    assert abs(done.distance_done_m - route.totals.distance_m) < 1.0
    # Toute la sortie est consommée : temps de marche et de travail aux trois cibles.
    assert done.elapsed_s >= route.totals.duration_s
    plan = sim.plan_source("plan-demo")
    assert plan is not None
    o2 = 100 * route.totals.consumption.oxygen_kg / plan.suit.oxygen_capacity_kg
    assert abs((100 - done.consumables.oxygen_pct) - o2) < 1.0

    kinds = [e.kind for e in sim.logbook(eva.id).entries]
    assert kinds[0] == "start" and kinds[-1] == "end"
    targets = [e.text for e in sim.logbook(eva.id).entries if e.kind == "target"]
    assert targets == [f"Arrivée à la cible {t}" for t in ("T1", "T3", "T2")]


def test_astronaut_stops_while_working_at_a_target(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    route = sim.current_route(eva.id)
    walk = route.segments[0].duration_s
    sim.step(eva.id, walk + 10)
    at_target = sim.get(eva.id)
    sim.step(eva.id, 300)
    still = sim.get(eva.id)
    assert still.position == at_target.position and still.speed_mps == 0
    assert still.consumables.oxygen_pct < at_target.consumables.oxygen_pct


def test_obstacle_reroutes_locally_in_under_two_seconds(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    sim.step(eva.id, 60.0)
    obstacle = ahead(sim, eva.id, 120.0)
    t0 = time.perf_counter()
    res = sim.report_obstacle(eva.id, ObstacleReport(position=obstacle, radius_m=8.0))
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0 and res.compute_time_ms is not None and res.compute_time_ms < 2000
    assert res.route is not None
    site = load_site("fictif")
    clearance = distance_to_line_m(
        site, [LonLat(*c) for c in res.route.geometry.coordinates], obstacle
    )
    assert clearance >= 8.0, f"le tracé passe à {clearance:.1f} m de l'obstacle"
    # Le nouvel itinéraire part d'ici, garde les cibles restantes et finit à l'habitat.
    here = sim.get(eva.id).position
    assert distance_m(LonLat(*res.route.geometry.coordinates[0]), LonLat(*here)) < 1.0
    assert [s.to_target_id for s in res.route.segments] == ["T1", "T3", "T2", None]
    assert res.route.explanation[0].reasons[0].startswith("Obstacle signalé")
    assert sim.current_route(eva.id).id == res.route.id

    # L'astronaute contourne bien l'obstacle en avançant.
    for _ in range(40):
        sim.step(eva.id, 5.0)
        assert distance_m(LonLat(*sim.get(eva.id).position), obstacle) >= 8.0


def test_obstacle_away_from_route_changes_nothing(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    far = LonLat(77.565, 18.366)
    res = sim.report_obstacle(eva.id, ObstacleReport(position=far, radius_m=5.0))
    assert res.route is None
    assert [e.kind for e in sim.logbook(eva.id).entries][-1] == "obstacle"


def test_obstacle_while_working_waits_for_the_end_of_the_work(
    sim: A4Service, a3: A3Service
) -> None:
    eva = sim.start(DEMO)
    first = sim.current_route(eva.id).segments[0]
    sim.step(eva.id, first.duration_s + 60)
    obstacle = next(
        LonLat(*p.position)
        for p in sim.current_route(eva.id).profile
        if p.segment_index == 1 and p.distance_m > first.distance_m + 80
    )
    res = sim.report_obstacle(eva.id, ObstacleReport(position=obstacle, radius_m=6.0))
    assert res.route is not None
    assert res.route.segments[0].to_target_id == "T3"
    working = sim.get(eva.id)
    sim.step(eva.id, 600)
    assert sim.get(eva.id).position == working.position  # le travail continue
    sim.step(eva.id, first.work_time_s)
    assert sim.get(eva.id).position != working.position


def test_off_route_position_triggers_a_reroute(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    sim.step(eva.id, 120.0)
    here = sim.get(eva.id).position
    off = LonLat(here[0] + 0.0012, here[1] - 0.0008)  # environ 60 m à côté du tracé
    moved = sim.report_position(eva.id, PositionReport(position=off))
    route = sim.current_route(eva.id)
    assert moved.position == off
    assert route.id != "route-safest"
    assert route.explanation[0].reasons[0].startswith("Écart au tracé")
    assert distance_m(LonLat(*route.geometry.coordinates[0]), off) < 1.0


def test_position_on_route_keeps_the_route(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    point = ahead(sim, eva.id, 200.0)
    sim.report_position(eva.id, PositionReport(position=point))
    assert sim.current_route(eva.id).id == "route-safest"
    sim.step(eva.id, 10.0)
    assert distance_m(LonLat(*sim.get(eva.id).position), point) < 15.0


def test_danger_alert_forces_the_return(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    # Pic de dose : l'alerte de site « Retour à l'abri » est levée au premier tic de A3.
    a3.provider_factory = lambda mode, scenario_id=None: _Spike()
    a3.tick()
    sim.step(eva.id, 10.0)
    returning = sim.get(eva.id)
    assert returning.status == EvaStatus.returning
    route = sim.current_route(eva.id)
    assert route.explanation[0].reasons[0].startswith("Retour forcé")
    assert [s.to_target_id for s in route.segments] == [None]
    run_until_done(sim, eva.id)
    done = sim.get(eva.id)
    habitat = LonLat(*load_site("fictif").manifest.habitat)
    assert done.status == EvaStatus.completed
    assert distance_m(LonLat(*done.position), habitat) < 1.0
    assert any(e.kind == "reroute" for e in sim.logbook(eva.id).entries)


def test_observation_goes_to_the_logbook(sim: A4Service, a3: A3Service) -> None:
    eva = sim.start(DEMO)
    obs = sim.add_observation(
        eva.id, ObservationCreate(position=eva.position, note="Litage oblique")
    )
    assert obs.id == "obs-1" and obs.eva_id == eva.id and obs.sol == 14
    entry = sim.logbook(eva.id).entries[-1]
    assert entry.kind == "observation" and entry.ref_id == obs.id and entry.lmst == obs.lmst


class _Spike:
    def current(self, utc: datetime) -> Conditions:
        return Conditions(
            utc=utc,
            mode="historical",
            dust_tau=0.6,
            dose_rate_usv_h=250.0,
            space_weather=SpaceWeather(),
            source="test",
        )

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        return [self.current(utc)]
