import pytest
from ai_engine.pipeline.types import (
    ObjectClass,
    ThreatSeverity,
    BoundingBox,
    Detection,
    TrackedEntity,
    SpatialZoneEvent,
)
from ai_engine.pipeline.interfaces import BaseDetector, BaseTracker, BaseRulesEngine


def test_bounding_box_calculations():
    bbox = BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=300.0)
    assert bbox.center == (150.0, 200.0)
    assert bbox.bottom_center == (150.0, 300.0)


def test_detection_instantiation():
    bbox = BoundingBox(x1=10.0, y1=20.0, x2=50.0, y2=100.0)
    det = Detection(
        class_name=ObjectClass.HUMAN,
        confidence=0.92,
        bbox=bbox,
        track_id=1
    )
    assert det.class_name == ObjectClass.HUMAN
    assert det.confidence == 0.92
    assert det.track_id == 1


def test_abstract_interfaces_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseDetector()  # type: ignore

    with pytest.raises(TypeError):
        BaseTracker()  # type: ignore

    with pytest.raises(TypeError):
        BaseRulesEngine()  # type: ignore
