"""Transfert de plages d'octets sur plusieurs connexions, avec reprise par segment.

Certains serveurs (USGS sur Amazon S3) plafonnent chaque connexion à quelques centaines de
Ko/s : on découpe donc en segments de `SEGMENT` octets transférés par `WORKERS` connexions,
chacun écrit à sa place dans le fichier cible. Les segments terminés sont notés dans
`<fichier>.segments` : une reprise ne transfère que ceux qui manquent.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .http import Http

WORKERS = 8
SEGMENT = 2 << 20


def merge_ranges(ranges: list[tuple[int, int]], gap: int = 1 << 20) -> list[tuple[int, int]]:
    """Fusionne des plages [début, fin) proches (écart inférieur à `gap`)."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(r for r in ranges if r[1] > r[0]):
        if merged and start - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def split(ranges: list[tuple[int, int]], size: int | None = None) -> list[tuple[int, int]]:
    size = size or SEGMENT
    return [(s, min(s + size, end)) for start, end in ranges for s in range(start, end, size)]


def fetch_ranges(
    http: Http,
    url: str,
    ranges: list[tuple[int, int]],
    path: Path,
    file_size: int,
    on_bytes: Callable[[int], None] = lambda _: None,
    workers: int = WORKERS,
) -> None:
    """Écrit les plages `ranges` de `url` aux mêmes positions dans `path` (taille `file_size`)."""
    state = path.with_name(path.name + ".segments")
    done: set[int] = set()
    if path.exists() and state.exists():
        done = set(json.loads(state.read_text("utf-8")))
    else:
        with path.open("wb") as f:
            f.truncate(file_size)  # fichier creux : seules les plages utiles occupent le disque
    segments = [seg for seg in split(ranges) if seg[0] not in done]
    on_bytes(sum(e - s for s, e in split(ranges)) - sum(e - s for s, e in segments))
    lock = threading.Lock()
    fd = os.open(path, os.O_WRONLY)

    def get(seg: tuple[int, int]) -> None:
        pos = seg[0]
        for chunk in http.stream(url, seg[0], seg[1]):
            os.pwrite(fd, chunk, pos)
            pos += len(chunk)
            on_bytes(len(chunk))
        if pos != seg[1]:
            raise OSError(f"segment incomplet {seg[0]}-{seg[1]} : {pos - seg[0]} octets")
        with lock:
            done.add(seg[0])
            state.write_text(json.dumps(sorted(done)), "utf-8")

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in [pool.submit(get, seg) for seg in segments]:
                future.result()
    finally:
        os.close(fd)
    state.unlink(missing_ok=True)
