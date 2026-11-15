"""Temps martien du site (A3, ENF-11), calculé par C1 (Mars24)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from marswalk_api.services.a3 import get_service
from marswalk_api.services.a3.clock import time_info
from marswalk_core.schemas import TimeInfo
from marswalk_core.site_package import load_site

router = APIRouter(tags=["time"])


@router.get("/api/time", response_model=TimeInfo)
def get_time(site_id: str = "fictif") -> TimeInfo:
    """UTC, date solaire martienne, sol de mission et heure solaire locale du site."""
    # Pendant un scénario, l'instant est celui du scénario.
    try:
        site = load_site(site_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Site inconnu : {site_id}") from exc
    return time_info(site, get_service().scenario_utc())
