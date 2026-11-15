"""Interfaces et contrats pour le service mission_planning (SOLID - ISP & DIP).

Définit les interfaces de persistance (Repository Pattern) et de calcul pour :
- Les cibles scientifiques et waypoints
- Les plans de sortie et recherche d'itinéraires
- Les zones à risques (hazards) et seuils de sécurité
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from marswalk_core.schemas import (
    FeatureCollection,
    Plan,
    PlanCreate,
    PlanUpdate,
    SafetySettings,
    Target,
    TargetCreate,
    TargetUpdate,
)


class ITargetRepository(ABC):
    """Interface de persistance des cibles (CRUD).

    Cette interface sera implémentée par PostGISTargetRepository lorsque la base
    PostGIS sera raccordée, et par InMemoryTargetRepository pour le mock / mode autonome.
    """

    @abstractmethod
    def list_by_site(self, site_id: str) -> list[Target]:
        """Retourne la liste des cibles associées à un site."""
        ...

    @abstractmethod
    def get(self, target_id: str) -> Target | None:
        """Récupère une cible par son identifiant."""
        ...

    @abstractmethod
    def create(self, site_id: str, data: TargetCreate) -> Target:
        """Crée une nouvelle cible sur un site."""
        ...

    @abstractmethod
    def update(self, target_id: str, data: TargetUpdate) -> Target | None:
        """Met à jour partiellement une cible existante."""
        ...

    @abstractmethod
    def delete(self, target_id: str) -> bool:
        """Supprime une cible par son identifiant. Retourne True si supprimée."""
        ...


class IPlanRepository(ABC):
    """Interface de persistance des plans de mission et variantes."""

    @abstractmethod
    def get(self, plan_id: str) -> Plan | None:
        """Récupère un plan par son identifiant."""
        ...

    @abstractmethod
    def save(self, plan: Plan) -> Plan:
        """Sauvegarde un plan complet."""
        ...

    @abstractmethod
    def update(self, plan_id: str, data: PlanUpdate) -> Plan | None:
        """Met à jour un plan (ex: choix de la variante active)."""
        ...


class ISafetySettingsRepository(ABC):
    """Interface de persistance des réglages de sécurité et seuils par site."""

    @abstractmethod
    def get(self, site_id: str) -> SafetySettings:
        """Récupère les réglages de sécurité courants d'un site."""
        ...

    @abstractmethod
    def save(self, site_id: str, settings: SafetySettings) -> SafetySettings:
        """Enregistre de nouveaux réglages de sécurité pour un site."""
        ...


class IHazardService(ABC):
    """Interface de calcul des zones de danger et polygones de risque."""

    @abstractmethod
    def get_hazard_polygons(self, site_id: str, preset: str | None = None) -> FeatureCollection:
        """Calcule et renvoie les polygones de zones interdites et pénalisées."""
        ...


class IPlanComputationService(ABC):
    """Interface de calcul et d'optimisation d'itinéraires pour un plan."""

    @abstractmethod
    def compute_plan(self, site_id: str, plan_create: PlanCreate) -> Plan:
        """Calcule un plan multi-variantes conforme aux exigences EF-05 & EF-06."""
        ...
