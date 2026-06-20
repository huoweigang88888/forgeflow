"""
ForgeFlow API - Middleware Package.

Middleware components for the FastAPI application:
- Request ID: injects X-Request-ID into every request/response
- Tenant: extracts and validates tenant context from JWT (Phase 1)
- CORS: cross-origin configuration
"""
