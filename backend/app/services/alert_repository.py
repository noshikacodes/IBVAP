from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict
from collections import OrderedDict
import threading

from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.core.config import settings


class BaseAlertRepository(ABC):
    """Abstract interface for storing and retrieving security alerts."""

    @abstractmethod
    def create(self, alert: Alert) -> Alert:
        """Stores a new alert."""
        pass

    @abstractmethod
    def get(self, alert_id: str) -> Optional[Alert]:
        """Retrieves an alert by ID."""
        pass

    @abstractmethod
    def list(
        self,
        camera_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Alert]:
        """Lists alerts with optional filtering and pagination."""
        pass

    @abstractmethod
    def acknowledge(self, alert_id: str, operator_id: str = "operator") -> Optional[Alert]:
        """Marks an alert as acknowledged."""
        pass

    @abstractmethod
    def resolve(self, alert_id: str, operator_id: str = "operator", notes: Optional[str] = None) -> Optional[Alert]:
        """Marks an alert as resolved."""
        pass

    @abstractmethod
    def count(self, status: Optional[AlertStatus] = None, camera_id: Optional[str] = None) -> int:
        """Returns the total number of alerts matching optional filters."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears all stored alerts."""
        pass


class InMemoryAlertRepository(BaseAlertRepository):
    """
    Thread-safe in-memory alert repository bounded by max_capacity.
    Can be replaced seamlessly with a PostgreSQL / TimescaleDB repository in future phases.
    """

    def __init__(self, max_capacity: int = 1000):
        self.max_capacity = max_capacity
        self._alerts: OrderedDict[str, Alert] = OrderedDict()
        self._lock = threading.Lock()

    def create(self, alert: Alert) -> Alert:
        with self._lock:
            # If at max capacity, evict the oldest alert (FIFO)
            if len(self._alerts) >= self.max_capacity and alert.alert_id not in self._alerts:
                self._alerts.popitem(last=False)
            self._alerts[alert.alert_id] = alert
            return alert

    def get(self, alert_id: str) -> Optional[Alert]:
        with self._lock:
            return self._alerts.get(alert_id)

    def list(
        self,
        camera_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[AlertStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Alert]:
        with self._lock:
            # Alerts returned in reverse chronological order (newest first)
            all_alerts = list(reversed(self._alerts.values()))

            filtered = []
            for alt in all_alerts:
                if camera_id and alt.camera_id != camera_id:
                    continue
                if severity and alt.severity.lower() != severity.lower():
                    continue
                if status and alt.status != status:
                    continue
                filtered.append(alt)

            return filtered[offset : offset + limit]

    def acknowledge(self, alert_id: str, operator_id: str = "operator") -> Optional[Alert]:
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = operator_id
            return alert

    def resolve(self, alert_id: str, operator_id: str = "operator", notes: Optional[str] = None) -> Optional[Alert]:
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = operator_id
            if notes:
                alert.metadata["resolution_notes"] = notes
            return alert

    def count(self, status: Optional[AlertStatus] = None, camera_id: Optional[str] = None) -> int:
        with self._lock:
            count = 0
            for alt in self._alerts.values():
                if status and alt.status != status:
                    continue
                if camera_id and alt.camera_id != camera_id:
                    continue
                count += 1
            return count

    def clear(self) -> None:
        with self._lock:
            self._alerts.clear()


# Global singleton instance
alert_repository = InMemoryAlertRepository(max_capacity=settings.MAX_IN_MEMORY_ALERTS)
