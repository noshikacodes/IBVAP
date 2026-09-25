import os
import tempfile
import cv2
import numpy as np
import pytest

from ai_engine.pipeline.stream_reader import (
    VideoReader,
    VideoNotFoundError,
    InvalidVideoFormatError,
    CorruptVideoError
)


def create_synthetic_mp4(filepath: str, num_frames: int = 15, width: int = 64, height: int = 64, fps: float = 10.0):
    """Creates a small valid synthetic MP4 file for testing without internet."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Draw moving circle
        cv2.circle(frame, (10 + i * 2, 10 + i * 2), 5, (0, 255, 0), -1)
        writer.write(frame)
    writer.release()


def test_missing_video_raises_not_found():
    with pytest.raises(VideoNotFoundError):
        VideoReader("non_existent_video_path_123.mp4")


def test_invalid_extension_raises_format_error(tmp_path):
    txt_file = tmp_path / "not_a_video.txt"
    txt_file.write_text("dummy text")
    with pytest.raises(InvalidVideoFormatError):
        VideoReader(str(txt_file))


def test_synthetic_video_reader_reading(tmp_path):
    video_path = str(tmp_path / "synthetic_test.mp4")
    create_synthetic_mp4(video_path, num_frames=12, width=80, height=60, fps=15.0)

    reader = VideoReader(video_path)
    assert reader.width == 80
    assert reader.height == 60
    assert abs(reader.fps - 15.0) < 1.0

    frames_read = list(reader.read_frames())
    assert len(frames_read) == 12

    idx, ts, frame = frames_read[0]
    assert idx == 0
    assert ts == 0.0
    assert frame.shape == (60, 80, 3)


def test_synthetic_video_frame_skipping(tmp_path):
    video_path = str(tmp_path / "synthetic_skip.mp4")
    create_synthetic_mp4(video_path, num_frames=10, width=64, height=64, fps=10.0)

    # skip_frames = 1 means process every 2nd frame: 0, 2, 4, 6, 8 (5 frames)
    reader = VideoReader(video_path, skip_frames=1)
    frames_read = list(reader.read_frames())
    assert len(frames_read) == 5
    indices = [f[0] for f in frames_read]
    assert indices == [0, 2, 4, 6, 8]
