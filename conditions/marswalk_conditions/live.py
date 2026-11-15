"""Client DONKI et fournisseur de conditions en mode direct (live).

Architecture SOLID :
- ISpaceWeatherSource et ICacheStore assurent le découplage et la testabilité (DIP).
- DonkiCache assure la résilience hors-ligne (ENF-01) : sans réseau, la dernière
  valeur en cache est retournée avec sa date `cached_at`.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime, timedelta

from marswalk_conditions.climatology import MedaClimatologyEngine
from marswalk_conditions.interfaces import (
    ConditionsProvider,
    ICacheStore,
    ISpaceWeatherSource,
)
from marswalk_core.schemas import (
    Conditions,
    SpaceWeather,
    SpaceWeatherLevel,
)


class InMemoryCacheStore(ICacheStore):
    """Stockage de cache en mémoire (avec possibilité de sauvegarde disque)."""

    def __init__(
        self,
        initial_weather: SpaceWeather | None = None,
        initial_cached_at: datetime | None = None,
    ) -> None:
        self._weather = initial_weather or SpaceWeather(
            level=SpaceWeatherLevel.quiet,
            event="Flux solaire nominal (base de secours)",
            source="DONKI Cache local",
        )
        self._cached_at = initial_cached_at or datetime(2026, 11, 14, 8, 0, 0, tzinfo=UTC)

    def get(self) -> tuple[SpaceWeather, datetime] | None:
        return self._weather, self._cached_at

    def set(self, data: SpaceWeather, cached_at: datetime) -> None:
        self._weather = data
        self._cached_at = cached_at


class DonkiClient(ISpaceWeatherSource):
    """Client interrogeant l'API DONKI de la NASA avec gestion d'erreurs et timeout court."""

    def __init__(self, api_url: str = "https://api.nasa.gov/DONKI/notifications") -> None:
        self.api_url = api_url

    def fetch_current(self) -> SpaceWeather:
        """Tente de requêter l'API DONKI. Sans réseau, lève une exception."""
        req = urllib.request.Request(
            f"{self.api_url}?type=all",
            headers={"User-Agent": "Marswalk-Conditions/0.1.0"},
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0:
                latest = data[0]
                message_type = latest.get("messageType", "")
                level = SpaceWeatherLevel.quiet
                if "SEP" in message_type or "CME" in message_type:
                    level = SpaceWeatherLevel.storm
                elif "FLR" in message_type:
                    level = SpaceWeatherLevel.warning

                return SpaceWeather(
                    level=level,
                    event=latest.get("messageID", "Notification DONKI"),
                    source="NASA DONKI Live",
                )
            return SpaceWeather(level=SpaceWeatherLevel.quiet, source="NASA DONKI Live")


class LiveProvider(ConditionsProvider):
    """Fournisseur de conditions en mode 'live' avec secours automatique sur cache."""

    def __init__(
        self,
        client: ISpaceWeatherSource | None = None,
        cache_store: ICacheStore | None = None,
        climatology: MedaClimatologyEngine | None = None,
    ) -> None:
        self._client = client or DonkiClient()
        self._cache = cache_store or InMemoryCacheStore()
        self._climatology = climatology or MedaClimatologyEngine()

    def current(self, utc: datetime) -> Conditions:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)

        space_weather: SpaceWeather
        cached_at: datetime | None = None
        source_note: str

        try:
            # Tentative de récupération en direct
            space_weather = self._client.fetch_current()
            cached_at = utc
            self._cache.set(space_weather, cached_at)
            source_note = "Données DONKI en direct"
        except Exception:
            # Repli sur le cache local en l'absence de réseau (ENF-01)
            cached_data = self._cache.get()
            if cached_data:
                space_weather, cached_at = cached_data
                source_note = "DONKI (mode hors ligne - dernière valeur en cache)"
            else:
                space_weather = SpaceWeather(level=SpaceWeatherLevel.quiet)
                cached_at = utc
                source_note = "DONKI (valeur de secours par défaut)"

        # Ajustement du débit de dose selon le niveau d'alerte météo spatiale
        dose_rate = 10.0
        if space_weather.level == SpaceWeatherLevel.storm:
            dose_rate = 1200.0
        elif space_weather.level == SpaceWeatherLevel.warning:
            dose_rate = 150.0
        elif space_weather.level == SpaceWeatherLevel.watch:
            dose_rate = 30.0

        return self._climatology.compute_conditions(
            utc=utc,
            mode="live",
            dose_rate_override=dose_rate,
            space_weather_override=space_weather,
            source_note=source_note,
            cached_at=cached_at,
        )

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)

        forecasts: list[Conditions] = []
        for h in range(hours):
            t = utc + timedelta(hours=h)
            forecasts.append(self.current(t))
        return forecasts
