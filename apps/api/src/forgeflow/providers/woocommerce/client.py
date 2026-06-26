"""
ForgeFlow AI - WooCommerce Provider.

Implements PlatformProvider for WooCommerce stores using the REST API v3.
All methods are fully async with httpx, tenacity retry, and structured logging.

Authentication: WooCommerce Consumer Key + Consumer Secret (HTTP Basic Auth).

Per-tenant credentials are passed via constructor:
    provider = WooCommerceProvider(
        store_url="https://mystore.com",
        consumer_key="ck_xxxx",
        consumer_secret="cs_xxxx",
    )

Reference: https://woocommerce.com/document/woocommerce-rest-api/
"""

from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forgeflow.core.exceptions import (
    ProviderError,
    ProviderTimeoutError,
)
from forgeflow.monitoring.logger import get_logger
from forgeflow.providers.base import PlatformProvider
from forgeflow.providers.dto import ExchangeResult, OrderInfo, RefundResult, TrackingInfo

logger = get_logger(component="providers.woocommerce")


# ── WooCommerce API Error ──


class WooCommerceAPIError(ProviderError):
    """WooCommerce-specific API error with response details."""

    def __init__(self, message: str, *, status_code: int = 0, retryable: bool = False):
        super().__init__("woocommerce", message, retryable=retryable)
        self.status_code = status_code


# ── WooCommerce Provider ──


class WooCommerceProvider(PlatformProvider):
    """WooCommerce platform provider implementation.

    Uses WooCommerce REST API v3 with HTTP Basic Auth (consumer key + secret).
    All API calls include exponential backoff retry on transient errors.

    Usage:
        provider = WooCommerceProvider(
            store_url="https://mystore.com",
            consumer_key="ck_xxxx",
            consumer_secret="cs_xxxx",
        )
        order = await provider.get_order("727")
    """

    API_PATH = "/wp-json/wc/v3"

    def __init__(
        self,
        store_url: str,
        consumer_key: str = "",
        consumer_secret: str = "",
        api_version: str = "wc/v3",
    ):
        """Initialize WooCommerce provider.

        Args:
            store_url: WooCommerce store URL (e.g., https://mystore.com).
            consumer_key: WooCommerce REST API consumer key.
            consumer_secret: WooCommerce REST API consumer secret.
            api_version: API version string (informational only).
        """
        self.store_url = store_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self._api_version = api_version
        self._client: httpx.AsyncClient | None = None

    @property
    def platform_name(self) -> str:
        return "woocommerce"

    @property
    def platform_version(self) -> str:
        return self._api_version

    @property
    def base_url(self) -> str:
        return f"{self.store_url}{self.API_PATH}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client with Basic Auth."""
        if self._client is None:
            if not self.consumer_key or not self.consumer_secret:
                raise WooCommerceAPIError(
                    "No API credentials configured. Pass consumer_key and "
                    "consumer_secret to constructor. For development, use "
                    "platform='mock' instead of 'woocommerce'.",
                    retryable=False,
                )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.consumer_key, self.consumer_secret),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
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
        """Fetch a single order from WooCommerce REST API.

        GET /wp-json/wc/v3/orders/{id}

        Args:
            order_id: WooCommerce order ID (numeric string).

        Returns:
            Normalized OrderInfo DTO.
        """
        client = await self._get_client()
        try:
            response = await client.get(f"/orders/{order_id}")
            response.raise_for_status()
            order = response.json()

            logger.info(
                "woocommerce_get_order_success",
                order_id=order_id,
                order_number=order.get("number"),
            )
            return _parse_woocommerce_order(order)

        except httpx.TimeoutException:
            raise ProviderTimeoutError("woocommerce", timeout_s=30) from None
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

        WooCommerce REST API v3 does not expose a direct customer-orders
        endpoint.  We query orders filtered by customer_id.

        GET /wp-json/wc/v3/orders?customer={customer_id}&per_page={limit}

        Args:
            customer_id: WooCommerce customer ID (numeric).
            limit: Maximum orders to return.

        Returns:
            List of normalized OrderInfo DTOs, most recent first.
        """
        client = await self._get_client()
        try:
            response = await client.get(
                "/orders",
                params={
                    "customer": int(customer_id),
                    "per_page": min(limit, 100),
                    "orderby": "date",
                    "order": "desc",
                },
            )
            response.raise_for_status()
            orders = response.json()

            logger.info(
                "woocommerce_get_customer_orders_success",
                customer_id=customer_id,
                count=len(orders),
            )
            return [_parse_woocommerce_order(o) for o in orders]

        except httpx.TimeoutException:
            raise ProviderTimeoutError("woocommerce", timeout_s=30) from None
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
        """Process a refund for an order.

        POST /wp-json/wc/v3/orders/{id}/refunds

        Args:
            order_id: WooCommerce order ID.
            amount: Refund amount in order currency.
            reason: Reason for the refund.
            notify_customer: Whether to send notification email.

        Returns:
            RefundResult with success status and refund ID.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "amount": str(amount),
            "reason": reason,
            "api_refund": True,  # Use WooCommerce payment gateway refund
        }

        try:
            response = await client.post(
                f"/orders/{order_id}/refunds",
                json=payload,
            )
            response.raise_for_status()
            refund = response.json()

            logger.info(
                "woocommerce_refund_success",
                order_id=order_id,
                refund_id=refund.get("id"),
                amount=amount,
            )
            return RefundResult(
                success=True,
                refund_id=str(refund.get("id", "")),
                amount=amount,
            )

        except httpx.TimeoutException:
            raise ProviderTimeoutError("woocommerce", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def create_exchange(
        self,
        order_id: str,
        reason: str,
        exchange_items: list[dict[str, Any]] | None = None,
        notify_customer: bool = True,
    ) -> ExchangeResult:
        """Initiate an exchange/return for a WooCommerce order.

        WooCommerce handles exchanges by creating a refund with restock
        items enabled. A replacement order must be created manually or
        via a separate plugin API.

        POST /wp-json/wc/v3/orders/{id}/refunds
        with ``line_items`` for the items being exchanged.

        Args:
            order_id: WooCommerce order ID.
            reason: Reason for the exchange.
            exchange_items: Optional line items to exchange.
            notify_customer: Whether to send notification.

        Returns:
            ExchangeResult with refund/exchange ID.
        """
        client = await self._get_client()
        payload: dict[str, Any] = {
            "amount": "0.00",  # Exchange is $0 refund
            "reason": f"Exchange: {reason}",
            "api_refund": False,
            "restock_items": True,  # Return items to inventory
        }

        if exchange_items:
            payload["line_items"] = exchange_items

        try:
            response = await client.post(
                f"/orders/{order_id}/refunds",
                json=payload,
            )
            response.raise_for_status()
            refund = response.json()

            logger.info(
                "woocommerce_exchange_success",
                order_id=order_id,
                exchange_id=refund.get("id"),
            )
            return ExchangeResult(
                success=True,
                exchange_id=str(refund.get("id", "")),
                return_label_url=None,
                replacement_order_id=None,
                amount=0.0,
            )

        except httpx.TimeoutException:
            raise ProviderTimeoutError("woocommerce", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_fulfillment_status(self, order_id: str) -> str:
        """Get the fulfillment status of an order.

        WooCommerce orders use a unified "status" field rather than a
        separate "fulfillment_status".  We map order status to our
        normalized fulfillment status.

        GET /wp-json/wc/v3/orders/{id} (reads only status).

        Args:
            order_id: WooCommerce order ID.

        Returns:
            Status string: unfulfilled | fulfilled | partial | unknown.
        """
        client = await self._get_client()
        try:
            response = await client.get(
                f"/orders/{order_id}",
                params={"_fields": "status"},
            )
            response.raise_for_status()
            data = response.json()
            wc_status = data.get("status", "")

            normalized = _map_wc_status_to_fulfillment(wc_status)

            logger.info(
                "woocommerce_fulfillment_status",
                order_id=order_id,
                wc_status=wc_status,
                normalized=normalized,
            )
            return normalized

        except httpx.TimeoutException:
            raise ProviderTimeoutError("woocommerce", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    async def get_customer_history(
        self, customer_email: str, order_id: str | None = None
    ) -> dict[str, Any]:
        """Retrieve customer history for decision-making.

        Aggregates order history, refund count, and customer metadata
        from the WooCommerce REST API.

        Args:
            customer_email: Customer email address.
            order_id: Optional related order ID for context.

        Returns:
            Dict with total_orders, total_spent, refund_count,
            previous_tickets, average_order_value, is_vip, account_age_days.
        """
        client = await self._get_client()

        try:
            # 1. Search for customer by email
            customer_resp = await client.get(
                "/customers",
                params={"email": customer_email, "per_page": 1},
            )
            customer_resp.raise_for_status()
            customers = customer_resp.json()

            if not customers:
                logger.info(
                    "woocommerce_customer_not_found",
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

            customer = customers[0]
            customer_id = customer.get("id")
            total_orders_count = customer.get("orders_count", 0)
            total_spent_val = float(customer.get("total_spent", "0") or "0")
            account_created = _parse_woocommerce_date(customer.get("date_created"))

            # 2. Fetch recent orders for refund/ticket history
            recent_orders: list[dict[str, Any]] = []
            if customer_id:
                try:
                    orders_resp = await client.get(
                        "/orders",
                        params={
                            "customer": int(customer_id),
                            "per_page": 10,
                            "orderby": "date",
                            "order": "desc",
                        },
                    )
                    orders_resp.raise_for_status()
                    recent_orders = orders_resp.json()
                except (httpx.HTTPStatusError, httpx.TimeoutException):
                    logger.warning(
                        "woocommerce_customer_orders_fetch_failed",
                        customer_id=customer_id,
                    )

            # 3. Count refunds from order status
            refund_count = sum(1 for o in recent_orders if o.get("status") == "refunded")

            # 4. Extract notes from orders with customer notes
            previous_tickets = []
            for o in recent_orders:
                note = o.get("customer_note")
                if note:
                    previous_tickets.append(
                        {
                            "order_id": str(o.get("id", "")),
                            "note": note[:200],
                            "created_at": o.get("date_created"),
                        }
                    )

            # 5. Compute VIP status
            is_vip = total_orders_count >= 10 or total_spent_val >= 1000.0
            avg_order_value = (
                total_spent_val / total_orders_count if total_orders_count > 0 else 0.0
            )

            # Compute account age
            account_age_days: int | None = None
            if account_created:
                account_age_days = (datetime.now(UTC) - account_created).days

            logger.info(
                "woocommerce_customer_history_success",
                email=customer_email,
                total_orders=total_orders_count,
                refund_count=refund_count,
                is_vip=is_vip,
            )

            return {
                "total_orders": total_orders_count,
                "total_spent": total_spent_val,
                "refund_count": refund_count,
                "previous_tickets": previous_tickets,
                "average_order_value": round(avg_order_value, 2),
                "is_vip": is_vip,
                "account_age_days": account_age_days,
            }

        except httpx.TimeoutException:
            raise ProviderTimeoutError("woocommerce", timeout_s=30) from None
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
        """Track a shipment by searching recent orders' shipping lines.

        WooCommerce does not have native shipment tracking.  This method
        searches recent completed orders for matching tracking numbers
        in the ``shipping_lines`` and ``meta_data``.

        Falls back to "unknown" status if no match found.  Phase 2 can
        integrate AfterShip/17Track for richer carrier-level tracking.

        Args:
            tracking_number: Carrier tracking number.
            carrier: Optional carrier name.

        Returns:
            Normalized TrackingInfo DTO.
        """
        client = await self._get_client()

        try:
            # Search recent orders with meta_data containing the tracking number
            response = await client.get(
                "/orders",
                params={
                    "status": "completed",
                    "per_page": 50,
                    "orderby": "date",
                    "order": "desc",
                },
            )
            response.raise_for_status()
            orders = response.json()

            for order in orders:
                # Check shipping_lines for tracking info
                shipping_lines = order.get("shipping_lines", [])
                for shipping in shipping_lines:
                    meta_items = shipping.get("meta_data", [])
                    for meta in meta_items:
                        if meta.get("value") == tracking_number:
                            track_carrier = carrier
                            if not track_carrier:
                                track_carrier = shipping.get("method_title", "Unknown")

                            days_in_transit = _days_since(
                                _parse_woocommerce_date(order.get("date_completed"))
                            )

                            logger.info(
                                "woocommerce_tracking_found",
                                tracking_number=tracking_number,
                                carrier=track_carrier,
                                order_id=order.get("id"),
                            )

                            return TrackingInfo(
                                tracking_number=tracking_number,
                                carrier=track_carrier,
                                status="delivered"
                                if order.get("status") == "completed"
                                else "in_transit",
                                status_detail=order.get("status", "unknown"),
                                days_in_transit=days_in_transit,
                                last_update=_parse_woocommerce_date(order.get("date_modified"))
                                or datetime.now(UTC),
                            )

            # Not found
            logger.warning(
                "woocommerce_tracking_not_found",
                tracking_number=tracking_number,
            )
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=carrier or "Unknown",
                status="unknown",
                status_detail="Tracking number not found in recent orders",
                days_in_transit=0,
                last_update=datetime.now(UTC),
            )

        except httpx.TimeoutException:
            raise ProviderTimeoutError("woocommerce", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    async def get_delivery_estimate(self, order_id: str) -> datetime | None:
        """Get estimated delivery date for an order.

        WooCommerce doesn't have a native EDD field.  Some plugins
        (e.g., WooCommerce Shipment Tracking) store it in meta_data.
        We attempt to extract it; return None if unavailable.

        Args:
            order_id: WooCommerce order ID.

        Returns:
            Estimated delivery datetime, or None.
        """
        client = await self._get_client()
        try:
            response = await client.get(
                f"/orders/{order_id}",
                params={"_fields": "meta_data,date_completed"},
            )
            response.raise_for_status()
            data = response.json()

            # Check meta_data for tracking plugin fields
            for meta in data.get("meta_data", []):
                key = meta.get("key", "")
                if key in (
                    "_tracking_estimated_delivery",
                    "_estimated_delivery_date",
                    "estimated_delivery",
                    "_wc_shipment_tracking_est_delivery",
                ):
                    est = _parse_woocommerce_date(meta.get("value"))
                    if est:
                        return est

            return None

        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            logger.warning(
                "woocommerce_delivery_estimate_failed",
                order_id=order_id,
                error=str(e)[:200],
            )
            return None

    # =========================================================================
    # NotificationProvider
    # =========================================================================

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email notification.

        WooCommerce does not expose a native transactional email API.
        In V2, we log the email and return True.  Phase 2 integrates
        SendGrid/SMTP or the WP Mail API.

        Args:
            to: Recipient email.
            subject: Email subject.
            body: Email body.

        Returns:
            True (logged and queued).
        """
        logger.info(
            "woocommerce_email_queued",
            to=to[:50],
            subject=subject[:100],
        )
        return True

    async def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS notification.

        WooCommerce does not support SMS natively.  Phase 2 integrates Twilio.

        Args:
            to: Recipient phone number.
            message: SMS content.

        Returns:
            True (logged and queued).
        """
        logger.info(
            "woocommerce_sms_queued",
            to=f"{to[:3]}***{to[-3:]}" if len(to) > 6 else to,
        )
        return True


# =============================================================================
# Helpers
# =============================================================================


# WooCommerce status → our normalized fulfillment status
_WC_STATUS_TO_FULFILLMENT: dict[str, str] = {
    "pending": "unfulfilled",
    "processing": "unfulfilled",
    "on-hold": "unfulfilled",
    "completed": "fulfilled",
    "cancelled": "unknown",
    "refunded": "unknown",
    "failed": "unknown",
    "checkout-draft": "unfulfilled",
}


def _map_wc_status_to_fulfillment(wc_status: str) -> str:
    """Map WooCommerce order status to normalized fulfillment status.

    Args:
        wc_status: WooCommerce order status string.

    Returns:
        Normalized status: unfulfilled | fulfilled | partial | unknown.
    """
    return _WC_STATUS_TO_FULFILLMENT.get(wc_status, "unknown")


def _parse_woocommerce_order(order: dict[str, Any]) -> OrderInfo:
    """Parse a raw WooCommerce order dict into a normalized OrderInfo DTO.

    Args:
        order: Raw order dict from WooCommerce REST API response.

    Returns:
        Normalized OrderInfo DTO.
    """
    # Extract tracking from shipping_lines meta_data
    tracking_number: str | None = None
    tracking_carrier: str | None = None
    shipping_lines = order.get("shipping_lines", [])
    for shipping in shipping_lines:
        method_title = shipping.get("method_title", "")
        meta_items = shipping.get("meta_data", [])
        for meta in meta_items:
            key = meta.get("key", "").lower()
            if "tracking" in key:
                tracking_number = str(meta.get("value", ""))
                if method_title:
                    tracking_carrier = method_title

    # Also check order-level meta_data for tracking plugins
    if not tracking_number:
        for meta in order.get("meta_data", []):
            key = meta.get("key", "").lower()
            if key in (
                "_tracking_number",
                "_wc_shipment_tracking_number",
                "tracking_number",
            ):
                tracking_number = str(meta.get("value", ""))

    # Extract shipping address
    shipping = order.get("shipping", {}) or {}
    shipping_info = {
        "city": shipping.get("city", ""),
        "zip": shipping.get("postcode", ""),
        "country": shipping.get("country", ""),
        "province": shipping.get("state", ""),
        "address_1": shipping.get("address_1", ""),
    }

    # Extract line items
    line_items = order.get("line_items", [])
    items = [
        {
            "title": li.get("name", "Unknown Product"),
            "quantity": li.get("quantity", 0),
            "price": float(li.get("price", 0)),
            "sku": li.get("sku", ""),
            "product_id": li.get("product_id"),
        }
        for li in line_items
    ]

    # Customer info
    billing = order.get("billing", {}) or {}
    customer_name = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip()
    customer_email = billing.get("email", "")

    return OrderInfo(
        order_id=str(order.get("id", "")),
        order_number=f"#{order.get('number', order.get('id', 'N/A'))}",
        customer_email=customer_email,
        customer_name=customer_name or "Valued Customer",
        total_price=float(order.get("total", 0)),
        currency=order.get("currency", "USD"),
        fulfillment_status=_map_wc_status_to_fulfillment(order.get("status", "")),
        financial_status="paid" if order.get("date_paid") else "pending",
        tracking_number=tracking_number,
        tracking_carrier=tracking_carrier,
        shipping_address=shipping_info,
        line_items=items,
        created_at=_parse_woocommerce_date(order.get("date_created")),
    )


def _parse_woocommerce_date(date_str: str | None) -> datetime | None:
    """Parse a WooCommerce ISO 8601 date string.

    WooCommerce returns dates in the format "2024-01-15T10:30:00"
    (without timezone — site-local time).  We treat them as UTC for
    simplicity in after-sales workflows.

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


def _days_since(dt: datetime | None) -> int:
    """Calculate days since a given datetime.

    Args:
        dt: A datetime, or None.

    Returns:
        Number of days since, or 0 if None.
    """
    if dt is None:
        return 0
    delta = datetime.now(UTC) - dt
    return max(0, delta.days)


def _handle_http_error(error: httpx.HTTPStatusError) -> WooCommerceAPIError:
    """Map httpx HTTP errors to WooCommerceAPIError.

    WooCommerce REST API returns errors in the format:
        {"code": "...", "message": "...", "data": {"status": 400}}

    Args:
        error: The httpx HTTPStatusError.

    Returns:
        WooCommerceAPIError with appropriate retryability.
    """
    status_code = error.response.status_code if error.response else 0
    retryable = status_code in (429, 500, 502, 503, 504)

    try:
        body = error.response.json() if error.response else {}
        wc_message = body.get("message", str(error))
    except (ValueError, AttributeError):
        wc_message = str(error)

    logger.warning(
        "woocommerce_api_error",
        status_code=status_code,
        retryable=retryable,
        error=str(wc_message)[:300],
    )
    return WooCommerceAPIError(
        f"HTTP {status_code}: {str(wc_message)[:500]}",
        status_code=status_code,
        retryable=retryable,
    )
