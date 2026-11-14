"""Service d'alertes et de temps réel (A3) : relie conditions, télémétrie, alertes et WebSocket.

Interface utilisée par A4 (simulateur) :

- ``get_service().ingest_eva(eva)`` après chaque pas de la sortie : évalue la télémétrie et
  publie ``telemetry``, ``budget``, ``alert`` et ``alert_cleared`` ;
- ``get_service().publish(eva_id, message)`` pour un autre message (``route_updated``).

Un scénario de conditions (K1) se rejoue en accéléré : ``start_scenario`` lance une tâche
qui, toutes les ``tick_s`` secondes réelles, lit les conditions à l'instant simulé,
évalue les règles et publie les changements.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import cache
from typing import Literal

import marswalk_conditions
from marswalk_api.deps import get_settings
from marswalk_core.config import load_safety_settings
from marswalk_core.schemas import (
    Alert,
    AlertClearedPayload,
    BudgetPayload,
    Conditions,
    Eva,
    SafetySettings,
    Scenario,
    ScenarioState,
    TelemetryPayload,
    WsAlert,
    WsAlertCleared,
    WsBudget,
    WsConditions,
    WsTelemetry,
)
from marswalk_core.site_package import Site, load_site

from .clock import Stamp, utc_now
from .engine import AlertEngine, Change
from .hub import Hub
from .rules import EvaReading, condition_findings, eva_findings

ProviderFactory = Callable[..., marswalk_conditions.ConditionsProvider]


class ScenarioNotFoundError(LookupError):
    pass


class A3Service:
    def __init__(
        self,
        provider_factory: ProviderFactory = marswalk_conditions.get_provider,
        tick_s: float = 0.2,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.provider_factory = provider_factory
        self.tick_s = tick_s
        self.monotonic = monotonic
        self.now = now
        self.engine = AlertEngine()
        self.hub = Hub()
        self.site_id = get_settings().default_site
        self.safety: SafetySettings = load_safety_settings()
        self._lock = threading.RLock()
        self._eva_sites: dict[str, str] = {}
        self._scenario: Scenario | None = None
        self._speed = 1.0
        self._started_utc: datetime | None = None
        self._started_mono = 0.0
        self._task: asyncio.Task[None] | None = None
        self._last_conditions: Conditions | None = None

    # -- site et horloge ---------------------------------------------------------
    def site(self, eva_id: str | None = None) -> Site:
        return load_site(self._eva_sites.get(eva_id or "", self.site_id))

    def stamp(self, eva_id: str | None = None, utc: datetime | None = None) -> Stamp:
        return Stamp.of(self.site(eva_id), utc or self.now())

    # -- scénarios ----------------------------------------------------------------
    def scenarios(self) -> list[Scenario]:
        return marswalk_conditions.list_scenarios()

    def scenario_state(self) -> ScenarioState:
        with self._lock:
            if self._scenario is None:
                return ScenarioState(scenario_id=None, running=False)
            elapsed = self._elapsed_s()
            return ScenarioState(
                scenario_id=self._scenario.id,
                running=self._running(),
                started_at=self._started_utc,
                elapsed_s=round(elapsed, 3),
                speed=self._speed,
            )

    def _running(self) -> bool:
        return self._scenario is not None and self._task is not None and not self._task.done()

    def _elapsed_s(self) -> float:
        return (self.monotonic() - self._started_mono) * self._speed

    def scenario_utc(self) -> datetime:
        """Instant simulé du scénario en cours, ou maintenant."""
        with self._lock:
            if not self._running() or self._started_utc is None:
                return self.now()
            return self._started_utc + timedelta(seconds=self._elapsed_s())

    async def start_scenario(self, scenario_id: str, speed: float = 1.0) -> ScenarioState:
        scenario = next((s for s in self.scenarios() if s.id == scenario_id), None)
        if scenario is None:
            raise ScenarioNotFoundError(scenario_id)
        await self.stop_scenario()
        with self._lock:
            self._scenario = scenario
            self._speed = max(speed, 0.01)
            self._started_utc = self.now()
            self._started_mono = self.monotonic()
            self._task = asyncio.create_task(self._run(scenario))
        self.tick()
        return self.scenario_state()

    async def stop_scenario(self) -> ScenarioState:
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        state = self.scenario_state()
        return state.model_copy(update={"running": False})

    async def _run(self, scenario: Scenario) -> None:
        while self._elapsed_s() < scenario.duration_s:
            await asyncio.sleep(self.tick_s)
            self.tick()

    def provider(self) -> marswalk_conditions.ConditionsProvider:
        if self._running():
            assert self._scenario is not None
            return self.provider_factory("scenario", self._scenario.id)
        return self.provider_factory("historical", None)

    # -- conditions ---------------------------------------------------------------
    def current_conditions(self) -> Conditions:
        utc = self.scenario_utc()
        c = self.provider().current(utc)
        return self._stamped(c)

    def forecast(self, hours: int) -> list[Conditions]:
        utc = self.scenario_utc()
        return [self._stamped(c) for c in self.provider().forecast(utc, hours)]

    def _stamped(self, c: Conditions) -> Conditions:
        if c.sol is not None and c.lmst is not None:
            return c
        st = self.stamp(utc=c.utc)
        return c.model_copy(update={"sol": st.sol, "lmst": st.lmst})

    def tick(self) -> Change:
        """Lit les conditions, évalue les règles du site et publie ce qui change."""
        conditions = self.current_conditions()
        st = self.stamp(utc=conditions.utc)
        change = self.engine.process(
            None, condition_findings(conditions, self.safety), self.monotonic(), st
        )
        if conditions != self._last_conditions:
            self._last_conditions = conditions
            self.hub.publish(
                None, WsConditions(utc=st.utc, sol=st.sol, lmst=st.lmst, payload=conditions)
            )
        self._publish_change(change, st)
        return change

    # -- sorties ------------------------------------------------------------------
    def ingest_eva(self, eva: Eva) -> Change:
        """Évalue la télémétrie d'une sortie (appelé par A4) et publie les messages."""
        self._eva_sites[eva.id] = eva.site_id
        site = self.site(eva.id)
        st = self.stamp(eva.id, self.scenario_utc())
        lon, lat = eva.position
        reading = EvaReading(
            dose_usv=eva.dose_usv,
            oxygen_pct=eva.consumables.oxygen_pct,
            battery_pct=eva.consumables.battery_pct,
            reserve_pct=eva.reserve_pct,
            time_to_pnr_s=eva.time_to_pnr_s,
            slope_deg=site.sample("slope", lon, lat),
            radio=site.sample("radio_coverage", lon, lat),
            illumination=site.sample("illumination", lon, lat),
            daylight_left_s=st.daylight_left_s(),
        )
        change = self.engine.process(
            eva.id, eva_findings(reading, self.safety), self.monotonic(), st, eva.position
        )
        self.hub.publish(
            eva.id,
            WsTelemetry(
                utc=st.utc,
                sol=st.sol,
                lmst=st.lmst,
                payload=TelemetryPayload(
                    position=eva.position,
                    heading_deg=eva.heading_deg,
                    speed_mps=eva.speed_mps,
                    consumables=eva.consumables,
                    dose_usv=eva.dose_usv,
                    distance_done_m=eva.distance_done_m,
                    elapsed_s=eva.elapsed_s,
                ),
            ),
        )
        if eva.reserve_pct is not None:
            self.hub.publish(
                eva.id,
                WsBudget(
                    utc=st.utc,
                    sol=st.sol,
                    lmst=st.lmst,
                    payload=BudgetPayload(
                        reserve_pct=eva.reserve_pct,
                        time_to_pnr_s=eva.time_to_pnr_s,
                        return_time_s=eva.return_time_s,
                        limiting_consumable=_limiting(eva),
                    ),
                ),
            )
        self._publish_change(change, st)
        return change

    def publish(self, eva_id: str | None, message: object) -> None:
        self.hub.publish(eva_id, message)

    # -- alertes ------------------------------------------------------------------
    def acknowledge(self, alert_id: str) -> Alert | None:
        alert = self.engine.get(alert_id)
        if alert is None:
            return None
        acked = self.engine.acknowledge(alert_id, self.stamp(alert.eva_id))
        assert acked is not None
        st = self.stamp(alert.eva_id)
        self.hub.publish(acked.eva_id, WsAlert(utc=st.utc, sol=st.sol, lmst=st.lmst, payload=acked))
        return acked

    def _publish_change(self, change: Change, st: Stamp) -> None:
        for alert, reason in change.cleared:
            self.hub.publish(
                alert.eva_id,
                WsAlertCleared(
                    utc=st.utc,
                    sol=st.sol,
                    lmst=st.lmst,
                    payload=AlertClearedPayload(alert_id=alert.id, reason=reason),
                ),
            )
        for alert in change.raised:
            self.hub.publish(
                alert.eva_id, WsAlert(utc=st.utc, sol=st.sol, lmst=st.lmst, payload=alert)
            )

    def reset(self) -> None:
        self.engine.reset()
        self._last_conditions = None
        self._eva_sites.clear()
        with self._lock:
            self._scenario = None
            self._task = None


def _limiting(eva: Eva) -> Literal["oxygen", "battery", "water"]:
    c = eva.consumables
    levels: dict[Literal["oxygen", "battery", "water"], float] = {
        "oxygen": c.oxygen_pct,
        "battery": c.battery_pct,
        "water": c.water_pct,
    }
    return min(levels, key=lambda k: levels[k])


@cache
def get_service() -> A3Service:
    return A3Service()
