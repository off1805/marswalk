"""Images au sol (G1, EF-09) : index du paquet de site, produit par le pipeline de G1."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import SiteDep
from marswalk_core.schemas import FeatureCollection

router = APIRouter(tags=["ground-images"])


@router.get("/api/sites/{site_id}/ground-images", response_model=FeatureCollection)
def list_ground_images(site: SiteDep) -> FeatureCollection:
    # Chaque image : sol, instrument, caméra, identifiant, vignette et lien vers l'image
    # complète, placée à la position du rover au sol de prise de vue. Vide si le paquet
    # n'a pas encore d'images au sol.
    info = next((i for i in site.manifest.layers if i.id == "ground_images"), None)
    path = site.root / info.vector if info and info.vector else None
    if path is None or not path.is_file():
        return FeatureCollection()
    return FeatureCollection.model_validate_json(path.read_text(encoding="utf-8"))
