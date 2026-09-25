import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Path, Body

from backend.app.services.traffic_repository import traffic_repository
from backend.app.api.v1.endpoints.cameras import _camera_telemetry_cache
from backend.app.core.logging import logger


router = APIRouter()


@router.post(
    "/{camera_id}/traffic-events",
    summary="Record Traffic Line-Crossing Event",
    description="Persists a unique vehicle or person crossing event into the database and broadcasts to WebSocket subscribers."
)
async def record_traffic_event(
    camera_id: str = Path(..., description="Unique camera identifier"),
    payload: Dict[str, Any] = Body(...)
):
    payload["camera_id"] = camera_id
    is_new = traffic_repository.record_event(payload)

    # Broadcast over WebSocket to connected dashboard clients if new event
    if is_new:
        try:
            from backend.app.api.v1.endpoints.ws import ws_manager
            await ws_manager.broadcast_event("TRAFFIC_EVENT", payload)
        except Exception as e:
            logger.debug("Failed to broadcast traffic event: %s", e)

    return {
        "status": "recorded" if is_new else "duplicate_ignored",
        "camera_id": camera_id,
        "track_id": payload.get("track_id"),
        "object_type": payload.get("object_type"),
        "direction": payload.get("direction")
    }


@router.get(
    "/{camera_id}/traffic-analytics",
    summary="Get Traffic Analytics Summary",
    description="Retrieves live tracked counts, today's totals, last hour, and last 10-minute traffic metrics."
)
async def get_traffic_analytics(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    # 1. Historical & today's persistent totals from SQLite
    analytics = traffic_repository.get_analytics_summary(camera_id)

    # 2. Real-time LIVE NOW counts from active camera telemetry cache
    telemetry = _camera_telemetry_cache.get(camera_id, {})
    traffic_snap = telemetry.get("traffic", {})

    live_now = traffic_snap.get("live_now", {
        "car": 0, "bus": 0, "truck": 0, "motorcycle": 0, "person": 0
    })

    # If traffic_snap has in-memory counted totals, blend with SQLite
    if "counted_totals" in traffic_snap:
        for k, v in traffic_snap["counted_totals"].items():
            if v > analytics["today_totals"].get(k, 0):
                analytics["today_totals"][k] = v
        analytics["total_today"] = sum(analytics["today_totals"].values())
        analytics["total_vehicles_today"] = (
            analytics["today_totals"].get("car", 0) +
            analytics["today_totals"].get("bus", 0) +
            analytics["today_totals"].get("truck", 0) +
            analytics["today_totals"].get("motorcycle", 0)
        )
        analytics["total_persons_today"] = analytics["today_totals"].get("person", 0)

    default_line = [[120.0, 360.0], [600.0, 360.0]] if "1809" in camera_id else [[80.0, 360.0], [650.0, 360.0]]

    return {
        **analytics,
        "live_now": live_now,
        "live_total": sum(live_now.values()),
        "counting_line": traffic_snap.get("counting_line", default_line),
        "fps": telemetry.get("fps", 0.0),
        "frame_idx": telemetry.get("frame_idx", 0),
        "active_tracks": telemetry.get("active_tracks", 0),
        "status": telemetry.get("status", "online")
    }


@router.get(
    "/{camera_id}/traffic-events",
    summary="List Recent Traffic Crossing Events",
    description="Retrieves ordered historical vehicle crossing event log for the camera."
)
async def list_traffic_events(
    camera_id: str = Path(..., description="Unique camera identifier"),
    limit: int = Query(50, ge=1, le=200, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    events = traffic_repository.get_recent_events(camera_id=camera_id, limit=limit, offset=offset)
    return {
        "camera_id": camera_id,
        "total": len(events),
        "events": events
    }


@router.get(
    "/{camera_id}/traffic-summary",
    summary="Get Aggregated Traffic Volume Time Series",
    description="Retrieves chronological time-series buckets for traffic volume charting."
)
async def get_traffic_time_series(
    camera_id: str = Path(..., description="Unique camera identifier"),
    limit: int = Query(12, ge=1, le=60, description="Number of time intervals to return")
):
    buckets = traffic_repository.get_time_series_summary(camera_id=camera_id, limit=limit)
    return {
        "camera_id": camera_id,
        "intervals": buckets,
        "total_intervals": len(buckets)
    }
