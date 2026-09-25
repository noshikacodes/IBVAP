import pytest
from ai_engine.pipeline.tracker import MultiObjectTracker
from ai_engine.pipeline.types import (
    Detection,
    BoundingBox,
    ObjectClass,
    TrackState,
)


def test_track_creation_on_first_detection():
    tracker = MultiObjectTracker(min_hits=1)
    det = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.88,
        bbox=BoundingBox(10.0, 10.0, 50.0, 100.0),
        raw_class_name="person"
    )

    active_tracks = tracker.update([det])
    assert len(active_tracks) == 1
    t = active_tracks[0]
    assert t.track_id == 1
    assert t.class_name == ObjectClass.PERSON
    assert t.state == TrackState.ACTIVE
    assert t.hits == 1
    assert len(t.trajectory) == 1
    assert t.trajectory[0] == (30.0, 55.0)


def test_persistent_ids_across_frames():
    tracker = MultiObjectTracker(iou_threshold=0.20, min_hits=1)

    # Frame 1: Person at (10, 10, 50, 100)
    det1 = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.90,
        bbox=BoundingBox(10.0, 10.0, 50.0, 100.0),
        raw_class_name="person"
    )
    tracks_f1 = tracker.update([det1])
    assert len(tracks_f1) == 1
    tid1 = tracks_f1[0].track_id

    # Frame 2: Person moved slightly to (15, 12, 55, 102)
    det2 = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.92,
        bbox=BoundingBox(15.0, 12.0, 55.0, 102.0),
        raw_class_name="person"
    )
    tracks_f2 = tracker.update([det2])
    assert len(tracks_f2) == 1
    assert tracks_f2[0].track_id == tid1  # Track ID must persist
    assert tracks_f2[0].hits == 2
    assert len(tracks_f2[0].trajectory) == 2


def test_trajectory_history_and_capping():
    max_len = 5
    tracker = MultiObjectTracker(max_trajectory_length=max_len, min_hits=1)

    # Simulate 8 consecutive moving detections
    for i in range(8):
        det = Detection(
            class_name=ObjectClass.CAR,
            confidence=0.85,
            bbox=BoundingBox(10.0 + i * 2, 20.0 + i * 2, 80.0 + i * 2, 60.0 + i * 2),
            raw_class_name="car"
        )
        tracks = tracker.update([det])
        assert len(tracks) == 1
        assert tracks[0].track_id == 1

    # Trajectory should be capped at max_len (5)
    assert len(tracks[0].trajectory) == 5


def test_track_expiration_after_max_lost_frames():
    max_lost = 3
    tracker = MultiObjectTracker(max_lost_frames=max_lost, min_hits=1)

    # Frame 1: Object detected
    det = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.80,
        bbox=BoundingBox(50, 50, 100, 150),
        raw_class_name="person"
    )
    tracks = tracker.update([det])
    assert len(tracks) == 1
    assert tracks[0].track_id == 1

    # Frame 2, 3, 4: Object disappears (missing for 3 frames, within threshold)
    for _ in range(3):
        tracks = tracker.update([])
        # Not returned as active, but maintained in internal state as LOST
        assert len(tracks) == 0

    # Frame 5: Missing for 4th frame (> max_lost_frames of 3) -> Expired and purged
    tracker.update([])
    assert len(tracker._tracks) == 0


def test_multiple_simultaneous_objects():
    tracker = MultiObjectTracker(min_hits=1)

    # Frame 1: 2 distinct objects (Person on left, Car on right)
    det_person = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.90,
        bbox=BoundingBox(10, 10, 40, 90),
        raw_class_name="person"
    )
    det_car = Detection(
        class_name=ObjectClass.CAR,
        confidence=0.85,
        bbox=BoundingBox(300, 200, 450, 280),
        raw_class_name="car"
    )

    tracks_f1 = tracker.update([det_person, det_car])
    assert len(tracks_f1) == 2
    ids_f1 = {t.track_id for t in tracks_f1}
    assert len(ids_f1) == 2

    # Frame 2: Both objects move slightly
    det_person_f2 = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.92,
        bbox=BoundingBox(14, 12, 44, 92),
        raw_class_name="person"
    )
    det_car_f2 = Detection(
        class_name=ObjectClass.CAR,
        confidence=0.88,
        bbox=BoundingBox(305, 202, 455, 282),
        raw_class_name="car"
    )

    tracks_f2 = tracker.update([det_person_f2, det_car_f2])
    assert len(tracks_f2) == 2
    ids_f2 = {t.track_id for t in tracks_f2}
    assert ids_f2 == ids_f1  # Both persistent IDs preserved


def test_empty_detections_handling():
    tracker = MultiObjectTracker()
    assert tracker.update([]) == []


def test_tracker_reset():
    tracker = MultiObjectTracker(min_hits=1)
    det = Detection(
        class_name=ObjectClass.PERSON,
        confidence=0.9,
        bbox=BoundingBox(10, 10, 50, 50),
        raw_class_name="person"
    )
    tracker.update([det])
    assert tracker.total_unique_tracks == 1

    tracker.reset()
    assert tracker.total_unique_tracks == 0
    assert len(tracker.active_tracks) == 0
    assert tracker.update([]) == []
