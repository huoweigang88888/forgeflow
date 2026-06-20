"""
ForgeFlow API - Test Configuration & Fixtures.

Provides shared fixtures for all tests:
- Async test client
- Test database session
- Mock providers and LLM clients
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def async_client():
    """Create an async HTTP test client for the FastAPI app."""
    from forgeflow.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
