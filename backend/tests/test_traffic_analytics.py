import os
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.services.traffic_repository import TrafficAnalyticsRepository, traffic_repository


@pytest.fixture
def test_repo(tmp_path):
    """Fixture providing an isolated SQLite repository for testing."""
    db_path = str(tmp_path / "test_traffic.db")
    repo = TrafficAnalyticsRepository(db_path=db_path)
    return repo


class TestTrafficAnalyticsRepository:

    def test_record_unique_event_and_aggregation(self, test_repo):
        """Recording a unique event updates both events log and 1-minute time-series bucket."""
        now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        event = {
            "camera_id": "CAM_SEJONG_95366",
            "track_id": 47,
            "object_type": "car",
            "timestamp": now_str,
            "direction": "IN",
            "event_type": "LINE_CROSSING",
            "confidence": 0.92,
            "bbox_x1": 100.0,
            "bbox_y1": 200.0,
            "bbox_x2": 200.0,
            "bbox_y2": 300.0,
        }

        # First insert succeeds
        is_new = test_repo.record_event(event)
        assert is_new is True

        # Duplicate insert of same track ID and event type is ignored
        is_dup = test_repo.record_event(event)
        assert is_dup is False

        # Summary reflects exactly 1 car
        summary = test_repo.get_analytics_summary("CAM_SEJONG_95366")
        assert summary["today_totals"]["car"] == 1
        assert summary["total_today"] == 1
        assert summary["total_vehicles_today"] == 1
        assert summary["last_hour"] == 1
        assert summary["last_10_minutes"] == 1

    def test_multi_vehicle_time_series(self, test_repo):
        """Verify multiple vehicles across different classes and time buckets."""
        now = datetime.utcnow()
        vehicles = [
            (10, "car", "IN", now),
            (11, "bus", "OUT", now),
            (12, "truck", "IN", now - timedelta(minutes=5)),
            (13, "motorcycle", "OUT", now - timedelta(minutes=20)),
            (14, "person", "IN", now - timedelta(minutes=2)),
        ]

        for tid, otype, dirn, ts in vehicles:
            test_repo.record_event({
                "camera_id": "CAM_TEST",
                "track_id": tid,
                "object_type": otype,
                "direction": dirn,
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "confidence": 0.88,
            })

        summary = test_repo.get_analytics_summary("CAM_TEST")
        assert summary["today_totals"]["car"] == 1
        assert summary["today_totals"]["bus"] == 1
        assert summary["today_totals"]["truck"] == 1
        assert summary["today_totals"]["motorcycle"] == 1
        assert summary["today_totals"]["person"] == 1
        assert summary["total_vehicles_today"] == 4
        assert summary["total_persons_today"] == 1

        # Check time-series intervals
        intervals = test_repo.get_time_series_summary("CAM_TEST", limit=10)
        assert len(intervals) >= 1
        total_in_intervals = sum(item["vehicles"] for item in intervals)
        assert total_in_intervals == 5

    def test_recent_events_ordering(self, test_repo):
        """Recent events should return in reverse chronological order (newest first)."""
        now = datetime.utcnow()
        for i in range(1, 6):
            test_repo.record_event({
                "camera_id": "CAM_TEST",
                "track_id": i,
                "object_type": "car",
                "timestamp": (now + timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

        events = test_repo.get_recent_events("CAM_TEST", limit=3)
        assert len(events) == 3
        # ID 5 is the most recent
        assert events[0]["track_id"] == 5
        assert events[1]["track_id"] == 4
        assert events[2]["track_id"] == 3


class TestTrafficEndpoints:

    @pytest.fixture(autouse=True)
    def setup_client(self):
        traffic_repository.clear("CAM_API_TEST")
        self.client = TestClient(app)
        yield
        traffic_repository.clear("CAM_API_TEST")

    def test_traffic_api_flow(self):
        """End-to-end test of POST crossing event and GET analytics."""
        camera_id = "CAM_API_TEST"
        now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. POST crossing event
        post_res = self.client.post(
            f"/api/v1/cameras/{camera_id}/traffic-events",
            json={
                "track_id": 999,
                "object_type": "truck",
                "direction": "IN",
                "timestamp": now_str,
                "confidence": 0.95,
                "bbox_x1": 50,
                "bbox_y1": 50,
                "bbox_x2": 150,
                "bbox_y2": 150
            }
        )
        assert post_res.status_code == 200
        assert post_res.json()["status"] == "recorded"

        # 2. GET analytics
        get_res = self.client.get(f"/api/v1/cameras/{camera_id}/traffic-analytics")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["camera_id"] == camera_id
        assert data["today_totals"]["truck"] >= 1
        assert "live_now" in data
        assert "counting_line" in data

        # 3. GET events feed
        events_res = self.client.get(f"/api/v1/cameras/{camera_id}/traffic-events")
        assert events_res.status_code == 200
        evts_data = events_res.json()
        assert evts_data["total"] >= 1
        assert evts_data["events"][0]["track_id"] == 999
        assert evts_data["events"][0]["object_type"] == "truck"

        # 4. GET time-series summary
        summary_res = self.client.get(f"/api/v1/cameras/{camera_id}/traffic-summary")
        assert summary_res.status_code == 200
        assert "intervals" in summary_res.json()
