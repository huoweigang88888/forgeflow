"""
ForgeFlow AI - Database Engine.

Provides async SQLAlchemy engine and session factory configured
from application settings.

IMPORTANT: The engine is lazily initialized via module __getattr__
to avoid triggering database connections at module import time.
This reduces cold-start import time from ~105s to <5s.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from forgeflow.core.config import get_settings

# ── Lazy engine / session factory ──
# Module-level engine creation was the #1 import bottleneck: every
# ``import forgeflow.main`` triggered a full DB engine instantiation
# (DNS lookup, connection pool init, etc.).  Now the engine is only
# created on first access via __getattr__.

_engine: create_async_engine | None = None  # type: ignore[valid-type]
_async_session_local: async_sessionmaker[AsyncSession] | None = None


def _init_engine():
    """Create the async SQLAlchemy engine (called once on first access)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database.url,
            echo=settings.database.echo,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections hourly
        )
    return _engine


def _init_session_local():
    """Create the session factory (called once on first access)."""
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = async_sessionmaker(
            _init_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # Keep objects usable after commit
            autoflush=False,  # Explicit flush control
        )
    return _async_session_local


def __getattr__(name: str):
    """Lazily resolve engine / AsyncSessionLocal on first access.

    This is Python 3.7+ module-level __getattr__ — it's only called
    when a name is NOT found in the module's globals.  So the heavy
    DB initialization is deferred until something actually imports
    or accesses ``engine`` / ``AsyncSessionLocal``.
    """
    if name == "engine":
        return _init_engine()
    if name == "AsyncSessionLocal":
        return _init_session_local()
    raise AttributeError(f"module 'forgeflow.db.engine' has no attribute {name!r}")
