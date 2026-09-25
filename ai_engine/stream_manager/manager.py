import os
import json
import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any

from ai_engine.stream_manager.types import (
    StreamConfig,
    StreamState,
    StreamStatusInfo,
    mask_credentials,
)
from ai_engine.stream_manager.worker_process import WorkerProcessHandle

logger = logging.getLogger("ibvap.stream_manager")


class StreamManager:
    """
    Centralized Multi-Stream Worker Supervisor.
    Orchestrates isolated AI worker processes per camera feed, monitors health,
    and applies bounded exponential backoff on crash recovery.
    """

    def __init__(
        self,
        max_streams: int = 8,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        max_restart_attempts: int = 10,
        stable_period_seconds: float = 30.0,
        popen_factory: Optional[Callable[..., Any]] = None,
        python_executable: Optional[str] = None
    ):
        self.max_streams = max(1, int(max_streams))
        self.initial_backoff = max(0.1, float(initial_backoff))
        self.max_backoff = max(self.initial_backoff, float(max_backoff))
        self.max_restart_attempts = max(1, int(max_restart_attempts))
        self.stable_period_seconds = max(1.0, float(stable_period_seconds))

        self._popen_factory = popen_factory
        self._python_executable = python_executable

        self._handles: Dict[str, WorkerProcessHandle] = {}
        self._lock = threading.Lock()

        # Monitoring background thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def get_active_stream_count(self) -> int:
        """Returns number of streams currently in STARTING or RUNNING or RECONNECTING state."""
        with self._lock:
            return sum(
                1 for h in self._handles.values()
                if h.state in (StreamState.STARTING, StreamState.RUNNING, StreamState.RECONNECTING)
            )

    def start_stream(self, config: StreamConfig) -> bool:
        """
        Registers and starts a new camera video stream worker process.
        Enforces max_streams safety limit.
        """
        with self._lock:
            # Check capacity if starting a new or previously stopped stream
            active_count = sum(
                1 for h in self._handles.values()
                if h.state in (StreamState.STARTING, StreamState.RUNNING, StreamState.RECONNECTING)
            )
            
            existing = self._handles.get(config.camera_id)
            if existing is not None and existing.state == StreamState.RUNNING:
                logger.warning("[%s] Stream is already running.", config.camera_id)
                return False

            if active_count >= self.max_streams and (existing is None or existing.state != StreamState.RUNNING):
                logger.error(
                    "Cannot start stream [%s]: Maximum concurrent streams limit (%d) reached.",
                    config.camera_id,
                    self.max_streams
                )
                return False

            handle = WorkerProcessHandle(config)
            self._handles[config.camera_id] = handle

            if not config.enabled:
                logger.info("[%s] Stream registered but disabled. State: STOPPED", config.camera_id)
                return False

            success = handle.start(
                popen_factory=self._popen_factory,
                python_executable=self._python_executable
            )
            return success

    def stop_stream(self, camera_id: str, timeout: float = 5.0) -> bool:
        """Stops a specific camera stream worker process."""
        with self._lock:
            handle = self._handles.get(camera_id)
            if handle is None:
                logger.warning("Cannot stop stream [%s]: Camera not registered.", camera_id)
                return False

            handle.stop(timeout=timeout)
            return True

    def restart_stream(self, camera_id: str, timeout: float = 5.0) -> bool:
        """Restarts a specific camera stream."""
        with self._lock:
            handle = self._handles.get(camera_id)
            if handle is None:
                logger.warning("Cannot restart stream [%s]: Camera not registered.", camera_id)
                return False

            handle.stop(timeout=timeout)
            handle.restart_count = 0  # Manual restart resets crash counter
            handle.last_error = None
            return handle.start(
                popen_factory=self._popen_factory,
                python_executable=self._python_executable
            )

    def stop_all(self, timeout: float = 5.0) -> None:
        """Stops all active camera streams gracefully."""
        self.stop_monitoring()
        with self._lock:
            for handle in self._handles.values():
                handle.stop(timeout=timeout)

    def get_status(self, camera_id: str) -> Optional[StreamStatusInfo]:
        """Retrieves runtime status of a specific camera."""
        with self._lock:
            handle = self._handles.get(camera_id)
            if handle is not None:
                return handle.get_status()
            return None

    def get_all_status(self) -> List[StreamStatusInfo]:
        """Retrieves status snapshots of all registered cameras."""
        with self._lock:
            return [h.get_status() for h in self._handles.values()]

    def calculate_backoff(self, restart_count: int) -> float:
        """Computes exponential backoff with ceiling: min(initial * 2^count, max_backoff)."""
        backoff = self.initial_backoff * (2 ** max(0, restart_count - 1))
        return min(backoff, self.max_backoff)

    def monitor_step(self, current_time: Optional[float] = None) -> Dict[str, StreamState]:
        """
        Single inspection step across all managed processes.
        Detects crashes, calculates backoffs, restarts dropped workers,
        and resets stable running streams.
        """
        now = current_time if current_time is not None else time.time()
        states_summary: Dict[str, StreamState] = {}

        with self._lock:
            for cam_id, handle in list(self._handles.items()):
                # 1. Inspect RUNNING handles for sudden process exit
                if handle.state == StreamState.RUNNING:
                    exit_code = handle.poll()
                    if exit_code is not None:
                        # Process terminated unexpectedly
                        if handle.restart_count < self.max_restart_attempts:
                            handle.restart_count += 1
                            handle.last_restart_attempt = now
                            err_msg = f"Process exited with code {exit_code}"
                            handle._set_state(StreamState.RECONNECTING, error_msg=err_msg)
                            logger.warning(
                                "[%s] RECONNECTING (Attempt %d/%d, Backoff %.1fs): %s",
                                cam_id,
                                handle.restart_count,
                                self.max_restart_attempts,
                                self.calculate_backoff(handle.restart_count),
                                err_msg
                            )
                        else:
                            err_msg = f"Max restart attempts ({self.max_restart_attempts}) exceeded. Process exit code {exit_code}"
                            handle._set_state(StreamState.FAILED, error_msg=err_msg)
                            logger.error("[%s] FAILED: %s", cam_id, err_msg)
                    else:
                        # Check for stable running reset
                        uptime = (datetime.utcnow() - handle.start_time).total_seconds() if handle.start_time else 0.0
                        if uptime >= self.stable_period_seconds and handle.restart_count > 0:
                            logger.info(
                                "[%s] Stream has run stably for %.1fs. Resetting restart counter.",
                                cam_id,
                                uptime
                            )
                            handle.restart_count = 0

                # 2. Inspect RECONNECTING handles for backoff expiration
                elif handle.state == StreamState.RECONNECTING:
                    required_backoff = self.calculate_backoff(handle.restart_count)
                    elapsed = now - handle.last_restart_attempt
                    if elapsed >= required_backoff:
                        logger.info(
                            "[%s] Backoff elapsed (%.1fs >= %.1fs). Restarting worker...",
                            cam_id,
                            elapsed,
                            required_backoff
                        )
                        handle.start(
                            popen_factory=self._popen_factory,
                            python_executable=self._python_executable
                        )

                states_summary[cam_id] = handle.state

        return states_summary

    def start_monitoring(self, interval: float = 1.0) -> None:
        """Starts the background supervisor monitor thread."""
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()

        def _run_loop():
            logger.info("StreamManager supervisor monitoring loop started (interval: %.1fs)", interval)
            while not self._stop_event.is_set():
                try:
                    self.monitor_step()
                except Exception as e:
                    logger.error("Error in StreamManager monitor loop: %s", e)
                self._stop_event.wait(timeout=interval)
            logger.info("StreamManager supervisor monitoring loop stopped.")

        self._monitor_thread = threading.Thread(
            target=_run_loop,
            name="StreamManagerMonitor",
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stops the background monitor thread."""
        self._stop_event.set()
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=3.0)
            self._monitor_thread = None

    def load_from_json(self, json_path: str, autostart: bool = True) -> int:
        """
        Loads stream definitions from a JSON file and optionally starts them.
        Returns the number of successfully registered streams.
        """
        if not os.path.exists(json_path):
            logger.error("Stream configuration file not found: %s", json_path)
            return 0

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to parse stream configuration JSON from %s: %s", json_path, e)
            return 0

        streams_list = data.get("streams", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        registered_count = 0

        for item in streams_list:
            if not isinstance(item, dict):
                continue
            try:
                config = StreamConfig.from_dict(item)
                if autostart:
                    if self.start_stream(config):
                        registered_count += 1
                else:
                    with self._lock:
                        self._handles[config.camera_id] = WorkerProcessHandle(config)
                        registered_count += 1
            except Exception as e:
                logger.warning("Failed to register stream config item %s: %s", item, e)

        logger.info("Loaded and processed %d streams from %s", registered_count, json_path)
        return registered_count
