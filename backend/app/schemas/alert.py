from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List
import uuid
from pydantic import BaseModel, Field


class AlertStatus(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """Core domain model representing a prioritized, deduplicated security alert."""
    alert_id: str = field(default_factory=lambda: f"alt_{uuid.uuid4().hex[:12]}")
    event_id: str = ""
    event_type: str = "intrusion"
    severity: str = "critical"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    camera_id: str = "CAM_01"
    track_id: int = 0
    object_class: str = "person"
    zone_id: Optional[str] = None
    tripwire_id: Optional[str] = None
    position: Tuple[float, float] = (0.0, 0.0)
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: AlertStatus = AlertStatus.NEW
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes alert to a JSON-serializable dictionary."""
        return {
            "alert_id": self.alert_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "object_class": self.object_class,
            "zone_id": self.zone_id,
            "tripwire_id": self.tripwire_id,
            "position": list(self.position),
            "message": self.message,
            "metadata": self.metadata,
            "status": self.status.value,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """Reconstructs Alert domain model from a dictionary."""
        ts = data.get("timestamp")
        if isinstance(ts, str):
            try:
                parsed_ts = datetime.fromisoformat(ts)
            except ValueError:
                parsed_ts = datetime.utcnow()
        elif isinstance(ts, datetime):
            parsed_ts = ts
        else:
            parsed_ts = datetime.utcnow()

        ack_at = data.get("acknowledged_at")
        if isinstance(ack_at, str):
            try:
                ack_at_parsed = datetime.fromisoformat(ack_at)
            except ValueError:
                ack_at_parsed = None
        else:
            ack_at_parsed = ack_at

        res_at = data.get("resolved_at")
        if isinstance(res_at, str):
            try:
                res_at_parsed = datetime.fromisoformat(res_at)
            except ValueError:
                res_at_parsed = None
        else:
            res_at_parsed = res_at

        pos = data.get("position", (0.0, 0.0))
        if isinstance(pos, list) and len(pos) >= 2:
            pos = (float(pos[0]), float(pos[1]))
        elif not isinstance(pos, tuple):
            pos = (0.0, 0.0)

        status_val = data.get("status", AlertStatus.NEW.value)
        try:
            status = AlertStatus(status_val)
        except ValueError:
            status = AlertStatus.NEW

        return cls(
            alert_id=data.get("alert_id", f"alt_{uuid.uuid4().hex[:12]}"),
            event_id=data.get("event_id", ""),
            event_type=data.get("event_type", "intrusion"),
            severity=data.get("severity", "critical"),
            timestamp=parsed_ts,
            camera_id=data.get("camera_id", "CAM_01"),
            track_id=int(data.get("track_id", 0)),
            object_class=data.get("object_class", "person"),
            zone_id=data.get("zone_id"),
            tripwire_id=data.get("tripwire_id"),
            position=pos,
            message=data.get("message", ""),
            metadata=data.get("metadata", {}),
            status=status,
            acknowledged_at=ack_at_parsed,
            acknowledged_by=data.get("acknowledged_by"),
            resolved_at=res_at_parsed,
            resolved_by=data.get("resolved_by"),
        )


# --- Pydantic DTOs for REST API ---

class AlertCreateRequest(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    event_type: str = "intrusion"
    severity: str = "critical"
    timestamp: Optional[datetime] = None
    camera_id: str = "CAM_01"
    track_id: int = 0
    object_class: str = "person"
    zone_id: Optional[str] = None
    tripwire_id: Optional[str] = None
    position: Tuple[float, float] = (0.0, 0.0)
    message: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AlertRead(BaseModel):
    alert_id: str
    event_id: str
    event_type: str
    severity: str
    timestamp: datetime
    camera_id: str
    track_id: int
    object_class: str
    zone_id: Optional[str] = None
    tripwire_id: Optional[str] = None
    position: Tuple[float, float]
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: AlertStatus
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None


class AlertAcknowledgeRequest(BaseModel):
    operator_id: str = "operator_01"


class AlertResolveRequest(BaseModel):
    operator_id: str = "operator_01"
    resolution_notes: Optional[str] = None


class AlertListResponse(BaseModel):
    total: int
    alerts: List[AlertRead]
