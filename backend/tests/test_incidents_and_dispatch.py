import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from backend.app.schemas.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    EvidenceType,
    AgencyType,
    DispatchStatus,
    IncidentCreateRequest,
    IncidentUpdateRequest,
    IncidentEvidenceAddRequest,
    IncidentDispatchCreateRequest,
    calculate_evidence_hash,
)
from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.services.incident_service import IncidentService, InMemoryIncidentRepository, incident_service
from backend.app.services.dossier_generator import DossierGenerator
from backend.app.services.dispatch_service import MultiAgencyDispatchService
from backend.main import app


def test_evidence_hash_determinism():
    data1 = {"track_id": 101, "plate": "DL01AB1234", "confidence": 0.95}
    data2 = {"confidence": 0.95, "plate": "DL01AB1234", "track_id": 101}
    # Different key ordering in dict must produce identical canonical SHA256
    hash1 = calculate_evidence_hash(data1)
    hash2 = calculate_evidence_hash(data2)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_incident_service_create_and_lifecycle():
    repo = InMemoryIncidentRepository()
    service = IncidentService(repository=repo)

    req = IncidentCreateRequest(
        title="Test Virtual Fence Breach",
        severity=IncidentSeverity.CRITICAL,
        sector="Bravo Sector",
        primary_camera_id="CAM_FENCE",
        track_ids=[55],
        description="Suspicious intruder breach detected at fence line",
    )

    inc = service.create_incident(req)
    assert inc.incident_id.startswith("INC-2026-")
    assert inc.severity == IncidentSeverity.CRITICAL
    assert inc.status == IncidentStatus.OPEN
    assert len(inc.timeline) == 1
    assert inc.dossier_hash is not None

    # Add evidence
    ev_req = IncidentEvidenceAddRequest(
        evidence_type=EvidenceType.ZONE_BREACH,
        camera_id="CAM_FENCE",
        data={"breach_type": "tripwire_crossing", "x": 100, "y": 200},
    )
    inc_with_ev = service.add_evidence(inc.incident_id, ev_req)
    assert len(inc_with_ev.evidence_items) == 1
    assert inc_with_ev.evidence_items[0].sha256_hash is not None
    assert len(inc_with_ev.timeline) == 2

    # Update incident status
    upd_req = IncidentUpdateRequest(
        status=IncidentStatus.IN_INVESTIGATION,
        summary="Security team deployed to verify target."
    )
    inc_upd = service.update_incident(inc.incident_id, upd_req)
    assert inc_upd.status == IncidentStatus.IN_INVESTIGATION
    assert inc_upd.summary == "Security team deployed to verify target."


def test_create_incident_from_alert():
    repo = InMemoryIncidentRepository()
    service = IncidentService(repository=repo)

    alert = Alert(
        alert_id="alt_test_001",
        event_id="evt_001",
        event_type="intrusion",
        severity="critical",
        camera_id="CAM_PATROL",
        track_id=77,
        object_class="person",
        position=(150.0, 220.0),
        message="PERSON #77 breached patrol perimeter",
        metadata={"sector": "Sector Alpha Corridor"},
        status=AlertStatus.NEW
    )

    inc = service.create_from_alert(alert)
    assert inc.incident_id.startswith("INC-2026-")
    assert inc.severity == IncidentSeverity.CRITICAL
    assert inc.primary_camera_id == "CAM_PATROL"
    assert inc.track_ids == [77]
    assert len(inc.evidence_items) == 1
    assert inc.evidence_items[0].evidence_type == EvidenceType.ALERT
    assert len(inc.timeline) == 1


def test_json_dossier_generation():
    repo = InMemoryIncidentRepository()
    service = IncidentService(repository=repo)

    req = IncidentCreateRequest(
        title="Dossier Test Incident",
        severity=IncidentSeverity.HIGH,
        sector="Sector Alpha",
        primary_camera_id="CAM_GATE",
        description="Vehicle inspection breach test",
    )
    inc = service.create_incident(req)

    dossier = DossierGenerator.generate_json_dossier(inc)
    assert "dossier_header" in dossier
    assert dossier["dossier_header"]["system"].startswith("IBVAP")
    assert "RESTRICTED" in dossier["dossier_header"]["classification"]
    assert "chronological_timeline" in dossier
    assert "evidence_ledger" in dossier
    assert "digital_signature_block" in dossier
    assert dossier["digital_signature_block"]["tamper_evident"] is True


def test_pdf_dossier_generation():
    repo = InMemoryIncidentRepository()
    service = IncidentService(repository=repo)

    req = IncidentCreateRequest(
        title="PDF Dossier Test Incident",
        severity=IncidentSeverity.CRITICAL,
        sector="Sector Bravo East",
        primary_camera_id="CAM_FENCE",
        description="High security perimeter breach document generation test",
    )
    inc = service.create_incident(req)

    pdf_bytes = DossierGenerator.generate_pdf_dossier(inc)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_bytes


def test_multi_agency_dispatch_service_sandbox():
    disp_svc = MultiAgencyDispatchService(sandbox_mode=True)

    repo = InMemoryIncidentRepository()
    service = IncidentService(repository=repo)

    req = IncidentCreateRequest(
        title="Tactical QRT Interception Incident",
        severity=IncidentSeverity.CRITICAL,
        sector="Delta Sector Hilltop",
        primary_camera_id="CAM_OUTPOST_04",
        description="High priority armed threat detected",
    )
    inc = service.create_incident(req)

    results = disp_svc.dispatch_incident(
        incident=inc,
        agencies=[
            AgencyType.QUICK_REACTION_TEAM_QRT,
            AgencyType.BORDER_PATROL_COMMAND,
        ],
        notes="Code RED - Intercept immediately"
    )

    assert len(results) == 2
    assert results[0].agency == AgencyType.QUICK_REACTION_TEAM_QRT
    assert results[0].status == DispatchStatus.DELIVERED
    assert results[0].ack_reference.startswith("ACK-QUI-")
    assert results[0].response_payload["status"] == "MOBILIZED"

    assert results[1].agency == AgencyType.BORDER_PATROL_COMMAND
    assert results[1].status == DispatchStatus.DELIVERED
    assert results[1].ack_reference.startswith("ACK-BOR-")


def test_incident_rest_apis():
    client = TestClient(app)

    # 1. List incidents
    res = client.get("/api/v1/incidents")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "incidents" in data
    assert data["total"] >= 2  # Seed incidents present

    # 2. Create new incident via API
    create_res = client.post(
        "/api/v1/incidents",
        json={
            "title": "API Test Perimeter Breach",
            "severity": "critical",
            "sector": "Sector Alpha Gate",
            "primary_camera_id": "CAM_01",
            "description": "Automated security alert escalation test",
        }
    )
    assert create_res.status_code == 201
    new_inc = create_res.json()
    inc_id = new_inc["incident_id"]

    # 3. Get incident details
    get_res = client.get(f"/api/v1/incidents/{inc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "API Test Perimeter Breach"

    # 4. Attach evidence via API
    ev_res = client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        json={
            "evidence_type": "anpr_plate",
            "camera_id": "CAM_01",
            "data": {"plate": "UP16AB9999", "confidence": 0.92},
        }
    )
    assert ev_res.status_code == 200
    assert len(ev_res.json()["evidence_items"]) == 1

    # 5. Export JSON Dossier
    json_res = client.get(f"/api/v1/incidents/{inc_id}/dossier/json")
    assert json_res.status_code == 200
    assert "dossier_header" in json_res.json()

    # 6. Export PDF Dossier
    pdf_res = client.get(f"/api/v1/incidents/{inc_id}/dossier/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-1.4")

    # 7. Execute Multi-Agency Dispatch via API
    disp_res = client.post(
        f"/api/v1/incidents/{inc_id}/dispatch",
        json={
            "agencies": ["quick_reaction_team_qrt", "customs_intelligence"],
            "notes": "Urgent deployment order"
        }
    )
    assert disp_res.status_code == 200
    updated_inc = disp_res.json()
    assert updated_inc["status"] == "dispatched"
    assert len(updated_inc["dispatches"]) == 2

    # 8. List dispatches endpoint
    dispatches_res = client.get(f"/api/v1/incidents/{inc_id}/dispatches")
    assert dispatches_res.status_code == 200
    assert len(dispatches_res.json()) == 2
