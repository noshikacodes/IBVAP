from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import uuid
import numpy as np

from ai_engine.pipeline.types import BoundingBox


class PlateFormat(str, Enum):
    """Supported license plate format classifications."""
    UNKNOWN = "unknown"
    STANDARD_INDIAN = "standard_indian"
    BH_SERIES = "bh_series"


@dataclass
class PlateDetection:
    """Domain representation of a localized license plate within a frame or vehicle crop."""
    bbox: BoundingBox
    confidence: float
    parent_track_id: Optional[int] = None
    crop: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": self.bbox.as_xywh(),
            "confidence": round(self.confidence, 4),
            "parent_track_id": self.parent_track_id,
            "metadata": self.metadata,
        }


@dataclass
class OCRResult:
    """Domain representation of extracted OCR text from a license plate crop."""
    raw_text: str
    normalized_text: str
    confidence: float
    plate_format: PlateFormat = PlateFormat.UNKNOWN
    is_valid: bool = False
    character_confidences: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "confidence": round(self.confidence, 4),
            "plate_format": self.plate_format.value if hasattr(self.plate_format, "value") else str(self.plate_format),
            "is_valid": self.is_valid,
            "character_confidences": [round(c, 4) for c in self.character_confidences],
            "metadata": self.metadata,
        }


@dataclass
class ANPREvent:
    """Domain event emitted when a license plate is recognized and associated with a tracked vehicle."""
    camera_id: str
    track_id: int
    plate_number: str
    raw_plate_text: str
    confidence: float
    plate_format: PlateFormat = PlateFormat.UNKNOWN
    is_valid_format: bool = False
    vehicle_class: str = "vehicle"
    event_id: str = field(default_factory=lambda: f"anpr_{uuid.uuid4().hex[:12]}")
    event_type: str = "anpr_detection"
    severity: str = "low"
    bbox: Optional[BoundingBox] = None
    position: Tuple[float, float] = (0.0, 0.0)
    frame_idx: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "plate_number": self.plate_number,
            "raw_plate_text": self.raw_plate_text,
            "confidence": round(self.confidence, 4),
            "plate_format": self.plate_format.value if hasattr(self.plate_format, "value") else str(self.plate_format),
            "is_valid_format": self.is_valid_format,
            "vehicle_class": self.vehicle_class,
            "position": list(self.position),
            "frame_idx": self.frame_idx,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
