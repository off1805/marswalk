"""Index des images au sol (G1), sans réseau : réponses du JPL simulées."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from marswalk_core.schemas import FeatureCollection, LayerSource, PointGeometry
from marswalk_core.site_package import load_site
from marswalk_pipeline.ground_images import (
    IndexOptions,
    build_index,
    parse_images,
    parse_waypoints,
)
from marswalk_pipeline.ground_images.__main__ import main
from marswalk_pipeline.ground_images.sources import (
    RAW_IMAGES_URL,
    WAYPOINTS_URL,
    cache_name,
    raw_images_url,
)

BBOX = load_site("fictif").manifest.bbox
WEST, SOUTH, EAST, NORTH = BBOX
THUMB_URL = "https://mars.nasa.gov/mars2020-raw-images/{id}_320.jpg"


def jpeg(color: tuple[int, int, int] = (180, 90, 40)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(out, format="JPEG")
    return out.getvalue()


def waypoints() -> dict[str, Any]:
    """Arrêts : sols 1 à 3 hors emprise (à l'est), 4 à 15 dans l'emprise, 16 au-delà."""
    feats: list[dict[str, Any]] = []
    for sol in range(1, 17):
        if sol <= 3:
            lon, lat = EAST + 0.02, NORTH + 0.01
        elif sol <= 15:
            k = (sol - 4) / 11
            lon, lat = WEST + 0.004 + k * (EAST - WEST - 0.008), SOUTH + 0.004 + k * 0.02
        else:
            lon, lat = WEST - 0.05, SOUTH - 0.05
        feats.append(
            {
                "type": "Feature",
                # Longitudes en 0–360 dans certaines couches du JPL : normalisées à -180–180.
                "geometry": {"type": "Point", "coordinates": [lon if sol % 2 else lon + 360, lat]},
                "properties": {"sol": sol, "site": 3, "drive": sol * 100},
            }
        )
    feats.append({"type": "Feature", "geometry": None, "properties": {"sol": 99}})
    return {"type": "FeatureCollection", "features": feats}


def image(
    sol: int, n: int, instrument: str, *, sample: str = "Full", drive: bool = True
) -> dict[str, Any]:
    image_id = f"{instrument}_{sol:04d}_{n:02d}"
    data: dict[str, Any] = {
        "imageid": image_id,
        "sol": sol,
        "camera": {"instrument": instrument},
        "sample_type": sample,
        "date_taken_utc": f"2021-03-{sol:02d}T12:00:00.000",
        "site": 3 if drive else None,
        "drive": sol * 100 if drive else None,
        "image_files": {
            "full_res": f"https://mars.nasa.gov/mars2020-raw-images/{image_id}.png",
            "small": THUMB_URL.format(id=image_id),
        },
        "extended": {"mastAz": "123.4", "mastEl": "UNK"},
    }
    return data


def pages() -> dict[int, dict[str, Any]]:
    out = {}
    for sol in range(1, 17):
        imgs = [
            image(sol, 1, "MCZ_LEFT"),
            image(sol, 2, "MCZ_RIGHT"),
            image(sol, 3, "NAVCAM_LEFT", drive=sol % 3 != 0),
            image(sol, 4, "NAVCAM_RIGHT", sample="Thumbnail"),
            image(sol, 5, "FRONT_HAZCAM_LEFT_A"),
            image(sol, 6, "SHERLOC_WATSON"),
        ]
        out[sol] = {"images": imgs, "per_page": 100, "page": 0, "total_results": len(imgs)}
    return out


class FakeFetcher:
    def __init__(self) -> None:
        self.json: dict[str, Any] = {WAYPOINTS_URL: waypoints()}
        for sol, page in pages().items():
            self.json[raw_images_url(RAW_IMAGES_URL, sol, 0, 100)] = page
        self.calls: list[str] = []

    def get_json(self, url: str) -> Any:
        self.calls.append(url)
        if url not in self.json:
            raise FileNotFoundError(url)
        return self.json[url]

    def get_bytes(self, url: str) -> bytes:
        self.calls.append(url)
        if "SOL_BROKEN" in url:
            raise OSError("404")
        return jpeg()


def test_parsers_keep_only_mastcam_z_and_navcam_full_frames() -> None:
    imgs = parse_images(pages()[5])
    assert [i.camera for i in imgs] == ["Mastcam-Z", "Mastcam-Z", "Navcam"]
    assert imgs[0].azimuth_deg == pytest.approx(123.4) and imgs[0].elevation_deg is None
    wps = parse_waypoints(waypoints())
    assert len(wps) == 16 and all(-180 <= w.lon <= 180 for w in wps)
    assert [w.sol for w in wps] == sorted(w.sol for w in wps)


def test_index_places_at_least_twenty_images_on_the_site() -> None:
    fetcher = FakeFetcher()
    result = build_index(fetcher, IndexOptions(bbox=BBOX, per_stop=2))
    fc = FeatureCollection.model_validate(result.images.model_dump())
    feats = fc.features
    assert len(feats) >= 20
    # Seuls les sols passés dans l'emprise sont interrogés.
    asked = {u for u in fetcher.calls if "raw_images" in u}
    assert len(asked) == 12
    for f in feats:
        assert isinstance(f.geometry, PointGeometry)
        lon, lat = f.geometry.coordinates
        assert WEST <= lon <= EAST and SOUTH <= lat <= NORTH
        p = f.properties
        # Chaque image affiche sol, instrument et identifiant.
        assert isinstance(p["sol"], int) and p["instrument"] and p["image_id"] == f.id
        assert p["camera"] in ("Mastcam-Z", "Navcam")
        assert p["thumb"] == f"thumbs/{f.id}.jpg" and p["url"].endswith(".png")
    # Au plus deux images par arrêt et par caméra.
    per_stop: dict[tuple[int, str], int] = {}
    for f in feats:
        key = (f.properties["sol"], f.properties["camera"])
        per_stop[key] = per_stop.get(key, 0) + 1
    assert max(per_stop.values()) <= 2
    hows = {f.properties["position_source"] for f in feats}
    assert hows == {"site_drive", "sol"}
    assert len(result.thumbs) == len(feats)
    with Image.open(io.BytesIO(next(iter(result.thumbs.values())))) as im:
        assert max(im.size) <= 256


def test_traverse_is_clipped_to_the_site() -> None:
    result = build_index(FakeFetcher(), IndexOptions(bbox=BBOX, thumbs=False))
    (line,) = result.traverse.features
    assert line.properties["sol_start"] == 4 and line.properties["sol_end"] == 15
    assert len(line.geometry.coordinates) == 12  # type: ignore[union-attr]


def test_max_images_spreads_the_selection_over_time() -> None:
    result = build_index(FakeFetcher(), IndexOptions(bbox=BBOX, max_images=6, thumbs=False))
    sols = [f.properties["sol"] for f in result.images.features]
    assert len(sols) == 6 and sols[0] == 4 and sols[-1] >= 12


def test_missing_thumbnail_keeps_the_remote_link() -> None:
    fetcher = FakeFetcher()
    page = fetcher.json[raw_images_url(RAW_IMAGES_URL, 4, 0, 100)]
    page["images"][0]["image_files"]["small"] = "https://example.org/SOL_BROKEN.jpg"
    result = build_index(fetcher, IndexOptions(bbox=BBOX))
    f = next(f for f in result.images.features if f.id == page["images"][0]["imageid"])
    assert f.properties["thumb"] == "https://example.org/SOL_BROKEN.jpg"
    assert any("Vignettes en erreur : 1" in line for line in result.report)


def test_command_replays_a_cache_and_writes_the_package_inputs(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    fake = FakeFetcher()
    for url, data in fake.json.items():
        (cache / cache_name(url)).write_text(json.dumps(data), encoding="utf-8")
        for img in data.get("images", []):
            thumb = img["image_files"]["small"]
            (cache / cache_name(thumb, ".jpg")).write_bytes(jpeg())
    work = tmp_path / "work"
    assert main(["fictif", "--work", str(work), "--from-cache", str(cache), "--margin-m", "0"]) == 0
    site = work / "fictif"
    images = FeatureCollection.model_validate_json(
        (site / "vector" / "ground_images.geojson").read_text(encoding="utf-8")
    )
    assert len(images.features) >= 20
    assert len(list((site / "thumbs").glob("*.jpg"))) == len(images.features)
    FeatureCollection.model_validate_json(
        (site / "vector" / "rover_traverse.geojson").read_text(encoding="utf-8")
    )
    for layer in ("ground_images", "rover_traverse"):
        meta = json.loads((site / "layers" / f"{layer}.json").read_text(encoding="utf-8"))
        LayerSource.model_validate(meta["source"])
    assert "Images positionnées gardées" in (site / "ground_images_report.md").read_text("utf-8")
