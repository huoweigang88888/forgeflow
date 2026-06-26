"""
ForgeFlow AI - Auth API Endpoints.

Shopify OAuth 2.0 install / callback / session management.
All endpoints follow the existing response format: ``{"code": 0, "data": {...}}``.

Endpoints:
    GET  /api/v1/auth/shopify/install   — Redirect to Shopify OAuth
    GET  /api/v1/auth/shopify/callback  — Handle OAuth callback
    GET  /api/v1/auth/session           — Get current session info
    DELETE /api/v1/auth/session         — Disconnect / uninstall
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from forgeflow.core.exceptions import ForgeFlowError
from forgeflow.core.security import create_access_token
from forgeflow.crud.shopify_session import (
    create_session,
    get_session_by_domain,
    mark_uninstalled,
)
from forgeflow.db.session import OptionalDBSession
from forgeflow.monitoring.logger import get_logger
from forgeflow.schemas.shopify_oauth import (
    LogoutEnvelope,
    SessionInfoEnvelope,
    ShopifyCallbackEnvelope,
    ShopifyInstallRequest,
)
from forgeflow.security import encrypt_token
from forgeflow.services.shopify_oauth import get_shopify_oauth_service

logger = get_logger(component="api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Public path marker used by AuthMiddleware to skip JWT validation ──
_PUBLIC_PREFIXES = ("/api/v1/auth/shopify/",)

# ── Module-level singleton for Depends() — avoids B008 ──
_SHOPIFY_INSTALL_DEPENDS = Depends()


# =============================================================================
# GET /auth/shopify/install — Step 1: Redirect to Shopify
# =============================================================================


@router.get("/shopify/install", include_in_schema=True)
async def shopify_install(
    params: ShopifyInstallRequest = _SHOPIFY_INSTALL_DEPENDS,
) -> RedirectResponse:
    """Initiate Shopify OAuth installation.

    Generates the Shopify authorization URL and redirects the merchant's
    browser.  After the merchant approves, Shopify redirects back to the
    callback endpoint.

    Query params:
        shop: Shopify store domain (e.g., mystore.myshopify.com).
    """
    try:
        oauth = get_shopify_oauth_service()
        install_url = oauth.generate_install_url(params.shop)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    logger.info("shopify_install_redirect", shop=params.shop)
    return RedirectResponse(url=install_url, status_code=302)


# =============================================================================
# GET /auth/shopify/callback — Step 2: Handle OAuth callback
# =============================================================================


@router.get("/shopify/callback", response_model=ShopifyCallbackEnvelope, include_in_schema=True)
async def shopify_callback(
    code: str = Query(..., description="OAuth authorization code"),
    shop: str = Query(..., description="Shopify store domain"),
    hmac_param: str = Query("", alias="hmac", description="HMAC signature"),
    state: str = Query("", description="State nonce from install"),
    timestamp: str = Query("", description="OAuth timestamp"),
    db: OptionalDBSession = None,
) -> dict[str, Any]:
    """Handle the Shopify OAuth callback.

    After the merchant approves the app, Shopify redirects here with
    ``code``, ``shop``, ``hmac``, ``state``, and ``timestamp`` query params.

    This endpoint:
    1. Verifies the HMAC signature (prevents request tampering)
    2. Verifies the state nonce (prevents CSRF)
    3. Exchanges the code for a permanent access token
    4. Encrypts and stores the token in the database
    5. Returns a ForgeFlow JWT for subsequent API calls

    Returns a JSON response (NOT a redirect) — the frontend callback
    page handles the final redirect client-side.
    """
    oauth = get_shopify_oauth_service()

    # ── 1. Verify HMAC ──
    params = {
        "code": code,
        "shop": shop,
        "state": state,
        "timestamp": timestamp,
        "hmac": hmac_param,
    }
    if not oauth.verify_callback_hmac(params):
        logger.warning("shopify_callback_hmac_failed", shop=shop)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_hmac",
                "error_description": "HMAC verification failed. Request may be tampered.",
            },
        )

    # ── 2. Verify state ──
    verified_shop = oauth.verify_state_nonce(state)
    if verified_shop is None:
        logger.warning("shopify_callback_state_invalid", shop=shop)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_state",
                "error_description": "State nonce is invalid or expired. Please try connecting again.",
            },
        )
    if verified_shop != shop:
        logger.warning(
            "shopify_callback_shop_mismatch",
            expected=verified_shop,
            received=shop,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "shop_mismatch",
                "error_description": "Shop domain does not match the state nonce.",
            },
        )

    # ── 3. Exchange code for token ──
    try:
        token_data = await oauth.exchange_code_for_token(shop, code)
    except Exception as e:
        logger.error("shopify_callback_token_exchange_failed", shop=shop, error=str(e)[:300])
        raise HTTPException(
            status_code=500,
            detail={
                "error": "token_exchange_failed",
                "error_description": f"Failed to exchange authorization code: {e}",
            },
        ) from e

    access_token = token_data["access_token"]
    scopes = token_data.get("scope", "")

    # ── 4. Encrypt and store ──
    try:
        assert db is not None  # OptionalDBSession guaranteed by FastAPI DI
        encrypted = encrypt_token(access_token)

        # Upsert: if this shop already has a session, update it
        existing = await get_session_by_domain(db, shop)
        if existing is not None:
            # Re-authenticating — update existing session
            from forgeflow.crud.shopify_session import update_session_token

            await update_session_token(db, shop, encrypted, scopes)
            installed_at = existing.installed_at.isoformat()
        else:
            session = await create_session(
                db,
                shop_domain=shop,
                encrypted_token=encrypted,
                scopes=scopes,
            )
            installed_at = session.installed_at.isoformat()
    except ForgeFlowError as e:
        logger.error("shopify_callback_encryption_failed", shop=shop, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "token_storage_failed",
                "error_description": "Failed to securely store the access token.",
            },
        ) from e

    # ── 4.5 Register webhooks (fire-and-forget) ──
    # Schedule webhook registration in the background so the OAuth
    # response returns immediately.  Webhook registration makes 7
    # sequential HTTP calls and can take 1-5 seconds.
    import asyncio

    from forgeflow.core.config import get_settings
    from forgeflow.services.shopify_webhooks import register_shopify_webhooks

    app_settings = get_settings()
    # Derive the public base URL from the redirect URI.
    # Example: http://localhost:3000/auth/shopify/callback → http://localhost:3000
    _redirect = app_settings.shopify_oauth_redirect_uri
    _split_at = _redirect.rfind("/auth/")
    webhook_base = _redirect[:_split_at] if _split_at != -1 else _redirect

    _bg_task = asyncio.create_task(  # noqa: RUF006
        register_shopify_webhooks(
            shop_domain=shop,
            access_token=access_token,
            webhook_base_url=webhook_base,
        )
    )
    logger.info("shopify_webhook_registration_scheduled", shop=shop)

    # ── 5. Create ForgeFlow JWT ──
    jwt_token = create_access_token(
        data={
            "sub": shop,
            "shop": shop,
            "scopes": scopes,
        }
    )

    await db.commit()

    logger.info("shopify_callback_success", shop=shop, scopes=scopes)

    return {
        "code": 0,
        "message": "Shopify store connected successfully",
        "data": {
            "access_token": jwt_token,  # ForgeFlow JWT, NOT the Shopify token
            "shop_domain": shop,
            "scopes": scopes,
            "installed_at": installed_at,
        },
    }


# =============================================================================
# GET /auth/session — Current session info
# =============================================================================


@router.get("/session", response_model=SessionInfoEnvelope)
async def get_session(
    request: Request,
    db: OptionalDBSession = None,
) -> dict[str, Any]:
    """Return info about the current authenticated session.

    Requires a valid JWT in the Authorization header (enforced by
    AuthMiddleware — this endpoint is NOT in the public path list).
    The middleware sets ``request.state.shopify_domain``.
    """
    shop_domain = getattr(request.state, "shopify_domain", None)

    if not shop_domain:
        return {
            "code": 0,
            "data": {
                "authenticated": False,
                "shop_domain": None,
                "installed_at": None,
                "scopes": [],
            },
        }

    assert db is not None  # OptionalDBSession guaranteed by FastAPI DI
    # Look up session to confirm the store is still installed
    session = await get_session_by_domain(db, shop_domain)

    if session is None or not session.is_installed:
        return {
            "code": 0,
            "data": {
                "authenticated": False,
                "shop_domain": shop_domain,
                "installed_at": None,
                "scopes": [],
            },
        }

    return {
        "code": 0,
        "data": {
            "authenticated": True,
            "shop_domain": session.shop_domain,
            "installed_at": session.installed_at.isoformat() if session.installed_at else None,
            "scopes": session.scopes.split(",") if session.scopes else [],
        },
    }


# =============================================================================
# DELETE /auth/session — Disconnect / uninstall
# =============================================================================


@router.delete("/session", response_model=LogoutEnvelope)
async def delete_session_endpoint(
    request: Request,
    db: OptionalDBSession = None,
) -> dict[str, Any]:
    """Disconnect the Shopify store by marking the session as uninstalled.

    Requires a valid JWT.  After this call:
    - The Shopify session is soft-deleted (is_active=False, uninstalled_at set)
    - Further API calls will receive 401 responses (the JWT is still valid
      until expiry, but the session lookup will fail)
    - The Shopify store itself is NOT uninstalled — the merchant must
      also uninstall via Shopify Admin (the app/uninstalled webhook
      will trigger shop/redact cleanup)

    Phase 2: Add webhook-triggered cleanup for app/uninstalled.
    """
    shop_domain = getattr(request.state, "shopify_domain", None)

    if not shop_domain:
        raise HTTPException(status_code=401, detail="Not authenticated")

    assert db is not None  # OptionalDBSession guaranteed by FastAPI DI
    await mark_uninstalled(db, shop_domain)
    await db.commit()

    logger.info("shopify_session_disconnected", shop=shop_domain)

    return {
        "code": 0,
        "message": "Shopify store disconnected successfully",
        "data": None,
    }
