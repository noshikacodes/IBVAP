import os
import pytest
import numpy as np
import cv2
from datetime import datetime

from ai_engine.pipeline.gits_resolver import (
    is_gits_source,
    extract_gits_cctv_id,
    resolve_gits_hls_url,
)
from ai_engine.pipeline.detector import YOLODetector
from ai_engine.pipeline.types import TrackedEntity, ObjectClass, BoundingBox
from ai_engine.pipeline.traffic_counter import TrafficCountingEngine, TrafficCrossingEvent
from backend.app.services.camera_registry import camera_registry, resolve_live_camera_url
from backend.app.services.traffic_repository import traffic_repository


class TestGITS1809Integration:
    """Automated integration test suite for CAM_GITS_1809 (우체국4R(상행))."""

    def test_gits_1809_id_extraction_and_recognition(self):
        """Validates that 1809 is recognized as a valid GITS source across varied formats."""
        assert is_gits_source("1809") is True
        assert is_gits_source("gits://1809") is True
        assert is_gits_source("https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=1809") is True
        assert is_gits_source("https://trafficvision.live/?continent=Asia&camera=gits-1809") is True

        assert extract_gits_cctv_id("1809") == "1809"
        assert extract_gits_cctv_id("gits://1809") == "1809"
        assert extract_gits_cctv_id("https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=1809") == "1809"
        assert extract_gits_cctv_id("https://trafficvision.live/?continent=Asia&camera=gits-1809") == "1809"

    def test_camera_registry_contains_both_real_cctv_cameras(self):
        """Validates that both CAM_GITS_1809 and CAM_SEJONG_95366 are registered and independent."""
        cam_1809 = camera_registry.get("CAM_GITS_1809")
        assert cam_1809 is not None, "CAM_GITS_1809 must be registered in camera_registry"
        assert cam_1809.camera_id == "CAM_GITS_1809"
        assert cam_1809.source_url.startswith("http")
        assert cam_1809.location_metadata.get("cctv_id") == "1809"
        assert "우체국" in cam_1809.name

        cam_95366 = camera_registry.get("CAM_SEJONG_95366")
        assert cam_95366 is not None, "CAM_SEJONG_95366 must remain registered and intact"
        assert cam_95366.camera_id == "CAM_SEJONG_95366"
        assert cam_95366.source_url.startswith("http")
        assert cam_95366.location_metadata.get("cctv_id") == "95366"

    def test_gits_1809_counting_engine_configuration(self, tmp_path):
        """Validates camera-specific counting line geometry and deduplication for CAM_GITS_1809."""
        evidence_dir = str(tmp_path / "evidence")
        engine = TrafficCountingEngine(
            camera_id="CAM_GITS_1809",
            line_pt1=(120.0, 360.0),
            line_pt2=(600.0, 360.0),
            evidence_dir=evidence_dir,
            save_evidence=True
        )

        assert engine.camera_id == "CAM_GITS_1809"
        assert engine.line_pt1 == (120.0, 360.0)
        assert engine.line_pt2 == (600.0, 360.0)

        # Create synthetic track moving across line (from y=320 to y=390)
        frame = np.zeros((480, 720, 3), dtype=np.uint8)

        # Frame 1: Vehicle above counting line at y=320
        track = TrackedEntity(
            track_id=101,
            class_name=ObjectClass.CAR,
            confidence=0.88,
            current_bbox=BoundingBox(300.0, 280.0, 380.0, 320.0),
            trajectory=[(340.0, 320.0)]
        )
        events_f1 = engine.process_tracks([track], frame=frame, frame_idx=1)
        assert len(events_f1) == 0
        assert engine.counted_totals["car"] == 0

        # Frame 2: Vehicle crosses line downwards to y=390
        track.current_bbox = BoundingBox(300.0, 350.0, 380.0, 390.0)
        track.trajectory.append((340.0, 390.0))
        events_f2 = engine.process_tracks([track], frame=frame, frame_idx=2)

        assert len(events_f2) == 1
        evt = events_f2[0]
        assert evt.track_id == 101
        assert evt.camera_id == "CAM_GITS_1809"
        assert evt.object_type == "car"
        assert evt.direction == "OUT"
        assert engine.counted_totals["car"] == 1
        assert evt.snapshot_path is not None
        assert os.path.exists(evt.snapshot_path)

        # Frame 3: Same vehicle continues moving to y=430 (STRICT DEDUPLICATION TEST)
        track.current_bbox = BoundingBox(300.0, 390.0, 380.0, 430.0)
        track.trajectory.append((340.0, 430.0))
        events_f3 = engine.process_tracks([track], frame=frame, frame_idx=3)
        assert len(events_f3) == 0, "Duplicate crossing event must NOT be triggered for same vehicle track ID"
        assert engine.counted_totals["car"] == 1, "Count total must not double-count vehicle"

    def test_traffic_repository_isolation_between_cameras(self):
        """Verifies database isolation: events for 1809 do not pollute 95366 metrics."""
        cam_a = "CAM_TEST_1809"
        cam_b = "CAM_TEST_95366"

        traffic_repository.clear(cam_a)
        traffic_repository.clear(cam_b)

        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # Record event for Camera A
        evt_a = TrafficCrossingEvent(
            camera_id=cam_a,
            track_id=1,
            object_type="bus",
            timestamp=now_iso,
            direction="IN",
            confidence=0.91,
            bbox=(100.0, 200.0, 200.0, 300.0)
        )
        traffic_repository.record_event(evt_a)

        # Record event for Camera B
        evt_b = TrafficCrossingEvent(
            camera_id=cam_b,
            track_id=2,
            object_type="truck",
            timestamp=now_iso,
            direction="OUT",
            confidence=0.85,
            bbox=(150.0, 250.0, 250.0, 350.0)
        )
        traffic_repository.record_event(evt_b)

        summary_a = traffic_repository.get_analytics_summary(cam_a)
        summary_b = traffic_repository.get_analytics_summary(cam_b)

        assert summary_a["today_totals"]["bus"] == 1
        assert summary_a["today_totals"]["truck"] == 0

        assert summary_b["today_totals"]["truck"] == 1
        assert summary_b["today_totals"]["bus"] == 0

        # Teardown
        traffic_repository.clear(cam_a)
        traffic_repository.clear(cam_b)

    def test_yolo26_detector_initialization_and_inference(self):
        """Tests that YOLODetector initializes with yolo26s.pt and runs inference."""
        detector = YOLODetector(
            model_name_or_path="yolo26s.pt",
            confidence_threshold=0.25,
            device="cpu"
        )
        # Create mock BGR frame
        frame = np.zeros((480, 720, 3), dtype=np.uint8)
        # Draw a synthetic bright rectangular box resembling a vehicle
        cv2.rectangle(frame, (200, 200), (350, 300), (200, 200, 200), -1)

        detections = detector.detect(frame, track=False)
        assert isinstance(detections, list)
