"""
Integration tests for Shopify GDPR webhook endpoints.
"""

import base64
import hashlib
import hmac as hmac_module
import json
from unittest.mock import AsyncMock, patch

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
class TestGdprWebhooks:
    """Integration tests for the 3 GDPR mandatory webhook endpoints."""

    # ── customers/data_request ──

    async def test_customers_data_request_valid(self, async_client):
        """customers/data_request with valid HMAC should return 200."""
        payload = {
            "shop_domain": "test-store.myshopify.com",
            "customer": {
                "id": 555,
                "email": "buyer@example.com",
                "first_name": "John",
            },
        }
        from forgeflow.services import GDRPExportResult, GDRPService

        with patch.object(GDRPService, "export_customer_data") as mock_export:
            mock_export.return_value = GDRPExportResult(
                customer_email="buyer@example.com",
                exported_at="2026-01-01T00:00:00Z",
                data={"customers": []},
            )
            response = await async_client.post(
                "/api/v1/gdpr/customers/data_request",
                json=payload,
                headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_customers_data_request_missing_hmac(self, async_client):
        """Data request without HMAC should return 401."""
        payload = {
            "shop_domain": "test-store.myshopify.com",
            "customer": {"email": "buyer@example.com"},
        }
        response = await async_client.post(
            "/api/v1/gdpr/customers/data_request",
            json=payload,
        )
        assert response.status_code == 401

    # ── customers/redact ──

    async def test_customers_redact_valid(self, async_client):
        """customers/redact with valid HMAC should return 200."""
        payload = {
            "shop_domain": "test-store.myshopify.com",
            "customer": {
                "id": 555,
                "email": "buyer@example.com",
            },
        }
        from forgeflow.services import GDPRAnonymizeResult, GDRPService

        with patch.object(GDRPService, "anonymize_customer_data") as mock_anon:
            mock_anon.return_value = GDPRAnonymizeResult(
                customer_email="buyer@example.com",
                anonymized_at="2026-01-01T00:00:00Z",
                tickets_anonymized=3,
                orders_anonymized=5,
                customer_deleted=False,
            )
            response = await async_client.post(
                "/api/v1/gdpr/customers/redact",
                json=payload,
                headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    async def test_customers_redact_empty_customer_field(self, async_client):
        """Redact with empty customer field should still return 200 (no-op)."""
        payload = {
            "shop_domain": "test-store.myshopify.com",
            "customer": {},
        }
        response = await async_client.post(
            "/api/v1/gdpr/customers/redact",
            json=payload,
            headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
        )
        assert response.status_code == 200

    # ── shop/redact ──

    async def test_shop_redact_valid(self, async_client):
        """shop/redact with valid HMAC should return 200."""
        payload = {"shop_domain": "test-store.myshopify.com"}

        with patch(
            "forgeflow.crud.shopify_session.mark_uninstalled", new_callable=AsyncMock
        ) as mock_mark:
            response = await async_client.post(
                "/api/v1/gdpr/shop/redact",
                json=payload,
                headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        mock_mark.assert_called_once()

    async def test_shop_redact_missing_hmac(self, async_client):
        """Shop redact without HMAC should return 401."""
        payload = {"shop_domain": "test-store.myshopify.com"}
        response = await async_client.post(
            "/api/v1/gdpr/shop/redact",
            json=payload,
        )
        assert response.status_code == 401

    # ── All 3 endpoints are registered ──

    async def test_all_gdpr_webhook_endpoints_registered(self, async_client):
        """Verify all 3 GDPR webhook routes are registered and respond."""
        endpoints = [
            "/api/v1/gdpr/customers/data_request",
            "/api/v1/gdpr/customers/redact",
            "/api/v1/gdpr/shop/redact",
        ]
        for path in endpoints:
            payload = {"shop_domain": "test.myshopify.com"}
            response = await async_client.post(
                path,
                json=payload,
                headers={"X-Shopify-Hmac-Sha256": _sign_payload(payload)},
            )
            assert response.status_code == 200, f"{path} returned {response.status_code}"
