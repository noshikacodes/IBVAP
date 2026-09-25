from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    RTSP = "rtsp"
    FILE = "file"
    WEBCAM = "webcam"


class StreamStatus(str, Enum):
    ONLINE = "online"
    CONNECTING = "connecting"
    OFFLINE = "offline"
    RECONNECTING = "reconnecting"
    SIMULATED = "simulated"


@dataclass
class CameraSource:
    """Core domain model representing a surveillance camera stream source."""
    camera_id: str
    name: str
    source_type: SourceType = SourceType.RTSP
    source_url: str = "rtsp://localhost:8554/ibvap-demo"
    enabled: bool = True
    status: StreamStatus = StreamStatus.SIMULATED
    location_metadata: Dict[str, Any] = field(default_factory=lambda: {
        "sector": "Sector Alpha",
        "resolution": "640x480",
        "fps": 15,
    })
    last_event_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "source_type": self.source_type.value,
            "source_url": self.source_url,
            "enabled": self.enabled,
            "status": self.status.value,
            "location_metadata": self.location_metadata,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CameraSource":
        st = data.get("source_type", SourceType.RTSP.value)
        try:
            source_type = SourceType(st)
        except ValueError:
            source_type = SourceType.RTSP

        stat = data.get("status", StreamStatus.SIMULATED.value)
        try:
            status = StreamStatus(stat)
        except ValueError:
            status = StreamStatus.SIMULATED

        last_event = data.get("last_event_at")
        if isinstance(last_event, str):
            try:
                last_event_parsed = datetime.fromisoformat(last_event)
            except ValueError:
                last_event_parsed = None
        else:
            last_event_parsed = last_event

        return cls(
            camera_id=data.get("camera_id", "CAM_01"),
            name=data.get("name", "Surveillance Camera"),
            source_type=source_type,
            source_url=data.get("source_url", "rtsp://localhost:8554/ibvap-demo"),
            enabled=data.get("enabled", True),
            status=status,
            location_metadata=data.get("location_metadata", {}),
            last_event_at=last_event_parsed,
        )


# --- Pydantic DTOs for REST API ---

class CameraRead(BaseModel):
    camera_id: str
    name: str
    source_type: SourceType
    source_url: str
    enabled: bool
    status: StreamStatus
    is_simulated: bool = True
    location_metadata: Dict[str, Any] = Field(default_factory=dict)
    last_event_at: Optional[datetime] = None
    created_at: datetime


class CameraCreateRequest(BaseModel):
    camera_id: str = Field(..., json_schema_extra={"example": "CAM_05"})
    name: str = Field(..., json_schema_extra={"example": "North Sector Outpost"})
    source_type: SourceType = Field(default=SourceType.RTSP)
    source_url: str = Field(..., json_schema_extra={"example": "rtsp://localhost:8554/cam05"})
    enabled: bool = True
    status: StreamStatus = StreamStatus.CONNECTING
    is_simulated: bool = True
    location_metadata: Dict[str, Any] = Field(default_factory=lambda: {
        "sector": "North Perimeter",
        "resolution": "640x480",
        "fps": 15
    })


class CameraSourceUpdateRequest(BaseModel):
    source_type: Optional[SourceType] = Field(default=SourceType.RTSP)
    source_url: Optional[str] = Field(default=None, json_schema_extra={"example": "rtsp://192.168.1.101:8554/live"})
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    name: Optional[str] = Field(default=None)
    sector: Optional[str] = Field(default=None)
    location_name: Optional[str] = Field(default=None)
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    is_simulated: Optional[bool] = Field(default=None)


class ConnectionTestRequest(BaseModel):
    source_url: str = Field(..., json_schema_extra={"example": "rtsp://192.168.1.101:8554/live"})
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    timeout_seconds: float = Field(default=3.0, ge=0.5, le=10.0)


class ConnectionTestResponse(BaseModel):
    camera_id: Optional[str] = None
    reachable: bool
    status: str
    protocol: str = "RTSP"
    codec: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[float] = None
    latency_ms: Optional[float] = None
    relay_status: Optional[str] = None
    hls_status: Optional[str] = None
    masked_url: Optional[str] = None
    error_reason: Optional[str] = None


class CameraStatusUpdateRequest(BaseModel):
    status: StreamStatus = StreamStatus.ONLINE


class CameraListResponse(BaseModel):
    total: int
    cameras: List[CameraRead]


class CameraHealthResponse(BaseModel):
    camera_id: str
    name: str
    connection_state: StreamStatus
    source_url: str
    resolution: str = "640x480"
    fps: float = 15.0
    reconnect_count: int = 0
    frames_received: int = 0
    last_frame_timestamp: Optional[datetime] = None
    last_error: Optional[str] = None
    calibration_metadata: Dict[str, Any] = Field(default_factory=dict)


class PTZMoveRequest(BaseModel):
    pan: float = Field(..., ge=-180.0, le=180.0, json_schema_extra={"example": 45.0})
    tilt: float = Field(..., ge=-90.0, le=90.0, json_schema_extra={"example": -15.0})
    zoom: float = Field(1.0, ge=1.0, le=30.0, json_schema_extra={"example": 2.5})


class PTZStatusResponse(BaseModel):
    camera_id: str
    connection_state: str
    pan: float
    tilt: float
    zoom: float
    driver_type: str
    last_command_id: Optional[str] = None
    last_command_timestamp: Optional[datetime] = None
    last_command_status: Optional[str] = None
    current_target: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PTZCommandResponse(BaseModel):
    command_id: str
    camera_id: str
    status: str
    position: Dict[str, float]
    error: Optional[str] = None
    timestamp: datetime


