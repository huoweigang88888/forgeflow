"""
ForgeFlow API - Root Router.

Aggregates all API version routers under a common prefix.

Sub-routers are imported lazily via ``setup_routes()`` to avoid
cascading imports of heavy dependencies (LangGraph, LLM SDKs,
provider clients) at module load time.

Call ``setup_routes()`` once during ``create_app()`` — typically
from ``forgeflow.main``.
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter(prefix="/api")


def setup_routes() -> None:
    """Import and register all sub-routers.

    This function exists so that ``import forgeflow.api.router`` (or
    ``from forgeflow.api import api_router``) completes in <1s instead
    of ~105s.  All heavy imports — LangGraph, LLM provider SDKs,
    Shopify API clients — are deferred until the app actually starts.

    Called from ``forgeflow.main.create_app()``.
    """
    from forgeflow.api.v1.auth import router as auth_router
    from forgeflow.api.v1.gdpr import router as gdpr_router
    from forgeflow.api.v1.health import router as health_router
    from forgeflow.api.v1.policies import router as policies_router
    from forgeflow.api.v1.prompts import router as prompts_router
    from forgeflow.api.v1.tickets import router as tickets_router
    from forgeflow.api.v1.webhooks import router as webhooks_router
    from forgeflow.monitoring.metrics import router as metrics_router

    # Health check (unversioned)
    api_router.include_router(health_router, tags=["health"])

    # V1 routes (prefix: /api/v1)
    v1_router = APIRouter(prefix="/v1")
    v1_router.include_router(auth_router)
    v1_router.include_router(tickets_router)
    v1_router.include_router(policies_router)
    v1_router.include_router(prompts_router)
    v1_router.include_router(gdpr_router)
    v1_router.include_router(webhooks_router)
    api_router.include_router(v1_router)

    # Monitoring
    api_router.include_router(metrics_router, tags=["monitoring"])
