"""Interfaces et protocoles pour le package conditions (SOLID - ISP & DIP).

Définit :
- ConditionsProvider : Protocole gelé pour la fourniture des conditions météo et radiatives.
- IMedaRadSource : Abstraction des données historiques MEDA et RAD (Jezero / Gale).
- ISpaceWeatherSource : Abstraction des flux météo spatiale (DONKI).
- ICacheStore : Abstraction de la persistance locale de cache pour le mode hors ligne.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from marswalk_core.schemas import Conditions, SpaceWeather


@runtime_checkable
class ConditionsProvider(Protocol):
    """Interface gelée fournissant les conditions environnementales actuelles et prévues."""

    def current(self, utc: datetime) -> Conditions:
        """Retourne les conditions martiennes à l'instant UTC spécifié."""
        ...

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        """Retourne la liste des prévisions horaires pour les N prochaines heures."""
        ...


@runtime_checkable
class IMedaRadSource(Protocol):
    """Source de données météorologiques MEDA et radiatives RAD (réelles ou mock)."""

    def get_measurements(
        self,
        sol: int,
        lmst_hours: float,
        utc: datetime,
    ) -> Conditions | None:
        """Retourne les mesures pour un sol et une heure solaire donnés, ou None."""
        ...


@runtime_checkable
class ISpaceWeatherSource(Protocol):
    """Client météo spatiale (DONKI)."""

    def fetch_current(self) -> SpaceWeather:
        """Récupère l'état actuel de la météo spatiale (ou lève une exception réseau)."""
        ...


@runtime_checkable
class ICacheStore(Protocol):
    """Stockage persistant local pour la météo spatiale en mode hors ligne."""

    def get(self) -> tuple[SpaceWeather, datetime] | None:
        """Retourne le dernier enregistrement en cache (SpaceWeather, cached_at)."""
        ...

    def set(self, data: SpaceWeather, cached_at: datetime) -> None:
        """Enregistre un état météo spatiale avec son horodatage."""
        ...
