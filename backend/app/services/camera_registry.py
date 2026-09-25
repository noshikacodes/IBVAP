import copy
import time
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Tuple
from collections import OrderedDict
import threading
from datetime import datetime

from backend.app.schemas.camera import CameraSource, SourceType, StreamStatus

try:
    from ai_engine.pipeline.gits_resolver import is_gits_source, resolve_gits_hls_url
except ImportError:
    is_gits_source = lambda s: False
    resolve_gits_hls_url = None

logger = logging.getLogger("ibvap.backend.camera_registry")

_gits_hls_cache: Dict[str, Tuple[str, float]] = {}


def resolve_live_camera_url(source_url: str) -> str:
    """Resolves active public HLS stream URL if source is GITS camera."""
    if not source_url or not is_gits_source(source_url) or not resolve_gits_hls_url:
        return source_url

    now = time.time()
    if source_url in _gits_hls_cache:
        cached_url, expiry = _gits_hls_cache[source_url]
        if now < expiry:
            return cached_url

    try:
        resolved, meta = resolve_gits_hls_url(source_url)
        # Cache for 60 minutes (tokens are valid for 120 mins)
        _gits_hls_cache[source_url] = (resolved, now + 3600)
        return resolved
    except Exception as e:
        logger.warning("Failed to resolve GITS camera URL for '%s': %s", source_url, e)
        return source_url


class BaseCameraRegistry(ABC):
    """Abstract interface for managing registered camera video sources."""

    @abstractmethod
    def register(self, camera: CameraSource) -> CameraSource:
        """Registers or updates a camera source."""
        pass

    @abstractmethod
    def get(self, camera_id: str) -> Optional[CameraSource]:
        """Retrieves a camera source by identifier."""
        pass

    @abstractmethod
    def list(
        self,
        enabled_only: bool = False,
        source_type: Optional[SourceType] = None
    ) -> List[CameraSource]:
        """Lists registered camera sources."""
        pass

    @abstractmethod
    def update_source(
        self,
        camera_id: str,
        source_type: Optional[SourceType] = None,
        source_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        enabled: Optional[bool] = None,
        name: Optional[str] = None,
        sector: Optional[str] = None,
        location_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        is_simulated: Optional[bool] = None,
    ) -> Optional[CameraSource]:
        """Updates camera stream source, location metadata, and switches relay mode."""
        pass

    @abstractmethod
    def reset_demo(self, camera_id: str) -> Optional[CameraSource]:
        """Resets camera stream to default local synthetic demo feed."""
        pass

    @abstractmethod
    def update_status(self, camera_id: str, status: StreamStatus) -> Optional[CameraSource]:
        """Updates connection or stream status of a camera."""
        pass

    @abstractmethod
    def enable(self, camera_id: str) -> Optional[CameraSource]:
        """Enables camera monitoring."""
        pass

    @abstractmethod
    def disable(self, camera_id: str) -> Optional[CameraSource]:
        """Disables camera monitoring."""
        pass

    @abstractmethod
    def delete(self, camera_id: str) -> bool:
        """Removes a camera from the registry."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears all registered cameras."""
        pass


class InMemoryCameraRegistry(BaseCameraRegistry):
    """
    Thread-safe in-memory camera registry.
    Can be replaced seamlessly with a database-backed repository in future phases.
    """

    def __init__(self, initialize_defaults: bool = True):
        self._cameras: OrderedDict[str, CameraSource] = OrderedDict()
        self._lock = threading.Lock()

        if initialize_defaults:
            self._seed_default_cameras()

    def _seed_default_cameras(self) -> None:
        defaults = [
            CameraSource(
                camera_id="CAM_01",
                name="Sector Alpha - North Perimeter Gate",
                source_type=SourceType.RTSP,
                source_url="rtsp://localhost:8554/ibvap-cam01",
                enabled=True,
                status=StreamStatus.SIMULATED,
                location_metadata={
                    "sector": "North Border Sector A",
                    "resolution": "640x480",
                    "fps": 15,
                    "pipeline": "YOLOv8 + ByteTrack + Spatial Geofences",
                }
            ),
            CameraSource(
                camera_id="CAM_02",
                name="Sector Alpha - South Vehicle Corridor",
                source_type=SourceType.RTSP,
                source_url="rtsp://localhost:8554/ibvap-cam02",
                enabled=True,
                status=StreamStatus.SIMULATED,
                location_metadata={
                    "sector": "South Transport Corridor",
                    "resolution": "640x480",
                    "fps": 15,
                    "pipeline": "YOLOv8 + ByteTrack + Spatial Geofences",
                }
            ),
            CameraSource(
                camera_id="CAM_03",
                name="Sector Bravo - East Virtual Fence",
                source_type=SourceType.RTSP,
                source_url="rtsp://localhost:8554/ibvap-cam03",
                enabled=True,
                status=StreamStatus.SIMULATED,
                location_metadata={
                    "sector": "Bravo East Exclusion Zone",
                    "resolution": "640x480",
                    "fps": 15,
                    "pipeline": "YOLOv8 + ByteTrack + Spatial Geofences",
                }
            ),
            CameraSource(
                camera_id="CAM_04",
                name="Sector Bravo - West Outpost",
                source_type=SourceType.RTSP,
                source_url="rtsp://localhost:8554/ibvap-cam04",
                enabled=True,
                status=StreamStatus.SIMULATED,
                location_metadata={
                    "sector": "Bravo West Boundary",
                    "resolution": "640x480",
                    "fps": 15,
                    "pipeline": "YOLOv8 + ByteTrack + Spatial Geofences",
                }
            ),
            CameraSource(
                camera_id="CAM_SEJONG_95366",
                name="[세종]운학터널(세종)-13|13",
                source_type=SourceType.RTSP,
                source_url="https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=95366",
                enabled=True,
                status=StreamStatus.ONLINE,
                location_metadata={
                    "sector": "Sejong / Wunhak Tunnel",
                    "location_name": "Sejong-Pocheon Expressway Wunhak Tunnel",
                    "resolution": "720x480",
                    "fps": 30,
                    "protocol": "HLS",
                    "cctv_id": "95366",
                    "pipeline": "YOLO26s + ByteTrack + Live Highway Analytics",
                }
            ),
            CameraSource(
                camera_id="CAM_GITS_1809",
                name="우체국4R(상행)",
                source_type=SourceType.RTSP,
                source_url="https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId=1809",
                enabled=True,
                status=StreamStatus.ONLINE,
                location_metadata={
                    "sector": "Gwacheon / Post Office Intersection",
                    "location_name": "Gwacheon Post Office 4-way Intersection",
                    "resolution": "720x480",
                    "fps": 30,
                    "protocol": "HLS",
                    "cctv_id": "1809",
                    "pipeline": "YOLO26s + ByteTrack + Live Urban Intersection Analytics",
                }
            ),
        ]
        for cam in defaults:
            self._cameras[cam.camera_id] = cam

    def _seed_defaults(self) -> None:
        self._seed_default_cameras()

    def register(self, camera: CameraSource) -> CameraSource:
        with self._lock:
            self._cameras[camera.camera_id] = camera
            return camera

    def get(self, camera_id: str) -> Optional[CameraSource]:
        with self._lock:
            cam = self._cameras.get(camera_id)
            if cam is None:
                return None
            active_url = resolve_live_camera_url(cam.source_url)
            if active_url != cam.source_url:
                c = copy.copy(cam)
                c.source_url = active_url
                return c
            return cam

    def list(
        self,
        enabled_only: bool = False,
        source_type: Optional[SourceType] = None
    ) -> List[CameraSource]:
        with self._lock:
            result = []
            for cam in self._cameras.values():
                if enabled_only and not cam.enabled:
                    continue
                if source_type and cam.source_type != source_type:
                    continue
                active_url = resolve_live_camera_url(cam.source_url)
                if active_url != cam.source_url:
                    c = copy.copy(cam)
                    c.source_url = active_url
                    result.append(c)
                else:
                    result.append(cam)
            return result

    def update_source(
        self,
        camera_id: str,
        source_type: Optional[SourceType] = None,
        source_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        enabled: Optional[bool] = None,
        name: Optional[str] = None,
        sector: Optional[str] = None,
        location_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        is_simulated: Optional[bool] = None,
    ) -> Optional[CameraSource]:
        with self._lock:
            cam = self._cameras.get(camera_id)
            if cam is None:
                return None

            if name is not None:
                cam.name = name
            if source_type is not None:
                cam.source_type = source_type
            if enabled is not None:
                cam.enabled = enabled

            # Update location metadata
            if cam.location_metadata is None:
                cam.location_metadata = {}
            if sector is not None:
                cam.location_metadata["sector"] = sector
            if location_name is not None:
                cam.location_metadata["location_name"] = location_name
            if latitude is not None:
                cam.location_metadata["latitude"] = latitude
            if longitude is not None:
                cam.location_metadata["longitude"] = longitude

            # Handle source URL & relay switching
            from backend.app.services.stream_relay import stream_relay_manager, mask_rtsp_url, normalize_slot_id, SLOT_CONFIGS

            norm_slot = normalize_slot_id(camera_id) or "CAM_01"
            slot_cfg = SLOT_CONFIGS.get(norm_slot, {"path": f"ibvap-{norm_slot.lower().replace('_', '')}"})
            default_demo_url = f"rtsp://localhost:8554/{slot_cfg['path']}"

            if is_simulated is False and source_url:
                cam.source_url = mask_rtsp_url(source_url)
                cam.status = StreamStatus.ONLINE
                # Start real camera relay to local MediaMTX slot
                stream_relay_manager.start_real_camera_relay(
                    camera_id=camera_id,
                    rtsp_url=source_url,
                    username=username,
                    password=password
                )
            elif is_simulated is True:
                cam.source_url = default_demo_url
                cam.status = StreamStatus.SIMULATED
                stream_relay_manager.start_demo_relay(camera_id)
            elif source_url:
                cam.source_url = mask_rtsp_url(source_url)

            return cam

    def reset_demo(self, camera_id: str) -> Optional[CameraSource]:
        from backend.app.services.stream_relay import normalize_slot_id, SLOT_CONFIGS
        norm_slot = normalize_slot_id(camera_id) or "CAM_01"
        slot_cfg = SLOT_CONFIGS.get(norm_slot, {"path": f"ibvap-{norm_slot.lower().replace('_', '')}"})
        default_demo_url = f"rtsp://localhost:8554/{slot_cfg['path']}"

        return self.update_source(
            camera_id=camera_id,
            source_type=SourceType.RTSP,
            source_url=default_demo_url,
            is_simulated=True,
            enabled=True
        )

    def update_status(self, camera_id: str, status: StreamStatus) -> Optional[CameraSource]:
        with self._lock:
            cam = self._cameras.get(camera_id)
            if cam is None:
                return None
            cam.status = status
            try:
                from ai_engine.telemetry.metrics import metrics_registry
                st_val = status.value if hasattr(status, "value") else str(status)
                metrics_registry.camera_connection_state.set(1.0, labels={"camera_id": camera_id, "state": st_val})
            except Exception:
                pass
            return cam

    def enable(self, camera_id: str) -> Optional[CameraSource]:
        with self._lock:
            cam = self._cameras.get(camera_id)
            if cam is None:
                return None
            cam.enabled = True
            return cam

    def disable(self, camera_id: str) -> Optional[CameraSource]:
        with self._lock:
            cam = self._cameras.get(camera_id)
            if cam is None:
                return None
            cam.enabled = False
            cam.status = StreamStatus.OFFLINE
            return cam

    def delete(self, camera_id: str) -> bool:
        with self._lock:
            if camera_id in self._cameras:
                del self._cameras[camera_id]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cameras.clear()

    def get_health(self, camera_id: str) -> Optional[Dict]:
        with self._lock:
            cam = self._cameras.get(camera_id)
            if cam is None:
                return None

            meta = cam.location_metadata or {}
            fps_val = float(meta.get("fps", 15.0))
            reconn_val = int(meta.get("reconnect_count", 0))
            frames_val = int(meta.get("frames_received", 0))

            try:
                from ai_engine.telemetry.metrics import metrics_registry
                metrics_registry.camera_fps.set(fps_val, labels={"camera_id": camera_id})
                st_val = cam.status.value if hasattr(cam.status, "value") else str(cam.status)
                metrics_registry.camera_connection_state.set(1.0, labels={"camera_id": camera_id, "state": st_val})
            except Exception:
                pass

            return {
                "camera_id": cam.camera_id,
                "name": cam.name,
                "connection_state": cam.status,
                "source_url": cam.source_url,
                "resolution": meta.get("resolution", "640x480"),
                "fps": fps_val,
                "reconnect_count": reconn_val,
                "frames_received": frames_val,
                "last_frame_timestamp": cam.last_event_at,
                "last_error": meta.get("last_error"),
                "calibration_metadata": {
                    "sector": meta.get("sector", "Sector Alpha"),
                    "night_mode": meta.get("night_mode", False),
                    "min_object_size": meta.get("min_object_size", 16),
                    "transport": meta.get("transport", "tcp"),
                    "detection_confidence": meta.get("detection_confidence", 0.40),
                    "anpr_enabled": meta.get("anpr_enabled", False),
                    "frs_enabled": meta.get("frs_enabled", False),
                    "spatial_rules_enabled": meta.get("spatial_rules_enabled", True),
                }
            }



# Global singleton instance
camera_registry = InMemoryCameraRegistry(initialize_defaults=True)

