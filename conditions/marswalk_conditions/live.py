"""Client DONKI et fournisseur de conditions en mode direct (``live``).

- La météo spatiale vient de DONKI (NASA), seulement dans ce mode. La clé est lue dans
  ``NASA_API_KEY`` (``DEMO_KEY`` par défaut, limitée à quelques requêtes par heure).
- Chaque réponse est écrite dans un cache sur disque (``data/cache/donki.json`` ou
  ``MARSWALK_DONKI_CACHE``). Sans réseau, la dernière valeur en cache est renvoyée avec sa
  date dans ``cached_at`` (ENF-01), y compris après un redémarrage.
- Le reste des conditions (MEDA, fond de dose) vient de la climatologie, comme en historique.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from marswalk_conditions.climatology import MedaClimatologyEngine
from marswalk_conditions.interfaces import (
    ConditionsProvider,
    ICacheStore,
    ISpaceWeatherSource,
)
from marswalk_core.paths import repo_root
from marswalk_core.schemas import (
    Conditions,
    SpaceWeather,
    SpaceWeatherLevel,
)

DONKI_URL = "https://api.nasa.gov/DONKI/notifications"

# Multiplicateur du fond de dose selon le niveau DONKI (ordre de grandeur, hypothèse :
# DONKI décrit l'espace proche de la Terre et du Soleil, pas le sol martien).
LEVEL_DOSE_FACTOR = {
    SpaceWeatherLevel.quiet: 1.0,
    SpaceWeatherLevel.watch: 2.0,
    SpaceWeatherLevel.warning: 8.0,
    SpaceWeatherLevel.storm: 70.0,
}


def default_cache_path() -> Path:
    env = os.environ.get("MARSWALK_DONKI_CACHE")
    if env:
        return Path(env)
    return repo_root() / "data" / "cache" / "donki.json"


class InMemoryCacheStore(ICacheStore):
    """Cache en mémoire, vide par défaut (tests)."""

    def __init__(
        self,
        initial_weather: SpaceWeather | None = None,
        initial_cached_at: datetime | None = None,
    ) -> None:
        self._entry: tuple[SpaceWeather, datetime] | None = None
        if initial_weather is not None and initial_cached_at is not None:
            self._entry = (initial_weather, initial_cached_at)

    def get(self) -> tuple[SpaceWeather, datetime] | None:
        return self._entry

    def set(self, data: SpaceWeather, cached_at: datetime) -> None:
        self._entry = (data, cached_at)


class JsonFileCacheStore(ICacheStore):
    """Cache persistant : un petit fichier JSON, écrit de façon atomique."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_cache_path()

    def get(self) -> tuple[SpaceWeather, datetime] | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return (
                SpaceWeather.model_validate(data["space_weather"]),
                datetime.fromisoformat(data["cached_at"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def set(self, data: SpaceWeather, cached_at: datetime) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".part")
            payload = {"space_weather": data.model_dump(mode="json"), "cached_at": cached_at}
            tmp.write_text(json.dumps(payload, default=str), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass  # un cache non écrit ne doit pas casser le mode direct


def classify(notifications: list[dict[str, Any]]) -> SpaceWeather:
    """Niveau de météo spatiale d'après la notification DONKI la plus récente."""
    if not notifications:
        return SpaceWeather(level=SpaceWeatherLevel.quiet, source="NASA DONKI")
    latest = max(notifications, key=lambda n: str(n.get("messageIssueTime", "")))
    kind = str(latest.get("messageType", ""))
    level = SpaceWeatherLevel.watch
    if kind in {"SEP", "RBE"}:
        level = SpaceWeatherLevel.storm
    elif kind in {"FLR", "CME", "IPS", "GST"}:
        level = SpaceWeatherLevel.warning
    return SpaceWeather(
        level=level,
        event=f"{kind} {latest.get('messageID', '')}".strip(),
        source="NASA DONKI",
    )


class DonkiClient(ISpaceWeatherSource):
    """Client de l'API DONKI (notifications des 3 derniers jours), timeout court."""

    def __init__(
        self,
        api_url: str = DONKI_URL,
        api_key: str | None = None,
        timeout_s: float = 3.0,
        days: int = 3,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key or os.environ.get("NASA_API_KEY", "DEMO_KEY")
        self.timeout_s = timeout_s
        self.days = days

    def url(self, now: datetime | None = None) -> str:
        now = now or datetime.now(UTC)
        params = {
            "startDate": (now - timedelta(days=self.days)).strftime("%Y-%m-%d"),
            "endDate": now.strftime("%Y-%m-%d"),
            "type": "all",
            "api_key": self.api_key,
        }
        return f"{self.api_url}?{urllib.parse.urlencode(params)}"

    def fetch_current(self) -> SpaceWeather:
        """Interroge DONKI. Sans réseau, lève une exception (gérée par LiveProvider)."""
        req = urllib.request.Request(self.url(), headers={"User-Agent": "marswalk-conditions"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return classify(data if isinstance(data, list) else [])


class LiveProvider(ConditionsProvider):
    """Mode direct : DONKI si le réseau répond, sinon la dernière valeur en cache."""

    def __init__(
        self,
        client: ISpaceWeatherSource | None = None,
        cache_store: ICacheStore | None = None,
        climatology: MedaClimatologyEngine | None = None,
    ) -> None:
        self._client = client or DonkiClient()
        self._cache = cache_store or JsonFileCacheStore()
        self._climatology = climatology or MedaClimatologyEngine()

    def space_weather(self, utc: datetime) -> tuple[SpaceWeather, datetime | None, str]:
        try:
            sw = self._client.fetch_current()
        except Exception:  # réseau absent, quota, réponse illisible : même repli
            cached = self._cache.get()
            if cached:
                sw, at = cached
                return (
                    sw,
                    at,
                    f"DONKI hors ligne : dernière valeur en cache du {at:%Y-%m-%d %H:%M} UTC",
                )
            return (
                SpaceWeather(level=SpaceWeatherLevel.quiet, source="aucune donnée DONKI"),
                None,
                "DONKI hors ligne et aucun cache",
            )
        self._cache.set(sw, utc)
        return sw, utc, "DONKI en direct"

    def _build(self, utc: datetime, sw: SpaceWeather, at: datetime | None, note: str) -> Conditions:
        dose = self._climatology.baseline_dose_usv_h() * LEVEL_DOSE_FACTOR[sw.level]
        return self._climatology.compute_conditions(
            utc=utc,
            mode="live",
            dose_rate_override=dose,
            space_weather_override=sw,
            source_note=note,
            cached_at=at,
        )

    def current(self, utc: datetime) -> Conditions:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)
        return self._build(utc, *self.space_weather(utc))

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        """Météo spatiale du moment (une seule requête) et climatologie MEDA."""
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)
        sw, at, note = self.space_weather(utc)
        out: list[Conditions] = []
        for h in range(hours):
            t = utc + timedelta(hours=h)
            c = self._build(t, sw, at, note)
            clim = self._climatology.compute_conditions(t, mode="live", basis="climatology")
            out.append(
                c.model_copy(
                    update={
                        "temperature_c": clim.temperature_c,
                        "pressure_pa": clim.pressure_pa,
                        "wind_mps": clim.wind_mps,
                    }
                )
            )
        return out
