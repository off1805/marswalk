"""Moteur de rejeu de scénarios martiens (K1).

Fournit :
- Le scénario de référence "solar-event" (éruption solaire majeure / pic de dose RAD).
- Le moteur de scénarios avec prise en charge de l'accélération temporelle.
- ScenarioProvider implémentant ConditionsProvider.
"""

from __future__ import annotations

import math
import threading
from datetime import UTC, datetime, timedelta

from marswalk_conditions.climatology import MedaClimatologyEngine
from marswalk_conditions.interfaces import ConditionsProvider
from marswalk_core.schemas import (
    Conditions,
    Scenario,
    ScenarioEvent,
    ScenarioState,
    SpaceWeather,
    SpaceWeatherLevel,
)

# Scénario de référence fondé sur l'événement solaire majeur de mai 2024
SOLAR_EVENT_SCENARIO = Scenario(
    id="solar-event",
    title="Éruption solaire pendant la sortie",
    description=(
        "Rejeu d'un événement à particules solaires vu au sol par RAD "
        "(Curiosity, événement de mai 2024 ; transposé au cratère Jezero). "
        "Comporte un pic de dose extrême déclenchant l'alerte danger."
    ),
    duration_s=3600.0,
    events=[
        ScenarioEvent(t_s=0.0, kind="start", description="Conditions calmes"),
        ScenarioEvent(t_s=1200.0, kind="solar_event", description="Pic de dose"),
        ScenarioEvent(t_s=2400.0, kind="end", description="Retour au calme"),
    ],
)

SCENARIOS_CATALOG: dict[str, Scenario] = {
    SOLAR_EVENT_SCENARIO.id: SOLAR_EVENT_SCENARIO,
}


class ScenarioManager:
    """Gestionnaire d'état d'exécution des scénarios (thread-safe singleton)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_state = ScenarioState(
            scenario_id=None,
            running=False,
            started_at=None,
            elapsed_s=0.0,
            speed=1.0,
        )

    def start(
        self, scenario_id: str, speed: float = 1.0, started_at: datetime | None = None
    ) -> ScenarioState:
        with self._lock:
            if scenario_id not in SCENARIOS_CATALOG:
                raise ValueError(f"Scénario inconnu : {scenario_id}")
            now = started_at or datetime.now(UTC)
            self._active_state = ScenarioState(
                scenario_id=scenario_id,
                running=True,
                started_at=now,
                elapsed_s=0.0,
                speed=max(0.1, speed),
            )
            return self._active_state

    def stop(self, scenario_id: str | None = None) -> ScenarioState:
        with self._lock:
            self._active_state = self._active_state.model_copy(update={"running": False})
            return self._active_state

    def get_state(self) -> ScenarioState:
        with self._lock:
            return self._active_state

    def get_elapsed_s(self, utc: datetime) -> float:
        with self._lock:
            if not self._active_state.running or self._active_state.started_at is None:
                return self._active_state.elapsed_s
            delta = (utc - self._active_state.started_at).total_seconds()
            return max(0.0, delta * self._active_state.speed)


_scenario_manager = ScenarioManager()


def get_scenario_manager() -> ScenarioManager:
    return _scenario_manager


class ScenarioProvider(ConditionsProvider):
    """Fournisseur de conditions asservi à la chronologie d'un scénario."""

    def __init__(
        self,
        scenario_id: str = "solar-event",
        manager: ScenarioManager | None = None,
        climatology: MedaClimatologyEngine | None = None,
    ) -> None:
        self.scenario_id = scenario_id
        self._manager = manager or get_scenario_manager()
        self._climatology = climatology or MedaClimatologyEngine()

    def _compute_solar_event(self, elapsed_s: float) -> tuple[float, SpaceWeather]:
        """Calcule le profil de dose et météo spatiale pour 'solar-event'."""
        # Baseline calme
        if elapsed_s < 1200.0:
            return 10.0, SpaceWeather(level=SpaceWeatherLevel.quiet)

        # Montée brutale et pic de l'événement solaire (1200s à 2400s)
        if 1200.0 <= elapsed_s <= 2400.0:
            # Pic centré à 1500s atteignant ~1250 µSv/h (alerte danger critique)
            progress = (elapsed_s - 1200.0) / 1200.0
            peak_factor = math.sin(progress * math.pi) ** 2
            dose_rate = 10.0 + 1240.0 * peak_factor
            sw = SpaceWeather(
                level=SpaceWeatherLevel.storm,
                event="Événement à particules solaires (SPE) - Alerte Dose Extrême",
                source="RAD Transposé / Modèle Scénario",
            )
            return dose_rate, sw

        # Décroissance progressive (2400s à 3600s)
        if 2400.0 < elapsed_s <= 3600.0:
            progress = (elapsed_s - 2400.0) / 1200.0
            decay = math.exp(-2.5 * progress)
            dose_rate = 10.0 + 40.0 * decay
            sw = SpaceWeather(
                level=SpaceWeatherLevel.watch,
                event="Phase de décroissance SPE",
                source="RAD Transposé / Modèle Scénario",
            )
            return dose_rate, sw

        # Au-delà de la durée du scénario : retour au calme
        return 10.0, SpaceWeather(level=SpaceWeatherLevel.quiet)

    def current(self, utc: datetime) -> Conditions:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)

        elapsed = self._manager.get_elapsed_s(utc)

        if self.scenario_id == "solar-event":
            dose_rate, space_weather = self._compute_solar_event(elapsed)
            source_note = f"Scénario solar-event (t={round(elapsed)}s)"
        else:
            dose_rate, space_weather = 10.0, SpaceWeather()
            source_note = f"Scénario {self.scenario_id}"

        return self._climatology.compute_conditions(
            utc=utc,
            mode="scenario",
            dose_rate_override=dose_rate,
            space_weather_override=space_weather,
            source_note=source_note,
        )

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)

        forecasts: list[Conditions] = []
        for h in range(hours):
            t = utc + timedelta(hours=h)
            forecasts.append(self.current(t))
        return forecasts


def list_scenarios() -> list[Scenario]:
    """Retourne la liste des scénarios disponibles."""
    return list(SCENARIOS_CATALOG.values())
