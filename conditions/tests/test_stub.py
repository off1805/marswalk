from datetime import UTC, datetime

from marswalk_conditions import LiveProvider, get_provider, list_scenarios
from marswalk_core.schemas import SpaceWeather


class _Offline:
    def fetch_current(self) -> SpaceWeather:
        raise ConnectionError("hors ligne")


def test_constant_provider() -> None:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    provider = get_provider("scenario", "solar-event")
    assert provider.current(now).dose_rate_usv_h is not None
    assert len(provider.forecast(now, 6)) == 6
    assert "solar-event" in {s.id for s in list_scenarios()}


def test_historical_mode() -> None:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    provider = get_provider("historical")
    assert provider.current(now).temperature_c is not None


def test_live_mode() -> None:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    assert isinstance(get_provider("live"), LiveProvider)
    cond = LiveProvider(client=_Offline()).current(now)
    assert cond.space_weather is not None
