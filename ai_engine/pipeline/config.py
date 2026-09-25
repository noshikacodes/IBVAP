import os
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple


DEFAULT_TARGET_CLASSES = [
    "person",
    "human",
    "car",
    "motorcycle",
    "bus",
    "truck",
    "bicycle",
    "boat",
    "vessel",
    "vehicle"
]

NETWORK_STREAM_PREFIXES = ("rtsp://", "rtsps://", "http://", "https://", "rtmp://")


@dataclass
class InferenceConfig:
    """Configuration settings for the AI inference, tracking, spatial rules, and alert pipeline."""

    input_path: str
    output_path: Optional[str] = None
    model_name_or_path: str = "yolo26s.pt"
    models_dir: str = "ai_engine/models_weight"
    confidence_threshold: float = 0.25
    imgsz: int = 640
    device: str = "cpu"  # "cpu", "cuda", "cuda:0", etc.
    skip_frames: int = 0  # 0 means process every frame, 1 means process every 2nd frame, etc.
    target_classes: Optional[List[str]] = field(default_factory=lambda: list(DEFAULT_TARGET_CLASSES))
    
    # Road ROI Configuration (Enhance distant vehicle detection)
    use_road_roi: bool = False
    road_roi_ymin: float = 160.0
    road_roi_ymax: float = 480.0
    
    # Tracking Configuration (Phase 2B)
    enable_tracking: bool = True
    tracker_type: str = "bytetrack"  # "bytetrack" or "native"
    max_trajectory_length: int = 30
    max_lost_frames: int = 15
    iou_threshold: float = 0.25
    min_hits: int = 1
    
    # Spatial Rules Configuration (Phase 3A)
    spatial_rules_path: Optional[str] = None
    camera_id: str = "CAM_01"
    draw_zones: bool = True
    draw_events: bool = True
    
    # Alert Delivery Configuration (Phase 3B)
    enable_alert_engine: bool = True
    publish_redis: bool = False
    redis_url: Optional[str] = None
    redis_channel: Optional[str] = None
    alert_cooldown_seconds: float = 15.0
    
    # RTSP Ingestion Configuration (Phase 5A)
    reconnect_delay: float = 2.0
    max_reconnect_retries: int = 5
    
    # ANPR Configuration (Phase 5B)
    enable_anpr: bool = False
    anpr_detector_model: str = "yolov8n_plate.pt"
    anpr_ocr_engine: str = "paddleocr"
    anpr_min_conf: float = 0.60
    anpr_consensus_votes: int = 3
    anpr_frame_stride: int = 3
    anpr_min_vehicle_size: int = 60
    anpr_ocr_confidence: float = 0.50
    anpr_voting_window_frames: int = 15

    # Face Recognition Configuration (Phase 5C)
    enable_frs: bool = False
    frs_detector_model: str = "yolov8n_face.pt"
    frs_recognizer_model: str = "mobilefacenet_arcface.onnx"
    frs_face_confidence: float = 0.50
    frs_match_threshold: float = 0.65
    frs_frame_stride: int = 3
    frs_consensus_votes: int = 3
    frs_min_face_size: int = 32
    frs_unknown_enabled: bool = True
    frs_embedding_dimension: int = 512
    frs_voting_window_frames: int = 15
    frs_gallery_path: Optional[str] = None

    # Traffic Analytics & Unique Counting Configuration
    enable_traffic_counting: bool = True
    traffic_line_pt1: Tuple[float, float] = (50.0, 360.0)
    traffic_line_pt2: Tuple[float, float] = (670.0, 360.0)
    save_traffic_evidence: bool = True
    traffic_evidence_dir: str = "data/evidence"

    # Visualization Configuration
    draw_trajectories: bool = True
    draw_telemetry: bool = True
    save_annotated_video: bool = True

    def __post_init__(self):
        # Normalize and validate paths
        if self.input_path and not self.input_path.lower().startswith(NETWORK_STREAM_PREFIXES) and not self.input_path.isdigit():
            self.input_path = os.path.abspath(self.input_path)
        
        if self.output_path:
            self.output_path = os.path.abspath(self.output_path)

        self.models_dir = os.path.abspath(self.models_dir)
        if self.spatial_rules_path:
            self.spatial_rules_path = os.path.abspath(self.spatial_rules_path)

        # Auto-configure camera-specific counting lines if using default line
        if self.traffic_line_pt1 == (50.0, 360.0) and self.traffic_line_pt2 == (670.0, 360.0):
            if "1809" in self.camera_id:
                self.traffic_line_pt1 = (120.0, 360.0)
                self.traffic_line_pt2 = (600.0, 360.0)
            elif "95366" in self.camera_id or "SEJONG" in self.camera_id:
                self.traffic_line_pt1 = (80.0, 360.0)
                self.traffic_line_pt2 = (650.0, 360.0)

        # Validate confidence
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(f"Confidence threshold must be between 0.0 and 1.0, got {self.confidence_threshold}")

        # Validate image size
        if self.imgsz <= 0 or self.imgsz % 32 != 0:
            raise ValueError(f"imgsz must be a positive multiple of 32, got {self.imgsz}")

        # Validate skip frames
        if self.skip_frames < 0:
            raise ValueError(f"skip_frames must be >= 0, got {self.skip_frames}")

        # Validate tracking parameters
        if self.max_trajectory_length < 2:
            raise ValueError(f"max_trajectory_length must be >= 2, got {self.max_trajectory_length}")

        if self.max_lost_frames < 1:
            raise ValueError(f"max_lost_frames must be >= 1, got {self.max_lost_frames}")

        if not (0.0 <= self.iou_threshold <= 1.0):
            raise ValueError(f"iou_threshold must be between 0.0 and 1.0, got {self.iou_threshold}")

        # Validate ANPR parameters (Phase 5B)
        if not (0.0 <= self.anpr_min_conf <= 1.0):
            raise ValueError(f"anpr_min_conf must be between 0.0 and 1.0, got {self.anpr_min_conf}")

        if not (0.0 <= self.anpr_ocr_confidence <= 1.0):
            raise ValueError(f"anpr_ocr_confidence must be between 0.0 and 1.0, got {self.anpr_ocr_confidence}")

        if self.anpr_consensus_votes < 1:
            raise ValueError(f"anpr_consensus_votes must be >= 1, got {self.anpr_consensus_votes}")

        if self.anpr_frame_stride < 1:
            raise ValueError(f"anpr_frame_stride must be >= 1, got {self.anpr_frame_stride}")

        if self.anpr_min_vehicle_size < 10:
            raise ValueError(f"anpr_min_vehicle_size must be >= 10, got {self.anpr_min_vehicle_size}")

        if self.anpr_voting_window_frames < 1:
            raise ValueError(f"anpr_voting_window_frames must be >= 1, got {self.anpr_voting_window_frames}")

        # Validate FRS parameters (Phase 5C)
        if not (0.0 <= self.frs_face_confidence <= 1.0):
            raise ValueError(f"frs_face_confidence must be between 0.0 and 1.0, got {self.frs_face_confidence}")

        if not (0.0 <= self.frs_match_threshold <= 1.0):
            raise ValueError(f"frs_match_threshold must be between 0.0 and 1.0, got {self.frs_match_threshold}")

        if self.frs_consensus_votes < 1:
            raise ValueError(f"frs_consensus_votes must be >= 1, got {self.frs_consensus_votes}")

        if self.frs_frame_stride < 1:
            raise ValueError(f"frs_frame_stride must be >= 1, got {self.frs_frame_stride}")

        if self.frs_min_face_size < 10:
            raise ValueError(f"frs_min_face_size must be >= 10, got {self.frs_min_face_size}")

        if self.frs_embedding_dimension < 64:
            raise ValueError(f"frs_embedding_dimension must be >= 64, got {self.frs_embedding_dimension}")

        if self.frs_voting_window_frames < 1:
            raise ValueError(f"frs_voting_window_frames must be >= 1, got {self.frs_voting_window_frames}")

        # Lowercase target classes set for fast lookup
        if self.target_classes is not None:
            self._target_classes_set: Set[str] = {c.strip().lower() for c in self.target_classes if c.strip()}
        else:
            self._target_classes_set = set()

    def is_class_allowed(self, class_name: str) -> bool:
        """Checks if a given class name is in the allowed target classes."""
        if not self._target_classes_set:
            return True
        return class_name.strip().lower() in self._target_classes_set
