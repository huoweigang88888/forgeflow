"""
ForgeFlow AI - Auth Middleware.

JWT validation middleware that extracts tenant identity and injects it
into ``request.state`` for downstream middleware and route handlers.

Works in tandem with:
- ``middleware/tenant.py`` — reads ``request.state.shopify_domain``
- ``core/security.py`` — ``verify_token()`` for JWT validation
- ``api/v1/auth.py`` — public OAuth endpoints are skipped

Design:
- Stateless JWT (HS256, 24h expiry)
- No session lookup on every request (the JWT is authoritative)
- Tenant identity comes from the ``shop`` claim in the JWT
- Access token lookup only happens at the point of use (ticket creation)
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from forgeflow.core.security import verify_token
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="middleware.auth")

# ── Paths that do NOT require authentication ──
_PUBLIC_PATH_PREFIXES = (
    "/api/v1/auth/shopify/",
    "/api/v1/webhooks/shopify/",  # Shopify business webhooks (HMAC auth)
    "/api/v1/gdpr/customers/",  # GDPR customer webhooks (HMAC auth)
    "/api/v1/gdpr/shop/",  # GDPR shop redact webhook (HMAC auth)
    "/api/health",  # Health check endpoints (liveness/readiness)
    "/api/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/ws/",  # WebSocket auth handled separately
)


def _is_public_path(path: str) -> bool:
    """Check if a request path is public (no auth required).

    In development mode, ALL paths are public — auth is skipped so
    E2E tests and local development don't require a valid Shopify JWT.

    Args:
        path: The request URL path.

    Returns:
        True if the path should be allowed without a JWT.
    """
    from forgeflow.core.config import get_settings

    settings = get_settings()
    if settings.app_env == "development":
        return True

    return any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate JWT tokens and inject tenant identity.

    For every request:
    1. Extract ``Authorization: Bearer <token>`` header
    2. Verify the JWT via ``verify_token()``
    3. Set ``request.state.shopify_domain`` from the ``shop`` claim
    4. Set ``request.state.token_claims`` (full JWT payload)

    Public paths (OAuth install/callback, health, metrics, docs) are
    skipped — they pass through without authentication.

    On failure, returns 401 with a consistent error shape.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # ── Skip auth for public paths ──
        if _is_public_path(request.url.path):
            # Still initialize state attributes so downstream code
            # doesn't crash on attribute access
            request.state.shopify_domain = ""
            request.state.token_claims = {}
            return await call_next(request)

        # ── Extract token ──
        auth_header = request.headers.get("Authorization", "")
        token: str | None = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # Try query param (used by WebSocket connections)
            token = request.query_params.get("token")

        if not token:
            return _unauthorized_response(
                request,
                "Missing Authorization header. Use: Bearer <token>",
            )

        # ── Verify JWT ──
        claims = verify_token(token)
        if claims is None:
            return _unauthorized_response(
                request,
                "Invalid or expired token. Please re-authenticate.",
            )

        # ── Inject tenant identity ──
        shop_domain = claims.get("shop", "")
        request.state.shopify_domain = shop_domain
        request.state.token_claims = claims

        # Proceed to the next middleware / handler
        return await call_next(request)


# =============================================================================
# FastAPI Dependencies (for route-level opt-in auth)
# =============================================================================


def get_current_shop(request: Request) -> str:
    """FastAPI dependency: return the authenticated shop domain.

    Import this in route handlers to get the current tenant:
    ::

        @router.post("/tickets")
        async def create_ticket(
            body: TicketCreateRequest,
            shop: str = Depends(get_current_shop),
        ):
            ...

    Raises:
        HTTPException 401: If the request is not authenticated.
    """
    from fastapi import HTTPException

    shop_domain: str = getattr(request.state, "shopify_domain", "")
    if not shop_domain:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a valid Bearer token.",
        )
    return shop_domain


def get_optional_shop(request: Request) -> str | None:
    """FastAPI dependency: return shop domain or None if unauthenticated.

    Use for endpoints that work both with and without auth.
    """
    shop_domain: str = getattr(request.state, "shopify_domain", "")
    return shop_domain if shop_domain else None


# =============================================================================
# Helpers
# =============================================================================


def _unauthorized_response(request: Request, message: str) -> JSONResponse:
    """Return a 401 JSON response in the standard error format.

    Matches the existing ForgeFlow error response shape:
    ``{"code": "UNAUTHORIZED", "message": "...", "details": null}``
    """
    logger.warning(
        "auth_unauthorized",
        path=request.url.path,
        client_host=request.client.host if request.client else "unknown",
    )
    return JSONResponse(
        status_code=401,
        content={
            "code": "UNAUTHORIZED",
            "message": message,
            "details": None,
            "request_id": getattr(request.state, "request_id", None),
        },
    )
