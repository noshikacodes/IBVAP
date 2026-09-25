import os
import logging
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Set, Tuple
import numpy as np

from ai_engine.pipeline.interfaces import BaseFaceAnalyzer
from ai_engine.pipeline.types import TrackedEntity, ObjectClass, BoundingBox
from ai_engine.pipeline.face.types import (
    FaceDetection,
    FaceEmbedding,
    FaceIdentityMatch,
    FaceEvent,
)
from ai_engine.pipeline.face.detector import FaceDetector
from ai_engine.pipeline.face.recognizer import FaceRecognizer
from ai_engine.pipeline.face.matcher import (
    BaseFaceMatcher,
    CosineFaceMatcher,
    GalleryManager,
)

logger = logging.getLogger("ibvap.face.analyzer")

PERSON_CLASSES = {
    ObjectClass.PERSON,
    ObjectClass.HUMAN,
}


class FaceAnalyzer(BaseFaceAnalyzer):
    """
    Concrete Face Recognition System (FRS) Analyzer coordinating:
    1. Person Track upper-body ROI cropping
    2. Face localization via BaseFaceDetector (YOLOv8n-Face)
    3. 512-D ArcFace feature embedding via BaseFaceRecognizer (MobileFaceNet)
    4. Fast vectorized cosine similarity matching against Gallery
    5. Multi-frame temporal consensus voting & track locking
    6. FaceEvent emission & deduplication
    """

    def __init__(
        self,
        detector: Optional[FaceDetector] = None,
        recognizer: Optional[FaceRecognizer] = None,
        matcher: Optional[BaseFaceMatcher] = None,
        gallery: Optional[GalleryManager] = None,
        confidence_threshold: float = 0.50,
        match_threshold: float = 0.65,
        consensus_votes: int = 3,
        frame_stride: int = 3,
        min_face_size: int = 32,
        voting_window: int = 15,
        unknown_enabled: bool = True,
        auto_initialize: bool = True,
        detector_model_path: Optional[str] = None,
        recognizer_model_path: Optional[str] = None,
        gallery_path: Optional[str] = None,
    ):
        self.confidence_threshold = float(confidence_threshold)
        self.match_threshold = float(match_threshold)
        self.consensus_votes = max(1, int(consensus_votes))
        self.frame_stride = max(1, int(frame_stride))
        self.min_face_size = max(10, int(min_face_size))
        self.voting_window = max(1, int(voting_window))
        self.unknown_enabled = bool(unknown_enabled)

        # Initialize detector
        if detector is not None:
            self.detector = detector
        elif auto_initialize:
            det_path = detector_model_path or "ai_engine/models_weight/yolov8n_face.pt"
            if os.path.exists(det_path):
                self.detector = FaceDetector(
                    model_path=det_path,
                    device="cpu",
                    confidence_threshold=self.confidence_threshold,
                    min_face_size=self.min_face_size
                )
            else:
                self.detector = None
        else:
            self.detector = None

        # Initialize recognizer
        if recognizer is not None:
            self.recognizer = recognizer
        elif auto_initialize:
            rec_path = recognizer_model_path or "ai_engine/models_weight/mobilefacenet_arcface.onnx"
            if os.path.exists(rec_path):
                self.recognizer = FaceRecognizer(
                    model_path=rec_path,
                    device="cpu"
                )
            else:
                self.recognizer = None
        else:
            self.recognizer = None

        # Initialize gallery & matcher
        if matcher is not None:
            self.matcher = matcher
        else:
            gal = gallery if gallery is not None else GalleryManager(expected_dim=512)
            if gallery_path and os.path.exists(gallery_path):
                enrolled = gal.load_from_json(gallery_path)
                logger.info(f"Loaded {enrolled} enrolled face profiles from {gallery_path}")
            self.matcher = CosineFaceMatcher(gallery=gal, default_threshold=self.match_threshold)

        # Temporal voting buffers: track_id -> List[FaceIdentityMatch]
        self.track_buffers: Dict[int, List[FaceIdentityMatch]] = defaultdict(list)
        # Resolved consensus: track_id -> FaceEvent
        self.resolved_tracks: Dict[int, FaceEvent] = {}
        # Emitted alert tracks (to prevent alert duplicate spam)
        self.alerted_tracks: Set[int] = set()

    def is_person(self, track: TrackedEntity) -> bool:
        """Checks if a tracked entity is a person/human class."""
        if hasattr(track, "class_name"):
            if track.class_name in PERSON_CLASSES:
                return True
            cls_str = str(track.class_name.value if hasattr(track.class_name, "value") else track.class_name).lower()
            return cls_str in ("person", "human")
        return False

    def process_tracks(
        self,
        frame: np.ndarray,
        tracks: List[TrackedEntity],
        camera_id: str,
        frame_idx: int
    ) -> List[FaceEvent]:
        """
        Processes active person tracks on the given frame.
        Skips frames not matching the configured frame stride.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or not tracks:
            return []

        # Maintain existing attached identity for already resolved tracks
        for track in tracks:
            if track.track_id in self.resolved_tracks:
                res = self.resolved_tracks[track.track_id]
                track.extra_metadata["frs_identity"] = res.display_name
                track.extra_metadata["frs_similarity"] = res.similarity
                track.extra_metadata["frs_is_unknown"] = res.is_unknown

        # Frame stride gating
        if frame_idx % self.frame_stride != 0:
            return []

        if self.detector is None or self.recognizer is None or self.matcher is None:
            return []

        new_events: List[FaceEvent] = []
        frame_h, frame_w = frame.shape[:2]

        for track in tracks:
            if not self.is_person(track):
                continue

            # Skip if already locked with consensus identity
            if track.track_id in self.resolved_tracks:
                continue

            # Check person minimum bounding box dimensions
            px1, py1, px2, py2 = track.current_bbox.as_int_xyxy()
            pw = max(0, px2 - px1)
            ph = max(0, py2 - py1)
            if pw < self.min_face_size or ph < self.min_face_size:
                continue

            # Crop upper-body ROI (top 45% of person bbox)
            uy1 = max(0, min(frame_h, py1))
            uy2 = max(0, min(frame_h, py1 + int(ph * 0.45)))
            ux1 = max(0, min(frame_w, px1))
            ux2 = max(0, min(frame_w, px2))

            if (uy2 - uy1) < self.min_face_size or (ux2 - ux1) < self.min_face_size:
                continue

            upper_body_crop = frame[uy1:uy2, ux1:ux2]
            if upper_body_crop.size == 0:
                continue

            # Localize face within upper-body crop
            face_detections = self.detector.detect_faces(
                person_crop=upper_body_crop,
                confidence_threshold=self.confidence_threshold
            )

            if not face_detections:
                continue

            # Select most confident face detection
            best_face = max(face_detections, key=lambda d: d.confidence)
            if best_face.crop is None or best_face.crop.size == 0:
                continue

            # Map face crop coordinates back to full frame bounding box
            fx1, fy1, fx2, fy2 = best_face.bbox.as_int_xyxy()
            full_face_bbox = BoundingBox(
                x1=ux1 + fx1,
                y1=uy1 + fy1,
                x2=ux1 + fx2,
                y2=uy1 + fy2
            )

            # Compute 512-D normalized embedding
            emb = self.recognizer.compute_embedding(best_face.crop)
            if np.linalg.norm(emb) == 0.0:
                continue

            # Match against enrolled gallery
            match_res = self.matcher.match(emb, threshold=self.match_threshold)
            self.track_buffers[track.track_id].append(match_res)

            # Maintain sliding temporal window
            if len(self.track_buffers[track.track_id]) > self.voting_window:
                self.track_buffers[track.track_id] = self.track_buffers[track.track_id][-self.voting_window:]

            # Evaluate temporal consensus
            consensus_event = self._evaluate_consensus(
                track=track,
                matches=self.track_buffers[track.track_id],
                camera_id=camera_id,
                full_face_bbox=full_face_bbox,
                frame_idx=frame_idx
            )

            if consensus_event is not None:
                self.resolved_tracks[track.track_id] = consensus_event

                # Attach tactical identity metadata to track
                track.extra_metadata["frs_identity"] = consensus_event.display_name
                track.extra_metadata["frs_similarity"] = consensus_event.similarity
                track.extra_metadata["frs_is_unknown"] = consensus_event.is_unknown

                # Emit event if not already alerted
                if track.track_id not in self.alerted_tracks:
                    if not consensus_event.is_unknown or self.unknown_enabled:
                        self.alerted_tracks.add(track.track_id)
                        new_events.append(consensus_event)

        return new_events

    def _evaluate_consensus(
        self,
        track: TrackedEntity,
        matches: List[FaceIdentityMatch],
        camera_id: str,
        full_face_bbox: BoundingBox,
        frame_idx: int
    ) -> Optional[FaceEvent]:
        """
        Evaluates temporal consensus over accumulated identity match votes.
        Requires at least `self.consensus_votes` consistent matches.
        """
        if not matches or len(matches) < self.consensus_votes:
            return None

        # Count identity occurrences
        id_counts = Counter(m.identity_id for m in matches)
        top_id, top_count = id_counts.most_common(1)[0]

        if top_count < self.consensus_votes:
            return None

        # Filter matches for the winning identity
        matching_votes = [m for m in matches if m.identity_id == top_id]
        avg_similarity = float(np.mean([m.similarity for m in matching_votes]))
        is_unknown = (top_id == "UNKNOWN")
        display_name = matching_votes[0].display_name if not is_unknown else "Unknown Person"
        event_type = "frs_unregistered" if is_unknown else "frs_watchlist_hit"
        severity = "medium" if is_unknown else "high"

        return FaceEvent(
            camera_id=camera_id,
            track_id=track.track_id,
            identity_id=top_id,
            display_name=display_name,
            similarity=avg_similarity,
            confidence=avg_similarity,
            is_unknown=is_unknown,
            event_type=event_type,
            severity=severity,
            bbox=full_face_bbox,
            position=track.current_center,
            frame_idx=frame_idx,
            metadata={
                "consensus_votes": top_count,
                "total_votes_analyzed": len(matches),
                "match_threshold": self.match_threshold
            }
        )

    def reset(self) -> None:
        """Resets all track voting buffers and resolved states."""
        self.track_buffers.clear()
        self.resolved_tracks.clear()
        self.alerted_tracks.clear()
