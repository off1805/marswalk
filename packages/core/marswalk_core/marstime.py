"""Temps martien (C1). BOUCHON de T00 : sol = jours terrestres écoulés.

Signature gelée : ``mars_time(utc, lon_east, epoch_utc) -> MarsTime``. C1 remplace le
corps par l'algorithme Mars24 (Allison et McEwen) ; le bouchon donne déjà une MSD
approchée et une heure locale cohérente pour que l'interface s'affiche.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from marswalk_core.schemas import MarsTime

_J2000_UNIX_DAYS = 10957.5  # 2000-01-01T12:00Z en jours depuis 1970
_SOL_RATIO = 1.0274912517


def _hms(hours: float) -> str:
    hours %= 24.0
    total = round(hours * 3600) % 86400
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def mars_time(utc: datetime, lon_east: float, epoch_utc: datetime) -> MarsTime:
    """Date solaire martienne, sol de mission et heure solaire moyenne locale."""
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=UTC)
    if epoch_utc.tzinfo is None:
        epoch_utc = epoch_utc.replace(tzinfo=UTC)
    days_unix = utc.timestamp() / 86400.0
    msd = (days_unix - _J2000_UNIX_DAYS) / _SOL_RATIO + 44796.0 - 0.00096
    mtc_hours = (24.0 * msd) % 24.0
    lmst_hours = (mtc_hours + lon_east / 15.0) % 24.0
    elapsed_days = (utc - epoch_utc).total_seconds() / 86400.0
    sol = math.floor(elapsed_days) + 1
    return MarsTime(
        utc=utc,
        msd=msd,
        sol=sol,
        lmst=_hms(lmst_hours),
        lmst_hours=lmst_hours,
        ltst=None,
        ls_deg=None,
    )
