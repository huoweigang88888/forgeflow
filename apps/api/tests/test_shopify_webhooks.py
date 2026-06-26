"""
Integration tests for Shopify business webhook endpoints.
"""

import base64
import hashlib
import hmac as hmac_module
import json

import pytest

# Must match the value set in tests/conftest.py
TEST_SECRET = "test-secret-for-webhooks"


def _sign_payload(payload: dict) -> str:
    """Compute a valid Shopify webhook HMAC signature.

    Uses compact JSON separators (no spaces) to match the exact body
    that httpx produces when sending ``json=payload``.
    """
    body = json.dumps(payload, separators=(",", ":")).encode()
    computed = hmac_module.new(
        key=TEST_SECRET.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(computed).decode("ascii")


@pytest.mark.integration
@pytest.mark.asyncio
class TestBusinessWebhooks:
    """Integration tests for the 4 business webhook endpoints.

    These tests use the real HMAC verification dependency but require
    the SHOPIFY_CLIENT_SECRET to be set to ``TEST_SECRET`` in the test
    environment.
    """

    async def test_orders_create_with_valid_hmac(self, async_client):
        """A valid HMAC header should result in 200 OK."""
        payload = {"id": 1234567890, "order_number": 1001}
        response = await async_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            json=payload,
            headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["message"] == "Webhook received"

    async def test_orders_updated_with_valid_hmac(self, async_client):
        """orders/updated should accept valid HMAC."""
        payload = {
            "id": 1234567890,
            "fulfillment_status": "fulfilled",
        }
        response = await async_client.post(
            "/api/v1/webhooks/shopify/orders/updated",
            json=payload,
            headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
        )
        assert response.status_code == 200

    async def test_fulfillments_create_with_valid_hmac(self, async_client):
        """fulfillments/create should accept valid HMAC."""
        payload = {
            "id": 98765,
            "order_id": 1234567890,
            "status": "success",
            "tracking_number": "1Z999AA10123456784",
        }
        response = await async_client.post(
            "/api/v1/webhooks/shopify/fulfillments/create",
            json=payload,
            headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
        )
        assert response.status_code == 200

    async def test_fulfillments_update_with_valid_hmac(self, async_client):
        """fulfillments/update should accept valid HMAC."""
        payload = {
            "id": 98765,
            "order_id": 1234567890,
            "tracking_number": "1Z999AA10123456784",
            "tracking_url": "https://www.ups.com/track/1Z999AA10123456784",
        }
        response = await async_client.post(
            "/api/v1/webhooks/shopify/fulfillments/update",
            json=payload,
            headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
        )
        assert response.status_code == 200

    # ── Authentication failure cases ──

    async def test_missing_hmac_header_returns_401(self, async_client):
        """Missing HMAC header should be rejected with 401."""
        payload = {"id": 123}
        response = await async_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            json=payload,
        )
        assert response.status_code == 401

    async def test_invalid_hmac_signature_returns_401(self, async_client):
        """An obviously invalid HMAC should be rejected with 401."""
        payload = {"id": 123}
        invalid_hmac = base64.b64encode(b"this_is_not_a_valid_signature").decode()
        response = await async_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            json=payload,
            headers={"X-Shopify-Hmac-Sha256": invalid_hmac},
        )
        assert response.status_code == 401

    async def test_wrong_secret_hmac_returns_401(self, async_client):
        """HMAC signed with wrong secret should be rejected."""
        payload = {"id": 123}
        wrong_secret = "not-the-real-secret-xx"
        body = json.dumps(payload).encode()
        c = hmac_module.new(
            key=wrong_secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).digest()
        wrong_hmac = base64.b64encode(c).decode("ascii")
        response = await async_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            json=payload,
            headers={"X-Shopify-Hmac-Sha256": wrong_hmac},
        )
        assert response.status_code == 401

    async def test_non_json_body_returns_400(self, async_client):
        """Non-JSON body should produce a 400 error (not 500)."""
        body = b"this is not valid json"
        computed = hmac_module.new(
            key=TEST_SECRET.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).digest()
        hmac_header = base64.b64encode(computed).decode("ascii")

        response = await async_client.post(
            "/api/v1/webhooks/shopify/orders/create",
            content=body,
            headers={
                "Content-Type": "text/plain",
                "X-Shopify-Hmac-Sha256": hmac_header,
            },
        )
        assert response.status_code == 400

    # ── All 4 endpoints are reachable ──

    async def test_all_endpoints_registered(self, async_client):
        """Verify all 4 webhook routes are registered and respond."""
        endpoints = [
            "/api/v1/webhooks/shopify/orders/create",
            "/api/v1/webhooks/shopify/orders/updated",
            "/api/v1/webhooks/shopify/fulfillments/create",
            "/api/v1/webhooks/shopify/fulfillments/update",
        ]
        for path in endpoints:
            payload = {"id": 1}
            response = await async_client.post(
                path,
                json=payload,
                headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
            )
            assert response.status_code == 200, f"{path} returned {response.status_code}"
