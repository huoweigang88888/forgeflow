"""
Tests for health check endpoints.
"""

import pytest


@pytest.mark.asyncio
async def test_health_check(async_client):
    """The basic health check should return 200 OK."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "forgeflow-api"
