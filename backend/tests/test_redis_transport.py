import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.services.redis_bus import RedisEventBus


def test_alert_serialization_roundtrip():
    alert = Alert(
        alert_id="alt_ser_01",
        event_id="evt_01",
        event_type="intrusion",
        severity="critical",
        camera_id="CAM_BORDER_04",
        track_id=5,
        object_class="person",
        zone_id="zone_sector_7",
        position=(120.5, 340.2),
        message="Suspicious person in sector 7",
        metadata={"speed": 1.4}
    )

    data_dict = alert.to_dict()
    assert data_dict["alert_id"] == "alt_ser_01"
    assert data_dict["position"] == [120.5, 340.2]
    assert data_dict["metadata"]["speed"] == 1.4

    json_str = json.dumps(data_dict)
    loaded_dict = json.loads(json_str)

    restored = Alert.from_dict(loaded_dict)
    assert restored.alert_id == alert.alert_id
    assert restored.position == (120.5, 340.2)
    assert restored.severity == "critical"
    assert restored.metadata["speed"] == 1.4


def test_redis_mock_sync_publish():
    bus = RedisEventBus(redis_url="redis://localhost:6379/0", channel="test.alerts")
    mock_client = MagicMock()
    bus._sync_client = mock_client

    alert = Alert(alert_id="alt_sync")
    success = bus.publish_alert_sync(alert)

    assert success is True
    mock_client.publish.assert_called_once()
    call_args = mock_client.publish.call_args[0]
    assert call_args[0] == "test.alerts"
    assert "alt_sync" in call_args[1]


@pytest.mark.asyncio
async def test_redis_mock_async_publish():
    bus = RedisEventBus(redis_url="redis://localhost:6379/0", channel="test.alerts")
    mock_async_client = AsyncMock()
    bus._async_client = mock_async_client

    alert = Alert(alert_id="alt_async")
    success = await bus.publish_alert_async(alert)

    assert success is True
    mock_async_client.publish.assert_called_once()


def test_redis_offline_graceful_fallback():
    # Points to non-existent port to test offline behavior
    bus = RedisEventBus(redis_url="redis://127.0.0.1:59999/0", channel="test.alerts")
    alert = Alert(alert_id="alt_offline")

    # Sync publish should return False without throwing an unhandled exception
    success = bus.publish_alert_sync(alert)
    assert success is False
