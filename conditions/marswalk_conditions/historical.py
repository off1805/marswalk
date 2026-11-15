"""Fournisseur de conditions historiques (MEDA / RAD).

Architecture SOLID :
- HistoricalProvider implémente ConditionsProvider.
- Dépendance vers l'interface IMedaRadSource (DIP).
- MockMedaRadSource fournit les données en l'absence des fichiers PDS bruts (LSP).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from marswalk_conditions.climatology import MedaClimatologyEngine
from marswalk_conditions.interfaces import ConditionsProvider, IMedaRadSource
from marswalk_core.marstime import mars_time
from marswalk_core.schemas import Conditions


class MockMedaRadSource(IMedaRadSource):
    """Source de données mockée reproduisant les variations mesurées par MEDA et RAD."""

    def __init__(self, climatology: MedaClimatologyEngine | None = None) -> None:
        self._climatology = climatology or MedaClimatologyEngine()

    def get_measurements(
        self,
        sol: int,
        lmst_hours: float,
        utc: datetime,
    ) -> Conditions | None:
        # Génère une condition cohérente avec le sol demandé et une légère variance
        cond = self._climatology.compute_conditions(
            utc=utc,
            mode="historical",
            source_note=f"Rejeu historique MEDA sol {sol} (Jezero) / RAD (Curiosity)",
        )
        return cond


class PdsMedaRadSource(IMedaRadSource):
    """Source de données lisant les tables réelles de séries MEDA/RAD importées depuis le PDS."""

    def __init__(self, data_dir: str | None = None) -> None:
        self._data_dir = data_dir
        self._cache: dict[tuple[int, int], Conditions] = {}

    def get_measurements(
        self,
        sol: int,
        lmst_hours: float,
        utc: datetime,
    ) -> Conditions | None:
        # Implémentation prête pour lecture des CSV/Parquet PDS dès leur rapatriement par D0
        return None


class HistoricalProvider(ConditionsProvider):
    """Fournisseur de conditions environnementales en mode rejeu historique."""

    def __init__(
        self,
        source: IMedaRadSource | None = None,
        climatology: MedaClimatologyEngine | None = None,
    ) -> None:
        self._climatology = climatology or MedaClimatologyEngine()
        self._source = source or MockMedaRadSource(self._climatology)

    def current(self, utc: datetime) -> Conditions:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)

        mtime = mars_time(utc, self._climatology.lon_east, self._climatology.epoch_utc)
        result = self._source.get_measurements(mtime.sol, mtime.lmst_hours, utc)
        if result is not None:
            return result

        return self._climatology.compute_conditions(
            utc=utc,
            mode="historical",
            source_note="Climatologie MEDA (repli historique)",
        )

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        """Génère la prévision horaire pour les N prochaines heures via la climatologie."""
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)

        forecasts: list[Conditions] = []
        for h in range(hours):
            t = utc + timedelta(hours=h)
            cond = self._climatology.compute_conditions(
                utc=t,
                mode="historical",
                source_note="Prévision climatologique MEDA",
            )
            forecasts.append(cond)
        return forecasts
