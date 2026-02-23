"""
WebSocket connection manager and router.
"""
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
ws_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"WS connected. Total: {len(self._connections)}")

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        logger.info(f"WS disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message: str):
        dead = set()
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for d in dead:
            self._connections.discard(d)

    async def send_personal(self, ws: WebSocket, message: str):
        try:
            await ws.send_text(message)
        except Exception:
            self._connections.discard(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


@ws_router.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    # Access the shared manager via app state
    mgr: ConnectionManager = ws.app.state.ws_manager if hasattr(ws.app.state, "ws_manager") else ConnectionManager()
    await mgr.connect(ws)
    try:
        while True:
            # Keep alive — also accept client messages (e.g. manual commands)
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                # Handle client-sent commands
                if msg.get("action") == "ping":
                    await mgr.send_personal(ws, json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        mgr.disconnect(ws)
