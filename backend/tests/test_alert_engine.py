import pytest
from datetime import datetime
from ai_engine.pipeline.types import (
    SpatialZoneEvent,
    SpatialEventType,
    ObjectClass,
    ThreatSeverity,
)
from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.services.alert_engine import AlertEngine
from backend.app.services.alert_repository import InMemoryAlertRepository
from backend.app.services.priority import get_alert_severity


def test_priority_policy_mapping():
    assert get_alert_severity("intrusion") == "critical"
    assert get_alert_severity("tripwire_crossing") == "high"
    assert get_alert_severity("loitering") == "medium"
    assert get_alert_severity("zone_exit") == "low"
    assert get_alert_severity("unknown_new_event") == "medium"


def test_event_to_alert_conversion():
    repo = InMemoryAlertRepository()
    engine = AlertEngine(repository=repo, publish_to_redis=False, cooldown_seconds=10.0)

    event = SpatialZoneEvent(
        camera_id="CAM_NORTH_01",
        track_id=7,
        rule_type="intrusion",
        event_type=SpatialEventType.INTRUSION,
        severity=ThreatSeverity.HIGH,
        object_class=ObjectClass.PERSON,
        zone_id="zone_vault",
        confidence=0.91,
        position=(150.0, 250.0),
        details={"zone_name": "Vault Perimeter", "message": "Person #7 breached Vault Perimeter"}
    )

    alert = engine.process_event(event, current_time=100.0)
    assert alert is not None
    assert alert.event_id == event.event_id
    assert alert.event_type == "intrusion"
    assert alert.severity == "critical"
    assert alert.camera_id == "CAM_NORTH_01"
    assert alert.track_id == 7
    assert alert.object_class == "person"
    assert alert.zone_id == "zone_vault"
    assert alert.position == (150.0, 250.0)
    assert alert.status == AlertStatus.NEW
    assert "Vault Perimeter" in alert.message

    # Verify alert was saved in repository
    saved = repo.get(alert.alert_id)
    assert saved is not None
    assert saved.alert_id == alert.alert_id


def test_alert_deduplication_and_cooldown():
    repo = InMemoryAlertRepository()
    engine = AlertEngine(repository=repo, publish_to_redis=False, cooldown_seconds=20.0)

    event = SpatialZoneEvent(
        camera_id="CAM_01",
        track_id=12,
        rule_type="intrusion",
        zone_id="zone_gate"
    )

    # First event at t = 100s -> Produced!
    a1 = engine.process_event(event, current_time=100.0)
    assert a1 is not None

    # Duplicate event at t = 110s (< 20s cooldown) -> Suppressed!
    a2 = engine.process_event(event, current_time=110.0)
    assert a2 is None

    # Event at t = 125s (> 20s cooldown) -> Produced!
    a3 = engine.process_event(event, current_time=125.0)
    assert a3 is not None
    assert a3.alert_id != a1.alert_id


def test_independent_deduplication_keys():
    repo = InMemoryAlertRepository()
    engine = AlertEngine(repository=repo, publish_to_redis=False, cooldown_seconds=30.0)

    # Event for Track #1 on Camera A
    e1 = SpatialZoneEvent(camera_id="CAM_A", track_id=1, rule_type="intrusion", zone_id="z1")
    # Event for Track #2 on Camera A (different track)
    e2 = SpatialZoneEvent(camera_id="CAM_A", track_id=2, rule_type="intrusion", zone_id="z1")
    # Event for Track #1 on Camera B (different camera)
    e3 = SpatialZoneEvent(camera_id="CAM_B", track_id=1, rule_type="intrusion", zone_id="z1")
    # Event for Track #1 in Zone 2 (different zone)
    e4 = SpatialZoneEvent(camera_id="CAM_A", track_id=1, rule_type="intrusion", zone_id="z2")

    a1 = engine.process_event(e1, current_time=100.0)
    a2 = engine.process_event(e2, current_time=100.0)
    a3 = engine.process_event(e3, current_time=100.0)
    a4 = engine.process_event(e4, current_time=100.0)

    assert all(a is not None for a in (a1, a2, a3, a4))
    assert len({a.alert_id for a in (a1, a2, a3, a4)}) == 4
