"""Outils de test de A4 : services A3 et A4 neufs, horloge martienne fixée au matin."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from marswalk_api.services.a3 import A3Service
from marswalk_api.services.a3 import get_service as get_a3
from marswalk_api.services.a4 import A4Service, get_simulator
from marswalk_core.schemas import Conditions, SpaceWeather

MORNING_UTC = datetime(2026, 11, 14, 14, 55, tzinfo=UTC)
"""Sol 14, 08:58 LMST sur le site fictif : la sortie se fait de jour."""
SPIKE_AT_S = 1200.0
"""Pic de dose du scénario solar-event, en secondes de scénario (contrat K1)."""


class SolarEventProvider:
    """Imite le contrat de K1 : calme, puis pic de dose à ``SPIKE_AT_S`` du scénario."""

    def __init__(self, start: datetime | None) -> None:
        self.start = start

    def current(self, utc: datetime) -> Conditions:
        spike = self.start is not None and utc >= self.start + timedelta(seconds=SPIKE_AT_S)
        return Conditions(
            utc=utc,
            mode="scenario" if self.start is not None else "historical",
            dust_tau=0.6,
            dose_rate_usv_h=250.0 if spike else 10.0,
            space_weather=SpaceWeather(),
            source="fournisseur de test (contrat K1)",
        )

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        return [self.current(utc + timedelta(hours=h)) for h in range(hours)]


@pytest.fixture
def a3() -> Iterator[A3Service]:
    svc = get_a3()
    svc.reset()

    def factory(mode: str, scenario_id: str | None = None) -> SolarEventProvider:
        return SolarEventProvider(svc._started_utc if mode == "scenario" else None)

    original = svc.provider_factory, svc.now
    svc.provider_factory = factory
    svc.now = lambda: MORNING_UTC
    yield svc
    svc.provider_factory, svc.now = original
    svc.reset()


@pytest.fixture
def sim(a3: A3Service) -> Iterator[A4Service]:
    svc = get_simulator()
    svc.reset()
    tick = svc.tick_s
    svc.tick_s = 0.02
    yield svc
    svc.tick_s = tick
    svc.reset()
