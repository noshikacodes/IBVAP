import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.services.camera_registry import camera_registry
from backend.app.schemas.camera import CameraSource, SourceType, StreamStatus


@pytest.fixture(autouse=True)
def reset_registry():
    camera_registry.clear()
    cam1 = CameraSource(
        camera_id="CAM_01",
        name="Sector Alpha Gate",
        source_type=SourceType.RTSP,
        source_url="rtsp://localhost:8554/cam01",
        enabled=True,
        status=StreamStatus.ONLINE,
        location_metadata={"sector": "Sector Alpha", "fps": 15}
    )
    cam2 = CameraSource(
        camera_id="CAM_02",
        name="Sector Bravo Gate",
        source_type=SourceType.FILE,
        source_url="mock_streams/sample.mp4",
        enabled=False,
        status=StreamStatus.OFFLINE,
        location_metadata={"sector": "Sector Bravo", "fps": 15}
    )
    camera_registry.register(cam1)
    camera_registry.register(cam2)
    yield


def test_list_cameras():
    client = TestClient(app)
    response = client.get("/api/v1/cameras")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["cameras"]) == 2


def test_list_cameras_enabled_filter():
    client = TestClient(app)
    response = client.get("/api/v1/cameras?enabled_only=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["cameras"][0]["camera_id"] == "CAM_01"


def test_get_camera_by_id():
    client = TestClient(app)
    response = client.get("/api/v1/cameras/CAM_01")
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "CAM_01"
    assert data["name"] == "Sector Alpha Gate"
    assert data["source_type"] == "rtsp"


def test_get_camera_not_found():
    client = TestClient(app)
    response = client.get("/api/v1/cameras/NON_EXISTENT")
    assert response.status_code == 404


def test_register_camera():
    client = TestClient(app)
    payload = {
        "camera_id": "CAM_03",
        "name": "North Observation Tower",
        "source_type": "rtsp",
        "source_url": "rtsp://localhost:8554/cam03",
        "enabled": True,
        "status": "connecting",
        "location_metadata": {"sector": "Sector North"}
    }
    response = client.post("/api/v1/cameras", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["camera_id"] == "CAM_03"
    assert data["status"] == "connecting"

    # Duplicate ID should return 409
    dup_res = client.post("/api/v1/cameras", json=payload)
    assert dup_res.status_code == 409


def test_update_camera_status():
    client = TestClient(app)
    response = client.patch("/api/v1/cameras/CAM_01/status", json={"status": "reconnecting"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reconnecting"


def test_enable_and_disable_camera():
    client = TestClient(app)
    dis_res = client.post("/api/v1/cameras/CAM_01/disable")
    assert dis_res.status_code == 200
    assert dis_res.json()["enabled"] is False
    assert dis_res.json()["status"] == "offline"

    en_res = client.post("/api/v1/cameras/CAM_01/enable")
    assert en_res.status_code == 200
    assert en_res.json()["enabled"] is True


def test_get_camera_health():
    client = TestClient(app)
    response = client.get("/api/v1/cameras/CAM_01/health")
    assert response.status_code == 200
    data = response.json()
    assert data["camera_id"] == "CAM_01"
    assert data["name"] == "Sector Alpha Gate"
    assert data["connection_state"] == "online"
    assert "calibration_metadata" in data
    assert data["calibration_metadata"]["sector"] == "Sector Alpha"


def test_get_camera_health_not_found():
    client = TestClient(app)
    response = client.get("/api/v1/cameras/NON_EXISTENT/health")
    assert response.status_code == 404

