import os
import pytest
import numpy as np
import cv2

from ai_engine.pipeline.face.detector import FaceDetector
from ai_engine.pipeline.face.recognizer import FaceRecognizer
from ai_engine.pipeline.face.matcher import CosineFaceMatcher, GalleryManager
from ai_engine.pipeline.face.types import FaceDetection, FaceEmbedding, FaceIdentityMatch


MODEL_DETECTOR_PATH = "ai_engine/models_weight/yolov8n_face.pt"
MODEL_RECOGNIZER_PATH = "ai_engine/models_weight/mobilefacenet_arcface.onnx"


def create_synthetic_face_image(width: int = 200, height: int = 240) -> np.ndarray:
    """Creates a deterministic synthetic geometric face drawing for unit testing."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 180
    # Head oval
    center = (width // 2, height // 2)
    cv2.ellipse(img, center, (width // 3, height // 2 - 10), 0, 0, 360, (220, 200, 180), -1)
    # Eyes
    left_eye = (width // 2 - 25, height // 2 - 20)
    right_eye = (width // 2 + 25, height // 2 - 20)
    cv2.circle(img, left_eye, 8, (50, 40, 30), -1)
    cv2.circle(img, right_eye, 8, (50, 40, 30), -1)
    # Nose
    cv2.line(img, (width // 2, height // 2 - 10), (width // 2, height // 2 + 15), (140, 120, 100), 3)
    # Mouth
    cv2.ellipse(img, (width // 2, height // 2 + 40), (20, 8), 0, 0, 180, (120, 60, 60), 3)
    return img


# ============================================================================
# 1. Face Detector Tests
# ============================================================================

def test_face_detector_initialization_and_loading():
    if not os.path.exists(MODEL_DETECTOR_PATH):
        pytest.skip("YOLOv8n-Face weights not found")

    det = FaceDetector(model_path=MODEL_DETECTOR_PATH, device="cpu")
    assert det.model is not None
    assert det.device == "cpu"


def test_face_detector_on_synthetic_and_blank_frames():
    if not os.path.exists(MODEL_DETECTOR_PATH):
        pytest.skip("YOLOv8n-Face weights not found")

    det = FaceDetector(model_path=MODEL_DETECTOR_PATH, device="cpu", confidence_threshold=0.20)

    # 1. Blank/dark frame -> does not crash and returns empty list
    blank = np.zeros((300, 300, 3), dtype=np.uint8)
    res_blank = det.detect_faces(blank)
    assert isinstance(res_blank, list)

    # 2. Malformed/Empty frame -> returns empty list safely
    assert det.detect_faces(None) == []
    assert det.detect_faces(np.empty((0, 0, 3), dtype=np.uint8)) == []

    # 3. Very small frame (smaller than min_face_size) -> returns empty list
    tiny = np.zeros((16, 16, 3), dtype=np.uint8)
    assert det.detect_faces(tiny) == []

    # 4. Synthetic face image
    face_img = create_synthetic_face_image(240, 300)
    res = det.detect_faces(face_img)
    assert isinstance(res, list)
    for d in res:
        assert isinstance(d, FaceDetection)
        assert 0.0 <= d.confidence <= 1.0
        assert d.bbox.width >= det.min_face_size
        assert d.bbox.height >= det.min_face_size


# ============================================================================
# 2. Face Recognizer Tests
# ============================================================================

def test_face_recognizer_initialization_and_loading():
    if not os.path.exists(MODEL_RECOGNIZER_PATH):
        pytest.skip("MobileFaceNet ONNX weights not found")

    rec = FaceRecognizer(model_path=MODEL_RECOGNIZER_PATH, device="cpu")
    assert rec.net is not None


def test_face_recognizer_embedding_properties():
    if not os.path.exists(MODEL_RECOGNIZER_PATH):
        pytest.skip("MobileFaceNet ONNX weights not found")

    rec = FaceRecognizer(model_path=MODEL_RECOGNIZER_PATH, device="cpu")

    # Synthetic face crop (112x112)
    crop = create_synthetic_face_image(112, 112)
    emb = rec.compute_embedding(crop)

    # Validate output vector shape and properties
    assert isinstance(emb, np.ndarray)
    assert emb.shape == (512,)
    assert emb.dtype == np.float32
    assert not np.isnan(emb).any()
    assert not np.isinf(emb).any()

    # Verify L2 normalization
    norm = np.linalg.norm(emb)
    assert np.isclose(norm, 1.0, atol=1e-4)


def test_face_recognizer_invalid_and_blank_crops():
    if not os.path.exists(MODEL_RECOGNIZER_PATH):
        pytest.skip("MobileFaceNet ONNX weights not found")

    rec = FaceRecognizer(model_path=MODEL_RECOGNIZER_PATH, device="cpu")

    # None crop -> returns zero vector of size 512
    emb_none = rec.compute_embedding(None)
    assert emb_none.shape == (512,)
    assert np.all(emb_none == 0.0)

    # Empty crop
    emb_empty = rec.compute_embedding(np.empty((0, 0, 3), dtype=np.uint8))
    assert emb_empty.shape == (512,)
    assert np.all(emb_empty == 0.0)


# ============================================================================
# 3. Matcher End-to-End Integration Tests
# ============================================================================

def test_matcher_with_recognizer_embeddings():
    if not os.path.exists(MODEL_RECOGNIZER_PATH):
        pytest.skip("MobileFaceNet ONNX weights not found")

    rec = FaceRecognizer(model_path=MODEL_RECOGNIZER_PATH, device="cpu")
    matcher = CosineFaceMatcher(default_threshold=0.65)

    # Enrolled synthetic face
    enrolled_crop = create_synthetic_face_image(112, 112)
    enrolled_emb = rec.compute_embedding(enrolled_crop)
    assert np.linalg.norm(enrolled_emb) > 0.0

    matcher.register_identity(
        identity_id="STAFF_01",
        display_name="Test Staff Member",
        embedding=enrolled_emb,
        metadata={"department": "Security"}
    )

    # 1. Matching same face crop -> similarity ~ 1.0 -> MATCH
    match_same = matcher.match(enrolled_emb)
    assert match_same.is_match is True
    assert match_same.is_unknown is False
    assert match_same.identity_id == "STAFF_01"
    assert np.isclose(match_same.similarity, 1.0, atol=1e-4)

    # 2. Unknown synthetic face embedding (different pattern)
    different_crop = np.ones((112, 112, 3), dtype=np.uint8) * 40
    cv2.rectangle(different_crop, (20, 20), (90, 90), (200, 200, 200), -1)
    diff_emb = rec.compute_embedding(different_crop)

    match_diff = matcher.match(diff_emb)
    # Different pattern should have lower similarity or return UNKNOWN
    assert match_diff.similarity < 0.95
