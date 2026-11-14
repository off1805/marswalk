"""Diffusion des messages WebSocket aux clients abonnés (A3, section 6).

Un client s'abonne à une sortie (``/ws/eva/{eva_id}``). Un message publié pour une sortie
va à ses abonnés ; un message publié pour ``None`` (conditions du site, alerte du site) va
à tous. La publication marche depuis la boucle asyncio comme depuis un fil de travail.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from marswalk_core.schemas import WsEnvelope


class Hub:
    def __init__(self) -> None:
        self._subs: dict[
            str | None, set[tuple[asyncio.Queue[dict[str, Any]], asyncio.AbstractEventLoop]]
        ] = {}
        self._lock = threading.Lock()

    def subscribe(self, eva_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subs.setdefault(eva_id, set()).add((queue, loop))
        return queue

    def unsubscribe(self, eva_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            subs = self._subs.get(eva_id, set())
            for item in list(subs):
                if item[0] is queue:
                    subs.discard(item)
            if not subs:
                self._subs.pop(eva_id, None)

    def subscribers(self) -> int:
        with self._lock:
            return sum(len(s) for s in self._subs.values())

    def publish(self, eva_id: str | None, message: Any) -> None:
        """Envoie ``message`` (un modèle ``Ws*`` ou un dict déjà sérialisé)."""
        data = (
            message
            if isinstance(message, dict)
            else WsEnvelope.model_validate({"message": message}).message.model_dump(mode="json")
        )
        with self._lock:
            targets = (
                [t for subs in self._subs.values() for t in subs]
                if eva_id is None
                else list(self._subs.get(eva_id, set()))
            )
        for queue, loop in targets:
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is loop:
                queue.put_nowait(data)
            elif not loop.is_closed():
                loop.call_soon_threadsafe(queue.put_nowait, data)
