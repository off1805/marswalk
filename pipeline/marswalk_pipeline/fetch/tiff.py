"""Plages d'octets de la structure d'un TIFF distant (répertoires et tableaux de valeurs).

Le répertoire (IFD) et les tables de positions des blocs peuvent être n'importe où dans le
fichier, souvent à la fin. Pour qu'une copie locale creuse s'ouvre avec GDAL, il faut les
avoir tous transférés, en plus des blocs de pixels utiles.
"""

from __future__ import annotations

import struct

from .http import Http

TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
TYPE_SIZES |= {13: 4, 16: 8, 17: 8, 18: 8}
MAX_IFDS = 16


def _read(http: Http, url: str, start: int, length: int) -> bytes:
    return b"".join(http.stream(url, start, start + length))


def structure_ranges(http: Http, url: str) -> list[tuple[int, int]]:
    """En-tête, répertoires chaînés et valeurs hors répertoire, en plages [début, fin)."""
    head = _read(http, url, 0, 16)
    order = {b"II": "<", b"MM": ">"}.get(head[:2])
    if order is None:
        raise ValueError("pas un fichier TIFF")
    (version,) = struct.unpack(order + "H", head[2:4])
    big = version == 43
    if version not in (42, 43):
        raise ValueError(f"version TIFF inconnue : {version}")
    count_fmt, count_len = ("Q", 8) if big else ("H", 2)
    entry_len, off_fmt, off_len = (20, "Q", 8) if big else (12, "I", 4)
    ranges = [(0, 16)]
    (ifd,) = struct.unpack(order + off_fmt, head[8:16] if big else head[4:8])
    for _ in range(MAX_IFDS):
        if not ifd:
            break
        (n,) = struct.unpack(order + count_fmt, _read(http, url, ifd, count_len))
        size = count_len + n * entry_len + off_len
        raw = _read(http, url, ifd, size)
        ranges.append((ifd, ifd + size))
        for i in range(n):
            e = raw[count_len + i * entry_len : count_len + (i + 1) * entry_len]
            _tag, typ = struct.unpack(order + "HH", e[:4])
            (cnt,) = struct.unpack(order + off_fmt, e[4 : 4 + off_len])
            nbytes = cnt * TYPE_SIZES.get(typ, 1)
            if nbytes > off_len:
                (off,) = struct.unpack(order + off_fmt, e[4 + off_len :])
                ranges.append((off, off + nbytes))
        (ifd,) = struct.unpack(order + off_fmt, raw[-off_len:])
    return ranges
