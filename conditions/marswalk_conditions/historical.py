"""Fournisseur de conditions historiques (MEDA / RAD).

- ``current`` rejoue le sol MEDA importé correspondant au sol de mission (les sols importés
  tournent en boucle), à l'heure solaire locale de Jezero, avec le fond de dose RAD.
- ``forecast`` donne la climatologie MEDA : moyenne de chaque demi-heure locale sur tous les
  sols importés.

Sans jeu importé (``python -m marswalk_conditions import``), le repli est un modèle diurne,
et ``Conditions.source`` le dit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from marswalk_conditions.climatology import MedaClimatologyEngine
from marswalk_conditions.dataset import ConditionsDataset
from marswalk_conditions.interfaces import ConditionsProvider, IMedaRadSource
from marswalk_core.schemas import Conditions


class PdsMedaRadSource(IMedaRadSource):
    """Mesures MEDA et RAD importées depuis le PDS (jeu compact de ``dataset.py``)."""

    def __init__(self, climatology: MedaClimatologyEngine | None = None) -> None:
        self._climatology = climatology or MedaClimatologyEngine()

    def get_measurements(
        self,
        sol: int,
        lmst_hours: float,
        utc: datetime,
    ) -> Conditions | None:
        ds = self._climatology.dataset
        if ds is None or not ds.meda:
            return None
        return self._climatology.compute_conditions(utc=utc, mode="historical", basis="sol")


class HistoricalProvider(ConditionsProvider):
    """Fournisseur de conditions environnementales en mode rejeu historique."""

    def __init__(
        self,
        source: IMedaRadSource | None = None,
        climatology: MedaClimatologyEngine | None = None,
        dataset: ConditionsDataset | None = None,
    ) -> None:
        self._climatology = climatology or MedaClimatologyEngine(dataset=dataset)
        self._source = source or PdsMedaRadSource(self._climatology)

    def current(self, utc: datetime) -> Conditions:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)
        result = self._source.get_measurements(0, 0.0, utc)
        if result is not None:
            return result
        return self._climatology.compute_conditions(utc=utc, mode="historical")

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        """Prévision horaire pour les N prochaines heures : climatologie MEDA."""
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)
        return [
            self._climatology.compute_conditions(
                utc=utc + timedelta(hours=h),
                mode="historical",
                source_note="Prévision climatologique",
                basis="climatology",
            )
            for h in range(hours)
        ]
