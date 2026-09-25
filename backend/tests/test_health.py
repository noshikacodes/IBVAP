import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_endpoint(async_client: AsyncClient):
    """Test the root /health endpoint."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_name" in data
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_v1_health_endpoint(async_client: AsyncClient):
    """Test the versioned /api/v1/health endpoint."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["environment"] == "development"


@pytest.mark.asyncio
async def test_v1_info_endpoint(async_client: AsyncClient):
    """Test the /api/v1/info endpoint."""
    response = await async_client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert data["api_v1_path"] == "/api/v1"
    assert data["version"] == "0.1.0"
