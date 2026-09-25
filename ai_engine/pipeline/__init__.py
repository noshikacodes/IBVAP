"""IBVAP AI Engine Pipeline Package."""
from ai_engine.pipeline.types import (
    ObjectClass,
    ThreatSeverity,
    TrackState,
    SpatialEventType,
    TripwireDirection,
    BoundingBox,
    Detection,
    TrackedEntity,
    SpatialZoneEvent,
)
from ai_engine.pipeline.interfaces import (
    BaseDetector,
    BaseTracker,
    BaseRulesEngine,
)
from ai_engine.pipeline.config import (
    InferenceConfig,
    DEFAULT_TARGET_CLASSES,
)
from ai_engine.pipeline.stream_reader import (
    VideoReader,
    VideoStreamError,
    VideoNotFoundError,
    InvalidVideoFormatError,
    CorruptVideoError,
)
from ai_engine.pipeline.gits_resolver import (
    is_gits_source,
    extract_gits_cctv_id,
    resolve_gits_hls_url,
    GITSResolutionError,
)
from ai_engine.pipeline.detector import (
    YOLODetector,
    DetectorError,
    ModelLoadError,
    ModelInferenceError,
)
from ai_engine.pipeline.tracker import (
    MultiObjectTracker,
    TrackerError,
)
from ai_engine.pipeline.spatial_rules import (
    SpatialRulesEngine,
    PolygonZone,
    Tripwire,
    segments_intersect,
    get_crossing_direction,
)
from ai_engine.pipeline.annotator import (
    VideoAnnotator,
    VideoWriter,
    CLASS_COLORS,
    EVENT_COLORS,
)
from ai_engine.pipeline.inference_runner import (
    InferencePipeline,
)
from ai_engine.pipeline.traffic_counter import (
    TrafficCountingEngine,
    TrafficCrossingEvent,
    normalize_traffic_class,
)

__all__ = [
    # Domain Types & Lifecycles
    "ObjectClass",
    "ThreatSeverity",
    "TrackState",
    "SpatialEventType",
    "TripwireDirection",
    "BoundingBox",
    "Detection",
    "TrackedEntity",
    "SpatialZoneEvent",
    # Abstract Interfaces
    "BaseDetector",
    "BaseTracker",
    "BaseRulesEngine",
    # Configuration
    "InferenceConfig",
    "DEFAULT_TARGET_CLASSES",
    # Video Ingestion
    "VideoReader",
    "VideoStreamError",
    "VideoNotFoundError",
    "InvalidVideoFormatError",
    "CorruptVideoError",
    "is_gits_source",
    "extract_gits_cctv_id",
    "resolve_gits_hls_url",
    "GITSResolutionError",
    # Object Detection
    "YOLODetector",
    "DetectorError",
    "ModelLoadError",
    "ModelInferenceError",
    # Multi-Object Tracking
    "MultiObjectTracker",
    "TrackerError",
    # Spatial Intelligence & Rules
    "SpatialRulesEngine",
    "PolygonZone",
    "Tripwire",
    "segments_intersect",
    "get_crossing_direction",
    # Video Annotation & HUD
    "VideoAnnotator",
    "VideoWriter",
    "CLASS_COLORS",
    "EVENT_COLORS",
    # Traffic Analytics & Counting
    "TrafficCountingEngine",
    "TrafficCrossingEvent",
    "normalize_traffic_class",
    # Pipeline Orchestration
    "InferencePipeline",
]
