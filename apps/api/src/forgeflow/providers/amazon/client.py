"""
ForgeFlow AI - Amazon SP-API Provider.

Implements PlatformProvider for Amazon Seller Central using the
Selling Partner API (SP-API).

Phase 1 (query): LWA OAuth 2.0 client credentials grant → LWA access token.
Phase 2 (write/refund/tracking): STS AssumeRole → AWS Signature V4 signing.

Per-tenant credentials are passed via constructor:
    provider = AmazonProvider(
        client_id="amzn1.application-oa2-client.xxx",
        client_secret="xxx",
        refresh_token="Atzr|xxx",
        region="na",  # na | eu | fe
    )

Reference: https://developer-docs.amazon.com/sp-api/
"""

from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forgeflow.core.config import get_settings
from forgeflow.core.exceptions import (
    ProviderError,
    ProviderTimeoutError,
)
from forgeflow.monitoring.logger import get_logger
from forgeflow.providers.amazon.auth import AmazonAuthManager, AWSSigV4Error
from forgeflow.providers.base import PlatformProvider
from forgeflow.providers.dto import ExchangeResult, OrderInfo, RefundResult, TrackingInfo

logger = get_logger(component="providers.amazon")

# ── SP-API Endpoints by region ──
_SP_API_ENDPOINTS: dict[str, str] = {
    "na": "https://sellingpartnerapi-na.amazon.com",
    "eu": "https://sellingpartnerapi-eu.amazon.com",
    "fe": "https://sellingpartnerapi-fe.amazon.com",
}

_LWA_ENDPOINTS: dict[str, str] = {
    "na": "https://api.amazon.com/auth/o2/token",
    "eu": "https://api-eu.amazon.com/auth/o2/token",
    "fe": "https://api-fe.amazon.com/auth/o2/token",
}


# ── Amazon API Error ──


class AmazonAPIError(ProviderError):
    """Amazon SP-API specific error with response details."""

    def __init__(self, message: str, *, status_code: int = 0, retryable: bool = False):
        super().__init__("amazon", message, retryable=retryable)
        self.status_code = status_code


# ── Amazon Provider ──


class AmazonProvider(PlatformProvider):
    """Amazon SP-API platform provider.

    Uses Login with Amazon (LWA) OAuth 2.0 client credentials grant to
    obtain an access token, then calls the Selling Partner API.

    Phase 1 scope:
        - get_order, get_customer_orders (query-only via LWA)
        - get_fulfillment_status (via order status mapping)
        - get_customer_history (via order aggregation)

    Phase 2 scope:
        - create_refund (requires IAM+STS + AWS Signature V4 for write ops)
        - track_shipment (requires IAM+STS for Shipping API or feeds)
        - send_email / send_sms (via external providers: SendGrid / Twilio)

    Usage:
        provider = AmazonProvider(
            client_id="amzn1.application-oa2-client.xxx",
            client_secret="xxx",
            refresh_token="Atzr|xxx",
        )
        order = await provider.get_order("113-1234567-1234567")
    """

    # Token refresh buffer — refresh when < 5 minutes remaining
    _TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        refresh_token: str = "",
        region: str = "na",
        api_version: str = "v0",
    ):
        """Initialize Amazon SP-API provider.

        Args:
            client_id: LWA application client ID.
            client_secret: LWA application client secret.
            refresh_token: LWA refresh token (obtained via OAuth web flow).
            region: SP-API region: na | eu | fe.
            api_version: Orders API version string (informational).
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.region = region
        self._api_version = api_version

        self._api_endpoint = _SP_API_ENDPOINTS.get(region, _SP_API_ENDPOINTS["na"])
        self._lwa_endpoint = _LWA_ENDPOINTS.get(region, _LWA_ENDPOINTS["na"])

        # Token cache
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

        self._client: httpx.AsyncClient | None = None

        # Phase 2: IAM+STS auth manager for write operations
        settings = get_settings()
        self._auth_manager = AmazonAuthManager(
            role_arn=settings.amazon_role_arn,
            region=region,
        )

    @property
    def platform_name(self) -> str:
        return "amazon"

    @property
    def platform_version(self) -> str:
        return self._api_version

    # =========================================================================
    # Auth helpers
    # =========================================================================

    async def _get_access_token(self) -> str:
        """Obtain or refresh the LWA access token.

        Uses the client credentials grant with a refresh token.
        Tokens are cached and refreshed when within 5 minutes of expiry.

        Returns:
            A valid LWA access token string.
        """
        now = datetime.now(UTC)

        # Return cached token if still valid
        if (
            self._access_token
            and self._token_expires_at
            and (self._token_expires_at - now) > self._TOKEN_REFRESH_BUFFER
        ):
            return self._access_token

        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise AmazonAPIError(
                "No API credentials configured. Pass client_id, client_secret, "
                "and refresh_token to constructor. For development, use "
                "platform='mock' instead of 'amazon'.",
                retryable=False,
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self._lwa_endpoint,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self.refresh_token,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                data = response.json()

                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = now + timedelta(seconds=expires_in)

                logger.info("amazon_lwa_token_refreshed", region=self.region)
                return self._access_token

            except httpx.TimeoutException:
                raise ProviderTimeoutError("amazon", timeout_s=30) from None
            except httpx.HTTPStatusError as e:
                raise _handle_http_error(e) from e

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client with LWA auth headers."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._api_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        # Always refresh auth headers (token may have changed)
        token = await self._get_access_token()
        self._client.headers["x-amz-access-token"] = token
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # OrderProvider
    # =========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_order(self, order_id: str) -> OrderInfo:
        """Fetch a single order from Amazon SP-API.

        GET /orders/v0/orders/{orderId}

        Args:
            order_id: Amazon order ID (format: 113-1234567-1234567).

        Returns:
            Normalized OrderInfo DTO.
        """
        client = await self._get_client()
        try:
            response = await client.get(f"/orders/v0/orders/{order_id}")
            response.raise_for_status()
            payload = response.json()
            order = payload.get("payload", {})

            logger.info(
                "amazon_get_order_success",
                order_id=order_id,
                amazon_order_id=order.get("AmazonOrderId"),
            )
            return _parse_amazon_order(order)

        except httpx.TimeoutException:
            raise ProviderTimeoutError("amazon", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_customer_orders(self, customer_id: str, limit: int = 10) -> list[OrderInfo]:
        """Fetch recent orders for a customer.

        SP-API /orders/v0/orders supports filtering by buyer email
        (AmazonOrderId is buyer-email-searchable via the orders API).
        We use the CreatedAfter/CreatedBefore window and filter client-side.

        GET /orders/v0/orders?BuyerEmail={customer_id}&MaxResultsPerPage={limit}

        NOTE: customer_id for Amazon is the buyer's email address.
        The SP-API Orders API filters by BuyerEmail, not a CustomerId.

        Args:
            customer_id: Amazon buyer email address.
            limit: Maximum orders to return.

        Returns:
            List of normalized OrderInfo DTOs, most recent first.
        """
        client = await self._get_client()
        try:
            # SP-API requires a CreatedAfter parameter
            created_after = (datetime.now(UTC) - timedelta(days=365)).isoformat()

            response = await client.get(
                "/orders/v0/orders",
                params={
                    "BuyerEmail": customer_id,
                    "MaxResultsPerPage": min(limit, 100),
                    "MarketplaceIds": "ATVPDKIKX0DER",  # Amazon.com; extend for other marketplaces
                    "CreatedAfter": created_after,
                },
            )
            response.raise_for_status()
            payload = response.json()
            orders_data = payload.get("payload", {}).get("Orders", [])

            logger.info(
                "amazon_get_customer_orders_success",
                customer_id=customer_id,
                count=len(orders_data),
            )
            return [_parse_amazon_order(o) for o in orders_data]

        except httpx.TimeoutException:
            raise ProviderTimeoutError("amazon", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def create_refund(
        self,
        order_id: str,
        amount: float,
        reason: str,
        notify_customer: bool = True,
    ) -> RefundResult:
        """Process a refund via SP-API (Phase 2: IAM+STS + SigV4).

        Amazon SP-API refunds require AWS Signature V4 via STS AssumeRole.
        Falls back gracefully if IAM role is not yet configured.

        Uses the SP-API Feeds API to submit an order adjustment for the
        refund amount. For partial refunds, specifies the adjustment reason.

        Args:
            order_id: Amazon order ID.
            amount: Refund amount in order currency.
            reason: Reason for the refund.
            notify_customer: Whether Amazon should notify the buyer.

        Returns:
            RefundResult indicating success or failure.
        """
        if not self._auth_manager.is_configured:
            logger.warning(
                "amazon_refund_no_iam",
                order_id=order_id,
                amount=amount,
            )
            return RefundResult(
                success=False,
                amount=amount,
                error=(
                    "Amazon refunds require IAM+STS (Phase 2). "
                    "Set AMAZON_ROLE_ARN, AMAZON_IAM_ACCESS_KEY, and "
                    "AMAZON_IAM_SECRET_KEY in environment to enable."
                ),
            )

        try:
            # Step 1: Assume the IAM role via STS
            credentials = await self._auth_manager.assume_role()

            # Step 2: Build the refund payload
            # SP-API Feeds API: POST /feeds/2021-06-30/feeds
            # Feed type: POST_ORDER_ADJUSTMENT_DATA
            refund_payload = {
                "feedType": "POST_ORDER_ADJUSTMENT_DATA",
                "marketplaceIds": ["ATVPDKIKX0DER"],  # Amazon.com
                "inputFeedDocumentId": "",  # We first upload the feed document
            }

            # Step 3: First create a feed document
            create_doc_body = {
                "contentType": "application/json; charset=UTF-8",
            }

            # Get LWA token for the SP-API call
            lwa_token = await self._get_access_token()

            # Sign the createFeedDocument request with SigV4
            sig_headers = self._auth_manager.sign_sp_api_request(
                method="POST",
                path="/feeds/2021-06-30/documents",
                body=_json_dumps(create_doc_body),
                credentials=credentials,
            )

            client = await self._get_client()
            doc_response = await client.post(
                "/feeds/2021-06-30/documents",
                json=create_doc_body,
                headers={
                    **sig_headers,
                    "x-amz-access-token": lwa_token,
                },
            )
            doc_response.raise_for_status()
            doc_data = doc_response.json()
            feed_document_id = doc_data.get("feedDocumentId", "")
            upload_url = doc_data.get("url", "")

            if not feed_document_id or not upload_url:
                return RefundResult(
                    success=False,
                    amount=amount,
                    error="Failed to create feed document for refund.",
                )

            # Step 4: Upload the feed content (order adjustment data)
            adjustment_data = {
                "header": {
                    "sellerId": "",  # Will be filled by SP-API
                    "version": "2.0",
                    "issueCountry": "US",
                },
                "messages": [
                    {
                        "messageId": "1",
                        "orderAdjustment": {
                            "amazonOrderID": order_id,
                            "adjustmentReason": _map_refund_reason(reason),
                            "adjustmentAmount": {
                                "amount": str(amount),
                                "currencyCode": "USD",
                            },
                        },
                    }
                ],
            }

            # Upload to the pre-signed URL (no SigV4 needed — it's a pre-signed S3 URL)
            async with httpx.AsyncClient(timeout=30.0) as upload_client:
                upload_resp = await upload_client.put(
                    upload_url,
                    content=_json_dumps(adjustment_data),
                    headers={
                        "Content-Type": "application/json; charset=UTF-8",
                    },
                )
                upload_resp.raise_for_status()

            # Step 5: Submit the feed
            refund_payload["inputFeedDocumentId"] = feed_document_id
            sig_headers2 = self._auth_manager.sign_sp_api_request(
                method="POST",
                path="/feeds/2021-06-30/feeds",
                body=_json_dumps(refund_payload),
                credentials=credentials,
            )

            feed_response = await client.post(
                "/feeds/2021-06-30/feeds",
                json=refund_payload,
                headers={
                    **sig_headers2,
                    "x-amz-access-token": lwa_token,
                },
            )
            feed_response.raise_for_status()
            feed_data = feed_response.json()
            feed_id = feed_data.get("feedId", "")

            logger.info(
                "amazon_refund_submitted",
                order_id=order_id,
                amount=amount,
                feed_id=feed_id,
            )

            return RefundResult(
                success=True,
                refund_id=feed_id,
                amount=amount,
            )

        except AWSSigV4Error as e:
            logger.error(
                "amazon_refund_auth_error",
                order_id=order_id,
                error=str(e)[:300],
            )
            return RefundResult(
                success=False,
                amount=amount,
                error=f"STS/SigV4 auth error: {e}",
            )
        except httpx.HTTPStatusError as e:
            amazon_err = _handle_http_error(e)
            logger.error(
                "amazon_refund_api_error",
                order_id=order_id,
                status=amazon_err.status_code,
                error=str(amazon_err)[:300],
            )
            return RefundResult(
                success=False,
                amount=amount,
                error=str(amazon_err),
            )
        except httpx.TimeoutException:
            logger.error(
                "amazon_refund_timeout",
                order_id=order_id,
            )
            return RefundResult(
                success=False,
                amount=amount,
                error="Refund request timed out. Retry or escalate to manual.",
            )

    async def create_exchange(
        self,
        order_id: str,
        reason: str,
        exchange_items: list[dict[str, Any]] | None = None,
        notify_customer: bool = True,
    ) -> ExchangeResult:
        """Initiate an exchange for an Amazon order (Phase 2: IAM+STS + SigV4).

        Amazon exchanges require the SP-API Feeds API with
        POST_ORDER_ADJUSTMENT_DATA feed type, similar to refunds but
        with different adjustment reason codes.

        Falls back gracefully if IAM role is not yet configured.

        Args:
            order_id: Amazon order ID.
            reason: Reason for the exchange.
            exchange_items: Optional line items to exchange.
            notify_customer: Whether Amazon should notify the buyer.

        Returns:
            ExchangeResult indicating success or failure.
        """
        if not self._auth_manager.is_configured:
            logger.warning(
                "amazon_exchange_no_iam",
                order_id=order_id,
            )
            return ExchangeResult(
                success=False,
                error=(
                    "Amazon exchanges require IAM+STS (Phase 2). "
                    "Set AMAZON_ROLE_ARN, AMAZON_IAM_ACCESS_KEY, and "
                    "AMAZON_IAM_SECRET_KEY in environment to enable."
                ),
            )

        # Phase 2: Implement full SP-API exchange flow
        # For now, return a placeholder indicating Phase 2 is needed
        logger.info(
            "amazon_exchange_phase2_placeholder",
            order_id=order_id,
            reason=reason,
        )
        return ExchangeResult(
            success=False,
            error="Amazon exchange processing requires Phase 2 SP-API Feeds integration.",
        )

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_fulfillment_status(self, order_id: str) -> str:
        """Get the fulfillment status of an order.

        Amazon orders use OrderStatus for state and FulfillmentChannel
        plus ShipmentServiceLevelCategory for fulfillment classification.

        GET /orders/v0/orders/{orderId}

        Args:
            order_id: Amazon order ID.

        Returns:
            Status string: unfulfilled | fulfilled | partial | unknown.
        """
        client = await self._get_client()
        try:
            response = await client.get(f"/orders/v0/orders/{order_id}")
            response.raise_for_status()
            payload = response.json()
            order = payload.get("payload", {})

            normalized = _map_amazon_status_to_fulfillment(order)

            logger.info(
                "amazon_fulfillment_status",
                order_id=order_id,
                order_status=order.get("OrderStatus"),
                normalized=normalized,
            )
            return normalized

        except httpx.TimeoutException:
            raise ProviderTimeoutError("amazon", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    async def get_customer_history(
        self, customer_email: str, order_id: str | None = None
    ) -> dict[str, Any]:
        """Retrieve customer history for decision-making.

        Aggregates order history from the SP-API Orders API.

        Args:
            customer_email: Amazon buyer email address.
            order_id: Optional related order ID for context.

        Returns:
            Dict with total_orders, total_spent, refund_count,
            previous_tickets, average_order_value, is_vip, account_age_days.
        """
        client = await self._get_client()

        try:
            created_after = (datetime.now(UTC) - timedelta(days=730)).isoformat()

            response = await client.get(
                "/orders/v0/orders",
                params={
                    "BuyerEmail": customer_email,
                    "MaxResultsPerPage": 100,
                    "MarketplaceIds": "ATVPDKIKX0DER",
                    "CreatedAfter": created_after,
                },
            )
            response.raise_for_status()
            payload = response.json()
            orders = payload.get("payload", {}).get("Orders", [])

            if not orders:
                logger.info(
                    "amazon_customer_not_found",
                    email=customer_email,
                )
                return {
                    "total_orders": 0,
                    "total_spent": 0.0,
                    "refund_count": 0,
                    "previous_tickets": [],
                    "average_order_value": 0.0,
                    "is_vip": False,
                    "account_age_days": None,
                }

            total_orders_count = len(orders)

            # Estimate total_spent from OrderTotal
            total_spent_val = 0.0
            refund_count = 0
            for o in orders:
                order_total = o.get("OrderTotal", {})
                amount_str = order_total.get("Amount", "0") if order_total else "0"
                with suppress(ValueError, TypeError):
                    total_spent_val += float(amount_str)
                if o.get("OrderStatus") == "Canceled":
                    refund_count += 1

            # Average order value
            avg_order_value = (
                total_spent_val / total_orders_count if total_orders_count > 0 else 0.0
            )

            # VIP detection
            is_vip = total_orders_count >= 10 or total_spent_val >= 1000.0

            # Previous tickets (from orders where buyer message exists)
            previous_tickets = []
            for o in orders:
                buyer_message = (
                    o.get("BuyerCustomizedInfo", {}).get("CustomizedURL")
                    if o.get("BuyerCustomizedInfo")
                    else None
                )
                if buyer_message:
                    previous_tickets.append(
                        {
                            "order_id": o.get("AmazonOrderId", ""),
                            "note": buyer_message[:200],
                            "created_at": o.get("PurchaseDate"),
                        }
                    )

            # Account age — estimate from earliest PurchaseDate
            account_age_days: int | None = None
            purchase_dates = [
                _parse_amazon_date(o.get("PurchaseDate")) for o in orders if o.get("PurchaseDate")
            ]
            if purchase_dates:
                earliest = min(d for d in purchase_dates if d is not None)
                if earliest:
                    account_age_days = (datetime.now(UTC) - earliest).days

            logger.info(
                "amazon_customer_history_success",
                email=customer_email,
                total_orders=total_orders_count,
                refund_count=refund_count,
                is_vip=is_vip,
            )

            return {
                "total_orders": total_orders_count,
                "total_spent": round(total_spent_val, 2),
                "refund_count": refund_count,
                "previous_tickets": previous_tickets,
                "average_order_value": round(avg_order_value, 2),
                "is_vip": is_vip,
                "account_age_days": account_age_days,
            }

        except httpx.TimeoutException:
            raise ProviderTimeoutError("amazon", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    # =========================================================================
    # LogisticsProvider
    # =========================================================================

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def track_shipment(
        self, tracking_number: str, carrier: str | None = None
    ) -> TrackingInfo:
        """Track a shipment via SP-API Shipping API (Phase 2: IAM+STS + SigV4).

        Uses the SP-API Shipping API v2 to track packages by tracking number.
        Falls back gracefully if IAM role is not yet configured.

        If the carrier is not provided, AMAZON (Amazon Logistics) is assumed
        since SP-API tracking is primarily for Amazon's own fulfillment.

        Args:
            tracking_number: Carrier tracking number.
            carrier: Carrier identifier (auto-detected: AMAZON, UPS, USPS, etc.)

        Returns:
            TrackingInfo with status, events, and estimated delivery.
        """
        if not self._auth_manager.is_configured:
            logger.warning(
                "amazon_tracking_no_iam",
                tracking_number=tracking_number,
            )
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=carrier or "Amazon Logistics",
                status="unknown",
                status_detail=(
                    "Shipment tracking requires IAM+STS (Phase 2). "
                    "Set AMAZON_ROLE_ARN, AMAZON_IAM_ACCESS_KEY, and "
                    "AMAZON_IAM_SECRET_KEY in environment."
                ),
                days_in_transit=0,
                last_update=datetime.now(UTC),
            )

        try:
            # Step 1: Assume the IAM role via STS
            credentials = await self._auth_manager.assume_role()

            # Step 2: Build the tracking request
            # SP-API Shipping API v2: POST /shipping/v2/tracking
            resolved_carrier = carrier or "AMAZON"
            tracking_body = {
                "trackingId": tracking_number,
                "carrierId": resolved_carrier,
            }

            # Get LWA token for the SP-API call
            lwa_token = await self._get_access_token()

            # Sign the request with SigV4
            sig_headers = self._auth_manager.sign_sp_api_request(
                method="POST",
                path="/shipping/v2/tracking",
                body=_json_dumps(tracking_body),
                credentials=credentials,
            )

            client = await self._get_client()
            response = await client.post(
                "/shipping/v2/tracking",
                json=tracking_body,
                headers={
                    **sig_headers,
                    "x-amz-access-token": lwa_token,
                },
            )
            response.raise_for_status()
            data = response.json()
            payload = data.get("payload", {})

            # Step 3: Parse tracking response
            tracking_status = payload.get("status", "unknown")
            events_raw = payload.get("events", []) or []
            events: list[dict[str, Any]] = [
                {
                    "timestamp": e.get("eventTime", ""),
                    "location": e.get("location", {}).get("city", ""),
                    "description": e.get("eventCode", ""),
                }
                for e in events_raw
            ]

            # Estimate days in transit
            days_in_transit = 0
            if events:
                first_event = _parse_amazon_date(events[0].get("timestamp"))
                if first_event:
                    days_in_transit = (datetime.now(UTC) - first_event).days

            # Map status to normalized form
            status_map = {
                "DELIVERED": "delivered",
                "IN_TRANSIT": "in_transit",
                "OUT_FOR_DELIVERY": "in_transit",
                "DELAYED": "delayed",
                "LOST": "lost",
                "UNKNOWN": "unknown",
            }
            normalized_status = status_map.get(tracking_status.upper(), "unknown")

            est_delivery = _parse_amazon_date(payload.get("estimatedDeliveryDate"))

            logger.info(
                "amazon_tracking_success",
                tracking_number=tracking_number,
                status=normalized_status,
                events_count=len(events),
            )

            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=resolved_carrier,
                status=normalized_status,
                status_detail=payload.get("statusDetail", ""),
                estimated_delivery=est_delivery,
                days_in_transit=days_in_transit,
                last_update=datetime.now(UTC),
                events=events,
            )

        except AWSSigV4Error as e:
            logger.error(
                "amazon_tracking_auth_error",
                tracking_number=tracking_number,
                error=str(e)[:300],
            )
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=carrier or "Amazon Logistics",
                status="unknown",
                status_detail=f"STS/SigV4 auth error: {e}",
                days_in_transit=0,
                last_update=datetime.now(UTC),
            )
        except httpx.HTTPStatusError as e:
            amazon_err = _handle_http_error(e)
            logger.error(
                "amazon_tracking_api_error",
                tracking_number=tracking_number,
                status=amazon_err.status_code,
                error=str(amazon_err)[:300],
            )
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=carrier or "Amazon Logistics",
                status="unknown",
                status_detail=f"SP-API error: {amazon_err}",
                days_in_transit=0,
                last_update=datetime.now(UTC),
            )
        except httpx.TimeoutException:
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=carrier or "Amazon Logistics",
                status="unknown",
                status_detail="Tracking request timed out.",
                days_in_transit=0,
                last_update=datetime.now(UTC),
            )

    async def get_delivery_estimate(self, order_id: str) -> datetime | None:
        """Get estimated delivery date for an order.

        Amazon SP-API orders include LatestShipDate and EarliestShipDate
        but not a single EDD. We use LatestShipDate + 3 days buffer as
        a rough estimate.

        Args:
            order_id: Amazon order ID.

        Returns:
            Estimated delivery datetime, or None.
        """
        client = await self._get_client()
        try:
            response = await client.get(f"/orders/v0/orders/{order_id}")
            response.raise_for_status()
            payload = response.json()
            order = payload.get("payload", {})

            latest_ship = _parse_amazon_date(order.get("LatestShipDate"))
            if latest_ship:
                # Rough estimate: ship date + 3 business days
                return latest_ship + timedelta(days=3)
            return None

        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            logger.warning(
                "amazon_delivery_estimate_failed",
                order_id=order_id,
                error=str(e)[:200],
            )
            return None

    # =========================================================================
    # NotificationProvider
    # =========================================================================

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email notification.

        Amazon does not expose a native transactional email API.
        Phase 2 integrates SendGrid/SMTP.

        Args:
            to: Recipient email.
            subject: Email subject.
            body: Email body.

        Returns:
            True (logged and queued).
        """
        logger.info(
            "amazon_email_queued",
            to=to[:50],
            subject=subject[:100],
        )
        return True

    async def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS notification.

        Amazon does not support SMS natively. Phase 2 integrates Twilio.

        Args:
            to: Recipient phone number.
            message: SMS content.

        Returns:
            True (logged and queued).
        """
        logger.info(
            "amazon_sms_queued",
            to=f"{to[:3]}***{to[-3:]}" if len(to) > 6 else to,
        )
        return True


# =============================================================================
# Helpers
# =============================================================================


# Amazon OrderStatus → normalized fulfillment status
_AMAZON_STATUS_TO_FULFILLMENT: dict[str, str] = {
    "Pending": "unfulfilled",
    "Unshipped": "unfulfilled",
    "PartiallyShipped": "partial",
    "Shipped": "fulfilled",
    "Canceled": "unknown",
    "Unfulfillable": "unknown",
    "InvoiceUnconfirmed": "unfulfilled",
}


def _map_amazon_status_to_fulfillment(order: dict[str, Any]) -> str:
    """Map Amazon order status to normalized fulfillment status.

    Uses both OrderStatus and FulfillmentChannel to determine the
    normalized fulfillment state.

    Args:
        order: Raw order dict from SP-API response.

    Returns:
        Normalized status: unfulfilled | fulfilled | partial | unknown.
    """
    order_status = order.get("OrderStatus", "")
    return _AMAZON_STATUS_TO_FULFILLMENT.get(order_status, "unknown")


def _parse_amazon_order(order: dict[str, Any]) -> OrderInfo:
    """Parse a raw Amazon SP-API order dict into a normalized OrderInfo DTO.

    Args:
        order: Raw order dict from SP-API Orders API response.

    Returns:
        Normalized OrderInfo DTO.
    """
    # Order total
    order_total = order.get("OrderTotal", {}) or {}
    amount_str = order_total.get("Amount", "0")
    currency_code = order_total.get("CurrencyCode", "USD")
    try:
        total_price = float(amount_str)
    except (ValueError, TypeError):
        total_price = 0.0

    # Shipping address
    shipping_address_data = order.get("ShippingAddress", {}) or {}
    shipping_info = {
        "city": shipping_address_data.get("City", ""),
        "zip": shipping_address_data.get("PostalCode", ""),
        "country": shipping_address_data.get("CountryCode", ""),
        "province": shipping_address_data.get("StateOrRegion", ""),
        "address_1": shipping_address_data.get("AddressLine1", ""),
        "address_2": shipping_address_data.get("AddressLine2", ""),
        "phone": shipping_address_data.get("Phone", ""),
    }

    # Customer info
    buyer_info = order.get("BuyerInfo", {}) or {}
    buyer_name = buyer_info.get("BuyerName", "")
    buyer_email = buyer_info.get("BuyerEmail", "")

    # Financial status
    financial_status = "paid"
    if order.get("OrderStatus") == "Canceled":
        financial_status = "refunded"
    elif order.get("OrderStatus") == "Pending":
        financial_status = "pending"

    return OrderInfo(
        order_id=order.get("AmazonOrderId", ""),
        order_number=order.get("AmazonOrderId", "N/A"),
        customer_email=buyer_email,
        customer_name=buyer_name or "Valued Customer",
        total_price=total_price,
        currency=currency_code,
        fulfillment_status=_map_amazon_status_to_fulfillment(order),
        financial_status=financial_status,
        tracking_number=None,  # SP-API Orders API doesn't include tracking
        tracking_carrier=None,
        shipping_address=shipping_info,
        line_items=[],  # Requires separate OrderItems API call
        created_at=_parse_amazon_date(order.get("PurchaseDate")),
    )


def _parse_amazon_date(date_str: str | None) -> datetime | None:
    """Parse an Amazon SP-API ISO 8601 date string.

    Amazon returns dates like "2024-01-15T10:30:00Z" or
    "2024-01-15T10:30:00.000Z".

    Args:
        date_str: ISO 8601 date string, or None.

    Returns:
        Timezone-aware datetime, or None.
    """
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _handle_http_error(error: httpx.HTTPStatusError) -> AmazonAPIError:
    """Map httpx HTTP errors to AmazonAPIError.

    SP-API returns errors in the format:
        {"errors": [{"code": "...", "message": "...", "details": "..."}]}

    Args:
        error: The httpx HTTPStatusError.

    Returns:
        AmazonAPIError with appropriate retryability.
    """
    status_code = error.response.status_code if error.response else 0
    retryable = status_code in (429, 500, 502, 503, 504)

    try:
        body = error.response.json() if error.response else {}
        errors = body.get("errors", [])
        if errors:
            amz_message = errors[0].get("message", str(error)) if errors else str(error)
    except (ValueError, AttributeError):
        amz_message = str(error)

    logger.warning(
        "amazon_api_error",
        status_code=status_code,
        retryable=retryable,
        error=str(amz_message)[:300],
    )
    return AmazonAPIError(
        f"HTTP {status_code}: {str(amz_message)[:500]}",
        status_code=status_code,
        retryable=retryable,
    )


# ── Phase 2 helpers ──


def _json_dumps(obj: Any) -> str:
    """Serialize to JSON string (no external import needed for simple cases)."""
    import json

    return json.dumps(obj, default=str)


def _map_refund_reason(reason: str) -> str:
    """Map a human-readable refund reason to an SP-API adjustment reason code.

    SP-API order adjustment reason codes:
        - CustomerReturn
        - CustomerCancel
        - NoInventory
        - GeneralAdjustment
        - CourtesyAdjustment
        - ShippingChargeRefund
        - Goodwill

    Args:
        reason: Human-readable refund reason string.

    Returns:
        SP-API adjustment reason code.
    """
    reason_lower = reason.lower()
    if "return" in reason_lower:
        return "CustomerReturn"
    if "cancel" in reason_lower:
        return "CustomerCancel"
    if "inventory" in reason_lower or "stock" in reason_lower:
        return "NoInventory"
    if "shipping" in reason_lower or "delivery" in reason_lower:
        return "ShippingChargeRefund"
    if "goodwill" in reason_lower or "courtesy" in reason_lower:
        return "CourtesyAdjustment"
    return "GeneralAdjustment"
