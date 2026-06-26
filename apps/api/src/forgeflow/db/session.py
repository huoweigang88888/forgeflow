"""
ForgeFlow AI - Database Session Management.

Provides FastAPI dependency for async database sessions with
automatic commit on success and rollback on error.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from forgeflow.core.config import get_settings
from forgeflow.db.engine import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async database session.

    Usage:
        @router.get("/tickets")
        async def list_tickets(db: DBSession):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Alias for consistency — all new code should use `get_session`
get_session = get_db


# Type alias for FastAPI dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db)]

# Optional variant — for endpoints that allow None (webhooks, etc.)
OptionalDBSession = Annotated[AsyncSession | None, Depends(get_db)]


# ------------------------------------------------------------------
# Redis Client
# ------------------------------------------------------------------

_redis_client: Redis[Any] | None = None


async def get_redis_client() -> Redis[Any]:
    """Return a shared Redis async client (lazy singleton).

    Usage:
        redis = await get_redis_client()
        await redis.publish("channel", "message")
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis_client() -> None:
    """Close the shared Redis client (call on app shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
