import os
import json
import pytest
import numpy as np

from ai_engine.pipeline.types import BoundingBox, TrackedEntity, ObjectClass
from ai_engine.pipeline.face import (
    FaceAnalyzer,
    CosineFaceMatcher,
    GalleryManager,
    FaceEvent,
)
from ai_engine.pipeline.annotator import VideoAnnotator
from backend.app.services.alert_engine import AlertEngine
from backend.app.services.alert_repository import InMemoryAlertRepository


class SyntheticFaceRecognizer:
    def __init__(self, embedding_sequence):
        self.embeddings = embedding_sequence
        self.call_idx = 0

    def compute_embedding(self, face_crop: np.ndarray) -> np.ndarray:
        idx = min(self.call_idx, len(self.embeddings) - 1)
        self.call_idx += 1
        return self.embeddings[idx].copy()


class ConstantFaceDetector:
    def detect_faces(self, person_crop: np.ndarray, confidence_threshold: float = 0.50):
        h, w = person_crop.shape[:2]
        from ai_engine.pipeline.face.types import FaceDetection
        return [
            FaceDetection(
                bbox=BoundingBox(10, 10, w - 10, h - 10),
                confidence=0.95,
                crop=person_crop
            )
        ]


def test_face_recognition_synthetic_end_to_end_pipeline():
    """
    Step 12: Deterministic synthetic E2E pipeline test.
    Validates:
    1. 3-frame temporal consensus for DEMO_001 ("Capt. Sharma")
    2. Event emission and AlertEngine dispatch
    3. VideoAnnotator tactical badge rendering
    4. Unknown probe returning UNKNOWN without false identity
    """
    # 1. Load synthetic gallery
    gallery_path = "mock_streams/face_gallery.json"
    assert os.path.exists(gallery_path)
    with open(gallery_path, "r", encoding="utf-8") as f:
        gal_data = json.load(f)

    target_emb = np.asarray(gal_data["identities"][0]["embedding"], dtype=np.float32)
    target_emb /= np.linalg.norm(target_emb)

    # Generate 3 noisy probe vectors close to target (sim ~ 0.99)
    rng = np.random.RandomState(123)
    probe_seq = []
    for _ in range(3):
        noise = rng.randn(512).astype(np.float32)
        noise = (noise / np.linalg.norm(noise)) * 0.10
        v_noisy = target_emb + noise
        v_noisy /= np.linalg.norm(v_noisy)
        probe_seq.append(v_noisy)

    recognizer = SyntheticFaceRecognizer(probe_seq)
    detector = ConstantFaceDetector()

    gallery = GalleryManager(expected_dim=512)
    gallery.load_from_json(gallery_path)
    matcher = CosineFaceMatcher(gallery=gallery, default_threshold=0.65)

    analyzer = FaceAnalyzer(
        detector=detector,
        recognizer=recognizer,
        matcher=matcher,
        consensus_votes=3,
        frame_stride=1,
        auto_initialize=False
    )

    repo = InMemoryAlertRepository()
    alert_engine = AlertEngine(repository=repo, cooldown_seconds=15.0)
    annotator = VideoAnnotator()

    frame = np.ones((480, 640, 3), dtype=np.uint8) * 120
    box_person = BoundingBox(120, 80, 240, 360)
    track = TrackedEntity(
        track_id=12,
        class_name=ObjectClass.PERSON,
        confidence=0.92,
        current_bbox=box_person,
        trajectory=[box_person]
    )

    # Frame 1: Vote 1/3
    evts1 = analyzer.process_tracks(frame, [track], camera_id="CAM_01", frame_idx=0)
    assert len(evts1) == 0

    # Frame 2: Vote 2/3
    evts2 = analyzer.process_tracks(frame, [track], camera_id="CAM_01", frame_idx=1)
    assert len(evts2) == 0

    # Frame 3: Vote 3/3 -> Consensus reached!
    evts3 = analyzer.process_tracks(frame, [track], camera_id="CAM_01", frame_idx=2)
    assert len(evts3) == 1

    face_evt = evts3[0]
    assert face_evt.identity_id == "DEMO_001"
    assert face_evt.display_name == "Capt. Sharma"
    assert face_evt.similarity >= 0.90
    assert face_evt.is_unknown is False

    # Route to AlertEngine
    alert = alert_engine.process_face_event(face_evt)
    assert alert is not None
    assert alert.severity == "critical"
    assert "Capt. Sharma" in alert.message
    assert alert.metadata["identity_id"] == "DEMO_001"

    # Verify repository storage
    stored = repo.get(alert.alert_id)
    assert stored is not None
    assert stored.metadata["identity_id"] == "DEMO_001"

    # Test tactical VideoAnnotator badge rendering
    annotated = annotator.annotate_frame(frame, [track], frame_idx=2)
    assert annotated is not None
    assert annotated.shape == frame.shape
    assert track.extra_metadata.get("frs_identity") == "Capt. Sharma"


def test_face_recognition_synthetic_unknown_probe():
    """Validates that a distant/unregistered synthetic embedding produces UNKNOWN."""
    gallery_path = "mock_streams/face_gallery.json"
    gallery = GalleryManager(expected_dim=512)
    gallery.load_from_json(gallery_path)
    matcher = CosineFaceMatcher(gallery=gallery, default_threshold=0.65)

    rng = np.random.RandomState(999)
    v_unknown = rng.randn(512).astype(np.float32)
    v_unknown /= np.linalg.norm(v_unknown)

    recognizer = SyntheticFaceRecognizer([v_unknown, v_unknown])
    detector = ConstantFaceDetector()

    analyzer = FaceAnalyzer(
        detector=detector,
        recognizer=recognizer,
        matcher=matcher,
        consensus_votes=2,
        frame_stride=1,
        unknown_enabled=True,
        auto_initialize=False
    )

    repo = InMemoryAlertRepository()
    alert_engine = AlertEngine(repository=repo, cooldown_seconds=15.0)

    frame = np.ones((480, 640, 3), dtype=np.uint8) * 120
    box_person = BoundingBox(120, 80, 240, 360)
    track = TrackedEntity(
        track_id=19,
        class_name=ObjectClass.PERSON,
        confidence=0.89,
        current_bbox=box_person,
        trajectory=[box_person]
    )

    # Frame 1: Vote 1/2
    assert len(analyzer.process_tracks(frame, [track], "CAM_01", frame_idx=0)) == 0
    # Frame 2: Vote 2/2 -> Consensus UNKNOWN
    evts = analyzer.process_tracks(frame, [track], "CAM_01", frame_idx=1)
    assert len(evts) == 1
    assert evts[0].is_unknown is True
    assert evts[0].identity_id == "UNKNOWN"

    alert = alert_engine.process_face_event(evts[0])
    assert alert is not None
    assert alert.severity == "medium"
    assert "UNREGISTERED / UNKNOWN" in alert.message
