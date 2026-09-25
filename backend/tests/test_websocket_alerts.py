import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.schemas.alert import Alert
from backend.app.api.v1.endpoints.ws import ws_manager


def test_websocket_connect_and_ping():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws/alerts") as ws:
        # Send ping
        ws.send_text(json.dumps({"action": "ping"}))
        response_text = ws.receive_text()
        response = json.loads(response_text)
        assert response.get("action") == "pong"


@pytest.mark.asyncio
async def test_websocket_connection_manager_broadcast():
    class DummyWebSocket:
        def __init__(self):
            self.messages = []
            self.closed = False

        async def send_text(self, text: str):
            if self.closed:
                raise RuntimeError("Closed")
            self.messages.append(text)

        async def accept(self):
            pass

    dummy_ws1 = DummyWebSocket()
    dummy_ws2 = DummyWebSocket()

    await ws_manager.connect(dummy_ws1)
    await ws_manager.connect(dummy_ws2)

    test_alert = Alert(alert_id="alt_broadcast_01", message="Critical Breach")
    await ws_manager.broadcast_alert(test_alert)

    assert len(dummy_ws1.messages) == 1
    assert "alt_broadcast_01" in dummy_ws1.messages[0]
    assert len(dummy_ws2.messages) == 1

    # Test disconnect cleanup
    await ws_manager.disconnect(dummy_ws1)
    await ws_manager.disconnect(dummy_ws2)
    assert dummy_ws1 not in ws_manager.active_connections
