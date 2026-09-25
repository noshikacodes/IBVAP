import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.services.alert_repository import alert_repository


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repository():
    alert_repository.clear()
    yield
    alert_repository.clear()


def test_list_alerts_empty():
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["alerts"] == []


def test_list_alerts_with_data_and_filters():
    alert_repository.create(Alert(alert_id="alt_1", camera_id="CAM_01", severity="critical", status=AlertStatus.NEW))
    alert_repository.create(Alert(alert_id="alt_2", camera_id="CAM_02", severity="medium", status=AlertStatus.NEW))
    alert_repository.create(Alert(alert_id="alt_3", camera_id="CAM_01", severity="critical", status=AlertStatus.ACKNOWLEDGED))

    # All alerts
    resp_all = client.get("/api/v1/alerts")
    assert resp_all.status_code == 200
    assert resp_all.json()["total"] == 3

    # Filter by camera
    resp_cam = client.get("/api/v1/alerts?camera_id=CAM_01")
    assert resp_cam.status_code == 200
    assert len(resp_cam.json()["alerts"]) == 2

    # Filter by status
    resp_status = client.get("/api/v1/alerts?status=acknowledged")
    assert resp_status.status_code == 200
    assert len(resp_status.json()["alerts"]) == 1


def test_get_alert_by_id():
    alert_repository.create(Alert(alert_id="alt_target", message="Target breach"))

    response = client.get("/api/v1/alerts/alt_target")
    assert response.status_code == 200
    data = response.json()
    assert data["alert_id"] == "alt_target"
    assert data["message"] == "Target breach"

    # Non-existent alert
    resp_404 = client.get("/api/v1/alerts/alt_non_existent")
    assert resp_404.status_code == 404


def test_acknowledge_and_resolve_alert():
    alert_repository.create(Alert(alert_id="alt_action", status=AlertStatus.NEW))

    # Acknowledge
    ack_resp = client.post("/api/v1/alerts/alt_action/acknowledge", json={"operator_id": "operator_alpha"})
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "acknowledged"
    assert ack_resp.json()["acknowledged_by"] == "operator_alpha"

    # Resolve
    res_resp = client.post(
        "/api/v1/alerts/alt_action/resolve",
        json={"operator_id": "operator_alpha", "resolution_notes": "Resolved by patrol unit"}
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "resolved"
    assert res_resp.json()["resolved_by"] == "operator_alpha"
    assert res_resp.json()["metadata"]["resolution_notes"] == "Resolved by patrol unit"
