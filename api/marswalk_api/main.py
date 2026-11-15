"""Application FastAPI de Marswalk (T00). Tous les routeurs sont enregistrés ici.

Lancement : ``uv run uvicorn marswalk_api.main:app --reload``.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from marswalk_api import __version__
from marswalk_api.db.session import database_status
from marswalk_api.deps import get_settings, load_example
from marswalk_api.routers import (
    alerts,
    conditions,
    eva,
    export,
    ground_images,
    hazards,
    plans,
    query,
    sites,
    targets,
    tiles,
    ws,
)
from marswalk_api.routers import time as time_router
from marswalk_core.paths import list_package_ids
from marswalk_core.schemas import CONTRACTS_VERSION, Health, WsEnvelope

ROUTERS = [
    sites.router,
    tiles.router,
    query.router,
    hazards.router,
    targets.router,
    plans.router,
    conditions.router,
    alerts.router,
    time_router.router,
    ws.router,
    eva.router,
    ground_images.router,
    export.router,
]


logger = logging.getLogger(__name__)


def _warm_up(site_id: str) -> None:
    """Lit les couches et calcule un plan sur toutes les cibles proposées du site : les
    grilles de coût des trois variantes, le champ de retour et les tronçons restent en
    cache pour les requêtes suivantes."""
    from marswalk_api.services.mission_planning.deps import (
        get_plan_computation_service,
        get_plan_repository,
        get_safety_settings_repository,
        get_target_repository,
    )
    from marswalk_core.schemas import PlanCreate
    from marswalk_core.site_package import load_site

    try:
        site = load_site(site_id)
        for layer_id in site.raster_layer_ids():
            if site.has_layer(layer_id):
                site.read_layer(layer_id)
        targets = get_target_repository().list_by_site(site_id)
        if targets:
            service = get_plan_computation_service(
                get_target_repository(), get_plan_repository(), get_safety_settings_repository()
            )
            plan = service.compute_plan(site_id, PlanCreate(target_ids=[t.id for t in targets]))
            logger.info("Préchauffage de %s : plan calculé en %s ms", site_id, plan.compute_time_ms)
    except Exception:  # le préchauffage ne doit jamais empêcher l'API de démarrer
        logger.exception("Préchauffage de %s impossible", site_id)


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.warmup:
        threading.Thread(target=_warm_up, args=(settings.default_site,), daemon=True).start()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=_lifespan,
        title="Marswalk API",
        version=__version__,
        description=(
            "Carte et planification de sorties sur Mars. Coordonnées en degrés "
            "planétocentriques est, Mars 2000 (IAU_2015:49900). Contrats : "
            f"{CONTRACTS_VERSION}."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=Health, tags=["health"])
    def health() -> Health:
        db = database_status()
        return Health(
            status="ok" if db != "unavailable" else "degraded",
            version=__version__,
            contracts=CONTRACTS_VERSION,
            database=db,
            sites=list_package_ids(),
        )

    @app.get(
        "/api/_contracts/ws-message",
        response_model=WsEnvelope,
        tags=["contracts"],
        summary="Forme des messages du WebSocket /ws/eva/{eva_id} (documentation)",
    )
    def ws_message_contract() -> WsEnvelope:
        return WsEnvelope.model_validate({"message": load_example("ws_telemetry")})

    for router in ROUTERS:
        app.include_router(router)
    return app


app = create_app()
