"""Simulateur de sortie (A4) : un astronaute virtuel qui suit l'itinéraire choisi.

Le temps de sortie (``Eva.elapsed_s``) avance par pas. Pour chaque pas, le simulateur :

1. place l'astronaute sur le profil de l'itinéraire suivi (``ProfileSample.time_s`` compte la
   marche et le travail aux cibles : l'astronaute s'arrête le temps du travail) ;
2. ajoute la consommation de l'instant (celle du tronçon en cours, rapportée à sa durée) et
   la dose au débit mesuré par les conditions de A3 ;
3. recalcule la réserve au retour, le temps de retour et le temps avant le point de non-retour ;
4. remet la sortie à A3 (``ingest_eva``), qui publie ``telemetry``, ``budget`` et les alertes ;
5. si une alerte ``danger`` l'exige, force le retour vers l'habitat (``route_updated``).

Un obstacle signalé ou un écart au tracé déclenche un recalcul local depuis la position
courante, vers les cibles restantes puis l'habitat (``routing.compute_route``).

``simulate`` fait avancer le temps en tâche de fond, ``speed`` secondes de sortie par seconde
réelle ; ``step`` fait avancer d'un pas donné (tests, rejeu).
"""

from __future__ import annotations

import asyncio
import bisect
import contextlib
import itertools
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache

from marswalk_api.services.a3 import A3Service
from marswalk_api.services.a3 import get_service as get_a3
from marswalk_core.geodesy import bearing_deg
from marswalk_core.schemas import (
    Alert,
    AlertCause,
    AlertLevel,
    ConsumablesState,
    Eva,
    EvaCreate,
    EvaStatus,
    Logbook,
    LogbookEntry,
    LonLat,
    Observation,
    ObservationCreate,
    ObstacleReport,
    ObstacleResponse,
    Plan,
    PositionReport,
    Route,
    RouteUpdatedPayload,
    SimulationState,
    WsRouteUpdated,
)
from marswalk_core.site_package import Site, load_site

from .plans import PlanRegistry, PlanSource
from .routing import (
    GridCache,
    LocalPlan,
    Obstacle,
    compute_route,
    distance_to_line_m,
    return_time_s,
    stop_target,
    touches,
)

DEMO_EVA_ID = "eva-demo"
"""Sortie de démonstration : créée à la demande sur ``plan-demo`` / ``route-safest``."""
DEMO_ROUTE_ID = "route-safest"
OFF_ROUTE_M = 20.0
"""Écart au tracé, en mètres, au-delà duquel une position signalée déclenche un recalcul."""
RETURN_CAUSES = frozenset(
    {
        AlertCause.radiation,
        AlertCause.solar_event,
        AlertCause.dust,
        AlertCause.consumables,
        AlertCause.return_reserve,
        AlertCause.point_of_no_return,
        AlertCause.illumination,
    }
)
"""Causes d'une alerte ``danger`` qui imposent le retour (pente et radio : action locale)."""
CONSUMABLES = ("oxygen", "battery", "water")


class EvaNotFoundError(LookupError):
    pass


class PlanNotFoundError(LookupError):
    pass


# -- itinéraire suivi -------------------------------------------------------------------


@dataclass
class _Track:
    """Un itinéraire suivi à partir du temps de sortie ``t0``."""

    route: Route
    t0: float
    distance_before: float
    times: list[float] = field(init=False)
    dist: list[float] = field(init=False)
    pos: list[LonLat] = field(init=False)
    seg_arrive: list[float] = field(init=False)
    seg_end: list[float] = field(init=False)

    def __post_init__(self) -> None:
        prof = self.route.profile
        if prof:
            self.times = [p.time_s for p in prof]
            self.dist = [p.distance_m for p in prof]
            self.pos = [LonLat(*p.position) for p in prof]
        else:
            coords = [LonLat(*c) for c in self.route.geometry.coordinates]
            self.times, self.dist, self.pos = [0.0] * len(coords), [0.0] * len(coords), coords
        start = 0.0
        self.seg_arrive, self.seg_end = [], []
        for s in self.route.segments:
            self.seg_arrive.append(start + s.duration_s)
            start += s.duration_s + s.work_time_s
            self.seg_end.append(start)

    @property
    def end_time(self) -> float:
        return max(self.times[-1] if self.times else 0.0, self.seg_end[-1] if self.seg_end else 0.0)

    def at(self, tau: float) -> tuple[LonLat, float, float]:
        """Position, distance parcourue sur l'itinéraire et vitesse au temps ``tau``."""
        if tau <= self.times[0]:
            return self.pos[0], self.dist[0], 0.0
        if tau >= self.times[-1]:
            return self.pos[-1], self.dist[-1], 0.0
        j = bisect.bisect_right(self.times, tau) - 1
        dt = self.times[j + 1] - self.times[j]
        if dt <= 0:
            return self.pos[j + 1], self.dist[j + 1], 0.0
        k = (tau - self.times[j]) / dt
        a, b = self.pos[j], self.pos[j + 1]
        p = LonLat(a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        dd = self.dist[j + 1] - self.dist[j]
        return p, self.dist[j] + dd * k, dd / dt

    def segment(self, tau: float) -> int:
        i = bisect.bisect_right(self.seg_end, tau)
        return min(i, len(self.seg_end) - 1)

    def working(self, tau: float) -> int | None:
        """Tronçon dont l'astronaute fait le travail à la cible d'arrivée, ou ``None``."""
        i = self.segment(tau)
        seg = self.route.segments[i]
        if seg.to_target_id and self.seg_arrive[i] <= tau < self.seg_end[i]:
            return i
        return None

    def rate(self, tau: float, name: str) -> float:
        """Consommation par seconde au temps ``tau`` (moyenne du tronçon en cours)."""
        seg = self.route.segments[self.segment(tau)]
        span = seg.duration_s + seg.work_time_s
        return _amount(seg.consumption, name) / span if span > 0 else 0.0

    def remaining(self, tau: float, name: str) -> float:
        """Consommation prévue de ``tau`` jusqu'à la fin de l'itinéraire."""
        total = 0.0
        start = 0.0
        for s, end in zip(self.route.segments, self.seg_end, strict=True):
            amount = _amount(s.consumption, name)
            if tau <= start:
                total += amount
            elif tau < end:
                total += amount * (end - tau) / (end - start)
            start = end
        return total

    def future_coords(self, tau: float) -> list[LonLat]:
        here, _, _ = self.at(tau)
        return [here, *[p for p, t in zip(self.pos, self.times, strict=True) if t > tau]]


def _amount(c: object, name: str) -> float:
    key = {"oxygen": "oxygen_kg", "battery": "battery_wh", "water": "water_l"}[name]
    return float(getattr(c, key))


# -- sortie en cours ----------------------------------------------------------------------


@dataclass
class _Run:
    eva: Eva
    plan: Plan
    site: Site
    track: _Track
    pending: _Track | None = None
    used: dict[str, float] = field(default_factory=lambda: dict.fromkeys(CONSUMABLES, 0.0))
    obstacles: list[Obstacle] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    logbook: list[LogbookEntry] = field(default_factory=list)
    reached: set[tuple[str, int]] = field(default_factory=set)
    routes: int = 0
    speed: float = 0.0
    scenario_id: str | None = None
    task: asyncio.Task[None] | None = None

    @property
    def done(self) -> bool:
        return self.eva.status in (EvaStatus.completed, EvaStatus.aborted)


class A4Service:
    def __init__(
        self,
        a3: Callable[[], A3Service] = get_a3,
        plan_source: PlanSource | None = None,
        tick_s: float = 0.2,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._a3 = a3
        self.plans = PlanRegistry()
        self.plan_source: PlanSource = plan_source or self.plans
        self.tick_s = tick_s
        self.monotonic = monotonic
        self.grids = GridCache()
        self._runs: dict[str, _Run] = {}
        self._lock = threading.RLock()
        self._ids = itertools.count(1)
        self._obs_ids = itertools.count(1)
        self._obst_ids = itertools.count(1)

    @property
    def a3(self) -> A3Service:
        return self._a3()

    # -- lecture ----------------------------------------------------------------
    def get(self, eva_id: str) -> Eva:
        with self._lock:
            return self._run(eva_id).eva.model_copy(deep=True)

    def current_route(self, eva_id: str) -> Route:
        """Itinéraire que suit la sortie (le dernier recalculé, s'il y en a un)."""
        with self._lock:
            run = self._run(eva_id)
            return (run.pending or run.track).route

    def logbook(self, eva_id: str) -> Logbook:
        """Carnet de terrain de la sortie (pour X1)."""
        with self._lock:
            run = self._run(eva_id)
            return Logbook(eva_id=eva_id, site_id=run.eva.site_id, entries=list(run.logbook))

    def observations(self, eva_id: str) -> list[Observation]:
        with self._lock:
            return list(self._run(eva_id).observations)

    def _run(self, eva_id: str) -> _Run:
        run = self._runs.get(eva_id)
        if run is None and eva_id == DEMO_EVA_ID:
            self.start(EvaCreate(plan_id="plan-demo", route_id=DEMO_ROUTE_ID), eva_id=eva_id)
            run = self._runs[eva_id]
        if run is None:
            raise EvaNotFoundError(eva_id)
        return run

    # -- démarrage ---------------------------------------------------------------
    def start(self, body: EvaCreate, eva_id: str | None = None) -> Eva:
        plan = self.plan_source(body.plan_id)
        if plan is None:
            raise PlanNotFoundError(f"Plan inconnu : {body.plan_id}")
        route = next((r for r in plan.routes if r.id == body.route_id), None)
        if route is None:
            raise PlanNotFoundError(f"Variante inconnue dans {plan.id} : {body.route_id}")
        site = load_site(plan.site_id)
        eva_id = eva_id or f"eva-{next(self._ids)}"
        a3 = self.a3
        started = body.start_utc or a3.scenario_utc()
        track = _Track(route, t0=0.0, distance_before=0.0)
        eva = Eva(
            id=eva_id,
            site_id=plan.site_id,
            plan_id=plan.id,
            route_id=route.id,
            crew=body.crew,
            status=EvaStatus.active,
            started_at=started,
            position=track.pos[0],
            consumables=ConsumablesState(oxygen_pct=100.0, battery_pct=100.0, water_pct=100.0),
            next_target_id=next((s.to_target_id for s in route.segments if s.to_target_id), None),
        )
        run = _Run(eva=eva, plan=plan, site=site, track=track)
        with self._lock:
            self._runs[eva_id] = run
            self._update(run, 0.0)
            self._log(run, "start", f"Début de la sortie sur la variante {route.variant.value}")
            self._ingest(run)
            return run.eva.model_copy(deep=True)

    # -- avance du temps ------------------------------------------------------------
    def step(self, eva_id: str, dt: float) -> Eva:
        """Fait avancer la sortie de ``dt`` secondes de sortie."""
        with self._lock:
            run = self._run(eva_id)
            if not run.done:
                self._advance(run, dt)
                self._ingest(run)
            return run.eva.model_copy(deep=True)

    async def simulate(
        self, eva_id: str, speed: float, scenario_id: str | None = None
    ) -> SimulationState:
        with self._lock:
            run = self._run(eva_id)
        if scenario_id is not None:
            await self.a3.start_scenario(scenario_id, speed)
        await self._stop_task(run)
        with self._lock:
            run.speed, run.scenario_id = speed, scenario_id
            if not run.done:
                run.task = asyncio.create_task(self._loop(run))
            return self.simulation_state(eva_id)

    def simulation_state(self, eva_id: str) -> SimulationState:
        with self._lock:
            run = self._run(eva_id)
            running = run.task is not None and not run.task.done() and not run.done
            return SimulationState(
                eva_id=eva_id, running=running, speed=run.speed, scenario_id=run.scenario_id
            )

    async def _stop_task(self, run: _Run) -> None:
        task = run.task
        if task is not None and not task.done() and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _loop(self, run: _Run) -> None:
        last = self.monotonic()
        while True:
            await asyncio.sleep(self.tick_s)
            now = self.monotonic()
            with self._lock:
                if self._runs.get(run.eva.id) is not run or run.done:
                    return
                self._advance(run, (now - last) * run.speed)
                self._ingest(run)
                if run.done:
                    return
            last = now

    def _advance(self, run: _Run, dt: float) -> None:
        eva = run.eva
        if dt <= 0:
            self._update(run, 0.0)
            return
        # Débit de dose réel : celui des conditions (scénario K1 rejoué par A3).
        tau = eva.elapsed_s - run.track.t0
        for name in CONSUMABLES:
            run.used[name] += run.track.rate(tau, name) * dt
        dose_rate = self.a3.current_conditions().dose_rate_usv_h
        if dose_rate is None:
            seg = run.track.route.segments[run.track.segment(tau)]
            span = seg.duration_s + seg.work_time_s
            dose_rate = seg.consumption.dose_usv / span * 3600 if span > 0 else 0.0
        eva.dose_usv = round(eva.dose_usv + dose_rate * dt / 3600.0, 3)
        eva.elapsed_s = round(eva.elapsed_s + dt, 3)
        if run.pending is not None and eva.elapsed_s >= run.pending.t0:
            run.track, run.pending = run.pending, None
        self._update(run, dt)

    def _update(self, run: _Run, dt: float) -> None:
        """Position, arrivées, fin de sortie et budgets à l'instant ``eva.elapsed_s``."""
        eva, track, plan = run.eva, run.track, run.plan
        tau = eva.elapsed_s - track.t0
        before = LonLat(*eva.position)
        pos, dist, speed = track.at(tau)
        eva.position = pos
        eva.distance_done_m = round(track.distance_before + dist, 2)
        eva.speed_mps = round(speed, 3)
        if dt > 0 and before != pos:
            eva.heading_deg = round(bearing_deg(before, pos), 1)
        for i, seg in enumerate(track.route.segments):
            key = (track.route.id, i)
            if seg.to_target_id and track.seg_arrive[i] <= tau and key not in run.reached:
                run.reached.add(key)
                self._log(run, "target", f"Arrivée à la cible {seg.to_target_id}", seg.to_point)
        eva.next_target_id = next(
            (
                s.to_target_id
                for s, arrive in zip(track.route.segments, track.seg_arrive, strict=True)
                if s.to_target_id and arrive > tau
            ),
            None,
        )
        if run.pending is None and tau >= track.end_time and dt > 0:
            eva.status = EvaStatus.completed
            eva.ended_at = self.a3.scenario_utc()
            eva.speed_mps = 0.0
            self._log(run, "end", "Fin de la sortie, retour à l'habitat", pos)

        suit = plan.suit
        caps = {
            "oxygen": suit.oxygen_capacity_kg,
            "battery": suit.battery_capacity_wh,
            "water": suit.water_capacity_l,
        }
        rates = {
            "oxygen": suit.oxygen_rate_kg_h / 3600.0,
            "battery": suit.battery_rate_w / 3600.0,
            "water": suit.water_rate_l_h / 3600.0,
        }
        pct = {k: max(0.0, 100.0 * (1.0 - run.used[k] / caps[k])) for k in CONSUMABLES}
        eva.consumables = ConsumablesState(
            oxygen_pct=round(pct["oxygen"], 2),
            battery_pct=round(pct["battery"], 2),
            water_pct=round(pct["water"], 2),
        )
        future = run.pending or track
        future_tau = eva.elapsed_s - future.t0
        reserve = {
            k: pct[k] - 100.0 * future.remaining(max(future_tau, 0.0), k) / caps[k]
            for k in CONSUMABLES
        }
        eva.reserve_pct = round(min(reserve.values()), 2)
        field_ = self.grids.field(run.site, plan.settings, suit)
        back = return_time_s(field_, pos)
        eva.return_time_s = None if back is None else round(back, 1)
        margin = min(
            (pct[k] - plan.settings.min_reserve_pct) / 100.0 * caps[k] / rates[k]
            for k in CONSUMABLES
            if rates[k] > 0
        )
        eva.time_to_pnr_s = round(margin - (back or 0.0), 1)

    # -- A3 : télémétrie, alertes et retour forcé ------------------------------------
    def _ingest(self, run: _Run) -> None:
        a3 = self.a3
        change = a3.ingest_eva(run.eva.model_copy(deep=True))
        for alert in change.raised:
            self._log(run, "alert", f"{alert.title} : {alert.action}", alert.position, alert.id)
        active = a3.engine.list(run.eva.id)
        run.eva.active_alert_ids = [a.id for a in active]
        if run.eva.status == EvaStatus.active:
            trigger = next((a for a in active if _forces_return(a)), None)
            if trigger is not None:
                self._force_return(run, trigger)

    def _force_return(self, run: _Run, alert: Alert) -> None:
        run.eva.status = EvaStatus.returning
        self._reroute(run, f"Retour forcé : {alert.title}", targets=False)

    # -- recalcul local ---------------------------------------------------------------
    def _reroute(
        self, run: _Run, reason: str, *, targets: bool = True, start: LonLat | None = None
    ) -> Route:
        eva = run.eva
        track = run.pending or run.track
        tau = eva.elapsed_s - track.t0
        t0 = eva.elapsed_s
        origin = LonLat(*(start or eva.position))
        stops = []
        if targets and eva.status == EvaStatus.active:
            working = None if start is not None else track.working(tau)
            if working is not None:
                # Finir le travail en cours, puis repartir de la cible.
                t0 = eva.elapsed_s + (track.seg_end[working] - tau)
                origin = LonLat(*track.route.segments[working].to_point)
            stops = [
                stop_target(s.to_target_id, eva.site_id, LonLat(*s.to_point), s.work_time_s)
                for s, arrive in zip(track.route.segments, track.seg_arrive, strict=True)
                if s.to_target_id and arrive > tau
            ]
        end = LonLat(*run.plan.return_to)
        run.routes += 1
        lp = LocalPlan(
            site=run.site,
            settings=run.plan.settings,
            suit=run.plan.suit,
            conditions=self.a3.current_conditions(),
            variant=track.route.variant,
            obstacles=list(run.obstacles),
        )
        route = compute_route(
            lp, self.grids, origin, stops, end, f"{eva.id}-route-{run.routes}", reason
        )
        new = _Track(route, t0=t0, distance_before=eva.distance_done_m)
        if t0 > eva.elapsed_s:
            run.pending = new
        else:
            run.track, run.pending = new, None
            self._update(run, 0.0)
        self._log(run, "reroute", reason, origin, route.id)
        st = self.a3.stamp(eva.id, self.a3.scenario_utc())
        self.a3.publish(
            eva.id,
            WsRouteUpdated(
                utc=st.utc,
                sol=st.sol,
                lmst=st.lmst,
                payload=RouteUpdatedPayload(reason=reason, route=route),
            ),
        )
        return route

    def report_obstacle(self, eva_id: str, body: ObstacleReport) -> ObstacleResponse:
        t = time.perf_counter()
        with self._lock:
            run = self._run(eva_id)
            ob = Obstacle(
                id=f"obst-{next(self._obst_ids)}",
                position=LonLat(*body.position),
                radius_m=body.radius_m,
                note=body.note,
            )
            run.obstacles.append(ob)
            text = f"Obstacle signalé (rayon {body.radius_m:g} m)"
            self._log(
                run, "obstacle", f"{text} : {body.note}" if body.note else text, ob.position, ob.id
            )
            route = None
            track = run.pending or run.track
            future = track.future_coords(max(run.eva.elapsed_s - track.t0, 0.0))
            if not run.done and touches(run.site, future, ob, run.plan.settings.obstacle_buffer_m):
                route = self._reroute(run, "Obstacle signalé : contournement local")
                self._ingest(run)
            return ObstacleResponse(
                obstacle_id=ob.id,
                route=route,
                compute_time_ms=round((time.perf_counter() - t) * 1000.0, 1),
            )

    def report_position(self, eva_id: str, body: PositionReport) -> Eva:
        with self._lock:
            run = self._run(eva_id)
            eva = run.eva
            if run.done:
                return eva.model_copy(deep=True)
            simulating = run.task is not None and not run.task.done()
            if not simulating and eva.started_at is not None:
                utc = body.utc or self.a3.scenario_utc()
                self._advance(run, (utc - eva.started_at).total_seconds() - eva.elapsed_s)
            here = LonLat(*body.position)
            track = run.pending or run.track
            tau = max(eva.elapsed_s - track.t0, 0.0)
            gap = distance_to_line_m(run.site, track.future_coords(tau), here)
            if gap > OFF_ROUTE_M:
                self._reroute(run, f"Écart au tracé de {gap:.0f} m", start=here)
            else:
                # Sur le tracé : reprendre l'avance au point le plus proche.
                j = min(
                    range(len(track.pos)),
                    key=lambda k: distance_to_line_m(run.site, [track.pos[k]], here),
                )
                if run.pending is None:
                    track.t0 = eva.elapsed_s - track.times[j]
                self._update(run, 0.0)
            eva.position = here
            if body.heading_deg is not None:
                eva.heading_deg = body.heading_deg
            if body.speed_mps is not None:
                eva.speed_mps = body.speed_mps
            self._ingest(run)
            return eva.model_copy(deep=True)

    # -- carnet ------------------------------------------------------------------------
    def add_observation(self, eva_id: str, body: ObservationCreate) -> Observation:
        with self._lock:
            run = self._run(eva_id)
            st = self.a3.stamp(eva_id, body.utc or self.a3.scenario_utc())
            obs = Observation(
                **body.model_dump(exclude={"utc"}),
                id=f"obs-{next(self._obs_ids)}",
                eva_id=eva_id,
                utc=st.utc,
                sol=st.sol,
                lmst=st.lmst,
            )
            run.observations.append(obs)
            self._log(run, "observation", body.note, LonLat(*body.position), obs.id, st.utc)
            return obs

    def _log(
        self,
        run: _Run,
        kind: str,
        text: str,
        position: LonLat | None = None,
        ref_id: str | None = None,
        utc: datetime | None = None,
    ) -> None:
        st = self.a3.stamp(run.eva.id, utc or self.a3.scenario_utc())
        run.logbook.append(
            LogbookEntry.model_validate(
                {
                    "utc": st.utc,
                    "sol": st.sol,
                    "lmst": st.lmst,
                    "kind": kind,
                    "text": text,
                    "position": position,
                    "ref_id": ref_id,
                }
            )
        )

    def reset(self) -> None:
        with self._lock:
            for run in self._runs.values():
                if run.task is not None and not run.task.done():
                    run.task.cancel()
            self._runs.clear()
            self.plans.clear()
            self._ids = itertools.count(1)
            self._obs_ids = itertools.count(1)
            self._obst_ids = itertools.count(1)


def _forces_return(alert: Alert) -> bool:
    return alert.level == AlertLevel.danger and alert.cause in RETURN_CAUSES


@cache
def get_simulator() -> A4Service:
    """Simulateur partagé, branché sur les plans calculés par A2.

    Une sortie démarre sur un plan de ``POST /api/sites/{site_id}/plans`` (dépôt de A2), sinon
    sur un plan enregistré ou sur ``plan-demo`` (``PlanRegistry``). Voir
    ``tasks/change-requests/A4-source-des-plans.md``.
    """
    from marswalk_api.services.mission_planning.deps import get_plan_repository

    sim = A4Service()
    registry = sim.plans
    repo = get_plan_repository()

    def plan_source(plan_id: str) -> Plan | None:
        return repo.get(plan_id) or registry(plan_id)

    sim.plan_source = plan_source
    return sim


__all__ = [
    "DEMO_EVA_ID",
    "A4Service",
    "EvaNotFoundError",
    "PlanNotFoundError",
    "get_simulator",
]
