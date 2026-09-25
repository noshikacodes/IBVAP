import os
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
import numpy as np
import cv2

from ai_engine.pipeline.anpr.types import PlateDetection
from ai_engine.pipeline.types import BoundingBox

logger = logging.getLogger("ibvap.anpr.detector")


class BasePlateDetector(ABC):
    """Abstract Interface for License Plate Detectors (YOLO-plate, ONNX, etc.)."""

    @abstractmethod
    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads and initializes plate localization model weights."""
        pass

    @abstractmethod
    def detect_plates(
        self,
        vehicle_crop: np.ndarray,
        confidence_threshold: float = 0.40,
        parent_track_id: Optional[int] = None
    ) -> List[PlateDetection]:
        """
        Detects license plate regions within a vehicle crop image.
        Returns a list of PlateDetection objects with bounding boxes relative to the vehicle crop.
        """
        pass


class PlateDetector(BasePlateDetector):
    """
    Concrete License Plate Detector for Phase 5B.2.
    Supports:
    1. Ultralytics YOLO custom plate weights (when *.pt is provided).
    2. High-gradient morphological plate ROI localization fallback on vehicle lower-quadrant crops.
    """

    def __init__(
        self,
        model_name_or_path: str = "yolov8n_plate.pt",
        models_dir: str = "ai_engine/models_weight",
        device: str = "cpu",
        confidence_threshold: float = 0.40
    ):
        self.model_name_or_path = model_name_or_path
        self.models_dir = models_dir
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.is_loaded = False

        # Attempt to load model if path exists
        resolved_path = self._resolve_model_path(model_name_or_path)
        if resolved_path and os.path.exists(resolved_path):
            self.load_model(resolved_path, device=device)

    def _resolve_model_path(self, model_name_or_path: str) -> Optional[str]:
        """Resolves absolute path to weights file."""
        if not model_name_or_path:
            return None
        if os.path.isabs(model_name_or_path) and os.path.exists(model_name_or_path):
            return model_name_or_path
        candidate = os.path.join(self.models_dir, os.path.basename(model_name_or_path))
        if os.path.exists(candidate):
            return candidate
        if os.path.exists(model_name_or_path):
            return os.path.abspath(model_name_or_path)
        return None

    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads Ultralytics YOLO plate detector model."""
        self.device = device
        self.model_name_or_path = model_path
        if os.path.exists(model_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                self.is_loaded = True
                logger.info("Loaded YOLO plate detector weights from %s on %s", model_path, device)
            except Exception as e:
                logger.warning("Failed to load YOLO plate model from %s: %s. Using heuristic fallback.", model_path, e)
                self.model = None
                self.is_loaded = False
        else:
            logger.debug("Plate detector weights not found at %s. Morphological fallback active.", model_path)
            self.model = None
            self.is_loaded = False

    def detect_plates(
        self,
        vehicle_crop: np.ndarray,
        confidence_threshold: Optional[float] = None,
        parent_track_id: Optional[int] = None
    ) -> List[PlateDetection]:
        """
        Runs license plate detection within a vehicle bounding box crop.
        Returns plate detections relative to vehicle crop coordinates.
        """
        if vehicle_crop is None or not isinstance(vehicle_crop, np.ndarray) or vehicle_crop.size == 0:
            return []

        h, w = vehicle_crop.shape[:2]
        if h < 30 or w < 30:
            return []

        conf = confidence_threshold if confidence_threshold is not None else self.confidence_threshold

        # Branch 1: Deep YOLO model inference if loaded
        if self.model is not None:
            try:
                results = self.model(
                    vehicle_crop,
                    conf=conf,
                    verbose=False,
                    device=self.device
                )
                detections: List[PlateDetection] = []
                for r in results:
                    boxes = r.boxes
                    if boxes is None or len(boxes) == 0:
                        continue
                    for box in boxes:
                        score = float(box.conf[0].cpu().numpy())
                        if score < conf:
                            continue
                        xyxy = box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                        # Clamp
                        x1 = max(0.0, min(float(w), x1))
                        y1 = max(0.0, min(float(h), y1))
                        x2 = max(0.0, min(float(w), x2))
                        y2 = max(0.0, min(float(h), y2))
                        if (x2 - x1) >= 15 and (y2 - y1) >= 8:
                            plate_roi = vehicle_crop[int(y1):int(y2), int(x1):int(x2)]
                            detections.append(
                                PlateDetection(
                                    bbox=BoundingBox(x1, y1, x2, y2),
                                    confidence=score,
                                    parent_track_id=parent_track_id,
                                    crop=plate_roi,
                                    metadata={"source": "yolo_plate_model"}
                                )
                            )
                if detections:
                    return detections
            except Exception as e:
                logger.debug("YOLO plate inference error: %s. Falling back to morphology.", e)

        # Branch 2: Heuristic / Morphological plate candidate detection on vehicle crop
        return self._detect_plates_morphological(vehicle_crop, conf=conf, parent_track_id=parent_track_id)

    def _detect_plates_morphological(
        self,
        vehicle_crop: np.ndarray,
        conf: float = 0.40,
        parent_track_id: Optional[int] = None
    ) -> List[PlateDetection]:
        """
        Locates rectangular, high-contrast license plate regions in the lower 60% of vehicle crop.
        """
        h, w = vehicle_crop.shape[:2]
        # Restrict search to bottom 65% of vehicle (where bumper and plates are located)
        y_offset = int(h * 0.35)
        search_region = vehicle_crop[y_offset:, :]
        if search_region.size == 0:
            return []

        try:
            gray = cv2.cvtColor(search_region, cv2.COLOR_BGR2GRAY) if len(search_region.shape) == 3 else search_region
            # Bilateral filter to reduce noise while preserving edges
            blurred = cv2.bilateralFilter(gray, 9, 75, 75)
            # Morphological black-hat / top-hat gradient to highlight embossed plate characters
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
            grad = cv2.morphologyEx(blurred, cv2.MORPH_GRADIENT, kernel)
            _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            candidates: List[PlateDetection] = []
            vehicle_area = float(w * h)

            for cnt in contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect_ratio = cw / float(max(1, ch))
                area = cw * ch
                area_ratio = area / vehicle_area

                # Indian plates standard aspect ratio is between 1.5 and 6.0
                # Plate area should occupy roughly 0.5% to 35% of vehicle crop
                if 1.5 <= aspect_ratio <= 6.0 and 0.005 <= area_ratio <= 0.35:
                    px1 = max(0.0, float(x))
                    py1 = max(0.0, float(y + y_offset))
                    px2 = min(float(w), float(x + cw))
                    py2 = min(float(h), float(y + y_offset + ch))
                    plate_crop = vehicle_crop[int(py1):int(py2), int(px1):int(px2)]
                    if plate_crop.size > 0:
                        candidates.append(
                            PlateDetection(
                                bbox=BoundingBox(px1, py1, px2, py2),
                                confidence=0.55,
                                parent_track_id=parent_track_id,
                                crop=plate_crop,
                                metadata={"source": "morphological_locator"}
                            )
                        )

            # Return at most top 2 candidate plate regions sorted by aspect ratio fit (closer to 3.5)
            candidates.sort(key=lambda d: abs((d.bbox.width / max(1.0, d.bbox.height)) - 3.5))
            return candidates[:2]
        except Exception as e:
            logger.debug("Morphological plate localization error: %s", e)
            return []
