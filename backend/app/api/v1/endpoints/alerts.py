from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Path

from backend.app.schemas.alert import (
    Alert,
    AlertRead,
    AlertCreateRequest,
    AlertListResponse,
    AlertAcknowledgeRequest,
    AlertResolveRequest,
    AlertStatus,
)
from backend.app.services.alert_repository import alert_repository
from backend.app.services.camera_registry import camera_registry
from backend.app.api.v1.endpoints.ws import ws_manager


router = APIRouter()


@router.get(
    "",
    response_model=AlertListResponse,
    summary="List Security Alerts",
    description="Returns a paginated list of security alerts with optional filters."
)
async def list_alerts(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium, low)"),
    status: Optional[AlertStatus] = Query(None, description="Filter by alert status (new, acknowledged, resolved)"),
    limit: int = Query(50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    alerts = alert_repository.list(
        camera_id=camera_id,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset
    )
    total = alert_repository.count(status=status, camera_id=camera_id)
    
    # Map domain models to Pydantic DTOs
    alert_dtos = [
        AlertRead(
            alert_id=a.alert_id,
            event_id=a.event_id,
            event_type=a.event_type,
            severity=a.severity,
            timestamp=a.timestamp,
            camera_id=a.camera_id,
            track_id=a.track_id,
            object_class=a.object_class,
            zone_id=a.zone_id,
            tripwire_id=a.tripwire_id,
            position=a.position,
            message=a.message,
            metadata=a.metadata,
            status=a.status,
            acknowledged_at=a.acknowledged_at,
            acknowledged_by=a.acknowledged_by,
            resolved_at=a.resolved_at,
            resolved_by=a.resolved_by
        )
        for a in alerts
    ]
    
    return AlertListResponse(total=total, alerts=alert_dtos)


@router.delete(
    "",
    summary="Clear All Alerts",
    description="Deletes all security alerts from the active repository (useful for test resets)."
)
async def clear_alerts():
    alert_repository.clear()
    return {"message": "Alerts repository cleared", "total": 0}


@router.post(
    "",
    response_model=AlertRead,
    status_code=201,
    summary="Create Security Alert",
    description="Ingests a new security alert into the platform and broadcasts it to connected C2 dashboards."
)
async def create_alert(payload: AlertCreateRequest):
    alert = Alert(
        event_id=payload.event_id,
        event_type=payload.event_type,
        severity=payload.severity,
        timestamp=payload.timestamp or datetime.utcnow(),
        camera_id=payload.camera_id,
        track_id=payload.track_id,
        object_class=payload.object_class,
        zone_id=payload.zone_id,
        tripwire_id=payload.tripwire_id,
        position=payload.position,
        message=payload.message,
        metadata=payload.metadata,
        status=AlertStatus.NEW,
    )
    saved = alert_repository.create(alert)

    # Update camera registry timestamp
    cam = camera_registry.get(payload.camera_id)
    if cam:
        cam.last_event_at = saved.timestamp

    # Broadcast to live WebSocket clients
    await ws_manager.broadcast_alert(saved.to_dict())

    return AlertRead(
        alert_id=saved.alert_id,
        event_id=saved.event_id,
        event_type=saved.event_type,
        severity=saved.severity,
        timestamp=saved.timestamp,
        camera_id=saved.camera_id,
        track_id=saved.track_id,
        object_class=saved.object_class,
        zone_id=saved.zone_id,
        tripwire_id=saved.tripwire_id,
        position=saved.position,
        message=saved.message,
        metadata=saved.metadata,
        status=saved.status,
        acknowledged_at=saved.acknowledged_at,
        acknowledged_by=saved.acknowledged_by,
        resolved_at=saved.resolved_at,
        resolved_by=saved.resolved_by
    )


@router.get(
    "/{alert_id}",
    response_model=AlertRead,
    summary="Get Alert by ID",
    description="Retrieves full details for a single security alert."
)
async def get_alert(
    alert_id: str = Path(..., description="Unique alert identifier")
):
    alert = alert_repository.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    
    return AlertRead(
        alert_id=alert.alert_id,
        event_id=alert.event_id,
        event_type=alert.event_type,
        severity=alert.severity,
        timestamp=alert.timestamp,
        camera_id=alert.camera_id,
        track_id=alert.track_id,
        object_class=alert.object_class,
        zone_id=alert.zone_id,
        tripwire_id=alert.tripwire_id,
        position=alert.position,
        message=alert.message,
        metadata=alert.metadata,
        status=alert.status,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by
    )


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertRead,
    summary="Acknowledge Alert",
    description="Marks an alert as acknowledged by a human operator."
)
async def acknowledge_alert(
    alert_id: str = Path(..., description="Unique alert identifier"),
    payload: AlertAcknowledgeRequest = AlertAcknowledgeRequest()
):
    alert = alert_repository.acknowledge(alert_id, operator_id=payload.operator_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    
    return AlertRead(
        alert_id=alert.alert_id,
        event_id=alert.event_id,
        event_type=alert.event_type,
        severity=alert.severity,
        timestamp=alert.timestamp,
        camera_id=alert.camera_id,
        track_id=alert.track_id,
        object_class=alert.object_class,
        zone_id=alert.zone_id,
        tripwire_id=alert.tripwire_id,
        position=alert.position,
        message=alert.message,
        metadata=alert.metadata,
        status=alert.status,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by
    )


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Resolve Alert",
    description="Marks an alert as resolved with optional resolution notes."
)
async def resolve_alert(
    alert_id: str = Path(..., description="Unique alert identifier"),
    payload: AlertResolveRequest = AlertResolveRequest()
):
    alert = alert_repository.resolve(
        alert_id,
        operator_id=payload.operator_id,
        notes=payload.resolution_notes
    )
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    
    return AlertRead(
        alert_id=alert.alert_id,
        event_id=alert.event_id,
        event_type=alert.event_type,
        severity=alert.severity,
        timestamp=alert.timestamp,
        camera_id=alert.camera_id,
        track_id=alert.track_id,
        object_class=alert.object_class,
        zone_id=alert.zone_id,
        tripwire_id=alert.tripwire_id,
        position=alert.position,
        message=alert.message,
        metadata=alert.metadata,
        status=alert.status,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by
    )
