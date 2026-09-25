import logging
from abc import ABC, abstractmethod
from typing import Optional, List
import numpy as np
import cv2

from ai_engine.pipeline.anpr.types import OCRResult, PlateFormat
from ai_engine.pipeline.anpr.normalizer import IndianPlateNormalizer

logger = logging.getLogger("ibvap.anpr.ocr")


class BaseOCREngine(ABC):
    """Abstract Interface for Optical Character Recognition Engines (EasyOCR, PaddleOCR, etc.)."""

    @abstractmethod
    def initialize(self, language: str = "en", use_gpu: bool = False) -> None:
        """Initializes the OCR runtime and character dictionaries."""
        pass

    @abstractmethod
    def extract_text(
        self,
        plate_crop: np.ndarray
    ) -> OCRResult:
        """
        Runs optical character recognition on a cropped license plate image.
        Returns an OCRResult containing raw and normalized text.
        """
        pass


class OCREngine(BaseOCREngine):
    """
    Concrete OCR Engine for Phase 5B.2.
    Utilizes EasyOCR (offline CPU/GPU) with image preprocessing and Indian plate normalization.
    """

    def __init__(
        self,
        engine_type: str = "easyocr",
        language: str = "en",
        use_gpu: bool = False,
        normalizer: Optional[IndianPlateNormalizer] = None,
        auto_initialize: bool = True
    ):
        self.engine_type = engine_type.lower()
        self.language = language
        self.use_gpu = use_gpu
        self.normalizer = normalizer or IndianPlateNormalizer()
        self.reader = None
        self.is_initialized = False

        if auto_initialize:
            self.initialize(language=language, use_gpu=use_gpu)

    def initialize(self, language: Optional[str] = None, use_gpu: Optional[bool] = None) -> None:
        """Initializes EasyOCR reader instance."""
        if language is not None:
            self.language = language
        if use_gpu is not None:
            self.use_gpu = use_gpu

        try:
            import easyocr
            self.reader = easyocr.Reader([self.language], gpu=self.use_gpu, verbose=False)
            self.is_initialized = True
            logger.info("Initialized EasyOCR engine (lang=%s, gpu=%s)", self.language, self.use_gpu)
        except Exception as e:
            logger.warning("Failed to initialize EasyOCR: %s. Running in stub fallback mode.", e)
            self.reader = None
            self.is_initialized = False

    def preprocess_plate(self, plate_crop: np.ndarray) -> np.ndarray:
        """
        Conservative preprocessing pipeline:
        - Resize small crops with aspect ratio preservation (min height 48px, min width 140px)
        - Grayscale conversion
        - CLAHE contrast enhancement for embossed characters
        """
        if plate_crop is None or plate_crop.size == 0:
            return plate_crop

        h, w = plate_crop.shape[:2]
        target_h = max(48, h)
        scale = target_h / float(h)
        target_w = max(140, int(w * scale))

        # 1. Resize
        resized = cv2.resize(plate_crop, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

        # 2. Grayscale
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized

        # 3. Mild CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        return enhanced

    def extract_text(
        self,
        plate_crop: np.ndarray
    ) -> OCRResult:
        """
        Runs optical character recognition on a cropped license plate image.
        Returns an OCRResult containing raw text, normalized text, and confidence.
        Never throws unhandled exceptions to prevent crashing the video pipeline.
        """
        if plate_crop is None or not isinstance(plate_crop, np.ndarray) or plate_crop.size == 0:
            return OCRResult(
                raw_text="",
                normalized_text="",
                confidence=0.0,
                plate_format=PlateFormat.UNKNOWN,
                is_valid=False
            )

        if not self.is_initialized or self.reader is None:
            return OCRResult(
                raw_text="",
                normalized_text="",
                confidence=0.0,
                plate_format=PlateFormat.UNKNOWN,
                is_valid=False,
                metadata={"error": "OCR engine not initialized"}
            )

        try:
            preprocessed = self.preprocess_plate(plate_crop)

            # EasyOCR readtext returns: [ (bbox, text, prob), ... ]
            detections = self.reader.readtext(preprocessed, detail=1, paragraph=False)
            if not detections:
                return OCRResult(
                    raw_text="",
                    normalized_text="",
                    confidence=0.0,
                    plate_format=PlateFormat.UNKNOWN,
                    is_valid=False
                )

            # Combine text fragments ordered horizontally/vertically
            text_tokens: List[str] = []
            confidences: List[float] = []

            for item in detections:
                if len(item) >= 3:
                    _, text, prob = item[0], item[1], float(item[2])
                    cleaned_token = str(text).strip()
                    if cleaned_token:
                        text_tokens.append(cleaned_token)
                        confidences.append(prob)

            if not text_tokens:
                return OCRResult(
                    raw_text="",
                    normalized_text="",
                    confidence=0.0,
                    plate_format=PlateFormat.UNKNOWN,
                    is_valid=False
                )

            raw_combined = " ".join(text_tokens)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            # Pass through IndianPlateNormalizer
            norm_result = self.normalizer.process(raw_combined, confidence=avg_conf)
            norm_result.character_confidences = confidences
            norm_result.metadata = {
                "engine": self.engine_type,
                "token_count": len(text_tokens),
            }
            return norm_result

        except Exception as e:
            logger.debug("OCR extraction exception: %s", e)
            return OCRResult(
                raw_text="",
                normalized_text="",
                confidence=0.0,
                plate_format=PlateFormat.UNKNOWN,
                is_valid=False,
                metadata={"exception": str(e)}
            )
