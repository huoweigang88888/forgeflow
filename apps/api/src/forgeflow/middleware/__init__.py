"""
ForgeFlow API - Middleware Package.

Middleware components for the FastAPI application:
- Auth:        JWT validation, sets request.state.shopify_domain
- Rate Limit:  Per-tenant / per-IP sliding window rate limiting
- Request ID:  Injects X-Request-ID into every request/response
- Tenant:      Extracts and validates tenant context from JWT
- Metrics:     HTTP request/response metrics collection
"""
