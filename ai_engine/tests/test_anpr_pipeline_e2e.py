import pytest
import numpy as np
import cv2

from ai_engine.pipeline.config import InferenceConfig
from ai_engine.pipeline.types import BoundingBox, TrackedEntity, ObjectClass
from ai_engine.pipeline.anpr.types import PlateFormat, ANPREvent
from ai_engine.pipeline.anpr.plate_detector import PlateDetector
from ai_engine.pipeline.anpr.ocr_engine import OCREngine
from ai_engine.pipeline.anpr.normalizer import IndianPlateNormalizer
from ai_engine.pipeline.anpr.analyzer import ANPRAnalyzer
from ai_engine.pipeline.annotator import VideoAnnotator
from backend.app.services.alert_engine import AlertEngine
from backend.app.services.alert_repository import InMemoryAlertRepository
from backend.app.schemas.alert import Alert


def create_synthetic_vehicle_plate_frame(plate_text: str = "DL 01 AB 1234", width: int = 640, height: int = 480) -> np.ndarray:
    """Builds a frame containing a vehicle with an embedded license plate."""
    frame = np.ones((height, width, 3), dtype=np.uint8) * 35

    # Vehicle body
    vx1, vy1, vx2, vy2 = 140, 160, 500, 380
    frame[vy1:vy2, vx1:vx2] = 85

    # License plate
    pw, ph = 200, 50
    px = vx1 + (vx2 - vx1 - pw) // 2
    py = vy2 - 70
    plate_crop = np.ones((ph, pw, 3), dtype=np.uint8) * 255
    cv2.rectangle(plate_crop, (1, 1), (pw - 2, ph - 2), (0, 0, 0), 2)
    cv2.putText(plate_crop, plate_text, (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2, cv2.LINE_AA)
    frame[py:py + ph, px:px + pw] = plate_crop

    return frame


def test_anpr_analyzer_with_alert_engine_pipeline():
    """Validates the full chain: Track -> ANPR -> AlertEngine -> Alert."""
    detector = PlateDetector(confidence_threshold=0.30)
    ocr = OCREngine(engine_type="easyocr", language="en", use_gpu=False)
    normalizer = IndianPlateNormalizer()

    analyzer = ANPRAnalyzer(
        detector=detector,
        ocr_engine=ocr,
        normalizer=normalizer,
        min_confidence=0.30,
        ocr_confidence=0.30,
        consensus_votes=2,
        frame_stride=1,
        min_vehicle_size=50
    )

    repo = InMemoryAlertRepository()
    engine = AlertEngine(repository=repo, cooldown_seconds=0.0, publish_to_redis=False)

    frame = create_synthetic_vehicle_plate_frame("DL 01 AB 1234")
    car_track = TrackedEntity(
        track_id=42,
        class_name=ObjectClass.CAR,
        current_bbox=BoundingBox(140, 160, 500, 380)
    )

    # Frame 0: Vote 1
    events_0 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=0)
    assert len(events_0) == 0

    # Frame 1: Vote 2 -> Consensus reached
    events_1 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=1)
    assert len(events_1) == 1

    anpr_evt = events_1[0]
    assert anpr_evt.track_id == 42
    assert anpr_evt.plate_number == "DL01AB1234"
    assert anpr_evt.plate_format == PlateFormat.STANDARD_INDIAN
    assert car_track.extra_metadata.get("anpr_plate") == "DL01AB1234"

    # Process through AlertEngine
    alert = engine.process_anpr_event(anpr_evt)
    assert alert is not None
    assert alert.event_type == "anpr_detection"
    assert alert.severity == "low"
    assert alert.track_id == 42
    assert alert.metadata["plate_number"] == "DL01AB1234"
    assert "DL01AB1234" in alert.message

    # Verify repository storage
    stored = repo.get(alert.alert_id)
    assert stored is not None
    assert stored.metadata["plate_number"] == "DL01AB1234"


def test_video_annotator_renders_anpr_plate_badge():
    """Validates that VideoAnnotator renders license plate badges when present in TrackedEntity."""
    annotator = VideoAnnotator(draw_telemetry=False, draw_trajectories=False, draw_zones=False, draw_events=False)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    car_track = TrackedEntity(
        track_id=15,
        class_name=ObjectClass.CAR,
        current_bbox=BoundingBox(100, 100, 300, 300),
        extra_metadata={"anpr_plate": "MH12DE1433"}
    )

    annotated = annotator.annotate_frame(frame, [car_track], frame_idx=0)
    assert annotated is not None
    assert annotated.shape == (480, 640, 3)
    # Ensure drawing happened (not all zeros)
    assert np.any(annotated > 0)
