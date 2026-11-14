"""Tests de l'algorithme Mars24 (C1) — Python.

Les cas de référence de la NASA GISS sont vérifiés à mieux que 2 secondes LMST.
Les vecteurs de test partagés avec TypeScript sont dans ``marstime_vectors.json``.

Référence : https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
"""

from __future__ import annotations

import datetime as _dt
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from marswalk_core.marstime import (
    _delta_j2000_tt,
    _ls,
    _mars_mean_anomaly,
    _mars_sol_date,
    _mst_hours,
    mars_time,
)

# Chemin vers les vecteurs partagés Python / TypeScript
_VECTORS_PATH = Path(__file__).parent / "marstime_vectors.json"

# ---------------------------------------------------------------------------
# Utilitaires locaux
# ---------------------------------------------------------------------------


def _hms(hours: float) -> str:
    total = round(((hours % 24.0) + 24.0) % 24.0 * 3600.0) % 86400
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _parse_hms(s: str) -> float:
    h, m, sec = (int(x) for x in s.split(":"))
    return h + m / 60.0 + sec / 3600.0


def _diff_hms_s(a: str, b: str) -> float:
    diff = abs(_parse_hms(a) - _parse_hms(b))
    return min(diff, 24.0 - diff) * 3600.0


# ---------------------------------------------------------------------------
# Vecteurs publiés par la NASA GISS
# ---------------------------------------------------------------------------


class TestNasaGissCase1:
    """Cas 1 : 2000-01-06T00:00:00Z — quasi-minuit commun Terre/Mars."""

    def _utc(self) -> datetime:
        return datetime(2000, 1, 6, 0, 0, 0, tzinfo=UTC)

    def test_delta_j2000(self) -> None:
        """ΔtJ2000 ≈ 4.50074 jours (étape A-6)."""
        dt = _delta_j2000_tt(self._utc())
        assert abs(dt - 4.50074) < 0.0002

    def test_mean_anomaly(self) -> None:
        """M ≈ 21.74558° (B-1)."""
        m = _mars_mean_anomaly(_delta_j2000_tt(self._utc()))
        assert abs(m - 21.746) < 0.01

    def test_ls(self) -> None:
        """Ls ≈ 277.188° (B-5)."""
        dt = _delta_j2000_tt(self._utc())
        ls = _ls(dt)
        assert abs(ls - 277.188) < 0.05

    def test_mst(self) -> None:
        """MST ≈ 23:59:39 (C-2)."""
        mst_h = _mst_hours(self._utc())
        assert _diff_hms_s(_hms(mst_h), "23:59:39") < 2.0

    def test_lmst(self) -> None:
        """LMST = MST à lon = 0°, doit valoir ≈ 23:59:39."""
        result = mars_time(self._utc(), lon_east=0.0, epoch_utc=self._utc())
        assert _diff_hms_s(result.lmst, "23:59:39") < 2.0

    def test_ltst(self) -> None:
        """LTST ≈ 23:38:54 (C-4)."""
        result = mars_time(self._utc(), lon_east=0.0, epoch_utc=self._utc())
        assert result.ltst is not None
        assert _diff_hms_s(result.ltst, "23:38:54") < 2.0

    def test_ls_deg_field(self) -> None:
        result = mars_time(self._utc(), lon_east=0.0, epoch_utc=self._utc())
        assert result.ls_deg is not None
        assert abs(result.ls_deg - 277.188) < 0.05


class TestNasaGissCase2:
    """Cas 2 : Spirit landing 2004-01-03T13:46:31Z — LTST ≈ 00:00:00 à 184.702°W."""

    LON_EAST = -184.702  # 184.702°W → convention degrés Est du projet

    def _utc(self) -> datetime:
        return datetime(2004, 1, 3, 13, 46, 31, tzinfo=UTC)

    def test_delta_j2000(self) -> None:
        """ΔtJ2000 ≈ 1463.07471 jours."""
        dt = _delta_j2000_tt(self._utc())
        assert abs(dt - 1463.075) < 0.002

    def test_ls(self) -> None:
        """Ls ≈ 327.324°."""
        dt = _delta_j2000_tt(self._utc())
        ls = _ls(dt)
        assert abs(ls - 327.324) < 0.05

    def test_lmst(self) -> None:
        """LMST ≈ 00:51:07."""
        result = mars_time(self._utc(), lon_east=self.LON_EAST, epoch_utc=self._utc())
        assert _diff_hms_s(result.lmst, "00:51:07") < 2.0

    def test_ltst(self) -> None:
        """LTST ≈ 00:00:00 (critère de choix de l'instant par la NASA GISS)."""
        result = mars_time(self._utc(), lon_east=self.LON_EAST, epoch_utc=self._utc())
        assert result.ltst is not None
        assert _diff_hms_s(result.ltst, "00:00:00") < 3.0


# ---------------------------------------------------------------------------
# Comportements généraux
# ---------------------------------------------------------------------------


def test_naive_utc_treated_as_utc() -> None:
    """Un datetime naïf donne le même résultat qu'un aware UTC."""
    naive = datetime(2026, 11, 14, 12, 0, 0)
    aware = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    epoch = aware
    r_naive = mars_time(naive, lon_east=77.58, epoch_utc=epoch)
    r_aware = mars_time(aware, lon_east=77.58, epoch_utc=epoch)
    assert r_naive.lmst == r_aware.lmst
    assert abs(r_naive.msd - r_aware.msd) < 1e-9


def test_sol_of_mission_first_sol() -> None:
    """Un instant pendant le premier sol donne sol = 1."""
    epoch = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
    utc = datetime(2026, 11, 1, 6, 0, 0, tzinfo=UTC)
    result = mars_time(utc, lon_east=77.58, epoch_utc=epoch)
    assert result.sol == 1


def test_sol_of_mission_second_sol() -> None:
    """Après 1 sol (88 776 s environ), on est au sol 2."""
    epoch = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
    # 1 sol = 1.0274912517 × 86400 = 88 775.244 s
    utc = epoch + _dt.timedelta(seconds=88_776)
    result = mars_time(utc, lon_east=77.58, epoch_utc=epoch)
    assert result.sol == 2


def test_lmst_offset_plus_6h() -> None:
    """Un décalage de +90° Est vaut exactement +6 h de LMST."""
    utc = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    epoch = utc
    r0 = mars_time(utc, lon_east=0.0, epoch_utc=epoch)
    r90 = mars_time(utc, lon_east=90.0, epoch_utc=epoch)
    diff = (r90.lmst_hours - r0.lmst_hours) % 24.0
    assert abs(diff - 6.0) < 0.001


def test_lmst_offset_minus_6h() -> None:
    """Un décalage de -90° Est vaut exactement -6 h de LMST (mod 24 → +18 h)."""
    utc = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    epoch = utc
    r0 = mars_time(utc, lon_east=0.0, epoch_utc=epoch)
    r_neg = mars_time(utc, lon_east=-90.0, epoch_utc=epoch)
    diff = (r_neg.lmst_hours - r0.lmst_hours) % 24.0
    assert abs(diff - 18.0) < 0.001


def test_longitude_antimeridian_east() -> None:
    """Longitude +180° : LMST_hours toujours dans [0, 24)."""
    utc = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    r = mars_time(utc, lon_east=180.0, epoch_utc=utc)
    assert 0.0 <= r.lmst_hours < 24.0


def test_longitude_antiméridien_ouest() -> None:
    """Longitude -180° : LMST_hours toujours dans [0, 24)."""
    utc = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    r = mars_time(utc, lon_east=-180.0, epoch_utc=utc)
    assert 0.0 <= r.lmst_hours < 24.0


def test_msd_increases_monotonically() -> None:
    """MSD augmente avec le temps."""
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 6, 1, tzinfo=UTC)
    t3 = datetime(2026, 11, 1, tzinfo=UTC)
    r1 = mars_time(t1, 0.0, t1)
    r2 = mars_time(t2, 0.0, t1)
    r3 = mars_time(t3, 0.0, t1)
    assert r1.msd < r2.msd < r3.msd


def test_ls_range() -> None:
    """Ls est toujours dans [0, 360)."""
    for y in (2000, 2004, 2020, 2026):
        utc = datetime(y, 6, 15, tzinfo=UTC)
        result = mars_time(utc, lon_east=0.0, epoch_utc=utc)
        assert result.ls_deg is not None
        assert 0.0 <= result.ls_deg < 360.0


def test_lmst_hours_in_range() -> None:
    """lmst_hours est toujours dans [0, 24), quelle que soit la longitude."""
    for lon in (-180.0, -90.0, -0.001, 0.0, 77.58, 90.0, 179.99, 180.0):
        utc = datetime(2026, 11, 14, 8, 0, tzinfo=UTC)
        result = mars_time(utc, lon_east=lon, epoch_utc=utc)
        assert 0.0 <= result.lmst_hours < 24.0, f"lon={lon}: lmst_hours={result.lmst_hours}"


def test_ltst_not_none() -> None:
    """ltst et ls_deg sont calculés (implémentation C1)."""
    utc = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    result = mars_time(utc, lon_east=77.58, epoch_utc=utc)
    assert result.ltst is not None
    assert result.ls_deg is not None


def test_leap_year_terrestrial_no_crash() -> None:
    """29 février (année bissextile terrestre) ne lève pas d'exception."""
    utc = datetime(2000, 2, 29, 12, 0, 0, tzinfo=UTC)
    result = mars_time(utc, lon_east=0.0, epoch_utc=utc)
    assert 0.0 <= result.lmst_hours < 24.0
    assert result.ls_deg is not None


def test_non_leap_year_terrestrial_no_crash() -> None:
    """28 février d'une année non-bissextile ne lève pas d'exception."""
    utc = datetime(2026, 2, 28, 12, 0, 0, tzinfo=UTC)
    result = mars_time(utc, lon_east=0.0, epoch_utc=utc)
    assert 0.0 <= result.lmst_hours < 24.0


def test_sol_boundary_precision() -> None:
    """La frontière de sol ne saute pas un entier ni n'en répète un."""
    epoch = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
    sol_seconds = 1.0274912517 * 86400.0  # 88775.244 s
    # Juste avant la frontière du sol 2
    before = epoch + _dt.timedelta(seconds=sol_seconds - 1)
    # Juste après
    after = epoch + _dt.timedelta(seconds=sol_seconds + 1)
    r_before = mars_time(before, 0.0, epoch)
    r_after = mars_time(after, 0.0, epoch)
    assert r_before.sol == 1
    assert r_after.sol == 2


def test_msd_approx_giss1() -> None:
    """MSD proche de 44796 au voisinage de J2000.0."""
    utc = datetime(2000, 1, 6, tzinfo=UTC)
    msd = _mars_sol_date(utc)
    assert abs(msd - 44796.0) < 0.5


# ---------------------------------------------------------------------------
# Vecteurs partagés (fichier JSON)
# ---------------------------------------------------------------------------


def _load_vectors() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]
    return data


@pytest.mark.parametrize("v", [v for v in _load_vectors() if "lmst" in v["expected"]])
def test_vectors_lmst(v: dict[str, Any]) -> None:
    """LMST retrouvé à ±tolérance secondes pour chaque vecteur avec 'lmst' attendu."""
    utc = datetime.fromisoformat(v["utc"].replace("Z", "+00:00"))
    result = mars_time(utc, lon_east=v["lon_east"], epoch_utc=utc)
    diff = _diff_hms_s(result.lmst, v["expected"]["lmst"])
    assert diff <= v["tolerance_lmst_s"], (
        f"{v['name']}: LMST attendu {v['expected']['lmst']}, "
        f"obtenu {result.lmst}, écart {diff:.1f} s"
    )


@pytest.mark.parametrize("v", [v for v in _load_vectors() if "ls_deg" in v["expected"]])
def test_vectors_ls(v: dict[str, Any]) -> None:
    """Ls retrouvé à ±0.1° pour les vecteurs avec 'ls_deg' attendu."""
    utc = datetime.fromisoformat(v["utc"].replace("Z", "+00:00"))
    result = mars_time(utc, lon_east=v["lon_east"], epoch_utc=utc)
    assert result.ls_deg is not None
    assert abs(result.ls_deg - v["expected"]["ls_deg"]) < 0.1, (
        f"{v['name']}: Ls attendu {v['expected']['ls_deg']}, obtenu {result.ls_deg}"
    )


@pytest.mark.parametrize("v", [v for v in _load_vectors() if "lmst_hours_range" in v["expected"]])
def test_vectors_lmst_range(v: dict[str, Any]) -> None:
    """LMST dans la plage attendue."""
    utc = datetime.fromisoformat(v["utc"].replace("Z", "+00:00"))
    result = mars_time(utc, lon_east=v["lon_east"], epoch_utc=utc)
    lo, hi = v["expected"]["lmst_hours_range"]
    assert lo <= result.lmst_hours < hi, (
        f"{v['name']}: lmst_hours={result.lmst_hours} hors [{lo}, {hi})"
    )


@pytest.mark.parametrize(
    "v", [v for v in _load_vectors() if "lmst_offset_from_mst_h" in v["expected"]]
)
def test_vectors_lmst_offset(v: dict[str, Any]) -> None:
    """LMST = MST + lon/15 avec la tolérance indiquée."""
    utc = datetime.fromisoformat(v["utc"].replace("Z", "+00:00"))
    result = mars_time(utc, lon_east=v["lon_east"], epoch_utc=utc)
    mst = _mst_hours(utc)
    expected_lmst = ((mst + v["expected"]["lmst_offset_from_mst_h"]) % 24.0 + 24.0) % 24.0
    diff_s = abs(result.lmst_hours - expected_lmst) * 3600.0
    # Prendre le minimum modulo 24 h
    diff_s = min(diff_s, 86400.0 - diff_s)
    assert diff_s <= v["tolerance_lmst_s"], (
        f"{v['name']}: offset LMST attendu {expected_lmst:.4f} h, "
        f"obtenu {result.lmst_hours:.4f} h, écart {diff_s:.1f} s"
    )


@pytest.mark.parametrize("v", [v for v in _load_vectors() if "sol_min" in v["expected"]])
def test_vectors_sol_min(v: dict[str, Any]) -> None:
    """Sol de mission ≥ valeur minimale attendue."""
    utc = datetime.fromisoformat(v["utc"].replace("Z", "+00:00"))
    epoch = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
    result = mars_time(utc, lon_east=v["lon_east"], epoch_utc=epoch)
    assert result.sol >= v["expected"]["sol_min"], (
        f"{v['name']}: sol={result.sol} < {v['expected']['sol_min']}"
    )
