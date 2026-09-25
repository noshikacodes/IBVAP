import os
import time
import math
from datetime import datetime
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set, Any
import cv2
import numpy as np

from ai_engine.pipeline.types import TrackedEntity, ObjectClass, BoundingBox
from ai_engine.pipeline.spatial_rules import segments_intersect, _ccw


# Standardized traffic object classes for analytics
TRACKED_TRAFFIC_CLASSES = ("car", "bus", "truck", "motorcycle", "person")


def normalize_traffic_class(class_name: str) -> str:
    """Normalizes object class names to standard traffic analytics taxonomy."""
    c = str(class_name).strip().lower()
    if c in ("car", "automobile", "sedan", "suv", "vehicle", "van"):
        return "car"
    if c in ("bus",):
        return "bus"
    if c in ("truck", "trailer", "lorry"):
        return "truck"
    if c in ("motorcycle", "motorbike", "bike", "bicycle", "scooter"):
        return "motorcycle"
    if c in ("person", "human", "pedestrian", "man", "woman"):
        return "person"
    return "car"  # Default automotive fallback


@dataclass
class TrafficCrossingEvent:
    """Immutable record of a unique vehicle/person crossing the counting line."""
    camera_id: str
    track_id: int
    object_type: str       # 'car', 'bus', 'truck', 'motorcycle', 'person'
    timestamp: str         # ISO-8601 string
    direction: str         # 'IN' (towards tunnel/north) or 'OUT' (towards camera/south)
    event_type: str = "LINE_CROSSING"
    confidence: float = 0.0
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0) # (x1, y1, x2, y2)
    snapshot_path: Optional[str] = None
    frame_idx: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "object_type": self.object_type,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "event_type": self.event_type,
            "confidence": round(self.confidence, 3),
            "bbox_x1": round(self.bbox[0], 1),
            "bbox_y1": round(self.bbox[1], 1),
            "bbox_x2": round(self.bbox[2], 1),
            "bbox_y2": round(self.bbox[3], 1),
            "snapshot_path": self.snapshot_path,
            "frame_idx": self.frame_idx,
        }


class TrafficCountingEngine:
    """
    Stateful traffic analytics and unique vehicle counting engine.
    Uses ByteTrack persistent track IDs and virtual counting lines across the roadway.
    Enforces strict deduplication: a single tracked vehicle is counted at most once,
    preventing any frame-by-frame double counting or oscillation duplicate triggers.
    """

    def __init__(
        self,
        camera_id: str = "CAM_SEJONG_95366",
        line_pt1: Tuple[float, float] = (50.0, 360.0),
        line_pt2: Tuple[float, float] = (670.0, 360.0),
        evidence_dir: str = "data/evidence",
        save_evidence: bool = True,
        max_counted_history: int = 10000,
        stale_track_timeout_frames: int = 90
    ):
        self.camera_id = camera_id
        self.line_pt1 = (float(line_pt1[0]), float(line_pt1[1]))
        self.line_pt2 = (float(line_pt2[0]), float(line_pt2[1]))
        self.evidence_dir = os.path.abspath(evidence_dir)
        self.save_evidence = save_evidence
        self.max_counted_history = max_counted_history
        self.stale_track_timeout_frames = stale_track_timeout_frames

        if self.save_evidence:
            os.makedirs(self.evidence_dir, exist_ok=True)

        # Unique IDs that have already crossed and been counted (strictly prevents double counting)
        self._counted_track_ids: Set[int] = set()
        self._counted_id_order: List[int] = []

        # Majority class voting per track: track_id -> Counter(class_names)
        self._track_class_votes: Dict[int, Counter] = defaultdict(Counter)

        # Last observed position per track: track_id -> (x, y)
        self._track_last_position: Dict[int, Tuple[float, float]] = {}
        self._track_last_frame: Dict[int, int] = {}

        # Cumulative totals by class
        self.counted_totals: Dict[str, int] = {c: 0 for c in TRACKED_TRAFFIC_CLASSES}

        # In-memory recent events buffer (most recent first)
        self.recent_events: List[TrafficCrossingEvent] = []
        self._max_recent_events: int = 100

    def get_counting_line(self) -> List[List[float]]:
        """Returns [[x1, y1], [x2, y2]] coordinates for visual overlay."""
        return [list(self.line_pt1), list(self.line_pt2)]

    def set_counting_line(self, pt1: Tuple[float, float], pt2: Tuple[float, float]) -> None:
        self.line_pt1 = (float(pt1[0]), float(pt1[1]))
        self.line_pt2 = (float(pt2[0]), float(pt2[1]))

    def determine_direction(self, p_prev: Tuple[float, float], p_curr: Tuple[float, float]) -> str:
        """
        Determines travel direction relative to the counting line.
        For Wunhak Tunnel (horizontal line y=360):
        - Traveling upwards (decreasing y, into tunnel): 'IN'
        - Traveling downwards (increasing y, towards camera): 'OUT'
        """
        dy = p_curr[1] - p_prev[1]
        if dy < -1.0:
            return "IN"
        elif dy > 1.0:
            return "OUT"

        # Fallback to cross product orientation relative to line
        d_start = _ccw(self.line_pt1, self.line_pt2, p_prev)
        d_end = _ccw(self.line_pt1, self.line_pt2, p_curr)
        if d_start > 0 and d_end <= 0:
            return "OUT"
        elif d_start < 0 and d_end >= 0:
            return "IN"
        return "OUT"

    def get_consensus_class(self, track_id: int, fallback_class: str) -> str:
        """Returns the majority voted class for a track ID."""
        votes = self._track_class_votes.get(track_id)
        if votes:
            most_common = votes.most_common(1)
            if most_common:
                return most_common[0][0]
        return normalize_traffic_class(fallback_class)

    def process_tracks(
        self,
        tracks: List[TrackedEntity],
        frame: Optional[np.ndarray] = None,
        frame_idx: int = 0,
        timestamp_str: Optional[str] = None
    ) -> List[TrafficCrossingEvent]:
        """
        Evaluates active tracks against the counting line.
        Returns newly triggered crossing events for this frame.
        """
        if timestamp_str is None:
            timestamp_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        new_events: List[TrafficCrossingEvent] = []

        for track in tracks:
            track_id = track.track_id
            raw_class = track.class_name.value if hasattr(track.class_name, "value") else str(track.class_name)
            norm_class = normalize_traffic_class(raw_class)

            # Record class observation for voting
            self._track_class_votes[track_id][norm_class] += 1

            # Use bottom-center of bounding box as ground contact point
            curr_pos = track.current_bottom_center

            # If track has previous position, test for line intersection
            if track_id in self._track_last_position:
                prev_pos = self._track_last_position[track_id]

                # Check if track has already been counted
                if track_id not in self._counted_track_ids:
                    # Line intersection test
                    if segments_intersect(prev_pos, curr_pos, self.line_pt1, self.line_pt2):
                        # Determine consensus class and direction
                        final_class = self.get_consensus_class(track_id, norm_class)
                        direction = self.determine_direction(prev_pos, curr_pos)

                        # Save evidence snapshot if requested and frame provided
                        snapshot_path = None
                        if self.save_evidence and frame is not None and frame.size > 0:
                            snapshot_path = self._save_evidence_snapshot(
                                frame=frame,
                                track=track,
                                track_id=track_id,
                                obj_class=final_class,
                                frame_idx=frame_idx,
                                direction=direction
                            )

                        box_tuple = (
                            float(track.current_bbox.x1),
                            float(track.current_bbox.y1),
                            float(track.current_bbox.x2),
                            float(track.current_bbox.y2)
                        )

                        event = TrafficCrossingEvent(
                            camera_id=self.camera_id,
                            track_id=track_id,
                            object_type=final_class,
                            timestamp=timestamp_str,
                            direction=direction,
                            confidence=float(track.confidence),
                            bbox=box_tuple,
                            snapshot_path=snapshot_path,
                            frame_idx=frame_idx
                        )

                        # Mark as counted (Strict deduplication)
                        self._counted_track_ids.add(track_id)
                        self._counted_id_order.append(track_id)
                        if len(self._counted_id_order) > self.max_counted_history:
                            oldest = self._counted_id_order.pop(0)
                            self._counted_track_ids.discard(oldest)

                        # Increment unique totals
                        self.counted_totals[final_class] = self.counted_totals.get(final_class, 0) + 1

                        # Store in recent events
                        self.recent_events.insert(0, event)
                        if len(self.recent_events) > self._max_recent_events:
                            self.recent_events.pop()

                        new_events.append(event)

            # Update last known state
            self._track_last_position[track_id] = curr_pos
            self._track_last_frame[track_id] = frame_idx

        # Periodic cleanup of stale tracks
        if frame_idx % 30 == 0:
            self._cleanup_stale_tracks(frame_idx)

        return new_events

    def _save_evidence_snapshot(
        self,
        frame: np.ndarray,
        track: TrackedEntity,
        track_id: int,
        obj_class: str,
        frame_idx: int,
        direction: str = "IN"
    ) -> Optional[str]:
        """Saves a high-clarity evidence snapshot with tactical HUD metadata of the crossing vehicle."""
        try:
            h, w = frame.shape[:2]
            snap = frame.copy()

            # Top evidence banner
            cv2.rectangle(snap, (0, 0), (w, 28), (15, 23, 42), -1)
            cv2.line(snap, (0, 28), (w, 28), (56, 189, 248), 1)
            time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            header_text = f"[EVIDENCE RECORD] CAM: {self.camera_id} | TRACK #{track_id} ({obj_class.upper()}) | DIR: {direction} | {time_str}"
            cv2.putText(snap, header_text, (10, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (56, 189, 248), 1, lineType=cv2.LINE_AA)

            # Draw virtual line
            pt1_int = (int(round(self.line_pt1[0])), int(round(self.line_pt1[1])))
            pt2_int = (int(round(self.line_pt2[0])), int(round(self.line_pt2[1])))
            cv2.line(snap, pt1_int, pt2_int, (255, 220, 0), 2, lineType=cv2.LINE_AA)

            # Draw vehicle bounding box and text
            x1, y1, x2, y2 = track.current_bbox.as_int_xyxy()
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w - 1, x2), min(h - 1, y2)
            cv2.rectangle(snap, (x1, y1), (x2, y2), (0, 255, 128), 2, lineType=cv2.LINE_AA)
            label = f"#{track_id} {obj_class.upper()} {int(track.confidence * 100)}%"
            cv2.rectangle(snap, (x1, max(30, y1 - 20)), (x1 + 140, max(30, y1)), (0, 255, 128), -1)
            cv2.putText(snap, label, (x1 + 4, max(30, y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, lineType=cv2.LINE_AA)

            filename = f"crossing_{self.camera_id}_t{track_id}_f{frame_idx}_{int(time.time())}.jpg"
            filepath = os.path.join(self.evidence_dir, filename)
            cv2.imwrite(filepath, snap)
            return filepath
        except Exception:
            return None

    def _cleanup_stale_tracks(self, current_frame: int) -> None:
        """Evicts internal trajectory records for tracks not seen for stale_track_timeout_frames."""
        stale_ids = [
            tid for tid, last_f in self._track_last_frame.items()
            if (current_frame - last_f) > self.stale_track_timeout_frames
        ]
        for tid in stale_ids:
            self._track_last_position.pop(tid, None)
            self._track_last_frame.pop(tid, None)
            self._track_class_votes.pop(tid, None)

    def get_live_now(self, active_tracks: List[TrackedEntity]) -> Dict[str, int]:
        """Calculates the breakdown of vehicles/persons currently visible in the active frame."""
        counts = {c: 0 for c in TRACKED_TRAFFIC_CLASSES}
        for t in active_tracks:
            norm_c = normalize_traffic_class(
                t.class_name.value if hasattr(t.class_name, "value") else str(t.class_name)
            )
            counts[norm_c] = counts.get(norm_c, 0) + 1
        return counts

    def get_telemetry_snapshot(self, active_tracks: List[TrackedEntity]) -> Dict[str, Any]:
        """Produces traffic analytics snapshot payload for backend dispatch."""
        live_now = self.get_live_now(active_tracks)
        return {
            "live_now": live_now,
            "live_total": sum(live_now.values()),
            "counted_totals": dict(self.counted_totals),
            "total_counted": sum(self.counted_totals.values()),
            "counting_line": self.get_counting_line(),
            "recent_events": [e.to_dict() for e in self.recent_events[:10]],
        }
