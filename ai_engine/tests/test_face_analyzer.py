import os
import json
import pytest
import numpy as np
import cv2

from ai_engine.pipeline.types import BoundingBox, TrackedEntity, ObjectClass
from ai_engine.pipeline.face import (
    FaceAnalyzer,
    FaceDetector,
    FaceRecognizer,
    CosineFaceMatcher,
    GalleryManager,
    FaceIdentityMatch,
    FaceEvent,
)
from ai_engine.tests.test_face_inference import create_synthetic_face_image


# ============================================================================
# 1. Mock Detector / Recognizer for Deterministic Testing
# ============================================================================

class MockFaceDetector:
    def __init__(self, should_detect: bool = True, conf: float = 0.90):
        self.should_detect = should_detect
        self.conf = conf

    def detect_faces(self, person_crop: np.ndarray, confidence_threshold: float = 0.50):
        if not self.should_detect or person_crop is None or person_crop.size == 0:
            return []
        h, w = person_crop.shape[:2]
        if h < 20 or w < 20:
            return []
        from ai_engine.pipeline.face.types import FaceDetection
        # Return face bbox in upper middle
        return [
            FaceDetection(
                bbox=BoundingBox(10, 10, w - 10, h - 10),
                confidence=self.conf,
                crop=person_crop[10:h - 10, 10:w - 10]
            )
        ]


class MockFaceRecognizer:
    def __init__(self, embedding_to_return: np.ndarray):
        self.emb = embedding_to_return

    def compute_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        return self.emb.copy()


# ============================================================================
# 2. FaceAnalyzer Unit & Integration Tests
# ============================================================================

def test_face_analyzer_filters_only_persons():
    rng = np.random.RandomState(42)
    v_alice = rng.randn(512).astype(np.float32)
    v_alice /= np.linalg.norm(v_alice)

    gallery = GalleryManager(expected_dim=512)
    gallery.register_identity("ID_ALICE", "Alice Officer", v_alice)

    matcher = CosineFaceMatcher(gallery=gallery, default_threshold=0.65)
    analyzer = FaceAnalyzer(
        detector=MockFaceDetector(should_detect=True),
        recognizer=MockFaceRecognizer(v_alice),
        matcher=matcher,
        consensus_votes=1,
        frame_stride=1,
        auto_initialize=False
    )

    frame = np.ones((480, 640, 3), dtype=np.uint8) * 100

    # 1. Vehicle track -> should NOT be processed
    box_car = BoundingBox(50, 50, 200, 200)
    car_track = TrackedEntity(
        track_id=1,
        class_name=ObjectClass.CAR,
        confidence=0.90,
        current_bbox=box_car,
        trajectory=[box_car]
    )
    events = analyzer.process_tracks(frame, [car_track], "CAM_01", frame_idx=0)
    assert len(events) == 0
    assert "frs_identity" not in car_track.extra_metadata

    # 2. Person track -> SHOULD be processed and produce FaceEvent
    box_person = BoundingBox(50, 50, 200, 350)
    person_track = TrackedEntity(
        track_id=2,
        class_name=ObjectClass.PERSON,
        confidence=0.90,
        current_bbox=box_person,
        trajectory=[box_person]
    )
    events = analyzer.process_tracks(frame, [person_track], "CAM_01", frame_idx=0)
    assert len(events) == 1
    assert events[0].identity_id == "ID_ALICE"
    assert person_track.extra_metadata.get("frs_identity") == "Alice Officer"


def test_face_analyzer_temporal_consensus_and_locking():
    rng = np.random.RandomState(42)
    v_bob = rng.randn(512).astype(np.float32)
    v_bob /= np.linalg.norm(v_bob)

    gallery = GalleryManager(expected_dim=512)
    gallery.register_identity("ID_BOB", "Bob Security", v_bob)

    matcher = CosineFaceMatcher(gallery=gallery, default_threshold=0.65)
    analyzer = FaceAnalyzer(
        detector=MockFaceDetector(should_detect=True),
        recognizer=MockFaceRecognizer(v_bob),
        matcher=matcher,
        consensus_votes=3,
        frame_stride=1,
        auto_initialize=False
    )

    frame = np.ones((480, 640, 3), dtype=np.uint8) * 100
    box_bob = BoundingBox(100, 80, 250, 380)
    person_track = TrackedEntity(
        track_id=12,
        class_name=ObjectClass.PERSON,
        confidence=0.88,
        current_bbox=box_bob,
        trajectory=[box_bob]
    )

    # Frame 1: Vote 1/3 -> No event yet
    evts1 = analyzer.process_tracks(frame, [person_track], "CAM_01", frame_idx=0)
    assert len(evts1) == 0

    # Frame 2: Vote 2/3 -> No event yet
    evts2 = analyzer.process_tracks(frame, [person_track], "CAM_01", frame_idx=1)
    assert len(evts2) == 0

    # Frame 3: Vote 3/3 -> Consensus reached! 1 FaceEvent emitted
    evts3 = analyzer.process_tracks(frame, [person_track], "CAM_01", frame_idx=2)
    assert len(evts3) == 1
    assert evts3[0].identity_id == "ID_BOB"
    assert evts3[0].display_name == "Bob Security"
    assert person_track.extra_metadata.get("frs_identity") == "Bob Security"

    # Frame 4: Already locked -> No duplicate event emitted
    evts4 = analyzer.process_tracks(frame, [person_track], "CAM_01", frame_idx=3)
    assert len(evts4) == 0
    # Identity remains attached
    assert person_track.extra_metadata.get("frs_identity") == "Bob Security"


def test_face_analyzer_unknown_person_consensus():
    rng = np.random.RandomState(42)
    v_enrolled = rng.randn(512).astype(np.float32)
    v_enrolled /= np.linalg.norm(v_enrolled)

    gallery = GalleryManager(expected_dim=512)
    gallery.register_identity("ID_KNOWN", "Known Officer", v_enrolled)

    # Unknown probe vector (orthogonal)
    v_unknown = rng.randn(512).astype(np.float32)
    v_unknown -= np.dot(v_unknown, v_enrolled) * v_enrolled
    v_unknown /= np.linalg.norm(v_unknown)

    matcher = CosineFaceMatcher(gallery=gallery, default_threshold=0.65)
    analyzer = FaceAnalyzer(
        detector=MockFaceDetector(should_detect=True),
        recognizer=MockFaceRecognizer(v_unknown),
        matcher=matcher,
        consensus_votes=2,
        frame_stride=1,
        unknown_enabled=True,
        auto_initialize=False
    )

    frame = np.ones((480, 640, 3), dtype=np.uint8) * 100
    box_unk = BoundingBox(80, 60, 200, 320)
    person_track = TrackedEntity(
        track_id=7,
        class_name=ObjectClass.PERSON,
        confidence=0.85,
        current_bbox=box_unk,
        trajectory=[box_unk]
    )

    # Vote 1/2
    assert len(analyzer.process_tracks(frame, [person_track], "CAM_01", frame_idx=0)) == 0
    # Vote 2/2 -> Consensus reached for UNKNOWN!
    evts = analyzer.process_tracks(frame, [person_track], "CAM_01", frame_idx=1)
    assert len(evts) == 1
    assert evts[0].is_unknown is True
    assert evts[0].identity_id == "UNKNOWN"
    assert evts[0].event_type == "frs_unregistered"


def test_face_analyzer_gallery_json_loading(tmp_path):
    rng = np.random.RandomState(42)
    v1 = (rng.randn(512).astype(np.float32) / 5.0).tolist()
    v2 = (rng.randn(512).astype(np.float32) / 5.0).tolist()

    gallery_data = {
        "identities": [
            {
                "identity_id": "PERS_01",
                "display_name": "Agent 1",
                "embedding": v1,
                "metadata": {"unit": "Delta"}
            },
            {
                "identity_id": "PERS_02",
                "display_name": "Agent 2",
                "embedding": v2,
                "metadata": {"unit": "Echo"}
            }
        ]
    }
    gal_file = tmp_path / "test_gallery.json"
    gal_file.write_text(json.dumps(gallery_data))

    analyzer = FaceAnalyzer(
        gallery_path=str(gal_file),
        auto_initialize=False
    )
    assert analyzer.matcher.gallery.count() == 2
    entry = analyzer.matcher.gallery.get_identity("PERS_01")
    assert entry is not None
    assert entry["display_name"] == "Agent 1"


def test_face_analyzer_reset():
    analyzer = FaceAnalyzer(auto_initialize=False)
    analyzer.track_buffers[1].append(None)
    analyzer.resolved_tracks[1] = None
    analyzer.alerted_tracks.add(1)

    analyzer.reset()
    assert len(analyzer.track_buffers) == 0
    assert len(analyzer.resolved_tracks) == 0
    assert len(analyzer.alerted_tracks) == 0
