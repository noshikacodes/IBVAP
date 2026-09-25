from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.api.v1.api import api_router
from datetime import datetime
import time
from backend.app.schemas.health import HealthResponse
from ai_engine.telemetry.metrics import metrics_registry



@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing %s (v%s)...", settings.PROJECT_NAME, settings.VERSION)
    logger.info("Environment: %s | Debug: %s", settings.ENVIRONMENT, settings.DEBUG)
    yield
    logger.info("Shutting down %s...", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered Video Management and Perimeter Intrusion Analytics Platform Backend.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Set up CORS middleware
if settings.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Telemetry Request Middleware
@app.middleware("http")
async def metrics_middleware(request, call_next):
    method = request.method
    path = request.url.path
    # Group dynamic path parameters to prevent high cardinality in metrics
    sanitized_path = path
    if path.startswith("/api/v1/cameras/") and len(path.split("/")) > 4:
        sub = path.split("/")[4]
        sanitized_path = f"/api/v1/cameras/{{id}}/{sub}"
    elif path.startswith("/api/v1/cameras/") and len(path.split("/")) == 4:
        sanitized_path = "/api/v1/cameras/{id}"
    elif path.startswith("/api/v1/incidents/") and len(path.split("/")) > 4:
        sub = path.split("/")[4]
        sanitized_path = f"/api/v1/incidents/{{id}}/{sub}"
    elif path.startswith("/api/v1/incidents/") and len(path.split("/")) == 4:
        sanitized_path = "/api/v1/incidents/{id}"
    elif path.startswith("/api/v1/alerts/"):
        sanitized_path = "/api/v1/alerts/{id}"

    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration = time.perf_counter() - start_time
        status_code = str(response.status_code)
        metrics_registry.http_requests.inc(labels={"method": method, "endpoint": sanitized_path, "status_code": status_code})
        metrics_registry.http_request_duration.observe(duration, labels={"method": method, "endpoint": sanitized_path})
        return response
    except Exception as exc:
        duration = time.perf_counter() - start_time
        metrics_registry.http_requests.inc(labels={"method": method, "endpoint": sanitized_path, "status_code": "500"})
        metrics_registry.http_request_duration.observe(duration, labels={"method": method, "endpoint": sanitized_path})
        raise exc


# Top-level direct health check for infrastructure / load balancers
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Root"],
    summary="Root Health Check",
    include_in_schema=True
)
async def root_health():
    return HealthResponse(
        status="healthy",
        app_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.utcnow()
    )


# Standard Prometheus metrics endpoint at root
@app.get(
    "/metrics",
    tags=["Root"],
    summary="Prometheus Metrics Exposition",
    include_in_schema=True
)
async def root_metrics():
    metrics_text = metrics_registry.render_prometheus_text()
    from fastapi import Response
    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root path to interactive API documentation."""
    return RedirectResponse(url=f"{settings.API_V1_STR}/docs")


# Mount API V1 router
app.include_router(api_router, prefix=settings.API_V1_STR)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
