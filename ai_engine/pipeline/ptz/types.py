from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid

from ai_engine.stream_manager.types import mask_credentials


class PTZCommandStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    COOLDOWN = "COOLDOWN"
    IN_PROGRESS = "IN_PROGRESS"


class PTZDriverType(str, Enum):
    SIMULATOR = "simulator"
    ONVIF = "onvif"


@dataclass
class PTZPosition:
    """Represents a 3D spherical position of a PTZ camera."""
    pan: float = 0.0    # Degrees: e.g. -180.0 to +180.0
    tilt: float = 0.0   # Degrees: e.g. -90.0 to +90.0
    zoom: float = 1.0   # Optical magnification factor: e.g. 1.0x to 30.0x

    def clamp(
        self,
        pan_min: float = -180.0,
        pan_max: float = 180.0,
        tilt_min: float = -90.0,
        tilt_max: float = 90.0,
        zoom_min: float = 1.0,
        zoom_max: float = 30.0
    ) -> "PTZPosition":
        """Returns a new PTZPosition clamped within the given physical bounds."""
        clamped_pan = max(pan_min, min(pan_max, self.pan))
        clamped_tilt = max(tilt_min, min(tilt_max, self.tilt))
        clamped_zoom = max(zoom_min, min(zoom_max, self.zoom))
        return PTZPosition(pan=round(clamped_pan, 2), tilt=round(clamped_tilt, 2), zoom=round(clamped_zoom, 2))

    def to_dict(self) -> Dict[str, float]:
        return {
            "pan": round(self.pan, 2),
            "tilt": round(self.tilt, 2),
            "zoom": round(self.zoom, 2),
        }


@dataclass
class PTZCommand:
    """Represents a movement or positioning command sent to a PTZ camera controller."""
    camera_id: str
    target_pan: float
    target_tilt: float
    target_zoom: float = 1.0
    reason: str = "manual_override"
    priority: str = "HIGH"  # CRITICAL, HIGH, MEDIUM, LOW, MANUAL
    track_id: Optional[int] = None
    command_id: str = field(default_factory=lambda: f"ptz_cmd_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "camera_id": self.camera_id,
            "target_pan": round(self.target_pan, 2),
            "target_tilt": round(self.target_tilt, 2),
            "target_zoom": round(self.target_zoom, 2),
            "reason": self.reason,
            "priority": self.priority,
            "track_id": self.track_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PTZCommandResult:
    """Result and acknowledgement returned following PTZ command execution."""
    command_id: str
    camera_id: str
    status: PTZCommandStatus
    position: PTZPosition
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "camera_id": self.camera_id,
            "status": self.status.value,
            "position": self.position.to_dict(),
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PTZCameraState:
    """Live state snapshot and telemetry for a PTZ camera."""
    camera_id: str
    connection_state: str = "CONNECTED"  # CONNECTED, SLEWING, STOPPED, ERROR, DISCONNECTED
    position: PTZPosition = field(default_factory=PTZPosition)
    driver_type: PTZDriverType = PTZDriverType.SIMULATOR
    last_command_id: Optional[str] = None
    last_command_timestamp: Optional[datetime] = None
    last_command_status: Optional[str] = None
    current_target: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "connection_state": self.connection_state,
            "position": self.position.to_dict(),
            "driver_type": self.driver_type.value,
            "last_command_id": self.last_command_id,
            "last_command_timestamp": self.last_command_timestamp.isoformat() if self.last_command_timestamp else None,
            "last_command_status": self.last_command_status,
            "current_target": self.current_target,
            "error": self.error,
        }


@dataclass
class PTZConfig:
    """Configuration parameters for a PTZ-capable surveillance camera."""
    camera_id: str
    ptz_enabled: bool = False
    ptz_driver: str = "simulator"
    ptz_auto_cue: bool = True
    ptz_min_severity: str = "high"  # critical, high, medium
    ptz_command_cooldown: float = 2.0
    ptz_pan_min: float = -180.0
    ptz_pan_max: float = 180.0
    ptz_tilt_min: float = -90.0
    ptz_tilt_max: float = 90.0
    ptz_zoom_min: float = 1.0
    ptz_zoom_max: float = 30.0
    onvif_host: Optional[str] = None
    onvif_port: int = 80
    onvif_username: Optional[str] = None
    onvif_password: Optional[str] = None

    def to_dict(self, mask_secrets: bool = True) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "ptz_enabled": self.ptz_enabled,
            "ptz_driver": self.ptz_driver,
            "ptz_auto_cue": self.ptz_auto_cue,
            "ptz_min_severity": self.ptz_min_severity,
            "ptz_command_cooldown": self.ptz_command_cooldown,
            "ptz_pan_min": self.ptz_pan_min,
            "ptz_pan_max": self.ptz_pan_max,
            "ptz_tilt_min": self.ptz_tilt_min,
            "ptz_tilt_max": self.ptz_tilt_max,
            "ptz_zoom_min": self.ptz_zoom_min,
            "ptz_zoom_max": self.ptz_zoom_max,
            "onvif_host": self.onvif_host,
            "onvif_port": self.onvif_port,
            "onvif_username": "***" if (mask_secrets and self.onvif_username) else self.onvif_username,
        }
