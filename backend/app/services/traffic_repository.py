import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple


DB_DIR = os.path.abspath("data")
DEFAULT_DB_PATH = os.path.join(DB_DIR, "traffic_analytics.db")


class TrafficAnalyticsRepository:
    """
    Thread-safe SQLite persistent repository for vehicle crossing events and
    aggregated time-series traffic counts.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initializes tables and indexes with idempotency constraints."""
        with self._lock, self._get_connection() as conn:
            # 1. Individual unique crossing events
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traffic_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    track_id INTEGER NOT NULL,
                    object_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'LINE_CROSSING',
                    confidence REAL DEFAULT 0.0,
                    bbox_x1 REAL DEFAULT 0.0,
                    bbox_y1 REAL DEFAULT 0.0,
                    bbox_x2 REAL DEFAULT 0.0,
                    bbox_y2 REAL DEFAULT 0.0,
                    snapshot_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(camera_id, track_id, event_type)
                );
            """)

            # 2. Aggregated time-series counts by 1-minute bucket
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traffic_counts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    time_bucket TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(camera_id, time_bucket, object_type)
                );
            """)

            # Indexes for high-performance dashboard queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_camera_ts ON traffic_events(camera_id, timestamp);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_camera_track ON traffic_events(camera_id, track_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_counts_camera_bucket ON traffic_counts(camera_id, time_bucket);")
            conn.commit()

    def record_event(self, event_dict: Dict[str, Any]) -> bool:
        """
        Records a crossing event into SQLite.
        Returns True if inserted (new unique track), False if duplicate/ignored.
        """
        if hasattr(event_dict, "to_dict"):
            event_dict = event_dict.to_dict()

        camera_id = str(event_dict.get("camera_id", "CAM_SEJONG_95366"))
        track_id = int(event_dict.get("track_id", 0))
        object_type = str(event_dict.get("object_type", "car")).lower()
        timestamp = str(event_dict.get("timestamp") or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
        direction = str(event_dict.get("direction", "OUT")).upper()
        event_type = str(event_dict.get("event_type", "LINE_CROSSING"))
        confidence = float(event_dict.get("confidence", 0.0))
        b_x1 = float(event_dict.get("bbox_x1", 0.0))
        b_y1 = float(event_dict.get("bbox_y1", 0.0))
        b_x2 = float(event_dict.get("bbox_x2", 0.0))
        b_y2 = float(event_dict.get("bbox_y2", 0.0))
        snapshot_path = event_dict.get("snapshot_path")

        # 1-minute bucket (e.g. 2026-09-01T15:43:00)
        clean_ts = timestamp.replace("Z", "")
        time_bucket = clean_ts[:16] + ":00" if len(clean_ts) >= 16 else clean_ts

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO traffic_events (
                    camera_id, track_id, object_type, timestamp, direction,
                    event_type, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2, snapshot_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                camera_id, track_id, object_type, timestamp, direction,
                event_type, confidence, b_x1, b_y1, b_x2, b_y2, snapshot_path
            ))

            if cursor.rowcount > 0:
                # Increment aggregated time bucket
                cursor.execute("""
                    INSERT INTO traffic_counts (camera_id, time_bucket, object_type, count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(camera_id, time_bucket, object_type)
                    DO UPDATE SET count = count + 1
                """, (camera_id, time_bucket, object_type))
                conn.commit()
                return True

            return False

    def get_analytics_summary(self, camera_id: str) -> Dict[str, Any]:
        """
        Calculates today's cumulative totals, vehicles in the last hour,
        and vehicles in the last 10 minutes from SQLite records.
        """
        now = datetime.utcnow()
        today_prefix = now.strftime("%Y-%m-%d")
        one_hour_ago = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ten_min_ago = (now - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

        totals_today: Dict[str, int] = {
            "car": 0,
            "bus": 0,
            "truck": 0,
            "motorcycle": 0,
            "person": 0,
        }

        with self._lock, self._get_connection() as conn:
            # 1. Cumulative totals today by class
            rows = conn.execute("""
                SELECT object_type, COUNT(*) as cnt
                FROM traffic_events
                WHERE camera_id = ? AND timestamp LIKE ?
                GROUP BY object_type
            """, (camera_id, f"{today_prefix}%")).fetchall()

            for r in rows:
                obj_type = r["object_type"].lower()
                totals_today[obj_type] = r["cnt"]

            # 2. Last hour count
            row_hour = conn.execute("""
                SELECT COUNT(*) as cnt
                FROM traffic_events
                WHERE camera_id = ? AND timestamp >= ?
            """, (camera_id, one_hour_ago)).fetchone()
            last_hour_count = row_hour["cnt"] if row_hour else 0

            # 3. Last 10 minutes count
            row_10m = conn.execute("""
                SELECT COUNT(*) as cnt
                FROM traffic_events
                WHERE camera_id = ? AND timestamp >= ?
            """, (camera_id, ten_min_ago)).fetchone()
            last_10m_count = row_10m["cnt"] if row_10m else 0

            # 4. Total all-time recorded
            row_all = conn.execute("""
                SELECT COUNT(*) as cnt FROM traffic_events WHERE camera_id = ?
            """, (camera_id,)).fetchone()
            total_all_time = row_all["cnt"] if row_all else 0

        total_vehicles_today = (
            totals_today.get("car", 0) +
            totals_today.get("bus", 0) +
            totals_today.get("truck", 0) +
            totals_today.get("motorcycle", 0)
        )

        return {
            "camera_id": camera_id,
            "today_totals": totals_today,
            "total_today": sum(totals_today.values()),
            "total_vehicles_today": total_vehicles_today,
            "total_persons_today": totals_today.get("person", 0),
            "last_hour": last_hour_count,
            "last_10_minutes": last_10m_count,
            "total_all_time": total_all_time,
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def get_recent_events(
        self,
        camera_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Returns ordered list of recent crossing events."""
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("""
                SELECT id, camera_id, track_id, object_type, timestamp, direction,
                       event_type, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2, snapshot_path
                FROM traffic_events
                WHERE camera_id = ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, (camera_id, limit, offset)).fetchall()

            return [dict(r) for r in rows]

    def get_time_series_summary(
        self,
        camera_id: str,
        limit: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Returns chronological aggregated traffic volume time buckets for chart rendering.
        Groups into recent time slots.
        """
        with self._lock, self._get_connection() as conn:
            rows = conn.execute("""
                SELECT time_bucket, object_type, SUM(count) as total_count
                FROM traffic_counts
                WHERE camera_id = ?
                GROUP BY time_bucket, object_type
                ORDER BY time_bucket DESC
                LIMIT ?
            """, (camera_id, limit * 5)).fetchall()

            # Group by bucket
            buckets: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                tb = r["time_bucket"]
                if tb not in buckets:
                    # Format e.g. 15:40
                    label = tb[11:16] if len(tb) >= 16 else tb
                    buckets[tb] = {
                        "time_bucket": tb,
                        "time_label": label,
                        "vehicles": 0,
                        "breakdown": {}
                    }
                cnt = r["total_count"]
                obj = r["object_type"]
                buckets[tb]["breakdown"][obj] = cnt
                buckets[tb]["vehicles"] += cnt

            sorted_list = sorted(buckets.values(), key=lambda x: x["time_bucket"])
            return sorted_list[-limit:] if len(sorted_list) > limit else sorted_list

    def clear(self, camera_id: Optional[str] = None) -> None:
        """Clears records (useful for test teardown)."""
        with self._lock, self._get_connection() as conn:
            if camera_id:
                conn.execute("DELETE FROM traffic_events WHERE camera_id = ?", (camera_id,))
                conn.execute("DELETE FROM traffic_counts WHERE camera_id = ?", (camera_id,))
            else:
                conn.execute("DELETE FROM traffic_events;")
                conn.execute("DELETE FROM traffic_counts;")
            conn.commit()


# Singleton repository instance
traffic_repository = TrafficAnalyticsRepository()
