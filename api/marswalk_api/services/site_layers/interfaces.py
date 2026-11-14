"""Interfaces et contrats pour le service site_layers (SOLID - ISP & DIP).

Ce module définit les interfaces abstraites pour le catalogue de sites, l'accès
aux tuiles et l'interrogation de couches en un point géographique.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from marswalk_core.schemas import (
    DisplayPreset,
    FeatureCollection,
    PointQuery,
    SiteManifest,
    SiteSummary,
)


@runtime_checkable
class ISiteDataSource(Protocol):
    """Source de données d'un site martien (données réelles ou mock)."""

    @abstractmethod
    def get_manifest(self, site_id: str) -> SiteManifest:
        """Retourne le manifeste d'un site."""
        ...

    @abstractmethod
    def sample_layer(self, site_id: str, layer_id: str, lon: float, lat: float) -> float | None:
        """Échantillonne la valeur d'une couche au point (lon, lat)."""
        ...

    @abstractmethod
    def get_tile_file(self, site_id: str, layer_id: str, z: int, x: int, y: int, ext: str) -> Path | None:
        """Retourne le chemin d'accès au fichier de tuile s'il existe."""
        ...

    @abstractmethod
    def get_vector_geojson(self, site_id: str, layer_id: str) -> str | None:
        """Retourne le contenu GeoJSON brut d'une couche vectorielle."""
        ...

    @abstractmethod
    def contains_point(self, site_id: str, lon: float, lat: float) -> bool:
        """Vérifie si les coordonnées sont dans l'emprise du site."""
        ...


class ISiteCatalogService(ABC):
    """Service d'accès aux métadonnées des sites et configurations d'affichage."""

    @abstractmethod
    def list_sites(self) -> list[SiteSummary]:
        """Liste les résumés des sites disponibles."""
        ...

    @abstractmethod
    def get_site_manifest(self, site_id: str) -> SiteManifest:
        """Récupère le manifeste complet d'un site."""
        ...

    @abstractmethod
    def list_presets(self) -> list[DisplayPreset]:
        """Liste les préréglages d'affichage disponibles."""
        ...

    @abstractmethod
    def get_vector_layer(self, site_id: str, layer_id: str) -> FeatureCollection:
        """Récupère une couche vectorielle au format FeatureCollection GeoJSON."""
        ...


class IPointQueryService(ABC):
    """Service d'interrogation multicouche en un point planétocentrique."""

    @abstractmethod
    def query_point(self, site_id: str, lon: float, lat: float) -> PointQuery:
        """Interroge toutes les couches d'un site pour une coordonnée donnée."""
        ...


class ITileService(ABC):
    """Service de distribution des tuiles cartographiques statiques."""

    @abstractmethod
    def get_tile(self, site_id: str, layer_id: str, z: int, x: int, y: int, ext: str) -> Path:
        """Résout le chemin d'une tuile demandée avec vérification de validité."""
        ...
