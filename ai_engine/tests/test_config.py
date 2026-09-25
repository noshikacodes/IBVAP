import pytest
from ai_engine.pipeline.config import InferenceConfig, DEFAULT_TARGET_CLASSES


def test_valid_inference_config():
    cfg = InferenceConfig(
        input_path="sample.mp4",
        output_path="out.mp4",
        confidence_threshold=0.55,
        imgsz=640,
        device="cpu",
        target_classes=["person", "car"]
    )
    assert cfg.confidence_threshold == 0.55
    assert cfg.imgsz == 640
    assert cfg.is_class_allowed("person") is True
    assert cfg.is_class_allowed("car") is True
    assert cfg.is_class_allowed("airplane") is False


def test_invalid_confidence_raises():
    with pytest.raises(ValueError, match="Confidence threshold"):
        InferenceConfig(
            input_path="sample.mp4",
            output_path="out.mp4",
            confidence_threshold=1.5
        )


def test_invalid_imgsz_raises():
    with pytest.raises(ValueError, match="imgsz"):
        InferenceConfig(
            input_path="sample.mp4",
            output_path="out.mp4",
            imgsz=500  # Not a multiple of 32
        )


def test_invalid_skip_frames_raises():
    with pytest.raises(ValueError, match="skip_frames"):
        InferenceConfig(
            input_path="sample.mp4",
            output_path="out.mp4",
            skip_frames=-1
        )
