import pytest
from datetime import datetime, timedelta
from typing import List, Tuple

from ai_engine.pipeline.types import (
    TrackedEntity,
    BoundingBox,
    ObjectClass,
    SpatialEventType,
    ThreatSeverity,
    TripwireDirection,
)
from ai_engine.pipeline.spatial_rules import (
    PolygonZone,
    Tripwire,
    SpatialRulesEngine,
    segments_intersect,
    get_crossing_direction,
)


# Helper to create a dummy TrackedEntity
def make_track(
    track_id: int,
    center_pt: Tuple[float, float],
    class_name: ObjectClass = ObjectClass.PERSON,
    raw_class: str = "person",
    trajectory: List[Tuple[float, float]] = None,
    confidence: float = 0.90
) -> TrackedEntity:
    cx, cy = center_pt
    bbox = BoundingBox(cx - 20, cy - 40, cx + 20, cy + 40)
    traj = trajectory if trajectory is not None else [center_pt]
    return TrackedEntity(
        track_id=track_id,
        class_name=class_name,
        current_bbox=bbox,
        confidence=confidence,
        raw_class_name=raw_class,
        trajectory=traj
    )


# ----------------------------------------------------------------------
# 1. Polygon Zone Geometry & Point-in-Polygon Tests
# ----------------------------------------------------------------------
def test_polygon_zone_point_in_polygon():
    zone = PolygonZone(
        zone_id="z1",
        name="Test Zone",
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]
    )

    # Point clearly inside
    assert zone.contains_point((200.0, 200.0)) is True

    # Point clearly outside
    assert zone.contains_point((50.0, 50.0)) is False
    assert zone.contains_point((400.0, 200.0)) is False

    # Disabled zone should return False
    zone.enabled = False
    assert zone.contains_point((200.0, 200.0)) is False


def test_polygon_zone_class_filtering():
    zone = PolygonZone(
        zone_id="z_restricted",
        name="Pedestrian Restricted",
        polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        applicable_classes=["person", "human"],
        allowed_classes=[]
    )

    assert zone.is_class_applicable("person") is True
    assert zone.is_class_applicable("human") is True
    assert zone.is_class_applicable("car") is False

    # Zone with allowed class (e.g. authorized vehicles)
    zone_vehicle = PolygonZone(
        zone_id="z_authorized",
        name="Vehicle Only",
        polygon=[(0, 0), (100, 0), (100, 100), (0, 100)],
        applicable_classes=[],
        allowed_classes=["car", "bus"]
    )
    assert zone_vehicle.is_class_applicable("person") is True  # Person not allowed -> violation
    assert zone_vehicle.is_class_applicable("car") is False     # Car is allowed -> no violation


# ----------------------------------------------------------------------
# 2. State Transitions & Spam Prevention Tests
# ----------------------------------------------------------------------
def test_zone_state_transitions_no_spam():
    zone = PolygonZone(
        zone_id="z1",
        name="Restricted Zone",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)]
    )
    engine = SpatialRulesEngine(zones=[zone], fps=10.0)

    # Frame 1: Track is OUTSIDE at (50, 50)
    t1 = make_track(1, (50, 50))
    events_f1 = engine.evaluate([t1], frame_idx=1, timestamp_sec=0.1)
    assert len(events_f1) == 0

    # Frame 2: Track moves INSIDE to (200, 200) -> Triggers INTRUSION!
    t1_inside = make_track(1, (200, 200))
    events_f2 = engine.evaluate([t1_inside], frame_idx=2, timestamp_sec=0.2)
    assert len(events_f2) == 1
    assert events_f2[0].event_type == SpatialEventType.INTRUSION
    assert events_f2[0].track_id == 1
    assert events_f2[0].zone_id == "z1"

    # Frame 3: Track REMAINS INSIDE at (210, 210) -> MUST NOT SPAM INTRUSION!
    t1_inside_cont = make_track(1, (210, 210))
    events_f3 = engine.evaluate([t1_inside_cont], frame_idx=3, timestamp_sec=0.3)
    assert len(events_f3) == 0

    # Frame 4: Track EXITS zone to (400, 400) -> Triggers ZONE_EXIT
    t1_exit = make_track(1, (400, 400))
    events_f4 = engine.evaluate([t1_exit], frame_idx=4, timestamp_sec=0.4)
    assert len(events_f4) == 1
    assert events_f4[0].event_type == SpatialEventType.ZONE_EXIT

    # Frame 5: Track RE-ENTERS zone to (250, 250) -> Triggers NEW INTRUSION!
    t1_reenter = make_track(1, (250, 250))
    events_f5 = engine.evaluate([t1_reenter], frame_idx=5, timestamp_sec=0.5)
    assert len(events_f5) == 1
    assert events_f5[0].event_type == SpatialEventType.INTRUSION


# ----------------------------------------------------------------------
# 3. Tripwire Crossing & Direction Tests
# ----------------------------------------------------------------------
def test_segments_intersect_math():
    # Perpendicular intersection
    assert segments_intersect((0, 5), (10, 5), (5, 0), (5, 10)) is True

    # Parallel non-intersecting
    assert segments_intersect((0, 0), (10, 0), (0, 5), (10, 5)) is False

    # Disjoint segments
    assert segments_intersect((0, 0), (2, 2), (5, 5), (10, 10)) is False


def test_tripwire_directional_crossing():
    # Vertical tripwire from (100, 0) to (100, 200), pointing south
    # Left side (x < 100) is Side A, Right side (x > 100) is Side B
    tripwire = Tripwire(
        tripwire_id="tw1",
        name="Border Line",
        pt1=(100, 0),
        pt2=(100, 200),
        direction=TripwireDirection.A_TO_B
    )
    engine = SpatialRulesEngine(tripwires=[tripwire], tripwire_cooldown_frames=5)

    # Track crosses from left (80, 100) to right (120, 100) -> A_TO_B
    t_a_to_b = make_track(1, (120, 100), trajectory=[(80, 100), (120, 100)])
    events = engine.evaluate([t_a_to_b], frame_idx=1)
    assert len(events) == 1
    assert events[0].event_type == SpatialEventType.TRIPWIRE_CROSSING
    assert events[0].details["direction"] == "A_TO_B"

    # Reset engine and test opposite crossing with A_TO_B filter
    engine.reset()
    t_b_to_a = make_track(2, (80, 100), trajectory=[(120, 100), (80, 100)])
    events_b = engine.evaluate([t_b_to_a], frame_idx=1)
    # Should NOT trigger because tripwire is configured strictly A_TO_B
    assert len(events_b) == 0


def test_tripwire_cooldown_prevents_burst_spam():
    tripwire = Tripwire(
        tripwire_id="tw1",
        name="Fence Line",
        pt1=(0, 100),
        pt2=(200, 100),
        direction=TripwireDirection.BIDIRECTIONAL
    )
    engine = SpatialRulesEngine(tripwires=[tripwire], tripwire_cooldown_frames=5)

    # Frame 1: Crosses from (50, 80) to (50, 120)
    t1 = make_track(1, (50, 120), trajectory=[(50, 80), (50, 120)])
    ev1 = engine.evaluate([t1], frame_idx=1)
    assert len(ev1) == 1

    # Frame 2: Immediately jitters across line again within cooldown
    t2 = make_track(1, (50, 80), trajectory=[(50, 120), (50, 80)])
    ev2 = engine.evaluate([t2], frame_idx=2)
    # Cooldown suppresses duplicate burst
    assert len(ev2) == 0


# ----------------------------------------------------------------------
# 4. Loitering Rule Tests
# ----------------------------------------------------------------------
def test_loitering_duration_threshold():
    zone = PolygonZone(
        zone_id="z_loiter",
        name="Secure Vault Area",
        polygon=[(100, 100), (400, 100), (400, 400), (100, 400)],
        loitering_threshold_seconds=2.0
    )
    engine = SpatialRulesEngine(zones=[zone], fps=10.0)

    # Track enters zone at t = 0.0s (Frame 0)
    t = make_track(1, (200, 200))
    ev0 = engine.evaluate([t], frame_idx=0, timestamp_sec=0.0)
    assert len(ev0) == 1
    assert ev0[0].event_type == SpatialEventType.INTRUSION

    # Track remains inside at t = 1.0s (Frame 10, < 2.0s threshold)
    ev_under = engine.evaluate([t], frame_idx=10, timestamp_sec=1.0)
    assert len(ev_under) == 0

    # Track reaches threshold at t = 2.0s (Frame 20, == 2.0s threshold) -> Triggers LOITERING!
    ev_loiter = engine.evaluate([t], frame_idx=20, timestamp_sec=2.0)
    assert len(ev_loiter) == 1
    assert ev_loiter[0].event_type == SpatialEventType.LOITERING
    assert ev_loiter[0].details["threshold_seconds"] == 2.0

    # Track stays inside further at t = 3.5s -> MUST NOT SPAM LOITERING!
    ev_after = engine.evaluate([t], frame_idx=35, timestamp_sec=3.5)
    assert len(ev_after) == 0


# ----------------------------------------------------------------------
# 5. Multi-Object & Independent Zone State Tests
# ----------------------------------------------------------------------
def test_multiple_simultaneous_tracks_independent_rules():
    zone = PolygonZone(
        zone_id="z_restricted",
        name="Restricted Zone",
        polygon=[(0, 0), (200, 0), (200, 200), (0, 200)]
    )
    engine = SpatialRulesEngine(zones=[zone])

    # Track 1 is inside, Track 2 is outside
    t1 = make_track(1, (100, 100))
    t2 = make_track(2, (500, 500))

    events = engine.evaluate([t1, t2], frame_idx=1)
    assert len(events) == 1
    assert events[0].track_id == 1
    assert events[0].event_type == SpatialEventType.INTRUSION
