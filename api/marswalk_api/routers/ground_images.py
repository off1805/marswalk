"""Images au sol (G1, EF-09). Bouchon T00 : exemple versionné."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import SiteDep, load_example
from marswalk_core.schemas import FeatureCollection

router = APIRouter(tags=["ground-images"])


@router.get("/api/sites/{site_id}/ground-images", response_model=FeatureCollection)
def list_ground_images(site: SiteDep) -> FeatureCollection:
    return FeatureCollection.model_validate(load_example("ground_images"))
