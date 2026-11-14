"""Temps martien (A3, ENF-11). Bouchon T00 : exemple versionné."""

from __future__ import annotations

from fastapi import APIRouter

from marswalk_api.deps import load_example
from marswalk_core.schemas import TimeInfo

router = APIRouter(tags=["time"])


@router.get("/api/time", response_model=TimeInfo)
def get_time(site_id: str = "fictif") -> TimeInfo:
    """UTC, date solaire martienne, sol de mission et heure solaire locale du site."""
    return TimeInfo.model_validate(load_example("time"))
