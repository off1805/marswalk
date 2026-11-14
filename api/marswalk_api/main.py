"""Application FastAPI de Marswalk (T00). Tous les routeurs sont enregistrés ici.

Lancement : ``uv run uvicorn marswalk_api.main:app --reload``.
"""

from __future__ import annotations

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


def create_app() -> FastAPI:
    app = FastAPI(
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
