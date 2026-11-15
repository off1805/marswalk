"""Accès HTTP minimal (bibliothèque standard), remplaçable dans les tests."""

from __future__ import annotations

import re
import urllib.request
from collections.abc import Iterator
from typing import Any, Protocol
from urllib.parse import urljoin

USER_AGENT = "marswalk-fetch/0.1 (NASA Space Apps 2026)"
CHUNK = 1 << 20


class Http(Protocol):
    def size(self, url: str) -> int:
        """Taille annoncée par le serveur (0 si inconnue)."""

    def stream(self, url: str, start: int = 0, end: int | None = None) -> Iterator[bytes]:
        """Octets `start` à `end` exclu (fin du fichier si None), par en-tête Range."""

    def resolve(self, url: str) -> str:
        """URL finale après redirections (évite une redirection par requête)."""

    def text(self, url: str) -> str: ...


class UrllibHttp:
    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    def _open(self, url: str, method: str = "GET", start: int = 0, end: int | None = None) -> Any:
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        if start or end is not None:
            last = "" if end is None else str(end - 1)
            req.add_header("Range", f"bytes={start}-{last}")
        return urllib.request.urlopen(req, timeout=self.timeout)

    def size(self, url: str) -> int:
        with self._open(url, "HEAD") as r:
            return int(r.headers.get("Content-Length") or 0)

    def stream(self, url: str, start: int = 0, end: int | None = None) -> Iterator[bytes]:
        with self._open(url, start=start, end=end) as r:
            if (start or end is not None) and r.status != 206:
                raise OSError(f"le serveur ne reprend pas les téléchargements : {url}")
            while chunk := r.read(CHUNK):
                yield chunk

    def resolve(self, url: str) -> str:
        with self._open(url, "HEAD") as r:
            final: str = r.geturl()
        return final

    def text(self, url: str) -> str:
        with self._open(url) as r:
            data: bytes = r.read()
        return data.decode("utf-8", errors="replace")


_HREF = re.compile(r'href="([^"?#]+)"', re.IGNORECASE)


def list_directory(
    http: Http, url: str, pattern: str, recursive: bool, dir_pattern: str = ""
) -> list[str]:
    """URL des fichiers d'un index HTTP (Apache) dont le nom correspond à `pattern`."""
    rx, drx = re.compile(pattern), re.compile(dir_pattern)
    found: list[str] = []
    for href in _HREF.findall(http.text(url)):
        full = urljoin(url, href)
        if not full.startswith(url) or full == url:
            continue  # parent, liens absolus hors du répertoire
        if href.endswith("/"):
            if recursive and drx.search(href.rstrip("/").rsplit("/", 1)[-1]):
                found += list_directory(http, full, pattern, recursive, dir_pattern)
        elif rx.search(href.rsplit("/", 1)[-1]):
            found.append(full)
    return sorted(set(found))
