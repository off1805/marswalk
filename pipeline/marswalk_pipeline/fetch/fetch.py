"""Téléchargement des produits bruts d'un site (D0).

Pour chaque fichier : découpe à la source si `clip` (seuls les blocs utiles du fichier distant
sont transférés), sinon téléchargement complet avec reprise. Les gros transferts passent par
plusieurs connexions en parallèle (voir parallel.py). Un fichier déjà inscrit
dans `sources.lock.yaml` avec la même URL et la même taille sur disque n'est pas retéléchargé.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

from .http import Http, UrllibHttp, list_directory
from .parallel import fetch_ranges, merge_ranges, split
from .sources import Extent, Product, Sources
from .tiff import structure_ranges

LOCK_NAME = "sources.lock.yaml"
REPORT_NAME = "fetch_report.md"

Clipper = Callable[[str, Path, tuple[float, float, float, float]], None]


@dataclass
class Planned:
    product: Product
    url: str
    dest: Path
    size: int  # octets à transférer au pire (fichier complet)
    clip: bool


@dataclass
class Outcome:
    planned: Planned
    status: str  # "téléchargé", "découpé", "déjà présent", "échec"
    detail: str = ""


def file_name(url: str) -> str:
    return unquote(Path(urlparse(url).path).name)


def plan(
    sources: Sources, http: Http, out_dir: Path, only: set[str] | None = None
) -> list[Planned]:
    def size_of(url: str) -> int:
        try:
            return http.size(url)
        except OSError:
            return 0

    items: list[Planned] = []
    for p in sources.products:
        if only and p.id not in only:
            continue
        files = [(f.url, f.size) for f in p.files]
        if p.listing:
            lst = p.listing
            urls = list_directory(http, lst.url, lst.pattern, lst.recursive, lst.dir_pattern)
            files += [(u, 0) for u in urls]
        unknown = [u for u, s in files if not s]
        with ThreadPoolExecutor(max_workers=8) as pool:
            sizes = dict(zip(unknown, pool.map(size_of, unknown), strict=True))
        for url, size in files:
            name = file_name(url)
            if p.clip:
                name = Path(name).stem + "_clip.tif"
            items.append(Planned(p, url, out_dir / p.id / name, size or sizes[url], p.clip))
    return items


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def read_lock(out_dir: Path) -> dict[str, Any]:
    path = out_dir / LOCK_NAME
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data.get("files", {}))


def write_lock(out_dir: Path, entries: dict[str, Any]) -> None:
    body = {"files": dict(sorted(entries.items()))}
    (out_dir / LOCK_NAME).write_text(
        yaml.safe_dump(body, allow_unicode=True, sort_keys=False), "utf-8"
    )


def is_complete(item: Planned, out_dir: Path, lock: dict[str, Any]) -> bool:
    key = item.dest.relative_to(out_dir).as_posix()
    entry = lock.get(key)
    return bool(
        entry
        and item.dest.exists()
        and entry.get("url") == item.url
        and entry.get("size") == item.dest.stat().st_size
    )


class Progress:
    """Ligne de progression sur stderr : Mo transférés, pourcentage, vitesse, temps restant."""

    def __init__(
        self, total: int, done: int = 0, label: str = "", fmt: Callable[[int], str] | None = None
    ) -> None:
        self.total, self.done, self.label = total, done, label
        self.fmt = fmt or human
        self.start_done, self.t0, self.last = done, time.monotonic(), 0.0
        self.lock = threading.Lock()

    def add(self, n: int) -> None:
        with self.lock:
            self.done += n
            now = time.monotonic()
            if now - self.last >= 0.5:
                self.last = now
                self.show()

    def show(self, end: str = "") -> None:
        elapsed = max(time.monotonic() - self.t0, 1e-6)
        speed = (self.done - self.start_done) / elapsed
        parts = [f"  {self.label}{self.fmt(self.done)}"]
        if self.total:
            pct = 100 * self.done / self.total
            parts.append(f"/ {self.fmt(self.total)} ({pct:5.1f} %)")
        parts.append(f"{self.fmt(int(speed))}/s")
        if self.total and speed > 0:
            parts.append(f"reste {_duration((self.total - self.done) / speed)}")
        sys.stderr.write("\r" + "  ".join(parts).ljust(78) + end)
        sys.stderr.flush()

    def close(self) -> None:
        self.show(end="\n")


def _duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {s:02d} s"


PARALLEL_MIN = 4 << 20  # en dessous, une seule connexion suffit
FALLBACK_MAX = 200 << 20  # au-delà, une découpe ratée est signalée, pas remplacée


def download(http: Http, url: str, dest: Path, expected: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    if expected >= PARALLEL_MIN:
        real = http.resolve(url)
        bar = Progress(expected)
        try:
            fetch_ranges(http, real, [(0, expected)], part, expected, bar.add)
        finally:
            bar.close()
        part.replace(dest)
        return
    start = part.stat().st_size if part.exists() else 0
    if expected and start > expected:
        part.unlink()
        start = 0
    if not expected or start < expected:
        bar = Progress(expected, start, "reprise " if start else "")
        try:
            with part.open("ab") as f:
                for chunk in http.stream(url, start):
                    f.write(chunk)
                    bar.add(len(chunk))
        finally:
            bar.close()
    got = part.stat().st_size
    if expected and got != expected:
        raise OSError(f"taille incorrecte : {got} octets au lieu de {expected}")
    part.replace(dest)


GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "GDAL_HTTP_MAX_RETRY": "5",
    "CPL_VSIL_CURL_CHUNK_SIZE": "10485760",
}


def gdal_clip(
    url: str, dest: Path, bounds: tuple[float, float, float, float], http: Http | None = None
) -> None:
    """Découpe une emprise en degrés dans un raster distant et l'écrit en GeoTIFF.

    GeoTIFF : on lit les positions des blocs utiles dans l'en-tête distant, on transfère ces
    plages d'octets en parallèle dans une copie locale creuse, puis on découpe en local.
    Autres formats (cube ISIS) : lecture fenêtrée directe par /vsicurl/.
    """
    import rasterio

    http = http or UrllibHttp()
    real = http.resolve(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.Env(**GDAL_ENV), rasterio.open(f"/vsicurl/{real}") as src:
        win = _window(src, bounds)
        ranges = _block_ranges(src, win) if src.driver == "GTiff" else None
    if ranges is None:
        with rasterio.Env(**GDAL_ENV), rasterio.open(f"/vsicurl/{real}") as src:
            _write_window(src, win, dest, label="découpe distante ")
        return
    total = http.size(real)
    mirror = dest.with_name(dest.name + ".src")
    wanted = merge_ranges(ranges + structure_ranges(http, real))
    bar = Progress(sum(e - s for s, e in split(wanted)), label="blocs ")
    try:
        fetch_ranges(http, real, wanted, mirror, total, bar.add)
    finally:
        bar.close()
    with rasterio.open(mirror) as src:
        _write_window(src, win, dest, label="")
    mirror.unlink()


def _window(src: Any, bounds: tuple[float, float, float, float]) -> Any:
    from rasterio.crs import CRS
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds

    mars_geo = CRS.from_proj4("+proj=longlat +R=3396190 +no_defs")
    b = transform_bounds(mars_geo, src.crs, *bounds) if src.crs else bounds
    win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
    return win.intersection(Window(0, 0, src.width, src.height))


def _block_ranges(src: Any, win: Any) -> list[tuple[int, int]] | None:
    """Plages d'octets : en-tête + blocs (tuiles ou bandes) qui touchent la fenêtre."""
    bh, bw = src.block_shapes[0]
    first = src.get_tag_item("BLOCK_OFFSET_0_0", "TIFF", bidx=1)
    if not first:
        return None
    ranges = [(0, int(first))]  # en-tête et tables des positions
    rows = range(int(win.row_off) // bh, (int(win.row_off + win.height) - 1) // bh + 1)
    cols = range(int(win.col_off) // bw, (int(win.col_off + win.width) - 1) // bw + 1)
    for band in range(1, src.count + 1):
        for by in rows:
            for bx in cols:
                off = src.get_tag_item(f"BLOCK_OFFSET_{bx}_{by}", "TIFF", bidx=band)
                size = src.get_tag_item(f"BLOCK_SIZE_{bx}_{by}", "TIFF", bidx=band)
                if not off or not size:
                    return None
                ranges.append((int(off), int(off) + int(size)))
    return ranges


def _write_window(src: Any, win: Any, dest: Path, label: str) -> None:
    import rasterio
    from rasterio.windows import Window

    tmp = dest.with_name(dest.name + ".part")
    profile = src.profile | {
        "driver": "GTiff",
        "width": int(win.width),
        "height": int(win.height),
        "transform": src.window_transform(win),
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "compress": "deflate",
        "BIGTIFF": "IF_SAFER",
    }
    height, step = int(win.height), 256
    bar = Progress(height, label=label, fmt=lambda n: f"{n} lignes") if label else None
    try:
        with rasterio.open(tmp, "w", **profile) as dst:
            for r0 in range(0, height, step):
                h = min(step, height - r0)
                part = Window(win.col_off, win.row_off + r0, win.width, h)
                dst.write(src.read(window=part), window=Window(0, r0, win.width, h))
                if bar:
                    bar.add(h)
    finally:
        if bar:
            bar.close()
    tmp.replace(dest)


def run(
    sources: Sources,
    http: Http,
    out_dir: Path,
    only: set[str] | None = None,
    clipper: Clipper = gdal_clip,
    log: Callable[[str], None] = lambda msg: print(msg, flush=True),
) -> list[Outcome]:
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = read_lock(out_dir)
    outcomes: list[Outcome] = []
    items = plan(sources, http, out_dir, only)
    for n, item in enumerate(items, 1):
        key = item.dest.relative_to(out_dir).as_posix()
        full = Planned(
            item.product, item.url, item.dest.with_name(file_name(item.url)), item.size, False
        )
        if is_complete(item, out_dir, lock) or (item.clip and is_complete(full, out_dir, lock)):
            outcomes.append(Outcome(item, "déjà présent"))
            continue
        mode = "découpe" if item.clip else human(item.size)
        log(f"[{n}/{len(items)}] {item.product.id} : {file_name(item.url)} ({mode})")
        status, detail, used = "téléchargé", "", item.url
        try:
            if item.clip:
                try:
                    clipper(item.url, item.dest, _bounds(sources.extent, item.product))
                    status = "découpé"
                except Exception as exc:  # repli : fichier complet, s'il reste raisonnable
                    if item.size > FALLBACK_MAX:
                        raise RuntimeError(
                            f"découpe impossible ({exc}) ; fichier complet de "
                            f"{human(item.size)} non téléchargé"
                        ) from exc
                    detail = f"découpe impossible ({exc}), fichier complet"
                    item = full
                    key = item.dest.relative_to(out_dir).as_posix()
                    download(http, item.url, item.dest, item.size)
            else:
                download(http, item.url, item.dest, item.size)
        except Exception as exc:
            outcomes.append(Outcome(item, "échec", str(exc)))
            log(f"  échec : {exc}")
            continue
        lock[key] = {
            "product": item.product.id,
            "url": used,
            "size": item.dest.stat().st_size,
            "sha256": sha256(item.dest),
            "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "clipped": status == "découpé",
        }
        write_lock(out_dir, lock)
        outcomes.append(Outcome(item, status, detail))
    write_report(sources, out_dir, outcomes)
    return outcomes


def _bounds(extent: Extent, product: Product) -> tuple[float, float, float, float]:
    return extent.bounds(product.margin_m)


def human(n: int) -> str:
    size = float(n)
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"


def write_report(sources: Sources, out_dir: Path, outcomes: list[Outcome]) -> None:
    w, s, e, n = sources.extent.bounds()
    lines = [
        f"# Rapport de téléchargement : {sources.site_id}",
        "",
        f"Date : {dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}  ",
        f"Emprise (marge par défaut) : {w:.4f} à {e:.4f} E, {s:.4f} à {n:.4f} N",
        "",
        "| Produit | Priorité | Fichier | État | Détail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for o in outcomes:
        p = o.planned
        lines.append(
            f"| {p.product.id} | {p.product.priority} | {p.dest.name} | {o.status} | {o.detail} |"
        )
    seen = {o.planned.product.id for o in outcomes if o.status != "échec"}
    missing = [p for p in sources.products if p.id not in seen]
    lines += ["", "## Manquants", ""]
    lines += [f"- {p.id} ({p.priority}) : aucun fichier obtenu" for p in missing] or ["Aucun."]
    lines += [
        "",
        "## Notes",
        "",
        "- Les produits 1 à 4 viennent des portails de la page des ressources (Mars Trek, USGS).",
        "- THEMIS, CRISM, MEDA et RAD ne sont pas couverts par ces portails : URL prises sur "
        "l'USGS Astropedia, l'API ODE et les nœuds PDS (Atmosphères, PPI).",
        "- Le cube THEMIS (ISIS .cub) est découpé par GDAL ; le repli télécharge 2,5 Go.",
    ]
    (out_dir / REPORT_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
