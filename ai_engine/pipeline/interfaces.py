from abc import ABC, abstractmethod
from typing import List, Any, Optional, Dict
import numpy as np
from ai_engine.pipeline.types import Detection, TrackedEntity, SpatialZoneEvent


class BaseDetector(ABC):
    """Abstract Interface for Object Detectors (YOLO, Thermal, etc.)"""

    @abstractmethod
    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads and initializes model weights."""
        pass

    @abstractmethod
    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.45) -> List[Detection]:
        """Runs detection inference on a single frame."""
        pass


class BaseTracker(ABC):
    """Abstract Interface for Multi-Object Trackers (ByteTrack, BoT-SORT)."""

    @abstractmethod
    def update(self, detections: List[Detection], frame: np.ndarray) -> List[TrackedEntity]:
        """Updates active tracks with new frame detections."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets tracker state."""
        pass


class BaseRulesEngine(ABC):
    """Abstract Interface for Spatial Geometry & Behavioral Rules."""

    @abstractmethod
    def evaluate(self, tracks: List[TrackedEntity], camera_id: str) -> List[SpatialZoneEvent]:
        """Evaluates tracks against configured spatial zones and tripwires."""
        pass


class BasePlateDetector(ABC):
    """Abstract Interface for License Plate Detectors."""

    @abstractmethod
    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads and initializes plate detector weights."""
        pass

    @abstractmethod
    def detect_plates(
        self,
        vehicle_crop: np.ndarray,
        confidence_threshold: float = 0.40
    ) -> List[Any]:
        """Detects plate bounding boxes within a cropped vehicle image."""
        pass


class BaseOCREngine(ABC):
    """Abstract Interface for Optical Character Recognition Engines."""

    @abstractmethod
    def initialize(self, language: str = "en", use_gpu: bool = False) -> None:
        """Initializes the OCR runtime."""
        pass

    @abstractmethod
    def extract_text(
        self,
        plate_crop: np.ndarray
    ) -> Any:
        """Runs OCR extraction on a cropped plate image."""
        pass


class BaseANPRAnalyzer(ABC):
    """Abstract Interface for ANPR Track Processing and Association."""

    @abstractmethod
    def process_tracks(
        self,
        frame: np.ndarray,
        tracks: List[TrackedEntity],
        camera_id: str,
        frame_idx: int
    ) -> List[Any]:
        """Processes vehicle tracks, detects plates, runs OCR, and produces ANPREvents."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets temporal buffers and state."""
        pass


class BaseFaceDetector(ABC):
    """Abstract Interface for Face Detectors (YOLO-Face, SCRFD, etc.)"""

    @abstractmethod
    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads and initializes face detector weights."""
        pass

    @abstractmethod
    def detect_faces(
        self,
        person_crop: np.ndarray,
        confidence_threshold: float = 0.50
    ) -> List[Any]:
        """Detects face bounding boxes within a cropped person image."""
        pass


class BaseFaceRecognizer(ABC):
    """Abstract Interface for Face Feature Embedding Extractors."""

    @abstractmethod
    def load_model(self, model_path: str, device: str = "cpu") -> None:
        """Loads and initializes face recognition / embedding model weights."""
        pass

    @abstractmethod
    def compute_embedding(
        self,
        face_crop: np.ndarray
    ) -> np.ndarray:
        """Extracts a 512-D L2-normalized feature embedding vector from a cropped face."""
        pass


class BaseFaceMatcher(ABC):
    """Abstract Interface for Face Identity Matching and Gallery Verification."""

    @abstractmethod
    def register_identity(
        self,
        identity_id: str,
        display_name: str,
        embedding: np.ndarray,
        metadata: Optional[dict] = None
    ) -> bool:
        """Enrolls an identity with a reference feature embedding vector."""
        pass

    @abstractmethod
    def remove_identity(self, identity_id: str) -> bool:
        """Removes an identity from the enrolled database."""
        pass

    @abstractmethod
    def match(
        self,
        embedding: np.ndarray,
        threshold: Optional[float] = None
    ) -> Any:
        """Matches a probe face embedding against the enrolled gallery."""
        pass


class BaseFaceAnalyzer(ABC):
    """Abstract Interface for Face Track Processing, Identity Matching, and Temporal Consensus."""

    @abstractmethod
    def process_tracks(
        self,
        frame: np.ndarray,
        tracks: List[TrackedEntity],
        camera_id: str,
        frame_idx: int
    ) -> List[Any]:
        """Processes person tracks, extracts face embeddings, matches gallery, and produces FaceEvents."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets temporal buffers and state."""
        pass

