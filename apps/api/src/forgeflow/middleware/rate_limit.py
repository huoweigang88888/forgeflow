"""
ForgeFlow AI - Rate Limiting Middleware.

Provides per-tenant (shop domain) and per-IP rate limiting using
an in-memory sliding window.  Production deployments should replace
the in-memory store with Redis for multi-process compatibility.

Configuration (via environment / .env):
    RATE_LIMIT_PER_MINUTE=60         # Per-tenant requests per minute
    RATE_LIMIT_PER_IP_MINUTE=120     # Per-IP requests per minute
    RATE_LIMIT_ENABLED=true          # Set to false to disable (dev only)
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="middleware.rate_limit")

# ── Constants ──
_WINDOW_SECONDS = 60  # 1-minute sliding window
_DEFAULT_TENANT_LIMIT = 60  # Per-tenant requests per minute
_DEFAULT_IP_LIMIT = 120  # Per-IP requests per minute

# ── Public paths that skip rate limiting ──
_RATELIMIT_SKIP_PREFIXES = (
    "/api/health",
    "/api/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _should_skip(path: str) -> bool:
    """Check if a path should skip rate limiting."""
    return any(path.startswith(prefix) for prefix in _RATELIMIT_SKIP_PREFIXES)


# ── In-Memory Sliding Window Store ──
#
# Structure: {key: [timestamp, timestamp, ...]}
# Each key (tenant or IP) maps to a sorted list of request timestamps
# within the current window.  This is fine for single-process deployments
# (Fly.io / Railway with 1-2 instances).  For scaling beyond that,
# replace with a Redis sorted-set implementation.
#
# The store is bounded by periodic cleanup — we trim expired entries
# on every request, so memory grows with concurrent tenants, not time.

_store: dict[str, list[float]] = defaultdict(list)


def _cleanup_expired(key: str, now: float, cutoff: float) -> int:
    """Remove timestamps older than the window cutoff.

    Returns the count of requests remaining in the window.
    """
    timestamps = _store[key]
    # Find the first timestamp that is within the window
    idx = 0
    for ts in timestamps:
        if ts >= cutoff:
            break
        idx += 1
    # Trim expired entries
    if idx > 0:
        _store[key] = timestamps[idx:]
    return len(_store[key])


def _check_and_increment(key: str, limit: int, now: float) -> tuple[bool, int, int]:
    """Check if a key is within its rate limit and record the request.

    Args:
        key: The rate limit key (tenant domain or IP).
        limit: Maximum requests allowed in the window.
        now: Current time (monotonic or epoch).

    Returns:
        Tuple of (allowed: bool, remaining: int, reset_seconds: int).
    """
    cutoff = now - _WINDOW_SECONDS
    count = _cleanup_expired(key, now, cutoff)

    if count >= limit:
        # Rate limit exceeded — don't record this request
        oldest = _store[key][0] if _store[key] else now
        reset_in = max(1, int(_WINDOW_SECONDS - (now - oldest)))
        return False, 0, reset_in

    # Record this request
    _store[key].append(now)
    remaining = limit - count - 1
    # Estimate reset time based on the oldest entry
    oldest = _store[key][0]
    reset_in = max(1, int(_WINDOW_SECONDS - (now - oldest)))
    return True, remaining, reset_in


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant and per-IP rate limiting middleware.

    Rate limits are applied in this order:
    1. If the path is public (health/metrics/docs), skip rate limiting.
    2. Check tenant limit (by shop_domain from request.state).
    3. If no tenant, check IP limit.

    On rate limit violation, returns 429 with ``Retry-After`` header
    and a standard error response body.

    Configuration:
        Set ``RATE_LIMIT_ENABLED=false`` to disable entirely (dev mode).
    """

    def __init__(
        self,
        app,
        *,
        tenant_limit: int = _DEFAULT_TENANT_LIMIT,
        ip_limit: int = _DEFAULT_IP_LIMIT,
        enabled: bool = True,
    ):
        super().__init__(app)
        self.tenant_limit = tenant_limit
        self.ip_limit = ip_limit
        self.enabled = enabled

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for infrastructure endpoints
        if _should_skip(request.url.path):
            return await call_next(request)

        now = time.monotonic()

        # ── Tenant-based rate limit ──
        shop_domain: str = getattr(request.state, "shopify_domain", "")
        if shop_domain:
            allowed, remaining, reset_in = _check_and_increment(
                f"tenant:{shop_domain}", self.tenant_limit, now
            )
            if not allowed:
                logger.warning(
                    "rate_limit_tenant_exceeded",
                    shop=shop_domain,
                    path=request.url.path,
                    limit=self.tenant_limit,
                )
                return _rate_limit_response(self.tenant_limit, reset_in, scope="tenant")
            # Attach rate limit headers for the tenant
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.tenant_limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_in)
            response.headers["X-RateLimit-Scope"] = "tenant"
            return response

        # ── IP-based rate limit (fallback for unauthenticated requests) ──
        client_ip = _get_client_ip(request)
        allowed, remaining, reset_in = _check_and_increment(f"ip:{client_ip}", self.ip_limit, now)
        if not allowed:
            logger.warning(
                "rate_limit_ip_exceeded",
                ip=client_ip,
                path=request.url.path,
                limit=self.ip_limit,
            )
            return _rate_limit_response(self.ip_limit, reset_in, scope="ip")

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.ip_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)
        response.headers["X-RateLimit-Scope"] = "ip"
        return response


# =========================================================================
# Helpers
# =========================================================================


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting common proxy headers."""
    # X-Forwarded-For: client, proxy1, proxy2
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # X-Real-IP (set by nginx)
    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip.strip()
    # Fallback to direct client
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit_response(limit: int, reset_in: int, scope: str = "tenant") -> JSONResponse:
    """Return a 429 Too Many Requests response."""
    return JSONResponse(
        status_code=429,
        content={
            "code": "RATE_LIMITED",
            "message": (
                f"Rate limit exceeded ({scope}). "
                f"Limit: {limit} requests per minute. "
                f"Retry after {reset_in} seconds."
            ),
            "details": {
                "limit": limit,
                "reset_in_seconds": reset_in,
                "scope": scope,
            },
        },
        headers={
            "Retry-After": str(reset_in),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset_in),
        },
    )
