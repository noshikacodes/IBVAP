from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict, Counter
import logging
import numpy as np

from ai_engine.pipeline.anpr.types import ANPREvent, PlateDetection, OCRResult, PlateFormat
from ai_engine.pipeline.anpr.plate_detector import BasePlateDetector, PlateDetector
from ai_engine.pipeline.anpr.ocr_engine import BaseOCREngine, OCREngine
from ai_engine.pipeline.anpr.normalizer import IndianPlateNormalizer
from ai_engine.pipeline.types import TrackedEntity, ObjectClass, BoundingBox

logger = logging.getLogger("ibvap.anpr.analyzer")

VEHICLE_CLASSES = {
    ObjectClass.CAR,
    ObjectClass.TRUCK,
    ObjectClass.BUS,
    ObjectClass.MOTORCYCLE,
    ObjectClass.VEHICLE,
}


class BaseANPRAnalyzer(ABC):
    """Abstract Interface for ANPR Track Processing and Vehicle-Plate Association."""

    @abstractmethod
    def process_tracks(
        self,
        frame: np.ndarray,
        tracks: List[TrackedEntity],
        camera_id: str,
        frame_idx: int
    ) -> List[ANPREvent]:
        """Processes active vehicle tracks and produces recognized ANPREvents."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets all temporal track buffers and recognized state."""
        pass


class ANPRAnalyzer(BaseANPRAnalyzer):
    """
    Concrete ANPR Analyzer coordinating:
    1. Vehicle Track Cropping
    2. Plate Localization via BasePlateDetector
    3. Character Extraction via BaseOCREngine
    4. Deterministic Indian Plate Normalization
    5. Multi-Frame Temporal Voting & Track Consensus
    """

    def __init__(
        self,
        detector: Optional[BasePlateDetector] = None,
        ocr_engine: Optional[BaseOCREngine] = None,
        normalizer: Optional[IndianPlateNormalizer] = None,
        min_confidence: float = 0.40,
        ocr_confidence: float = 0.45,
        consensus_votes: int = 3,
        frame_stride: int = 3,
        min_vehicle_size: int = 60,
        voting_window: int = 15,
        auto_initialize: bool = True
    ):
        self.detector = detector if detector is not None else (PlateDetector() if auto_initialize else None)
        self.ocr_engine = ocr_engine if ocr_engine is not None else (OCREngine() if auto_initialize else None)
        self.normalizer = normalizer or IndianPlateNormalizer()
        self.min_confidence = min_confidence
        self.ocr_confidence = ocr_confidence
        self.consensus_votes = max(1, consensus_votes)
        self.frame_stride = max(1, frame_stride)
        self.min_vehicle_size = max(10, min_vehicle_size)
        self.voting_window = max(1, voting_window)

        # Buffer: track_id -> List[OCRResult]
        self.track_buffers: Dict[int, List[OCRResult]] = defaultdict(list)
        # Resolved consensus: track_id -> ANPREvent
        self.resolved_tracks: Dict[int, ANPREvent] = {}

    def is_vehicle(self, track: TrackedEntity) -> bool:
        """Checks if a tracked entity is a recognized vehicle class."""
        if hasattr(track, "class_name"):
            return track.class_name in VEHICLE_CLASSES
        return False

    def process_tracks(
        self,
        frame: np.ndarray,
        tracks: List[TrackedEntity],
        camera_id: str,
        frame_idx: int
    ) -> List[ANPREvent]:
        """
        Processes active vehicle tracks on the given frame.
        Skips frames not matching the configured frame stride.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or not tracks:
            return []

        # Frame stride gating
        if frame_idx % self.frame_stride != 0:
            return []

        if self.detector is None or self.ocr_engine is None:
            return []

        new_events: List[ANPREvent] = []

        for track in tracks:
            if not self.is_vehicle(track):
                continue

            # Skip if already locked with consensus plate
            if track.track_id in self.resolved_tracks:
                continue

            # Check vehicle minimum dimension threshold
            vx1, vy1, vx2, vy2 = track.current_bbox.as_int_xyxy()
            vw = max(0, vx2 - vx1)
            vh = max(0, vy2 - vy1)
            if vw < self.min_vehicle_size or vh < self.min_vehicle_size:
                continue

            # Crop vehicle ROI
            frame_h, frame_w = frame.shape[:2]
            crop_y1 = max(0, min(frame_h, vy1))
            crop_y2 = max(0, min(frame_h, vy2))
            crop_x1 = max(0, min(frame_w, vx1))
            crop_x2 = max(0, min(frame_w, vx2))
            vehicle_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            if vehicle_crop.size == 0:
                continue

            # Detect plate bounding boxes in vehicle ROI
            plate_detections = self.detector.detect_plates(
                vehicle_crop=vehicle_crop,
                confidence_threshold=self.min_confidence,
                parent_track_id=track.track_id
            )

            for p_det in plate_detections:
                px1, py1, px2, py2 = p_det.bbox.as_int_xyxy()
                p_crop_y1 = max(0, min(vehicle_crop.shape[0], py1))
                p_crop_y2 = max(0, min(vehicle_crop.shape[0], py2))
                p_crop_x1 = max(0, min(vehicle_crop.shape[1], px1))
                p_crop_x2 = max(0, min(vehicle_crop.shape[1], px2))
                plate_crop = vehicle_crop[p_crop_y1:p_crop_y2, p_crop_x1:p_crop_x2]
                if plate_crop.size == 0:
                    continue

                # Run OCR
                ocr_res = self.ocr_engine.extract_text(plate_crop)
                if ocr_res and ocr_res.is_valid and ocr_res.confidence >= self.ocr_confidence:
                    self.track_buffers[track.track_id].append(ocr_res)
                    if len(self.track_buffers[track.track_id]) > self.voting_window:
                        self.track_buffers[track.track_id].pop(0)

                    # Check multi-frame voting consensus
                    event = self._evaluate_consensus(track, camera_id, frame_idx, p_det.bbox, (crop_x1, crop_y1))
                    if event:
                        self.resolved_tracks[track.track_id] = event
                        track.extra_metadata["anpr_plate"] = event.plate_number
                        new_events.append(event)
                        break

        return new_events

    def _evaluate_consensus(
        self,
        track: TrackedEntity,
        camera_id: str,
        frame_idx: int,
        local_plate_bbox: Optional[BoundingBox] = None,
        vehicle_origin: Tuple[int, int] = (0, 0)
    ) -> Optional[ANPREvent]:
        """Computes consensus plate string from multi-frame track voting buffer."""
        buffer = self.track_buffers.get(track.track_id, [])
        if not buffer or len(buffer) < self.consensus_votes:
            return None

        # Count frequencies of normalized plate texts
        counts = Counter(res.normalized_text for res in buffer if res.is_valid)
        if not counts:
            return None

        most_common_plate, vote_count = counts.most_common(1)[0]
        if vote_count < self.consensus_votes:
            return None

        # Find matching OCRResults
        matching_results = [r for r in buffer if r.normalized_text == most_common_plate]
        avg_confidence = sum(r.confidence for r in matching_results) / len(matching_results)
        best_result = max(matching_results, key=lambda r: r.confidence)

        # Global bounding box for plate relative to frame
        global_plate_bbox = None
        if local_plate_bbox is not None:
            vox, voy = vehicle_origin
            global_plate_bbox = BoundingBox(
                local_plate_bbox.x1 + vox,
                local_plate_bbox.y1 + voy,
                local_plate_bbox.x2 + vox,
                local_plate_bbox.y2 + voy
            )

        return ANPREvent(
            camera_id=camera_id,
            track_id=track.track_id,
            plate_number=most_common_plate,
            raw_plate_text=best_result.raw_text,
            confidence=avg_confidence,
            plate_format=best_result.plate_format,
            is_valid_format=True,
            vehicle_class=track.class_name.value if hasattr(track.class_name, "value") else str(track.class_name),
            bbox=global_plate_bbox or track.current_bbox,
            position=track.current_center,
            frame_idx=frame_idx,
            metadata={
                "consensus_votes": vote_count,
                "total_observations": len(buffer),
                "vehicle_track_id": track.track_id,
            }
        )

    def reset(self) -> None:
        self.track_buffers.clear()
        self.resolved_tracks.clear()
