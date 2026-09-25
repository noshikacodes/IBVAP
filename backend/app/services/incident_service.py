import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import uuid

from backend.app.schemas.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    EvidenceType,
    IncidentEvidence,
    IncidentTimelineEntry,
    IncidentCreateRequest,
    IncidentUpdateRequest,
    IncidentEvidenceAddRequest,
    IncidentDispatchCreateRequest,
    calculate_evidence_hash,
)
from backend.app.schemas.alert import Alert
from backend.app.services.dispatch_service import dispatch_service
from backend.app.services.dossier_generator import DossierGenerator

logger = logging.getLogger("ibvap.incident")


class BaseIncidentRepository:
    def create(self, incident: Incident) -> Incident:
        raise NotImplementedError

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        raise NotImplementedError

    def update(self, incident: Incident) -> Incident:
        raise NotImplementedError

    def list(
        self,
        severity: Optional[IncidentSeverity] = None,
        status: Optional[IncidentStatus] = None,
        sector: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Incident], int]:
        raise NotImplementedError


class InMemoryIncidentRepository(BaseIncidentRepository):
    """Thread-safe In-Memory Incident Store with seed intelligence data."""

    def __init__(self):
        self._lock = threading.Lock()
        self._incidents: Dict[str, Incident] = {}
        self._seed_demo_incidents()

    def _seed_demo_incidents(self):
        now = datetime.utcnow()

        # Seed Incident 1: Perimeter Intrusion Breach (CRITICAL)
        inc1_id = "INC-2026-0041"
        ev1_data = {
            "track_id": 104,
            "zone_id": "ZONE_NORTH_PERIMETER",
            "detection_confidence": 0.88,
            "coordinates": [320.0, 180.0],
            "rule_violation": "virtual_fence_intrusion",
        }
        ev1 = IncidentEvidence(
            evidence_id="ev_8a91b2c3",
            evidence_type=EvidenceType.ZONE_BREACH,
            timestamp=now - timedelta(minutes=15),
            camera_id="CAM_FENCE",
            sha256_hash=calculate_evidence_hash(ev1_data),
            data=ev1_data,
        )

        timeline1 = [
            IncidentTimelineEntry(
                entry_id="tl_001",
                timestamp=now - timedelta(minutes=15),
                source="AI_SPATIAL_RULES",
                severity=IncidentSeverity.CRITICAL,
                event_type="virtual_fence_breach",
                description="PERSON #104 breached restricted East Virtual Fence",
                camera_id="CAM_FENCE",
                details={"zone": "ZONE_NORTH_PERIMETER"},
            ),
            IncidentTimelineEntry(
                entry_id="tl_002",
                timestamp=now - timedelta(minutes=14),
                source="PTZ_CONTROLLER",
                severity=IncidentSeverity.HIGH,
                event_type="ptz_slew_to_cue",
                description="PTZ Slew-to-Cue engaged on Track #104 (Pan: 45.0°, Tilt: -12.0°, Zoom: 4.0x)",
                camera_id="CAM_FENCE",
                details={"pan": 45.0, "tilt": -12.0, "zoom": 4.0},
            )
        ]

        inc1 = Incident(
            incident_id=inc1_id,
            title="Perimeter Fence Intrusion & PTZ Optical Lock",
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.OPEN,
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=14),
            sector="Bravo East Virtual Fence",
            primary_camera_id="CAM_FENCE",
            track_ids=[104],
            description="Autonomous spatial rules detected unauthorized person breach across East Exclusion Boundary. PTZ camera locked onto suspect.",
            summary="Intruder breached northern sector virtual line; automated PTZ slew acquired visual contact.",
            evidence_items=[ev1],
            timeline=timeline1,
        )
        inc1.dossier_hash = DossierGenerator.generate_json_dossier(inc1)["dossier_header"]["integrity_checksum_sha256"]
        self._incidents[inc1_id] = inc1

        # Seed Incident 2: Watchlist Vehicle Breach (HIGH)
        inc2_id = "INC-2026-0038"
        ev2_data = {
            "track_id": 82,
            "plate_number": "DL01AB1234",
            "watchlist_category": "STOLEN_VEHICLE_ALERT",
            "ocr_confidence": 0.94,
        }
        ev2 = IncidentEvidence(
            evidence_id="ev_4d72e9a1",
            evidence_type=EvidenceType.ANPR_PLATE,
            timestamp=now - timedelta(hours=2),
            camera_id="CAM_GATE",
            sha256_hash=calculate_evidence_hash(ev2_data),
            data=ev2_data,
        )

        timeline2 = [
            IncidentTimelineEntry(
                entry_id="tl_003",
                timestamp=now - timedelta(hours=2),
                source="ANPR_ENGINE",
                severity=IncidentSeverity.HIGH,
                event_type="anpr_watchlist_hit",
                description="Flagged vehicle plate DL01AB1234 identified at Gate A1",
                camera_id="CAM_GATE",
                details=ev2_data,
            )
        ]

        inc2 = Incident(
            incident_id=inc2_id,
            title="Watchlist Vehicle Detected at Gate A1",
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.DISPATCHED,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=1, minutes=50),
            sector="North Perimeter Gate A1",
            primary_camera_id="CAM_GATE",
            track_ids=[82],
            description="ANPR engine identified vehicle on security watchlist approaching checkpoint.",
            summary="Hotlist vehicle plate flagged; Border Patrol Command dispatched.",
            evidence_items=[ev2],
            timeline=timeline2,
        )
        inc2.dossier_hash = DossierGenerator.generate_json_dossier(inc2)["dossier_header"]["integrity_checksum_sha256"]
        self._incidents[inc2_id] = inc2

    def create(self, incident: Incident) -> Incident:
        with self._lock:
            self._incidents[incident.incident_id] = incident
        return incident

    def get_by_id(self, incident_id: str) -> Optional[Incident]:
        with self._lock:
            return self._incidents.get(incident_id)

    def update(self, incident: Incident) -> Incident:
        with self._lock:
            incident.updated_at = datetime.utcnow()
            self._incidents[incident.incident_id] = incident
        return incident

    def list(
        self,
        severity: Optional[IncidentSeverity] = None,
        status: Optional[IncidentStatus] = None,
        sector: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Incident], int]:
        with self._lock:
            items = list(self._incidents.values())

        if severity:
            items = [i for i in items if i.severity == severity]
        if status:
            items = [i for i in items if i.status == status]
        if sector:
            items = [i for i in items if sector.lower() in i.sector.lower()]

        items.sort(key=lambda x: x.created_at, reverse=True)
        total = len(items)
        paginated = items[offset : offset + limit]
        return paginated, total


class IncidentService:
    """Business logic coordinator for tactical incident lifecycle and evidence."""

    def __init__(self, repository: Optional[BaseIncidentRepository] = None):
        self.repository = repository or InMemoryIncidentRepository()

    def create_incident(self, request: IncidentCreateRequest) -> Incident:
        inc_id = f"INC-2026-{uuid.uuid4().hex[:4].upper()}"
        now = datetime.utcnow()

        timeline_entries = [
            IncidentTimelineEntry(
                entry_id=f"tl_{uuid.uuid4().hex[:6]}",
                timestamp=now,
                source="OPERATOR",
                severity=request.severity,
                event_type="incident_declared",
                description=f"Incident opened: {request.title}",
                camera_id=request.primary_camera_id,
                details={"initial_notes": request.description},
            )
        ]

        incident = Incident(
            incident_id=inc_id,
            title=request.title,
            severity=request.severity,
            status=IncidentStatus.OPEN,
            created_at=now,
            updated_at=now,
            sector=request.sector,
            primary_camera_id=request.primary_camera_id,
            track_ids=request.track_ids,
            description=request.description,
            summary=request.description,
            evidence_items=[],
            timeline=timeline_entries,
            dispatches=[],
            metadata=request.metadata,
        )

        dossier = DossierGenerator.generate_json_dossier(incident)
        incident.dossier_hash = dossier["dossier_header"]["integrity_checksum_sha256"]

        created_inc = self.repository.create(incident)
        try:
            from ai_engine.telemetry.metrics import metrics_registry
            metrics_registry.incidents_created.inc(labels={"severity": incident.severity.value})
        except Exception:
            pass
        return created_inc


    def create_from_alert(self, alert: Alert) -> Incident:
        """Instantiates an incident directly from a high-priority alert."""
        inc_id = f"INC-2026-{uuid.uuid4().hex[:4].upper()}"
        now = datetime.utcnow()

        sev_map = {
            "critical": IncidentSeverity.CRITICAL,
            "high": IncidentSeverity.HIGH,
            "medium": IncidentSeverity.MEDIUM,
            "low": IncidentSeverity.LOW,
        }
        sev_str = alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity).lower()
        severity = sev_map.get(sev_str, IncidentSeverity.HIGH)

        ev_data = {
            "alert_id": alert.alert_id,
            "event_type": alert.event_type,
            "track_id": alert.track_id,
            "position": alert.position,
            "message": alert.message,
            "metadata": alert.metadata,
        }

        ev = IncidentEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            evidence_type=EvidenceType.ALERT,
            timestamp=alert.timestamp or now,
            camera_id=alert.camera_id,
            sha256_hash=calculate_evidence_hash(ev_data),
            data=ev_data,
        )

        timeline_entries = [
            IncidentTimelineEntry(
                entry_id=f"tl_{uuid.uuid4().hex[:6]}",
                timestamp=alert.timestamp or now,
                source="AI_ALERT_ENGINE",
                severity=severity,
                event_type=alert.event_type,
                description=alert.message,
                camera_id=alert.camera_id,
                details=alert.metadata,
            )
        ]

        incident = Incident(
            incident_id=inc_id,
            title=f"{alert.event_type.upper().replace('_', ' ')} on {alert.camera_id}",
            severity=severity,
            status=IncidentStatus.OPEN,
            created_at=now,
            updated_at=now,
            sector=alert.metadata.get("sector", "Sector Alpha"),
            primary_camera_id=alert.camera_id,
            track_ids=[alert.track_id] if alert.track_id else [],
            description=alert.message,
            summary=f"Automated incident generated from Alert {alert.alert_id}",
            evidence_items=[ev],
            timeline=timeline_entries,
            dispatches=[],
            metadata={"source_alert_id": alert.alert_id},
        )

        dossier = DossierGenerator.generate_json_dossier(incident)
        incident.dossier_hash = dossier["dossier_header"]["integrity_checksum_sha256"]

        created_inc = self.repository.create(incident)
        try:
            from ai_engine.telemetry.metrics import metrics_registry
            metrics_registry.incidents_created.inc(labels={"severity": incident.severity.value})
        except Exception:
            pass
        return created_inc

    def add_evidence(self, incident_id: str, request: IncidentEvidenceAddRequest) -> Optional[Incident]:
        incident = self.repository.get_by_id(incident_id)
        if not incident:
            return None

        ev_id = f"ev_{uuid.uuid4().hex[:8]}"
        ev = IncidentEvidence(
            evidence_id=ev_id,
            evidence_type=request.evidence_type,
            timestamp=datetime.utcnow(),
            camera_id=request.camera_id,
            sha256_hash=calculate_evidence_hash(request.data),
            data=request.data,
            uri=request.uri,
        )

        incident.evidence_items.append(ev)

        # Append timeline entry for new evidence
        incident.timeline.append(
            IncidentTimelineEntry(
                entry_id=f"tl_{uuid.uuid4().hex[:6]}",
                timestamp=datetime.utcnow(),
                source="EVIDENCE_LEDGER",
                severity=incident.severity,
                event_type=f"evidence_added:{request.evidence_type.value}",
                description=f"Evidence {ev_id} attached ({request.evidence_type.value})",
                camera_id=request.camera_id,
                details={"evidence_id": ev_id, "sha256": ev.sha256_hash},
            )
        )

        dossier = DossierGenerator.generate_json_dossier(incident)
        incident.dossier_hash = dossier["dossier_header"]["integrity_checksum_sha256"]

        return self.repository.update(incident)

    def update_incident(self, incident_id: str, request: IncidentUpdateRequest) -> Optional[Incident]:
        incident = self.repository.get_by_id(incident_id)
        if not incident:
            return None

        if request.title is not None:
            incident.title = request.title
        if request.severity is not None:
            incident.severity = request.severity
        if request.status is not None:
            incident.status = request.status
            incident.timeline.append(
                IncidentTimelineEntry(
                    entry_id=f"tl_{uuid.uuid4().hex[:6]}",
                    timestamp=datetime.utcnow(),
                    source="OPERATOR",
                    severity=incident.severity,
                    event_type="status_changed",
                    description=f"Incident status updated to {request.status.value.upper()}",
                    camera_id=incident.primary_camera_id,
                )
            )
        if request.description is not None:
            incident.description = request.description
        if request.summary is not None:
            incident.summary = request.summary
        if request.metadata is not None:
            incident.metadata.update(request.metadata)

        dossier = DossierGenerator.generate_json_dossier(incident)
        incident.dossier_hash = dossier["dossier_header"]["integrity_checksum_sha256"]

        return self.repository.update(incident)

    def dispatch_incident(
        self,
        incident_id: str,
        request: IncidentDispatchCreateRequest
    ) -> Optional[Incident]:
        incident = self.repository.get_by_id(incident_id)
        if not incident:
            return None

        # Execute dispatch through MultiAgencyDispatchService
        dispatches = dispatch_service.dispatch_incident(
            incident=incident,
            agencies=request.agencies,
            notes=request.notes
        )

        incident.dispatches.extend(dispatches)
        incident.status = IncidentStatus.DISPATCHED

        for d in dispatches:
            try:
                from ai_engine.telemetry.metrics import metrics_registry
                metrics_registry.incident_dispatches.inc(labels={
                    "agency": d.agency.value if hasattr(d.agency, "value") else str(d.agency),
                    "status": d.status.value if hasattr(d.status, "value") else str(d.status)
                })
            except Exception:
                pass
            incident.timeline.append(
                IncidentTimelineEntry(
                    entry_id=f"tl_{uuid.uuid4().hex[:6]}",
                    timestamp=datetime.utcnow(),
                    source="DISPATCH_ENGINE",
                    severity=incident.severity,
                    event_type="agency_dispatched",
                    description=f"Tactical dispatch sent to {d.agency_name} (Status: {d.status.value.upper()})",
                    camera_id=incident.primary_camera_id,
                    details={"dispatch_id": d.dispatch_id, "ack_ref": d.ack_reference},
                )
            )

        dossier = DossierGenerator.generate_json_dossier(incident)
        incident.dossier_hash = dossier["dossier_header"]["integrity_checksum_sha256"]

        return self.repository.update(incident)


    def get_incident(self, incident_id: str) -> Optional[Incident]:
        return self.repository.get_by_id(incident_id)

    def list_incidents(
        self,
        severity: Optional[IncidentSeverity] = None,
        status: Optional[IncidentStatus] = None,
        sector: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Incident], int]:
        return self.repository.list(
            severity=severity,
            status=status,
            sector=sector,
            limit=limit,
            offset=offset
        )


# Global singleton instance
incident_service = IncidentService()
