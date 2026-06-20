"""
ForgeFlow API - Root Router.

Aggregates all API version routers under a common prefix.
"""

from fastapi import APIRouter

from forgeflow.api.v1.gdpr import router as gdpr_router
from forgeflow.api.v1.health import router as health_router
from forgeflow.api.v1.policies import router as policies_router
from forgeflow.api.v1.prompts import router as prompts_router
from forgeflow.api.v1.tickets import router as tickets_router
from forgeflow.monitoring.metrics import router as metrics_router

api_router = APIRouter(prefix="/api")

# Health check (unversioned)
api_router.include_router(health_router, tags=["health"])

# V1 routes (prefix: /api/v1)
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(tickets_router)
v1_router.include_router(policies_router)
v1_router.include_router(prompts_router)
v1_router.include_router(gdpr_router)
api_router.include_router(v1_router)

# Monitoring
api_router.include_router(metrics_router, tags=["monitoring"])
