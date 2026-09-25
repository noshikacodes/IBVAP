import os
import logging
from typing import List, Optional, Any
import numpy as np
import cv2

from ai_engine.pipeline.interfaces import BaseFaceDetector
from ai_engine.pipeline.types import BoundingBox
from ai_engine.pipeline.face.types import FaceDetection

logger = logging.getLogger("ibvap.face.detector")


class FaceDetector(BaseFaceDetector):
    """
    Lightweight CPU-friendly Face Detector implementing BaseFaceDetector.
    Uses YOLOv8n-Face weights for accurate face localization within person ROI crops.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cpu",
        confidence_threshold: float = 0.50,
        min_face_size: int = 32
    ):
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.min_face_size = min_face_size
        self.model = None
        self.model_path = model_path

        if model_path:
            self.load_model(model_path, device=device)

    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads and initializes YOLO face detector model weights."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Face detector model file not found: {model_path}")

        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.device = device
            self.model_path = model_path
            logger.info(f"Loaded YOLO face detector weights from {model_path} on {device}")
        except Exception as e:
            logger.error(f"Failed to load YOLO face detector weights from {model_path}: {e}")
            raise RuntimeError(f"Failed to initialize FaceDetector: {e}")

    def detect_faces(
        self,
        person_crop: np.ndarray,
        confidence_threshold: Optional[float] = None
    ) -> List[FaceDetection]:
        """
        Detects faces within a cropped person image ROI.
        Returns a list of FaceDetection instances.
        """
        if person_crop is None or person_crop.size == 0 or self.model is None:
            return []

        h, w = person_crop.shape[:2]
        if h < self.min_face_size or w < self.min_face_size:
            return []

        conf_thresh = confidence_threshold if confidence_threshold is not None else self.confidence_threshold

        try:
            results = self.model.predict(
                source=person_crop,
                conf=conf_thresh,
                device=self.device,
                verbose=False
            )
        except Exception as e:
            logger.warning(f"Face detector inference failed on crop: {e}")
            return []

        detections: List[FaceDetection] = []
        if not results or len(results) == 0:
            return detections

        res = results[0]
        if res.boxes is None or len(res.boxes) == 0:
            return detections

        boxes = res.boxes.xyxy.cpu().numpy()
        confs = res.boxes.conf.cpu().numpy()

        for i in range(len(boxes)):
            box = boxes[i]
            conf = float(confs[i])
            if conf < conf_thresh:
                continue

            x1, y1, x2, y2 = map(int, box)
            # Clip bounds to image dimensions
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            x2 = max(0, min(w, x2))
            y2 = max(0, min(h, y2))

            bw = x2 - x1
            bh = y2 - y1

            if bw < self.min_face_size or bh < self.min_face_size:
                continue

            face_crop = person_crop[y1:y2, x1:x2].copy()
            bbox = BoundingBox(x1, y1, x2, y2)

            detections.append(
                FaceDetection(
                    bbox=bbox,
                    confidence=conf,
                    crop=face_crop,
                    metadata={"crop_resolution": (bw, bh)}
                )
            )

        return detections
