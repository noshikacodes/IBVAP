from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Path, Response
from fastapi.responses import JSONResponse

from backend.app.schemas.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentCreateRequest,
    IncidentUpdateRequest,
    IncidentEvidenceAddRequest,
    IncidentDispatchCreateRequest,
    IncidentListResponse,
    AgencyDispatch,
)
from backend.app.services.incident_service import incident_service
from backend.app.services.dossier_generator import DossierGenerator

router = APIRouter()


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List Tactical Incidents",
    description="Retrieves a paginated list of tactical security incidents with optional severity and status filters."
)
async def list_incidents(
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by incident severity"),
    status: Optional[IncidentStatus] = Query(None, description="Filter by lifecycle status"),
    sector: Optional[str] = Query(None, description="Filter by sector name keyword"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    items, total = incident_service.list_incidents(
        severity=severity,
        status=status,
        sector=sector,
        limit=limit,
        offset=offset
    )
    return IncidentListResponse(total=total, incidents=items)


@router.post(
    "",
    response_model=Incident,
    status_code=201,
    summary="Create Tactical Incident",
    description="Manually registers a new security incident or attaches an initial alert."
)
async def create_incident(payload: IncidentCreateRequest):
    return incident_service.create_incident(payload)


@router.get(
    "/{incident_id}",
    response_model=Incident,
    summary="Get Incident Details",
    description="Retrieves complete incident dossier data, evidence items, and chronological timeline."
)
async def get_incident(
    incident_id: str = Path(..., description="Unique incident identifier")
):
    inc = incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc


@router.patch(
    "/{incident_id}",
    response_model=Incident,
    summary="Update Incident Status or Notes",
    description="Modifies incident severity, status, or investigative summary."
)
async def update_incident(
    incident_id: str = Path(..., description="Unique incident identifier"),
    payload: IncidentUpdateRequest = IncidentUpdateRequest()
):
    inc = incident_service.update_incident(incident_id, payload)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc


@router.post(
    "/{incident_id}/evidence",
    response_model=Incident,
    summary="Attach Evidence Item",
    description="Appends an immutable evidence item (e.g. plate OCR, biometric match, or snapshot) with SHA-256 seal."
)
async def add_incident_evidence(
    incident_id: str = Path(..., description="Unique incident identifier"),
    payload: IncidentEvidenceAddRequest = ...
):
    inc = incident_service.add_evidence(incident_id, payload)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc


@router.get(
    "/{incident_id}/dossier/json",
    summary="Export JSON Incident Dossier",
    description="Exports a verifiable tactical intelligence dossier in canonical JSON format with cryptographic signatures."
)
async def export_json_dossier(
    incident_id: str = Path(..., description="Unique incident identifier")
):
    inc = incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    
    dossier = DossierGenerator.generate_json_dossier(inc)
    return JSONResponse(
        content=dossier,
        headers={"Content-Disposition": f'attachment; filename="dossier_{incident_id}.json"'}
    )


@router.get(
    "/{incident_id}/dossier/pdf",
    summary="Export PDF Incident Dossier",
    description="Generates and downloads a standardized military/border security PDF incident dossier document."
)
async def export_pdf_dossier(
    incident_id: str = Path(..., description="Unique incident identifier")
):
    inc = incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    
    pdf_bytes = DossierGenerator.generate_pdf_dossier(inc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="dossier_{incident_id}.pdf"'}
    )


@router.post(
    "/{incident_id}/dispatch",
    response_model=Incident,
    summary="Execute Multi-Agency Tactical Dispatch",
    description="Dispatches authenticated tactical incident alerts to Quick Reaction Teams (QRT), Border Patrol Command, or Customs."
)
async def dispatch_incident(
    incident_id: str = Path(..., description="Unique incident identifier"),
    payload: IncidentDispatchCreateRequest = ...
):
    inc = incident_service.dispatch_incident(incident_id, payload)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc


@router.get(
    "/{incident_id}/dispatches",
    response_model=List[AgencyDispatch],
    summary="List Incident Dispatches",
    description="Retrieves all multi-agency dispatch records and acknowledgement statuses for an incident."
)
async def list_incident_dispatches(
    incident_id: str = Path(..., description="Unique incident identifier")
):
    inc = incident_service.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return inc.dispatches
