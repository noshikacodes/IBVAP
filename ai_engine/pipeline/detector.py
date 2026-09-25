import os
from typing import List, Optional, Dict, Any, Union
import numpy as np

from ai_engine.pipeline.interfaces import BaseDetector
from ai_engine.pipeline.types import Detection, BoundingBox, ObjectClass
from ai_engine.pipeline.config import DEFAULT_TARGET_CLASSES


class DetectorError(Exception):
    """Base exception for detector errors."""
    pass


class ModelLoadError(DetectorError):
    """Raised when the YOLO model cannot be loaded."""
    pass


class ModelInferenceError(DetectorError):
    """Raised when inference fails on a frame."""
    pass


class YOLODetector(BaseDetector):
    """
    Ultralytics YOLO Object Detector implementing BaseDetector.
    Provides class mapping, confidence filtering, hardware acceleration,
    and optional native ByteTrack tracking support.
    """

    def __init__(
        self,
        model_name_or_path: str = "yolo26n.pt",
        models_dir: str = "ai_engine/models_weight",
        device: str = "cpu",
        confidence_threshold: float = 0.28,
        target_classes: Optional[List[str]] = None,
        imgsz: int = 640,
        use_road_roi: bool = False,
        road_roi_ymin: float = 160.0,
        road_roi_ymax: float = 480.0
    ):
        self.model_name_or_path = model_name_or_path
        self.models_dir = os.path.abspath(models_dir)
        self.device = device.lower().strip()
        self.confidence_threshold = float(confidence_threshold)
        self.imgsz = int(imgsz)
        self.use_road_roi = bool(use_road_roi)
        self.road_roi_ymin = float(road_roi_ymin)
        self.road_roi_ymax = float(road_roi_ymax)

        if target_classes is not None:
            self.target_classes = [c.strip().lower() for c in target_classes if c.strip()]
        else:
            self.target_classes = list(DEFAULT_TARGET_CLASSES)

        self._model = None
        self._class_names: Dict[int, str] = {}

        os.makedirs(self.models_dir, exist_ok=True)
        self.load_model(self.model_name_or_path, self.device)

    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """
        Loads the Ultralytics YOLO model.
        If model_path is a standard model tag (e.g., 'yolo26n.pt'), it is resolved
        in models_dir.
        """
        try:
            from ultralytics import YOLO  # Lazy import so types/tests can import module freely
        except ImportError as e:
            raise ModelLoadError(
                "Ultralytics library is not installed. Run: pip install -r ai_engine/requirements.txt"
            ) from e

        # Determine target file path
        if not os.path.isabs(model_path) and not os.path.exists(model_path):
            target_model_file = os.path.join(self.models_dir, model_path)
            # If the weights exist in models_dir, use that path directly
            if os.path.exists(target_model_file):
                model_path = target_model_file
            elif os.path.exists(model_path):
                pass
            else:
                model_path = target_model_file

        try:
            self._model = YOLO(model_path)
            self._model.to(device)
            # Cache model class name mappings
            if hasattr(self._model, "names") and isinstance(self._model.names, dict):
                self._class_names = {k: v.lower() for k, v in self._model.names.items()}
            self.device = device
        except Exception as e:
            raise ModelLoadError(
                f"Failed to load YOLO model from '{model_path}' on device '{device}': {str(e)}"
            ) from e

    def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: Optional[float] = None,
        track: bool = False,
        tracker: str = "bytetrack.yaml"
    ) -> List[Detection]:
        """
        Runs object detection or tracking inference on a single BGR image/frame.
        Applies Road ROI cropping if configured to enhance small distant vehicles.
        """
        if self._model is None:
            raise ModelLoadError("Model is not loaded. Call load_model() first.")

        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []

        conf = confidence_threshold if confidence_threshold is not None else self.confidence_threshold

        # Road ROI extraction to focus inference resolution on roadway
        y_offset = 0.0
        inference_frame = frame
        if self.use_road_roi and frame.shape[0] >= int(self.road_roi_ymax):
            ymin = int(self.road_roi_ymin)
            ymax = int(self.road_roi_ymax)
            if ymax > ymin and ymin >= 0 and ymax <= frame.shape[0]:
                inference_frame = frame[ymin:ymax, :]
                y_offset = float(ymin)

        try:
            if track:
                results = self._model.track(
                    source=inference_frame,
                    conf=conf,
                    imgsz=self.imgsz,
                    device=self.device,
                    persist=True,
                    tracker=tracker,
                    verbose=False
                )
            else:
                results = self._model.predict(
                    source=inference_frame,
                    conf=conf,
                    imgsz=self.imgsz,
                    device=self.device,
                    verbose=False
                )
        except Exception as e:
            raise ModelInferenceError(f"Inference failed on frame: {str(e)}") from e

        detections: List[Detection] = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None:
            return detections

        boxes_data = result.boxes.data.cpu().numpy()  # [x1, y1, x2, y2, (track_id), conf, cls_id]
        has_track_ids = result.boxes.id is not None
        track_ids = result.boxes.id.int().cpu().tolist() if has_track_ids else []

        for idx, row in enumerate(boxes_data):
            if len(row) < 6:
                continue

            # When tracking is enabled, row layout might be [x1, y1, x2, y2, id, conf, cls_id] or standard with result.boxes.id
            x1, y1, x2, y2 = row[:4]
            # Offset y coordinates if Road ROI cropping was applied
            y1 += y_offset
            y2 += y_offset
            if len(row) == 7:
                box_conf = float(row[5])
                cls_idx = int(row[6])
                tid = int(row[4])
            else:
                box_conf = float(row[4])
                cls_idx = int(row[5])
                tid = track_ids[idx] if idx < len(track_ids) else None

            raw_class_name = self._class_names.get(cls_idx, f"class_{cls_idx}")

            # Check if class is in target classes
            if self.target_classes and raw_class_name not in self.target_classes:
                # Also check mapped generic name
                mapped_enum = ObjectClass.from_string(raw_class_name)
                if mapped_enum.value not in self.target_classes:
                    continue

            obj_class = ObjectClass.from_string(raw_class_name)
            bbox = BoundingBox.from_xyxy(x1, y1, x2, y2)

            detection = Detection(
                class_name=obj_class,
                confidence=box_conf,
                bbox=bbox,
                track_id=tid,
                raw_class_name=raw_class_name,
                extra_metadata={"class_id": cls_idx}
            )
            detections.append(detection)

        return detections
