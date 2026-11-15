"""Isole les tests K1 des données locales : pas de jeu importé, cache DONKI temporaire."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from marswalk_conditions import get_scenario_manager


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MARSWALK_CONDITIONS_FILE", str(tmp_path / "absent.json"))
    monkeypatch.setenv("MARSWALK_DONKI_CACHE", str(tmp_path / "donki.json"))
    get_scenario_manager().stop()
    yield
    get_scenario_manager().stop()
