import pytest
from backend.app.schemas.camera import CameraSource, SourceType, StreamStatus
from backend.app.services.camera_registry import InMemoryCameraRegistry


@pytest.fixture
def registry():
    return InMemoryCameraRegistry(initialize_defaults=False)


def test_register_and_get_camera(registry):
    cam = CameraSource(
        camera_id="CAM_TEST_01",
        name="Test Border Camera",
        source_type=SourceType.RTSP,
        source_url="rtsp://localhost:8554/test-stream",
        enabled=True,
        status=StreamStatus.ONLINE,
        location_metadata={"sector": "Sector Alpha", "fps": 30}
    )

    saved = registry.register(cam)
    assert saved.camera_id == "CAM_TEST_01"

    retrieved = registry.get("CAM_TEST_01")
    assert retrieved is not None
    assert retrieved.name == "Test Border Camera"
    assert retrieved.source_type == SourceType.RTSP
    assert retrieved.status == StreamStatus.ONLINE


def test_list_cameras_with_filters(registry):
    cam1 = CameraSource(
        camera_id="CAM_01",
        name="RTSP Cam 1",
        source_type=SourceType.RTSP,
        enabled=True
    )
    cam2 = CameraSource(
        camera_id="CAM_02",
        name="File Cam 2",
        source_type=SourceType.FILE,
        enabled=False
    )
    cam3 = CameraSource(
        camera_id="CAM_03",
        name="RTSP Cam 3",
        source_type=SourceType.RTSP,
        enabled=False
    )

    registry.register(cam1)
    registry.register(cam2)
    registry.register(cam3)

    all_cams = registry.list()
    assert len(all_cams) == 3

    enabled_only = registry.list(enabled_only=True)
    assert len(enabled_only) == 1
    assert enabled_only[0].camera_id == "CAM_01"

    rtsp_only = registry.list(source_type=SourceType.RTSP)
    assert len(rtsp_only) == 2


def test_update_status_and_enable_disable(registry):
    cam = CameraSource(
        camera_id="CAM_01",
        name="RTSP Cam 1",
        source_type=SourceType.RTSP,
        enabled=True,
        status=StreamStatus.CONNECTING
    )
    registry.register(cam)

    updated = registry.update_status("CAM_01", StreamStatus.ONLINE)
    assert updated.status == StreamStatus.ONLINE

    disabled = registry.disable("CAM_01")
    assert disabled.enabled is False
    assert disabled.status == StreamStatus.OFFLINE

    enabled = registry.enable("CAM_01")
    assert enabled.enabled is True


def test_delete_and_clear(registry):
    cam = CameraSource(camera_id="CAM_01", name="Cam 1")
    registry.register(cam)

    assert registry.get("CAM_01") is not None
    assert registry.delete("CAM_01") is True
    assert registry.get("CAM_01") is None
    assert registry.delete("NON_EXISTENT") is False
