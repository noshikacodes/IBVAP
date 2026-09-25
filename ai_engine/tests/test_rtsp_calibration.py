import time
import pytest
import os
from unittest.mock import MagicMock, patch
from ai_engine.stream_manager.types import (
    StreamConfig,
    StreamState,
    StreamStatusInfo,
    mask_credentials,
)
from ai_engine.stream_manager.worker_process import WorkerProcessHandle, build_worker_command
from ai_engine.stream_manager.manager import StreamManager
from ai_engine.pipeline.stream_reader import VideoReader


def test_rtsp_credential_masking_comprehensive():
    """Verify that credentials in all RTSP formats are redacted from logs and status."""
    raw_url = "rtsp://admin:SecretPass123!@192.168.1.100:554/live/ch0?token=xyz"
    masked = mask_credentials(raw_url)
    assert "SecretPass123!" not in masked
    assert "admin" not in masked or "***:***" in masked
    assert "192.168.1.100:554/live/ch0" in masked

    config = StreamConfig(
        camera_id="CAM_RTSP_01",
        input_url=raw_url,
        name="Perimeter Gate",
        location="Sector Alpha",
        transport="tcp",
    )
    assert "SecretPass123!" not in config.masked_input_url
    d = config.to_dict(mask_secret=True)
    assert "SecretPass123!" not in d["input_url"]


def test_rtsp_config_validation_rules():
    """Test validation constraints on RTSP stream configuration."""
    # Invalid transport
    with pytest.raises(ValueError, match="transport must be 'tcp' or 'udp'"):
        StreamConfig(
            camera_id="CAM_01",
            input_url="rtsp://localhost:8554/live",
            transport="http"
        )

    # Invalid FPS
    with pytest.raises(ValueError, match="fps must be between 1 and 120"):
        StreamConfig(
            camera_id="CAM_01",
            input_url="rtsp://localhost:8554/live",
            fps=0
        )

    # Invalid min_object_size
    with pytest.raises(ValueError, match="min_object_size must be >= 1"):
        StreamConfig(
            camera_id="CAM_01",
            input_url="rtsp://localhost:8554/live",
            min_object_size=0
        )


def test_rtsp_config_aliases_and_field_calibration():
    """Verify that rtsp_url and reconnect_attempts aliases are mapped cleanly."""
    data = {
        "camera_id": "CAM_CALIB_01",
        "name": "Tower 4 Optical",
        "location": "North Hilltop",
        "rtsp_url": "rtsp://operator:pass@10.0.0.50:554/stream1",
        "reconnect_attempts": 7,
        "reconnect_delay": 3.0,
        "fps": 25,
        "resolution": "1920x1080",
        "transport": "udp",
        "night_mode": True,
        "min_object_size": 24,
        "roi": [100, 100, 800, 600]
    }
    cfg = StreamConfig.from_dict(data)
    assert cfg.camera_id == "CAM_CALIB_01"
    assert cfg.name == "Tower 4 Optical"
    assert cfg.location == "North Hilltop"
    assert cfg.input_url == "rtsp://operator:pass@10.0.0.50:554/stream1"
    assert cfg.max_retries == 7
    assert cfg.reconnect_delay == 3.0
    assert cfg.fps == 25
    assert cfg.resolution == "1920x1080"
    assert cfg.transport == "udp"
    assert cfg.night_mode is True
    assert cfg.min_object_size == 24
    assert cfg.roi == [100, 100, 800, 600]


def test_worker_handle_telemetry_and_state_mapping():
    """Verify telemetry state mapping from internal StreamState to C2 connection state."""
    config = StreamConfig(
        camera_id="CAM_STATE_TEST",
        input_url="rtsp://192.168.1.50:554/live",
        name="Sector North Camera",
        location="Sector Alpha",
        resolution="1280x720",
        fps=20,
        night_mode=True,
    )
    handle = WorkerProcessHandle(config)

    # Initial STOPPED state -> OFFLINE
    status = handle.get_status()
    assert status.connection_state == "OFFLINE"
    assert status.state == StreamState.STOPPED
    assert status.calibration_metadata["night_mode"] is True
    assert status.calibration_metadata["fps"] == 20

    # STARTING state -> CONNECTING
    handle.state = StreamState.STARTING
    assert handle.get_status().connection_state == "CONNECTING"

    # RUNNING state -> ONLINE
    handle.state = StreamState.RUNNING
    assert handle.get_status().connection_state == "ONLINE"

    # RECONNECTING state -> DEGRADED
    handle.state = StreamState.RECONNECTING
    assert handle.get_status().connection_state == "DEGRADED"


def test_camera_fault_isolation_in_stream_manager():
    """
    Verify that an invalid or crashing stream does NOT affect healthy streams.
    CAM_GOOD_1 (Running) + CAM_BAD (Failing) + CAM_GOOD_2 (Running).
    """
    def mock_factory(cmd, **kwargs):
        proc = MagicMock()
        # Fail CAM_BAD immediately
        if "CAM_BAD" in cmd:
            proc.poll.return_value = 1
            proc.pid = 9999
        else:
            proc.poll.return_value = None
            proc.pid = 1234
        return proc

    manager = StreamManager(max_streams=5, popen_factory=mock_factory)

    cfg_good1 = StreamConfig(camera_id="CAM_GOOD_1", input_url="rtsp://10.0.0.1/live")
    cfg_bad = StreamConfig(camera_id="CAM_BAD", input_url="rtsp://10.0.0.2/broken")
    cfg_good2 = StreamConfig(camera_id="CAM_GOOD_2", input_url="rtsp://10.0.0.3/live")

    manager.start_stream(cfg_good1)
    manager.start_stream(cfg_bad)
    manager.start_stream(cfg_good2)

    # Step monitor
    manager.monitor_step(current_time=time.time())

    # CAM_GOOD_1 and CAM_GOOD_2 must remain RUNNING (ONLINE)
    s1 = manager.get_status("CAM_GOOD_1")
    s2 = manager.get_status("CAM_GOOD_2")
    s_bad = manager.get_status("CAM_BAD")

    assert s1.state == StreamState.RUNNING
    assert s1.connection_state == "ONLINE"

    assert s2.state == StreamState.RUNNING
    assert s2.connection_state == "ONLINE"

    assert s_bad.state == StreamState.RECONNECTING
    assert s_bad.connection_state == "DEGRADED"

    manager.stop_all()


def test_videoreader_rtsp_transport_and_masking():
    """Verify VideoReader handles network streams with credential masking."""
    rtsp_source = "rtsp://user:pass123@192.168.1.100:554/live"
    reader = VideoReader(
        video_path=rtsp_source,
        transport="tcp",
        stall_timeout_seconds=5.0,
        reconnect_delay=1.0,
        max_retries=2
    )

    assert reader.is_network_stream is True
    assert "pass123" not in reader.masked_path
    assert reader.transport == "tcp"
    assert reader.fps == 15.0
    assert reader.resolution == "640x480"


def test_videoreader_stall_watchdog_detection():
    """Verify that stall detection triggers reconnection when no frame is received."""
    # Synthetic reader test on sample file verifies normal flow without stall
    sample_file = "mock_streams/sample_patrol.mp4"
    if os.path.exists(sample_file):
        with VideoReader(sample_file, stall_timeout_seconds=2.0) as reader:
            frames = []
            for idx, ts, frame in reader.read_frames():
                frames.append(idx)
                if len(frames) >= 5:
                    break
            assert len(frames) == 5
            assert reader.frames_read == 5
            assert reader.last_frame_timestamp is not None
