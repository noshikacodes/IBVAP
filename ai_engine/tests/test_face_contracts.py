import pytest
import numpy as np
from datetime import datetime

from ai_engine.pipeline.types import BoundingBox
from ai_engine.pipeline.config import InferenceConfig
from ai_engine.pipeline.interfaces import (
    BaseFaceDetector,
    BaseFaceRecognizer,
    BaseFaceMatcher,
    BaseFaceAnalyzer,
)
from ai_engine.pipeline.face import (
    FaceDetection,
    FaceEmbedding,
    FaceIdentityMatch,
    FaceEvent,
    CosineFaceMatcher,
    GalleryManager,
)


# ============================================================================
# 1. Data Model Creation & Validation Tests
# ============================================================================

def test_face_detection_creation():
    bbox = BoundingBox(50, 40, 150, 160)
    landmarks = [(75.0, 70.0), (125.0, 70.0), (100.0, 95.0), (80.0, 130.0), (120.0, 130.0)]
    det = FaceDetection(
        bbox=bbox,
        confidence=0.92,
        landmarks=landmarks,
        parent_track_id=7,
        metadata={"quality_score": 0.88}
    )

    assert det.bbox == bbox
    assert det.confidence == 0.92
    assert det.parent_track_id == 7
    assert len(det.landmarks) == 5

    d = det.to_dict()
    assert d["confidence"] == 0.92
    assert d["parent_track_id"] == 7
    assert len(d["landmarks"]) == 5


def test_face_embedding_creation_and_512d_validation():
    rng = np.random.RandomState(42)
    valid_vec = rng.randn(512).astype(np.float32)

    emb = FaceEmbedding(
        embedding=valid_vec,
        model_name="mobilefacenet_arcface",
        dimension=512,
        track_id=3,
        frame_idx=10
    )
    assert emb.dimension == 512
    assert emb.embedding.shape == (512,)
    assert emb.track_id == 3

    # Invalid dimension (e.g. 128 instead of 512)
    with pytest.raises(ValueError, match="Invalid face embedding dimension"):
        FaceEmbedding(embedding=rng.randn(128).astype(np.float32), dimension=512)

    # None embedding
    with pytest.raises(ValueError, match="Face embedding array cannot be None"):
        FaceEmbedding(embedding=None, dimension=512)

    # Embedding with NaN values
    nan_vec = valid_vec.copy()
    nan_vec[10] = np.nan
    with pytest.raises(ValueError, match="Face embedding contains NaN or Inf values"):
        FaceEmbedding(embedding=nan_vec, dimension=512)


def test_face_identity_match_creation():
    match = FaceIdentityMatch(
        identity_id="PERS_01",
        display_name="Officer Sharma",
        similarity=0.8842,
        confidence=0.8842,
        is_match=True,
        is_unknown=False,
        metadata={"role": "Patrol Officer"}
    )
    assert match.identity_id == "PERS_01"
    assert match.is_match is True
    assert match.is_unknown is False

    d = match.to_dict()
    assert d["similarity"] == 0.8842
    assert d["is_match"] is True


def test_face_event_creation_and_serialization():
    event = FaceEvent(
        camera_id="CAM_01",
        track_id=5,
        identity_id="PERS_02",
        display_name="Capt. Verma",
        similarity=0.912,
        confidence=0.912,
        is_unknown=False,
        bbox=BoundingBox(100, 80, 180, 180),
        position=(140.0, 130.0),
        frame_idx=42
    )
    assert event.camera_id == "CAM_01"
    assert event.track_id == 5
    assert event.identity_id == "PERS_02"
    assert event.similarity == 0.912

    d = event.to_dict()
    assert d["camera_id"] == "CAM_01"
    assert d["track_id"] == 5
    assert d["identity_id"] == "PERS_02"
    assert d["position"] == [140.0, 130.0]


# ============================================================================
# 2. Vector Math & Normalization Tests
# ============================================================================

def test_embedding_l2_normalization():
    gallery = GalleryManager(expected_dim=512)
    rng = np.random.RandomState(42)
    raw_vec = rng.randn(512).astype(np.float32) * 5.0

    is_valid, norm_vec = gallery.normalize_vector(raw_vec)
    assert is_valid is True
    norm_val = np.linalg.norm(norm_vec)
    assert np.isclose(norm_val, 1.0, atol=1e-5)


def test_cosine_similarity_mathematical_properties():
    """Validates mathematical properties: identical=1.0, orthogonal=0.0, opposite=-1.0."""
    matcher = CosineFaceMatcher(default_threshold=0.60)

    # Base synthetic unit vector
    rng = np.random.RandomState(100)
    v1 = rng.randn(512).astype(np.float32)
    v1 = v1 / np.linalg.norm(v1)

    # Enroll v1
    matcher.register_identity("ID_01", "Identity 1", v1)

    # 1. Identical vector -> Similarity ~ 1.0
    match_identical = matcher.match(v1)
    assert match_identical.is_match is True
    assert match_identical.identity_id == "ID_01"
    assert np.isclose(match_identical.similarity, 1.0, atol=1e-4)

    # 2. Orthogonal vector (via Gram-Schmidt step) -> Similarity ~ 0.0
    random_v = rng.randn(512).astype(np.float32)
    v_orthogonal = random_v - np.dot(random_v, v1) * v1
    v_orthogonal = v_orthogonal / np.linalg.norm(v_orthogonal)

    match_orthogonal = matcher.match(v_orthogonal)
    assert match_orthogonal.is_unknown is True
    assert np.isclose(match_orthogonal.similarity, 0.0, atol=1e-4)

    # 3. Inverted vector -> Similarity ~ -1.0
    v_inverted = -v1
    match_inverted = matcher.match(v_inverted)
    assert match_inverted.is_unknown is True
    assert np.isclose(match_inverted.similarity, -1.0, atol=1e-4)


# ============================================================================
# 3. Gallery Manager & Matcher Tests
# ============================================================================

def test_gallery_manager_crud_and_duplicates():
    gallery = GalleryManager(expected_dim=512)
    rng = np.random.RandomState(42)
    v_alice = rng.randn(512).astype(np.float32)
    v_bob = rng.randn(512).astype(np.float32)

    # Register identities
    assert gallery.register_identity("ID_ALICE", "Alice", v_alice) is True
    assert gallery.register_identity("ID_BOB", "Bob", v_bob) is True
    assert gallery.count() == 2

    # Duplicate registration updates profile cleanly
    v_alice_updated = rng.randn(512).astype(np.float32)
    assert gallery.register_identity("ID_ALICE", "Alice Officer", v_alice_updated) is True
    assert gallery.count() == 2
    alice_entry = gallery.get_identity("ID_ALICE")
    assert alice_entry["display_name"] == "Alice Officer"

    # List identities
    identities = gallery.list_identities()
    assert len(identities) == 2

    # Remove identity
    assert gallery.remove_identity("ID_BOB") is True
    assert gallery.remove_identity("ID_BOB") is False  # Already removed
    assert gallery.count() == 1

    # Clear
    gallery.clear()
    assert gallery.count() == 0


def test_matcher_empty_gallery():
    matcher = CosineFaceMatcher()
    rng = np.random.RandomState(42)
    vec = rng.randn(512).astype(np.float32)

    match = matcher.match(vec)
    assert match.is_unknown is True
    assert match.is_match is False
    assert match.similarity == 0.0


def test_matcher_threshold_gating_and_unknown_handling():
    matcher = CosineFaceMatcher(default_threshold=0.70)
    rng = np.random.RandomState(42)

    # Target enrolled vector
    v_target = rng.randn(512).astype(np.float32)
    v_target /= np.linalg.norm(v_target)
    matcher.register_identity("PERSONNEL_01", "Lt. Commander", v_target)

    # Probe 1: High similarity (10% unit noise, sim ~ 0.995)
    noise = rng.randn(512).astype(np.float32)
    noise = (noise / np.linalg.norm(noise)) * 0.10
    v_high = v_target + noise
    v_high /= np.linalg.norm(v_high)

    match_high = matcher.match(v_high)
    assert match_high.is_match is True
    assert match_high.is_unknown is False
    assert match_high.identity_id == "PERSONNEL_01"
    assert match_high.similarity >= 0.70

    # Probe 2: Unrelated random vector (sim ~ 0.0 < threshold)
    v_stranger = rng.randn(512).astype(np.float32)
    v_stranger /= np.linalg.norm(v_stranger)

    match_stranger = matcher.match(v_stranger)
    assert match_stranger.is_match is False
    assert match_stranger.is_unknown is True
    assert match_stranger.identity_id == "UNKNOWN"

    # Probe 3: Custom threshold override on call
    match_custom = matcher.match(v_high, threshold=0.999)
    # Threshold higher than similarity returns UNKNOWN
    if match_high.similarity < 0.999:
        assert match_custom.is_unknown is True


def test_matcher_malformed_and_nan_handling():
    matcher = CosineFaceMatcher()
    rng = np.random.RandomState(42)
    v_target = rng.randn(512).astype(np.float32)
    matcher.register_identity("ID_01", "Target", v_target)

    # None vector
    res_none = matcher.match(None)
    assert res_none.is_unknown is True
    assert res_none.similarity == 0.0

    # Wrong shape vector (e.g. 10 elements)
    res_short = matcher.match(np.zeros(10, dtype=np.float32))
    assert res_short.is_unknown is True

    # Vector with NaN / Inf
    nan_vec = np.zeros(512, dtype=np.float32)
    nan_vec[0] = np.nan
    res_nan = matcher.match(nan_vec)
    assert res_nan.is_unknown is True
    assert res_nan.similarity == 0.0


# ============================================================================
# 4. Configuration & Abstract Interface Tests
# ============================================================================

def test_inference_config_frs_defaults():
    config = InferenceConfig(
        input_path="mock_streams/sample_patrol.mp4",
        output_path="mock_streams/out.mp4"
    )

    # FRS defaults
    assert config.enable_frs is False
    assert config.frs_detector_model == "yolov8n_face.pt"
    assert config.frs_recognizer_model == "mobilefacenet_arcface.onnx"
    assert config.frs_face_confidence == 0.50
    assert config.frs_match_threshold == 0.65
    assert config.frs_frame_stride == 3
    assert config.frs_consensus_votes == 3
    assert config.frs_min_face_size == 32
    assert config.frs_unknown_enabled is True
    assert config.frs_embedding_dimension == 512
    assert config.frs_voting_window_frames == 15

    # ANPR defaults remain intact
    assert config.enable_anpr is False
    assert config.anpr_detector_model == "yolov8n_plate.pt"


def test_inference_config_frs_validations():
    base_args = {
        "input_path": "mock_streams/sample_patrol.mp4",
        "output_path": "mock_streams/out.mp4"
    }

    # Invalid confidence
    with pytest.raises(ValueError, match="frs_face_confidence must be between 0.0 and 1.0"):
        InferenceConfig(**base_args, frs_face_confidence=-0.1)

    # Invalid match threshold
    with pytest.raises(ValueError, match="frs_match_threshold must be between 0.0 and 1.0"):
        InferenceConfig(**base_args, frs_match_threshold=1.5)

    # Invalid consensus votes
    with pytest.raises(ValueError, match="frs_consensus_votes must be >= 1"):
        InferenceConfig(**base_args, frs_consensus_votes=0)

    # Invalid frame stride
    with pytest.raises(ValueError, match="frs_frame_stride must be >= 1"):
        InferenceConfig(**base_args, frs_frame_stride=0)

    # Invalid min face size
    with pytest.raises(ValueError, match="frs_min_face_size must be >= 10"):
        InferenceConfig(**base_args, frs_min_face_size=5)

    # Invalid embedding dimension
    with pytest.raises(ValueError, match="frs_embedding_dimension must be >= 64"):
        InferenceConfig(**base_args, frs_embedding_dimension=32)


def test_abstract_interfaces_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseFaceDetector()

    with pytest.raises(TypeError):
        BaseFaceRecognizer()

    with pytest.raises(TypeError):
        BaseFaceMatcher()

    with pytest.raises(TypeError):
        BaseFaceAnalyzer()
