import time
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from ai_engine.pipeline.ptz.types import (
    PTZPosition,
    PTZCommand,
    PTZCommandResult,
    PTZCommandStatus,
    PTZCameraState,
    PTZConfig,
    PTZDriverType,
)
from ai_engine.pipeline.ptz.interfaces import BasePTZDriver
from ai_engine.pipeline.ptz.simulator import SimulatedPTZDriver
from ai_engine.pipeline.ptz.onvif_adapter import ONVIFPTZDriver
from ai_engine.pipeline.ptz.cue_calculator import PTZCueCalculator
from ai_engine.pipeline.ptz.controller import PTZController, ptz_controller
from ai_engine.stream_manager.types import StreamConfig
from ai_engine.pipeline.types import SpatialZoneEvent, ObjectClass
from backend.app.services.alert_engine import AlertEngine
from backend.main import app


def test_ptz_position_validation_and_clamping():
    pos = PTZPosition(pan=200.0, tilt=-110.0, zoom=45.0)
    clamped = pos.clamp(pan_min=-180.0, pan_max=180.0, tilt_min=-90.0, tilt_max=90.0, zoom_min=1.0, zoom_max=30.0)
    assert clamped.pan == 180.0
    assert clamped.tilt == -90.0
    assert clamped.zoom == 30.0

    pos2 = PTZPosition(pan=-250.0, tilt=120.0, zoom=0.5)
    clamped2 = pos2.clamp()
    assert clamped2.pan == -180.0
    assert clamped2.tilt == 90.0
    assert clamped2.zoom == 1.0


def test_ptz_command_and_result_serialization():
    cmd = PTZCommand(
        camera_id="CAM_FENCE",
        target_pan=45.5,
        target_tilt=-12.0,
        target_zoom=3.0,
        reason="auto_cue:intrusion:HIGH",
        priority="HIGH",
        track_id=101
    )
    data = cmd.to_dict()
    assert data["camera_id"] == "CAM_FENCE"
    assert data["target_pan"] == 45.5
    assert data["target_tilt"] == -12.0
    assert data["target_zoom"] == 3.0
    assert data["track_id"] == 101
    assert "command_id" in data


def test_simulated_ptz_driver_lifecycle_and_movement():
    cfg = PTZConfig(camera_id="CAM_SIM_01", ptz_enabled=True, ptz_pan_min=-180.0, ptz_pan_max=180.0)
    driver = SimulatedPTZDriver(cfg)
    assert driver.connect() is True
    assert driver.get_position().pan == 0.0

    # Execute move
    res = driver.move_to(pan=35.0, tilt=-15.0, zoom=2.5, command_id="test_cmd_1")
    assert res.status == PTZCommandStatus.SUCCESS
    assert res.position.pan == 35.0
    assert res.position.tilt == -15.0
    assert res.position.zoom == 2.5

    # Emergency stop
    assert driver.stop() is True
    status = driver.get_status()
    assert status.connection_state == "STOPPED"

    driver.disconnect()
    res_after_dc = driver.move_to(pan=10.0, tilt=10.0, zoom=1.0)
    assert res_after_dc.status == PTZCommandStatus.FAILED


def test_onvif_adapter_boundary_safeguards():
    cfg = PTZConfig(camera_id="CAM_ONVIF_01", ptz_driver="onvif", onvif_host="192.168.1.50")
    driver = ONVIFPTZDriver(cfg)
    assert driver.connect() is False
    res = driver.move_to(pan=10.0, tilt=5.0, zoom=1.0)
    assert res.status == PTZCommandStatus.REJECTED
    assert "not connected" in res.error.lower()


def test_cue_calculator_mapping_and_adaptive_zoom():
    cfg = PTZConfig(
        camera_id="CAM_TEST",
        ptz_pan_min=-180.0,
        ptz_pan_max=180.0,
        ptz_tilt_min=-90.0,
        ptz_tilt_max=90.0,
        ptz_zoom_min=1.0,
        ptz_zoom_max=30.0
    )


    # 1. Target at exact frame center (320, 240 in 640x480)
    pos_center = PTZCueCalculator.calculate_cue(
        target_bbox_or_point=(300, 220, 340, 260),
        frame_width=640,
        frame_height=480,
        config=cfg,
        severity="HIGH"
    )
    assert abs(pos_center.pan - 0.0) < 1.0
    assert abs(pos_center.tilt - 0.0) < 1.0

    # 2. Target in upper-left quadrant (far left x=0, top y=0)
    pos_top_left = PTZCueCalculator.calculate_cue(
        target_bbox_or_point=(0, 0, 40, 40),
        frame_width=640,
        frame_height=480,
        config=cfg,
        severity="HIGH"
    )
    assert pos_top_left.pan < -150.0
    assert pos_top_left.tilt > 70.0
    # Small target should trigger optical zoom
    assert pos_top_left.zoom >= 4.0

    # 3. Critical threat triggers heightened zoom
    pos_critical = PTZCueCalculator.calculate_cue(
        target_bbox_or_point=(0, 0, 20, 20),
        frame_width=640,
        frame_height=480,
        config=cfg,
        severity="CRITICAL"
    )
    assert pos_critical.zoom > pos_top_left.zoom


def test_ptz_controller_severity_policy_and_cooldown():
    controller = PTZController(default_cooldown_seconds=1.0)
    cfg = PTZConfig(camera_id="CAM_POLICY_01", ptz_enabled=True, ptz_min_severity="high", ptz_command_cooldown=1.0)
    controller.register_camera(cfg)

    # 1. LOW / MEDIUM severity should be suppressed by policy
    res_low = controller.process_threat_cue(
        camera_id="CAM_POLICY_01",
        target_bbox_or_point=(100, 100, 200, 200),
        severity="LOW",
        track_id=1,
        current_time=100.0
    )
    assert res_low is None

    # 2. HIGH severity allowed
    res_high = controller.process_threat_cue(
        camera_id="CAM_POLICY_01",
        target_bbox_or_point=(100, 100, 200, 200),
        severity="HIGH",
        track_id=1,
        current_time=100.0
    )
    assert res_high is not None
    assert res_high.status == PTZCommandStatus.SUCCESS

    # 3. Command within cooldown for same target is coalesced
    res_dup = controller.process_threat_cue(
        camera_id="CAM_POLICY_01",
        target_bbox_or_point=(102, 101, 202, 201),
        severity="HIGH",
        track_id=1,
        current_time=100.2
    )
    assert res_dup is None


def test_threat_escalation_logic():
    controller = PTZController(escalation_window_seconds=5.0, escalation_repeat_threshold=2)

    # First breach event: stays at base HIGH severity
    sev1 = controller.evaluate_threat_escalation("CAM_01", track_id=42, base_severity="HIGH", current_time=10.0)
    assert sev1 == "HIGH"

    # Second breach event within 5s window: ESCALATES to CRITICAL
    sev2 = controller.evaluate_threat_escalation("CAM_01", track_id=42, base_severity="HIGH", current_time=12.0)
    assert sev2 == "CRITICAL"

    # Event outside window resets
    sev3 = controller.evaluate_threat_escalation("CAM_01", track_id=42, base_severity="HIGH", current_time=25.0)
    assert sev3 == "HIGH"


def test_stream_config_ptz_validation_and_properties():
    cfg = StreamConfig(
        camera_id="CAM_PTZ_VALID",
        input_url="rtsp://admin:pass@192.168.1.10:554/live",
        ptz_enabled=True,
        ptz_driver="simulator",
        ptz_auto_cue=True,
        ptz_min_severity="high",
        ptz_command_cooldown=2.5,
        ptz_pan_min=-180.0,
        ptz_pan_max=180.0
    )
    assert cfg.ptz_enabled is True
    assert cfg.masked_input_url == "rtsp://***:***@192.168.1.10:554/live"

    data = cfg.to_dict()
    assert data["ptz_enabled"] is True
    assert data["ptz_driver"] == "simulator"
    assert data["ptz_command_cooldown"] == 2.5

    # Invalid pan bounds check
    with pytest.raises(ValueError, match="ptz_pan_min"):
        StreamConfig(
            camera_id="CAM_BAD",
            input_url="mock.mp4",
            ptz_pan_min=50.0,
            ptz_pan_max=-50.0
        )


def test_end_to_end_spatial_alert_to_ptz_cue():
    cfg = PTZConfig(camera_id="CAM_E2E_01", ptz_enabled=True, ptz_auto_cue=True, ptz_min_severity="high")
    ptz_controller.register_camera(cfg)

    # Set up AlertEngine
    engine = AlertEngine(publish_to_redis=False)

    event = SpatialZoneEvent(
        event_id="evt_ptz_001",
        camera_id="CAM_E2E_01",
        zone_id="ZONE_PERIMETER",
        object_class=ObjectClass.PERSON,
        track_id=88,
        position=(100.0, 150.0),
        rule_type="intrusion",
        details={"zone_name": "North Virtual Fence", "message": "Perimeter intrusion breach"}
    )

    alert = engine.process_event(event)
    assert alert is not None
    assert alert.camera_id == "CAM_E2E_01"

    # Verify controller state
    status = ptz_controller.get_camera_status("CAM_E2E_01")
    assert status is not None
    assert status.last_command_id is not None
    assert status.current_target is not None
    assert status.current_target["track_id"] == 88



def test_ptz_rest_api_endpoints():
    client = TestClient(app)

    # 1. Get PTZ status
    res = client.get("/api/v1/cameras/CAM_GATE/ptz")
    assert res.status_code == 200
    data = res.json()
    assert data["camera_id"] == "CAM_GATE"
    assert "pan" in data
    assert "tilt" in data
    assert "zoom" in data

    # 2. Manual Move command
    move_res = client.post(
        "/api/v1/cameras/CAM_GATE/ptz/move",
        json={"pan": 45.0, "tilt": -10.0, "zoom": 2.0}
    )
    assert move_res.status_code == 200
    move_data = move_res.json()
    assert move_data["status"] == "SUCCESS"
    assert move_data["position"]["pan"] == 45.0
    assert move_data["position"]["tilt"] == -10.0
    assert move_data["position"]["zoom"] == 2.0

    # 3. Emergency Stop
    stop_res = client.post("/api/v1/cameras/CAM_GATE/ptz/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "STOPPED"
