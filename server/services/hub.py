"""
services.hub - tiny in-process WebSocket fan-out for the live dashboard feed (M2/M3).

Intake handlers call `hub.broadcast(...)` whenever a report is filed; the
dashboard's `WS /api/v1/ws/feed` subscribers receive it. Best-effort: a dead
socket is dropped silently, never raising into the intake path. For multi-worker
deploys this is replaced by a Redis pub/sub fan-out (M4) - same broadcast call.
"""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from core.logging_utils import get_logger

log = get_logger("nandi.hub")


class Hub:
    def __init__(self) -> None:
        self._conns: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._conns.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._conns.discard(ws)

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        message = {"type": event, "data": payload}
        dead: list[WebSocket] = []
        for ws in self._conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._conns.discard(ws)


hub = Hub()
