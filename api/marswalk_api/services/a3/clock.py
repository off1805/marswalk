"""Horodatage martien des messages (A3, ENF-11) : UTC, sol de mission et heure locale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from marswalk_core.marstime import mars_time
from marswalk_core.schemas import MarsTime, TimeInfo
from marswalk_core.site_package import Site

MARS_HOUR_S = 88775.244 / 24
"""Une heure solaire martienne, en secondes."""
SUNSET_LMST_H = 18.0
"""Coucher du Soleil retenu en heure solaire moyenne locale (approximation sans relief)."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def site_lon(site: Site) -> float:
    west, _, east, _ = site.manifest.bbox
    return (west + east) / 2


def mars_clock(site: Site, utc: datetime) -> MarsTime:
    return mars_time(utc, site_lon(site), site.manifest.mission_epoch_utc)


def time_info(site: Site, utc: datetime) -> TimeInfo:
    mt = mars_clock(site, utc)
    return TimeInfo(**mt.model_dump(), site_id=site.site_id, lon_east=site_lon(site))


@dataclass(frozen=True)
class Stamp:
    utc: datetime
    sol: int
    lmst: str
    lmst_hours: float

    @classmethod
    def of(cls, site: Site, utc: datetime) -> Stamp:
        mt = mars_clock(site, utc)
        return cls(utc, mt.sol, mt.lmst, mt.lmst_hours)

    def daylight_left_s(self) -> float:
        """Temps avant le coucher du Soleil (négatif la nuit)."""
        return (SUNSET_LMST_H - self.lmst_hours) * MARS_HOUR_S
