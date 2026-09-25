from typing import Optional, Dict, Any
import time
from fastapi import APIRouter, HTTPException, Query, Path, Body

from backend.app.schemas.camera import (
    CameraRead,
    CameraCreateRequest,
    CameraSourceUpdateRequest,
    ConnectionTestRequest,
    ConnectionTestResponse,
    CameraStatusUpdateRequest,
    CameraListResponse,
    CameraHealthResponse,
    PTZMoveRequest,
    PTZStatusResponse,
    PTZCommandResponse,
    CameraSource,
    SourceType,
    StreamStatus,
)
from backend.app.services.camera_registry import camera_registry


router = APIRouter()


@router.get(
    "",
    response_model=CameraListResponse,
    summary="List Registered Cameras",
    description="Returns all configured CCTV/RTSP surveillance camera streams."
)
async def list_cameras(
    enabled_only: bool = Query(False, description="Filter only enabled cameras"),
    source_type: Optional[SourceType] = Query(None, description="Filter by source type (rtsp, file, webcam)")
):
    cameras = camera_registry.list(enabled_only=enabled_only, source_type=source_type)
    camera_dtos = [
        CameraRead(
            camera_id=c.camera_id,
            name=c.name,
            source_type=c.source_type,
            source_url=c.source_url,
            enabled=c.enabled,
            status=c.status,
            is_simulated=c.status == StreamStatus.SIMULATED,
            location_metadata=c.location_metadata,
            last_event_at=c.last_event_at,
            created_at=c.created_at,
        )
        for c in cameras
    ]
    return CameraListResponse(total=len(camera_dtos), cameras=camera_dtos)


@router.get(
    "/{camera_id}",
    response_model=CameraRead,
    summary="Get Camera Details",
    description="Retrieves configuration and telemetry status of a specific camera source."
)
async def get_camera(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    camera = camera_registry.get(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    return CameraRead(
        camera_id=camera.camera_id,
        name=camera.name,
        source_type=camera.source_type,
        source_url=camera.source_url,
        enabled=camera.enabled,
        status=camera.status,
        is_simulated=camera.status == StreamStatus.SIMULATED,
        location_metadata=camera.location_metadata,
        last_event_at=camera.last_event_at,
        created_at=camera.created_at,
    )


@router.post(
    "",
    response_model=CameraRead,
    status_code=201,
    summary="Register Camera Source",
    description="Registers a new CCTV/RTSP camera source in the registry."
)
async def register_camera(payload: CameraCreateRequest):
    existing = camera_registry.get(payload.camera_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Camera ID '{payload.camera_id}' already registered.")

    camera = CameraSource(
        camera_id=payload.camera_id,
        name=payload.name,
        source_type=payload.source_type,
        source_url=payload.source_url,
        enabled=payload.enabled,
        status=payload.status,
        location_metadata=payload.location_metadata,
    )
    saved = camera_registry.register(camera)
    return CameraRead(
        camera_id=saved.camera_id,
        name=saved.name,
        source_type=saved.source_type,
        source_url=saved.source_url,
        enabled=saved.enabled,
        status=saved.status,
        is_simulated=saved.status == StreamStatus.SIMULATED,
        location_metadata=saved.location_metadata,
        last_event_at=saved.last_event_at,
        created_at=saved.created_at,
    )


@router.patch(
    "/{camera_id}/source",
    response_model=CameraRead,
    summary="Update Camera Stream Source & Settings",
    description="Configures real RTSP stream or resets to simulated demo stream with location settings."
)
async def update_camera_source(
    camera_id: str = Path(..., description="Unique camera identifier"),
    payload: CameraSourceUpdateRequest = CameraSourceUpdateRequest()
):
    camera = camera_registry.update_source(
        camera_id=camera_id,
        source_type=payload.source_type,
        source_url=payload.source_url,
        username=payload.username,
        password=payload.password,
        enabled=payload.enabled,
        name=payload.name,
        sector=payload.sector,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_simulated=payload.is_simulated,
    )
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    return CameraRead(
        camera_id=camera.camera_id,
        name=camera.name,
        source_type=camera.source_type,
        source_url=camera.source_url,
        enabled=camera.enabled,
        status=camera.status,
        is_simulated=camera.status == StreamStatus.SIMULATED,
        location_metadata=camera.location_metadata,
        last_event_at=camera.last_event_at,
        created_at=camera.created_at,
    )


@router.post(
    "/{camera_id}/test-connection",
    response_model=ConnectionTestResponse,
    summary="Test Camera RTSP Connection",
    description="Probes reachability, latency, resolution, and FPS of an RTSP source."
)
async def test_camera_connection(
    camera_id: str = Path(..., description="Unique camera identifier"),
    payload: ConnectionTestRequest = ConnectionTestRequest(source_url="rtsp://localhost:8554/ibvap-cam01")
):
    from backend.app.services.stream_relay import stream_relay_manager

    res = stream_relay_manager.test_rtsp_connection(
        rtsp_url=payload.source_url,
        username=payload.username,
        password=payload.password,
        timeout_seconds=payload.timeout_seconds
    )
    res["camera_id"] = camera_id
    return ConnectionTestResponse(**res)


@router.post(
    "/{camera_id}/reset-demo",
    response_model=CameraRead,
    summary="Reset Camera to Simulated Demo Stream",
    description="Resets camera configuration and stream relay to default deterministic synthetic demo stream."
)
async def reset_camera_demo(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    camera = camera_registry.reset_demo(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    return CameraRead(
        camera_id=camera.camera_id,
        name=camera.name,
        source_type=camera.source_type,
        source_url=camera.source_url,
        enabled=camera.enabled,
        status=camera.status,
        is_simulated=True,
        location_metadata=camera.location_metadata,
        last_event_at=camera.last_event_at,
        created_at=camera.created_at,
    )


@router.patch(
    "/{camera_id}/status",
    response_model=CameraRead,
    summary="Update Camera Stream Status",
    description="Updates the connection health state of a camera stream."
)
async def update_camera_status(
    camera_id: str = Path(..., description="Unique camera identifier"),
    payload: CameraStatusUpdateRequest = CameraStatusUpdateRequest()
):
    camera = camera_registry.update_status(camera_id, status=payload.status)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    return CameraRead(
        camera_id=camera.camera_id,
        name=camera.name,
        source_type=camera.source_type,
        source_url=camera.source_url,
        enabled=camera.enabled,
        status=camera.status,
        location_metadata=camera.location_metadata,
        last_event_at=camera.last_event_at,
        created_at=camera.created_at,
    )


@router.post(
    "/{camera_id}/enable",
    response_model=CameraRead,
    summary="Enable Camera",
    description="Enables monitoring on a camera stream."
)
async def enable_camera(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    camera = camera_registry.enable(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return CameraRead(
        camera_id=camera.camera_id,
        name=camera.name,
        source_type=camera.source_type,
        source_url=camera.source_url,
        enabled=camera.enabled,
        status=camera.status,
        location_metadata=camera.location_metadata,
        last_event_at=camera.last_event_at,
        created_at=camera.created_at,
    )


@router.post(
    "/{camera_id}/disable",
    response_model=CameraRead,
    summary="Disable Camera",
    description="Disables monitoring on a camera stream."
)
async def disable_camera(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    camera = camera_registry.disable(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return CameraRead(
        camera_id=camera.camera_id,
        name=camera.name,
        source_type=camera.source_type,
        source_url=camera.source_url,
        enabled=camera.enabled,
        status=camera.status,
        location_metadata=camera.location_metadata,
        last_event_at=camera.last_event_at,
        created_at=camera.created_at,
    )


@router.get(
    "/{camera_id}/health",
    response_model=CameraHealthResponse,
    summary="Get Camera Health & Telemetry",
    description="Retrieves live connection health, FPS, frame statistics, and calibration metadata for a specific camera."
)
async def get_camera_health(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    health_data = camera_registry.get_health(camera_id)
    if health_data is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    return CameraHealthResponse(**health_data)


# --- PTZ Endpoints ---

@router.get(
    "/{camera_id}/ptz",
    response_model=PTZStatusResponse,
    summary="Get PTZ Camera Status",
    description="Retrieves the current Pan-Tilt-Zoom position, driver type, and active target state."
)
@router.get(
    "/{camera_id}/ptz/status",
    response_model=PTZStatusResponse,
    summary="Get PTZ Camera Status Alias",
    include_in_schema=False
)
async def get_ptz_status(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    from ai_engine.pipeline.ptz import ptz_controller

    state = ptz_controller.get_camera_status(camera_id)
    if state is None:
        # Fallback to creating/getting default simulator
        driver = ptz_controller.get_driver(camera_id)
        state = driver.get_status()

    return PTZStatusResponse(
        camera_id=state.camera_id,
        connection_state=state.connection_state,
        pan=state.position.pan,
        tilt=state.position.tilt,
        zoom=state.position.zoom,
        driver_type=state.driver_type.value,
        last_command_id=state.last_command_id,
        last_command_timestamp=state.last_command_timestamp,
        last_command_status=state.last_command_status,
        current_target=state.current_target,
        error=state.error
    )


@router.post(
    "/{camera_id}/ptz/move",
    response_model=PTZCommandResponse,
    summary="Move PTZ Camera",
    description="Executes a manual Pan-Tilt-Zoom movement override on the specified camera."
)
async def move_ptz_camera(
    camera_id: str = Path(..., description="Unique camera identifier"),
    payload: PTZMoveRequest = PTZMoveRequest(pan=0.0, tilt=0.0, zoom=1.0)
):
    from ai_engine.pipeline.ptz import ptz_controller

    result = ptz_controller.manual_move(
        camera_id=camera_id,
        pan=payload.pan,
        tilt=payload.tilt,
        zoom=payload.zoom
    )

    return PTZCommandResponse(
        command_id=result.command_id,
        camera_id=result.camera_id,
        status=result.status.value,
        position=result.position.to_dict(),
        error=result.error,
        timestamp=result.timestamp
    )


@router.post(
    "/{camera_id}/ptz/stop",
    summary="Emergency Stop PTZ Camera",
    description="Halts all active movement on the specified PTZ camera."
)
async def stop_ptz_camera(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    from ai_engine.pipeline.ptz import ptz_controller

    stopped = ptz_controller.emergency_stop(camera_id)
    return {"camera_id": camera_id, "status": "STOPPED" if stopped else "FAILED"}


# In-memory telemetry cache for active cameras
_camera_telemetry_cache: Dict[str, Dict[str, Any]] = {}


@router.get(
    "/{camera_id}/hls-url",
    summary="Get Camera Live HLS URL",
    description="Resolves and returns the browser-compatible direct HLS stream URL."
)
async def get_camera_hls_url(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    camera = camera_registry.get(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    from backend.app.services.camera_registry import resolve_live_camera_url
    hls_url = resolve_live_camera_url(camera.source_url)
    return {
        "camera_id": camera_id,
        "hls_url": hls_url,
        "status": camera.status.value if hasattr(camera.status, "value") else str(camera.status)
    }


@router.get(
    "/{camera_id}/hls-proxy/playlist.m3u8",
    summary="Reverse Proxy for Camera HLS Stream (CORS-Free)",
    description="Proxies GITS live HLS streams so any web browser can play them directly."
)
async def get_camera_hls_proxy_playlist(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    import urllib.request
    import urllib.parse
    from fastapi.responses import Response

    camera = camera_registry.get(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")

    from backend.app.services.camera_registry import resolve_live_camera_url
    raw_hls_url = resolve_live_camera_url(camera.source_url)

    try:
        req = urllib.request.Request(raw_hls_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        base_url = raw_hls_url[:raw_hls_url.rfind("/") + 1]
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                full_item_url = urllib.parse.urljoin(base_url, line_str)
                proxied_url = f"/api/v1/cameras/{camera_id}/hls-proxy/sub-playlist.m3u8?target=" + urllib.parse.quote(full_item_url)
                new_lines.append(proxied_url)
            else:
                new_lines.append(line)
        return Response(content="\n".join(new_lines), media_type="application/vnd.apple.mpegurl")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch HLS stream: {e}")


@router.get(
    "/{camera_id}/hls-proxy/sub-playlist.m3u8",
    summary="Proxy Sub-Playlist",
    description="Proxies inner m3u8 playlist and rewrites segment URLs."
)
async def get_camera_hls_proxy_sub_playlist(
    camera_id: str = Path(..., description="Unique camera identifier"),
    target: str = Query(..., description="Full target URL")
):
    import urllib.request
    import urllib.parse
    from fastapi.responses import Response

    try:
        req = urllib.request.Request(target, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        base_url = target[:target.rfind("/") + 1]
        lines = content.splitlines()
        new_lines = []
        for line in lines:
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                full_ts_url = urllib.parse.urljoin(base_url, line_str)
                proxied_ts = f"/api/v1/cameras/{camera_id}/hls-proxy/segment.ts?target=" + urllib.parse.quote(full_ts_url)
                new_lines.append(proxied_ts)
            else:
                new_lines.append(line)
        return Response(content="\n".join(new_lines), media_type="application/vnd.apple.mpegurl")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch sub-playlist: {e}")


@router.get(
    "/{camera_id}/hls-proxy/segment.ts",
    summary="Proxy TS Video Segment",
    description="Streams binary video segment without CORS restrictions."
)
async def get_camera_hls_proxy_segment(
    camera_id: str = Path(..., description="Unique camera identifier"),
    target: str = Query(..., description="Full target TS URL")
):
    import urllib.request
    from fastapi.responses import Response

    try:
        req = urllib.request.Request(target, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = resp.read()
        return Response(content=data, media_type="video/MP2T")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch video segment: {e}")


@router.post(
    "/{camera_id}/telemetry",
    summary="Report Real-time Camera AI Telemetry",
    description="Receives real-time YOLO detections, ByteTrack tracks, and pipeline metrics from AI Engine."
)
async def report_camera_telemetry(
    camera_id: str = Path(..., description="Unique camera identifier"),
    payload: Dict[str, Any] = Body(...)
):
    payload["camera_id"] = camera_id
    payload["server_timestamp"] = time.time()
    _camera_telemetry_cache[camera_id] = payload

    # Broadcast over WebSocket to connected dashboard clients
    try:
        from backend.app.api.v1.endpoints.ws import ws_manager
        await ws_manager.broadcast_event("CAMERA_TELEMETRY", payload)
    except Exception:
        pass

    return {"status": "ok", "camera_id": camera_id}


@router.get(
    "/{camera_id}/telemetry",
    summary="Get Latest Camera AI Telemetry",
    description="Retrieves the most recent YOLO bounding boxes, classes, confidence, and track IDs."
)
async def get_camera_telemetry(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    telemetry = _camera_telemetry_cache.get(camera_id)
    if telemetry is None:
        return {
            "camera_id": camera_id,
            "status": "idle",
            "frame_idx": 0,
            "fps": 0.0,
            "active_tracks": 0,
            "total_unique_tracks": 0,
            "detections": [],
            "target_classes": []
        }
    return telemetry


# ---------------------------------------------------------------------------
# Live AI-Annotated Frame Streaming (Low Latency MJPEG)
# ---------------------------------------------------------------------------
import asyncio
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

_camera_frame_cache: Dict[str, bytes] = {}


@router.post(
    "/{camera_id}/frame",
    summary="Upload Latest Annotated Frame",
    description="Receives latest annotated JPEG frame directly from AI Engine worker."
)
async def upload_camera_frame(
    request: Request,
    camera_id: str = Path(..., description="Unique camera identifier")
):
    frame_bytes = await request.body()
    if frame_bytes:
        _camera_frame_cache[camera_id] = frame_bytes
    return {"status": "ok", "camera_id": camera_id, "size": len(frame_bytes)}


@router.get(
    "/{camera_id}/annotated-frame",
    summary="Get Latest Single Annotated Frame",
    description="Returns latest JPEG image with rendered bounding boxes, labels, and tracking trails."
)
async def get_latest_annotated_frame(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    frame_bytes = _camera_frame_cache.get(camera_id)
    if not frame_bytes:
        frame_bytes = _generate_standby_frame(camera_id)
    return Response(content=frame_bytes, media_type="image/jpeg")


def _generate_standby_frame(camera_id: str) -> bytes:
    import numpy as np
    import cv2
    img = np.zeros((480, 720, 3), dtype=np.uint8)
    img[:] = (15, 23, 42)  # Dark slate
    cv2.rectangle(img, (20, 20), (700, 460), (30, 41, 59), 1)
    cv2.putText(img, f"IBVAP AI LIVE STREAM: {camera_id}", (40, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (56, 189, 248), 2, lineType=cv2.LINE_AA)
    cv2.putText(img, "INITIALIZING YOLO26 + BYTETRACK PIPELINE...", (40, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (148, 163, 184), 1, lineType=cv2.LINE_AA)
    _, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return buf.tobytes()


@router.get(
    "/{camera_id}/annotated-stream",
    summary="Live Multipart MJPEG Stream",
    description="Streams real-time annotated video frames with bounding boxes and trails directly to browser."
)
async def get_camera_annotated_stream(
    camera_id: str = Path(..., description="Unique camera identifier")
):
    async def frame_generator():
        last_frame = None
        try:
            # Yield initial frame immediately
            current = _camera_frame_cache.get(camera_id) or _generate_standby_frame(camera_id)
            last_frame = current
            header = (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(current)).encode("ascii") + b"\r\n\r\n"
            )
            yield header + current + b"\r\n"

            last_yield_time = time.time()

            while True:
                frame_bytes = _camera_frame_cache.get(camera_id)
                now = time.time()
                # Yield if frame is new OR if 0.5s elapsed (keep-alive)
                if frame_bytes and (frame_bytes != last_frame or now - last_yield_time >= 0.5):
                    last_frame = frame_bytes
                    last_yield_time = now
                    header = (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(frame_bytes)).encode("ascii") + b"\r\n\r\n"
                    )
                    yield header + frame_bytes + b"\r\n"
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
