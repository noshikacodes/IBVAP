from backend.app.services.alert_engine import AlertEngine
from backend.app.services.alert_repository import InMemoryAlertRepository
from backend.app.schemas.alert import Alert, AlertStatus
from ai_engine.pipeline.face.types import FaceEvent
from ai_engine.pipeline.types import BoundingBox


def test_process_face_event_identified_person():
    repo = InMemoryAlertRepository()
    engine = AlertEngine(repository=repo, cooldown_seconds=10.0)

    event = FaceEvent(
        camera_id="CAM_PERIMETER_01",
        track_id=12,
        identity_id="PERS_SHARMA",
        display_name="Capt. Sharma",
        similarity=0.9245,
        confidence=0.9245,
        is_unknown=False,
        event_type="frs_watchlist_hit",
        severity="critical",
        bbox=BoundingBox(120, 80, 200, 190),
        position=(160.0, 135.0),
        frame_idx=15
    )

    alert = engine.process_face_event(event, current_time=100.0)
    assert alert is not None
    assert alert.severity == "critical"
    assert alert.event_type == "frs_watchlist_hit"
    assert alert.camera_id == "CAM_PERIMETER_01"
    assert alert.track_id == 12
    assert "Capt. Sharma" in alert.message
    assert alert.metadata["identity_id"] == "PERS_SHARMA"
    assert alert.metadata["display_name"] == "Capt. Sharma"
    assert alert.metadata["similarity"] == 0.9245
    assert alert.metadata["is_unknown"] is False

    # Check persistence
    stored = repo.get(alert.alert_id)
    assert stored is not None
    assert stored.metadata["identity_id"] == "PERS_SHARMA"


def test_process_face_event_unknown_person_and_deduplication():
    repo = InMemoryAlertRepository()
    engine = AlertEngine(repository=repo, cooldown_seconds=10.0)

    unk_event = FaceEvent(
        camera_id="CAM_01",
        track_id=8,
        identity_id="UNKNOWN",
        display_name="Unknown Person",
        similarity=0.412,
        confidence=0.412,
        is_unknown=True,
        event_type="frs_unregistered",
        severity="medium",
        position=(200.0, 250.0),
        frame_idx=20
    )

    # 1. First event -> generates alert
    alert1 = engine.process_face_event(unk_event, current_time=100.0)
    assert alert1 is not None
    assert alert1.severity == "medium"
    assert alert1.event_type == "frs_unregistered"
    assert alert1.metadata["is_unknown"] is True

    # 2. Duplicate within cooldown window -> suppressed (returns None)
    alert2 = engine.process_face_event(unk_event, current_time=105.0)
    assert alert2 is None

    # 3. After cooldown window expires -> generates new alert
    alert3 = engine.process_face_event(unk_event, current_time=115.0)
    assert alert3 is not None
