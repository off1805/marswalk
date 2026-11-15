"""``python -m marswalk_pipeline.ground_images <site>`` : index des images au sol (G1).

Écrit dans ``<work>/<site>/`` les entrées que D3 met dans le paquet de site :
``vector/ground_images.geojson``, ``vector/rover_traverse.geojson``, ``thumbs/``,
``layers/ground_images.json`` et ``layers/rover_traverse.json`` (provenance), plus
``ground_images_report.md``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

from marswalk_core.config import load_site_config
from marswalk_core.paths import repo_root
from marswalk_core.schemas import MARS_2000_RADIUS_M
from marswalk_core.site_package import load_site

from .index import IndexOptions, build_index
from .sources import RAW_IMAGES_URL, WAYPOINTS_URL, DirFetcher, Fetcher, HttpFetcher


def site_bbox(site_id: str) -> tuple[float, float, float, float]:
    """Emprise du site : celle du paquet s'il existe, sinon centre et taille de ``site.yaml``."""
    try:
        w, s, e, n = load_site(site_id).manifest.bbox
        return (w, s, e, n)
    except FileNotFoundError:
        pass
    cfg = load_site_config(site_id)
    lon, lat = float(cfg["center"]["lon"]), float(cfg["center"]["lat"])
    half = float(cfg.get("size_m", 5000)) / 2
    dlat = math.degrees(half / MARS_2000_RADIUS_M)
    dlon = dlat / math.cos(math.radians(lat))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def provenance(layer: str, url: str, note: str) -> dict[str, object]:
    return {
        "source": {"instrument": layer, "mission": "Mars 2020", "url": url, "note": note},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m marswalk_pipeline.ground_images")
    p.add_argument("site")
    p.add_argument("--work", type=Path, default=repo_root() / "data" / "work")
    p.add_argument("--sols", help="intervalle de sols, par ex. 1-1200")
    p.add_argument("--per-stop", type=int, default=2)
    p.add_argument("--max-images", type=int, default=300)
    p.add_argument("--margin-m", type=float, default=250.0)
    p.add_argument("--no-thumbs", action="store_true")
    p.add_argument("--cache", type=Path, help="garde les réponses brutes (rejouables)")
    p.add_argument("--from-cache", type=Path, help="rejoue des réponses gardées, sans réseau")
    p.add_argument("--waypoints-url", default=WAYPOINTS_URL)
    p.add_argument("--raw-url", default=RAW_IMAGES_URL)
    args = p.parse_args(argv)

    sols = None
    if args.sols:
        lo, _, hi = args.sols.partition("-")
        sols = (int(lo), int(hi or lo))
    fetcher: Fetcher = (
        DirFetcher(args.from_cache) if args.from_cache else HttpFetcher(cache_dir=args.cache)
    )
    opts = IndexOptions(
        bbox=site_bbox(args.site),
        margin_m=args.margin_m,
        sols=sols,
        per_stop=args.per_stop,
        max_images=args.max_images,
        thumbs=not args.no_thumbs,
    )
    result = build_index(
        fetcher,
        opts,
        waypoints_url=args.waypoints_url,
        raw_url=args.raw_url,
        log=lambda m: print(m, file=sys.stderr),
    )
    out = args.work / args.site
    (out / "vector").mkdir(parents=True, exist_ok=True)
    (out / "layers").mkdir(parents=True, exist_ok=True)
    (out / "vector" / "ground_images.geojson").write_text(
        result.images.model_dump_json(indent=1), encoding="utf-8"
    )
    (out / "vector" / "rover_traverse.geojson").write_text(
        result.traverse.model_dump_json(indent=1), encoding="utf-8"
    )
    if result.thumbs:
        (out / "thumbs").mkdir(exist_ok=True)
        for name, data in result.thumbs.items():
            (out / "thumbs" / name).write_bytes(data)
    (out / "layers" / "ground_images.json").write_text(
        json.dumps(
            provenance(
                "Mastcam-Z, Navcam",
                args.raw_url,
                "images brutes du JPL, placées à la position du rover au sol de prise de vue",
            ),
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    (out / "layers" / "rover_traverse.json").write_text(
        json.dumps(
            provenance("Localisation du rover", args.waypoints_url, "arrêts publiés par le JPL"),
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    report = "\n".join(f"- {line}" for line in result.report)
    (out / "ground_images_report.md").write_text(
        f"# Images au sol de {args.site}\n\nGénéré le {stamp}.\n\n{report}\n", encoding="utf-8"
    )
    print(report)
    n = len(result.images.features)
    if n < 20:
        print(f"Attention : {n} images positionnées, l'acceptation de G1 en demande 20.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
