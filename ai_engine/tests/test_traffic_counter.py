import pytest
import numpy as np
from datetime import datetime

from ai_engine.pipeline.types import TrackedEntity, ObjectClass, BoundingBox, TrackState
from ai_engine.pipeline.traffic_counter import (
    TrafficCountingEngine,
    TrafficCrossingEvent,
    normalize_traffic_class,
)


def _make_track(
    track_id: int,
    class_name: ObjectClass,
    x: float,
    y: float,
    w: float = 60.0,
    h: float = 40.0,
    conf: float = 0.85
) -> TrackedEntity:
    """Helper to create a synthetic tracked entity with bottom-center at (x, y)."""
    x1 = x - w / 2.0
    x2 = x + w / 2.0
    y1 = y - h
    y2 = y
    box = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
    return TrackedEntity(
        track_id=track_id,
        class_name=class_name,
        current_bbox=box,
        confidence=conf,
        state=TrackState.ACTIVE,
        trajectory=[(x, y)]
    )


class TestTrafficCountingEngine:

    def test_normalize_traffic_class(self):
        assert normalize_traffic_class("car") == "car"
        assert normalize_traffic_class("automobile") == "car"
        assert normalize_traffic_class("bus") == "bus"
        assert normalize_traffic_class("truck") == "truck"
        assert normalize_traffic_class("trailer") == "truck"
        assert normalize_traffic_class("motorcycle") == "motorcycle"
        assert normalize_traffic_class("bike") == "motorcycle"
        assert normalize_traffic_class("person") == "person"
        assert normalize_traffic_class("human") == "person"

    def test_single_crossing_event_triggered(self):
        """A vehicle moving across the line triggers exactly one crossing event."""
        engine = TrafficCountingEngine(
            camera_id="CAM_TEST",
            line_pt1=(0.0, 300.0),
            line_pt2=(500.0, 300.0),
            save_evidence=False
        )

        # Frame 1: Vehicle above the line (y=250)
        t1 = _make_track(track_id=1, class_name=ObjectClass.CAR, x=200.0, y=250.0)
        evts_1 = engine.process_tracks([t1], frame_idx=1)
        assert len(evts_1) == 0
        assert engine.counted_totals["car"] == 0

        # Frame 2: Vehicle crosses the line to y=350 (downwards / OUT)
        t2 = _make_track(track_id=1, class_name=ObjectClass.CAR, x=200.0, y=350.0)
        evts_2 = engine.process_tracks([t2], frame_idx=2)
        assert len(evts_2) == 1
        assert evts_2[0].track_id == 1
        assert evts_2[0].object_type == "car"
        assert evts_2[0].direction == "OUT"
        assert engine.counted_totals["car"] == 1

    def test_unique_counting_invariant_100_frames(self):
        """The same vehicle tracked over 100 frames must only ever increment the count by 1."""
        engine = TrafficCountingEngine(
            camera_id="CAM_TEST",
            line_pt1=(0.0, 300.0),
            line_pt2=(500.0, 300.0),
            save_evidence=False
        )

        total_crossing_events = 0
        # Simulate 100 frames of Track #17 moving from y=200 to y=500
        for f in range(1, 101):
            y = 200.0 + (f * 3.0)  # crosses y=300 around frame 34
            track = _make_track(track_id=17, class_name=ObjectClass.BUS, x=250.0, y=y)
            evts = engine.process_tracks([track], frame_idx=f)
            total_crossing_events += len(evts)

        # Invariant checks
        assert total_crossing_events == 1, "Must generate exactly 1 crossing event"
        assert engine.counted_totals["bus"] == 1, "Bus count must be exactly 1, not 100!"
        assert sum(engine.counted_totals.values()) == 1

    def test_duplicate_prevention_on_oscillation(self):
        """A vehicle oscillating back and forth across the line is counted only once."""
        engine = TrafficCountingEngine(
            camera_id="CAM_TEST",
            line_pt1=(0.0, 300.0),
            line_pt2=(500.0, 300.0),
            save_evidence=False
        )

        # First crossing (above to below)
        t_a = _make_track(track_id=42, class_name=ObjectClass.TRUCK, x=200.0, y=280.0)
        engine.process_tracks([t_a], frame_idx=1)
        t_b = _make_track(track_id=42, class_name=ObjectClass.TRUCK, x=200.0, y=320.0)
        evts_first = engine.process_tracks([t_b], frame_idx=2)
        assert len(evts_first) == 1
        assert engine.counted_totals["truck"] == 1

        # Second crossing (oscillates back above)
        t_c = _make_track(track_id=42, class_name=ObjectClass.TRUCK, x=200.0, y=280.0)
        evts_back = engine.process_tracks([t_c], frame_idx=3)
        assert len(evts_back) == 0, "Must not count again on reverse crossing"

        # Third crossing (oscillates forward below again)
        t_d = _make_track(track_id=42, class_name=ObjectClass.TRUCK, x=200.0, y=320.0)
        evts_re_cross = engine.process_tracks([t_d], frame_idx=4)
        assert len(evts_re_cross) == 0, "Must not count again on repeat oscillation"
        assert engine.counted_totals["truck"] == 1

    def test_direction_detection_in_vs_out(self):
        """Test receding (IN) vs approaching (OUT) direction calculations."""
        engine = TrafficCountingEngine(
            camera_id="CAM_TEST",
            line_pt1=(0.0, 300.0),
            line_pt2=(500.0, 300.0),
            save_evidence=False
        )

        # Track 1: Moving upwards (receding into tunnel: y=350 -> y=250)
        t1_pre = _make_track(track_id=101, class_name=ObjectClass.CAR, x=150.0, y=350.0)
        engine.process_tracks([t1_pre], frame_idx=1)
        t1_post = _make_track(track_id=101, class_name=ObjectClass.CAR, x=150.0, y=250.0)
        evts_in = engine.process_tracks([t1_post], frame_idx=2)
        assert len(evts_in) == 1
        assert evts_in[0].direction == "IN"

        # Track 2: Moving downwards (approaching camera: y=250 -> y=350)
        t2_pre = _make_track(track_id=102, class_name=ObjectClass.MOTORCYCLE, x=350.0, y=250.0)
        engine.process_tracks([t2_pre], frame_idx=3)
        t2_post = _make_track(track_id=102, class_name=ObjectClass.MOTORCYCLE, x=350.0, y=350.0)
        evts_out = engine.process_tracks([t2_post], frame_idx=4)
        assert len(evts_out) == 1
        assert evts_out[0].direction == "OUT"

    def test_multi_class_separation(self):
        """Verify distinct counters for cars, buses, trucks, motorcycles, persons."""
        engine = TrafficCountingEngine(save_evidence=False)

        classes = [
            (1, ObjectClass.CAR, "car"),
            (2, ObjectClass.BUS, "bus"),
            (3, ObjectClass.TRUCK, "truck"),
            (4, ObjectClass.MOTORCYCLE, "motorcycle"),
            (5, ObjectClass.PERSON, "person"),
        ]

        # Pre-line frame (y=200)
        pre_tracks = [_make_track(tid, cls, x=100.0 * tid, y=200.0) for tid, cls, _ in classes]
        engine.process_tracks(pre_tracks, frame_idx=1)

        # Post-line frame (y=400)
        post_tracks = [_make_track(tid, cls, x=100.0 * tid, y=400.0) for tid, cls, _ in classes]
        evts = engine.process_tracks(post_tracks, frame_idx=2)

        assert len(evts) == 5
        assert engine.counted_totals["car"] == 1
        assert engine.counted_totals["bus"] == 1
        assert engine.counted_totals["truck"] == 1
        assert engine.counted_totals["motorcycle"] == 1
        assert engine.counted_totals["person"] == 1
        assert sum(engine.counted_totals.values()) == 5

    def test_stale_track_cleanup(self):
        """Tracks not updated for > timeout frames are evicted from internal memory."""
        engine = TrafficCountingEngine(stale_track_timeout_frames=10, save_evidence=False)

        t = _make_track(track_id=99, class_name=ObjectClass.CAR, x=200.0, y=200.0)
        engine.process_tracks([t], frame_idx=1)
        assert 99 in engine._track_last_position

        # Frame 30 (more than 10 frames after frame 1)
        engine.process_tracks([], frame_idx=30)
        assert 99 not in engine._track_last_position

    def test_telemetry_snapshot_structure(self):
        """Telemetry snapshot contains all required keys for frontend dashboard."""
        engine = TrafficCountingEngine(camera_id="CAM_TEST", save_evidence=False)
        active = [
            _make_track(track_id=1, class_name=ObjectClass.CAR, x=100.0, y=200.0),
            _make_track(track_id=2, class_name=ObjectClass.BUS, x=200.0, y=200.0),
        ]
        snap = engine.get_telemetry_snapshot(active)

        assert "live_now" in snap
        assert snap["live_now"]["car"] == 1
        assert snap["live_now"]["bus"] == 1
        assert snap["live_total"] == 2
        assert "counted_totals" in snap
        assert "counting_line" in snap
        assert len(snap["counting_line"]) == 2
