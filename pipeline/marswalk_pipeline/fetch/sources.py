"""Lecture de `config/sites/<site_id>/sources.yaml` (D0)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_ROOT = Path("config/sites")


@dataclass(frozen=True)
class FileSpec:
    url: str
    size: int = 0


@dataclass(frozen=True)
class Listing:
    url: str
    pattern: str
    recursive: bool = False
    dir_pattern: str = ""


@dataclass(frozen=True)
class Product:
    id: str
    product: str
    pds_id: str
    layer: str
    priority: str
    clip: bool
    margin_m: float
    files: list[FileSpec] = field(default_factory=list)
    listing: Listing | None = None
    license: str = ""
    citation: str = ""


@dataclass(frozen=True)
class Extent:
    lon: float
    lat: float
    size_m: float
    margin_m: float
    radius_m: float

    def bounds(self, margin_m: float | None = None) -> tuple[float, float, float, float]:
        """Emprise (ouest, sud, est, nord) en degrés planétocentriques, marge comprise."""
        half = self.size_m / 2 + (self.margin_m if margin_m is None else margin_m)
        dlat = math.degrees(half / self.radius_m)
        dlon = dlat / math.cos(math.radians(self.lat))
        return (self.lon - dlon, self.lat - dlat, self.lon + dlon, self.lat + dlat)


@dataclass(frozen=True)
class Sources:
    site_id: str
    extent: Extent
    products: list[Product]

    def get(self, product_id: str) -> Product:
        for p in self.products:
            if p.id == product_id:
                return p
        raise KeyError(f"produit inconnu : {product_id}")


def load_sources(site_id: str, config_root: Path = DEFAULT_CONFIG_ROOT) -> Sources:
    path = config_root / site_id / "sources.yaml"
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    ext = raw["extent"]
    extent = Extent(
        lon=float(ext["center"]["lon"]),
        lat=float(ext["center"]["lat"]),
        size_m=float(ext["size_m"]),
        margin_m=float(ext.get("margin_m", 1000)),
        radius_m=float(raw.get("mars_radius_m", 3396190)),
    )
    products: list[Product] = []
    for p in raw["products"]:
        listing = p.get("listing")
        products.append(
            Product(
                id=p["id"],
                product=p["product"],
                pds_id=str(p.get("pds_id", "")),
                layer=p["layer"],
                priority=p["priority"],
                clip=bool(p.get("clip", False)),
                margin_m=float(p.get("margin_m", extent.margin_m)),
                files=[FileSpec(f["url"], int(f.get("size", 0))) for f in p.get("files", [])],
                listing=Listing(
                    listing["url"],
                    listing["pattern"],
                    bool(listing.get("recursive")),
                    listing.get("dir_pattern", ""),
                )
                if listing
                else None,
                license=p.get("license", ""),
                citation=p.get("citation", ""),
            )
        )
    return Sources(raw["site_id"], extent, products)
