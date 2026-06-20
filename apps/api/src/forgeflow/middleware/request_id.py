"""
ForgeFlow AI - Request ID Middleware.

Ensures every request has a unique X-Request-ID for tracing.
Uses the incoming header if present, otherwise generates a UUID.
"""

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects X-Request-ID into request state and response headers.

    This ID flows through to structured logs, OpenTelemetry spans,
    and LLM call records for end-to-end traceability.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use incoming request ID or generate one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response = await call_next(request)

        # Echo back in response
        response.headers["X-Request-ID"] = request_id
        return response
