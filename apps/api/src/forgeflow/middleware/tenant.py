"""
ForgeFlow AI - Tenant Middleware.

Extracts tenant context from JWT claims and injects it into the request
scope for database query filtering (shared DB + tenant_id isolation).

Phase 1 will implement:
- JWT claim extraction (shopify_domain from "shop" claim)
- ContextVar injection for current_tenant
- PostgreSQL RLS session variable setting

Phase 0 provides the stub skeleton.
"""

from contextvars import ContextVar

# Thread-safe async context variable for current tenant
current_tenant: ContextVar[str] = ContextVar("current_tenant", default="")

# Future Phase 1 implementation:
# async def tenant_middleware(request: Request, call_next):
#     shopify_domain = request.state.shopify_domain  # Set by JWT middleware
#     token = current_tenant.set(shopify_domain)
#     try:
#         response = await call_next(request)
#         return response
#     finally:
#         current_tenant.reset(token)
