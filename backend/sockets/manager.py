"""
WebSocket connection manager and router.
"""
import json
import logging
from typing import Dict, Set, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
ws_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        # Channel-based fanout:
        # - "real" for the main app
        # - "sim:<simulation_id>" for simulation instances
        self._channels: Dict[str, Set[WebSocket]] = {"real": set()}

    async def connect(self, ws: WebSocket, channel: str = "real"):
        await ws.accept()
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(ws)
        logger.info(
            f"WS connected. Channel={channel} Total={sum(len(v) for v in self._channels.values())}"
        )

    def disconnect(self, ws: WebSocket):
        for ch in list(self._channels.keys()):
            self._channels[ch].discard(ws)
            if ch != "real" and len(self._channels[ch]) == 0:
                # Cleanup empty simulation channels
                self._channels.pop(ch, None)
        logger.info(
            f"WS disconnected. Total={sum(len(v) for v in self._channels.values())}"
        )

    async def broadcast(self, message: str, channel: Optional[str] = None):
        """
        If channel is None -> broadcast to all channels.
        Otherwise -> broadcast only to that channel.
        """
        targets: Set[WebSocket] = set()
        if channel is None:
            for conns in self._channels.values():
                targets.update(conns)
        else:
            targets.update(self._channels.get(channel, set()))

        dead: Set[WebSocket] = set()
        for ws in list(targets):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for d in dead:
            self.disconnect(d)

    async def send_personal(self, ws: WebSocket, message: str):
        try:
            await ws.send_text(message)
        except Exception:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return sum(len(v) for v in self._channels.values())


@ws_router.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket):
    # Access the shared manager via app state
    mgr: ConnectionManager = ws.app.state.ws_manager if hasattr(ws.app.state, "ws_manager") else ConnectionManager()
    await mgr.connect(ws, channel="real")
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


@ws_router.websocket("/ws/simulation/{simulation_id}")
async def websocket_simulation(ws: WebSocket, simulation_id: str):
    mgr: ConnectionManager = ws.app.state.ws_manager if hasattr(ws.app.state, "ws_manager") else ConnectionManager()
    channel = f"sim:{simulation_id}"
    await mgr.connect(ws, channel=channel)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await mgr.send_personal(ws, json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        mgr.disconnect(ws)
