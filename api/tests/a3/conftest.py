"""Outils de test de A3 : service neuf et fournisseur de conditions façon K1."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest

from marswalk_api.services.a3 import A3Service, get_service
from marswalk_core.schemas import Conditions, SpaceWeather

SPIKE_AT_S = 1200.0
"""Pic de dose du scénario solar-event (événement « solar_event » de K1)."""


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
def service() -> Iterator[A3Service]:
    svc = get_service()
    svc.reset()

    def factory(mode: str, scenario_id: str | None = None) -> SolarEventProvider:
        return SolarEventProvider(svc._started_utc if mode == "scenario" else None)

    original = svc.provider_factory
    svc.provider_factory = factory
    yield svc
    svc.provider_factory = original
    svc.reset()
