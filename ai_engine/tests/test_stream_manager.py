import os
import json
import pytest
import time
from datetime import datetime
from typing import List, Optional

from ai_engine.stream_manager.types import (
    StreamState,
    StreamConfig,
    StreamStatusInfo,
    mask_credentials,
)
from ai_engine.stream_manager.worker_process import (
    build_worker_command,
    WorkerProcessHandle,
)
from ai_engine.stream_manager.manager import StreamManager


# ============================================================================
# Mock Subprocess for Deterministic Process Testing
# ============================================================================

class MockPopen:
    """Deterministic in-memory mock for subprocess.Popen."""
    def __init__(self, cmd: List[str], stdout=None, stderr=None, text=True):
        self.cmd = cmd
        self.pid = 54321
        self._returncode: Optional[int] = None
        self.terminated = False
        self.killed = False

    def poll(self) -> Optional[int]:
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = 0

    def kill(self) -> None:
        self.killed = True
        self._returncode = -9

    def wait(self, timeout: Optional[float] = None) -> int:
        if self._returncode is None:
            self._returncode = 0
        return self._returncode

    def simulate_crash(self, exit_code: int = 1) -> None:
        self._returncode = exit_code


# ============================================================================
# 1. StreamConfig & Validation Tests
# ============================================================================

def test_stream_config_defaults_and_serialization():
    config = StreamConfig(
        camera_id="CAM_NORTH_01",
        input_url="rtsp://192.168.1.100:8554/live"
    )

    assert config.camera_id == "CAM_NORTH_01"
    assert config.enabled is True
    assert config.enable_anpr is False
    assert config.enable_frs is False
    assert config.model_name == "yolov8n.pt"
    assert config.confidence_threshold == 0.40

    d = config.to_dict()
    assert d["camera_id"] == "CAM_NORTH_01"
    assert d["input_url"] == "rtsp://192.168.1.100:8554/live"
    assert d["enabled"] is True

    # Roundtrip from_dict
    reconstructed = StreamConfig.from_dict(d)
    assert reconstructed.camera_id == config.camera_id
    assert reconstructed.input_url == config.input_url


def test_stream_config_validations():
    # Empty camera_id
    with pytest.raises(ValueError, match="camera_id cannot be empty"):
        StreamConfig(camera_id="", input_url="sample.mp4")

    # Empty input_url
    with pytest.raises(ValueError, match="input_url cannot be empty"):
        StreamConfig(camera_id="CAM_01", input_url="")

    # Invalid confidence
    with pytest.raises(ValueError, match="confidence_threshold must be between 0.0 and 1.0"):
        StreamConfig(camera_id="CAM_01", input_url="sample.mp4", confidence_threshold=1.5)

    # Invalid ANPR stride
    with pytest.raises(ValueError, match="anpr_stride must be >= 1"):
        StreamConfig(camera_id="CAM_01", input_url="sample.mp4", anpr_stride=0)

    # Invalid FRS votes
    with pytest.raises(ValueError, match="frs_votes must be >= 1"):
        StreamConfig(camera_id="CAM_01", input_url="sample.mp4", frs_votes=0)


# ============================================================================
# 2. RTSP Credential Masking Tests
# ============================================================================

def test_credential_masking_standard_rtsp():
    raw_url = "rtsp://admin:supersecret123@192.168.1.50:8554/live/stream1"
    masked = mask_credentials(raw_url)
    assert "supersecret123" not in masked
    assert "admin" not in masked
    assert masked == "rtsp://***:***@192.168.1.50:8554/live/stream1"


def test_credential_masking_non_secret_urls_and_files():
    clean_rtsp = "rtsp://192.168.1.50:8554/live"
    assert mask_credentials(clean_rtsp) == clean_rtsp

    file_path = "mock_streams/sample_patrol.mp4"
    assert mask_credentials(file_path) == file_path

    empty_str = ""
    assert mask_credentials(empty_str) == ""


# ============================================================================
# 3. CLI Command Translation Tests (ANPR / FRS Matrix)
# ============================================================================

def test_command_builder_basic_stream():
    config = StreamConfig(
        camera_id="CAM_FENCE",
        input_url="mock_streams/sample_patrol.mp4",
        model_name="yolov8n.pt",
        confidence_threshold=0.45,
        spatial_rules_path="mock_streams/spatial_rules.json"
    )

    cmd = build_worker_command(config, python_executable="python")
    assert "python" in cmd[0]
    assert "-m" in cmd and "ai_engine.worker" in cmd
    assert "--input" in cmd and "mock_streams/sample_patrol.mp4" in cmd
    assert "--camera-id" in cmd and "CAM_FENCE" in cmd
    assert "--model" in cmd and "yolov8n.pt" in cmd
    assert "--conf" in cmd and "0.45" in cmd
    assert "--spatial-rules" in cmd and "mock_streams/spatial_rules.json" in cmd
    assert "--anpr" not in cmd
    assert "--frs" not in cmd


def test_command_builder_camera_specific_anpr():
    config = StreamConfig(
        camera_id="CAM_GATE",
        input_url="rtsp://localhost:8554/gate",
        enable_anpr=True,
        anpr_model="custom_plate.pt",
        anpr_ocr="paddleocr",
        anpr_confidence=0.55,
        anpr_stride=2,
        anpr_votes=4
    )

    cmd = build_worker_command(config, python_executable="python")
    assert "--anpr" in cmd
    assert "--anpr-model" in cmd and "custom_plate.pt" in cmd
    assert "--anpr-ocr" in cmd and "paddleocr" in cmd
    assert "--anpr-conf" in cmd and "0.55" in cmd
    assert "--anpr-stride" in cmd and "2" in cmd
    assert "--anpr-votes" in cmd and "4" in cmd
    assert "--frs" not in cmd


def test_command_builder_camera_specific_frs():
    config = StreamConfig(
        camera_id="CAM_PATROL",
        input_url="rtsp://localhost:8554/patrol",
        enable_frs=True,
        frs_gallery="mock_streams/face_gallery.json",
        frs_threshold=0.70,
        frs_stride=4,
        frs_votes=3,
        frs_min_size=40,
        frs_detector="yolov8n_face.pt",
        frs_recognizer="mobilefacenet_arcface.onnx"
    )

    cmd = build_worker_command(config, python_executable="python")
    assert "--frs" in cmd
    assert "--frs-gallery" in cmd and "mock_streams/face_gallery.json" in cmd
    assert "--frs-thresh" in cmd and "0.7" in cmd
    assert "--frs-stride" in cmd and "4" in cmd
    assert "--frs-votes" in cmd and "3" in cmd
    assert "--frs-min-size" in cmd and "40" in cmd
    assert "--anpr" not in cmd


# ============================================================================
# 4. Stream Lifecycle & State Machine Tests
# ============================================================================

def test_stream_lifecycle_start_stop_restart():
    created_processes = []

    def mock_factory(cmd, **kwargs):
        p = MockPopen(cmd, **kwargs)
        created_processes.append(p)
        return p

    manager = StreamManager(popen_factory=mock_factory)

    config = StreamConfig(
        camera_id="CAM_TEST_01",
        input_url="rtsp://localhost:8554/test"
    )

    # 1. Start Stream
    assert manager.start_stream(config) is True
    status = manager.get_status("CAM_TEST_01")
    assert status is not None
    assert status.state == StreamState.RUNNING
    assert status.process_id == 54321
    assert len(created_processes) == 1

    # 2. Starting already running stream returns False
    assert manager.start_stream(config) is False

    # 3. Stop Stream
    assert manager.stop_stream("CAM_TEST_01") is True
    status_stopped = manager.get_status("CAM_TEST_01")
    assert status_stopped.state == StreamState.STOPPED
    assert status_stopped.process_id is None
    assert created_processes[0].terminated is True

    # 4. Restart Stream
    assert manager.restart_stream("CAM_TEST_01") is True
    status_restarted = manager.get_status("CAM_TEST_01")
    assert status_restarted.state == StreamState.RUNNING
    assert len(created_processes) == 2


def test_disabled_stream_registration():
    manager = StreamManager()
    config = StreamConfig(
        camera_id="CAM_DISABLED",
        input_url="mock_streams/sample.mp4",
        enabled=False
    )

    # start_stream returns False and sets state to STOPPED without spawning
    assert manager.start_stream(config) is False
    status = manager.get_status("CAM_DISABLED")
    assert status is not None
    assert status.state == StreamState.STOPPED
    assert status.enabled is False
    assert status.process_id is None


def test_max_streams_capacity_limit():
    manager = StreamManager(max_streams=2, popen_factory=lambda cmd, **kwargs: MockPopen(cmd))

    c1 = StreamConfig(camera_id="CAM_1", input_url="stream1.mp4")
    c2 = StreamConfig(camera_id="CAM_2", input_url="stream2.mp4")
    c3 = StreamConfig(camera_id="CAM_3", input_url="stream3.mp4")

    assert manager.start_stream(c1) is True
    assert manager.start_stream(c2) is True
    # 3rd stream exceeds max_streams=2 limit
    assert manager.start_stream(c3) is False

    assert manager.get_active_stream_count() == 2


# ============================================================================
# 5. Crash Detection & Exponential Backoff Recovery Tests
# ============================================================================

def test_process_crash_detection_and_exponential_backoff():
    mock_procs: List[MockPopen] = []

    def mock_factory(cmd, **kwargs):
        p = MockPopen(cmd, **kwargs)
        mock_procs.append(p)
        return p

    manager = StreamManager(
        initial_backoff=1.0,
        max_backoff=16.0,
        max_restart_attempts=3,
        popen_factory=mock_factory
    )

    config = StreamConfig(camera_id="CAM_CRASH", input_url="rtsp://localhost:8554/crash")
    assert manager.start_stream(config) is True
    assert len(mock_procs) == 1
    p1 = mock_procs[0]

    # Simulate unexpected worker process crash (e.g. exit code 1)
    p1.simulate_crash(exit_code=1)

    t0 = 1000.0
    # Monitor step detects exit -> transitions to RECONNECTING with backoff 1.0s
    states1 = manager.monitor_step(current_time=t0)
    assert states1["CAM_CRASH"] == StreamState.RECONNECTING
    status1 = manager.get_status("CAM_CRASH")
    assert status1.restart_count == 1
    assert "exited with code 1" in status1.last_error

    # Before backoff expires (t0 + 0.5s) -> still RECONNECTING
    states_mid = manager.monitor_step(current_time=t0 + 0.5)
    assert states_mid["CAM_CRASH"] == StreamState.RECONNECTING
    assert len(mock_procs) == 1  # No new process spawned yet

    # After backoff expires (t0 + 1.0s) -> worker is restarted -> RUNNING
    states2 = manager.monitor_step(current_time=t0 + 1.1)
    assert states2["CAM_CRASH"] == StreamState.RUNNING
    assert len(mock_procs) == 2  # New process spawned
    p2 = mock_procs[1]

    # Crash 2: Backoff should double (2.0s)
    p2.simulate_crash(exit_code=137)
    t1 = t0 + 2.0
    manager.monitor_step(current_time=t1)
    status2 = manager.get_status("CAM_CRASH")
    assert status2.state == StreamState.RECONNECTING
    assert status2.restart_count == 2
    assert manager.calculate_backoff(status2.restart_count) == 2.0

    # Restart 2 triggers at t1 + 2.1s
    manager.monitor_step(current_time=t1 + 2.1)
    assert len(mock_procs) == 3
    p3 = mock_procs[2]

    # Crash 3: Final attempt before exceeding max_restart_attempts=3
    p3.simulate_crash(exit_code=1)
    t2 = t1 + 5.0
    manager.monitor_step(current_time=t2)
    status3 = manager.get_status("CAM_CRASH")
    assert status3.restart_count == 3
    assert manager.calculate_backoff(status3.restart_count) == 4.0

    manager.monitor_step(current_time=t2 + 4.1)
    assert len(mock_procs) == 4
    p4 = mock_procs[3]

    # Crash 4: Exceeds max_restart_attempts -> Transitions to FAILED
    p4.simulate_crash(exit_code=1)
    manager.monitor_step(current_time=t2 + 10.0)
    status_failed = manager.get_status("CAM_CRASH")
    assert status_failed.state == StreamState.FAILED
    assert "Max restart attempts" in status_failed.last_error


def test_stable_running_resets_restart_counter():
    def mock_factory(cmd, **kwargs):
        return MockPopen(cmd, **kwargs)

    manager = StreamManager(
        stable_period_seconds=10.0,
        popen_factory=mock_factory
    )

    config = StreamConfig(camera_id="CAM_RECOVER", input_url="rtsp://localhost:8554/recover")
    manager.start_stream(config)
    handle = manager._handles["CAM_RECOVER"]
    handle.restart_count = 3  # Had previous crashes

    from datetime import timedelta
    # Fake start time 15 seconds ago (> 10s stable period)
    handle.start_time = datetime.utcnow() - timedelta(seconds=15)
    # Mock uptime inspection in monitor_step
    manager.monitor_step()
    # Still running stably -> restart count is cleared
    assert handle.restart_count == 0


# ============================================================================
# 6. JSON Configuration Loading & stop_all() Tests
# ============================================================================

def test_load_from_json_and_stop_all(tmp_path):
    procs = []

    def mock_factory(cmd, **kwargs):
        p = MockPopen(cmd, **kwargs)
        procs.append(p)
        return p

    json_content = {
        "streams": [
            {
                "camera_id": "CAM_JSON_1",
                "input_url": "rtsp://localhost:8554/json1",
                "enabled": True,
                "enable_anpr": True
            },
            {
                "camera_id": "CAM_JSON_2",
                "input_url": "rtsp://localhost:8554/json2",
                "enabled": True,
                "enable_frs": True
            },
            {
                "camera_id": "CAM_JSON_DISABLED",
                "input_url": "rtsp://localhost:8554/json3",
                "enabled": False
            }
        ]
    }

    config_file = tmp_path / "test_streams.json"
    config_file.write_text(json.dumps(json_content))

    manager = StreamManager(popen_factory=mock_factory)
    loaded_count = manager.load_from_json(str(config_file), autostart=True)
    assert loaded_count == 2  # 2 active started, 1 disabled registered
    assert len(manager.get_all_status()) == 3

    statuses = {s.camera_id: s for s in manager.get_all_status()}
    assert statuses["CAM_JSON_1"].enable_anpr is True
    assert statuses["CAM_JSON_2"].enable_frs is True
    assert statuses["CAM_JSON_DISABLED"].enabled is False

    # Test stop_all()
    manager.stop_all()
    all_statuses = manager.get_all_status()
    for s in all_statuses:
        assert s.state == StreamState.STOPPED
        assert s.process_id is None


def test_manager_monitoring_thread_start_stop():
    manager = StreamManager(popen_factory=lambda cmd, **kwargs: MockPopen(cmd))
    manager.start_monitoring(interval=0.1)
    assert manager._monitor_thread is not None
    assert manager._monitor_thread.is_alive()

    # Calling start again while alive is a no-op
    manager.start_monitoring(interval=0.1)
    assert manager._monitor_thread.is_alive()

    manager.stop_monitoring()
    assert manager._monitor_thread is None


def test_status_info_and_unregistered_camera_operations():
    manager = StreamManager()

    # Operations on unregistered cameras safely return False / None
    assert manager.stop_stream("NONEXISTENT_CAM") is False
    assert manager.restart_stream("NONEXISTENT_CAM") is False
    assert manager.get_status("NONEXISTENT_CAM") is None

    # Invalid JSON path returns 0
    assert manager.load_from_json("nonexistent_path/streams.json") == 0


def test_mask_credentials_variations():
    # RTSP with user & password
    u1 = "rtsp://user1:pwd@10.0.0.5:554/feed"
    assert mask_credentials(u1) == "rtsp://***:***@10.0.0.5:554/feed"

    # HTTP with user & password
    u2 = "http://admin:pass@camera.local/stream.mjpg"
    assert mask_credentials(u2) == "http://***:***@camera.local/stream.mjpg"

    # None and empty
    assert mask_credentials(None) == ""
    assert mask_credentials(123) == ""

