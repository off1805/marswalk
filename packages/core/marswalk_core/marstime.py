"""Temps martien — algorithme Mars24 complet (C1).

Implémentation exacte de l'algorithme Mars24 de la NASA GISS, basée sur :

- Allison, M. et McEwen, M. (2000). « A post-Pathfinder evaluation of areocentric solar
  coordinates with improved timing recipes for Mars seasonal/diurnal climate studies ».
  Planetary and Space Science, 48(2–3), 215–235.
- NASA GISS Mars24 Sunclock — Algorithm and Worked Examples :
  https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
  (consulté novembre 2026)

Les deux cas de référence publiés par la NASA GISS sont vérifiés dans les tests (C1) :
1. 2000-01-06T00:00:00Z → MST = 23:59:39, Ls ≈ 277.19°
2. 2004-01-03T13:46:31Z → LTST ≈ 00:00:00 au site Spirit (184.702°W)

Conventions :
- MSD  : Mars Sol Date, nombre de jours martiens depuis une époque de référence.
- MST  : Mean Solar Time (Airy Mean Time) à la longitude 0°.
- LMST : Local Mean Solar Time, heure solaire *moyenne* locale.
- LTST : Local True Solar Time, heure solaire *vraie* locale.
- Ls   : Longitude solaire (0° = équinoxe de printemps de l'hémisphère nord).

L'interface publique est gelée (taches-agents.md § 7) :
    mars_time(utc, lon_east, epoch_utc) -> MarsTime
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from marswalk_core.schemas import MarsTime

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Époque Unix (1970-01-01T00:00Z) exprimée en Jour Julien
_JD_UNIX_EPOCH = 2_440_587.5

# Époque J2000.0 (2000-01-01T12:00 TT) exprimée en Jour Julien
_JD_J2000 = 2_451_545.0

# Table TAI − UTC en secondes depuis le 1972-01-01 (entrée en vigueur des leap seconds).
# Source : IERS Bulletin C 67 (consultée novembre 2026 ; aucun leap second depuis 2017).
# Format : (Unix timestamp de début de période, TAI-UTC en secondes entières)
# TT − UTC = TAI − UTC + 32.184 s
_TAI_MINUS_UTC_TABLE: tuple[tuple[float, int], ...] = (
    # (Unix timestamp, TAI-UTC)
    (0.0, 10),  # avant 1972-01-01 : approximatif
    (63072000.0, 10),  # 1972-01-01
    (78796800.0, 11),  # 1972-07-01
    (94694400.0, 12),  # 1973-01-01
    (126230400.0, 13),  # 1974-01-01
    (157766400.0, 14),  # 1975-01-01
    (189302400.0, 15),  # 1976-01-01
    (220924800.0, 16),  # 1977-01-01
    (252460800.0, 17),  # 1978-01-01
    (283996800.0, 18),  # 1979-01-01
    (315532800.0, 19),  # 1980-01-01
    (362793600.0, 20),  # 1981-07-01
    (394329600.0, 21),  # 1982-07-01
    (425865600.0, 22),  # 1983-07-01
    (489024000.0, 23),  # 1985-07-01
    (567993600.0, 24),  # 1988-01-01
    (631152000.0, 25),  # 1990-01-01
    (662688000.0, 26),  # 1991-01-01
    (709948800.0, 27),  # 1992-07-01
    (741484800.0, 28),  # 1993-07-01
    (773020800.0, 29),  # 1994-07-01
    (820454400.0, 30),  # 1996-01-01
    (867715200.0, 31),  # 1997-07-01
    (915148800.0, 32),  # 1999-01-01
    (1136073600.0, 33),  # 2006-01-01
    (1230768000.0, 34),  # 2009-01-01
    (1341100800.0, 35),  # 2012-07-01
    (1435708800.0, 36),  # 2015-07-01
    (1483228800.0, 37),  # 2017-01-01  ← dernier leap second (Bulletin C 67)
)
_TT_MINUS_TAI_S = 32.184


def _tt_minus_utc(unix_ts: float) -> float:
    """TT − UTC en secondes pour un timestamp Unix donné (table de leap seconds IERS)."""
    tai_utc = 10
    for ts, val in _TAI_MINUS_UTC_TABLE:
        if unix_ts >= ts:
            tai_utc = val
        else:
            break
    return tai_utc + _TT_MINUS_TAI_S


# Rapport sol martien / jour terrestre (1 sol = 24 h 39 min 35,244 s)
_SOL_DAYS = 1.0274912517

# Constante de la formule MST (Airy Mean Time) — eq. C-2 NASA GISS
_MST_REF_JD = 2_451_549.5  # JD de référence de la formule MST
_MST_EPOCH = 44796.0  # MSD à cette date de référence
_MST_CORR = 0.0009626  # correction empirique (eq. C-2)

# Anomalie moyenne de Mars à ΔtJ2000 = 0 (B-1)
_M0 = 19.3871
# Taux d'accroissement de M (degrés / jour TT)
_M_RATE = 0.52402073

# Angle du « Fictitious Mean Sun » (B-2) à ΔtJ2000 = 0
_AFMS0 = 270.3871
# Taux d'accroissement de αFMS (degrés / jour TT) — légèrement différent de M_RATE
_AFMS_RATE = 0.524038496

# Coefficient du terme linéaire dans ν − M (B-4) : 3×10⁻⁷ °/jour
_NU_M_DRIFT = 3.0e-7

# Coefficients de Fourier pour PBS (B-3) : (A_i, τ_i, φ_i)
# Source : tableau de l'algorithme NASA GISS
_PBS_TERMS: tuple[tuple[float, float, float], ...] = (
    (0.0071, 2.2353, 49.409),
    (0.0057, 2.7543, 168.173),
    (0.0039, 1.1177, 191.837),
    (0.0037, 15.7866, 21.736),
    (0.0021, 2.1354, 15.704),
    (0.0020, 2.4694, 95.528),
    (0.0018, 32.8493, 49.095),
)

_DEG2RAD = math.pi / 180.0


# ---------------------------------------------------------------------------
# Fonctions auxiliaires privées
# ---------------------------------------------------------------------------


def _hms(hours: float) -> str:
    """Convertit des heures décimales en chaîne 'HH:MM:SS' (mod 24)."""
    total = round(((hours % 24.0) + 24.0) % 24.0 * 3600.0) % 86400
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _jd_ut(utc: datetime) -> float:
    """Jour Julien (UT) depuis la date UTC (étapes A-1 et A-2)."""
    millis = utc.timestamp() * 1000.0
    return _JD_UNIX_EPOCH + millis / 86_400_000.0


def _delta_j2000_tt(utc: datetime) -> float:
    """Jours depuis J2000.0 en Temps Terrestre (TT) — étapes A-4 à A-6."""
    jd_ut = _jd_ut(utc)
    tt_minus_utc = _tt_minus_utc(utc.timestamp())
    jd_tt = jd_ut + tt_minus_utc / 86400.0
    return jd_tt - _JD_J2000


def _mars_mean_anomaly(dt: float) -> float:
    """Anomalie moyenne de Mars M en degrés (B-1) — Allison & McEwen éq. 16."""
    return (_M0 + _M_RATE * dt) % 360.0


def _afms(dt: float) -> float:
    """Angle du Fictitious Mean Sun αFMS en degrés (B-2) — éq. 17."""
    return (_AFMS0 + _AFMS_RATE * dt) % 360.0


def _pbs(dt: float) -> float:
    """Somme des perturbateurs PBS en degrés (B-3) — éq. 18 NASA GISS.

    PBS = Σ A_i · cos( 0.985626° · Δt / τ_i + φ_i )
    où 0.985626° = 360° / 365.25.
    """
    k = 0.985626 * dt
    return sum(a * math.cos(_DEG2RAD * (k / tau + phi)) for a, tau, phi in _PBS_TERMS)


def _nu_minus_m(dt: float, m_deg: float) -> float:
    """Équation du centre ν − M en degrés (B-4) — éq. 18 Allison & McEwen.

    ν − M = (10.691 + 3×10⁻⁷ Δt) sin M + 0.623 sin 2M + 0.050 sin 3M
           + 0.005 sin 4M + 0.0005 sin 5M + PBS
    """
    m = m_deg * _DEG2RAD
    return (
        (10.691 + _NU_M_DRIFT * dt) * math.sin(m)
        + 0.623 * math.sin(2 * m)
        + 0.050 * math.sin(3 * m)
        + 0.005 * math.sin(4 * m)
        + 0.0005 * math.sin(5 * m)
        + _pbs(dt)
    )


def _ls(dt: float) -> float:
    """Longitude solaire Ls en degrés [0, 360) (B-5) — éq. 19."""
    return (_afms(dt) + _nu_minus_m(dt, _mars_mean_anomaly(dt))) % 360.0


def _eot_hours(ls_deg: float, nu_m_deg: float) -> float:
    """Équation du temps EOT en heures (C-1) — éq. 20.

    EOT en degrés = 2.861 sin 2Ls − 0.071 sin 4Ls + 0.002 sin 6Ls − (ν − M)
    EOT en heures = EOT_deg / 15.
    """
    ls_r = ls_deg * _DEG2RAD
    eot_deg = (
        2.861 * math.sin(2 * ls_r)
        - 0.071 * math.sin(4 * ls_r)
        + 0.002 * math.sin(6 * ls_r)
        - nu_m_deg
    )
    return eot_deg / 15.0


def _mst_hours(utc: datetime) -> float:
    """Mean Solar Time (Airy Mean Time) en heures (C-2) — éq. modifiée NASA GISS."""
    jd_ut = _jd_ut(utc)
    tt_minus_utc = _tt_minus_utc(utc.timestamp())
    jd_tt = jd_ut + tt_minus_utc / 86400.0
    mst = 24.0 * ((jd_tt - _MST_REF_JD) / _SOL_DAYS + _MST_EPOCH - _MST_CORR)
    return mst % 24.0


def _mars_sol_date(utc: datetime) -> float:
    """Mars Sol Date (MSD), dérivé directement de JDTT — éq. C-2 sans mod24."""
    jd_ut = _jd_ut(utc)
    tt_minus_utc = _tt_minus_utc(utc.timestamp())
    jd_tt = jd_ut + tt_minus_utc / 86400.0
    return (jd_tt - _MST_REF_JD) / _SOL_DAYS + _MST_EPOCH - _MST_CORR


def _sol_of_mission(utc: datetime, epoch_utc: datetime) -> int:
    """Sol de mission : 1 pendant le premier sol terrestre après l'époque."""
    elapsed_s = (utc - epoch_utc).total_seconds()
    if elapsed_s < 0:
        return 0
    return math.floor(elapsed_s / (86400.0 * _SOL_DAYS)) + 1


# ---------------------------------------------------------------------------
# Interface publique
# ---------------------------------------------------------------------------


def mars_time(utc: datetime, lon_east: float, epoch_utc: datetime) -> MarsTime:
    """Date solaire martienne, sol de mission et heures solaires locale moyenne et vraie.

    Paramètres
    ----------
    utc :
        Instant UTC (peut être naïf, interprété comme UTC).
    lon_east :
        Longitude de référence du site, en degrés Est, IAU_2015:49900.
    epoch_utc :
        Début du sol 1 de la mission simulée (peut être naïf, interprété comme UTC).

    Retourne
    --------
    MarsTime avec :
    - msd        : Mars Sol Date (nombre continu de jours martiens).
    - sol        : Sol de mission (entier ≥ 1).
    - lmst       : Heure solaire moyenne locale « HH:MM:SS ».
    - lmst_hours : Même valeur en heures décimales.
    - ltst       : Heure solaire vraie locale « HH:MM:SS » (via équation du temps).
    - ls_deg     : Longitude solaire en degrés [0, 360).

    Précision
    ---------
    Les cas de référence du Mars24 NASA GISS sont retrouvés à mieux que 1 seconde LMST.

    Notes
    -----
    La formule utilise TT − UTC = 69.184 s (valeur fixe depuis janvier 2017 ; aucun
    nouveau leap second n'a été ajouté jusqu'à novembre 2026).
    La longitude Mars24 suit la convention **planétographique degrés Ouest** dans les
    formules internes (LMST = MST − Λ_west / 15).  On reçoit ici une longitude *Est*
    (convention du projet, règle R2) : ``Λ_west = −lon_east``, d'où
    ``LMST = MST + lon_east / 15``.

    Références
    ----------
    Allison & McEwen (2000), Planet. Space Sci. 48, 215–235.
    https://www.giss.nasa.gov/tools/mars24/help/algorithm.html
    """
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=UTC)
    if epoch_utc.tzinfo is None:
        epoch_utc = epoch_utc.replace(tzinfo=UTC)

    # --- paramètres orbitaux ---
    dt = _delta_j2000_tt(utc)
    m_deg = _mars_mean_anomaly(dt)
    nm = _nu_minus_m(dt, m_deg)
    ls = _ls(dt)

    # --- temps martiennes ---
    msd = _mars_sol_date(utc)
    mst = _mst_hours(utc)

    # LMST : convention planétographique Ouest → lon_east = −lon_west (C-3)
    lmst_hours = (mst + lon_east / 15.0) % 24.0

    # EOT et LTST (C-4)
    eot = _eot_hours(ls, nm)
    ltst_hours = (lmst_hours + eot) % 24.0

    # Sol de mission
    sol = _sol_of_mission(utc, epoch_utc)

    return MarsTime(
        utc=utc,
        msd=msd,
        sol=sol,
        lmst=_hms(lmst_hours),
        lmst_hours=lmst_hours,
        ltst=_hms(ltst_hours),
        ls_deg=round(ls, 4),
    )
