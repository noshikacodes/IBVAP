from fastapi import APIRouter
from backend.app.api.v1 import health
from backend.app.api.v1.endpoints import alerts, cameras, incidents, metrics, ws, traffic

api_router = APIRouter()

# Register V1 Sub-routers
api_router.include_router(health.router)
api_router.include_router(cameras.router, prefix="/cameras", tags=["Cameras"])
api_router.include_router(traffic.router, prefix="/cameras", tags=["Traffic Analytics"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
api_router.include_router(ws.router, tags=["WebSockets"])


