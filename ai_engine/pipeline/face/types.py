from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import uuid
import numpy as np

from ai_engine.pipeline.types import BoundingBox


@dataclass
class FaceDetection:
    """Domain representation of a localized human face within a frame or person ROI crop."""
    bbox: BoundingBox
    confidence: float
    landmarks: Optional[List[Tuple[float, float]]] = None  # 5 facial landmarks: (left eye, right eye, nose, left mouth, right mouth)
    parent_track_id: Optional[int] = None
    crop: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bbox": self.bbox.as_xywh(),
            "confidence": round(self.confidence, 4),
            "landmarks": self.landmarks,
            "parent_track_id": self.parent_track_id,
            "metadata": self.metadata,
        }


@dataclass
class FaceEmbedding:
    """
    Domain representation of a 512-dimensional normalized feature embedding vector
    extracted from a human face.
    """
    embedding: np.ndarray
    model_name: str = "mobilefacenet_arcface"
    dimension: int = 512
    track_id: Optional[int] = None
    frame_idx: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_normalized: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.embedding is None:
            raise ValueError("Face embedding array cannot be None")

        if not isinstance(self.embedding, np.ndarray):
            try:
                self.embedding = np.asarray(self.embedding, dtype=np.float32)
            except Exception as e:
                raise ValueError(f"Failed to convert embedding to numpy array: {e}")

        # Flatten in case of (1, 512)
        if self.embedding.ndim > 1:
            self.embedding = self.embedding.flatten()

        if self.embedding.size != self.dimension:
            raise ValueError(
                f"Invalid face embedding dimension: expected {self.dimension}, got {self.embedding.size}"
            )

        # Check for NaN or Inf values
        if np.isnan(self.embedding).any() or np.isinf(self.embedding).any():
            raise ValueError("Face embedding contains NaN or Inf values")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "track_id": self.track_id,
            "frame_idx": self.frame_idx,
            "timestamp": self.timestamp.isoformat(),
            "is_normalized": self.is_normalized,
            "embedding_sample": [round(float(x), 4) for x in self.embedding[:5]],
            "metadata": self.metadata,
        }


@dataclass
class FaceIdentityMatch:
    """Domain representation of a face matching query result against an enrolled gallery."""
    identity_id: str
    display_name: str
    similarity: float
    confidence: float
    is_match: bool = False
    is_unknown: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "display_name": self.display_name,
            "similarity": round(self.similarity, 4),
            "confidence": round(self.confidence, 4),
            "is_match": self.is_match,
            "is_unknown": self.is_unknown,
            "metadata": self.metadata,
        }


@dataclass
class FaceEvent:
    """Domain event emitted when a face is detected, recognized, and associated with a tracked person."""
    camera_id: str
    track_id: int
    identity_id: str
    display_name: str
    similarity: float
    confidence: float
    is_unknown: bool = False
    event_id: str = field(default_factory=lambda: f"face_{uuid.uuid4().hex[:12]}")
    event_type: str = "face_identification"
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
            "identity_id": self.identity_id,
            "display_name": self.display_name,
            "similarity": round(self.similarity, 4),
            "confidence": round(self.confidence, 4),
            "is_unknown": self.is_unknown,
            "position": list(self.position),
            "frame_idx": self.frame_idx,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
