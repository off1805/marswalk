from datetime import UTC, datetime

from marswalk_conditions import get_provider, list_scenarios


def test_constant_provider() -> None:
    now = datetime(2026, 11, 14, tzinfo=UTC)
    provider = get_provider("scenario", "solar-event")
    assert provider.current(now).dose_rate_usv_h is not None
    assert len(provider.forecast(now, 6)) == 6
    assert "solar-event" in {s.id for s in list_scenarios()}
