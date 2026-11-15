"""Tests complets pour le module conditions (K1).

Vérifie les critères d'acceptation :
1. Le mode 'historical' renvoie des valeurs MEDA cohérentes pour un sol donné.
2. Le scénario 'solar-event' produit un pic de dose à l'instant prévu, de façon reproductible.
3. Sans réseau, tout fonctionne et 'live' renvoie la dernière valeur en cache avec sa date.
4. Les prévisions horaires (forecast) sont générées.
"""

from datetime import UTC, datetime, timedelta

from marswalk_conditions import (
    ConditionsProvider,
    LiveProvider,
    get_provider,
    get_scenario_manager,
    list_scenarios,
)
from marswalk_conditions.interfaces import ISpaceWeatherSource
from marswalk_conditions.live import InMemoryCacheStore
from marswalk_core.schemas import SpaceWeather, SpaceWeatherLevel


def test_scenario_catalog() -> None:
    scenarios = list_scenarios()
    assert len(scenarios) >= 1
    ids = {s.id for s in scenarios}
    assert "solar-event" in ids
    solar_event = next(s for s in scenarios if s.id == "solar-event")
    assert solar_event.duration_s == 3600.0
    event_kinds = [e.kind for e in solar_event.events]
    assert "start" in event_kinds
    assert "solar_event" in event_kinds
    assert "end" in event_kinds


def test_historical_provider_returns_meda_values() -> None:
    provider = get_provider("historical")
    assert isinstance(provider, ConditionsProvider)

    # Date correspondant à Jezero
    ref_time = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    cond = provider.current(ref_time)

    assert cond.sol is not None
    assert cond.lmst is not None
    assert cond.temperature_c is not None
    assert -90.0 <= cond.temperature_c <= 0.0
    assert cond.pressure_pa is not None
    assert 700.0 <= cond.pressure_pa <= 1000.0
    assert cond.wind_mps is not None
    assert cond.wind_mps >= 0.0
    assert cond.uv_index is not None
    assert cond.dose_rate_usv_h is not None
    assert cond.dose_rate_usv_h > 0.0
    assert cond.dust_tau is not None

    # Test du forecast
    forecasts = provider.forecast(ref_time, hours=6)
    assert len(forecasts) == 6
    for f in forecasts:
        assert f.temperature_c is not None
        assert f.pressure_pa is not None


def test_solar_event_scenario_reproducible_peak() -> None:
    mgr = get_scenario_manager()
    start_time = datetime(2026, 11, 14, 10, 0, 0, tzinfo=UTC)
    mgr.start("solar-event", speed=1.0, started_at=start_time)

    provider = get_provider("scenario", "solar-event")

    # t = 0s (début : calme)
    c0 = provider.current(start_time)
    assert c0.dose_rate_usv_h is not None
    assert c0.dose_rate_usv_h < 50.0
    assert c0.space_weather.level == SpaceWeatherLevel.quiet

    # t = 600s (calme)
    c600 = provider.current(start_time + timedelta(seconds=600))
    assert c600.dose_rate_usv_h is not None
    assert c600.dose_rate_usv_h < 50.0

    # t = 1800s (au cœur du pic entre 1200s et 2400s)
    c1800 = provider.current(start_time + timedelta(seconds=1800))
    # Le pic doit dépasser 1000 µSv/h de façon reproductible
    assert c1800.dose_rate_usv_h is not None
    assert c1800.dose_rate_usv_h > 1000.0
    assert c1800.space_weather.level == SpaceWeatherLevel.storm
    assert "SPE" in str(c1800.space_weather.event) or "Dose" in str(c1800.space_weather.event)

    # t = 3000s (décroissance)
    c3000 = provider.current(start_time + timedelta(seconds=3000))
    assert c3000.dose_rate_usv_h is not None
    assert c3000.dose_rate_usv_h < c1800.dose_rate_usv_h

    # t = 4000s (après la fin du scénario : retour au nominal)
    c4000 = provider.current(start_time + timedelta(seconds=4000))
    assert c4000.dose_rate_usv_h is not None
    assert c4000.dose_rate_usv_h < 50.0
    assert c4000.space_weather.level == SpaceWeatherLevel.quiet

    mgr.stop("solar-event")


def test_live_provider_fallback_to_cache_without_network() -> None:
    # Client simulant l'absence totale de réseau
    class FailingNetworkClient(ISpaceWeatherSource):
        def fetch_current(self) -> SpaceWeather:
            raise ConnectionError("Network unreachable (offline)")

    cached_time = datetime(2026, 11, 14, 8, 30, 0, tzinfo=UTC)
    cached_sw = SpaceWeather(
        level=SpaceWeatherLevel.watch,
        event="Cached Coronal Mass Ejection",
        source="DONKI Offline Cache",
    )
    cache_store = InMemoryCacheStore(
        initial_weather=cached_sw,
        initial_cached_at=cached_time,
    )

    live_prov = LiveProvider(client=FailingNetworkClient(), cache_store=cache_store)
    now = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)

    # Sans réseau, live doit fonctionner et renvoyer la valeur en cache avec sa date
    cond = live_prov.current(now)
    assert cond.space_weather.level == SpaceWeatherLevel.watch
    assert cond.space_weather.event == "Cached Coronal Mass Ejection"
    assert cond.cached_at == cached_time
    assert cond.source is not None
    assert "hors ligne" in cond.source or "cache" in cond.source


def test_live_provider_with_active_network() -> None:
    # Client simulant une réponse réseau directe
    class SuccessNetworkClient(ISpaceWeatherSource):
        def fetch_current(self) -> SpaceWeather:
            return SpaceWeather(
                level=SpaceWeatherLevel.storm,
                event="LIVE-SEP-2026",
                source="NASA DONKI Live API",
            )

    cache_store = InMemoryCacheStore()
    live_prov = LiveProvider(client=SuccessNetworkClient(), cache_store=cache_store)
    now = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)

    cond = live_prov.current(now)
    assert cond.space_weather.level == SpaceWeatherLevel.storm
    assert cond.space_weather.event == "LIVE-SEP-2026"
    assert cond.dose_rate_usv_h is not None
    assert cond.dose_rate_usv_h > 1000.0  # Alerte dose ajustée en cas de tempête
    # Le cache a été mis à jour
    cached_result = cache_store.get()
    assert cached_result is not None
    cached_val, cached_date = cached_result
    assert cached_val.event == "LIVE-SEP-2026"
    assert cached_date == now
