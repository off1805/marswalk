"""Sources de données pour site_layers (SOLID - LSP).

Fournit :
1. PackageSiteDataSource : Source lisant les paquets locaux existants (ex: fixtures/sites/fictif).
2. MockSiteDataSource : Source de données mockée en mémoire / exemples pour tests et découplage
   lorsque les paquets réels ne sont pas encore téléchargés.
"""

from __future__ import annotations

from pathlib import Path

from marswalk_core.paths import repo_root
from marswalk_core.schemas import SiteManifest
from marswalk_core.site_package import Site, load_site
from marswalk_api.services.site_layers.interfaces import ISiteDataSource


class PackageSiteDataSource(ISiteDataSource):
    """Source de données s'appuyant sur les paquets de sites locaux (marswalk_core.site_package)."""

    def _get_site(self, site_id: str) -> Site:
        return load_site(site_id)

    def get_manifest(self, site_id: str) -> SiteManifest:
        return self._get_site(site_id).manifest

    def sample_layer(self, site_id: str, layer_id: str, lon: float, lat: float) -> float | None:
        site = self._get_site(site_id)
        return site.sample(layer_id, lon, lat)

    def get_tile_file(self, site_id: str, layer_id: str, z: int, x: int, y: int, ext: str) -> Path | None:
        site = self._get_site(site_id)
        tile_path = site.root / "tiles" / layer_id / str(z) / str(x) / f"{y}.{ext}"
        if tile_path.is_file():
            return tile_path
        return None

    def get_vector_geojson(self, site_id: str, layer_id: str) -> str | None:
        site = self._get_site(site_id)
        info = site.layer(layer_id)
        if not info.vector:
            return None
        vec_file = site.root / info.vector
        if vec_file.is_file():
            return vec_file.read_text(encoding="utf-8")
        return None

    def contains_point(self, site_id: str, lon: float, lat: float) -> bool:
        site = self._get_site(site_id)
        return site.contains(lon, lat)


class MockSiteDataSource(ISiteDataSource):
    """Source de données mockée en mémoire, utilisable sans dépendance rasterio ou disque."""

    def __init__(self, manifest: SiteManifest | None = None) -> None:
        self._manifest = manifest
        if self._manifest is None:
            example_file = repo_root() / "contracts" / "examples" / "site_manifest.json"
            if example_file.is_file():
                self._manifest = SiteManifest.model_validate_json(example_file.read_text(encoding="utf-8"))

    def get_manifest(self, site_id: str) -> SiteManifest:
        if self._manifest and self._manifest.site_id == site_id:
            return self._manifest
        raise FileNotFoundError(f"Site inconnu : {site_id}")

    def sample_layer(self, site_id: str, layer_id: str, lon: float, lat: float) -> float | None:
        if layer_id == "slope":
            return 8.5
        elif layer_id == "roughness":
            return 0.25
        elif layer_id == "dem":
            return -2500.0
        elif layer_id == "thermal_inertia":
            return 320.0
        elif layer_id == "crism_minerals":
            return 1.0
        elif layer_id == "obstacles":
            return 0.0
        elif layer_id == "scarps":
            return 0.0
        elif layer_id == "radio_coverage":
            return 1.0
        elif layer_id == "loose_soil":
            return 1.0
        elif layer_id == "illumination":
            return 0.95
        return 128.0

    def get_tile_file(self, site_id: str, layer_id: str, z: int, x: int, y: int, ext: str) -> Path | None:
        return None

    def get_vector_geojson(self, site_id: str, layer_id: str) -> str | None:
        example_file = repo_root() / "contracts" / "examples" / "ground_images.json"
        if example_file.is_file():
            return example_file.read_text(encoding="utf-8")
        return None

    def contains_point(self, site_id: str, lon: float, lat: float) -> bool:
        if not self._manifest:
            return True
        west, south, east, north = self._manifest.bbox
        return west <= lon <= east and south <= lat <= north
