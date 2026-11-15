"""Conditions à Jezero : mesures MEDA importées, climatologie MEDA, et modèle de repli.

Ordre de priorité pour chaque grandeur, à l'heure solaire locale (LMST) demandée :

1. ``sol`` : la mesure MEDA du sol rejoué (moyenne sur 30 min), si elle existe ;
2. ``climatologie`` : la moyenne MEDA de cette tranche horaire sur tous les sols importés ;
3. ``modèle`` : un cycle diurne analytique, utilisé seulement sans données importées.

La source de chaque grandeur est écrite dans ``Conditions.source`` : on ne présente jamais
une valeur modélisée comme une mesure. L'indice UV et l'opacité de la poussière restent
modélisés (les produits MEDA calibrés de D0 ne les donnent pas directement).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Literal

from marswalk_conditions.dataset import (
    FIELDS,
    Q_GCR,
    ConditionsDataset,
    bin_index,
    load_default,
)
from marswalk_core.marstime import mars_time
from marswalk_core.schemas import Conditions, SpaceWeather

ConditionsMode = Literal["historical", "scenario", "live", "constant"]
Basis = Literal["sol", "climatology"]

# Coordonnées du cratère Jezero
JEZERO_LON_EAST = 77.58
JEZERO_LAT_DEG = 18.38
DEFAULT_EPOCH_UTC = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)

# Fond RAD (détecteur E) mesuré à Gale avant l'événement de mai 2024 par l'import K1 ;
# sert quand aucune série RAD n'est importée.
FALLBACK_BASELINE_E_UGY_H = 5.3
DUST_TAU_MODEL = 0.55

LABELS = {"temperature_c": "T", "pressure_pa": "P", "wind_mps": "vent"}


def model_value(name: str, lmst_h: float) -> float:
    """Cycle diurne analytique de repli (ordres de grandeur MEDA, saison du lot de D0)."""
    if name == "temperature_c":
        return -46.5 + 28.5 * math.cos((lmst_h - 14.0) * (2.0 * math.pi / 24.0))
    if name == "pressure_pa":
        p1 = math.cos((lmst_h - 7.0) * (2.0 * math.pi / 24.0))
        p2 = math.cos((lmst_h - 10.0) * (4.0 * math.pi / 24.0))
        return 750.0 + 12.0 * p1 + 6.0 * p2
    return max(1.5, 5.5 + 4.5 * math.cos((lmst_h - 15.0) * (2.0 * math.pi / 24.0)))


def model_uv(lmst_h: float) -> float:
    if 6.0 <= lmst_h <= 18.0:
        return round(max(0.0, 7.5 * math.sin(math.pi * (lmst_h - 6.0) / 12.0)), 1)
    return 0.0


class MedaClimatologyEngine:
    """Conditions martiennes de Jezero à un instant UTC, à partir du jeu MEDA importé."""

    def __init__(
        self,
        lon_east: float = JEZERO_LON_EAST,
        lat_deg: float = JEZERO_LAT_DEG,
        epoch_utc: datetime = DEFAULT_EPOCH_UTC,
        dataset: ConditionsDataset | None = None,
        use_default_dataset: bool = True,
    ) -> None:
        self.lon_east = lon_east
        self.lat_deg = lat_deg
        self.epoch_utc = epoch_utc
        self._dataset = dataset
        self._use_default = dataset is None and use_default_dataset

    @property
    def dataset(self) -> ConditionsDataset | None:
        if self._dataset is not None:
            return self._dataset
        return load_default() if self._use_default else None

    def baseline_dose_usv_h(self) -> float:
        ds = self.dataset
        base = ds.rad.baseline_e_ugy_h if ds and ds.rad else FALLBACK_BASELINE_E_UGY_H
        return Q_GCR * base

    def _values(
        self, mission_sol: int, lmst_h: float, basis: Basis
    ) -> tuple[dict[str, float], str]:
        ds = self.dataset
        idx = bin_index(lmst_h)
        meda_sol = ds.meda_sol_for(mission_sol) if ds and basis == "sol" else None
        values: dict[str, float] = {}
        origin: dict[str, str] = {}
        for name in FIELDS:
            v: float | None = None
            if ds and meda_sol is not None:
                v = ds.meda[meda_sol].value(name, idx)
                if v is not None:
                    origin[name] = f"sol {meda_sol}"
            if v is None and ds:
                v = ds.climatology(name, idx)
                if v is not None:
                    origin[name] = "climatologie"
            if v is None:
                v = model_value(name, lmst_h)
                origin[name] = "modèle"
            values[name] = v
        if all(o == "modèle" for o in origin.values()):
            note = "modèle diurne (aucune donnée MEDA importée)"
        else:
            parts = [f"{LABELS[n]} : {origin[n]}" for n in FIELDS]
            note = "MEDA Perseverance (" + ", ".join(parts) + ")"
        return values, note

    def compute_conditions(
        self,
        utc: datetime,
        mode: ConditionsMode = "historical",
        dose_rate_override: float | None = None,
        space_weather_override: SpaceWeather | None = None,
        source_note: str | None = None,
        cached_at: datetime | None = None,
        basis: Basis = "sol",
    ) -> Conditions:
        """Conditions complètes à un instant UTC.

        ``basis="sol"`` rejoue le sol MEDA correspondant (mode historique) ;
        ``basis="climatology"`` donne la moyenne horaire (prévisions).
        """
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)
        mtime = mars_time(utc, self.lon_east, self.epoch_utc)
        values, meda_note = self._values(mtime.sol, mtime.lmst_hours, basis)
        dose = dose_rate_override if dose_rate_override is not None else self.baseline_dose_usv_h()
        notes = [n for n in (source_note, meda_note) if n]
        notes.append("UV et poussière : modèle")
        return Conditions(
            utc=utc,
            sol=mtime.sol,
            lmst=mtime.lmst,
            mode=mode,
            temperature_c=round(values["temperature_c"], 1),
            pressure_pa=round(values["pressure_pa"], 1),
            wind_mps=round(values["wind_mps"], 1),
            dust_tau=DUST_TAU_MODEL,
            uv_index=model_uv(mtime.lmst_hours),
            dose_rate_usv_h=round(dose, 2),
            space_weather=space_weather_override or SpaceWeather(),
            source=" ; ".join(notes),
            cached_at=cached_at,
        )
