import os
import time
import threading
import logging
from typing import Generator, Tuple, Optional, Union
import cv2
import numpy as np

from ai_engine.stream_manager.types import mask_credentials
from ai_engine.pipeline.gits_resolver import is_gits_source, resolve_gits_hls_url

logger = logging.getLogger("ibvap.pipeline.stream_reader")


class VideoStreamError(Exception):
    """Base exception for video reader errors."""
    pass


class VideoNotFoundError(VideoStreamError):
    """Raised when the specified video file cannot be found."""
    pass


class InvalidVideoFormatError(VideoStreamError):
    """Raised when the video file extension or format is unsupported."""
    pass


class CorruptVideoError(VideoStreamError):
    """Raised when the video stream cannot be opened or decoded."""
    pass


class RTSPConnectionError(VideoStreamError):
    """Raised when an RTSP / network stream fails to connect or reconnect."""
    pass


SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
NETWORK_STREAM_PREFIXES = ("rtsp://", "rtsps://", "http://", "https://", "rtmp://", "gits://")


class LowLatencyFrameReader:
    """
    Dedicated background reader thread that constantly reads frames from a network/HLS
    stream and retains ONLY the single newest frame in memory.
    Prevents OpenCV/FFmpeg internal queue buffer buildup and eliminates live stream lag.
    """
    def __init__(self, cap: cv2.VideoCapture):
        self.cap = cap
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_idx: int = 0
        self.last_served_idx: int = 0
        self.running: bool = True
        self.lock = threading.Lock()
        self.consecutive_failures: int = 0
        self.last_frame_time: float = time.monotonic()
        self.thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.thread.start()

    def _reader_loop(self) -> None:
        idx = 0
        while self.running:
            if not self.cap.isOpened():
                time.sleep(0.02)
                continue
            try:
                ret, frame = self.cap.read()
            except Exception:
                # Capture was released during reconnect
                if not self.running:
                    break
                time.sleep(0.05)
                continue
            if not ret or frame is None:
                self.consecutive_failures += 1
                time.sleep(0.01)
                continue

            idx += 1
            self.consecutive_failures = 0
            self.last_frame_time = time.monotonic()
            with self.lock:
                self.latest_frame = frame
                self.latest_idx = idx

    def get_latest_frame(self, timeout: float = 3.0) -> Tuple[int, Optional[np.ndarray]]:
        start_t = time.monotonic()
        while self.running and (time.monotonic() - start_t) < timeout:
            with self.lock:
                if self.latest_frame is not None and (self.latest_idx > self.last_served_idx or self.last_served_idx == 0):
                    self.last_served_idx = self.latest_idx
                    return self.latest_idx, self.latest_frame
            time.sleep(0.005)
        with self.lock:
            if self.latest_frame is not None:
                self.last_served_idx = self.latest_idx
            return self.latest_idx, self.latest_frame

    def stop(self) -> None:
        self.running = False


class VideoReader:
    """
    Robust Video & RTSP Stream Frame Reader with stream introspection,
    credential masking, transport protocol selection (TCP/UDP), automatic reconnection
    with exponential backoff, stall detection watchdog, GITS public CCTV resolution,
    and health telemetry.
    """

    def __init__(
        self,
        video_path: Union[str, int],
        skip_frames: int = 0,
        reconnect_delay: float = 2.0,
        max_retries: int = 50,
        transport: str = "tcp",
        stall_timeout_seconds: float = 20.0,
        low_latency: bool = False
    ):
        self.raw_source = video_path
        self.skip_frames = max(0, skip_frames)
        self.reconnect_delay = max(0.001, float(reconnect_delay))
        self.max_retries = max(1, int(max_retries))
        self.transport = str(transport).lower() if transport in ("tcp", "udp") else "tcp"
        self.stall_timeout_seconds = max(0.1, float(stall_timeout_seconds))
        self.low_latency = bool(low_latency)

        # Detect source type
        self.is_network_stream = False
        self.is_webcam = False
        self.is_gits_stream = is_gits_source(video_path)

        if isinstance(video_path, int) or (isinstance(video_path, str) and video_path.isdigit() and not self.is_gits_stream):
            self.is_webcam = True
            self.video_path = int(video_path)
            self.masked_path = f"Webcam({video_path})"
        elif self.is_gits_stream:
            self.is_network_stream = True
            self.masked_path = f"GITS({video_path})"
            self.video_path = str(video_path)
            self._resolve_gits_stream_url()
        elif isinstance(video_path, str) and video_path.lower().startswith(NETWORK_STREAM_PREFIXES):
            self.is_network_stream = True
            self.video_path = video_path.strip()
            self.masked_path = mask_credentials(self.video_path)
        else:
            self.video_path = os.path.abspath(str(video_path))
            self.masked_path = self.video_path

        self._cap: Optional[cv2.VideoCapture] = None
        self._fps: float = 25.0
        self._width: int = 640
        self._height: int = 480
        self._total_frames: int = 0
        self._duration_sec: float = 0.0
        self._reconnect_count: int = 0
        self._frames_read: int = 0
        self._last_frame_timestamp: Optional[float] = None
        self._start_monotonic: float = time.monotonic()

        self._validate_and_probe()

    def _resolve_gits_stream_url(self) -> None:
        """Dynamically resolves HLS stream URL from GITS portal and updates video_path."""
        if not self.is_gits_stream:
            return
        try:
            resolved_url, meta = resolve_gits_hls_url(str(self.raw_source))
            self.video_path = resolved_url
            cctv_id = meta.get("cctv_id", self.raw_source)
            self.masked_path = f"GITS({cctv_id})"
            logger.info("Resolved GITS camera stream ID=%s -> %s (Session valid %dm)", cctv_id, mask_credentials(resolved_url), meta.get("valid_minutes", 120))
        except Exception as e:
            logger.warning("Failed to dynamically resolve GITS stream for '%s': %s", self.raw_source, e)

    def _open_capture(self, refresh_source: bool = False) -> cv2.VideoCapture:
        """Opens a cv2.VideoCapture with optimized transport flags for RTSP/HLS/file."""
        if self.is_gits_stream and refresh_source:
            self._resolve_gits_stream_url()

        if self.is_network_stream:
            is_hls = isinstance(self.video_path, str) and (".m3u8" in self.video_path or "http" in self.video_path.lower())
            if not is_hls:
                # Set transport hints for RTSP (TCP preferred for reliability in CCTV)
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;{self.transport}|stimeout;5000000|fflags;nobuffer|flags;low_delay"
            else:
                # Optimized flags for HTTP / HLS live streaming (zero buffering)
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;5000000|fflags;nobuffer|flags;low_delay"
            return cv2.VideoCapture(self.video_path, cv2.CAP_FFMPEG)
        return cv2.VideoCapture(self.video_path)

    def _validate_and_probe(self) -> None:
        """Validates source path or probes RTSP stream headers."""
        if self.is_network_stream or self.is_webcam:
            # Network live streams: set default live stream properties; connection handled in read_frames
            self._fps = 15.0
            self._width = 640
            self._height = 480
            self._total_frames = 0
            self._duration_sec = 0.0
            return

        # Local video file validation
        if not os.path.exists(self.video_path):
            raise VideoNotFoundError(
                f"Video file not found at path: {self.masked_path}"
            )

        if not os.path.isfile(self.video_path):
            raise VideoNotFoundError(
                f"Target path is not a regular file: {self.masked_path}"
            )

        _, ext = os.path.splitext(self.video_path)
        if ext.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            raise InvalidVideoFormatError(
                f"Unsupported video format '{ext}'. Supported formats: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}"
            )

        # Probe local video headers
        cap = self._open_capture()
        if not cap.isOpened():
            raise CorruptVideoError(
                f"Failed to open video source '{self.masked_path}'. File may be corrupt or missing codec support."
            )

        fps_val = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        self._fps = fps_val if (0.0 < fps_val <= 240.0) else 25.0

        w_val = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h_val = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._width = w_val if w_val > 0 else 640
        self._height = h_val if h_val > 0 else 480
        self._total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if self._width <= 0 or self._height <= 0:
            cap.release()
            raise CorruptVideoError(
                f"Video '{self.masked_path}' reported invalid dimensions ({self._width}x{self._height})."
            )

        if self._total_frames > 0:
            self._duration_sec = self._total_frames / self._fps
        else:
            self._duration_sec = 0.0

        cap.release()

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def resolution(self) -> str:
        return f"{self._width}x{self._height}"

    @property
    def total_frames(self) -> int:
        return self._total_frames

    @property
    def duration_sec(self) -> float:
        return self._duration_sec

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    @property
    def frames_read(self) -> int:
        return self._frames_read

    @property
    def last_frame_timestamp(self) -> Optional[float]:
        return self._last_frame_timestamp

    @property
    def fps_estimate(self) -> float:
        elapsed = time.monotonic() - self._start_monotonic
        if elapsed > 0 and self._frames_read > 0:
            return round(self._frames_read / elapsed, 1)
        return self._fps

    def read_frames(self) -> Generator[Tuple[int, float, np.ndarray], None, None]:
        """
        Yields (frame_index, timestamp_in_seconds, frame_bgr_ndarray).
        For live network/RTSP/HLS streams, utilizes LowLatencyFrameReader to always
        deliver the single newest real-time frame, eliminating buffer latency.
        """
        cap = self._open_capture()
        grabber = LowLatencyFrameReader(cap) if (self.is_network_stream and self.low_latency) else None
        frame_idx = 0
        consecutive_failures = 0
        current_delay = self.reconnect_delay
        last_success_time = time.monotonic()

        try:
            while True:
                if not cap.isOpened():
                    if self.is_network_stream:
                        consecutive_failures += 1
                        if self.max_retries > 0 and consecutive_failures > self.max_retries:
                            logger.error("RTSP stream '%s' max reconnection retries (%d) exceeded.", self.masked_path, self.max_retries)
                            break
                        logger.info("Connecting to live source '%s' (Attempt %d/%d)...", self.masked_path, consecutive_failures, self.max_retries)
                        time.sleep(current_delay)
                        current_delay = min(current_delay * 1.5, 10.0)
                        if grabber is not None:
                            grabber.stop()
                            time.sleep(0.05)
                        cap.release()
                        cap = self._open_capture(refresh_source=True)
                        grabber = LowLatencyFrameReader(cap) if (self.is_network_stream and self.low_latency) else None
                        continue
                    else:
                        raise CorruptVideoError(f"Could not open video source: {self.masked_path}")

                if self.is_network_stream and grabber is not None:
                    _, frame = grabber.get_latest_frame(timeout=6.0)
                    ret = frame is not None
                else:
                    ret, frame = cap.read()

                now = time.monotonic()

                # Check for stalled stream watchdog
                effective_last_frame = grabber.last_frame_time if (grabber is not None) else last_success_time
                if self.is_network_stream and (now - effective_last_frame) > self.stall_timeout_seconds:
                    logger.warning("Live stream '%s' stalled (>%.1fs without frames). Triggering reconnect...", self.masked_path, self.stall_timeout_seconds)
                    consecutive_failures += 1
                    self._reconnect_count += 1
                    if self.max_retries > 0 and consecutive_failures > self.max_retries:
                        logger.error("Live stream '%s' exceeded max retries (%d). Stopping reader.", self.masked_path, self.max_retries)
                        break
                    if grabber is not None:
                        grabber.stop()
                        time.sleep(0.05)
                    cap.release()
                    time.sleep(self.reconnect_delay)
                    cap = self._open_capture(refresh_source=True)
                    grabber = LowLatencyFrameReader(cap) if (self.is_network_stream and self.low_latency) else None
                    last_success_time = time.monotonic()
                    continue

                if not ret or frame is None:
                    if self.is_network_stream:
                        consecutive_failures += 1
                        self._reconnect_count += 1
                        if self.max_retries > 0 and consecutive_failures > self.max_retries:
                            logger.error("Live stream interrupted on '%s'. Exceeded max retries (%d).", self.masked_path, self.max_retries)
                            break

                        logger.warning("Live stream interrupted on '%s'. Reconnecting (%d/%d) in %.1fs...", self.masked_path, consecutive_failures, self.max_retries, current_delay)
                        time.sleep(current_delay)
                        current_delay = min(current_delay * 1.5, 10.0)
                        if grabber is not None:
                            grabber.stop()
                            time.sleep(0.05)
                        cap.release()
                        cap = self._open_capture(refresh_source=True)
                        grabber = LowLatencyFrameReader(cap) if (self.is_network_stream and self.low_latency) else None
                        continue
                    else:
                        # End of regular file
                        break

                # Reset failure counter upon successful frame
                consecutive_failures = 0
                current_delay = self.reconnect_delay
                last_success_time = time.monotonic()
                self._last_frame_timestamp = time.time()
                self._frames_read += 1

                # Update probed resolution from live frame if default
                if frame is not None and (self._width == 640 and self._height == 480):
                    h, w = frame.shape[:2]
                    if w > 0 and h > 0:
                        self._width = w
                        self._height = h

                # Apply frame skip if requested (only for offline local video files; live streams naturally drop old frames)
                if not self.is_network_stream and self.skip_frames > 0 and (frame_idx % (self.skip_frames + 1) != 0):
                    frame_idx += 1
                    continue

                timestamp_sec = frame_idx / self._fps
                yield frame_idx, timestamp_sec, frame
                frame_idx += 1

        finally:
            if grabber is not None:
                grabber.stop()
            cap.release()

    def __enter__(self) -> "VideoReader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
