import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any, Set

from ai_engine.pipeline.interfaces import BaseRulesEngine
from ai_engine.pipeline.types import (
    TrackedEntity,
    SpatialZoneEvent,
    SpatialEventType,
    ThreatSeverity,
    TripwireDirection,
    ObjectClass,
)


@dataclass
class PolygonZone:
    """Configurable polygon geofence / virtual perimeter zone."""
    zone_id: str
    name: str
    polygon: List[Tuple[float, float]]
    enabled: bool = True
    severity: ThreatSeverity = ThreatSeverity.HIGH
    allowed_classes: List[str] = field(default_factory=list)
    applicable_classes: List[str] = field(default_factory=list)
    loitering_threshold_seconds: Optional[float] = None

    def __post_init__(self):
        self.allowed_classes = [c.strip().lower() for c in self.allowed_classes if c.strip()]
        self.applicable_classes = [c.strip().lower() for c in self.applicable_classes if c.strip()]
        # Ensure polygon coordinates are floats
        self.polygon = [(float(x), float(y)) for x, y in self.polygon]

    def contains_point(self, point: Tuple[float, float]) -> bool:
        """
        Determines if a 2D point (x, y) is inside the polygon using ray-casting.
        """
        if not self.enabled or len(self.polygon) < 3:
            return False

        x, y = point
        n = len(self.polygon)
        inside = False

        p1x, p1y = self.polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = self.polygon[i % n]
            if min(p1y, p2y) < y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def is_class_applicable(self, class_name: str) -> bool:
        """Checks if this zone rule applies to the object's class."""
        c = class_name.strip().lower()
        if self.applicable_classes and c not in self.applicable_classes:
            return False
        if self.allowed_classes and c in self.allowed_classes:
            return False
        return True


@dataclass
class Tripwire:
    """Configurable line-crossing tripwire."""
    tripwire_id: str
    name: str
    pt1: Tuple[float, float]
    pt2: Tuple[float, float]
    direction: TripwireDirection = TripwireDirection.BIDIRECTIONAL
    enabled: bool = True
    severity: ThreatSeverity = ThreatSeverity.HIGH
    applicable_classes: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.pt1 = (float(self.pt1[0]), float(self.pt1[1]))
        self.pt2 = (float(self.pt2[0]), float(self.pt2[1]))
        self.applicable_classes = [c.strip().lower() for c in self.applicable_classes if c.strip()]
        if isinstance(self.direction, str):
            try:
                self.direction = TripwireDirection(self.direction.upper())
            except ValueError:
                self.direction = TripwireDirection.BIDIRECTIONAL

    def is_class_applicable(self, class_name: str) -> bool:
        """Checks if tripwire evaluates the given object class."""
        if not self.applicable_classes:
            return True
        return class_name.strip().lower() in self.applicable_classes


def _ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> float:
    """Cross product orientation test."""
    return (C[1] - A[1]) * (B[0] - A[0]) - (B[1] - A[1]) * (C[0] - A[0])


def segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    q1: Tuple[float, float],
    q2: Tuple[float, float]
) -> bool:
    """
    Checks if 2D line segment (p1, p2) intersects with line segment (q1, q2).
    """
    # Fast bounding box rejection
    if max(min(p1[0], p2[0]), min(q1[0], q2[0])) > min(max(p1[0], p2[0]), max(q1[0], q2[0])) or \
       max(min(p1[1], p2[1]), min(q1[1], q2[1])) > min(max(p1[1], p2[1]), max(q1[1], q2[1])):
        return False

    d1 = _ccw(q1, q2, p1)
    d2 = _ccw(q1, q2, p2)
    d3 = _ccw(p1, p2, q1)
    d4 = _ccw(p1, p2, q2)

    return ((d1 * d2) < 0) and ((d3 * d4) < 0)


def get_crossing_direction(
    p_start: Tuple[float, float],
    p_end: Tuple[float, float],
    line_start: Tuple[float, float],
    line_end: Tuple[float, float]
) -> Optional[TripwireDirection]:
    """
    Calculates the crossing direction (A_TO_B or B_TO_A) relative to the directed line.
    """
    d_start = _ccw(line_start, line_end, p_start)
    d_end = _ccw(line_start, line_end, p_end)

    if d_start > 0 and d_end < 0:
        return TripwireDirection.A_TO_B
    elif d_start < 0 and d_end > 0:
        return TripwireDirection.B_TO_A
    return None


@dataclass
class _TrackZoneState:
    is_inside: bool = False
    entry_frame_idx: int = 0
    entry_timestamp: float = 0.0
    inside_duration_sec: float = 0.0
    intrusion_alerted: bool = False
    loitering_alerted: bool = False
    last_evaluated_frame: int = 0


@dataclass
class _TrackTripwireState:
    last_crossed_frame: int = -999
    last_direction: Optional[TripwireDirection] = None


class SpatialRulesEngine(BaseRulesEngine):
    """
    Stateful Spatial Rules Engine implementing BaseRulesEngine.
    Evaluates tracks against configured polygon zones (intrusion, loitering, zone exit)
    and line tripwires (directional crossing) with robust state transition tracking to prevent spam.
    """

    def __init__(
        self,
        zones: Optional[List[PolygonZone]] = None,
        tripwires: Optional[List[Tripwire]] = None,
        fps: float = 25.0,
        tripwire_cooldown_frames: int = 10
    ):
        self.zones: Dict[str, PolygonZone] = {z.zone_id: z for z in (zones or [])}
        self.tripwires: Dict[str, Tripwire] = {t.tripwire_id: t for t in (tripwires or [])}
        self.fps = max(1.0, float(fps))
        self.tripwire_cooldown_frames = int(tripwire_cooldown_frames)

        # Internal state tracking: (track_id, zone_id) -> _TrackZoneState
        self._zone_states: Dict[Tuple[int, str], _TrackZoneState] = {}
        # Internal state tracking: (track_id, tripwire_id) -> _TrackTripwireState
        self._tripwire_states: Dict[Tuple[int, str], _TrackTripwireState] = {}

    def add_zone(self, zone: PolygonZone) -> None:
        self.zones[zone.zone_id] = zone

    def add_tripwire(self, tripwire: Tripwire) -> None:
        self.tripwires[tripwire.tripwire_id] = tripwire

    def reset(self) -> None:
        """Resets state histories."""
        self._zone_states.clear()
        self._tripwire_states.clear()

    @classmethod
    def from_dict(cls, data: Dict[str, Any], fps: float = 25.0) -> "SpatialRulesEngine":
        """Constructs engine from a dictionary / parsed JSON schema."""
        zones: List[PolygonZone] = []
        for zd in data.get("zones", []):
            severity = ThreatSeverity(zd.get("severity", "high").lower())
            zone = PolygonZone(
                zone_id=zd["zone_id"],
                name=zd.get("name", zd["zone_id"]),
                polygon=[(p[0], p[1]) for p in zd["polygon"]],
                enabled=zd.get("enabled", True),
                severity=severity,
                allowed_classes=zd.get("allowed_classes", []),
                applicable_classes=zd.get("applicable_classes", []),
                loitering_threshold_seconds=zd.get("loitering_threshold_seconds")
            )
            zones.append(zone)

        tripwires: List[Tripwire] = []
        for td in data.get("tripwires", []):
            severity = ThreatSeverity(td.get("severity", "high").lower())
            direction = TripwireDirection(td.get("direction", "BIDIRECTIONAL").upper())
            tw = Tripwire(
                tripwire_id=td["tripwire_id"],
                name=td.get("name", td["tripwire_id"]),
                pt1=(td["pt1"][0], td["pt1"][1]),
                pt2=(td["pt2"][0], td["pt2"][1]),
                direction=direction,
                enabled=td.get("enabled", True),
                severity=severity,
                applicable_classes=td.get("applicable_classes", [])
            )
            tripwires.append(tw)

        return cls(zones=zones, tripwires=tripwires, fps=fps)

    @classmethod
    def from_file(cls, filepath: str, fps: float = 25.0) -> "SpatialRulesEngine":
        """Loads spatial rules from an external JSON or YAML file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Spatial configuration file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data, fps=fps)

    def evaluate(
        self,
        tracks: List[TrackedEntity],
        camera_id: str = "CAM_01",
        frame_idx: Optional[int] = None,
        timestamp_sec: Optional[float] = None
    ) -> List[SpatialZoneEvent]:
        """
        Evaluates active tracks against all configured zones and tripwires.
        Returns a list of generated security events for the current frame.
        """
        events: List[SpatialZoneEvent] = []
        now = datetime.utcnow()

        current_frame = frame_idx if frame_idx is not None else 0
        current_time_sec = timestamp_sec if timestamp_sec is not None else (current_frame / self.fps)

        # ----------------------------------------------------
        # 1. Evaluate Polygon Zones (Intrusion & Loitering)
        # ----------------------------------------------------
        for zone in self.zones.values():
            if not zone.enabled:
                continue

            for track in tracks:
                state_key = (track.track_id, zone.zone_id)
                state = self._zone_states.get(state_key, _TrackZoneState())

                # Check point-in-polygon using track's bottom center (or center)
                pos = track.current_center
                is_inside = zone.contains_point(pos)
                is_applicable = zone.is_class_applicable(track.raw_class_name)

                if is_inside and is_applicable:
                    if not state.is_inside:
                        # State Transition: OUTSIDE -> INSIDE (New Intrusion!)
                        state.is_inside = True
                        state.entry_frame_idx = current_frame
                        state.entry_timestamp = current_time_sec
                        state.inside_duration_sec = 0.0
                        state.intrusion_alerted = True
                        state.loitering_alerted = False

                        evt = SpatialZoneEvent(
                            camera_id=camera_id,
                            zone_id=zone.zone_id,
                            track_id=track.track_id,
                            rule_type="intrusion",
                            event_type=SpatialEventType.INTRUSION,
                            severity=zone.severity,
                            object_class=track.class_name,
                            confidence=track.confidence,
                            position=pos,
                            frame_idx=current_frame,
                            timestamp=now,
                            details={
                                "zone_name": zone.name,
                                "raw_class": track.raw_class_name,
                                "message": f"{track.raw_class_name.upper()} #{track.track_id} entered restricted zone '{zone.name}'"
                            }
                        )
                        events.append(evt)
                    else:
                        # Continuously Inside -> Update duration and check loitering
                        state.inside_duration_sec = max(0.0, current_time_sec - state.entry_timestamp)
                        # Fallback calculation if timestamp was static
                        if state.inside_duration_sec == 0.0 and current_frame > state.entry_frame_idx:
                            state.inside_duration_sec = (current_frame - state.entry_frame_idx) / self.fps

                        # Check Loitering Rule
                        if zone.loitering_threshold_seconds is not None:
                            if state.inside_duration_sec >= zone.loitering_threshold_seconds and not state.loitering_alerted:
                                state.loitering_alerted = True
                                evt = SpatialZoneEvent(
                                    camera_id=camera_id,
                                    zone_id=zone.zone_id,
                                    track_id=track.track_id,
                                    rule_type="loitering",
                                    event_type=SpatialEventType.LOITERING,
                                    severity=zone.severity,
                                    object_class=track.class_name,
                                    confidence=track.confidence,
                                    position=pos,
                                    frame_idx=current_frame,
                                    timestamp=now,
                                    details={
                                        "zone_name": zone.name,
                                        "duration_seconds": round(state.inside_duration_sec, 1),
                                        "threshold_seconds": zone.loitering_threshold_seconds,
                                        "message": f"{track.raw_class_name.upper()} #{track.track_id} loitering in '{zone.name}' ({state.inside_duration_sec:.1f}s >= {zone.loitering_threshold_seconds}s)"
                                    }
                                )
                                events.append(evt)

                elif not is_inside and state.is_inside:
                    # State Transition: INSIDE -> OUTSIDE (Zone Exit)
                    state.is_inside = False
                    state.intrusion_alerted = False
                    state.loitering_alerted = False
                    # Generate optional exit event for audit trail
                    evt = SpatialZoneEvent(
                        camera_id=camera_id,
                        zone_id=zone.zone_id,
                        track_id=track.track_id,
                        rule_type="zone_exit",
                        event_type=SpatialEventType.ZONE_EXIT,
                        severity=ThreatSeverity.LOW,
                        object_class=track.class_name,
                        confidence=track.confidence,
                        position=pos,
                        frame_idx=current_frame,
                        timestamp=now,
                        details={
                            "zone_name": zone.name,
                            "total_inside_duration": round(state.inside_duration_sec, 1),
                            "message": f"{track.raw_class_name.upper()} #{track.track_id} exited zone '{zone.name}'"
                        }
                    )
                    events.append(evt)

                state.last_evaluated_frame = current_frame
                self._zone_states[state_key] = state

        # ----------------------------------------------------
        # 2. Evaluate Line Tripwires (Crossing & Direction)
        # ----------------------------------------------------
        for tripwire in self.tripwires.values():
            if not tripwire.enabled:
                continue

            for track in tracks:
                if len(track.trajectory) < 2:
                    continue

                if not tripwire.is_class_applicable(track.raw_class_name):
                    continue

                state_key = (track.track_id, tripwire.tripwire_id)
                state = self._tripwire_states.get(state_key, _TrackTripwireState())

                # Check cooldown to prevent duplicate triggers on edge jitter
                if (current_frame - state.last_crossed_frame) < self.tripwire_cooldown_frames:
                    continue

                # Check latest movement vector against tripwire
                p_prev = track.trajectory[-2]
                p_curr = track.trajectory[-1]

                if segments_intersect(p_prev, p_curr, tripwire.pt1, tripwire.pt2):
                    direction = get_crossing_direction(p_prev, p_curr, tripwire.pt1, tripwire.pt2)
                    if direction is not None:
                        # Check direction compatibility
                        is_match = (
                            tripwire.direction == TripwireDirection.BIDIRECTIONAL or
                            tripwire.direction == direction
                        )
                        if is_match:
                            state.last_crossed_frame = current_frame
                            state.last_direction = direction
                            self._tripwire_states[state_key] = state

                            evt = SpatialZoneEvent(
                                camera_id=camera_id,
                                tripwire_id=tripwire.tripwire_id,
                                track_id=track.track_id,
                                rule_type="tripwire_crossing",
                                event_type=SpatialEventType.TRIPWIRE_CROSSING,
                                severity=tripwire.severity,
                                object_class=track.class_name,
                                confidence=track.confidence,
                                position=p_curr,
                                frame_idx=current_frame,
                                timestamp=now,
                                details={
                                    "tripwire_name": tripwire.name,
                                    "direction": direction.value,
                                    "configured_direction": tripwire.direction.value,
                                    "message": f"{track.raw_class_name.upper()} #{track.track_id} crossed tripwire '{tripwire.name}' ({direction.value})"
                                }
                            )
                            events.append(evt)

        return events

    def prune_inactive_tracks(self, active_track_ids: Set[int]) -> None:
        """Removes state entries for tracks that have expired or left the scene."""
        self._zone_states = {
            k: v for k, v in self._zone_states.items() if k[0] in active_track_ids
        }
        self._tripwire_states = {
            k: v for k, v in self._tripwire_states.items() if k[0] in active_track_ids
        }
