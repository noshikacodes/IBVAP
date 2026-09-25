import re
from typing import Tuple, Optional
from ai_engine.pipeline.anpr.types import PlateFormat, OCRResult


# Regex patterns for deterministic Indian plate syntax validation
# Standard RTO: 2-letter state code + 1 or 2-digit RTO district + 1 to 3 series letters + 4-digit number
STANDARD_INDIAN_REGEX = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$")

# Bharat Series (BH): 2-digit year of registration + 'BH' + 4-digit number + 1 or 2 letters
BH_SERIES_REGEX = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")

# Characters to strip during separator normalization
SEPARATORS_REGEX = re.compile(r"[\s\-\.\:_\/,\|\'\"\\~`#@$%^&*()+={}\[\]<>?]+", re.UNICODE)


def normalize_plate_text(raw_text: Optional[str]) -> str:
    """
    Performs deterministic cleanup on raw OCR text:
    - Converts to uppercase
    - Removes whitespace and common punctuation/separators
    - Safely strips isolated leading 'IND' country identifier if remaining string is a plausible plate length (>= 8 chars)
    
    Note: Does not perform speculative character mutations that could corrupt valid plates.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""

    # Step 1: Uppercase and strip outer whitespace
    cleaned = raw_text.strip().upper()

    # Step 2: Remove separators (spaces, hyphens, dots, colons, underscores, slashes)
    cleaned = SEPARATORS_REGEX.sub("", cleaned)

    # Step 3: Strip leading 'IND' prefix if plate length remains sufficient (>= 8 alphanumeric characters)
    if cleaned.startswith("IND") and len(cleaned) >= 11:
        candidate = cleaned[3:]
        # Only strip if the remaining part looks like a valid plate start (2 letters or 2 digits)
        if candidate[:2].isalpha() or (candidate[:2].isdigit() and candidate[2:4] == "BH"):
            cleaned = candidate

    return cleaned


def validate_indian_plate(plate_text: Optional[str]) -> Tuple[bool, PlateFormat]:
    """
    Validates normalized plate text against deterministic syntactic formats:
    - STANDARD_INDIAN (e.g., DL01AB1234, MH12DE1433, KA05M9999, HR26DQ5555)
    - BH_SERIES (e.g., 22BH1234AA, 23BH9876Z)
    
    Returns (is_valid: bool, format: PlateFormat).
    Note: Syntactic validity does not guarantee presence in official RTO registries.
    """
    if not plate_text or not isinstance(plate_text, str):
        return False, PlateFormat.UNKNOWN

    normalized = plate_text.strip().upper()

    if STANDARD_INDIAN_REGEX.match(normalized):
        return True, PlateFormat.STANDARD_INDIAN

    if BH_SERIES_REGEX.match(normalized):
        return True, PlateFormat.BH_SERIES

    return False, PlateFormat.UNKNOWN


class IndianPlateNormalizer:
    """
    Deterministic normalizer and syntax validator for Indian license plates.
    Keeps a strict separation between normalization and format validation.
    """

    def normalize(self, raw_text: Optional[str]) -> str:
        """Cleans and standardizes raw OCR plate string."""
        return normalize_plate_text(raw_text)

    def validate(self, plate_text: Optional[str]) -> Tuple[bool, PlateFormat]:
        """Checks if cleaned plate string matches known Indian plate grammar."""
        return validate_indian_plate(plate_text)

    def process(self, raw_text: Optional[str], confidence: float = 1.0) -> OCRResult:
        """
        Runs complete normalization and validation pipeline on raw OCR output.
        Returns an OCRResult domain model.
        """
        raw = raw_text or ""
        normalized = self.normalize(raw)
        is_valid, plate_format = self.validate(normalized)

        return OCRResult(
            raw_text=raw,
            normalized_text=normalized,
            confidence=max(0.0, min(1.0, float(confidence))),
            plate_format=plate_format,
            is_valid=is_valid
        )
