"""
ForgeFlow AI - HTTP Metrics Middleware.

ASGI middleware that records Prometheus metrics for every HTTP request:
- http_requests_total (by method, endpoint, status)
- http_request_duration_seconds (by method, endpoint)

Registered as the outermost middleware so it captures all requests,
including those from CORS, error handlers, and other middleware.
"""

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from forgeflow.monitoring.metrics import (
    http_request_duration_seconds,
    http_requests_total,
)


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    """Records HTTP metrics for every request.

    Skips the /api/metrics endpoint to avoid infinite metric recursion.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip metrics endpoint itself to avoid inflating its own metrics
        if request.url.path == "/api/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Simplify endpoint label: strip path params to avoid cardinality explosion
        # e.g. /api/v1/tickets/abc123/approve -> /api/v1/tickets/{id}/approve
        endpoint = self._normalize_path(request.url.path)

        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=str(response.status_code),
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint,
        ).observe(duration)

        return response

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Replace UUIDs and numeric path segments with placeholders.

        Simplifies Prometheus label cardinality by collapsing dynamic segments.
        """
        import re

        # Replace UUIDs: 8-4-4-4-12 hex pattern
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
        )
        # Replace numeric IDs: pure digits in a path segment
        path = re.sub(r"/\d+/", "/{id}/", path)
        # Trailing numeric ID
        path = re.sub(r"/\d+$", "/{id}", path)

        return path
