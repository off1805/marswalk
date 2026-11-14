"""WebSocket /ws/eva/{eva_id} (A3). Bouchon T00 : rejoue les messages d'exemple puis attend."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from marswalk_api.deps import load_example

router = APIRouter()

WS_EXAMPLES = ["telemetry", "alert", "alert_cleared", "conditions", "route_updated", "budget"]


@router.websocket("/ws/eva/{eva_id}")
async def eva_socket(websocket: WebSocket, eva_id: str) -> None:
    await websocket.accept()
    for name in WS_EXAMPLES:
        await websocket.send_json(load_example(f"ws_{name}"))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
