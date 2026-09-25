from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import uuid


class ObjectClass(str, Enum):
    HUMAN = "human"
    PERSON = "person"
    VEHICLE = "vehicle"
    CAR = "car"
    MOTORCYCLE = "motorcycle"
    BUS = "bus"
    TRUCK = "truck"
    VESSEL = "vessel"
    BOAT = "boat"
    BICYCLE = "bicycle"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, name: str) -> "ObjectClass":
        """Maps arbitrary string names to ObjectClass enum with fallback."""
        clean_name = name.strip().lower()
        for item in cls:
            if item.value == clean_name:
                return item
        # Common aliases
        if clean_name in ("pedestrian", "man", "woman"):
            return cls.HUMAN
        if clean_name in ("automobile", "sedan", "suv"):
            return cls.CAR
        if clean_name in ("motorbike", "bike"):
            return cls.MOTORCYCLE
        if clean_name in ("ship", "yacht"):
            return cls.VESSEL
        return cls.UNKNOWN


class ThreatSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrackState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    LOST = "lost"
    EXPIRED = "expired"


class SpatialEventType(str, Enum):
    INTRUSION = "intrusion"
    ZONE_EXIT = "zone_exit"
    TRIPWIRE_CROSSING = "tripwire_crossing"
    LOITERING = "loitering"


class TripwireDirection(str, Enum):
    A_TO_B = "A_TO_B"
    B_TO_A = "B_TO_A"
    BIDIRECTIONAL = "BIDIRECTIONAL"


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, self.y2)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_int_xyxy(self) -> Tuple[int, int, int, int]:
        """Returns integer pixel coordinates (x1, y1, x2, y2)."""
        return (int(round(self.x1)), int(round(self.y1)), int(round(self.x2)), int(round(self.y2)))

    def as_xywh(self) -> Tuple[float, float, float, float]:
        """Returns (x1, y1, width, height)."""
        return (self.x1, self.y1, self.width, self.height)

    @classmethod
    def from_xyxy(cls, x1: float, y1: float, x2: float, y2: float) -> "BoundingBox":
        return cls(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2))

    def iou(self, other: "BoundingBox") -> float:
        """Calculates Intersection over Union (IoU) with another BoundingBox."""
        ix1 = max(self.x1, other.x1)
        iy1 = max(self.y1, other.y1)
        ix2 = min(self.x2, other.x2)
        iy2 = min(self.y2, other.y2)

        intersection_w = max(0.0, ix2 - ix1)
        intersection_h = max(0.0, iy2 - iy1)
        intersection_area = intersection_w * intersection_h

        union_area = self.area + other.area - intersection_area
        if union_area <= 0.0:
            return 0.0
        return intersection_area / union_area


@dataclass
class Detection:
    class_name: ObjectClass
    confidence: float
    bbox: BoundingBox
    track_id: Optional[int] = None
    raw_class_name: str = ""
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.raw_class_name:
            self.raw_class_name = self.class_name.value


@dataclass
class TrackedEntity:
    """Domain representation of a persistent tracked object with trajectory history and lifecycle."""
    track_id: int
    class_name: ObjectClass
    current_bbox: BoundingBox
    confidence: float = 0.0
    raw_class_name: str = ""
    state: TrackState = TrackState.ACTIVE
    trajectory: List[Tuple[float, float]] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    first_frame_idx: int = 0
    last_frame_idx: int = 0
    hits: int = 1
    time_since_update: int = 0
    is_active: bool = True
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.raw_class_name:
            self.raw_class_name = self.class_name.value
        if not self.trajectory:
            self.trajectory.append(self.current_bbox.center)

    @property
    def current_center(self) -> Tuple[float, float]:
        return self.current_bbox.center

    @property
    def current_bottom_center(self) -> Tuple[float, float]:
        return self.current_bbox.bottom_center

    @property
    def age(self) -> int:
        return max(1, self.last_frame_idx - self.first_frame_idx + 1)

    def add_trajectory_point(self, pt: Tuple[float, float], max_length: int = 30) -> None:
        self.trajectory.append(pt)
        if len(self.trajectory) > max_length:
            self.trajectory = self.trajectory[-max_length:]

    def update(
        self,
        bbox: BoundingBox,
        confidence: float,
        frame_idx: int,
        max_trajectory_length: int = 30
    ) -> None:
        """Updates track with a new matched detection."""
        self.current_bbox = bbox
        self.confidence = float(confidence)
        self.last_seen = datetime.utcnow()
        self.last_frame_idx = frame_idx
        self.hits += 1
        self.time_since_update = 0
        self.state = TrackState.ACTIVE
        self.is_active = True
        self.add_trajectory_point(bbox.center, max_length=max_trajectory_length)

    def mark_missed(self, max_lost_frames: int) -> None:
        """Marks track as missing in current frame and transitions lifecycle state."""
        self.time_since_update += 1
        if self.time_since_update > max_lost_frames:
            self.state = TrackState.EXPIRED
            self.is_active = False
        else:
            self.state = TrackState.LOST


@dataclass
class SpatialZoneEvent:
    """Domain model for a verified spatial security rule violation or perimeter event."""
    camera_id: str
    track_id: int
    rule_type: str = "intrusion"  # e.g., "intrusion", "tripwire_crossing", "loitering", "zone_exit"
    severity: ThreatSeverity = ThreatSeverity.HIGH
    zone_id: Optional[str] = None
    tripwire_id: Optional[str] = None
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    event_type: Optional[SpatialEventType] = None
    object_class: ObjectClass = ObjectClass.UNKNOWN
    confidence: float = 0.0
    position: Tuple[float, float] = (0.0, 0.0)
    frame_idx: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    snapshot_path: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.event_type is None:
            # Map from rule_type string
            try:
                self.event_type = SpatialEventType(self.rule_type.lower())
            except ValueError:
                self.event_type = SpatialEventType.INTRUSION
        elif not self.rule_type:
            self.rule_type = self.event_type.value
