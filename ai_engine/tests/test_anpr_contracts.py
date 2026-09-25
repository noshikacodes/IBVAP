import pytest
import numpy as np
from datetime import datetime

from ai_engine.pipeline.types import BoundingBox, TrackedEntity, ObjectClass, TrackState
from ai_engine.pipeline.interfaces import (
    BasePlateDetector,
    BaseOCREngine,
    BaseANPRAnalyzer,
)
from ai_engine.pipeline.config import InferenceConfig
from ai_engine.pipeline.anpr.types import (
    PlateFormat,
    PlateDetection,
    OCRResult,
    ANPREvent,
)
from ai_engine.pipeline.anpr.normalizer import (
    IndianPlateNormalizer,
    normalize_plate_text,
    validate_indian_plate,
)
from ai_engine.pipeline.anpr.plate_detector import PlateDetector
from ai_engine.pipeline.anpr.ocr_engine import OCREngine
from ai_engine.pipeline.anpr.analyzer import ANPRAnalyzer


# ============================================================================
# 1. Data Model Tests (PlateDetection, OCRResult, ANPREvent, PlateFormat)
# ============================================================================

def test_plate_detection_creation():
    bbox = BoundingBox(10.0, 20.0, 110.0, 60.0)
    detection = PlateDetection(
        bbox=bbox,
        confidence=0.88,
        parent_track_id=7,
        metadata={"detector": "yolov8n_plate"}
    )

    assert detection.bbox.width == 100.0
    assert detection.bbox.height == 40.0
    assert detection.confidence == 0.88
    assert detection.parent_track_id == 7

    d_dict = detection.to_dict()
    assert d_dict["confidence"] == 0.88
    assert d_dict["parent_track_id"] == 7
    assert d_dict["bbox"] == (10.0, 20.0, 100.0, 40.0)


def test_ocr_result_creation():
    result = OCRResult(
        raw_text="DL-01-AB-1234",
        normalized_text="DL01AB1234",
        confidence=0.92,
        plate_format=PlateFormat.STANDARD_INDIAN,
        is_valid=True,
        character_confidences=[0.95, 0.94, 0.91, 0.90, 0.96, 0.95, 0.93, 0.92, 0.91, 0.89]
    )

    assert result.raw_text == "DL-01-AB-1234"
    assert result.normalized_text == "DL01AB1234"
    assert result.confidence == 0.92
    assert result.plate_format == PlateFormat.STANDARD_INDIAN
    assert result.is_valid is True
    assert len(result.character_confidences) == 10

    r_dict = result.to_dict()
    assert r_dict["normalized_text"] == "DL01AB1234"
    assert r_dict["plate_format"] == "standard_indian"
    assert r_dict["is_valid"] is True


def test_anpr_event_creation_and_field_preservation():
    bbox = BoundingBox(100.0, 200.0, 300.0, 400.0)
    now = datetime.utcnow()

    event = ANPREvent(
        camera_id="CAM_NORTH_01",
        track_id=14,
        plate_number="MH12DE1433",
        raw_plate_text="MH 12 DE 1433",
        confidence=0.945,
        plate_format=PlateFormat.STANDARD_INDIAN,
        is_valid_format=True,
        vehicle_class="car",
        bbox=bbox,
        position=(200.0, 300.0),
        frame_idx=42,
        timestamp=now,
        metadata={"source": "anpr_pipeline"}
    )

    # Validate essential field preservation
    assert event.camera_id == "CAM_NORTH_01"
    assert event.track_id == 14
    assert event.plate_number == "MH12DE1433"
    assert event.raw_plate_text == "MH 12 DE 1433"
    assert event.confidence == 0.945
    assert event.plate_format == PlateFormat.STANDARD_INDIAN
    assert event.is_valid_format is True
    assert event.vehicle_class == "car"
    assert event.frame_idx == 42
    assert event.position == (200.0, 300.0)
    assert event.timestamp == now

    e_dict = event.to_dict()
    assert e_dict["camera_id"] == "CAM_NORTH_01"
    assert e_dict["track_id"] == 14
    assert e_dict["plate_number"] == "MH12DE1433"
    assert e_dict["plate_format"] == "standard_indian"
    assert e_dict["confidence"] == 0.945
    assert e_dict["event_type"] == "anpr_detection"


# ============================================================================
# 2. Indian Plate Normalization & Validation Tests
# ============================================================================

def test_normalize_plate_text_cleanups():
    normalizer = IndianPlateNormalizer()

    # Uppercase conversion
    assert normalizer.normalize("dl01ab1234") == "DL01AB1234"

    # Whitespace stripping (outer, inner, multiple spaces, tabs)
    assert normalizer.normalize("  MH   12   DE   1433  \t") == "MH12DE1433"

    # Separator removal (hyphens, dots, colons, underscores, slashes)
    assert normalizer.normalize("DL-01-AB-1234") == "DL01AB1234"
    assert normalizer.normalize("KA.05.M.9999") == "KA05M9999"
    assert normalizer.normalize("HR:26_DQ/5555") == "HR26DQ5555"
    assert normalizer.normalize("UP|16,Z'0001\"") == "UP16Z0001"

    # Leading IND country code prefix stripping
    assert normalizer.normalize("IND DL 01 AB 1234") == "DL01AB1234"
    assert normalizer.normalize("IND-MH12DE1433") == "MH12DE1433"

    # Empty and None handling
    assert normalizer.normalize("") == ""
    assert normalizer.normalize(None) == ""


def test_validate_standard_indian_plates():
    normalizer = IndianPlateNormalizer()

    valid_plates = [
        "DL01AB1234",
        "MH12DE1433",
        "KA05M9999",
        "HR26DQ5555",
        "UP16Z0001",
        "DL1C1234",     # Single digit RTO
        "WB02AB1234",
        "TN09AZ4321",
    ]

    for plate in valid_plates:
        is_valid, p_format = normalizer.validate(plate)
        assert is_valid is True, f"Failed validation on valid plate: {plate}"
        assert p_format == PlateFormat.STANDARD_INDIAN


def test_validate_bharat_series_plates():
    normalizer = IndianPlateNormalizer()

    valid_bh_plates = [
        "22BH1234AA",
        "23BH9876Z",
        "21BH0001AB",
        "24BH5555C"
    ]

    for plate in valid_bh_plates:
        is_valid, p_format = normalizer.validate(plate)
        assert is_valid is True, f"Failed validation on BH plate: {plate}"
        assert p_format == PlateFormat.BH_SERIES


def test_validate_invalid_plates():
    normalizer = IndianPlateNormalizer()

    invalid_plates = [
        "123456",
        "ABCD",
        "DL01",
        "INVALID_PLATE",
        "1234DL5678",
        "",
        None,
    ]

    for plate in invalid_plates:
        is_valid, p_format = normalizer.validate(plate)
        assert is_valid is False
        assert p_format == PlateFormat.UNKNOWN


def test_normalizer_process_method():
    normalizer = IndianPlateNormalizer()

    # Valid raw text with punctuation
    res1 = normalizer.process("  ind-mh.12-de 1433 ", confidence=0.95)
    assert res1.normalized_text == "MH12DE1433"
    assert res1.is_valid is True
    assert res1.plate_format == PlateFormat.STANDARD_INDIAN
    assert res1.confidence == 0.95

    # Invalid garbage text
    res2 = normalizer.process("random text", confidence=0.40)
    assert res2.normalized_text == "RANDOMTEXT"
    assert res2.is_valid is False
    assert res2.plate_format == PlateFormat.UNKNOWN


# ============================================================================
# 3. Configuration Defaults & Validation Tests
# ============================================================================

def test_inference_config_anpr_defaults():
    config = InferenceConfig(
        input_path="mock_streams/sample_patrol.mp4",
        output_path="mock_streams/out.mp4"
    )

    # Check ANPR defaults
    assert config.enable_anpr is False
    assert config.anpr_detector_model == "yolov8n_plate.pt"
    assert config.anpr_ocr_engine == "paddleocr"
    assert config.anpr_min_conf == 0.60
    assert config.anpr_consensus_votes == 3
    assert config.anpr_frame_stride == 3
    assert config.anpr_min_vehicle_size == 60
    assert config.anpr_ocr_confidence == 0.50
    assert config.anpr_voting_window_frames == 15


def test_inference_config_anpr_validations():
    base_args = {
        "input_path": "mock_streams/sample_patrol.mp4",
        "output_path": "mock_streams/out.mp4"
    }

    # Invalid confidence (< 0 or > 1)
    with pytest.raises(ValueError, match="anpr_min_conf must be between 0.0 and 1.0"):
        InferenceConfig(**base_args, anpr_min_conf=-0.1)

    with pytest.raises(ValueError, match="anpr_min_conf must be between 0.0 and 1.0"):
        InferenceConfig(**base_args, anpr_min_conf=1.5)

    # Invalid OCR confidence
    with pytest.raises(ValueError, match="anpr_ocr_confidence must be between 0.0 and 1.0"):
        InferenceConfig(**base_args, anpr_ocr_confidence=2.0)

    # Invalid consensus votes (< 1)
    with pytest.raises(ValueError, match="anpr_consensus_votes must be >= 1"):
        InferenceConfig(**base_args, anpr_consensus_votes=0)

    # Invalid frame stride (< 1)
    with pytest.raises(ValueError, match="anpr_frame_stride must be >= 1"):
        InferenceConfig(**base_args, anpr_frame_stride=0)

    # Invalid min vehicle size (< 10)
    with pytest.raises(ValueError, match="anpr_min_vehicle_size must be >= 10"):
        InferenceConfig(**base_args, anpr_min_vehicle_size=5)

    # Invalid voting window (< 1)
    with pytest.raises(ValueError, match="anpr_voting_window_frames must be >= 1"):
        InferenceConfig(**base_args, anpr_voting_window_frames=0)


# ============================================================================
# 4. Interface Compatibility & Contract Implementation Tests
# ============================================================================

def test_abstract_interfaces_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BasePlateDetector()  # Abstract class

    with pytest.raises(TypeError):
        BaseOCREngine()      # Abstract class

    with pytest.raises(TypeError):
        BaseANPRAnalyzer()   # Abstract class


def test_plate_detector_contract_stub():
    detector = PlateDetector(model_name_or_path="yolov8n_plate.pt")
    # Empty frame handles gracefully
    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
    assert detector.detect_plates(empty_crop) == []

    # Blank flat synthetic crop with no plate features returns empty list
    synthetic_crop = np.zeros((100, 200, 3), dtype=np.uint8)
    detections = detector.detect_plates(synthetic_crop)
    assert isinstance(detections, list)
    assert len(detections) == 0


def test_ocr_engine_contract_stub():
    engine = OCREngine(engine_type="paddleocr")
    engine.initialize(language="en", use_gpu=False)
    assert engine.is_initialized is True

    # Empty crop
    empty_crop = np.zeros((0, 0, 3), dtype=np.uint8)
    res_empty = engine.extract_text(empty_crop)
    assert res_empty.raw_text == ""
    assert res_empty.is_valid is False

    # Synthetic crop
    synthetic_crop = np.zeros((50, 150, 3), dtype=np.uint8)
    res = engine.extract_text(synthetic_crop)
    assert isinstance(res, OCRResult)
    assert res.raw_text == ""


def test_anpr_analyzer_contract_stub_and_vehicle_check():
    analyzer = ANPRAnalyzer(
        min_confidence=0.60,
        consensus_votes=3,
        frame_stride=1,
        min_vehicle_size=40
    )

    # Test vehicle type verification
    car_track = TrackedEntity(track_id=1, class_name=ObjectClass.CAR, current_bbox=BoundingBox(0, 0, 100, 100))
    person_track = TrackedEntity(track_id=2, class_name=ObjectClass.PERSON, current_bbox=BoundingBox(0, 0, 50, 100))

    assert analyzer.is_vehicle(car_track) is True
    assert analyzer.is_vehicle(person_track) is False

    # Process frame with stub components
    synthetic_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    events = analyzer.process_tracks(
        frame=synthetic_frame,
        tracks=[car_track, person_track],
        camera_id="CAM_01",
        frame_idx=0
    )
    assert events == []


def test_anpr_analyzer_temporal_consensus_logic():
    """Tests the multi-frame temporal voting consensus mechanism using mocked detections."""
    class MockPlateDetector(BasePlateDetector):
        def load_model(self, model_path: str, device: str = "cpu") -> None:
            pass
        def detect_plates(self, vehicle_crop: np.ndarray, confidence_threshold: float = 0.40, parent_track_id = None):
            return [PlateDetection(bbox=BoundingBox(10, 10, 90, 40), confidence=0.90, parent_track_id=parent_track_id)]

    class MockOCREngine(BaseOCREngine):
        def __init__(self, responses):
            self.responses = list(responses)
            self.idx = 0
        def initialize(self, language: str = "en", use_gpu: bool = False) -> None:
            pass
        def extract_text(self, plate_crop: np.ndarray):
            text = self.responses[min(self.idx, len(self.responses) - 1)]
            self.idx += 1
            normalizer = IndianPlateNormalizer()
            return normalizer.process(text, confidence=0.92)

    # Sequence of 4 OCR readings: 3 consistent ("MH12DE1433") and 1 noise reading ("MH120E1433")
    ocr_mock = MockOCREngine(["MH-12-DE-1433", "MH 12 DE 1433", "MH-12-0E-1433", "MH12DE1433"])
    detector_mock = MockPlateDetector()

    analyzer = ANPRAnalyzer(
        detector=detector_mock,
        ocr_engine=ocr_mock,
        min_confidence=0.60,
        consensus_votes=3,
        frame_stride=1,
        min_vehicle_size=20
    )

    car_track = TrackedEntity(
        track_id=8,
        class_name=ObjectClass.CAR,
        current_bbox=BoundingBox(50, 50, 200, 200)
    )
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 200

    # Frame 0: Vote 1 (no consensus yet)
    events_f0 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=0)
    assert len(events_f0) == 0
    assert 8 not in analyzer.resolved_tracks

    # Frame 1: Vote 2 (no consensus yet)
    events_f1 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=1)
    assert len(events_f1) == 0

    # Frame 2: Outlier Vote ("MH120E1433" - invalid format)
    events_f2 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=2)
    assert len(events_f2) == 0

    # Frame 3: Vote 3 for "MH12DE1433" -> Consensus reached!
    events_f3 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=3)
    assert len(events_f3) == 1

    event = events_f3[0]
    assert event.camera_id == "CAM_01"
    assert event.track_id == 8
    assert event.plate_number == "MH12DE1433"
    assert event.plate_format == PlateFormat.STANDARD_INDIAN
    assert event.is_valid_format is True
    assert car_track.extra_metadata["anpr_plate"] == "MH12DE1433"

    # Subsequent frame should skip since track is already resolved
    events_f4 = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=4)
    assert len(events_f4) == 0

    # Reset
    analyzer.reset()
    assert len(analyzer.track_buffers) == 0
    assert len(analyzer.resolved_tracks) == 0
