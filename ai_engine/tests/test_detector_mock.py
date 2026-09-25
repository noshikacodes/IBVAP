from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from ai_engine.pipeline.detector import YOLODetector
from ai_engine.pipeline.types import ObjectClass


def test_yolo_detector_mock_inference():
    """Tests YOLODetector extraction & filtering logic using mock YOLO results."""
    with patch("ultralytics.YOLO") as MockYOLO:
        mock_model = MagicMock()
        mock_model.names = {0: "person", 2: "car", 7: "truck", 15: "cat"}
        MockYOLO.return_value = mock_model

        # Mock result structure from YOLO.predict()
        mock_result = MagicMock()
        # [x1, y1, x2, y2, conf, cls_id]
        mock_boxes_data = np.array([
            [10.0, 20.0, 50.0, 100.0, 0.85, 0.0],   # person
            [100.0, 120.0, 250.0, 200.0, 0.92, 2.0], # car
            [300.0, 300.0, 350.0, 350.0, 0.70, 15.0] # cat (should be filtered out by target_classes)
        ])
        mock_boxes = MagicMock()
        mock_boxes.data.cpu.return_value.numpy.return_value = mock_boxes_data
        mock_result.boxes = mock_boxes
        mock_model.predict.return_value = [mock_result]

        detector = YOLODetector(
            model_name_or_path="yolov8n.pt",
            target_classes=["person", "car", "truck"]
        )

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect(dummy_frame)

        # 2 detections should remain (person & car), cat should be filtered out
        assert len(detections) == 2

        det0 = detections[0]
        assert det0.class_name in (ObjectClass.PERSON, ObjectClass.HUMAN)
        assert det0.confidence == 0.85
        assert det0.bbox.as_int_xyxy() == (10, 20, 50, 100)

        det1 = detections[1]
        assert det1.class_name in (ObjectClass.CAR, ObjectClass.VEHICLE)
        assert det1.confidence == 0.92


def test_yolo_detector_empty_frame():
    with patch("ultralytics.YOLO") as MockYOLO:
        mock_model = MagicMock()
        mock_model.names = {0: "person"}
        MockYOLO.return_value = mock_model

        detector = YOLODetector(model_name_or_path="yolov8n.pt")
        # Empty array or None
        assert detector.detect(np.array([])) == []
        assert detector.detect(None) == []
