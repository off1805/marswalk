"""Modèle climatologique martien pour le cratère Jezero (MEDA climatology).

Fournit des estimations déterministes et réalistes des variations diurnes
(température, pression, vent, UV, opacité atmosphérique et rayonnement de fond).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from marswalk_core.marstime import mars_time
from marswalk_core.schemas import Conditions, SpaceWeather

# Coordonnées du cratère Jezero
JEZERO_LON_EAST = 77.58
JEZERO_LAT_DEG = 18.38
DEFAULT_EPOCH_UTC = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)


class MedaClimatologyEngine:
    """Moteur de calcul de la climatologie locale de Jezero (inspiré des mesures MEDA)."""

    def __init__(
        self,
        lon_east: float = JEZERO_LON_EAST,
        lat_deg: float = JEZERO_LAT_DEG,
        epoch_utc: datetime = DEFAULT_EPOCH_UTC,
    ) -> None:
        self.lon_east = lon_east
        self.lat_deg = lat_deg
        self.epoch_utc = epoch_utc

    def compute_conditions(
        self,
        utc: datetime,
        mode: str = "historical",
        dose_rate_override: float | None = None,
        space_weather_override: SpaceWeather | None = None,
        source_note: str = "Climatologie MEDA Jezero",
        cached_at: datetime | None = None,
    ) -> Conditions:
        """Calcule les conditions martiennes complètes à un instant UTC."""
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)

        mtime = mars_time(utc, self.lon_east, self.epoch_utc)
        lmst_h = mtime.lmst_hours

        # 1. Température de l'air (°C) : cycle diurne quasi-sinusoïdal
        # Minima à l'aube (~05:30 LMST : -75°C), Maxima en début d'après-midi (~14:00 LMST : -18°C)
        t_phase = (lmst_h - 14.0) * (2.0 * math.pi / 24.0)
        temp_c = -46.5 + 28.5 * math.cos(t_phase)

        # 2. Pression atmosphérique (Pa) : marée thermique semi-diurne (onde diurne + semi-diurne)
        # Moyenne ~840 Pa, amplitude diurne ~35 Pa
        p_phase1 = (lmst_h - 7.0) * (2.0 * math.pi / 24.0)
        p_phase2 = (lmst_h - 10.0) * (4.0 * math.pi / 24.0)
        pressure_pa = 845.0 + 20.0 * math.cos(p_phase1) + 15.0 * math.cos(p_phase2)

        # 3. Vent (m/s) : calme nocturne (~2 m/s), rafales et thermiques l'après-midi (~8 à 11 m/s)
        wind_phase = (lmst_h - 15.0) * (2.0 * math.pi / 24.0)
        wind_mps = max(1.5, 5.5 + 4.5 * math.cos(wind_phase))

        # 4. Indice UV : dépend de l'élévation du Soleil au-dessus de l'horizon
        # Hauteur solaire approximée pour Jezero (18.4°N)
        # Soleil au-dessus de l'horizon entre ~06:00 et ~18:00 LMST
        if 6.0 <= lmst_h <= 18.0:
            solar_elevation = math.sin(math.pi * (lmst_h - 6.0) / 12.0)
            uv_index = round(max(0.0, 7.5 * solar_elevation), 1)
        else:
            uv_index = 0.0

        # 5. Opacité de la poussière (tau) : baseline de saison normale à Jezero
        dust_tau = 0.55

        # 6. Débit de dose radiative (µSv/h) : fond cosmique galactique au sol martien
        dose_rate = dose_rate_override if dose_rate_override is not None else 10.0

        space_weather = space_weather_override if space_weather_override is not None else SpaceWeather()

        return Conditions(
            utc=utc,
            sol=mtime.sol,
            lmst=mtime.lmst,
            mode=mode,  # type: ignore[arg-type]
            temperature_c=round(temp_c, 1),
            pressure_pa=round(pressure_pa, 1),
            wind_mps=round(wind_mps, 1),
            dust_tau=round(dust_tau, 2),
            uv_index=uv_index,
            dose_rate_usv_h=round(dose_rate, 2),
            space_weather=space_weather,
            source=source_note,
            cached_at=cached_at,
        )
