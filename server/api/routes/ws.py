"""
api.routes.ws - live dashboard feed socket (M2/M3).

  WS /api/v1/ws/feed   pushes {type: "report.new", data: <feed item>} as reports
                       are filed on any channel (via services.hub).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.hub import hub

router = APIRouter(tags=["ws"])


@router.websocket("/ws/feed")
async def ws_feed(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()  # we don't expect inbound; keeps the socket open
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)
