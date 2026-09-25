import time
from typing import Dict, Optional, List, Callable, Any, Tuple
from datetime import datetime
import logging
import uuid

from ai_engine.pipeline.ptz.types import (
    PTZPosition,
    PTZCommand,
    PTZCommandResult,
    PTZCommandStatus,
    PTZCameraState,
    PTZConfig,
    PTZDriverType,
)
from ai_engine.pipeline.ptz.interfaces import BasePTZDriver
from ai_engine.pipeline.ptz.simulator import SimulatedPTZDriver
from ai_engine.pipeline.ptz.onvif_adapter import ONVIFPTZDriver
from ai_engine.pipeline.ptz.cue_calculator import PTZCueCalculator

logger = logging.getLogger("ibvap.ptz.controller")


class PTZController:
    """
    Central PTZ Controller & Threat Escalation Coordinator.
    Manages PTZ hardware/simulation drivers, evaluates threat severity policies,
    calculates slew-to-cue coordinates, applies command cooldowns & deduplication,
    and escalates repeated perimeter breaches.
    """

    def __init__(
        self,
        default_cooldown_seconds: float = 2.0,
        escalation_window_seconds: float = 5.0,
        escalation_repeat_threshold: int = 2
    ):
        self.default_cooldown_seconds = default_cooldown_seconds
        self.escalation_window_seconds = escalation_window_seconds
        self.escalation_repeat_threshold = escalation_repeat_threshold

        self._drivers: Dict[str, BasePTZDriver] = {}
        self._configs: Dict[str, PTZConfig] = {}
        self._last_command_time: Dict[str, float] = {}
        self._last_cued_target: Dict[str, Tuple[int, float, float]] = {}  # camera_id -> (track_id, pan, tilt)

        # Track history for threat escalation: (camera_id, track_id) -> list of timestamp floats
        self._track_history: Dict[Tuple[str, int], List[float]] = {}
        self._telemetry_listeners: List[Callable[[Dict[str, Any]], None]] = []

    def register_camera(self, config: PTZConfig) -> BasePTZDriver:
        """Registers a camera configuration and instantiates its driver."""
        self._configs[config.camera_id] = config

        if config.ptz_driver == "onvif":
            driver = ONVIFPTZDriver(config)
        else:
            driver = SimulatedPTZDriver(config)

        driver.connect()
        self._drivers[config.camera_id] = driver
        return driver

    def get_driver(self, camera_id: str) -> Optional[BasePTZDriver]:
        """Returns the driver for a specific camera or registers a default simulator."""
        if camera_id not in self._drivers:
            cfg = self._configs.get(camera_id) or PTZConfig(camera_id=camera_id, ptz_enabled=True)
            self.register_camera(cfg)
        return self._drivers.get(camera_id)

    def register_telemetry_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Registers a listener for PTZ command and telemetry events."""
        self._telemetry_listeners.append(callback)

    def _emit_telemetry(self, event_type: str, data: Dict[str, Any]) -> None:
        payload = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        for listener in self._telemetry_listeners:
            try:
                listener(payload)
            except Exception as e:
                logger.warning("Error in PTZ telemetry listener: %s", e)

    def evaluate_threat_escalation(
        self,
        camera_id: str,
        track_id: int,
        base_severity: str,
        current_time: Optional[float] = None
    ) -> str:
        """
        Deterministically evaluates if repeated intrusion events escalate threat priority.
        If >= escalation_repeat_threshold events occur within escalation_window_seconds,
        priority escalates to CRITICAL.
        """
        now = current_time if current_time is not None else time.time()
        key = (camera_id, track_id)

        timestamps = self._track_history.get(key, [])
        # Filter timestamps within sliding window
        valid_ts = [t for t in timestamps if (now - t) <= self.escalation_window_seconds]
        valid_ts.append(now)
        self._track_history[key] = valid_ts

        if len(valid_ts) >= self.escalation_repeat_threshold:
            logger.info(
                "[%s] Track #%d ESCALATED to CRITICAL (%d breach events in %.1fs)",
                camera_id, track_id, len(valid_ts), self.escalation_window_seconds
            )
            return "CRITICAL"

        return base_severity.upper()

    def process_threat_cue(
        self,
        camera_id: str,
        target_bbox_or_point: Any,
        severity: str = "HIGH",
        event_type: str = "intrusion",
        track_id: Optional[int] = None,
        frame_width: int = 640,
        frame_height: int = 480,
        current_time: Optional[float] = None
    ) -> Optional[PTZCommandResult]:
        """
        End-to-End Threat Slew-to-Cue Dispatcher:
        1. Checks camera PTZ enablement & automatic cue policies.
        2. Applies threat escalation for repeat track breaches.
        3. Enforces rate-limiting cooldown and deduplication.
        4. Calculates target Pan-Tilt-Zoom coordinates.
        5. Executes slew command on driver and emits WebSocket telemetry.
        """
        now = current_time if current_time is not None else time.time()
        cfg = self._configs.get(camera_id) or PTZConfig(camera_id=camera_id, ptz_enabled=True)

        if not cfg.ptz_enabled or not cfg.ptz_auto_cue:
            return None

        # 1. Evaluate threat escalation
        eff_severity = severity.upper()
        if track_id is not None:
            eff_severity = self.evaluate_threat_escalation(
                camera_id=camera_id,
                track_id=track_id,
                base_severity=severity,
                current_time=now
            )

        # 2. Priority Policy Check
        allowed_severities = ["CRITICAL"] if cfg.ptz_min_severity.lower() == "critical" else ["CRITICAL", "HIGH"]
        if eff_severity not in allowed_severities:
            return None

        # 3. Calculate Cue Position
        target_pos = PTZCueCalculator.calculate_cue(
            target_bbox_or_point=target_bbox_or_point,
            frame_width=frame_width,
            frame_height=frame_height,
            config=cfg,
            severity=eff_severity
        )

        # 4. Command Cooldown & Deduplication
        last_t = self._last_command_time.get(camera_id, 0.0)
        cooldown = cfg.ptz_command_cooldown or self.default_cooldown_seconds

        if (now - last_t) < cooldown:
            # Check if this is a redundant command for same track & similar angle
            last_target = self._last_cued_target.get(camera_id)
            if last_target and track_id is not None and last_target[0] == track_id:
                pan_diff = abs(last_target[1] - target_pos.pan)
                tilt_diff = abs(last_target[2] - target_pos.tilt)
                if pan_diff < 5.0 and tilt_diff < 5.0:
                    logger.debug("[%s] Coalescing redundant PTZ cue for Track #%d", camera_id, track_id)
                    return None

        # 5. Dispatch command to driver
        driver = self.get_driver(camera_id)
        if driver is None:
            return None

        cmd_id = f"ptz_{uuid.uuid4().hex[:8]}"
        command = PTZCommand(
            command_id=cmd_id,
            camera_id=camera_id,
            target_pan=target_pos.pan,
            target_tilt=target_pos.tilt,
            target_zoom=target_pos.zoom,
            reason=f"auto_cue:{event_type}:{eff_severity}",
            priority=eff_severity,
            track_id=track_id
        )

        self._last_command_time[camera_id] = now
        if track_id is not None:
            self._last_cued_target[camera_id] = (track_id, target_pos.pan, target_pos.tilt)

        # Emit command dispatched event
        self._emit_telemetry("PTZ_COMMAND", command.to_dict())

        # Telemetry Metrics Hook
        try:
            from ai_engine.telemetry.metrics import metrics_registry
            metrics_registry.ptz_commands.inc(labels={
                "camera_id": camera_id,
                "driver_type": cfg.ptz_driver.value if hasattr(cfg.ptz_driver, "value") else str(cfg.ptz_driver),
                "command_type": "auto_cue"
            })
        except Exception:
            pass

        t_start = time.perf_counter()
        try:
            result = driver.move_to(
                pan=target_pos.pan,
                tilt=target_pos.tilt,
                zoom=target_pos.zoom,
                command_id=cmd_id
            )
            # Record latency
            try:
                from ai_engine.telemetry.metrics import metrics_registry
                metrics_registry.ptz_latency.observe(time.perf_counter() - t_start, labels={"camera_id": camera_id})
            except Exception:
                pass
            # Update camera state target metadata
            status = driver.get_status()
            status.current_target = {
                "track_id": track_id,
                "event_type": event_type,
                "severity": eff_severity,
                "acquired_at": datetime.utcnow().isoformat()
            }

            self._emit_telemetry("PTZ_ACKNOWLEDGED", result.to_dict())

            return result
        except Exception as e:
            logger.error("[%s] PTZ Move failed: %s", camera_id, e)
            self._emit_telemetry("PTZ_ERROR", {"camera_id": camera_id, "command_id": cmd_id, "error": str(e)})
            return PTZCommandResult(
                command_id=cmd_id,
                camera_id=camera_id,
                status=PTZCommandStatus.FAILED,
                position=driver.get_position(),
                error=str(e)
            )

    def manual_move(
        self,
        camera_id: str,
        pan: float,
        tilt: float,
        zoom: float
    ) -> PTZCommandResult:
        """Executes a manual PTZ override command."""
        driver = self.get_driver(camera_id)
        if driver is None:
            return PTZCommandResult(
                command_id=f"ptz_err_{uuid.uuid4().hex[:6]}",
                camera_id=camera_id,
                status=PTZCommandStatus.FAILED,
                position=PTZPosition(),
                error=f"Camera '{camera_id}' PTZ driver not found"
            )

        cmd_id = f"ptz_manual_{uuid.uuid4().hex[:8]}"
        res = driver.move_to(pan=pan, tilt=tilt, zoom=zoom, command_id=cmd_id)
        self._emit_telemetry("PTZ_MANUAL_MOVE", res.to_dict())
        return res

    def emergency_stop(self, camera_id: str) -> bool:
        """Immediately halts PTZ movement on specified camera."""
        driver = self.get_driver(camera_id)
        if driver is not None:
            stopped = driver.stop()
            self._emit_telemetry("PTZ_STOP", {"camera_id": camera_id, "status": "STOPPED"})
            return stopped
        return False

    def get_camera_status(self, camera_id: str) -> Optional[PTZCameraState]:
        """Returns current PTZ telemetry state."""
        driver = self.get_driver(camera_id)
        if driver is not None:
            return driver.get_status()
        return None


# Global singleton instance
ptz_controller = PTZController()
