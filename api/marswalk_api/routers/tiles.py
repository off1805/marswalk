"""Tuiles statiques.

Architecture SOLID : le routeur délègue la résolution et validation des tuiles
au service `ITileService` (module `site_layers`).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from marswalk_api.services.site_layers.deps import TileDep

router = APIRouter(tags=["tiles"])

MEDIA = {"webp": "image/webp", "png": "image/png"}


@router.get(
    "/tiles/{site_id}/{layer_id}/{z}/{x}/{y}.{ext}",
    response_class=FileResponse,
    responses={200: {"content": {"image/webp": {}, "image/png": {}}}, 404: {}},
)
def get_tile(
    layer_id: str,
    z: int,
    x: int,
    y: int,
    ext: str,
    site_id: str,
    tile_service: TileDep,
) -> FileResponse:
    path = tile_service.get_tile(site_id=site_id, layer_id=layer_id, z=z, x=x, y=y, ext=ext)
    return FileResponse(
        path,
        media_type=MEDIA[ext],
        headers={"Cache-Control": "public, max-age=86400"},
    )
