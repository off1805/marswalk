"""Fournisseurs de dépendances FastAPI pour site_layers (SOLID - DIP)."""

from __future__ import annotations

from functools import cache
from typing import Annotated

from fastapi import Depends

from marswalk_api.services.site_layers.data_source import PackageSiteDataSource
from marswalk_api.services.site_layers.interfaces import (
    IPointQueryService,
    ISiteCatalogService,
    ISiteDataSource,
    ITileService,
)
from marswalk_api.services.site_layers.services import (
    PointQueryService,
    SiteCatalogService,
    TileService,
)


@cache
def get_site_data_source() -> ISiteDataSource:
    return PackageSiteDataSource()


def get_site_catalog_service(
    data_source: Annotated[ISiteDataSource, Depends(get_site_data_source)],
) -> ISiteCatalogService:
    return SiteCatalogService(data_source)


def get_point_query_service(
    data_source: Annotated[ISiteDataSource, Depends(get_site_data_source)],
) -> IPointQueryService:
    return PointQueryService(data_source)


def get_tile_service(
    data_source: Annotated[ISiteDataSource, Depends(get_site_data_source)],
) -> ITileService:
    return TileService(data_source)


SiteCatalogDep = Annotated[ISiteCatalogService, Depends(get_site_catalog_service)]
PointQueryDep = Annotated[IPointQueryService, Depends(get_point_query_service)]
TileDep = Annotated[ITileService, Depends(get_tile_service)]
