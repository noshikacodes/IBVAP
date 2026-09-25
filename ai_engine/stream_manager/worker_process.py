import sys
import os
import subprocess
import logging
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

from ai_engine.stream_manager.types import StreamConfig, StreamState, StreamStatusInfo, mask_credentials

logger = logging.getLogger("ibvap.stream_manager.worker")


def build_worker_command(
    config: StreamConfig,
    python_executable: Optional[str] = None
) -> List[str]:
    """
    Translates a StreamConfig into the corresponding CLI arguments
    for invoking `ai_engine.worker`.
    """
    py_exec = python_executable or sys.executable

    cmd: List[str] = [
        py_exec,
        "-m",
        "ai_engine.worker",
        "--input",
        config.input_url,
        "--camera-id",
        config.camera_id,
        "--model",
        config.model_name,
        "--conf",
        str(config.confidence_threshold),
        "--reconnect-delay",
        str(config.reconnect_delay),
        "--max-retries",
        str(config.max_retries),
        "--tracker",
        "bytetrack",
    ]

    if config.output_path:
        cmd.extend(["--output", config.output_path])

    if config.spatial_rules_path:
        cmd.extend(["--spatial-rules", config.spatial_rules_path])

    if config.skip_frames > 0:
        cmd.extend(["--skip-frames", str(config.skip_frames)])

    # ANPR Arguments (Phase 5B)
    if config.enable_anpr:
        cmd.append("--anpr")
        if config.anpr_model:
            cmd.extend(["--anpr-model", config.anpr_model])
        if config.anpr_ocr:
            cmd.extend(["--anpr-ocr", config.anpr_ocr])
        if config.anpr_confidence:
            cmd.extend(["--anpr-conf", str(config.anpr_confidence)])
        if config.anpr_stride:
            cmd.extend(["--anpr-stride", str(config.anpr_stride)])
        if config.anpr_votes:
            cmd.extend(["--anpr-votes", str(config.anpr_votes)])

    # FRS Arguments (Phase 5C)
    if config.enable_frs:
        cmd.append("--frs")
        if config.frs_gallery:
            cmd.extend(["--frs-gallery", config.frs_gallery])
        if config.frs_threshold:
            cmd.extend(["--frs-thresh", str(config.frs_threshold)])
        if config.frs_stride:
            cmd.extend(["--frs-stride", str(config.frs_stride)])
        if config.frs_votes:
            cmd.extend(["--frs-votes", str(config.frs_votes)])
        if config.frs_min_size:
            cmd.extend(["--frs-min-size", str(config.frs_min_size)])
        if config.frs_detector:
            cmd.extend(["--frs-detector", config.frs_detector])
        if config.frs_recognizer:
            cmd.extend(["--frs-recognizer", config.frs_recognizer])

    if config.extra_args:
        cmd.extend(config.extra_args)

    return cmd


class WorkerProcessHandle:
    """
    Manages the lifecycle, subprocess execution, and state telemetry
    of a single video analytics worker process.
    """

    def __init__(self, config: StreamConfig):
        self.config = config
        self.state: StreamState = StreamState.STOPPED
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.utcnow()
        self.restart_count: int = 0
        self.last_error: Optional[str] = None
        self.last_restart_attempt: float = 0.0

    def _set_state(self, new_state: StreamState, error_msg: Optional[str] = None) -> None:
        self.state = new_state
        self.last_state_change = datetime.utcnow()
        if error_msg is not None:
            self.last_error = error_msg
        logger.info(
            "[%s] %s (Source: %s)",
            self.config.camera_id,
            self.state.value,
            self.config.masked_input_url
        )

    def start(
        self,
        popen_factory: Optional[Callable[..., Any]] = None,
        python_executable: Optional[str] = None
    ) -> bool:
        """Spawns the worker subprocess."""
        if self.process is not None and self.process.poll() is None:
            logger.warning("[%s] Process already running (PID %s)", self.config.camera_id, self.process.pid)
            return False

        if not self.config.enabled:
            self._set_state(StreamState.STOPPED, error_msg="Stream is disabled")
            return False

        self._set_state(StreamState.STARTING)
        cmd = build_worker_command(self.config, python_executable=python_executable)

        # Log masked command without secrets
        masked_cmd = [mask_credentials(arg) for arg in cmd]
        logger.debug("[%s] Spawning worker: %s", self.config.camera_id, " ".join(masked_cmd))

        factory = popen_factory or subprocess.Popen
        try:
            self.process = factory(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.start_time = datetime.utcnow()
            self._set_state(StreamState.RUNNING)
            return True
        except Exception as e:
            self.process = None
            self._set_state(StreamState.FAILED, error_msg=str(e))
            logger.error("[%s] Failed to launch worker process: %s", self.config.camera_id, e)
            return False

    def poll(self) -> Optional[int]:
        """Polls the active process. Returns exit code if terminated, else None."""
        if self.process is None:
            return None
        return self.process.poll()

    def stop(self, timeout: float = 5.0) -> None:
        """Gracefully terminates the worker subprocess."""
        if self.process is None:
            self._set_state(StreamState.STOPPED)
            return

        self._set_state(StreamState.STOPPING)
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("[%s] Process did not terminate within %.1fs, killing...", self.config.camera_id, timeout)
                self.process.kill()
                self.process.wait(timeout=2.0)
        except Exception as e:
            logger.warning("[%s] Error stopping worker process: %s", self.config.camera_id, e)
        finally:
            self.process = None
            self._set_state(StreamState.STOPPED)

    def get_status(self) -> StreamStatusInfo:
        """Returns the current telemetry status and field calibration snapshot."""
        uptime = 0.0
        if self.state == StreamState.RUNNING and self.start_time:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()

        pid = self.process.pid if self.process is not None else None

        # Map state to high-level C2 connection state
        state_map = {
            StreamState.RUNNING: "ONLINE",
            StreamState.STARTING: "CONNECTING",
            StreamState.RECONNECTING: "DEGRADED",
            StreamState.FAILED: "OFFLINE",
            StreamState.STOPPED: "OFFLINE",
            StreamState.STOPPING: "OFFLINE",
        }
        conn_state = state_map.get(self.state, "OFFLINE")

        calibration = {
            "name": self.config.name,
            "location": self.config.location,
            "resolution": self.config.resolution,
            "fps": self.config.fps,
            "transport": self.config.transport,
            "min_object_size": self.config.min_object_size,
            "roi": self.config.roi,
            "night_mode": self.config.night_mode,
            "stall_timeout_seconds": self.config.stall_timeout_seconds,
            "confidence_threshold": self.config.confidence_threshold,
            "anpr_confidence": self.config.anpr_confidence,
            "frs_confidence": self.config.frs_confidence,
            "frs_threshold": self.config.frs_threshold,
            "spatial_rules_enabled": bool(self.config.spatial_rules_path),
            "spatial_rules_path": self.config.spatial_rules_path,
        }

        return StreamStatusInfo(
            camera_id=self.config.camera_id,
            name=self.config.name,
            location=self.config.location,
            state=self.state,
            connection_state=conn_state,
            input_url=self.config.masked_input_url,
            process_id=pid,
            start_time=self.start_time,
            last_state_change=self.last_state_change,
            restart_count=self.restart_count,
            reconnect_count=self.restart_count,
            frames_received=int(uptime * self.config.fps) if self.state == StreamState.RUNNING else 0,
            fps_estimate=float(self.config.fps),
            resolution=self.config.resolution,
            last_error=self.last_error,
            uptime_seconds=max(0.0, uptime),
            enable_anpr=self.config.enable_anpr,
            enable_frs=self.config.enable_frs,
            enabled=self.config.enabled,
            calibration_metadata=calibration,
        )
