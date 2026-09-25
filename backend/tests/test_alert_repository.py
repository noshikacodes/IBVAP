import pytest
from datetime import datetime
from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.services.alert_repository import InMemoryAlertRepository


def test_repository_crud():
    repo = InMemoryAlertRepository(max_capacity=10)

    alert = Alert(
        alert_id="alt_test_01",
        camera_id="CAM_EAST",
        event_type="intrusion",
        severity="critical",
        message="Intrusion on CAM_EAST"
    )

    created = repo.create(alert)
    assert created.alert_id == "alt_test_01"

    fetched = repo.get("alt_test_01")
    assert fetched is not None
    assert fetched.message == "Intrusion on CAM_EAST"

    # Non-existent ID returns None
    assert repo.get("alt_non_existent") is None


def test_repository_filtering_and_pagination():
    repo = InMemoryAlertRepository(max_capacity=50)

    for i in range(10):
        repo.create(Alert(
            alert_id=f"alt_{i}",
            camera_id="CAM_A" if i < 6 else "CAM_B",
            severity="critical" if i % 2 == 0 else "medium",
            status=AlertStatus.NEW if i < 8 else AlertStatus.ACKNOWLEDGED
        ))

    # Total count
    assert repo.count() == 10
    assert repo.count(camera_id="CAM_A") == 6
    assert repo.count(status=AlertStatus.ACKNOWLEDGED) == 2

    # Filtered listing
    cam_a_alerts = repo.list(camera_id="CAM_A")
    assert len(cam_a_alerts) == 6

    critical_alerts = repo.list(severity="critical")
    assert len(critical_alerts) == 5

    # Pagination
    page_1 = repo.list(limit=3, offset=0)
    page_2 = repo.list(limit=3, offset=3)
    assert len(page_1) == 3
    assert len(page_2) == 3
    assert page_1[0].alert_id != page_2[0].alert_id


def test_repository_acknowledge_and_resolve():
    repo = InMemoryAlertRepository()

    alert = Alert(alert_id="alt_flow", status=AlertStatus.NEW)
    repo.create(alert)

    # Acknowledge
    ack = repo.acknowledge("alt_flow", operator_id="officer_smith")
    assert ack is not None
    assert ack.status == AlertStatus.ACKNOWLEDGED
    assert ack.acknowledged_by == "officer_smith"
    assert ack.acknowledged_at is not None

    # Resolve
    res = repo.resolve("alt_flow", operator_id="officer_smith", notes="False alarm: wildlife")
    assert res is not None
    assert res.status == AlertStatus.RESOLVED
    assert res.resolved_by == "officer_smith"
    assert res.resolved_at is not None
    assert res.metadata["resolution_notes"] == "False alarm: wildlife"


def test_repository_fifo_eviction():
    repo = InMemoryAlertRepository(max_capacity=3)

    repo.create(Alert(alert_id="alt_1"))
    repo.create(Alert(alert_id="alt_2"))
    repo.create(Alert(alert_id="alt_3"))
    assert repo.count() == 3

    # Add 4th -> alt_1 should be evicted
    repo.create(Alert(alert_id="alt_4"))
    assert repo.count() == 3
    assert repo.get("alt_1") is None
    assert repo.get("alt_4") is not None
