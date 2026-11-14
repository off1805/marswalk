"""Sites, manifestes, préréglages et couches vectorielles (A1). Bouchon T00 : lecture directe."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from marswalk_api.deps import SiteDep
from marswalk_core.config import load_display_presets
from marswalk_core.paths import list_package_ids
from marswalk_core.schemas import DisplayPreset, FeatureCollection, SiteManifest, SiteSummary
from marswalk_core.site_package import load_site

router = APIRouter(tags=["sites"])


@router.get("/api/sites", response_model=list[SiteSummary])
def list_sites() -> list[SiteSummary]:
    out: list[SiteSummary] = []
    for site_id in list_package_ids():
        m = load_site(site_id).manifest
        out.append(SiteSummary(site_id=m.site_id, name=m.name, bbox=m.bbox, habitat=m.habitat))
    return out


@router.get("/api/sites/{site_id}", response_model=SiteManifest)
def get_site_manifest(site: SiteDep) -> SiteManifest:
    return site.manifest


@router.get("/api/presets", response_model=list[DisplayPreset])
def list_presets() -> list[DisplayPreset]:
    return load_display_presets()


@router.get("/api/sites/{site_id}/vector/{layer_id}", response_model=FeatureCollection)
def get_vector_layer(site: SiteDep, layer_id: str) -> FeatureCollection:
    try:
        info = site.layer(layer_id)
    except LookupError as exc:
        raise HTTPException(404, f"Couche inconnue : {layer_id}") from exc
    if not info.vector:
        raise HTTPException(404, f"Couche non vectorielle : {layer_id}")
    return FeatureCollection.model_validate_json((site.root / info.vector).read_text())
