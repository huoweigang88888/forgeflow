"""
ForgeFlow AI - Shopify OAuth Service.

Handles the Shopify OAuth 2.0 authorization flow for installing the
ForgeFlow AI app on a Shopify store.

OAuth flow (per Shopify docs):
1. Merchant enters store domain → GET /api/v1/auth/shopify/install
2. Service builds Shopify authorization URL with signed state nonce
3. Browser redirects to Shopify → merchant approves scopes
4. Shopify redirects to callback with code + hmac + state
5. Service verifies HMAC, verifies state, exchanges code for token
6. Permanent access token returned → encrypted → stored in DB
7. ForgeFlow JWT issued to the merchant's browser

Key Shopify OAuth details:
- Token is PERMANENT (no refresh) — custom apps issue permanent tokens
- ``grant_options[]=per-user`` is REQUIRED for usable access tokens
- HMAC verification uses ``client_secret`` as the signing key
- State nonce uses ``secret_key`` (application-level) for signing
"""

import base64
import hashlib
import hmac
import json
import time
import urllib.parse

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forgeflow.core.config import get_settings
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="services.shopify_oauth")

# ── Constants ──
_STATE_TTL_SECONDS = 600  # 10 minutes
_SHOPIFY_OAUTH_AUTHORIZE_PATH = "/admin/oauth/authorize"
_SHOPIFY_OAUTH_TOKEN_PATH = "/admin/oauth/access_token"


class ShopifyOAuthService:
    """Shopify OAuth 2.0 authorization service.

    Stateless — all parameters are passed via constructor.  Instantiate
    once at module level or per-request.

    Usage::

        oauth = ShopifyOAuthService(
            client_id="...",
            client_secret="...",
            scopes="read_orders,...",
            redirect_uri="http://localhost:3000/auth/shopify/callback",
        )
        redirect_url = oauth.generate_install_url("mystore.myshopify.com")
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: str,
        redirect_uri: str,
    ):
        """Initialize the OAuth service.

        Args:
            client_id: Shopify app API key.
            client_secret: Shopify app API secret.
            scopes: Comma-separated OAuth scope list.
            redirect_uri: Callback URL (must match Shopify app settings).
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.redirect_uri = redirect_uri

    # =========================================================================
    # Install URL — Step 1 of the OAuth flow
    # =========================================================================

    def generate_install_url(self, shop_domain: str) -> str:
        """Build the Shopify OAuth authorization URL.

        The merchant's browser is redirected to this URL.  Shopify presents
        the permission screen, and on approval redirects back to our callback.

        URL format::

            https://{shop}/admin/oauth/authorize?
                client_id={api_key}&
                scope={scopes}&
                redirect_uri={redirect_uri}&
                state={signed_nonce}&
                grant_options[]=per-user

        Args:
            shop_domain: Shopify store domain (e.g., mystore.myshopify.com).

        Returns:
            Full Shopify OAuth authorization URL.
        """
        state_nonce = self._generate_state_nonce(shop_domain)
        params: dict[str, str] = {
            "client_id": self.client_id,
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri,
            "state": state_nonce,
        }
        # grant_options[] is a repeated query param — append manually
        query = urllib.parse.urlencode(params)
        query += "&grant_options[]=per-user"

        url = f"https://{shop_domain}{_SHOPIFY_OAUTH_AUTHORIZE_PATH}?{query}"
        logger.info(
            "shopify_oauth_install_url_generated",
            shop=shop_domain,
            scopes=self.scopes,
        )
        return url

    # =========================================================================
    # Token Exchange — Step 2 of the OAuth flow
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def exchange_code_for_token(self, shop_domain: str, code: str) -> dict[str, str]:
        """Exchange an OAuth authorization code for a permanent access token.

        POST https://{shop}/admin/oauth/access_token

        Request body::

            {
                "client_id": "...",
                "client_secret": "...",
                "code": "..."
            }

        Response::

            {
                "access_token": "shpat_...",
                "scope": "read_orders,write_orders,..."
            }

        Args:
            shop_domain: Shopify store domain.
            code: Authorization code from the OAuth callback.

        Returns:
            Dict with ``access_token`` and ``scope`` keys.

        Raises:
            ProviderError: If the token exchange fails.
        """
        url = f"https://{shop_domain}{_SHOPIFY_OAUTH_TOKEN_PATH}"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        logger.info(
            "shopify_oauth_token_exchanged",
            shop=shop_domain,
            scopes_granted=data.get("scope", ""),
        )
        return {
            "access_token": data["access_token"],
            "scope": data.get("scope", ""),
        }

    # =========================================================================
    # HMAC Verification — Shopify callback security
    # =========================================================================

    def verify_callback_hmac(self, params: dict[str, str]) -> bool:
        """Verify the HMAC signature on the OAuth callback.

        Shopify signs every OAuth callback request with HMAC-SHA256 using
        the app's client_secret as the key.  This prevents request tampering
        and ensures the callback genuinely originated from Shopify.

        Algorithm (per Shopify docs):
        1. Remove ``hmac`` and ``signature`` keys from params
        2. Sort remaining keys alphabetically
        3. Build query string: ``key1=value1&key2=value2...``
        4. Compute ``HMAC-SHA256(query_string, client_secret)``
        5. Compare with ``params["hmac"]`` in constant time

        Args:
            params: All query parameters from the callback URL.

        Returns:
            True if the HMAC is valid.
        """
        received_hmac = params.get("hmac", "")
        if not received_hmac:
            logger.warning("shopify_oauth_missing_hmac")
            return False

        # Remove hmac and signature, then sort
        filtered = {k: v for k, v in params.items() if k not in ("hmac", "signature")}
        sorted_keys = sorted(filtered.keys())
        query_string = "&".join(f"{k}={filtered[k]}" for k in sorted_keys)

        computed_hmac = hmac.new(
            key=self.client_secret.encode("utf-8"),
            msg=query_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        is_valid = hmac.compare_digest(computed_hmac, received_hmac)

        if not is_valid:
            logger.warning(
                "shopify_oauth_invalid_hmac",
                expected_prefix=computed_hmac[:8],
                received_prefix=received_hmac[:8],
            )

        return is_valid

    # =========================================================================
    # State Nonce — CSRF protection
    # =========================================================================

    def _generate_state_nonce(self, shop_domain: str) -> str:
        """Generate a signed state nonce for CSRF protection.

        The state contains the shop domain and an expiry timestamp, signed
        with HMAC-SHA256 using the app's SECRET_KEY.  This prevents an
        attacker from initiating an OAuth install for an arbitrary shop.

        Format (JSON → base64url)::

            {
                "shop": "mystore.myshopify.com",
                "exp": 1718899200,
                "sig": "hmac_sha256(shop + str(exp), secret_key)"
            }

        Args:
            shop_domain: The Shopify store domain being installed.

        Returns:
            Base64-url-encoded state parameter string.
        """
        settings = get_settings()
        secret = settings.secret_key.get_secret_value()
        exp = int(time.time()) + _STATE_TTL_SECONDS

        # Build signature: HMAC-SHA256(shop + expiry, secret_key)
        sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=f"{shop_domain}{exp}".encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        payload = json.dumps(
            {"shop": shop_domain, "exp": exp, "sig": sig},
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")

    def verify_state_nonce(self, state: str) -> str | None:
        """Verify a state nonce and return the shop domain if valid.

        Checks:
        1. Base64 decoding succeeds
        2. JSON parsing succeeds
        3. HMAC signature matches (prevents tampering)
        4. Expiry timestamp has not passed (prevents replay)

        Args:
            state: The state parameter from the OAuth callback.

        Returns:
            The shop domain string if the state is valid, None otherwise.
        """
        try:
            payload_bytes = base64.urlsafe_b64decode(state.encode("ascii"))
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            logger.warning("shopify_oauth_invalid_state_encoding")
            return None

        shop = payload.get("shop")
        exp = payload.get("exp")
        sig = payload.get("sig")

        if not all([shop, exp, sig]):
            logger.warning("shopify_oauth_state_missing_fields")
            return None

        # Check expiry
        if int(time.time()) > int(exp):
            logger.warning("shopify_oauth_state_expired", shop=shop)
            return None

        # Verify signature
        settings = get_settings()
        secret = settings.secret_key.get_secret_value()
        expected_sig = hmac.new(
            key=secret.encode("utf-8"),
            msg=f"{shop}{exp}".encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, sig):
            logger.warning("shopify_oauth_state_bad_signature", shop=shop)
            return None

        return shop  # valid


# =============================================================================
# Module-level service factory
# =============================================================================

# Lazily initialized singleton — created on first call.
_oauth_service: ShopifyOAuthService | None = None


def get_shopify_oauth_service() -> ShopifyOAuthService:
    """Return a configured ShopifyOAuthService singleton.

    Reads credentials from application settings (environment variables /
    .env file).  Use this as a FastAPI dependency or call directly.

    Usage::

        oauth = get_shopify_oauth_service()
        url = oauth.generate_install_url("mystore.myshopify.com")

    Raises:
        ValueError: If Shopify OAuth credentials are not configured.
    """
    global _oauth_service
    if _oauth_service is None:
        settings = get_settings()
        client_id = settings.shopify_client_id
        client_secret = settings.shopify_client_secret.get_secret_value()
        scopes = settings.shopify_scopes
        redirect_uri = settings.shopify_oauth_redirect_uri

        if not client_id or client_id == "your-shopify-client-id":
            raise ValueError(
                "Shopify OAuth credentials not configured. "
                "Set SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET in .env"
            )

        _oauth_service = ShopifyOAuthService(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            redirect_uri=redirect_uri,
        )
        logger.info(
            "shopify_oauth_service_initialized",
            redirect_uri=redirect_uri,
            scopes=scopes,
        )

    return _oauth_service
