"""
ForgeFlow AI - Shopify Webhook Utilities.

Provides HMAC verification and webhook registration for Shopify
webhook endpoints.  Shopify signs every webhook POST body with
HMAC-SHA256 using the app's ``client_secret`` as the key.

Key differences from OAuth callback HMAC:
- Callback HMAC signs query params (key=value&key=value…)
- Webhook HMAC signs the raw POST body bytes directly
- Webhook HMAC header: ``X-Shopify-Hmac-Sha256: <base64-hex>``
"""

import base64
import hashlib
import hmac as hmac_module
import json

import httpx
from fastapi import HTTPException, Request
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forgeflow.core.config import get_settings
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="services.shopify_webhooks")

# ── Webhook Topic → API Path mapping ──
# This dict is the **single source of truth** for webhook URL paths.
# The router in ``api/v1/webhooks.py`` MUST register endpoints at the
# same paths listed here.

_WEBHOOK_TOPICS: dict[str, str] = {
    # Business webhooks
    "orders/create": "/api/v1/webhooks/shopify/orders/create",
    "orders/updated": "/api/v1/webhooks/shopify/orders/updated",
    "fulfillments/create": "/api/v1/webhooks/shopify/fulfillments/create",
    "fulfillments/update": "/api/v1/webhooks/shopify/fulfillments/update",
    # GDPR mandatory webhooks
    "customers/data_request": "/api/v1/gdpr/customers/data_request",
    "customers/redact": "/api/v1/gdpr/customers/redact",
    "shop/redact": "/api/v1/gdpr/shop/redact",
}

_SHOPIFY_WEBHOOK_REGISTER_PATH = "/admin/api/2024-01/webhooks.json"


# =============================================================================
# HMAC Verification
# =============================================================================


def verify_webhook_hmac(
    raw_body: bytes,
    hmac_header: str,
    client_secret: str,
) -> bool:
    """Verify a Shopify webhook HMAC-SHA256 signature.

    Shopify signs the raw POST body (exactly as received) with
    HMAC-SHA256 and sends the base64-encoded digest in the
    ``X-Shopify-Hmac-Sha256`` header.

    Algorithm:
        1. Compute ``HMAC-SHA256(raw_body, client_secret)``
        2. Base64-encode the digest
        3. Compare with header using constant-time comparison

    Args:
        raw_body: Raw request body bytes (``await request.body()``).
        hmac_header: Value of the ``X-Shopify-Hmac-Sha256`` header.
        client_secret: Shopify app client secret (signing key).

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not hmac_header:
        logger.warning("shopify_webhook_missing_hmac_header")
        return False

    computed = hmac_module.new(
        key=client_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).digest()

    computed_b64 = base64.b64encode(computed).decode("ascii")

    is_valid = hmac_module.compare_digest(computed_b64, hmac_header)

    if not is_valid:
        logger.warning(
            "shopify_webhook_invalid_hmac",
            expected_prefix=computed_b64[:8],
            received_prefix=hmac_header[:8],
        )

    return is_valid


async def verify_shopify_webhook_hmac(request: Request) -> dict[str, object]:
    """FastAPI dependency: verify Shopify webhook HMAC and return parsed JSON body.

    This dependency:
    1. Reads the raw request body (cached by Starlette)
    2. Extracts the ``X-Shopify-Hmac-Sha256`` header
    3. Verifies HMAC using the app's ``client_secret``
    4. Returns ``json.loads(body)`` on success, raises 401 on failure

    Usage in route handlers::

        @router.post("/orders/create")
        async def orders_create(
            payload: dict = Depends(verify_shopify_webhook_hmac),
        ):
            ...

    Returns:
        Parsed JSON body as a dict.

    Raises:
        HTTPException(401): If HMAC verification fails.
    """
    settings = get_settings()

    # Read raw body once (Starlette caches it for Request.json() later)
    raw_body = await request.body()

    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")

    client_secret = settings.shopify_client_secret.get_secret_value()

    if not verify_webhook_hmac(raw_body, hmac_header, client_secret):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_hmac",
                "error_description": "Webhook HMAC verification failed.",
            },
        )

    # Parse and return the body — the route handler receives it as ``payload``
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as err:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_json",
                "error_description": "Webhook body is not valid JSON.",
            },
        ) from err


# =============================================================================
# Webhook Registration
# =============================================================================


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    reraise=False,  # Don't reraise — we catch errors per-topic below
)
async def _register_one_webhook(
    client: httpx.AsyncClient,
    topic: str,
    address: str,
) -> dict[str, object]:
    """Register a single webhook topic with Shopify.

    POST /admin/api/2024-01/webhooks.json

    Args:
        client: httpx AsyncClient configured with the store's access token.
        topic: Shopify webhook topic (e.g., "orders/create").
        address: Full HTTPS URL where Shopify should POST webhook events.

    Returns:
        Parsed JSON response from Shopify.
    """
    payload = {
        "webhook": {
            "topic": topic,
            "address": address,
            "format": "json",
        }
    }
    response = await client.post(
        _SHOPIFY_WEBHOOK_REGISTER_PATH,
        json=payload,
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


async def register_shopify_webhooks(
    shop_domain: str,
    access_token: str,
    webhook_base_url: str,
) -> dict[str, bool]:
    """Register all required webhook topics for a newly-installed store.

    Called after OAuth callback (fire-and-forget via ``asyncio.create_task``).
    Makes 7 sequential POST requests to the Shopify REST API.

    The ``webhook_base_url`` should be the public-facing base URL of the
    ForgeFlow API (e.g., ``https://api.forgeflow.ai``).  The webhook path
    from ``_WEBHOOK_TOPICS`` is appended to this base.

    Args:
        shop_domain: Shopify store domain (e.g., mystore.myshopify.com).
        access_token: Decrypted Shopify permanent access token.
        webhook_base_url: Public base URL of the ForgeFlow API.

    Returns:
        Dict mapping topic name → registration success (True/False).
        Individual failures are logged but do not abort the batch.
    """
    base_url = f"https://{shop_domain}"
    results: dict[str, bool] = {}

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(15.0),
    ) as client:
        for topic, api_path in _WEBHOOK_TOPICS.items():
            address = f"{webhook_base_url.rstrip('/')}{api_path}"
            try:
                await _register_one_webhook(client, topic, address)
                results[topic] = True
                logger.info(
                    "shopify_webhook_registered",
                    shop=shop_domain,
                    topic=topic,
                )
            except Exception as exc:
                results[topic] = False
                logger.warning(
                    "shopify_webhook_registration_failed",
                    shop=shop_domain,
                    topic=topic,
                    error=str(exc)[:300],
                )

    succeeded = sum(1 for v in results.values() if v)
    logger.info(
        "shopify_webhooks_registration_complete",
        shop=shop_domain,
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
    )

    return results
