"""
ForgeFlow API - Test Configuration & Fixtures.
"""

import asyncio
import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

# ── Force the test secret BEFORE any forgeflow import ──
os.environ["SHOPIFY_CLIENT_SECRET"] = "test-secret-for-webhooks"


# ── Windows Event Loop Fix ──
# On Windows, pytest-asyncio defaults to ProactorEventLoop which can
# prematurely close during module/session-scoped fixture teardown.
# SelectorEventLoop is more stable for test scenarios.
@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop that works on Windows."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Ensure get_settings() reads the current env vars (including
    SHOPIFY_CLIENT_SECRET set above) on every test."""
    from forgeflow.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
async def async_client(_clear_settings_cache):
    """Create an async HTTP test client for the FastAPI app."""
    from forgeflow.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
