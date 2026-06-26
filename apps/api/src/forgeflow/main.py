"""
ForgeFlow AI - FastAPI Application Factory.

Creates and configures the FastAPI application with all middleware,
routers, and lifecycle handlers.

Performance note: Heavy imports (routers, middleware, monitoring) are
deferred into ``create_app()`` to avoid the ~105s import bottleneck.
Module-level imports are kept to the bare minimum (stdlib + FastAPI core).

Module-level ``app`` access is lazy via :pep:`562` ``__getattr__``:
``import forgeflow.main`` completes in <2s; the real app is only built
when ``forgeflow.main.app`` (or ``from forgeflow.main import app``) is
first accessed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forgeflow.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    # Deferred imports to avoid circular dependency at module level
    from forgeflow.api.v1.ws import close_redis_pool
    from forgeflow.monitoring.logger import get_logger, setup_logging
    from forgeflow.monitoring.sentry_setup import setup_sentry
    from forgeflow.monitoring.tracing import setup_tracing

    # --- Startup ---
    setup_logging(app_env=settings.app_env)
    logger = get_logger(component="app")
    logger.info("forgeflow_api_starting", env=settings.app_env)

    if settings.sentry_dsn:
        setup_sentry(settings.sentry_dsn, settings.app_env)

    # OpenTelemetry tracing (console exporter in dev, OTLP gRPC in prod)
    setup_tracing(app, settings.otel_endpoint if settings.otel_endpoint else None)

    yield

    # --- Shutdown ---
    logger.info("forgeflow_api_shutting_down")
    # Close Redis connection pool
    await close_redis_pool()
    # Dispose of the database engine connection pool
    from forgeflow.db.engine import engine

    await engine.dispose()


def _parse_cors_origins(settings_obj: Settings, *, debug: bool = False) -> list[str]:  # noqa: F821
    """Parse CORS origins from the settings string.

    In development mode, always includes localhost:3000.
    In production, reads from the CORS_ORIGINS env var (comma-separated).
    If empty in production, returns an empty list (secure-by-default).
    """
    if settings_obj.debug:
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    raw = settings_obj.cors_origins.strip()
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    All heavy imports are deferred here so that ``import forgeflow.main``
    completes in <2s instead of ~105s.  This also helps test suites that
    import ``app`` from ``forgeflow.main`` — the DB engine, routers, and
    middleware are only loaded when the app is actually created.

    Returns:
        Configured FastAPI application instance.
    """
    # Deferred imports — these trigger the cascading import chain
    # (routers → services → providers → models → db).  Keeping them
    # inside the factory means they only load when the app starts,
    # not when ANY module imports from forgeflow.main.
    from forgeflow.api.router import api_router, setup_routes
    from forgeflow.api.v1.ws import router as ws_router
    from forgeflow.middleware.auth import AuthMiddleware
    from forgeflow.middleware.metrics import HTTPMetricsMiddleware
    from forgeflow.middleware.rate_limit import RateLimitMiddleware
    from forgeflow.middleware.request_id import RequestIDMiddleware
    from forgeflow.middleware.tenant import TenantMiddleware

    # ── Register sub-routers (lazy — imports happen here, not at
    #     module load time of forgeflow.api.router) ──
    setup_routes()

    app = FastAPI(
        title="ForgeFlow AI API",
        description="AI After-Sales Workforce for E-commerce",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # --- Middleware (order matters: last added = first executed) ---
    #
    # Request flow:
    #   CORS → RateLimit → Auth → RequestID → Tenant → Metrics → API handler
    # Added in reverse order so CORS is outermost and Metrics is innermost.

    # HTTP Metrics (innermost — captures all handler time)
    app.add_middleware(HTTPMetricsMiddleware)

    # Tenant context (reads request.state.shopify_domain from AuthMiddleware)
    app.add_middleware(TenantMiddleware)

    # Request ID (generates/reads X-Request-ID header)
    app.add_middleware(RequestIDMiddleware)

    # Auth (JWT validation, sets request.state.shopify_domain)
    app.add_middleware(AuthMiddleware)

    # Rate Limiting (per-tenant and per-IP sliding window)
    app.add_middleware(
        RateLimitMiddleware,
        tenant_limit=settings.rate_limit_per_minute,
        ip_limit=settings.rate_limit_per_ip_minute,
        enabled=settings.rate_limit_enabled,
    )

    # CORS (outermost — handles OPTIONS preflight)
    # In production, origins are read from CORS_ORIGINS env var (comma-separated).
    # In development, defaults to localhost:3000 (frontend dev server).
    cors_origins = _parse_cors_origins(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Shopify-Hmac-Sha256"],
    )

    # --- Routers ---
    app.include_router(api_router)
    app.include_router(ws_router)  # WebSocket at /ws/v1/...

    return app


# ── Lazy module-level ``app`` singleton ───────────────────────────────
# ``import forgeflow.main`` stays fast — the real ``create_app()`` call
# (which triggers ~105s of heavy imports) only fires when ``app`` is
# first accessed.  This is transparent to all existing callers:
#   - ``uvicorn forgeflow.main:app``          ✓
#   - ``from forgeflow.main import app``      ✓
#   - ``async_client`` fixture in conftest    ✓
#
# Implementation: :pep:`562` module-level ``__getattr__`` (Python 3.7+).
# We cache the app in a file-private ``__dict__`` entry so that
# ``__getattr__`` is only called once.

_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    if name == "app":
        global _app
        if _app is None:
            _app = create_app()
        # Cache in module dict so __getattr__ is only called once
        import sys

        mod = sys.modules[__name__]
        mod.__dict__["app"] = _app
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
