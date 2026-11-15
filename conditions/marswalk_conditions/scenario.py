"""Moteur de rejeu de scénarios martiens (K1).

Le scénario ``solar-event`` rejoue l'événement à particules solaires du 20 mai 2024 mesuré au
sol de Gale par RAD (Curiosity), transposé à Jezero (Perseverance n'emporte pas de RAD).

Chronologie, en secondes de scénario (``duration_s`` = 3 600) :

- 0 à 1 200 s : conditions calmes, fond cosmique ;
- 1 200 s : début de l'événement (premier relevé RAD au-dessus de deux fois le fond) ;
- pic quelques dizaines de secondes plus tard, à l'instant donné par l'événement ``peak``
  du catalogue (calculé depuis la série importée) ;
- décroissance jusqu'à 3 600 s.

Une seconde de scénario vaut ``REAL_S_PER_SCENARIO_S`` secondes réelles : le scénario couvre
18 h avant le début et 36 h après. La vitesse de rejeu de A3 s'ajoute à cette compression.

Sans série RAD importée, un profil de repli reprend les ordres de grandeur mesurés (fond,
pic, décroissance) et ``Conditions.source`` le dit.
"""

from __future__ import annotations

import math
import threading
from datetime import UTC, datetime, timedelta

from marswalk_conditions.climatology import FALLBACK_BASELINE_E_UGY_H, MedaClimatologyEngine
from marswalk_conditions.dataset import (
    ConditionsDataset,
    RadSeries,
    equivalent_dose_usv_h,
    load_default,
)
from marswalk_conditions.interfaces import ConditionsProvider
from marswalk_core.schemas import (
    Conditions,
    Scenario,
    ScenarioEvent,
    ScenarioState,
    SpaceWeather,
    SpaceWeatherLevel,
)

SCENARIO_ID = "solar-event"
DURATION_S = 3600.0
ONSET_AT_S = 1200.0
REAL_S_PER_SCENARIO_S = 54.0

# Profil de repli, d'après la série RAD (détecteur E) du 20 mai 2024 lue par l'import K1 :
# premier relevé élevé vers 60 µGy/h, pic d'environ 350 µGy/h une demi-heure plus tard,
# puis décroissance sur environ 6 h.
FALLBACK_ONSET_E_UGY_H = 60.0
FALLBACK_PEAK_E_UGY_H = 350.0
FALLBACK_RISE_REAL_S = 0.6 * 3600.0
FALLBACK_DECAY_REAL_S = 6.0 * 3600.0
FALLBACK_PEAK_AT_S = ONSET_AT_S + FALLBACK_RISE_REAL_S / REAL_S_PER_SCENARIO_S


def _level(ratio: float) -> SpaceWeatherLevel:
    if ratio >= 10.0:
        return SpaceWeatherLevel.storm
    if ratio >= 3.0:
        return SpaceWeatherLevel.warning
    if ratio >= 1.5:
        return SpaceWeatherLevel.watch
    return SpaceWeatherLevel.quiet


def real_utc_at(rad: RadSeries, t_s: float) -> datetime:
    """Instant réel de la série RAD rejoué à ``t_s`` secondes de scénario."""
    return rad.onset_utc + timedelta(seconds=(t_s - ONSET_AT_S) * REAL_S_PER_SCENARIO_S)


def scenario_t_of(rad: RadSeries, real: datetime) -> float:
    return ONSET_AT_S + (real - rad.onset_utc).total_seconds() / REAL_S_PER_SCENARIO_S


def _fallback_dose_e(t_s: float) -> float:
    base = FALLBACK_BASELINE_E_UGY_H
    if t_s < ONSET_AT_S:
        return base
    dt_real = (t_s - ONSET_AT_S) * REAL_S_PER_SCENARIO_S
    if dt_real <= FALLBACK_RISE_REAL_S:
        # Front montant : du premier relevé élevé au pic.
        f = dt_real / FALLBACK_RISE_REAL_S
        return FALLBACK_ONSET_E_UGY_H + f * (FALLBACK_PEAK_E_UGY_H - FALLBACK_ONSET_E_UGY_H)
    decay = math.exp(-(dt_real - FALLBACK_RISE_REAL_S) / FALLBACK_DECAY_REAL_S)
    return base + (FALLBACK_PEAK_E_UGY_H - base) * decay


def build_solar_event(rad: RadSeries | None) -> Scenario:
    if rad is not None:
        peak_t = round(scenario_t_of(rad, rad.peak_utc), 1)
        description = (
            "Rejeu de l'événement à particules solaires du "
            f"{rad.onset_utc:%d/%m/%Y} mesuré au sol de Gale par RAD (Curiosity), transposé "
            f"au cratère Jezero : fond {rad.baseline_e_ugy_h:.1f} µGy/h, pic "
            f"{rad.peak_e_ugy_h:.0f} µGy/h le {rad.peak_utc:%d/%m/%Y à %H:%M} UTC. "
            f"Une seconde de scénario vaut {REAL_S_PER_SCENARIO_S:.0f} s réelles."
        )
    else:
        peak_t = round(FALLBACK_PEAK_AT_S, 1)
        description = (
            "Profil de repli calé sur l'événement solaire du 20 mai 2024 vu par RAD "
            "(Curiosity, Gale), transposé au cratère Jezero ; série RAD non importée."
        )
    return Scenario(
        id=SCENARIO_ID,
        title="Éruption solaire pendant la sortie",
        description=description,
        duration_s=DURATION_S,
        events=[
            ScenarioEvent(t_s=0.0, kind="start", description="Conditions calmes"),
            ScenarioEvent(
                t_s=ONSET_AT_S, kind="solar_event", description="Début de l'événement solaire"
            ),
            ScenarioEvent(t_s=peak_t, kind="peak", description="Pic de dose"),
            ScenarioEvent(t_s=DURATION_S, kind="end", description="Fin du rejeu"),
        ],
    )


# Catalogue de repli, sans série importée (gardé pour compatibilité).
SOLAR_EVENT_SCENARIO = build_solar_event(None)


class ScenarioManager:
    """État d'exécution des scénarios (singleton thread-safe).

    Deux façons de le piloter :

    - ``start()`` explicite, avec une vitesse ;
    - ancrage automatique : un fournisseur ``scenario`` interrogé alors que rien n'a été
      démarré s'ancre sur le premier instant reçu. C'est le cas de A3, qui fait avancer
      lui-même l'horloge du scénario. Un instant qui recule, ou qui dépasse la fin du
      scénario, ré-ancre (nouveau départ).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._explicit = False
        self._last_utc: datetime | None = None
        self._active_state = ScenarioState(
            scenario_id=None, running=False, started_at=None, elapsed_s=0.0, speed=1.0
        )

    def start(
        self, scenario_id: str, speed: float = 1.0, started_at: datetime | None = None
    ) -> ScenarioState:
        with self._lock:
            if scenario_id not in _catalog():
                raise ValueError(f"Scénario inconnu : {scenario_id}")
            self._explicit = True
            self._last_utc = None
            self._active_state = ScenarioState(
                scenario_id=scenario_id,
                running=True,
                started_at=started_at or datetime.now(UTC),
                elapsed_s=0.0,
                speed=max(0.1, speed),
            )
            return self._active_state

    def stop(self, scenario_id: str | None = None) -> ScenarioState:
        with self._lock:
            self._explicit = False
            self._last_utc = None
            self._active_state = self._active_state.model_copy(update={"running": False})
            return self._active_state

    def get_state(self) -> ScenarioState:
        with self._lock:
            return self._active_state

    def get_elapsed_s(self, utc: datetime) -> float:
        with self._lock:
            return self._elapsed(utc)

    def _elapsed(self, utc: datetime) -> float:
        st = self._active_state
        if not st.running or st.started_at is None:
            return st.elapsed_s
        return max(0.0, (utc - st.started_at).total_seconds() * st.speed)

    def observe(self, scenario_id: str, utc: datetime) -> float:
        """Temps écoulé à ``utc``, en s'ancrant si le scénario n'a pas été démarré."""
        with self._lock:
            st = self._active_state
            if not self._explicit:
                stale = (
                    not st.running
                    or st.scenario_id != scenario_id
                    or st.started_at is None
                    or (self._last_utc is not None and utc < self._last_utc)
                    or (utc - st.started_at).total_seconds() > DURATION_S + 60.0
                )
                if stale:
                    self._active_state = ScenarioState(
                        scenario_id=scenario_id,
                        running=True,
                        started_at=utc,
                        elapsed_s=0.0,
                        speed=1.0,
                    )
                self._last_utc = utc
            return self._elapsed(utc)


_scenario_manager = ScenarioManager()


def get_scenario_manager() -> ScenarioManager:
    return _scenario_manager


def _catalog(dataset: ConditionsDataset | None = None) -> dict[str, Scenario]:
    if dataset is None:
        dataset = load_default()
    scen = build_solar_event(dataset.rad if dataset else None)
    return {scen.id: scen}


class ScenarioProvider(ConditionsProvider):
    """Fournisseur de conditions asservi à la chronologie d'un scénario."""

    def __init__(
        self,
        scenario_id: str = SCENARIO_ID,
        manager: ScenarioManager | None = None,
        climatology: MedaClimatologyEngine | None = None,
        dataset: ConditionsDataset | None = None,
    ) -> None:
        self.scenario_id = scenario_id
        self._manager = manager or get_scenario_manager()
        self._climatology = climatology or MedaClimatologyEngine(dataset=dataset)

    def _rad(self) -> RadSeries | None:
        ds = self._climatology.dataset
        return ds.rad if ds else None

    def dose_profile(self, elapsed_s: float) -> tuple[float, SpaceWeather, str]:
        """Débit de dose équivalente (µSv/h), météo spatiale et source à ``elapsed_s``."""
        rad = self._rad()
        if rad is not None:
            base = rad.baseline_e_ugy_h
            real = real_utc_at(rad, elapsed_s)
            dose_e = rad.dose_e_at(real) if elapsed_s <= DURATION_S else base
            source = f"RAD Curiosity (Gale) du {real:%d/%m/%Y %H:%M} UTC, transposé à Jezero"
        else:
            base = FALLBACK_BASELINE_E_UGY_H
            dose_e = _fallback_dose_e(elapsed_s) if elapsed_s <= DURATION_S else base
            source = "profil de repli calé sur RAD mai 2024 (série non importée)"
        level = _level(dose_e / base)
        sw = SpaceWeather(
            level=level,
            event=(
                "Événement à particules solaires (SPE)"
                if level != SpaceWeatherLevel.quiet
                else None
            ),
            source=source,
        )
        return equivalent_dose_usv_h(dose_e, base), sw, source

    def _at(self, utc: datetime, elapsed: float) -> Conditions:
        if self.scenario_id == SCENARIO_ID:
            dose, sw, source = self.dose_profile(elapsed)
            note = f"Scénario solar-event (t={round(elapsed)} s) : {source}"
        else:
            dose, sw = self._climatology.baseline_dose_usv_h(), SpaceWeather()
            note = f"Scénario {self.scenario_id}"
        return self._climatology.compute_conditions(
            utc=utc,
            mode="scenario",
            dose_rate_override=dose,
            space_weather_override=sw,
            source_note=note,
        )

    def current(self, utc: datetime) -> Conditions:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)
        return self._at(utc, self._manager.observe(self.scenario_id, utc))

    def forecast(self, utc: datetime, hours: int) -> list[Conditions]:
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=UTC)
        elapsed0 = self._manager.observe(self.scenario_id, utc)
        state = self._manager.get_state()
        return [
            self._at(utc + timedelta(hours=h), elapsed0 + h * 3600.0 * state.speed)
            for h in range(hours)
        ]


def list_scenarios() -> list[Scenario]:
    """Scénarios disponibles (le pic de ``solar-event`` dépend de la série importée)."""
    return list(_catalog().values())
