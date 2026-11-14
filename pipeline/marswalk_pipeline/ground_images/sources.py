"""Accès aux sources du JPL (G1) : en ligne, ou depuis des réponses enregistrées.

Sources par défaut (publiques, sans clé) :

- trajet et arrêts de Perseverance : couche « waypoints » de la carte MMGIS de Mars 2020 ;
- images brutes : flux JSON ``raw_images`` du site mars.nasa.gov, interrogé sol par sol.

Les adresses se changent en option de la commande si le JPL les déplace.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Protocol

WAYPOINTS_URL = "https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints.json"
RAW_IMAGES_URL = "https://mars.nasa.gov/rss/api/"
USER_AGENT = "marswalk-pipeline/0.1 (NASA Space Apps)"


def raw_images_url(base: str, sol: int, page: int, per_page: int) -> str:
    query = {
        "feed": "raw_images",
        "category": "mars2020",
        "feedtype": "json",
        "sol": str(sol),
        "num": str(per_page),
        "page": str(page),
        "order": "sol desc",
    }
    return f"{base}?{urllib.parse.urlencode(query)}"


class Fetcher(Protocol):
    def get_json(self, url: str) -> Any: ...

    def get_bytes(self, url: str) -> bytes: ...


def cache_name(url: str, suffix: str = ".json") -> str:
    """Nom de fichier stable d'une réponse enregistrée."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24] + suffix


class HttpFetcher:
    """Téléchargement avec reprises ; garde chaque réponse dans ``cache_dir`` si donné."""

    def __init__(
        self, cache_dir: Path | None = None, retries: int = 4, timeout_s: float = 60.0
    ) -> None:
        self.cache_dir = cache_dir
        self.retries = retries
        self.timeout_s = timeout_s

    def _get(self, url: str) -> bytes:
        delay = 1.0
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout_s) as res:
                    data: bytes = res.read()
                    return data
            except OSError:
                if attempt == self.retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2
        raise AssertionError("inaccessible")

    def _cached(self, url: str, suffix: str) -> bytes:
        if self.cache_dir is None:
            return self._get(url)
        path = self.cache_dir / cache_name(url, suffix)
        if path.is_file():
            return path.read_bytes()
        data = self._get(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data

    def get_json(self, url: str) -> Any:
        return json.loads(self._cached(url, ".json"))

    def get_bytes(self, url: str) -> bytes:
        return self._cached(url, Path(urllib.parse.urlparse(url).path).suffix or ".bin")


class DirFetcher:
    """Réponses enregistrées par ``HttpFetcher(cache_dir=...)`` : aucune requête réseau."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, url: str, suffix: str) -> Path:
        return self.root / cache_name(url, suffix)

    def get_json(self, url: str) -> Any:
        path = self._path(url, ".json")
        if not path.is_file():
            raise FileNotFoundError(f"réponse non enregistrée : {url}")
        return json.loads(path.read_text(encoding="utf-8"))

    def get_bytes(self, url: str) -> bytes:
        path = self._path(url, Path(urllib.parse.urlparse(url).path).suffix or ".bin")
        if not path.is_file():
            raise FileNotFoundError(f"fichier non enregistré : {url}")
        return path.read_bytes()
