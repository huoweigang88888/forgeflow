"""
ForgeFlow AI - FastAPI Application Factory.

Creates and configures the FastAPI application with all middleware,
routers, and lifecycle handlers.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forgeflow.api.router import api_router
from forgeflow.api.v1.ws import close_redis_pool
from forgeflow.api.v1.ws import router as ws_router
from forgeflow.core.config import get_settings
from forgeflow.middleware.metrics import HTTPMetricsMiddleware
from forgeflow.middleware.request_id import RequestIDMiddleware
from forgeflow.monitoring.logger import get_logger, setup_logging
from forgeflow.monitoring.sentry_setup import setup_sentry
from forgeflow.monitoring.tracing import setup_tracing

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="ForgeFlow AI API",
        description="AI After-Sales Workforce for E-commerce",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # --- Middleware (order matters: last added = first executed) ---

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"] if settings.debug else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID
    app.add_middleware(RequestIDMiddleware)

    # HTTP Metrics (outermost — captures all requests)
    app.add_middleware(HTTPMetricsMiddleware)

    # --- Routers ---
    app.include_router(api_router)
    app.include_router(ws_router)  # WebSocket at /ws/v1/...

    return app


# Application instance (used by uvicorn)
app = create_app()
