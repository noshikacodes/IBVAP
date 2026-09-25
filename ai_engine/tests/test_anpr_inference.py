import pytest
import numpy as np
import cv2

from ai_engine.pipeline.types import BoundingBox, TrackedEntity, ObjectClass
from ai_engine.pipeline.anpr.types import PlateFormat, PlateDetection, OCRResult, ANPREvent
from ai_engine.pipeline.anpr.normalizer import IndianPlateNormalizer
from ai_engine.pipeline.anpr.plate_detector import PlateDetector
from ai_engine.pipeline.anpr.ocr_engine import OCREngine
from ai_engine.pipeline.anpr.analyzer import ANPRAnalyzer


def create_synthetic_plate_image(text: str = "DL 01 AB 1234", width: int = 220, height: int = 50) -> np.ndarray:
    """Generates a clean synthetic license plate image with white background and black text."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (1, 1), (width - 2, height - 2), (0, 0, 0), 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.65
    thickness = 2
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = max(6, (width - text_size[0]) // 2)
    text_y = (height + text_size[1]) // 2
    cv2.putText(img, text, (text_x, text_y), font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)
    return img


def create_synthetic_vehicle_with_plate(plate_text: str = "DL 01 AB 1234", v_w: int = 320, v_h: int = 200) -> np.ndarray:
    """Generates a synthetic vehicle image with an embedded license plate in the lower bumper region."""
    v_img = np.ones((v_h, v_w, 3), dtype=np.uint8) * 70  # Dark gray car body
    p_w, p_h = 180, 44
    plate = create_synthetic_plate_image(plate_text, width=p_w, height=p_h)
    p_x = (v_w - p_w) // 2
    p_y = v_h - 60
    v_img[p_y:p_y + p_h, p_x:p_x + p_w] = plate
    return v_img


# ============================================================================
# Concrete OCR Tests
# ============================================================================

def test_ocr_engine_synthetic_plate_reading():
    ocr = OCREngine(engine_type="easyocr", language="en", use_gpu=False)
    assert ocr.is_initialized is True

    plate_crop = create_synthetic_plate_image("DL 01 AB 1234", width=220, height=50)
    result = ocr.extract_text(plate_crop)

    assert result is not None
    assert result.is_valid is True
    assert result.normalized_text == "DL01AB1234"
    assert result.plate_format == PlateFormat.STANDARD_INDIAN
    assert result.confidence > 0.40


def test_ocr_engine_bh_series_plate_reading():
    ocr = OCREngine(engine_type="easyocr", language="en", use_gpu=False)
    plate_crop = create_synthetic_plate_image("22 BH 1234 AA", width=220, height=50)
    result = ocr.extract_text(plate_crop)

    assert result is not None
    assert result.is_valid is True
    assert result.normalized_text == "22BH1234AA"
    assert result.plate_format == PlateFormat.BH_SERIES


def test_ocr_engine_blank_image_handling():
    ocr = OCREngine(engine_type="easyocr", language="en", use_gpu=False)
    blank = np.zeros((60, 240, 3), dtype=np.uint8)
    result = ocr.extract_text(blank)

    assert result.raw_text == ""
    assert result.normalized_text == ""
    assert result.is_valid is False


# ============================================================================
# Concrete Plate Detector Tests
# ============================================================================

def test_plate_detector_on_vehicle_crop():
    detector = PlateDetector(confidence_threshold=0.30)
    vehicle_img = create_synthetic_vehicle_with_plate("MH 12 DE 1433", v_w=320, v_h=200)

    detections = detector.detect_plates(vehicle_img, parent_track_id=10)
    assert isinstance(detections, list)
    assert len(detections) > 0

    det = detections[0]
    assert det.parent_track_id == 10
    assert det.bbox.width > 20
    assert det.bbox.height > 10
    assert det.bbox.y2 <= 200


def test_plate_detector_invalid_input_graceful():
    detector = PlateDetector()
    assert detector.detect_plates(None) == []
    assert detector.detect_plates(np.zeros((10, 10, 3), dtype=np.uint8)) == []


# ============================================================================
# Concrete ANPR Analyzer End-to-End Tests
# ============================================================================

def test_anpr_analyzer_end_to_end_on_synthetic_stream():
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

    # Build 640x480 frame with vehicle containing "DL 01 AB 1234"
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 40
    vehicle = create_synthetic_vehicle_with_plate("DL 01 AB 1234", v_w=320, v_h=200)
    vx1, vy1 = 150, 140
    frame[vy1:vy1 + 200, vx1:vx1 + 320] = vehicle

    car_track = TrackedEntity(
        track_id=12,
        class_name=ObjectClass.CAR,
        current_bbox=BoundingBox(vx1, vy1, vx1 + 320, vy1 + 200)
    )

    # Frame 0: Vote 1
    events_0 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=0)
    assert len(events_0) == 0

    # Frame 1: Vote 2 -> Consensus reached (votes >= 2)
    events_1 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=1)
    assert len(events_1) == 1

    event = events_1[0]
    assert event.camera_id == "CAM_01"
    assert event.track_id == 12
    assert event.plate_number == "DL01AB1234"
    assert event.plate_format == PlateFormat.STANDARD_INDIAN
    assert event.is_valid_format is True
    assert car_track.extra_metadata["anpr_plate"] == "DL01AB1234"
