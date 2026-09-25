from ai_engine.pipeline.types import (
    ObjectClass,
    BoundingBox,
    Detection,
    TrackedEntity,
    ThreatSeverity
)


def test_bounding_box_geometry():
    box = BoundingBox(10.0, 20.0, 110.0, 220.0)
    assert box.width == 100.0
    assert box.height == 200.0
    assert box.area == 20000.0
    assert box.center == (60.0, 120.0)
    assert box.bottom_center == (60.0, 220.0)
    assert box.as_int_xyxy() == (10, 20, 110, 220)
    assert box.as_xywh() == (10.0, 20.0, 100.0, 200.0)


def test_object_class_mapping():
    assert ObjectClass.from_string("person") == ObjectClass.PERSON
    assert ObjectClass.from_string("PEDESTRIAN") == ObjectClass.HUMAN
    assert ObjectClass.from_string("car") == ObjectClass.CAR
    assert ObjectClass.from_string("Automobile") == ObjectClass.CAR
    assert ObjectClass.from_string("truck") == ObjectClass.TRUCK
    assert ObjectClass.from_string("motorcycle") == ObjectClass.MOTORCYCLE
    assert ObjectClass.from_string("bike") == ObjectClass.MOTORCYCLE
    assert ObjectClass.from_string("unrecognized_alien") == ObjectClass.UNKNOWN


def test_detection_creation_and_defaults():
    box = BoundingBox.from_xyxy(5, 5, 25, 35)
    det = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.88,
        bbox=box
    )
    assert det.raw_class_name == "person"
    assert det.confidence == 0.88
    assert det.track_id is None
    assert det.extra_metadata == {}
