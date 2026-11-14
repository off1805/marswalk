"""Services A3 et A4 neufs, horloge martienne fixée au matin (comme les tests de A4)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from marswalk_api.services.a3 import A3Service
from marswalk_api.services.a3 import get_service as get_a3
from marswalk_api.services.a4 import A4Service, get_simulator

MORNING_UTC = datetime(2026, 11, 14, 14, 55, tzinfo=UTC)
"""Sol 14, 08:58 LMST sur le site fictif."""


@pytest.fixture
def a3() -> Iterator[A3Service]:
    svc = get_a3()
    svc.reset()
    now = svc.now
    svc.now = lambda: MORNING_UTC
    yield svc
    svc.now = now
    svc.reset()


@pytest.fixture
def sim(a3: A3Service) -> Iterator[A4Service]:
    svc = get_simulator()
    svc.reset()
    yield svc
    svc.reset()
