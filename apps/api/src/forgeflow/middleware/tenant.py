"""
ForgeFlow AI - Tenant Middleware.

Extracts tenant context from ``request.state.shopify_domain`` (set by
``AuthMiddleware``) and injects it into a thread-safe ContextVar for
use by database queries, logging, and downstream services.

The ``current_tenant`` ContextVar is available throughout the request
lifecycle — import it directly in CRUD operations or services that need
tenant-aware behavior.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Thread-safe async context variable for the current tenant.
# Set by TenantMiddleware from request.state.shopify_domain.
# Read by CRUD operations for RLS-like query filtering.
current_tenant: ContextVar[str] = ContextVar("current_tenant", default="")


class TenantMiddleware(BaseHTTPMiddleware):
    """Inject the current tenant into a ContextVar for the request lifecycle.

    Reads ``request.state.shopify_domain`` (must be set by AuthMiddleware
    or an earlier middleware) and sets ``current_tenant`` ContextVar so
    all downstream code has access to the tenant identity.

    On request completion, the ContextVar is reset to its previous value
    (or the default empty string).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        shopify_domain: str = getattr(request.state, "shopify_domain", "")

        if shopify_domain:
            token = current_tenant.set(shopify_domain)
            try:
                response = await call_next(request)
                return response
            finally:
                current_tenant.reset(token)
        else:
            # No auth — pass through without setting tenant
            return await call_next(request)
