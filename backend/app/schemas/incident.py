from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import hashlib
import json
from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    OPEN = "open"
    IN_INVESTIGATION = "in_investigation"
    DISPATCHED = "dispatched"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EvidenceType(str, Enum):
    ALERT = "alert"
    SNAPSHOT = "snapshot"
    ANPR_PLATE = "anpr_plate"
    FRS_BIOMETRIC = "frs_biometric"
    PTZ_TELEMETRY = "ptz_telemetry"
    ZONE_BREACH = "zone_breach"
    MANUAL_NOTE = "manual_note"


class AgencyType(str, Enum):
    BORDER_PATROL_COMMAND = "border_patrol_command"
    QUICK_REACTION_TEAM_QRT = "quick_reaction_team_qrt"
    CUSTOMS_INTELLIGENCE = "customs_intelligence"
    LOCAL_LAW_ENFORCEMENT = "local_law_enforcement"


class DispatchStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    RETRYING = "retrying"
    FAILED = "failed"


def calculate_evidence_hash(data: Dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hash over canonical JSON data."""
    try:
        canonical_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    except Exception:
        return hashlib.sha256(str(data).encode("utf-8")).hexdigest()


class IncidentEvidence(BaseModel):
    evidence_id: str
    evidence_type: EvidenceType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    camera_id: str
    sha256_hash: str
    data: Dict[str, Any] = Field(default_factory=dict)
    uri: Optional[str] = None


class IncidentTimelineEntry(BaseModel):
    entry_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str  # e.g., "AI_SPATIAL_RULES", "ANPR_ENGINE", "FRS_ENGINE", "PTZ_CONTROLLER", "OPERATOR"
    severity: IncidentSeverity = IncidentSeverity.HIGH
    event_type: str
    description: str
    camera_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class AgencyDispatch(BaseModel):
    dispatch_id: str
    agency: AgencyType
    agency_name: str
    endpoint_url: str  # Always masked in client output
    status: DispatchStatus = DispatchStatus.PENDING
    dispatched_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    attempts: int = 1
    last_error: Optional[str] = None
    ack_reference: Optional[str] = None
    response_payload: Optional[Dict[str, Any]] = None


class Incident(BaseModel):
    incident_id: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sector: str = "Sector Alpha"
    primary_camera_id: str = "CAM_01"
    track_ids: List[int] = Field(default_factory=list)
    description: str = ""
    summary: str = ""
    evidence_items: List[IncidentEvidence] = Field(default_factory=list)
    timeline: List[IncidentTimelineEntry] = Field(default_factory=list)
    dispatches: List[AgencyDispatch] = Field(default_factory=list)
    dossier_hash: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    severity: IncidentSeverity = IncidentSeverity.HIGH
    sector: str = "Sector Alpha"
    primary_camera_id: str = "CAM_01"
    track_ids: List[int] = Field(default_factory=list)
    description: str = ""
    alert_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentUpdateRequest(BaseModel):
    title: Optional[str] = None
    severity: Optional[IncidentSeverity] = None
    status: Optional[IncidentStatus] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IncidentEvidenceAddRequest(BaseModel):
    evidence_type: EvidenceType
    camera_id: str
    data: Dict[str, Any]
    uri: Optional[str] = None


class IncidentDispatchCreateRequest(BaseModel):
    agencies: List[AgencyType] = Field(..., min_length=1)
    priority_override: Optional[IncidentSeverity] = None
    notes: Optional[str] = None


class IncidentListResponse(BaseModel):
    total: number if False else int
    incidents: List[Incident]
