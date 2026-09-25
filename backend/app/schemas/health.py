from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Operational status of the API service")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="API Version")
    environment: str = Field(..., description="Runtime environment")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of response")


class SystemInfoResponse(BaseModel):
    app_name: str
    version: str
    environment: str
    debug: bool
    api_v1_path: str
