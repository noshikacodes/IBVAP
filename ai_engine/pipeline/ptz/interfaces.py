from abc import ABC, abstractmethod
from typing import Optional

from ai_engine.pipeline.ptz.types import (
    PTZPosition,
    PTZCommand,
    PTZCommandResult,
    PTZCameraState,
    PTZConfig,
)


class BasePTZDriver(ABC):
    """
    Abstract Hardware / Driver interface for PTZ (Pan-Tilt-Zoom) surveillance cameras.
    Decouples higher-level C2 and analytics logic from specific camera hardware protocols.
    """

    def __init__(self, config: PTZConfig):
        self.config = config

    @abstractmethod
    def connect(self) -> bool:
        """Establishes communication with the PTZ controller or hardware interface."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Safely disconnects from the PTZ interface."""
        pass

    @abstractmethod
    def get_position(self) -> PTZPosition:
        """Retrieves the current mechanical/optical position of the camera."""
        pass

    @abstractmethod
    def move_to(
        self,
        pan: float,
        tilt: float,
        zoom: float,
        speed: float = 1.0,
        command_id: Optional[str] = None
    ) -> PTZCommandResult:
        """Executes an absolute slew/pan/tilt/zoom movement."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Immediately halts all active PTZ movement (Emergency Stop)."""
        pass

    @abstractmethod
    def get_status(self) -> PTZCameraState:
        """Returns the current state and telemetry snapshot."""
        pass
