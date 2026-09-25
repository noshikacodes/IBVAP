from datetime import datetime
from typing import Optional
import logging
import uuid

from ai_engine.pipeline.ptz.types import (
    PTZPosition,
    PTZCommand,
    PTZCommandResult,
    PTZCommandStatus,
    PTZCameraState,
    PTZDriverType,
    PTZConfig,
)
from ai_engine.pipeline.ptz.interfaces import BasePTZDriver

logger = logging.getLogger("ibvap.ptz.simulator")


class SimulatedPTZDriver(BasePTZDriver):
    """
    Deterministic Simulated PTZ Camera Driver.
    Simulates real-world pan, tilt, zoom mechanisms, bounds checking,
    command acknowledgement, and telemetry state transitions without hardware dependencies.
    """

    def __init__(self, config: Optional[PTZConfig] = None):
        super().__init__(config or PTZConfig(camera_id="SIM_PTZ_01", ptz_enabled=True))
        self._position = PTZPosition(pan=0.0, tilt=0.0, zoom=1.0)
        self._connected = True
        self._state = PTZCameraState(
            camera_id=self.config.camera_id,
            connection_state="CONNECTED",
            position=self._position,
            driver_type=PTZDriverType.SIMULATOR,
        )
        self._last_command_id: Optional[str] = None

    def connect(self) -> bool:
        self._connected = True
        self._state.connection_state = "CONNECTED"
        self._state.error = None
        logger.info("[%s] Simulated PTZ driver connected.", self.config.camera_id)
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._state.connection_state = "DISCONNECTED"
        logger.info("[%s] Simulated PTZ driver disconnected.", self.config.camera_id)

    def get_position(self) -> PTZPosition:
        return self._position

    def move_to(
        self,
        pan: float,
        tilt: float,
        zoom: float,
        speed: float = 1.0,
        command_id: Optional[str] = None
    ) -> PTZCommandResult:
        cid = command_id or f"ptz_cmd_{uuid.uuid4().hex[:8]}"

        if not self._connected:
            return PTZCommandResult(
                command_id=cid,
                camera_id=self.config.camera_id,
                status=PTZCommandStatus.FAILED,
                position=self._position,
                error="PTZ driver is disconnected",
            )

        # 1. Clamp target coordinates to physical camera limits
        target = PTZPosition(pan=pan, tilt=tilt, zoom=zoom)
        clamped = target.clamp(
            pan_min=self.config.ptz_pan_min,
            pan_max=self.config.ptz_pan_max,
            tilt_min=self.config.ptz_tilt_min,
            tilt_max=self.config.ptz_tilt_max,
            zoom_min=self.config.ptz_zoom_min,
            zoom_max=self.config.ptz_zoom_max,
        )

        # 2. Update mechanical state deterministically
        self._position = clamped
        self._last_command_id = cid

        self._state.position = self._position
        self._state.connection_state = "CONNECTED"
        self._state.last_command_id = cid
        self._state.last_command_timestamp = datetime.utcnow()
        self._state.last_command_status = PTZCommandStatus.SUCCESS.value
        self._state.error = None

        logger.info(
            "[%s] PTZ Move: Pan %.1f°, Tilt %.1f°, Zoom %.1fx (Command: %s)",
            self.config.camera_id,
            self._position.pan,
            self._position.tilt,
            self._position.zoom,
            cid
        )

        return PTZCommandResult(
            command_id=cid,
            camera_id=self.config.camera_id,
            status=PTZCommandStatus.SUCCESS,
            position=self._position,
            error=None,
        )

    def stop(self) -> bool:
        """Halts active movement."""
        self._state.connection_state = "STOPPED"
        self._state.last_command_status = "STOPPED"
        logger.info("[%s] PTZ Emergency Stop triggered.", self.config.camera_id)
        return True

    def get_status(self) -> PTZCameraState:
        return self._state
