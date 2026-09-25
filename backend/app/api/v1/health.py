from datetime import datetime
from fastapi import APIRouter, Depends
from backend.app.core.config import Settings, settings
from backend.app.api.deps import get_settings
from backend.app.schemas.health import HealthResponse, SystemInfoResponse

router = APIRouter(tags=["Health & Status"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Check",
    description="Returns the operational status, current version, and UTC timestamp of the API."
)
async def get_health(
    app_settings: Settings = Depends(get_settings)
) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        app_name=app_settings.PROJECT_NAME,
        version=app_settings.VERSION,
        environment=app_settings.ENVIRONMENT,
        timestamp=datetime.utcnow()
    )


@router.get(
    "/info",
    response_model=SystemInfoResponse,
    summary="Application Information",
    description="Returns high-level runtime metadata."
)
async def get_info(
    app_settings: Settings = Depends(get_settings)
) -> SystemInfoResponse:
    return SystemInfoResponse(
        app_name=app_settings.PROJECT_NAME,
        version=app_settings.VERSION,
        environment=app_settings.ENVIRONMENT,
        debug=app_settings.DEBUG,
        api_v1_path=app_settings.API_V1_STR
    )
