from fastapi import APIRouter, Response
from ai_engine.telemetry.metrics import metrics_registry

router = APIRouter()


@router.get(
    "",
    summary="Prometheus Metrics Exposition",
    description="Exposes real-time system, camera, AI inference, alert, and incident telemetry in standard Prometheus text format."
)
async def get_prometheus_metrics():
    metrics_text = metrics_registry.render_prometheus_text()
    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )
