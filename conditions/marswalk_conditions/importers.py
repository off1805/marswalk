"""Import des séries MEDA (Perseverance) et RAD (Curiosity) téléchargées par D0.

Entrée : ``data/raw/jezero/meda/`` et ``data/raw/jezero/rad_may2024/`` (voir
``config/sites/jezero/sources.yaml``). Sortie : le jeu compact de ``dataset.py``.

Formats lus (vérifiés sur les fichiers du PDS) :

- MEDA calibré, CSV PDS4 avec en-tête : ``SCLK,LMST,LTST,...`` où LMST vaut
  ``00030M12:34:56.789`` (sol 30). Colonnes retenues : ``ATS_LOCAL_TEMP1`` à ``3`` (K, capteurs
  du mât), ``BAROCAP1_PRESSURE`` (Pa, transducteur actif), ``BOOM1/2_HORIZONTAL_WIND_SPEED``
  (m/s). Le vent n'est publié que pour les sols où WS existe (36 à 39 dans le lot de D0).
- RAD RDR, texte PDS3 par sol : blocs ``[OBSERVATION: NN]`` avec ``START_OBS_UTC`` et
  ``OBS_DURATION``, puis ``[DOSIMETRY_TOTAL_DOSE_E: NN]`` et ``_B`` en µGy/h (E : détecteur
  plastique, proche du tissu ; B : silicium).
"""

from __future__ import annotations

import csv
import re
import statistics
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from marswalk_conditions.dataset import (
    N_BINS,
    ConditionsDataset,
    MedaSol,
    RadSample,
    RadSeries,
    bin_index,
)

MEDA_NAME = re.compile(r"^WE__(\d{4})_+CAL_(ATS|PS|WS)_+P(\d+)\.CSV$", re.IGNORECASE)
RAD_NAME = re.compile(r"^RAD_RDR_\d{4}_\d{3}_\d\d_\d\d_(\d{4})_V(\d+)\.TXT$", re.IGNORECASE)
LMST_RE = re.compile(r"^\s*(\d+)M(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)\s*$")

KELVIN = 273.15
# Bornes physiques larges : tout ce qui sort est un défaut de capteur.
VALID = {
    "temperature_c": (-140.0, 40.0),
    "pressure_pa": (400.0, 1300.0),
    "wind_mps": (0.0, 60.0),
}


# -- MEDA -------------------------------------------------------------------------


def parse_lmst(text: str) -> tuple[int, float] | None:
    """``00030M12:34:56.789`` vers (30, 12.5824...)."""
    m = LMST_RE.match(text)
    if not m:
        return None
    sol, h, mi, s = int(m[1]), int(m[2]), int(m[3]), float(m[4])
    return sol, h + mi / 60.0 + s / 3600.0


def _num(text: str | None) -> float | None:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _mean(values: Iterable[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _row_value(kind: str, row: dict[str, str]) -> tuple[str, float | None]:
    if kind == "ATS":
        k = _mean(_num(row.get(f"ATS_LOCAL_TEMP{i}")) for i in (1, 2, 3))
        return "temperature_c", None if k is None else k - KELVIN
    if kind == "PS":
        return "pressure_pa", _num(row.get("BAROCAP1_PRESSURE"))
    return "wind_mps", _mean(_num(row.get(f"BOOM{i}_HORIZONTAL_WIND_SPEED")) for i in (1, 2))


def bin_meda_csv(path: Path, kind: str) -> tuple[str, dict[int, list[float]]]:
    """Moyennes par (sol, tranche) d'un fichier MEDA : renvoie le champ et {sol: [sommes]}.

    Les sommes et les effectifs sont gardés à part pour pouvoir cumuler plusieurs fichiers.
    """
    field = ""
    sums: dict[int, list[float]] = {}
    counts: dict[int, list[int]] = {}
    lo_hi: tuple[float, float] | None = None
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            parsed = parse_lmst(row.get("LMST", ""))
            if parsed is None:
                continue
            field, value = _row_value(kind, row)
            if value is None:
                continue
            lo_hi = lo_hi or VALID[field]
            if not lo_hi[0] <= value <= lo_hi[1]:
                continue
            sol, hours = parsed
            idx = bin_index(hours)
            s = sums.setdefault(sol, [0.0] * N_BINS)
            c = counts.setdefault(sol, [0] * N_BINS)
            s[idx] += value
            c[idx] += 1
    means: dict[int, list[float]] = {}
    for sol, s in sums.items():
        c = counts[sol]
        means[sol] = [s[i] / c[i] if c[i] else float("nan") for i in range(N_BINS)]
    return field or _row_value(kind, {})[0], means


def latest_meda_files(meda_dir: Path) -> list[tuple[Path, str]]:
    """Un fichier par (sol, type), la version de produit la plus récente."""
    best: dict[tuple[int, str], tuple[int, Path]] = {}
    for p in sorted(meda_dir.glob("*")):
        m = MEDA_NAME.match(p.name)
        if not m:
            continue
        key = (int(m[1]), m[2].upper())
        version = int(m[3])
        if key not in best or version > best[key][0]:
            best[key] = (version, p)
    return [(p, kind) for (_, kind), (_, p) in sorted(best.items())]


def import_meda(meda_dir: Path) -> tuple[dict[int, MedaSol], list[str]]:
    sols: dict[int, dict[str, list[float | None]]] = {}
    sources: list[str] = []
    for path, kind in latest_meda_files(meda_dir):
        field, means = bin_meda_csv(path, kind)
        if not means:
            continue
        sources.append(path.name)
        for sol, series in means.items():
            target = sols.setdefault(
                sol, {f: [None] * N_BINS for f in ("temperature_c", "pressure_pa", "wind_mps")}
            )
            for i, v in enumerate(series):
                if v == v:  # pas NaN
                    target[field][i] = v
    out = {
        sol: MedaSol(sol, f["temperature_c"], f["pressure_pa"], f["wind_mps"])
        for sol, f in sols.items()
        # Un sol n'est retenu que si la température couvre au moins la moitié de la journée.
        if sum(v is not None for v in f["temperature_c"]) >= N_BINS // 2
    }
    return out, sources


# -- RAD --------------------------------------------------------------------------


@dataclass
class _Obs:
    start: datetime | None = None
    duration_s: float = 0.0
    dose_b: float | None = None
    dose_e: float | None = None


def parse_rad_utc(text: str) -> datetime:
    """``2024-141 19:08:25`` (année, jour de l'année) vers datetime UTC."""
    return datetime.strptime(text.strip().strip('"'), "%Y-%j %H:%M:%S").replace(tzinfo=UTC)


def iter_rad_observations(path: Path) -> Iterator[RadSample]:
    """Une mesure par observation qui porte une dosimétrie, datée au milieu de la pose."""
    obs = _Obs()
    section = ""

    def flush(o: _Obs) -> RadSample | None:
        if o.start is None or o.dose_e is None or o.dose_b is None:
            return None
        mid = o.start + timedelta(seconds=o.duration_s / 2.0)
        return RadSample(mid, o.dose_e, o.dose_b)

    with path.open(encoding="ascii", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("["):
                section = line
                if line.startswith("[OBSERVATION"):
                    sample = flush(obs)
                    if sample:
                        yield sample
                    obs = _Obs()
                continue
            if section.startswith("[OBSERVATION"):
                if line.startswith("START_OBS_UTC="):
                    obs.start = parse_rad_utc(line.split("=", 1)[1])
                elif line.startswith("OBS_DURATION="):
                    obs.duration_s = _num(line.split("=", 1)[1]) or 0.0
            elif section.startswith("[DOSIMETRY_TOTAL_DOSE_B"):
                obs.dose_b = _num(line)
                section = ""
            elif section.startswith("[DOSIMETRY_TOTAL_DOSE_E"):
                obs.dose_e = _num(line)
                section = ""
    sample = flush(obs)
    if sample:
        yield sample


def drop_outliers(samples: list[RadSample], ratio: float = 0.4) -> list[RadSample]:
    """Retire les poses écourtées dont la dose s'effondre.

    Une mesure est écartée si elle vaut moins de 40 % de ses deux voisines : c'est le cas des
    poses interrompues (dose de 1 µGy/h entre deux mesures à 6 µGy/h), pas d'un front montant.
    """
    kept: list[RadSample] = []
    for i, s in enumerate(samples):
        if s.dose_e_ugy_h <= 0:
            continue
        prev = samples[i - 1].dose_e_ugy_h if i > 0 else None
        nxt = samples[i + 1].dose_e_ugy_h if i + 1 < len(samples) else None
        neigh = [v for v in (prev, nxt) if v is not None and v > 0]
        if neigh and s.dose_e_ugy_h < ratio * min(neigh):
            continue
        kept.append(s)
    return kept


def analyse_rad(samples: list[RadSample], sources: list[str]) -> RadSeries:
    """Fond, début, pic et fin de l'événement solaire, puis dose de l'événement."""
    if len(samples) < 10:
        raise ValueError("Série RAD trop courte pour détecter un événement")
    samples = sorted(samples, key=lambda s: s.utc)
    i_peak = max(range(len(samples)), key=lambda i: samples[i].dose_e_ugy_h)
    peak = samples[i_peak]
    quiet = [s.dose_e_ugy_h for s in samples if s.utc < peak.utc - timedelta(days=1)]
    if len(quiet) < 10:
        quiet = [s.dose_e_ugy_h for s in samples]
    baseline = statistics.median(quiet)

    i_onset = i_peak
    while i_onset > 0 and samples[i_onset - 1].dose_e_ugy_h > 2.0 * baseline:
        i_onset -= 1
    i_end = i_peak
    while i_end < len(samples) - 1 and samples[i_end].dose_e_ugy_h > 1.2 * baseline:
        i_end += 1

    event_dose = 0.0
    for a, b in zip(samples[i_onset:i_end], samples[i_onset + 1 : i_end + 1], strict=False):
        dt_h = (b.utc - a.utc).total_seconds() / 3600.0
        excess = (a.dose_e_ugy_h + b.dose_e_ugy_h) / 2.0 - baseline
        event_dose += max(0.0, excess) * dt_h

    return RadSeries(
        samples=samples,
        baseline_e_ugy_h=baseline,
        onset_utc=samples[i_onset].utc,
        peak_utc=peak.utc,
        peak_e_ugy_h=peak.dose_e_ugy_h,
        end_utc=samples[i_end].utc,
        event_dose_ugy=event_dose,
        sources=sources,
    )


def import_rad(rad_dir: Path) -> RadSeries | None:
    best: dict[int, tuple[int, Path]] = {}
    for p in sorted(rad_dir.glob("*")):
        m = RAD_NAME.match(p.name)
        if m:
            sol, version = int(m[1]), int(m[2])
            if sol not in best or version > best[sol][0]:
                best[sol] = (version, p)
    if not best:
        return None
    samples: list[RadSample] = []
    sources: list[str] = []
    for _, (_, path) in sorted(best.items()):
        found = list(iter_rad_observations(path))
        if found:
            samples.extend(found)
            sources.append(path.name)
    if not samples:
        return None
    return analyse_rad(drop_outliers(sorted(samples, key=lambda s: s.utc)), sources)


# -- ensemble -----------------------------------------------------------------------


def import_all(raw_dir: Path) -> ConditionsDataset:
    """Importe MEDA et RAD depuis ``data/raw/jezero`` (sous-dossiers de D0)."""
    meda_dir, rad_dir = raw_dir / "meda", raw_dir / "rad_may2024"
    meda, meda_sources = import_meda(meda_dir) if meda_dir.is_dir() else ({}, [])
    rad = import_rad(rad_dir) if rad_dir.is_dir() else None
    if not meda and rad is None:
        raise FileNotFoundError(f"Aucune donnée MEDA ni RAD sous {raw_dir}")
    return ConditionsDataset(
        meda=meda, rad=rad, meda_sources=meda_sources, generated_at=datetime.now(UTC)
    )
