"""Conditions martiennes et scénarios (K1).

Interface gelée (taches-agents.md section 7) :
    class ConditionsProvider(Protocol):
        def current(self, utc: datetime) -> Conditions: ...
        def forecast(self, utc: datetime, hours: int) -> list[Conditions]: ...

    get_provider(mode, scenario_id) -> ConditionsProvider
    list_scenarios() -> list[Scenario]
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from marswalk_conditions.climatology import MedaClimatologyEngine
from marswalk_conditions.historical import HistoricalProvider, MockMedaRadSource, PdsMedaRadSource
from marswalk_conditions.interfaces import (
    ConditionsProvider,
    ICacheStore,
    IMedaRadSource,
    ISpaceWeatherSource,
)
from marswalk_conditions.live import DonkiClient, InMemoryCacheStore, LiveProvider
from marswalk_conditions.scenario import (
    SOLAR_EVENT_SCENARIO,
    ScenarioManager,
    ScenarioProvider,
    get_scenario_manager,
    list_scenarios,
)
from marswalk_core.schemas import Conditions, SpaceWeather

Mode = Literal["historical", "scenario", "live", "constant"]


class _ConstantProvider:
    """Fournisseur constant de secours (conforme T00)."""

    def __init__(self, mode: Mode = "constant") -> None:
        self.mode = mode

    def current(self, utc: datetime) -> Conditions:
        return Conditions(
            utc=utc,
            mode="constant",
            temperature_c=-20.0,
            pressure_pa=850.0,
            wind_mps=5.0,
            dust_tau=0.6,
            uv_index=5.0,
            dose_rate_usv_h=10.0,
            space_weather=SpaceWeather(),
            source="Bouchon constant de secours",
        )

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        return [self.current(utc + timedelta(hours=h)) for h in range(hours)]


def get_provider(
    mode: Mode,
    scenario_id: str | None = None,
) -> ConditionsProvider:
    """Retourne une instance du fournisseur selon le mode demandé (Factory Pattern)."""
    if mode == "historical":
        return HistoricalProvider()
    elif mode == "scenario":
        scen_id = scenario_id or "solar-event"
        return ScenarioProvider(scenario_id=scen_id)
    elif mode == "live":
        return LiveProvider()
    elif mode == "constant":
        return _ConstantProvider("constant")
    else:
        return _ConstantProvider("constant")


__all__ = [
    "ConditionsProvider",
    "DonkiClient",
    "HistoricalProvider",
    "ICacheStore",
    "IMedaRadSource",
    "ISpaceWeatherSource",
    "InMemoryCacheStore",
    "LiveProvider",
    "MedaClimatologyEngine",
    "MockMedaRadSource",
    "PdsMedaRadSource",
    "SOLAR_EVENT_SCENARIO",
    "ScenarioProvider",
    "get_provider",
    "get_scenario_manager",
    "list_scenarios",
]
