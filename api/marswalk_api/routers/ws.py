"""WebSocket /ws/eva/{eva_id} (A3, section 6).

À la connexion : les conditions du moment et les alertes actives. Ensuite : tous les
messages publiés pour la sortie et pour le site. Le client peut acquitter une alerte en
envoyant ``{"type": "ack", "alert_id": "..."}``.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from marswalk_api.services.a3 import get_service
from marswalk_core.schemas import WsAlert, WsConditions

router = APIRouter()


@router.websocket("/ws/eva/{eva_id}")
async def eva_socket(websocket: WebSocket, eva_id: str) -> None:
    await websocket.accept()
    service = get_service()
    queue = service.hub.subscribe(eva_id)
    try:
        conditions = service.current_conditions()
        st = service.stamp(eva_id, conditions.utc)
        await websocket.send_json(
            WsConditions(utc=st.utc, sol=st.sol, lmst=st.lmst, payload=conditions).model_dump(
                mode="json"
            )
        )
        for alert in reversed(service.engine.list(eva_id)):
            await websocket.send_json(
                WsAlert(utc=st.utc, sol=st.sol, lmst=st.lmst, payload=alert).model_dump(mode="json")
            )
        sender = asyncio.create_task(_forward(websocket, queue))
        try:
            while True:
                msg: Any = await websocket.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "ack" and msg.get("alert_id"):
                    service.acknowledge(str(msg["alert_id"]))
        finally:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender
    except WebSocketDisconnect:
        return
    finally:
        service.hub.unsubscribe(eva_id, queue)


async def _forward(websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]) -> None:
    while True:
        data = await queue.get()
        await websocket.send_json(data)
