"""Sites, manifestes, préréglages et couches vectorielles.

Architecture SOLID : le routeur délègue les opérations métier au service
`ISiteCatalogService` (module `site_layers`).
"""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.services.site_layers.deps import SiteCatalogDep
from marswalk_core.schemas import DisplayPreset, FeatureCollection, SiteManifest, SiteSummary

router = APIRouter(tags=["sites"])


@router.get("/api/sites", response_model=list[SiteSummary])
def list_sites(catalog: SiteCatalogDep) -> list[SiteSummary]:
    """Liste les résumés de tous les sites disponibles."""
    return catalog.list_sites()


@router.get("/api/sites/{site_id}", response_model=SiteManifest)
def get_site_manifest(site_id: str, catalog: SiteCatalogDep) -> SiteManifest:
    """Récupère le manifeste complet d'un site."""
    return catalog.get_site_manifest(site_id)


@router.get("/api/presets", response_model=list[DisplayPreset])
def list_presets(catalog: SiteCatalogDep) -> list[DisplayPreset]:
    """Liste les préréglages d'affichage disponibles pour la carte."""
    return catalog.list_presets()


@router.get("/api/sites/{site_id}/vector/{layer_id}", response_model=FeatureCollection)
def get_vector_layer(site_id: str, layer_id: str, catalog: SiteCatalogDep) -> FeatureCollection:
    """Récupère une couche vectorielle GeoJSON (ex: traverse de rover)."""
    return catalog.get_vector_layer(site_id, layer_id)
