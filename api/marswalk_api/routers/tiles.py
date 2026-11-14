"""Tuiles statiques (A1). Bouchon T00 : fichiers du paquet servis tels quels."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from marswalk_api.deps import SiteDep

router = APIRouter(tags=["tiles"])

MEDIA = {"webp": "image/webp", "png": "image/png"}


@router.get(
    "/tiles/{site_id}/{layer_id}/{z}/{x}/{y}.{ext}",
    response_class=FileResponse,
    responses={200: {"content": {"image/webp": {}, "image/png": {}}}, 404: {}},
)
def get_tile(site: SiteDep, layer_id: str, z: int, x: int, y: int, ext: str) -> FileResponse:
    if ext not in MEDIA or not layer_id.replace("_", "").isalnum():
        raise HTTPException(404, "Format de tuile inconnu")
    path = site.root / "tiles" / layer_id / str(z) / str(x) / f"{y}.{ext}"
    if not path.is_file():
        raise HTTPException(404, "Tuile absente")
    return FileResponse(path, media_type=MEDIA[ext], headers={"Cache-Control": "public, max-age=86400"})
