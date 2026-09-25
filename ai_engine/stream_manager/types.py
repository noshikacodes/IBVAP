import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from urllib.parse import urlsplit, urlunsplit


class StreamState(str, Enum):
    """Lifecycle state machine for supervised camera video streams."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"
    STOPPING = "STOPPING"


def mask_credentials(url: str) -> str:
    """
    Safely redacts embedded plaintext usernames and passwords in URLs.
    Example: 'rtsp://admin:pass123@192.168.1.50:8554/live' -> 'rtsp://***:***@192.168.1.50:8554/live'
    Non-URL filepaths or clean URLs are returned unmodified.
    """
    if not url or not isinstance(url, str):
        return ""

    if not (url.startswith("rtsp://") or url.startswith("rtsps://") or 
            url.startswith("http://") or url.startswith("https://") or 
            url.startswith("rtmp://")):
        return url

    try:
        parsed = urlsplit(url)
        if parsed.username or parsed.password:
            hostname = parsed.hostname or ""
            port_str = f":{parsed.port}" if parsed.port else ""
            masked_netloc = f"***:***@{hostname}{port_str}"
            return urlunsplit((parsed.scheme, masked_netloc, parsed.path, parsed.query, parsed.fragment))
    except Exception:
        # Regex fallback in case of unparseable custom RTSP format
        return re.sub(r"://([^:]+):([^@]+)@", r"://***:***@", url)

    return url


@dataclass
class StreamConfig:
    """Configuration for an individual video stream processed by a dedicated worker."""
    camera_id: str
    input_url: str
    name: str = ""
    location: str = "Sector Alpha"
    enabled: bool = True
    fps: int = 15
    resolution: str = "640x480"
    transport: str = "tcp"
    min_object_size: int = 16
    roi: Optional[List[int]] = None
    night_mode: bool = False
    stall_timeout_seconds: float = 10.0

    # ANPR Configuration (Phase 5B)
    enable_anpr: bool = False
    anpr_model: str = "yolov8n_plate.pt"
    anpr_ocr: str = "easyocr"
    anpr_confidence: float = 0.40
    anpr_stride: int = 3
    anpr_votes: int = 3

    # FRS Configuration (Phase 5C)
    enable_frs: bool = False
    frs_detector: str = "yolov8n_face.pt"
    frs_recognizer: str = "mobilefacenet_arcface.onnx"
    frs_confidence: float = 0.50
    frs_threshold: float = 0.65
    frs_stride: int = 3
    frs_votes: int = 3
    frs_min_size: int = 32
    frs_gallery: Optional[str] = None

    # PTZ Slew-to-Cue Configuration (Phase 6.2)
    ptz_enabled: bool = False
    ptz_driver: str = "simulator"
    ptz_auto_cue: bool = True
    ptz_min_severity: str = "high"
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

    # Spatial Rules & Detection
    spatial_rules_path: Optional[str] = None
    model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.40
    output_path: Optional[str] = None
    reconnect_delay: float = 2.0
    max_retries: int = 5
    skip_frames: int = 0
    extra_args: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.name:
            self.name = f"Camera {self.camera_id}"
        self.validate()

    def validate(self) -> None:
        """Validates configuration parameters."""
        if not self.camera_id or not str(self.camera_id).strip():
            raise ValueError("camera_id cannot be empty")
        if not self.input_url or not str(self.input_url).strip():
            raise ValueError("input_url cannot be empty")
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(f"confidence_threshold must be between 0.0 and 1.0, got {self.confidence_threshold}")
        if not (0.0 <= self.anpr_confidence <= 1.0):
            raise ValueError(f"anpr_confidence must be between 0.0 and 1.0, got {self.anpr_confidence}")
        if not (0.0 <= self.frs_confidence <= 1.0):
            raise ValueError(f"frs_confidence must be between 0.0 and 1.0, got {self.frs_confidence}")
        if not (0.0 <= self.frs_threshold <= 1.0):
            raise ValueError(f"frs_threshold must be between 0.0 and 1.0, got {self.frs_threshold}")
        if self.anpr_stride < 1:
            raise ValueError(f"anpr_stride must be >= 1, got {self.anpr_stride}")
        if self.anpr_votes < 1:
            raise ValueError(f"anpr_votes must be >= 1, got {self.anpr_votes}")
        if self.frs_stride < 1:
            raise ValueError(f"frs_stride must be >= 1, got {self.frs_stride}")
        if self.frs_votes < 1:
            raise ValueError(f"frs_votes must be >= 1, got {self.frs_votes}")
        if self.frs_min_size < 10:
            raise ValueError(f"frs_min_size must be >= 10, got {self.frs_min_size}")
        if self.transport.lower() not in ("tcp", "udp"):
            raise ValueError(f"transport must be 'tcp' or 'udp', got {self.transport}")
        if self.fps < 1 or self.fps > 120:
            raise ValueError(f"fps must be between 1 and 120, got {self.fps}")
        if self.min_object_size < 1:
            raise ValueError(f"min_object_size must be >= 1, got {self.min_object_size}")
        if self.ptz_pan_min >= self.ptz_pan_max:
            raise ValueError(f"ptz_pan_min ({self.ptz_pan_min}) must be less than ptz_pan_max ({self.ptz_pan_max})")
        if self.ptz_tilt_min >= self.ptz_tilt_max:
            raise ValueError(f"ptz_tilt_min ({self.ptz_tilt_min}) must be less than ptz_tilt_max ({self.ptz_tilt_max})")
        if self.ptz_zoom_min < 1.0 or self.ptz_zoom_min >= self.ptz_zoom_max:
            raise ValueError(f"ptz_zoom_min must be >= 1.0 and < ptz_zoom_max ({self.ptz_zoom_max})")

    @property
    def masked_input_url(self) -> str:
        """Returns input_url with sensitive credentials redacted."""
        return mask_credentials(self.input_url)

    def to_dict(self, mask_secret: bool = True) -> Dict[str, Any]:
        """Serializes configuration to dictionary."""
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "location": self.location,
            "input_url": self.masked_input_url if mask_secret else self.input_url,
            "enabled": self.enabled,
            "fps": self.fps,
            "resolution": self.resolution,
            "transport": self.transport,
            "min_object_size": self.min_object_size,
            "roi": self.roi,
            "night_mode": self.night_mode,
            "stall_timeout_seconds": self.stall_timeout_seconds,
            "enable_anpr": self.enable_anpr,
            "anpr_model": self.anpr_model,
            "anpr_ocr": self.anpr_ocr,
            "anpr_confidence": self.anpr_confidence,
            "anpr_stride": self.anpr_stride,
            "anpr_votes": self.anpr_votes,
            "enable_frs": self.enable_frs,
            "frs_detector": self.frs_detector,
            "frs_recognizer": self.frs_recognizer,
            "frs_confidence": self.frs_confidence,
            "frs_threshold": self.frs_threshold,
            "frs_stride": self.frs_stride,
            "frs_votes": self.frs_votes,
            "frs_min_size": self.frs_min_size,
            "frs_gallery": self.frs_gallery,
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
            "onvif_username": "***" if (mask_secret and self.onvif_username) else self.onvif_username,
            "spatial_rules_path": self.spatial_rules_path,
            "model_name": self.model_name,
            "confidence_threshold": self.confidence_threshold,
            "output_path": self.output_path,
            "reconnect_delay": self.reconnect_delay,
            "max_retries": self.max_retries,
            "skip_frames": self.skip_frames,
            "extra_args": list(self.extra_args),
        }


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StreamConfig":
        """Constructs a StreamConfig from dictionary data with alias support."""
        # Support rtsp_url alias for input_url
        raw_url = data.get("input_url") or data.get("rtsp_url") or ""
        reconnect_attempts = data.get("reconnect_attempts") or data.get("max_retries") or 5
        reconnect_delay = data.get("reconnect_delay") or 2.0

        return cls(
            camera_id=str(data.get("camera_id", "")).strip(),
            input_url=str(raw_url).strip(),
            name=str(data.get("name", "")).strip(),
            location=str(data.get("location", "Sector Alpha")),
            enabled=bool(data.get("enabled", True)),
            fps=int(data.get("fps", 15)),
            resolution=str(data.get("resolution", "640x480")),
            transport=str(data.get("transport", "tcp")).lower(),
            min_object_size=int(data.get("min_object_size", 16)),
            roi=data.get("roi"),
            night_mode=bool(data.get("night_mode", False)),
            stall_timeout_seconds=float(data.get("stall_timeout_seconds", 10.0)),
            enable_anpr=bool(data.get("enable_anpr", False)),
            anpr_model=str(data.get("anpr_model", "yolov8n_plate.pt")),
            anpr_ocr=str(data.get("anpr_ocr", "easyocr")),
            anpr_confidence=float(data.get("anpr_confidence", 0.40)),
            anpr_stride=int(data.get("anpr_stride", 3)),
            anpr_votes=int(data.get("anpr_votes", 3)),
            enable_frs=bool(data.get("enable_frs", False)),
            frs_detector=str(data.get("frs_detector", "yolov8n_face.pt")),
            frs_recognizer=str(data.get("frs_recognizer", "mobilefacenet_arcface.onnx")),
            frs_confidence=float(data.get("frs_confidence", 0.50)),
            frs_threshold=float(data.get("frs_threshold", 0.65)),
            frs_stride=int(data.get("frs_stride", 3)),
            frs_votes=int(data.get("frs_votes", 3)),
            frs_min_size=int(data.get("frs_min_size", 32)),
            frs_gallery=data.get("frs_gallery"),
            ptz_enabled=bool(data.get("ptz_enabled", False)),
            ptz_driver=str(data.get("ptz_driver", "simulator")),
            ptz_auto_cue=bool(data.get("ptz_auto_cue", True)),
            ptz_min_severity=str(data.get("ptz_min_severity", "high")),
            ptz_command_cooldown=float(data.get("ptz_command_cooldown", 2.0)),
            ptz_pan_min=float(data.get("ptz_pan_min", -180.0)),
            ptz_pan_max=float(data.get("ptz_pan_max", 180.0)),
            ptz_tilt_min=float(data.get("ptz_tilt_min", -90.0)),
            ptz_tilt_max=float(data.get("ptz_tilt_max", 90.0)),
            ptz_zoom_min=float(data.get("ptz_zoom_min", 1.0)),
            ptz_zoom_max=float(data.get("ptz_zoom_max", 30.0)),
            onvif_host=data.get("onvif_host"),
            onvif_port=int(data.get("onvif_port", 80)),
            onvif_username=data.get("onvif_username"),
            onvif_password=data.get("onvif_password"),
            spatial_rules_path=data.get("spatial_rules_path"),
            model_name=str(data.get("model_name", "yolov8n.pt")),
            confidence_threshold=float(data.get("confidence_threshold", 0.40)),
            output_path=data.get("output_path"),
            reconnect_delay=float(reconnect_delay),
            max_retries=int(reconnect_attempts),
            skip_frames=int(data.get("skip_frames", 0)),
            extra_args=list(data.get("extra_args", [])),
        )


@dataclass
class StreamStatusInfo:
    """Runtime health and telemetry snapshot for an active or managed video stream."""
    camera_id: str
    state: StreamState
    input_url: str  # Always masked
    name: str = ""
    location: str = "Sector Alpha"
    connection_state: str = "ONLINE"  # ONLINE, CONNECTING, DEGRADED, OFFLINE
    process_id: Optional[int] = None
    start_time: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    last_frame_timestamp: Optional[str] = None
    restart_count: int = 0
    reconnect_count: int = 0
    frames_received: int = 0
    fps_estimate: float = 15.0
    resolution: str = "640x480"
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
    enable_anpr: bool = False
    enable_frs: bool = False
    enabled: bool = True
    calibration_metadata: Dict[str, Any] = field(default_factory=dict)
    ptz_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "location": self.location,
            "connection_state": self.connection_state,
            "state": self.state.value,
            "input_url": self.input_url,
            "process_id": self.process_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_state_change": self.last_state_change.isoformat() if self.last_state_change else None,
            "last_frame_timestamp": self.last_frame_timestamp,
            "restart_count": self.restart_count,
            "reconnect_count": self.reconnect_count,
            "frames_received": self.frames_received,
            "fps_estimate": self.fps_estimate,
            "resolution": self.resolution,
            "last_error": self.last_error,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "enable_anpr": self.enable_anpr,
            "enable_frs": self.enable_frs,
            "enabled": self.enabled,
            "calibration_metadata": self.calibration_metadata,
            "ptz_metadata": self.ptz_metadata,
        }
