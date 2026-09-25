import numpy as np
import pytest

from ai_engine.pipeline.annotator import VideoAnnotator, VideoWriter
from ai_engine.pipeline.types import Detection, BoundingBox, ObjectClass


def test_annotator_on_synthetic_frame():
    annotator = VideoAnnotator(draw_telemetry=True)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    detections = [
        Detection(
            class_name=ObjectClass.PERSON,
            confidence=0.91,
            bbox=BoundingBox(50, 50, 100, 180),
            raw_class_name="person"
        ),
        Detection(
            class_name=ObjectClass.CAR,
            confidence=0.85,
            bbox=BoundingBox(120, 80, 280, 200),
            raw_class_name="car"
        )
    ]

    annotated = annotator.annotate_frame(frame, detections, frame_idx=10, fps=28.5)
    assert annotated is not None
    assert annotated.shape == (240, 320, 3)
    # The annotated frame should have been modified (non-zero pixels where badges/boxes/HUD are drawn)
    assert np.count_nonzero(annotated) > 0


def test_video_writer_synthetic(tmp_path):
    output_path = str(tmp_path / "test_out.mp4")
    writer = VideoWriter(output_path=output_path, fps=10.0, width=64, height=64)

    dummy_frame = np.ones((64, 64, 3), dtype=np.uint8) * 128
    for _ in range(5):
        writer.write_frame(dummy_frame)
    writer.release()

    assert writer._writer is None
