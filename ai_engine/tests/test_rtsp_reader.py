import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import cv2

from ai_engine.pipeline.stream_reader import (
    VideoReader,
    VideoStreamError,
    CorruptVideoError,
    NETWORK_STREAM_PREFIXES,
)


def test_rtsp_source_detection():
    rtsp_reader = VideoReader(
        video_path="rtsp://localhost:8554/ibvap-demo",
        reconnect_delay=0.1,
        max_retries=2
    )
    assert rtsp_reader.is_network_stream is True
    assert rtsp_reader.is_webcam is False
    assert rtsp_reader.video_path == "rtsp://localhost:8554/ibvap-demo"


def test_http_source_detection():
    http_reader = VideoReader(
        video_path="http://192.168.1.100:8080/stream.mjpg",
        reconnect_delay=0.1,
        max_retries=2
    )
    assert http_reader.is_network_stream is True
    assert http_reader.is_webcam is False


def test_webcam_source_detection():
    webcam_reader = VideoReader(
        video_path=0,
        reconnect_delay=0.1,
        max_retries=2
    )
    assert webcam_reader.is_network_stream is False
    assert webcam_reader.is_webcam is True
    assert webcam_reader.video_path == 0


def test_rtsp_stream_interruption_and_successful_reconnection():
    """Simulates an RTSP stream that drops a frame, triggers reconnection, and resumes frames."""
    reader = VideoReader(
        video_path="rtsp://localhost:8554/test-cam",
        reconnect_delay=0.01,
        max_retries=3
    )

    # Synthetic frames
    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame2 = np.ones((480, 640, 3), dtype=np.uint8)

    # First capture yields 1 frame then disconnects (False)
    mock_cap1 = MagicMock()
    mock_cap1.isOpened.return_value = True
    mock_cap1.read.side_effect = [(True, frame1), (False, None)]

    # Second capture (after reconnect) yields 1 frame then ends
    mock_cap2 = MagicMock()
    mock_cap2.isOpened.return_value = True
    mock_cap2.read.side_effect = [(True, frame2), (False, None)]

    # Third capture terminates stream
    mock_cap3 = MagicMock()
    mock_cap3.isOpened.return_value = False

    with patch.object(reader, "_open_capture", side_effect=[mock_cap1, mock_cap2, mock_cap3, mock_cap3, mock_cap3]):
        frames = list(reader.read_frames())

    assert len(frames) == 2
    assert frames[0][0] == 0  # frame_idx
    assert frames[1][0] == 1  # frame_idx
    assert reader.reconnect_count >= 1


def test_rtsp_stream_max_retries_exhaustion():
    """Simulates a permanently disconnected RTSP stream that aborts after max_retries without looping."""
    reader = VideoReader(
        video_path="rtsp://localhost:8554/dead-cam",
        reconnect_delay=0.01,
        max_retries=2
    )

    mock_cap_dead = MagicMock()
    mock_cap_dead.isOpened.return_value = False

    with patch.object(reader, "_open_capture", return_value=mock_cap_dead):
        frames = list(reader.read_frames())

    # Should gracefully terminate with 0 frames without hanging
    assert len(frames) == 0
