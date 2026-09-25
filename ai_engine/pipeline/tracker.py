from typing import List, Dict, Tuple, Optional, Set
import numpy as np

from ai_engine.pipeline.interfaces import BaseTracker
from ai_engine.pipeline.types import (
    Detection,
    TrackedEntity,
    BoundingBox,
    ObjectClass,
    TrackState,
)


class TrackerError(Exception):
    """Base exception for tracker errors."""
    pass


class MultiObjectTracker(BaseTracker):
    """
    Robust Multi-Object Tracker (MOT) implementing BaseTracker.
    Maintains persistent track IDs, trajectory history, and state lifecycle
    using IoU matching with velocity/distance fallback.
    """

    def __init__(
        self,
        iou_threshold: float = 0.25,
        max_lost_frames: int = 15,
        max_trajectory_length: int = 30,
        min_hits: int = 1
    ):
        self.iou_threshold = float(iou_threshold)
        self.max_lost_frames = int(max_lost_frames)
        self.max_trajectory_length = int(max_trajectory_length)
        self.min_hits = int(min_hits)

        self._tracks: Dict[int, TrackedEntity] = {}
        self._next_id: int = 1
        self._frame_count: int = 0
        self._all_time_track_count: int = 0

    @property
    def active_tracks(self) -> List[TrackedEntity]:
        """Returns all currently active (visible) tracks."""
        return [t for t in self._tracks.values() if t.is_active and t.state == TrackState.ACTIVE]

    @property
    def total_unique_tracks(self) -> int:
        """Returns total number of unique tracks initiated over time."""
        return self._all_time_track_count

    def reset(self) -> None:
        """Resets all tracker state and tracking IDs."""
        self._tracks.clear()
        self._next_id = 1
        self._frame_count = 0
        self._all_time_track_count = 0

    def update(
        self,
        detections: List[Detection],
        frame: Optional[np.ndarray] = None
    ) -> List[TrackedEntity]:
        """
        Associates frame detections with existing tracks, creates new tracks for
        unmatched detections, and manages lost/expired track lifecycles.
        """
        self._frame_count += 1
        current_frame_idx = self._frame_count

        if not detections and not self._tracks:
            return []

        # If detections already have external track IDs (e.g. from Ultralytics track)
        has_external_ids = any(d.track_id is not None for d in detections)
        if has_external_ids:
            return self._update_with_external_ids(detections, current_frame_idx)

        # Separate existing candidate tracks
        existing_track_ids = list(self._tracks.keys())
        existing_tracks = [self._tracks[tid] for tid in existing_track_ids]

        matched_tracks: Set[int] = set()
        matched_detections: Set[int] = set()

        if existing_tracks and detections:
            # Build IoU Cost Matrix
            iou_matrix = np.zeros((len(existing_tracks), len(detections)), dtype=np.float32)
            for t_idx, track in enumerate(existing_tracks):
                for d_idx, det in enumerate(detections):
                    # Class-aware matching: only match detections with compatible classes
                    if track.class_name == det.class_name or track.raw_class_name == det.raw_class_name:
                        iou_matrix[t_idx, d_idx] = track.current_bbox.iou(det.bbox)
                    else:
                        iou_matrix[t_idx, d_idx] = 0.0

            # Greedy Hungarian / IoU matching
            while True:
                max_iou = np.max(iou_matrix)
                if max_iou < self.iou_threshold:
                    break

                t_idx, d_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                if t_idx in matched_tracks or d_idx in matched_detections:
                    iou_matrix[t_idx, d_idx] = -1.0
                    continue

                matched_tracks.add(t_idx)
                matched_detections.add(d_idx)
                iou_matrix[t_idx, :] = -1.0
                iou_matrix[:, d_idx] = -1.0

                # Update matched track
                track = existing_tracks[t_idx]
                det = detections[d_idx]
                det.track_id = track.track_id
                track.update(
                    bbox=det.bbox,
                    confidence=det.confidence,
                    frame_idx=current_frame_idx,
                    max_trajectory_length=self.max_trajectory_length
                )

        # Handle unmatched detections -> spawn new tracks
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_detections:
                new_id = self._next_id
                self._next_id += 1
                self._all_time_track_count += 1
                det.track_id = new_id

                new_track = TrackedEntity(
                    track_id=new_id,
                    class_name=det.class_name,
                    current_bbox=det.bbox,
                    confidence=det.confidence,
                    raw_class_name=det.raw_class_name,
                    state=TrackState.ACTIVE,
                    first_frame_idx=current_frame_idx,
                    last_frame_idx=current_frame_idx,
                    hits=1,
                    time_since_update=0,
                    is_active=True
                )
                self._tracks[new_id] = new_track

        # Handle unmatched existing tracks -> mark as missed or expired
        tracks_to_delete: List[int] = []
        for t_idx, track in enumerate(existing_tracks):
            if t_idx not in matched_tracks:
                track.mark_missed(self.max_lost_frames)
                if track.state == TrackState.EXPIRED:
                    tracks_to_delete.append(track.track_id)

        for tid in tracks_to_delete:
            del self._tracks[tid]

        # Return all active tracks that have met min_hits requirement
        active_list = [
            t for t in self._tracks.values()
            if t.is_active and t.state == TrackState.ACTIVE and t.hits >= self.min_hits
        ]
        return active_list

    def _update_with_external_ids(
        self,
        detections: List[Detection],
        current_frame_idx: int
    ) -> List[TrackedEntity]:
        """Updates tracks when YOLO detector returns native tracker IDs."""
        seen_ids: Set[int] = set()

        for det in detections:
            if det.track_id is None:
                continue

            tid = det.track_id
            seen_ids.add(tid)

            if tid in self._tracks:
                track = self._tracks[tid]
                track.update(
                    bbox=det.bbox,
                    confidence=det.confidence,
                    frame_idx=current_frame_idx,
                    max_trajectory_length=self.max_trajectory_length
                )
            else:
                self._all_time_track_count += 1
                track = TrackedEntity(
                    track_id=tid,
                    class_name=det.class_name,
                    current_bbox=det.bbox,
                    confidence=det.confidence,
                    raw_class_name=det.raw_class_name,
                    state=TrackState.ACTIVE,
                    first_frame_idx=current_frame_idx,
                    last_frame_idx=current_frame_idx,
                    hits=1,
                    time_since_update=0,
                    is_active=True
                )
                self._tracks[tid] = track

        # Mark missed for tracks not in this frame
        tracks_to_delete: List[int] = []
        for tid, track in self._tracks.items():
            if tid not in seen_ids:
                track.mark_missed(self.max_lost_frames)
                if track.state == TrackState.EXPIRED:
                    tracks_to_delete.append(tid)

        for tid in tracks_to_delete:
            del self._tracks[tid]

        return [t for t in self._tracks.values() if t.is_active and t.state == TrackState.ACTIVE]
