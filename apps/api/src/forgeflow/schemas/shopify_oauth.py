"""
ForgeFlow AI - Shopify OAuth Schemas.

Pydantic request/response models for the Shopify OAuth flow endpoints
in ``api/v1/auth.py``.
"""

from pydantic import BaseModel, Field

# =============================================================================
# Request Schemas
# =============================================================================


class ShopifyInstallRequest(BaseModel):
    """Query parameters for initiating a Shopify OAuth install.

    Usage:
        GET /api/v1/auth/shopify/install?shop=mystore.myshopify.com
    """

    shop: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$",
        description="Shopify store domain (e.g., mystore.myshopify.com)",
        examples=["mystore.myshopify.com"],
    )


class ShopifyDisconnectRequest(BaseModel):
    """Body for disconnecting a Shopify store."""

    shop_domain: str = Field(
        ...,
        description="Shopify store domain to disconnect",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class ShopifyAuthResponse(BaseModel):
    """Response after successful OAuth callback + token exchange.

    Contains the ForgeFlow JWT that the frontend stores for subsequent
    authenticated API requests.
    """

    access_token: str = Field(
        ...,
        description="ForgeFlow JWT for authenticated API access",
    )
    shop_domain: str = Field(
        ...,
        description="Shopify store domain that was connected",
    )
    scopes: str = Field(
        ...,
        description="Comma-separated OAuth scopes granted",
    )
    installed_at: str = Field(
        ...,
        description="ISO 8601 timestamp of the installation",
    )


class SessionInfoResponse(BaseModel):
    """Current session status returned by GET /auth/session."""

    authenticated: bool = Field(
        ...,
        description="Whether the request has a valid JWT",
    )
    shop_domain: str | None = Field(
        None,
        description="Shopify store domain (null if unauthenticated)",
    )
    installed_at: str | None = Field(
        None,
        description="ISO 8601 installation timestamp",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="List of granted OAuth scopes",
    )


class LogoutResponse(BaseModel):
    """Response after disconnecting a Shopify store."""

    message: str = Field(
        default="Session terminated. Shopify access token deleted.",
        description="Human-readable confirmation",
    )


class ErrorDetail(BaseModel):
    """Detailed error response for OAuth failures."""

    error: str = Field(..., description="Machine-readable error code")
    error_description: str = Field(
        ...,
        description="Human-readable error description",
    )


# =============================================================================
# Response Envelopes (wrapping schemas above for consistent API format)
# =============================================================================


class ShopifyCallbackEnvelope(BaseModel):
    """Envelope for GET /auth/shopify/callback response."""

    code: int = Field(default=0, description="Status code (0 = success)")
    message: str = Field(default="Shopify store connected successfully")
    data: ShopifyAuthResponse


class SessionInfoEnvelope(BaseModel):
    """Envelope for GET /auth/session response."""

    code: int = Field(default=0, description="Status code (0 = success)")
    data: SessionInfoResponse


class LogoutEnvelope(BaseModel):
    """Envelope for DELETE /auth/session response."""

    code: int = Field(default=0, description="Status code (0 = success)")
    message: str = Field(default="Shopify store disconnected successfully")
    data: None = None
