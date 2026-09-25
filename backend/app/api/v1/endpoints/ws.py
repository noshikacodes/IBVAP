import json
import asyncio
from typing import List, Set, Any, Optional, Dict, Union
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.core.logging import logger
from backend.app.schemas.alert import Alert
from backend.app.services.alert_engine import alert_engine


router = APIRouter()


class WebSocketConnectionManager:
    """Manages active WebSocket dashboard client connections and alert broadcasts."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info("WebSocket client connected. Total active clients: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Total active clients: %d", len(self.active_connections))

    async def broadcast_alert(self, alert: Any) -> None:
        """Broadcasts an alert payload to all connected clients."""
        if not self.active_connections:
            return

        if isinstance(alert, dict):
            payload = alert
        elif hasattr(alert, "to_dict"):
            payload = alert.to_dict()
        else:
            payload = dict(alert)

        message_str = json.dumps({"type": "NEW_ALERT", "data": payload}, default=str)

        disconnected: List[WebSocket] = []
        async with self._lock:
            clients = list(self.active_connections)

        for connection in clients:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.debug("Failed to send message to WebSocket client: %s", e)
                disconnected.append(connection)

        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self.active_connections.discard(ws)


    async def broadcast_event(self, event_type: str, data: Any) -> None:
        """Broadcasts a generic structured event payload (e.g. PTZ telemetry) to all connected clients."""
        if not self.active_connections:
            return

        message_str = json.dumps({"type": event_type, "data": data}, default=str)

        disconnected: List[WebSocket] = []
        async with self._lock:
            clients = list(self.active_connections)

        for connection in clients:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.debug("Failed to send event to WebSocket client: %s", e)
                disconnected.append(connection)

        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    self.active_connections.discard(ws)


ws_manager = WebSocketConnectionManager()


# Register in-process bridge so alerts generated in backend are immediately broadcast
def _on_alert_generated(alert: Alert) -> None:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            asyncio.create_task(ws_manager.broadcast_alert(alert))
    except RuntimeError:
        pass


alert_engine.register_listener(_on_alert_generated)


# Register PTZ telemetry bridge
def _on_ptz_telemetry(event_payload: Dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            evt_type = event_payload.get("type", "PTZ_EVENT")
            data = event_payload.get("data", {})
            asyncio.create_task(ws_manager.broadcast_event(evt_type, data))
    except RuntimeError:
        pass


try:
    from ai_engine.pipeline.ptz import ptz_controller
    ptz_controller.register_telemetry_listener(_on_ptz_telemetry)
except Exception as e:
    logger.debug("PTZ controller telemetry registration deferred: %s", e)



@router.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    """
    Real-time WebSocket endpoint for receiving live security alerts.
    Clients connect to receive streaming alert notifications.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection open and accept optional client ping/ack messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"action": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug("WebSocket connection error: %s", e)
        await ws_manager.disconnect(websocket)
