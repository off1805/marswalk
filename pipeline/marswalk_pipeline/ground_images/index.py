"""Index des images au sol (G1) : chaque image placée à la position du rover au sol de prise.

Les images brutes du JPL ne portent pas de coordonnées. Elles portent le sol et, souvent,
l'arrêt du rover (``site`` et ``drive``, compteurs de la mission). On les place donc :

1. sur l'arrêt de même ``site`` et ``drive`` dans la liste des arrêts publiée par le JPL ;
2. à défaut, sur le dernier arrêt connu au sol de prise de vue (ou avant).

La position est celle du rover, pas celle de la scène photographiée ; ``azimuth_deg``
(azimut du mât) indique la direction de prise de vue quand le JPL le donne.
"""

from __future__ import annotations

import io
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

from marswalk_core.schemas import (
    MARS_2000_RADIUS_M,
    Feature,
    FeatureCollection,
    LineStringGeometry,
    LonLat,
    PointGeometry,
)

from .sources import RAW_IMAGES_URL, WAYPOINTS_URL, Fetcher, raw_images_url

CAMERAS = {"MCZ": "Mastcam-Z", "NAVCAM": "Navcam"}
"""Préfixe de l'instrument dans le flux du JPL vers le nom de la caméra."""
CREDITS = {"Mastcam-Z": "NASA/JPL-Caltech/ASU", "Navcam": "NASA/JPL-Caltech"}
THUMB_PX = 256


@dataclass(frozen=True)
class Waypoint:
    sol: int
    site: int | None
    drive: int | None
    lon: float
    lat: float


@dataclass(frozen=True)
class GroundImage:
    image_id: str
    sol: int
    instrument: str
    camera: str
    url: str | None
    thumb_url: str | None
    utc: str | None = None
    azimuth_deg: float | None = None
    elevation_deg: float | None = None
    site: int | None = None
    drive: int | None = None
    sample_type: str | None = None


@dataclass
class IndexOptions:
    bbox: tuple[float, float, float, float]
    """Emprise du site (ouest, sud, est, nord) en degrés."""
    margin_m: float = 0.0
    """Marge autour de l'emprise pour garder les images prises juste à côté."""
    sols: tuple[int, int] | None = None
    per_stop: int = 2
    """Images gardées par arrêt du rover et par caméra."""
    max_images: int = 300
    per_page: int = 100
    max_pages: int = 5
    thumbs: bool = True


@dataclass
class IndexResult:
    images: FeatureCollection
    traverse: FeatureCollection
    thumbs: dict[str, bytes] = field(default_factory=dict)
    report: list[str] = field(default_factory=list)


# -- lecture des sources -----------------------------------------------------------


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _lon(lon: float) -> float:
    """Longitude est ramenée entre -180 et 180 (règle R2)."""
    return (lon + 180.0) % 360.0 - 180.0


def _prop(props: dict[str, Any], *names: str) -> Any:
    for n in names:
        for key in (n, n.upper(), n.capitalize()):
            if key in props and props[key] not in (None, ""):
                return props[key]
    return None


def parse_waypoints(data: Any) -> list[Waypoint]:
    """Arrêts du rover depuis le GeoJSON MMGIS (points ``[lon, lat]``), triés dans le temps."""
    out: list[Waypoint] = []
    for f in data.get("features", []) if isinstance(data, dict) else []:
        geom = f.get("geometry") or {}
        props = f.get("properties") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        lon = _float(_prop(props, "lon")) if len(coords) < 2 else _float(coords[0])
        lat = _float(_prop(props, "lat")) if len(coords) < 2 else _float(coords[1])
        sol = _int(_prop(props, "sol"))
        if lon is None or lat is None or sol is None:
            continue
        out.append(
            Waypoint(
                sol=sol,
                site=_int(_prop(props, "site")),
                drive=_int(_prop(props, "drive")),
                lon=_lon(lon),
                lat=lat,
            )
        )
    return sorted(out, key=lambda w: (w.sol, w.site or 0, w.drive or 0))


def camera_of(instrument: str) -> str | None:
    up = instrument.upper()
    return next((name for prefix, name in CAMERAS.items() if up.startswith(prefix)), None)


def parse_images(data: Any) -> list[GroundImage]:
    """Images Mastcam-Z et Navcam d'une page du flux ``raw_images`` (vignettes exclues)."""
    out: list[GroundImage] = []
    items = data.get("images", []) if isinstance(data, dict) else []
    for it in items:
        cam = it.get("camera") or {}
        instrument = str(cam.get("instrument") or it.get("instrument") or "")
        camera = camera_of(instrument)
        image_id = it.get("imageid") or it.get("image_id") or it.get("id")
        sol = _int(it.get("sol"))
        if camera is None or not image_id or sol is None:
            continue
        sample = it.get("sample_type")
        if isinstance(sample, str) and sample.lower().startswith("thumb"):
            continue
        files = it.get("image_files") or {}
        ext = it.get("extended") or {}
        out.append(
            GroundImage(
                image_id=str(image_id),
                sol=sol,
                instrument=instrument,
                camera=camera,
                url=files.get("full_res") or files.get("large"),
                thumb_url=files.get("small") or files.get("medium") or files.get("large"),
                utc=it.get("date_taken_utc"),
                azimuth_deg=_float(ext.get("mastAz")),
                elevation_deg=_float(ext.get("mastEl")),
                site=_int(it.get("site", ext.get("site"))),
                drive=_int(it.get("drive", ext.get("drive"))),
                sample_type=sample if isinstance(sample, str) else None,
            )
        )
    return out


# -- position et emprise -----------------------------------------------------------


def _expanded(bbox: tuple[float, float, float, float], margin_m: float) -> tuple[float, ...]:
    west, south, east, north = bbox
    dlat = math.degrees(margin_m / MARS_2000_RADIUS_M)
    dlon = dlat / max(math.cos(math.radians((south + north) / 2)), 1e-6)
    return west - dlon, south - dlat, east + dlon, north + dlat


def _inside(w: Waypoint, box: tuple[float, ...]) -> bool:
    return box[0] <= w.lon <= box[2] and box[1] <= w.lat <= box[3]


def locate(img: GroundImage, waypoints: list[Waypoint]) -> tuple[Waypoint, str] | None:
    """Arrêt du rover au moment de l'image, et la façon dont on l'a trouvé."""
    if img.site is not None and img.drive is not None:
        exact = [w for w in waypoints if w.site == img.site and w.drive == img.drive]
        if exact:
            return exact[-1], "site_drive"
    before = [w for w in waypoints if w.sol <= img.sol]
    if before:
        return before[-1], "sol"
    return None


def traverse_features(waypoints: list[Waypoint], box: tuple[float, ...]) -> list[Feature]:
    """Trajet du rover dans l'emprise : une ligne par passage continu dans l'emprise."""
    runs: list[list[Waypoint]] = []
    current: list[Waypoint] = []
    for w in waypoints:
        if _inside(w, box):
            current.append(w)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    features = []
    for i, run in enumerate(r for r in runs if len(r) >= 2):
        features.append(
            Feature(
                id=f"traverse-{i + 1}",
                geometry=LineStringGeometry(coordinates=[LonLat(w.lon, w.lat) for w in run]),
                properties={
                    "name": "Trajet de Perseverance",
                    "sol_start": run[0].sol,
                    "sol_end": run[-1].sol,
                    "source": "JPL, arrêts publiés de Mars 2020 (MMGIS)",
                },
            )
        )
    return features


# -- construction -------------------------------------------------------------------


def _thumbnail(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as src:
        im = src.convert("RGB")
    im.thumbnail((THUMB_PX, THUMB_PX))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=82, optimize=True)
    return out.getvalue()


def _spread(items: list[Any], n: int) -> list[Any]:
    """``n`` éléments répartis régulièrement dans la liste."""
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def build_index(
    fetcher: Fetcher,
    options: IndexOptions,
    *,
    waypoints_url: str = WAYPOINTS_URL,
    raw_url: str = RAW_IMAGES_URL,
    log: Callable[[str], None] = lambda _: None,
) -> IndexResult:
    box = _expanded(options.bbox, options.margin_m)
    waypoints = parse_waypoints(fetcher.get_json(waypoints_url))
    report = [f"Arrêts du rover publiés : {len(waypoints)}"]
    sols = sorted({w.sol for w in waypoints if _inside(w, box)})
    if options.sols is not None:
        lo, hi = options.sols
        sols = [s for s in sols if lo <= s <= hi]
    report.append(f"Sols passés dans l'emprise : {len(sols)}")
    log(f"{len(sols)} sols à interroger")

    kept: dict[tuple[int, str], list[tuple[GroundImage, Waypoint, str]]] = defaultdict(list)
    seen: set[str] = set()
    stats: Counter[str] = Counter()
    for sol in sols:
        for page in range(options.max_pages):
            url = raw_images_url(raw_url, sol, page, options.per_page)
            try:
                data = fetcher.get_json(url)
            except (OSError, ValueError) as exc:
                stats["pages en erreur"] += 1
                log(f"sol {sol} page {page} : {exc}")
                break
            items = data.get("images", []) if isinstance(data, dict) else []
            for img in parse_images(data):
                if img.image_id in seen:
                    continue
                seen.add(img.image_id)
                found = locate(img, waypoints)
                if found is None:
                    stats["sans position"] += 1
                    continue
                wp, how = found
                if not _inside(wp, box):
                    stats["hors emprise"] += 1
                    continue
                key = (waypoints.index(wp), img.camera)
                if len(kept[key]) < options.per_stop:
                    kept[key].append((img, wp, how))
            if len(items) < options.per_page:
                break

    selected = sorted(
        (x for group in kept.values() for x in group), key=lambda x: (x[0].sol, x[0].image_id)
    )
    selected = _spread(selected, options.max_images)

    thumbs: dict[str, bytes] = {}
    features: list[Feature] = []
    for img, wp, how in selected:
        thumb: str | None = img.thumb_url
        if options.thumbs and img.thumb_url:
            try:
                name = f"{img.image_id}.jpg"
                thumbs[name] = _thumbnail(fetcher.get_bytes(img.thumb_url))
                thumb = f"thumbs/{name}"
            except (OSError, ValueError) as exc:
                stats["vignettes en erreur"] += 1
                log(f"vignette {img.image_id} : {exc}")
        features.append(
            Feature(
                id=img.image_id,
                geometry=PointGeometry(coordinates=LonLat(wp.lon, wp.lat)),
                properties={
                    "image_id": img.image_id,
                    "sol": img.sol,
                    "instrument": img.instrument,
                    "camera": img.camera,
                    "thumb": thumb,
                    "thumb_url": img.thumb_url,
                    "url": img.url,
                    "utc": img.utc,
                    "azimuth_deg": img.azimuth_deg,
                    "elevation_deg": img.elevation_deg,
                    "site": wp.site,
                    "drive": wp.drive,
                    "position_source": how,
                    "credit": CREDITS[img.camera],
                },
            )
        )
    by_camera = Counter(f.properties["camera"] for f in features)
    report += [
        f"Images positionnées gardées : {len(features)} "
        + ", ".join(f"{c} {n}" for c, n in sorted(by_camera.items())),
        f"Vignettes enregistrées : {len(thumbs)}",
        *[f"{k.capitalize()} : {v}" for k, v in sorted(stats.items())],
    ]
    return IndexResult(
        images=FeatureCollection(features=features),
        traverse=FeatureCollection(features=traverse_features(waypoints, box)),
        thumbs=thumbs,
        report=report,
    )


def sols_of(features: Iterable[Feature]) -> list[int]:
    return sorted({int(f.properties["sol"]) for f in features})
