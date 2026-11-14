"""Dépendances partagées de l'API (T00) : réglages, site, base de données, exemples."""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.orm import Session

from marswalk_core.paths import repo_root
from marswalk_core.site_package import Site, load_site


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MARSWALK_", env_file=".env", extra="ignore")

    database_url: str | None = None
    """URL SQLAlchemy de PostGIS, par ex. postgresql+psycopg://marswalk:marswalk@db:5432/marswalk.
    Sans valeur, l'API tourne sans base (bouchons et tests)."""
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    default_site: str = "fictif"


@cache
def get_settings() -> Settings:
    return Settings()


def get_site(site_id: str) -> Site:
    """Paquet du site demandé, ou 404 avec un message clair."""
    try:
        return load_site(site_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Site inconnu : {site_id}") from exc


SiteDep = Annotated[Site, Depends(get_site)]


def get_db() -> Iterator[Session | None]:
    """Session SQLAlchemy, ou None si ``MARSWALK_DATABASE_URL`` n'est pas défini."""
    from marswalk_api.db.session import get_sessionmaker

    maker = get_sessionmaker()
    if maker is None:
        yield None
        return
    with maker() as session:
        yield session


DbDep = Annotated[Session | None, Depends(get_db)]


def examples_dir() -> Path:
    return repo_root() / "contracts" / "examples"


@cache
def _example_text(name: str) -> str:
    return (examples_dir() / f"{name}.json").read_text(encoding="utf-8")


def load_example(name: str) -> Any:
    """Exemple versionné ``contracts/examples/<name>.json`` (réponse des bouchons)."""
    return json.loads(_example_text(name))
