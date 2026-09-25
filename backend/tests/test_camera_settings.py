"""
Unit tests for Camera Source Settings, RTSP URL Validation, Dynamic Relays,
and Credential Masking in IBVAP.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.schemas.camera import StreamStatus, SourceType
from backend.app.services.camera_registry import camera_registry
from backend.app.services.stream_relay import mask_rtsp_url, stream_relay_manager


@pytest.fixture(autouse=True)
def setup_camera_registry():
    """Ensure clean registry state with 4 default cameras for each test."""
    camera_registry.clear()
    camera_registry._seed_defaults()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_credential_masking_utility():
    """Test that passwords in RTSP URLs are securely masked."""
    # Plain URL with credentials
    url = "rtsp://admin:superSecret123@192.168.1.100:554/h264Preview_01_main"
    masked = mask_rtsp_url(url)
    assert "superSecret123" not in masked
    assert "admin" not in masked or "***" in masked
    assert "192.168.1.100:554" in masked

    # URL without credentials
    plain_url = "rtsp://localhost:8554/ibvap-cam01"
    assert mask_rtsp_url(plain_url) == plain_url

    # Empty URL
    assert mask_rtsp_url("") == ""


def test_update_camera_source_real_rtsp(client):
    """Test updating CAM_01 to a real IP camera RTSP source."""
    payload = {
        "source_type": "rtsp",
        "source_url": "rtsp://admin:secret999@192.168.1.50:554/stream1",
        "name": "North Gate Real IP Camera",
        "sector": "Sector Alpha High Security",
        "location_name": "Gate Checkpoint 01",
        "latitude": 32.7157,
        "longitude": -117.1611,
        "is_simulated": False,
        "enabled": True
    }
    response = client.patch("/api/v1/cameras/CAM_01/source", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["camera_id"] == "CAM_01"
    assert data["name"] == "North Gate Real IP Camera"
    assert data["is_simulated"] is False
    assert data["status"] == "online"
    assert data["location_metadata"]["sector"] == "Sector Alpha High Security"
    assert data["location_metadata"]["location_name"] == "Gate Checkpoint 01"
    assert data["location_metadata"]["latitude"] == 32.7157
    assert data["location_metadata"]["longitude"] == -117.1611

    # Security check: Password must NEVER appear in response
    assert "secret999" not in data["source_url"]


def test_reset_camera_demo(client):
    """Test resetting CAM_01 back to synthetic simulated demo stream."""
    # First set to real camera
    client.patch("/api/v1/cameras/CAM_01/source", json={
        "source_type": "rtsp",
        "source_url": "rtsp://192.168.1.50:554/live",
        "is_simulated": False
    })

    # Now reset to demo
    response = client.post("/api/v1/cameras/CAM_01/reset-demo")
    assert response.status_code == 200
    data = response.json()

    assert data["camera_id"] == "CAM_01"
    assert data["is_simulated"] is True
    assert data["status"] == "simulated"
    assert "ibvap-cam01" in data["source_url"]


def test_connection_test_invalid_url(client):
    """Test connection test rejects non-RTSP/HTTP protocols."""
    payload = {
        "source_url": "ftp://invalid-server.com/video.mp4",
        "timeout_seconds": 1.0
    }
    response = client.post("/api/v1/cameras/CAM_01/test-connection", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["reachable"] is False
    assert data["status"] == "error"
    assert "Invalid URL scheme" in data["error_reason"]


def test_connection_test_timeout_handling(client):
    """Test connection test handles unreachable hosts gracefully within timeout."""
    payload = {
        "source_url": "rtsp://10.255.255.1:8554/non_existent_stream",
        "timeout_seconds": 0.5
    }
    response = client.post("/api/v1/cameras/CAM_01/test-connection", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["reachable"] is False
    assert data["status"] in ("offline", "error")
    assert data["camera_id"] == "CAM_01"
    assert data["latency_ms"] is not None


def test_camera_status_transitions(client):
    """Test camera status transition lifecycle."""
    # Check default simulated state
    res = client.get("/api/v1/cameras/CAM_02")
    assert res.status_code == 200
    assert res.json()["status"] == "simulated"

    # Disable camera
    res_dis = client.post("/api/v1/cameras/CAM_02/disable")
    assert res_dis.status_code == 200
    assert res_dis.json()["enabled"] is False
    assert res_dis.json()["status"] == "offline"

    # Re-enable camera
    res_en = client.post("/api/v1/cameras/CAM_02/enable")
    assert res_en.status_code == 200
    assert res_en.json()["enabled"] is True


def test_update_nonexistent_camera(client):
    """Test updating a nonexistent camera returns 404."""
    response = client.patch("/api/v1/cameras/CAM_NONEXISTENT/source", json={
        "source_type": "rtsp",
        "source_url": "rtsp://192.168.1.1:554/live"
    })
    assert response.status_code == 404
