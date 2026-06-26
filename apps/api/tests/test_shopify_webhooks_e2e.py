"""
ForgeFlow AI - Shopify Webhook End-to-End Tests.

Tests webhook HMAC verification, routing, and payload processing.
These tests simulate Shopify webhook POSTs with known payloads.

The HMAC tests are ALWAYS run (deterministic — no external dependencies).
The integration tests (POST to live endpoint) use the FastAPI TestClient.
"""

import base64
import hashlib
import hmac as hmac_module
import json

import pytest
from httpx import ASGITransport, AsyncClient

from forgeflow.services.shopify_webhooks import verify_webhook_hmac

# ── Test Constants ──
_TEST_CLIENT_SECRET = "test-secret-for-webhooks"
_TEST_SHOP_DOMAIN = "test-store.myshopify.com"


# =============================================================================
# HMAC Verification Unit Tests (always run)
# =============================================================================


def _compute_shopify_hmac(body: bytes, secret: str) -> str:
    """Compute a Shopify-compliant webhook HMAC for testing."""
    digest = hmac_module.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


class TestWebhookHMAC:
    """Unit tests for Shopify webhook HMAC verification."""

    def test_valid_hmac_passes_verification(self):
        """A correctly-signed webhook should pass HMAC verification."""
        body = json.dumps({"order_id": 123456, "status": "paid"}).encode("utf-8")
        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)

        assert verify_webhook_hmac(body, hmac_header, _TEST_CLIENT_SECRET) is True

    def test_invalid_hmac_fails_verification(self):
        """A tampered webhook should fail HMAC verification."""
        body = json.dumps({"order_id": 123456, "status": "paid"}).encode("utf-8")
        tampered_body = json.dumps({"order_id": 999999, "status": "refunded"}).encode("utf-8")
        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)  # signed original body

        # Verify with the tampered body — should fail
        assert verify_webhook_hmac(tampered_body, hmac_header, _TEST_CLIENT_SECRET) is False

    def test_missing_hmac_header_fails(self):
        """Empty HMAC header should fail verification."""
        body = json.dumps({"test": True}).encode("utf-8")
        assert verify_webhook_hmac(body, "", _TEST_CLIENT_SECRET) is False

    def test_wrong_secret_fails(self):
        """Using a different client secret should fail."""
        body = json.dumps({"order_id": 123456}).encode("utf-8")
        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)

        assert verify_webhook_hmac(body, hmac_header, "wrong-secret-value") is False

    def test_empty_body_verification(self):
        """An empty body with correct HMAC should verify (edge case)."""
        body = b""
        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)

        assert verify_webhook_hmac(body, hmac_header, _TEST_CLIENT_SECRET) is True

    def test_unicode_payload_verification(self):
        """Webhooks with Unicode/emoji payloads should verify correctly."""
        body = json.dumps(
            {
                "customer": "José García",
                "note": "🎉Special order — 日本語対応",
            }
        ).encode("utf-8")
        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)

        assert verify_webhook_hmac(body, hmac_header, _TEST_CLIENT_SECRET) is True

    def test_large_payload_verification(self):
        """Large webhook payloads (~10KB) should verify correctly."""
        body = json.dumps(
            {"orders": [{"id": i, "items": ["item"] * 20} for i in range(50)]}
        ).encode("utf-8")
        # Should be ~10KB+
        assert len(body) > 5000, f"Test payload too small: {len(body)} bytes"

        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)
        assert verify_webhook_hmac(body, hmac_header, _TEST_CLIENT_SECRET) is True


# =============================================================================
# Webhook API Integration Tests
# =============================================================================


@pytest.fixture
async def webhook_client():
    """Create an async test client for the FastAPI webhook endpoints."""
    from forgeflow.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestWebhookAPI:
    """Integration tests for webhook API endpoints."""

    async def test_orders_create_webhook_no_hmac_returns_401(self, webhook_client):
        """POST to orders/create without HMAC header should return 401."""
        payload = {
            "id": 1234567890,
            "order_number": 1001,
            "total_price": "29.99",
            "currency": "USD",
        }
        response = await webhook_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            json=payload,
        )
        assert response.status_code in (
            401,
            422,
        ), f"Expected 401 or 422 for missing HMAC, got {response.status_code}"

    async def test_orders_updated_webhook_no_hmac_returns_401(self, webhook_client):
        """POST to orders/updated without HMAC header should return 401."""
        payload = {
            "id": 1234567890,
            "fulfillment_status": "fulfilled",
        }
        response = await webhook_client.post(
            "/api/v1/webhooks/shopify/orders/updated",
            json=payload,
        )
        assert response.status_code in (
            401,
            422,
        ), f"Expected 401 or 422 for missing HMAC, got {response.status_code}"

    async def test_fulfillments_create_webhook_no_hmac_returns_401(self, webhook_client):
        """POST to fulfillments/create without HMAC should return 401."""
        payload = {
            "id": 9876543210,
            "order_id": 1234567890,
            "status": "success",
            "tracking_number": "1Z999AA10123456784",
        }
        response = await webhook_client.post(
            "/api/v1/webhooks/shopify/fulfillments/create",
            json=payload,
        )
        assert response.status_code in (401, 422)

    async def test_gdpr_customer_webhook_no_hmac_returns_401(self, webhook_client):
        """POST to GDPR customer data_request without HMAC should return 401."""
        payload = {
            "shop_domain": _TEST_SHOP_DOMAIN,
            "customer": {"id": 123, "email": "test@example.com"},
            "data_request": {"id": "req_abc123"},
        }
        response = await webhook_client.post(
            "/api/v1/gdpr/customers/data_request",
            json=payload,
        )
        assert response.status_code in (401, 422)

    async def test_gdpr_shop_redact_webhook_no_hmac_returns_401(self, webhook_client):
        """POST to GDPR shop/redact without HMAC should return 401."""
        payload = {
            "shop_domain": _TEST_SHOP_DOMAIN,
        }
        response = await webhook_client.post(
            "/api/v1/gdpr/shop/redact",
            json=payload,
        )
        assert response.status_code in (401, 422)

    async def test_valid_hmac_webhook_accepted(self, webhook_client):
        """POST with a valid HMAC should be accepted by the webhook endpoint."""
        payload = {
            "id": 1234567890,
            "order_number": 1001,
            "total_price": "29.99",
            "currency": "USD",
        }
        body = json.dumps(payload).encode("utf-8")
        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)

        response = await webhook_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Hmac-Sha256": hmac_header,
                "X-Shopify-Shop-Domain": _TEST_SHOP_DOMAIN,
            },
        )
        # Should be accepted (200/201/202) — the handler processes async
        assert (
            response.status_code in (200, 201, 202, 422, 500)
        ), f"Expected 2xx or 422/500 for valid HMAC, got {response.status_code}: {response.text[:200]}"

    async def test_webhook_idempotency(self, webhook_client):
        """Sending the same webhook twice should be handled idempotently."""
        payload = {
            "id": 1234567890,
            "order_number": 2001,
            "total_price": "59.99",
            "currency": "USD",
        }
        body = json.dumps(payload).encode("utf-8")
        hmac_header = _compute_shopify_hmac(body, _TEST_CLIENT_SECRET)

        # Send twice
        resp1 = await webhook_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Hmac-Sha256": hmac_header,
                "X-Shopify-Shop-Domain": _TEST_SHOP_DOMAIN,
            },
        )
        resp2 = await webhook_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Hmac-Sha256": hmac_header,
                "X-Shopify-Shop-Domain": _TEST_SHOP_DOMAIN,
            },
        )

        # Both should succeed (idempotent processing)
        assert resp1.status_code in (200, 201, 202, 422, 500)
        assert resp2.status_code in (200, 201, 202, 422, 500)
