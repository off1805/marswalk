"""Jeu de données compact des conditions (MEDA et RAD), produit par l'import K1.

Un seul fichier JSON de quelques centaines de kilo-octets, lu sans réseau :

- ``meda`` : moyennes par tranche de 30 min d'heure solaire locale (LMST), pour chaque sol
  MEDA importé : température de l'air (°C), pression (Pa), vent horizontal (m/s).
- ``rad`` : série du débit de dose RAD (Curiosity, Gale) autour de l'événement solaire de
  mai 2024, avec le fond, le début et le pic détectés à l'import.

Emplacement par défaut : ``data/work/conditions/jezero.json`` (hors Git, comme toutes les
données réelles), ou ``MARSWALK_CONDITIONS_FILE``.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from marswalk_core.paths import repo_root

FORMAT_VERSION = 1
BIN_MINUTES = 30
N_BINS = 24 * 60 // BIN_MINUTES
FIELDS = ("temperature_c", "pressure_pa", "wind_mps")

# Facteurs de qualité (dose absorbée en tissu vers dose équivalente).
# Fond cosmique galactique au sol de Gale : Q moyen 3,05 (Hassler et al. 2014, Science 343).
Q_GCR = 3.05
# Particules solaires, dominées par les protons : Q pris à 1 (hypothèse, dite dans le pitch).
Q_SEP = 1.0


def default_path() -> Path:
    env = os.environ.get("MARSWALK_CONDITIONS_FILE")
    if env:
        return Path(env)
    return repo_root() / "data" / "work" / "conditions" / "jezero.json"


def bin_index(lmst_hours: float) -> int:
    return int((lmst_hours % 24.0) * 60 // BIN_MINUTES) % N_BINS


def equivalent_dose_usv_h(dose_e_ugy_h: float, baseline_e_ugy_h: float) -> float:
    """Débit de dose équivalente : fond pondéré par Q_GCR, excès solaire par Q_SEP."""
    gcr = min(dose_e_ugy_h, baseline_e_ugy_h)
    sep = max(0.0, dose_e_ugy_h - baseline_e_ugy_h)
    return Q_GCR * gcr + Q_SEP * sep


Series = list[float | None]


@dataclass
class MedaSol:
    sol: int
    temperature_c: Series
    pressure_pa: Series
    wind_mps: Series

    def value(self, name: str, idx: int) -> float | None:
        series: Series = getattr(self, name)
        return series[idx]


@dataclass
class RadSample:
    utc: datetime
    dose_e_ugy_h: float
    dose_b_ugy_h: float


@dataclass
class RadSeries:
    samples: list[RadSample]
    baseline_e_ugy_h: float
    onset_utc: datetime
    peak_utc: datetime
    peak_e_ugy_h: float
    end_utc: datetime
    event_dose_ugy: float
    sources: list[str] = field(default_factory=list)

    def dose_e_at(self, utc: datetime) -> float:
        """Débit de dose E interpolé linéairement ; fond en dehors de la série."""
        s = self.samples
        if not s or utc <= s[0].utc or utc >= s[-1].utc:
            return self.baseline_e_ugy_h
        lo, hi = 0, len(s) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if s[mid].utc <= utc:
                lo = mid
            else:
                hi = mid
        a, b = s[lo], s[hi]
        span = (b.utc - a.utc).total_seconds()
        if span <= 0:
            return a.dose_e_ugy_h
        f = (utc - a.utc).total_seconds() / span
        return a.dose_e_ugy_h + f * (b.dose_e_ugy_h - a.dose_e_ugy_h)


@dataclass
class ConditionsDataset:
    meda: dict[int, MedaSol]
    rad: RadSeries | None
    meda_sources: list[str] = field(default_factory=list)
    generated_at: datetime | None = None
    path: Path | None = None

    # -- MEDA --------------------------------------------------------------------
    @property
    def sols(self) -> list[int]:
        return sorted(self.meda)

    def meda_sol_for(self, mission_sol: int) -> int | None:
        """Sol MEDA rejoué pour un sol de mission : les sols importés tournent en boucle."""
        sols = self.sols
        if not sols:
            return None
        return sols[(max(mission_sol, 1) - 1) % len(sols)]

    def climatology(self, name: str, idx: int) -> float | None:
        """Moyenne sur tous les sols importés pour une tranche d'heure locale."""
        values = [v for s in self.meda.values() if (v := s.value(name, idx)) is not None]
        if not values:
            return None
        return sum(values) / len(values)

    # -- sérialisation -------------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "version": FORMAT_VERSION,
            "site_id": "jezero",
            "generated_at": (self.generated_at or datetime.now(UTC)).isoformat(),
            "bin_minutes": BIN_MINUTES,
            "meda": {
                "sources": self.meda_sources,
                "sols": {
                    str(s.sol): {f: [_round(v) for v in getattr(s, f)] for f in FIELDS}
                    for s in sorted(self.meda.values(), key=lambda m: m.sol)
                },
            },
            "rad": None,
        }
        if self.rad is not None:
            r = self.rad
            out["rad"] = {
                "sources": r.sources,
                "baseline_e_ugy_h": _round(r.baseline_e_ugy_h),
                "onset_utc": r.onset_utc.isoformat(),
                "peak_utc": r.peak_utc.isoformat(),
                "peak_e_ugy_h": _round(r.peak_e_ugy_h),
                "end_utc": r.end_utc.isoformat(),
                "event_dose_ugy": _round(r.event_dose_ugy),
                "samples": [
                    [x.utc.isoformat(), _round(x.dose_e_ugy_h), _round(x.dose_b_ugy_h)]
                    for x in r.samples
                ],
            }
        return out

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        tmp.write_text(json.dumps(self.to_json(), separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def from_json(cls, data: dict[str, Any], path: Path | None = None) -> ConditionsDataset:
        if data.get("version") != FORMAT_VERSION:
            raise ValueError(f"Version de format inconnue : {data.get('version')}")
        meda: dict[int, MedaSol] = {}
        for key, sol in data["meda"]["sols"].items():
            meda[int(key)] = MedaSol(
                sol=int(key),
                temperature_c=list(sol["temperature_c"]),
                pressure_pa=list(sol["pressure_pa"]),
                wind_mps=list(sol["wind_mps"]),
            )
        rad: RadSeries | None = None
        if data.get("rad"):
            r = data["rad"]
            rad = RadSeries(
                samples=[
                    RadSample(datetime.fromisoformat(t), float(e), float(b))
                    for t, e, b in r["samples"]
                ],
                baseline_e_ugy_h=float(r["baseline_e_ugy_h"]),
                onset_utc=datetime.fromisoformat(r["onset_utc"]),
                peak_utc=datetime.fromisoformat(r["peak_utc"]),
                peak_e_ugy_h=float(r["peak_e_ugy_h"]),
                end_utc=datetime.fromisoformat(r["end_utc"]),
                event_dose_ugy=float(r["event_dose_ugy"]),
                sources=list(r.get("sources", [])),
            )
        generated = data.get("generated_at")
        return cls(
            meda=meda,
            rad=rad,
            meda_sources=list(data["meda"].get("sources", [])),
            generated_at=datetime.fromisoformat(generated) if generated else None,
            path=path,
        )

    @classmethod
    def load(cls, path: Path) -> ConditionsDataset:
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")), path)


def _round(v: float | None) -> float | None:
    if v is None or not math.isfinite(v):
        return None
    return round(v, 3)


@lru_cache(maxsize=4)
def _load_cached(path: str, mtime: float) -> ConditionsDataset | None:
    try:
        return ConditionsDataset.load(Path(path))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_default() -> ConditionsDataset | None:
    """Jeu importé s'il existe et se lit, sinon None (repli sur les modèles)."""
    path = default_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return _load_cached(str(path), mtime)
