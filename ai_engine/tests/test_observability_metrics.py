import pytest
import time
from fastapi.testclient import TestClient

from ai_engine.telemetry.metrics import (
    MetricsRegistry,
    Counter,
    Gauge,
    Histogram,
    LabelValidator,
    metrics_registry,
)
from backend.main import app
from backend.app.schemas.alert import Alert, AlertStatus
from backend.app.schemas.incident import IncidentCreateRequest, IncidentSeverity, IncidentDispatchCreateRequest, AgencyType
from backend.app.services.alert_engine import AlertEngine
from backend.app.services.alert_repository import InMemoryAlertRepository
from backend.app.services.incident_service import IncidentService, InMemoryIncidentRepository
from backend.app.services.camera_registry import camera_registry
from ai_engine.pipeline.ptz import PTZController, SimulatedPTZDriver, PTZConfig


def test_metric_registration_and_types():
    registry = MetricsRegistry()
    assert isinstance(registry.camera_fps, Gauge)
    assert isinstance(registry.camera_frames_received, Counter)
    assert isinstance(registry.yolo_latency, Histogram)
    assert isinstance(registry.alerts_created, Counter)
    assert isinstance(registry.incidents_created, Counter)


def test_counter_monotonic_increment():
    c = Counter("test_counter", "Test description", ["camera_id"])
    c.inc(1.0, {"camera_id": "CAM_01"})
    c.inc(2.5, {"camera_id": "CAM_01"})
    assert c.get({"camera_id": "CAM_01"}) == 3.5

    with pytest.raises(ValueError):
        c.inc(-1.0, {"camera_id": "CAM_01"})


def test_gauge_set_inc_dec():
    g = Gauge("test_gauge", "Test description", ["camera_id"])
    g.set(15.0, {"camera_id": "CAM_01"})
    assert g.get({"camera_id": "CAM_01"}) == 15.0

    g.inc(5.0, {"camera_id": "CAM_01"})
    assert g.get({"camera_id": "CAM_01"}) == 20.0

    g.dec(8.0, {"camera_id": "CAM_01"})
    assert g.get({"camera_id": "CAM_01"}) == 12.0


def test_histogram_observation_and_buckets():
    h = Histogram("test_hist", "Test latency", ["op"], buckets=(0.01, 0.05, 0.1, 0.5))
    h.observe(0.02, {"op": "detect"})
    h.observe(0.08, {"op": "detect"})
    h.observe(0.40, {"op": "detect"})

    rendered = "\n".join(h.render())
    assert 'test_hist_bucket{le="0.01",op="detect"} 0' in rendered
    assert 'test_hist_bucket{le="0.05",op="detect"} 1' in rendered
    assert 'test_hist_bucket{le="0.1",op="detect"} 2' in rendered
    assert 'test_hist_bucket{le="0.5",op="detect"} 3' in rendered
    assert 'test_hist_bucket{le="+Inf",op="detect"} 3' in rendered
    assert 'test_hist_count{op="detect"} 3' in rendered

    with h.time({"op": "timed_op"}):
        time.sleep(0.01)
    rendered2 = "\n".join(h.render())
    assert 'test_hist_count{op="timed_op"} 1' in rendered2


def test_label_sanitization_and_credential_protection():
    sensitive_url = "rtsp://admin:SecretPassword123@192.168.1.100:554/live"
    sanitized = LabelValidator.sanitize_label_value(sensitive_url)
    assert "SecretPassword123" not in sanitized
    assert "***" in sanitized


def test_system_metrics_collector_cpu_fallback():
    registry = MetricsRegistry()
    registry.collect_system_metrics()
    assert registry.system_cpu_usage.get() >= 0.0
    assert registry.system_memory_usage.get() > 0.0


def test_fastapi_metrics_endpoint_and_middleware():
    client = TestClient(app)

    # Trigger a request
    res = client.get("/health")
    assert res.status_code == 200

    # Scrape root /metrics
    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "text/plain" in metrics_res.headers["content-type"]
    text = metrics_res.text

    assert "ibvap_http_requests_total" in text
    assert 'endpoint="/health"' in text
    assert "ibvap_system_cpu_usage_percent" in text
    assert "ibvap_camera_fps" in text

    # Scrape /api/v1/metrics
    v1_metrics_res = client.get("/api/v1/metrics")
    assert v1_metrics_res.status_code == 200
    assert "ibvap_http_requests_total" in v1_metrics_res.text


def test_alert_engine_metrics_integration():
    repo = InMemoryAlertRepository()
    engine = AlertEngine(repository=repo)

    from ai_engine.pipeline.types import ThreatSeverity
    alert_count_before = metrics_registry.alerts_created.get({
        "camera_id": "CAM_FENCE",
        "event_type": "intrusion",
        "severity": "critical"
    })

    from ai_engine.pipeline.spatial_rules import SpatialZoneEvent
    evt = SpatialZoneEvent(
        camera_id="CAM_FENCE",
        track_id=99,
        rule_type="intrusion",
        severity=ThreatSeverity.CRITICAL,
        position=(100.0, 150.0),
        details={"breached": True}
    )
    engine.process_event(evt)

    alert_count_after = metrics_registry.alerts_created.get({
        "camera_id": "CAM_FENCE",
        "event_type": "intrusion",
        "severity": "critical"
    })
    assert alert_count_after == alert_count_before + 1


def test_ptz_controller_metrics_integration():
    controller = PTZController()
    cfg = PTZConfig(camera_id="CAM_METRIC_TEST", ptz_enabled=True, ptz_driver="simulator")
    controller.register_camera(cfg)

    ptz_cmd_before = metrics_registry.ptz_commands.get({
        "camera_id": "CAM_METRIC_TEST",
        "driver_type": "simulator",
        "command_type": "auto_cue"
    })

    controller.process_threat_cue(
        camera_id="CAM_METRIC_TEST",
        target_bbox_or_point=(200.0, 200.0),
        severity="CRITICAL",
        event_type="intrusion",
        track_id=12
    )

    ptz_cmd_after = metrics_registry.ptz_commands.get({
        "camera_id": "CAM_METRIC_TEST",
        "driver_type": "simulator",
        "command_type": "auto_cue"
    })
    assert ptz_cmd_after == ptz_cmd_before + 1



def test_incident_service_metrics_integration():
    repo = InMemoryIncidentRepository()
    service = IncidentService(repository=repo)

    inc_before = metrics_registry.incidents_created.get({"severity": "critical"})
    inc = service.create_incident(
        IncidentCreateRequest(
            title="Telemetry Metric Test Incident",
            severity=IncidentSeverity.CRITICAL,
            sector="Sector Alpha",
            primary_camera_id="CAM_01",
            description="Testing incident creation metrics emission",
        )
    )
    inc_after = metrics_registry.incidents_created.get({"severity": "critical"})
    assert inc_after == inc_before + 1

    # Test dispatch metrics
    disp_before = metrics_registry.incident_dispatches.get({
        "agency": "quick_reaction_team_qrt",
        "status": "delivered"
    })
    service.dispatch_incident(
        incident_id=inc.incident_id,
        request=IncidentDispatchCreateRequest(
            agencies=[AgencyType.QUICK_REACTION_TEAM_QRT],
            notes="Deploy test"
        )
    )
    disp_after = metrics_registry.incident_dispatches.get({
        "agency": "quick_reaction_team_qrt",
        "status": "delivered"
    })
    assert disp_after == disp_before + 1


def test_camera_registry_health_telemetry_integration():
    health = camera_registry.get_health("CAM_01")
    assert health is not None
    assert metrics_registry.camera_fps.get({"camera_id": "CAM_01"}) == float(health["fps"])
