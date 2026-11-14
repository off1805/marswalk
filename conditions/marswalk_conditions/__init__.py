"""Conditions martiennes et scénarios (K1). BOUCHON de T00 : conditions constantes.

Interface gelée (``taches-agents.md`` section 7) ::

    class ConditionsProvider(Protocol):
        def current(self, utc: datetime) -> Conditions: ...
        def forecast(self, utc: datetime, hours: int) -> list[Conditions]: ...

    get_provider(mode, scenario_id) -> ConditionsProvider

T00 ajoute ``list_scenarios()`` pour ``GET /api/scenarios``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Protocol

from marswalk_core.schemas import Conditions, Scenario, ScenarioEvent, SpaceWeather

Mode = Literal["historical", "scenario", "live"]


class ConditionsProvider(Protocol):
    def current(self, utc: datetime) -> Conditions: ...

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]: ...


class _ConstantProvider:
    """Bouchon : mêmes valeurs à tout instant, plausibles pour Jezero de jour."""

    def __init__(self, mode: Mode, scenario_id: str | None) -> None:
        self.mode = mode
        self.scenario_id = scenario_id

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
            source="bouchon T00 (valeurs constantes)",
        )

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        return [self.current(utc + timedelta(hours=h)) for h in range(hours)]


def get_provider(mode: Mode, scenario_id: str | None = None) -> ConditionsProvider:
    return _ConstantProvider(mode, scenario_id)


def list_scenarios() -> list[Scenario]:
    return [
        Scenario(
            id="solar-event",
            title="Éruption solaire pendant la sortie",
            description=(
                "Rejeu d'un événement à particules solaires vu au sol par RAD "
                "(Curiosity, événement de mai 2024 ; date et dose à vérifier dans le PDS "
                "par K1). Perseverance n'emporte pas de RAD : la dose est transposée à Jezero."
            ),
            duration_s=3600.0,
            events=[
                ScenarioEvent(t_s=0.0, kind="start", description="Conditions calmes"),
                ScenarioEvent(t_s=1200.0, kind="solar_event", description="Pic de dose"),
                ScenarioEvent(t_s=2400.0, kind="end", description="Retour au calme"),
            ],
        )
    ]
