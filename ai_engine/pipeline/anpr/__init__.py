"""
IBVAP ANPR (Automatic Number Plate Recognition) Subsystem Contracts (Phase 5B.1)
"""

from ai_engine.pipeline.anpr.types import (
    PlateFormat,
    PlateDetection,
    OCRResult,
    ANPREvent,
)
from ai_engine.pipeline.anpr.normalizer import (
    IndianPlateNormalizer,
    normalize_plate_text,
    validate_indian_plate,
)
from ai_engine.pipeline.anpr.plate_detector import (
    BasePlateDetector,
    PlateDetector,
)
from ai_engine.pipeline.anpr.ocr_engine import (
    BaseOCREngine,
    OCREngine,
)
from ai_engine.pipeline.anpr.analyzer import (
    BaseANPRAnalyzer,
    ANPRAnalyzer,
)

__all__ = [
    "PlateFormat",
    "PlateDetection",
    "OCRResult",
    "ANPREvent",
    "IndianPlateNormalizer",
    "normalize_plate_text",
    "validate_indian_plate",
    "BasePlateDetector",
    "PlateDetector",
    "BaseOCREngine",
    "OCREngine",
    "BaseANPRAnalyzer",
    "ANPRAnalyzer",
]
