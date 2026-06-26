"""
Tests for the Amazon SP-API Provider.

Covers token management, order parsing, fulfillment status mapping,
date parsing, and error handling — using mocked HTTP responses.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from forgeflow.providers.amazon.client import (
    AmazonAPIError,
    AmazonProvider,
    _handle_http_error,
    _map_amazon_status_to_fulfillment,
    _parse_amazon_date,
    _parse_amazon_order,
)
from forgeflow.providers.dto import OrderInfo

# ═══════════════════════════════════════════════════════════════════════════
# Order parsing
# ═══════════════════════════════════════════════════════════════════════════


class TestParseAmazonOrder:
    """Tests for _parse_amazon_order — normalizing SP-API responses."""

    def test_parses_basic_order(self):
        """Should extract all standard fields from a valid SP-API order."""
        raw = {
            "AmazonOrderId": "113-1234567-1234567",
            "PurchaseDate": "2024-06-15T10:30:00Z",
            "OrderStatus": "Shipped",
            "OrderTotal": {"Amount": "49.99", "CurrencyCode": "USD"},
            "BuyerInfo": {
                "BuyerEmail": "buyer@example.com",
                "BuyerName": "Jane Doe",
            },
            "ShippingAddress": {
                "City": "Seattle",
                "PostalCode": "98101",
                "CountryCode": "US",
                "StateOrRegion": "WA",
                "AddressLine1": "123 Main St",
            },
        }

        order = _parse_amazon_order(raw)

        assert isinstance(order, OrderInfo)
        assert order.order_id == "113-1234567-1234567"
        assert order.order_number == "113-1234567-1234567"
        assert order.customer_email == "buyer@example.com"
        assert order.customer_name == "Jane Doe"
        assert order.total_price == 49.99
        assert order.currency == "USD"
        assert order.fulfillment_status == "fulfilled"
        assert order.financial_status == "paid"
        assert order.shipping_address["city"] == "Seattle"
        assert order.shipping_address["zip"] == "98101"
        assert order.shipping_address["country"] == "US"

    def test_parses_canceled_order(self):
        """Canceled orders should map to refunde financial status."""
        raw = {
            "AmazonOrderId": "113-0000000-0000000",
            "OrderStatus": "Canceled",
            "OrderTotal": {"Amount": "0.00", "CurrencyCode": "USD"},
            "BuyerInfo": {"BuyerEmail": "x@y.com", "BuyerName": "Bob"},
        }

        order = _parse_amazon_order(raw)

        assert order.financial_status == "refunded"
        assert order.total_price == 0.0

    def test_parses_pending_order(self):
        """Pending orders should map to pending financial status."""
        raw = {
            "AmazonOrderId": "113-0000000-0000001",
            "OrderStatus": "Pending",
            "OrderTotal": {"Amount": "25.00", "CurrencyCode": "USD"},
            "BuyerInfo": {"BuyerEmail": "p@q.com", "BuyerName": "Alice"},
        }

        order = _parse_amazon_order(raw)

        assert order.financial_status == "pending"

    def test_missing_order_total_defaults_to_zero(self):
        """Missing or malformed OrderTotal should default to 0.0."""
        raw = {
            "AmazonOrderId": "113-0000000-0000002",
            "OrderStatus": "Shipped",
            "BuyerInfo": {"BuyerEmail": "n@m.com", "BuyerName": "Test"},
        }

        order = _parse_amazon_order(raw)

        assert order.total_price == 0.0
        assert order.currency == "USD"

    def test_missing_buyer_name_defaults(self):
        """Missing BuyerName should use 'Valued Customer'."""
        raw = {
            "AmazonOrderId": "113-0000000-0000003",
            "OrderStatus": "Shipped",
            "OrderTotal": {"Amount": "10.00", "CurrencyCode": "USD"},
            "BuyerInfo": {"BuyerEmail": "anon@example.com"},
        }

        order = _parse_amazon_order(raw)

        assert order.customer_name == "Valued Customer"
        assert order.customer_email == "anon@example.com"

    def test_empty_shipping_address(self):
        """Missing ShippingAddress should produce empty dict with defaults."""
        raw = {
            "AmazonOrderId": "113-0000000-0000004",
            "OrderStatus": "Shipped",
            "OrderTotal": {"Amount": "10.00", "CurrencyCode": "USD"},
            "BuyerInfo": {"BuyerEmail": "a@b.com", "BuyerName": "C"},
        }

        order = _parse_amazon_order(raw)

        assert order.shipping_address["city"] == ""
        assert order.shipping_address["country"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# Fulfillment status mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestFulfillmentStatusMapping:
    """Tests for _map_amazon_status_to_fulfillment."""

    @pytest.mark.parametrize(
        "amazon_status,expected",
        [
            ("Pending", "unfulfilled"),
            ("Unshipped", "unfulfilled"),
            ("PartiallyShipped", "partial"),
            ("Shipped", "fulfilled"),
            ("Canceled", "unknown"),
            ("Unfulfillable", "unknown"),
            ("InvoiceUnconfirmed", "unfulfilled"),
            ("UnknownStatus", "unknown"),
        ],
    )
    def test_maps_all_known_statuses(self, amazon_status, expected):
        """Should correctly map every known Amazon OrderStatus."""
        assert _map_amazon_status_to_fulfillment({"OrderStatus": amazon_status}) == expected

    def test_missing_status_defaults_to_unknown(self):
        """Should return 'unknown' when OrderStatus key is absent."""
        assert _map_amazon_status_to_fulfillment({}) == "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# Date parsing
# ═══════════════════════════════════════════════════════════════════════════


class TestParseAmazonDate:
    """Tests for _parse_amazon_date."""

    def test_parses_iso_with_z(self):
        dt = _parse_amazon_date("2024-06-15T10:30:00Z")
        assert dt == datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)

    def test_parses_iso_with_milliseconds_and_z(self):
        dt = _parse_amazon_date("2024-06-15T10:30:00.123Z")
        assert dt == datetime(2024, 6, 15, 10, 30, 0, 123000, tzinfo=UTC)

    def test_returns_none_for_empty_string(self):
        assert _parse_amazon_date("") is None

    def test_returns_none_for_none(self):
        assert _parse_amazon_date(None) is None

    def test_returns_none_for_invalid_date(self):
        assert _parse_amazon_date("not-a-date") is None


# ═══════════════════════════════════════════════════════════════════════════
# Error handling
# ═══════════════════════════════════════════════════════════════════════════


class TestHandleHttpError:
    """Tests for _handle_http_error."""

    def test_retryable_on_429(self):
        import httpx

        response = httpx.Response(
            429, json={"errors": [{"code": "QuotaExceeded", "message": "Rate limit"}]}
        )
        error = httpx.HTTPStatusError(
            "too many requests", request=httpx.Request("GET", "https://test"), response=response
        )
        result = _handle_http_error(error)
        assert result.retryable is True
        assert result.status_code == 429

    def test_retryable_on_5xx(self):
        import httpx

        for code in (500, 502, 503, 504):
            response = httpx.Response(code, json={"errors": [{"message": "Server error"}]})
            error = httpx.HTTPStatusError(
                "server error", request=httpx.Request("GET", "https://test"), response=response
            )
            result = _handle_http_error(error)
            assert result.retryable is True, f"Expected {code} to be retryable"

    def test_not_retryable_on_400(self):
        import httpx

        response = httpx.Response(
            400, json={"errors": [{"code": "InvalidInput", "message": "Bad request"}]}
        )
        error = httpx.HTTPStatusError(
            "bad request", request=httpx.Request("GET", "https://test"), response=response
        )
        result = _handle_http_error(error)
        assert result.retryable is False
        assert result.status_code == 400

    def test_extracts_error_message_from_body(self):
        import httpx

        response = httpx.Response(
            400, json={"errors": [{"code": "InvalidOrderId", "message": "Order not found"}]}
        )
        error = httpx.HTTPStatusError(
            "bad request", request=httpx.Request("GET", "https://test"), response=response
        )
        result = _handle_http_error(error)
        assert "Order not found" in str(result)


# ═══════════════════════════════════════════════════════════════════════════
# AmazonProvider — lifecycle & config
# ═══════════════════════════════════════════════════════════════════════════


class TestAmazonProviderInit:
    """Tests for AmazonProvider construction and properties."""

    def test_default_region_is_na(self):
        provider = AmazonProvider()
        assert provider.platform_name == "amazon"
        assert provider.region == "na"

    def test_accepts_credentials(self):
        provider = AmazonProvider(
            client_id="test-id",
            client_secret="test-secret",
            refresh_token="test-refresh",
            region="eu",
        )
        assert provider.client_id == "test-id"
        assert provider.client_secret == "test-secret"
        assert provider.refresh_token == "test-refresh"
        assert provider.region == "eu"

    def test_region_endpoints(self):
        """Different regions should produce different API endpoints."""
        na = AmazonProvider(region="na")
        eu = AmazonProvider(region="eu")
        fe = AmazonProvider(region="fe")

        assert "na" in na._api_endpoint
        assert "eu" in eu._api_endpoint
        assert "fe" in fe._api_endpoint

    def test_invalid_region_falls_back_to_na(self):
        provider = AmazonProvider(region="unknown")
        assert "na" in provider._api_endpoint


# ═══════════════════════════════════════════════════════════════════════════
# AmazonProvider — token management
# ═══════════════════════════════════════════════════════════════════════════


class TestAmazonTokenManagement:
    """Tests for LWA token acquisition and caching."""

    @pytest.mark.asyncio
    async def test_raises_without_credentials(self):
        """Should raise AmazonAPIError when no credentials are configured."""
        provider = AmazonProvider()  # all empty

        with pytest.raises(AmazonAPIError, match="No API credentials"):
            await provider._get_access_token()

    @pytest.mark.asyncio
    async def test_caches_token_within_buffer(self):
        """Should return the cached token when not near expiry."""
        provider = AmazonProvider(client_id="id", client_secret="secret", refresh_token="refresh")
        # Simulate a fresh cached token
        provider._access_token = "cached-token"
        provider._token_expires_at = datetime.now(UTC) + timedelta(hours=1)

        token = await provider._get_access_token()

        assert token == "cached-token"

    @pytest.mark.asyncio
    async def test_refreshes_token_when_expired(self):
        """Should fetch a new token when the cached one is expired."""
        from unittest.mock import MagicMock

        provider = AmazonProvider(client_id="id", client_secret="secret", refresh_token="refresh")
        provider._access_token = "old-token"
        provider._token_expires_at = datetime.now(UTC) - timedelta(minutes=1)

        # Mock the HTTP call to LWA — use MagicMock for sync .json()/.raise_for_status()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            token = await provider._get_access_token()

        assert token == "new-token"


# ═══════════════════════════════════════════════════════════════════════════
# AmazonProvider — create_refund (Phase 2: IAM required)
# ═══════════════════════════════════════════════════════════════════════════


class TestAmazonRefundDeferred:
    """Tests for create_refund — Phase 2 with graceful fallback."""

    @pytest.mark.asyncio
    async def test_returns_failed_result_without_iam(self):
        """Should return RefundResult with success=False when IAM is not configured."""
        provider = AmazonProvider()

        result = await provider.create_refund(
            order_id="113-1234567-1234567",
            amount=49.99,
            reason="Customer request",
        )

        assert result.success is False
        assert result.amount == 49.99
        assert "IAM" in result.error


# ═══════════════════════════════════════════════════════════════════════════
# AmazonProvider — track_shipment (Phase 2: IAM required)
# ═══════════════════════════════════════════════════════════════════════════


class TestAmazonTrackingDeferred:
    """Tests for track_shipment — Phase 2 with graceful fallback."""

    @pytest.mark.asyncio
    async def test_returns_unknown_without_iam(self):
        """Should return TrackingInfo with unknown status when IAM is not configured."""
        provider = AmazonProvider()

        result = await provider.track_shipment(
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
        )

        assert result.status == "unknown"
        assert "IAM" in result.status_detail
        assert result.tracking_number == "1Z999AA10123456784"
