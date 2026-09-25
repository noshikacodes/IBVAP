import time
from typing import Optional, List, Dict, Tuple, Any, Callable
from datetime import datetime
import uuid

from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.services.priority import get_alert_severity
from backend.app.services.alert_repository import BaseAlertRepository, alert_repository
from backend.app.services.redis_bus import RedisEventBus, redis_event_bus
from backend.app.core.config import settings
from backend.app.core.logging import logger
from ai_engine.pipeline.types import SpatialZoneEvent


class AlertEngine:
    """
    Stateful Alert Engine:
    - Converts SecurityEvents to prioritized Alerts.
    - Performs alert deduplication and rate-limiting cooldown.
    - Stores alerts in the repository.
    - Dispatches alerts to Redis Pub/Sub transport and registered listeners.
    """

    def __init__(
        self,
        repository: Optional[BaseAlertRepository] = None,
        event_bus: Optional[RedisEventBus] = None,
        cooldown_seconds: Optional[float] = None,
        priority_policy: Optional[Dict[str, str]] = None,
        publish_to_redis: bool = True
    ):
        self.repository = repository or alert_repository
        self.event_bus = event_bus or redis_event_bus
        self.cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else settings.ALERT_COOLDOWN_SECONDS
        self.priority_policy = priority_policy if priority_policy is not None else settings.ALERT_PRIORITY_POLICY
        self.publish_to_redis = publish_to_redis

        # Internal deduplication cache: (event_type, camera_id, track_id, target_id) -> last_alert_timestamp
        self._dedup_cache: Dict[Tuple[str, str, int, str], float] = {}
        self._listeners: List[Callable[[Alert], Any]] = []

    def register_listener(self, callback: Callable[[Alert], Any]) -> None:
        """Registers an in-process callback listener for newly produced alerts."""
        self._listeners.append(callback)

    def is_duplicate(
        self,
        event_type: str,
        camera_id: str,
        track_id: int,
        target_id: str,
        current_time: Optional[float] = None
    ) -> bool:
        """
        Checks if an equivalent alert was generated recently within the cooldown window.
        """
        t = current_time if current_time is not None else time.time()
        dedup_key = (
            event_type.strip().lower(),
            camera_id.strip(),
            int(track_id),
            target_id.strip() if target_id else "default"
        )

        last_time = self._dedup_cache.get(dedup_key)
        if last_time is not None and (t - last_time) < self.cooldown_seconds:
            return True

        self._dedup_cache[dedup_key] = t
        return False

    def process_event(
        self,
        event: SpatialZoneEvent,
        current_time: Optional[float] = None
    ) -> Optional[Alert]:
        """
        Processes a single security event:
        Deduplicates, classifies priority, persists, and publishes the resulting Alert.
        Returns the Alert if created, or None if suppressed by deduplication cooldown.
        """
        event_type = event.rule_type or (event.event_type.value if event.event_type else "intrusion")
        target_id = event.zone_id or event.tripwire_id or ""

        # Step 1: Evaluate Deduplication Cooldown
        if self.is_duplicate(
            event_type=event_type,
            camera_id=event.camera_id,
            track_id=event.track_id,
            target_id=target_id,
            current_time=current_time
        ):
            logger.debug(
                "Suppressed duplicate alert: type=%s, cam=%s, track=%s, target=%s",
                event_type, event.camera_id, event.track_id, target_id
            )
            return None

        # Step 2: Determine Priority / Severity
        severity = get_alert_severity(event_type, self.priority_policy)

        # Step 3: Build Message
        message = event.details.get("message")
        if not message:
            class_str = event.object_class.value.upper() if hasattr(event.object_class, "value") else str(event.object_class).upper()
            target_name = event.details.get("zone_name") or event.details.get("tripwire_name") or target_id
            message = f"{class_str} #{event.track_id} triggered {event_type.upper()} on {target_name}"

        # Step 4: Create Alert Domain Object
        alert = Alert(
            alert_id=f"alt_{uuid.uuid4().hex[:12]}",
            event_id=event.event_id,
            event_type=event_type,
            severity=severity,
            timestamp=event.timestamp or datetime.utcnow(),
            camera_id=event.camera_id,
            track_id=event.track_id,
            object_class=event.object_class.value if hasattr(event.object_class, "value") else str(event.object_class),
            zone_id=event.zone_id,
            tripwire_id=event.tripwire_id,
            position=event.position,
            message=message,
            metadata=dict(event.details),
            status=AlertStatus.NEW
        )

        # Step 5: Save to Repository
        self.repository.create(alert)

        # Telemetry Hook
        try:
            from ai_engine.telemetry.metrics import metrics_registry
            evt_type = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
            sev_val = alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity)
            metrics_registry.alerts_created.inc(labels={
                "camera_id": event.camera_id,
                "event_type": str(evt_type),
                "severity": str(sev_val).lower()
            })
            metrics_registry.spatial_breaches.inc(labels={
                "camera_id": event.camera_id,
                "rule_type": str(evt_type),
                "severity": str(sev_val).lower()
            })
        except Exception:
            pass


        # Step 6: Publish to Redis Pub/Sub (if enabled)
        if self.publish_to_redis and self.event_bus:
            self.event_bus.publish_alert_sync(alert)


        # Step 7: Trigger PTZ Slew-to-Cue (if enabled for camera)
        try:
            from ai_engine.pipeline.ptz import ptz_controller
            ptz_controller.process_threat_cue(
                camera_id=event.camera_id,
                target_bbox_or_point=event.position or (320.0, 240.0),
                severity=severity.value if hasattr(severity, "value") else str(severity),
                event_type=event_type,
                track_id=event.track_id,
                current_time=current_time
            )
        except Exception as e:
            logger.debug("PTZ cue evaluation skipped: %s", e)

        # Step 8: Notify local listeners
        for listener in self._listeners:
            try:
                listener(alert)
            except Exception as e:
                logger.warning("Error in alert listener: %s", e)

        return alert

    def process_events_batch(
        self,
        events: List[SpatialZoneEvent],
        current_time: Optional[float] = None
    ) -> List[Alert]:
        """Processes a list of events and returns all created alerts."""
        alerts: List[Alert] = []
        for evt in events:
            alt = self.process_event(evt, current_time=current_time)
            if alt is not None:
                alerts.append(alt)
        return alerts

    def process_anpr_event(
        self,
        event: Any,
        current_time: Optional[float] = None
    ) -> Optional[Alert]:
        """
        Processes an ANPREvent:
        Deduplicates, classifies priority, persists, and publishes the resulting Alert.
        """
        event_type = getattr(event, "event_type", "anpr_detection")
        plate_number = getattr(event, "plate_number", "")
        camera_id = getattr(event, "camera_id", "CAM_01")
        track_id = getattr(event, "track_id", 0)

        # Deduplication check
        if self.is_duplicate(
            event_type=event_type,
            camera_id=camera_id,
            track_id=track_id,
            target_id=plate_number or "default_plate",
            current_time=current_time
        ):
            logger.debug(
                "Suppressed duplicate ANPR alert: cam=%s, track=%s, plate=%s",
                camera_id, track_id, plate_number
            )
            return None

        # Severity & Message
        severity = get_alert_severity(event_type, self.priority_policy)
        veh_class = getattr(event, "vehicle_class", "vehicle").upper()
        plate_format_val = getattr(event, "plate_format", None)
        if hasattr(plate_format_val, "value"):
            plate_format_str = plate_format_val.value
        else:
            plate_format_str = str(plate_format_val) if plate_format_val else "standard_indian"

        message = f"VEHICLE #{track_id} ({veh_class}) identified with Plate [{plate_number}]"

        metadata = dict(getattr(event, "metadata", {}) or {})
        metadata["plate_number"] = plate_number
        metadata["raw_plate_text"] = getattr(event, "raw_plate_text", "")
        metadata["plate_format"] = plate_format_str
        metadata["confidence"] = getattr(event, "confidence", 1.0)
        metadata["is_valid_format"] = getattr(event, "is_valid_format", True)

        alert = Alert(
            alert_id=f"alt_{uuid.uuid4().hex[:12]}",
            event_id=getattr(event, "event_id", f"anpr_{uuid.uuid4().hex[:8]}"),
            event_type=event_type,
            severity=severity,
            timestamp=getattr(event, "timestamp", datetime.utcnow()) or datetime.utcnow(),
            camera_id=camera_id,
            track_id=track_id,
            object_class=getattr(event, "vehicle_class", "car"),
            position=getattr(event, "position", (0.0, 0.0)) or (0.0, 0.0),
            message=message,
            metadata=metadata,
            status=AlertStatus.NEW
        )

        self.repository.create(alert)

        if self.publish_to_redis and self.event_bus:
            self.event_bus.publish_alert_sync(alert)

        for listener in self._listeners:
            try:
                listener(alert)
            except Exception as e:
                logger.warning("Error in alert listener: %s", e)

        return alert

    def process_face_event(
        self,
        event: Any,
        current_time: Optional[float] = None
    ) -> Optional[Alert]:
        """
        Processes a FaceEvent:
        Deduplicates, classifies priority, persists, and publishes the resulting Alert.
        """
        event_type = getattr(event, "event_type", "frs_identification")
        identity_id = getattr(event, "identity_id", "UNKNOWN")
        display_name = getattr(event, "display_name", identity_id)
        camera_id = getattr(event, "camera_id", "CAM_01")
        track_id = getattr(event, "track_id", 0)
        is_unknown = getattr(event, "is_unknown", False)
        similarity = float(getattr(event, "similarity", 0.0))

        # Deduplication check
        if self.is_duplicate(
            event_type=event_type,
            camera_id=camera_id,
            track_id=track_id,
            target_id=identity_id or "default_face",
            current_time=current_time
        ):
            logger.debug(
                "Suppressed duplicate Face alert: cam=%s, track=%s, identity=%s",
                camera_id, track_id, identity_id
            )
            return None

        # Severity & Message
        severity = get_alert_severity(event_type, self.priority_policy)
        if is_unknown or identity_id == "UNKNOWN":
            message = f"PERSON #{track_id} detected as UNREGISTERED / UNKNOWN (Face)"
        else:
            message = f"PERSON #{track_id} identified as [{display_name}] (Sim: {similarity * 100:.1f}%)"

        metadata = dict(getattr(event, "metadata", {}) or {})
        metadata["identity_id"] = identity_id
        metadata["display_name"] = display_name
        metadata["similarity"] = round(similarity, 4)
        metadata["confidence"] = round(float(getattr(event, "confidence", similarity)), 4)
        metadata["is_unknown"] = is_unknown

        bbox_val = getattr(event, "bbox", None)
        if bbox_val is not None:
            if hasattr(bbox_val, "as_xywh"):
                metadata["face_bbox"] = bbox_val.as_xywh()
            elif hasattr(bbox_val, "as_dict"):
                metadata["face_bbox"] = bbox_val.as_dict()

        alert = Alert(
            alert_id=f"alt_{uuid.uuid4().hex[:12]}",
            event_id=getattr(event, "event_id", f"face_{uuid.uuid4().hex[:8]}"),
            event_type=event_type,
            severity=severity,
            timestamp=getattr(event, "timestamp", datetime.utcnow()) or datetime.utcnow(),
            camera_id=camera_id,
            track_id=track_id,
            object_class="person",
            position=getattr(event, "position", (0.0, 0.0)) or (0.0, 0.0),
            message=message,
            metadata=metadata,
            status=AlertStatus.NEW
        )

        self.repository.create(alert)

        if self.publish_to_redis and self.event_bus:
            self.event_bus.publish_alert_sync(alert)

        for listener in self._listeners:
            try:
                listener(alert)
            except Exception as e:
                logger.warning("Error in alert listener: %s", e)

        return alert

    def clear_cooldowns(self) -> None:
        """Clears deduplication cache."""
        self._dedup_cache.clear()


# Global singleton instance
alert_engine = AlertEngine()

