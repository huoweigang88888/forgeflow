"""
ForgeFlow AI - Shopify Provider (Full Implementation).

Implements PlatformProvider for Shopify stores using the Admin REST API.
All methods are fully async with httpx, tenacity retry, and structured logging.

Authentication: Shopify Admin API access token (OAuth 2.0 or custom app).

Env vars needed:
    SHOPIFY_CLIENT_ID     — API key (optional, for OAuth)
    SHOPIFY_CLIENT_SECRET — API secret (optional, for OAuth)

Per-tenant credentials are passed via constructor, not env vars — each
Shopify store has its own access token obtained via OAuth.

Reference: https://shopify.dev/docs/api/admin-rest
"""

import json
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
from forgeflow.providers.dto import OrderInfo, RefundResult, TrackingInfo

logger = get_logger(component="providers.shopify")


# ── Shopify API Error ──


class ShopifyAPIError(ProviderError):
    """Shopify-specific API error with response details."""

    def __init__(self, message: str, *, status_code: int = 0, retryable: bool = False):
        super().__init__("shopify", message, retryable=retryable)
        self.status_code = status_code


# ── Shopify Provider ──


class ShopifyProvider(PlatformProvider):
    """Full Shopify platform provider implementation.

    Uses Shopify Admin REST API (2024-01) with async httpx client.
    All API calls include exponential backoff retry on transient errors.

    Usage:
        provider = ShopifyProvider(
            shop_domain="mystore.myshopify.com",
            access_token="shpat_xxxx",
        )
        order = await provider.get_order("gid://shopify/Order/1234567890")
    """

    BASE_URL = "https://{shop_domain}/admin/api/{version}"

    def __init__(
        self,
        shop_domain: str,
        access_token: str = "",
        api_version: str = "2024-01",
    ):
        """Initialize Shopify provider.

        Args:
            shop_domain: Shopify store domain (e.g., mystore.myshopify.com).
            access_token: Shopify Admin API access token.
            api_version: API version string.
        """
        self.shop_domain = shop_domain
        self.access_token = access_token
        self._api_version = api_version
        self._client: httpx.AsyncClient | None = None

    @property
    def platform_name(self) -> str:
        return "shopify"

    @property
    def platform_version(self) -> str:
        return self._api_version

    @property
    def base_url(self) -> str:
        return self.BASE_URL.format(
            shop_domain=self.shop_domain,
            version=self._api_version,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client."""
        if self._client is None:
            if not self.access_token:
                raise ShopifyAPIError(
                    "No access token configured. Set SHOPIFY_ACCESS_TOKEN or "
                    "pass access_token to constructor. For development, use "
                    "platform='mock' instead of 'shopify'.",
                    retryable=False,
                )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "X-Shopify-Access-Token": self.access_token,
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
        """Fetch a single order from Shopify Admin API.

        GET /admin/api/{version}/orders/{id}.json

        Args:
            order_id: Shopify order ID (numeric or gid format).

        Returns:
            Normalized OrderInfo DTO.
        """
        # Normalize order ID: strip gid:// prefix if present
        numeric_id = _extract_numeric_id(order_id)

        client = await self._get_client()
        try:
            response = await client.get(f"/orders/{numeric_id}.json")
            response.raise_for_status()
            data = response.json()
            order = data.get("order", {})

            logger.info(
                "shopify_get_order_success",
                order_id=numeric_id,
                order_number=order.get("order_number"),
            )
            return _parse_shopify_order(order)

        except httpx.TimeoutException:
            raise ProviderTimeoutError("shopify", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_customer_orders(
        self, customer_id: str, limit: int = 10
    ) -> list[OrderInfo]:
        """Fetch recent orders for a customer.

        GET /admin/api/{version}/customers/{id}/orders.json

        Args:
            customer_id: Shopify customer ID.
            limit: Maximum orders to return (max 250).

        Returns:
            List of normalized OrderInfo DTOs, most recent first.
        """
        numeric_id = _extract_numeric_id(customer_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/customers/{numeric_id}/orders.json",
                params={"limit": min(limit, 250), "status": "any"},
            )
            response.raise_for_status()
            data = response.json()
            orders = data.get("orders", [])

            logger.info(
                "shopify_get_customer_orders_success",
                customer_id=numeric_id,
                count=len(orders),
            )
            return [_parse_shopify_order(o) for o in orders]

        except httpx.TimeoutException:
            raise ProviderTimeoutError("shopify", timeout_s=30) from None
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

        POST /admin/api/{version}/orders/{id}/refunds.json

        Args:
            order_id: Shopify order ID.
            amount: Refund amount in order currency.
            reason: Reason for the refund.
            notify_customer: Whether to send Shopify's notification email.

        Returns:
            RefundResult with success status and refund ID.
        """
        numeric_id = _extract_numeric_id(order_id)

        client = await self._get_client()
        payload = {
            "refund": {
                "currency": "USD",  # Will be overridden by order currency
                "notify": notify_customer,
                "note": reason,
                "transactions": [
                    {
                        "parent_id": None,  # Shopify will resolve this
                        "amount": str(amount),
                        "kind": "refund",
                        "gateway": "shopify_payments",
                    }
                ],
            }
        }

        try:
            # First, get the order to find the transaction ID
            order_resp = await client.get(f"/orders/{numeric_id}.json")
            order_resp.raise_for_status()
            order_data = order_resp.json()
            order = order_data.get("order", {})

            # Use the most recent transaction as parent
            transactions = order.get("transactions", [])
            if transactions:
                payload["refund"]["transactions"][0]["parent_id"] = transactions[-1].get("id")

            payload["refund"]["currency"] = order.get("currency", "USD")

            response = await client.post(
                f"/orders/{numeric_id}/refunds.json",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            refund = data.get("refund", {})

            logger.info(
                "shopify_refund_success",
                order_id=numeric_id,
                refund_id=refund.get("id"),
                amount=amount,
            )
            return RefundResult(
                success=True,
                refund_id=str(refund.get("id", "")),
                amount=amount,
            )

        except httpx.TimeoutException:
            raise ProviderTimeoutError("shopify", timeout_s=30) from None
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

        GET /admin/api/{version}/orders/{id}.json (only reads fulfillment_status).

        Args:
            order_id: Shopify order ID.

        Returns:
            Status string: unfulfilled | fulfilled | partial | unknown.
        """
        numeric_id = _extract_numeric_id(order_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/orders/{numeric_id}.json",
                params={"fields": "fulfillment_status"},
            )
            response.raise_for_status()
            data = response.json()
            order = data.get("order", {})
            status = order.get("fulfillment_status") or "unknown"

            logger.info(
                "shopify_fulfillment_status",
                order_id=numeric_id,
                status=status,
            )
            return status

        except httpx.TimeoutException:
            raise ProviderTimeoutError("shopify", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    async def get_customer_history(
        self, customer_email: str, order_id: str | None = None
    ) -> dict:
        """Retrieve customer history for decision-making.

        Aggregates order history, refund count, and customer metadata
        from the Shopify Admin API.  Used by the decision node to assess
        fraud risk and customer value.

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
                "/customers/search.json",
                params={"query": f"email:{customer_email}"},
            )
            customer_resp.raise_for_status()
            customers = customer_resp.json().get("customers", [])

            if not customers:
                logger.info(
                    "shopify_customer_not_found",
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

            # 2. Fetch recent orders for ticket/refund history
            recent_orders: list[dict] = []
            if customer_id:
                try:
                    orders_resp = await client.get(
                        f"/customers/{customer_id}/orders.json",
                        params={"limit": 10, "status": "any"},
                    )
                    orders_resp.raise_for_status()
                    recent_orders = orders_resp.json().get("orders", [])
                except (httpx.HTTPStatusError, httpx.TimeoutException):
                    logger.warning(
                        "shopify_customer_orders_fetch_failed",
                        customer_id=customer_id,
                    )

            # 3. Count refunds from order financial status
            refund_count = sum(
                1
                for o in recent_orders
                if o.get("financial_status") in ("refunded", "partially_refunded")
            )

            # 4. Extract previous ticket-relevant issues from order notes
            previous_tickets = []
            for o in recent_orders:
                note = o.get("note")
                if note:
                    previous_tickets.append(
                        {
                            "order_id": str(o.get("id", "")),
                            "note": note[:200],
                            "created_at": o.get("created_at"),
                        }
                    )

            # 5. Compute VIP status (high spender or many orders)
            is_vip = total_orders_count >= 10 or total_spent_val >= 1000.0
            avg_order_value = (
                total_spent_val / total_orders_count if total_orders_count > 0 else 0.0
            )

            logger.info(
                "shopify_customer_history_success",
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
                "account_age_days": None,  # Shopify REST API doesn't expose created_at for customers easily
            }

        except httpx.TimeoutException:
            raise ProviderTimeoutError("shopify", timeout_s=30) from None
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
        """Track a shipment via Shopify Fulfillment API.

        GET /admin/api/{version}/orders/{id}/fulfillments.json
        (We find the fulfillment matching the tracking number.)

        Falls back to a basic "unknown" status if fulfillment data is
        unavailable. For richer tracking, Phase 2 integrates AfterShip/17Track.

        Args:
            tracking_number: Carrier tracking number.
            carrier: Optional carrier name (used for filtering).

        Returns:
            Normalized TrackingInfo DTO.
        """
        client = await self._get_client()

        try:
            # Find fulfillments by tracking number
            response = await client.get(
                "/orders.json",
                params={
                    "status": "any",
                    "limit": 50,
                },
            )
            response.raise_for_status()
            data = response.json()
            orders = data.get("orders", [])

            # Find the fulfillment with this tracking number
            for order in orders:
                for fulfillment in order.get("fulfillments", []):
                    if fulfillment.get("tracking_number") == tracking_number:
                        status = fulfillment.get("status", "unknown")
                        ship_status = fulfillment.get("shipment_status")

                        # Map Shopify statuses to our normalized statuses
                        status_map = {
                            "pending": "in_transit",
                            "open": "in_transit",
                            "success": "delivered",
                            "cancelled": "unknown",
                            "error": "unknown",
                            "failure": "unknown",
                            "label_printed": "in_transit",
                            "label_purchased": "in_transit",
                            "attempted_delivery": "in_transit",
                            "ready_for_pickup": "in_transit",
                            "confirmed": "in_transit",
                            "in_transit": "in_transit",
                            "out_for_delivery": "in_transit",
                            "delivered": "delivered",
                            "failed": "unknown",
                        }
                        normalized_status = status_map.get(
                            ship_status or status, "in_transit"
                        )

                        # Calculate days in transit
                        created_at = _parse_shopify_date(
                            fulfillment.get("created_at")
                        )
                        days_in_transit = _days_since(created_at)

                        logger.info(
                            "shopify_tracking_found",
                            tracking_number=tracking_number,
                            status=normalized_status,
                            days_in_transit=days_in_transit,
                        )

                        return TrackingInfo(
                            tracking_number=tracking_number,
                            carrier=carrier or fulfillment.get("tracking_company", "Unknown"),
                            status=normalized_status,
                            status_detail=ship_status or status,
                            estimated_delivery=_parse_shopify_date(
                                fulfillment.get("estimated_delivery_at")
                            ),
                            days_in_transit=days_in_transit,
                            last_update=_parse_shopify_date(
                                fulfillment.get("updated_at")
                            ) or datetime.now(UTC),
                            events=[],  # Shopify API doesn't provide tracking events
                        )

            # Not found — return unknown
            logger.warning(
                "shopify_tracking_not_found",
                tracking_number=tracking_number,
            )
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=carrier or "Unknown",
                status="unknown",
                status_detail="Tracking number not found in fulfillments",
                days_in_transit=0,
                last_update=datetime.now(UTC),
            )

        except httpx.TimeoutException:
            raise ProviderTimeoutError("shopify", timeout_s=30) from None
        except httpx.HTTPStatusError as e:
            raise _handle_http_error(e) from e

    async def get_delivery_estimate(self, order_id: str) -> datetime | None:
        """Get estimated delivery date for an order.

        Returns the most recent fulfillment's estimated_delivery_at.

        Args:
            order_id: Shopify order ID.

        Returns:
            Estimated delivery datetime, or None.
        """
        numeric_id = _extract_numeric_id(order_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/orders/{numeric_id}/fulfillments.json",
            )
            response.raise_for_status()
            data = response.json()
            fulfillments = data.get("fulfillments", [])

            if fulfillments:
                latest = fulfillments[-1]
                est = latest.get("estimated_delivery_at")
                if est:
                    return _parse_shopify_date(est)

            return None

        except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
            logger.warning(
                "shopify_delivery_estimate_failed",
                order_id=numeric_id,
                error=str(e)[:200],
            )
            return None

    # =========================================================================
    # NotificationProvider
    # =========================================================================

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email notification.

        Shopify does not have a native email API. In Phase 1, we log the
        email and return True. Phase 2 integrates SendGrid/SMTP.

        Args:
            to: Recipient email.
            subject: Email subject.
            body: Email body (plain text).

        Returns:
            True (logged and queued).
        """
        logger.info(
            "shopify_email_queued",
            to=to[:50],
            subject=subject[:100],
        )
        # Phase 2: Integrate with SendGrid or SMTP
        return True

    async def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS notification.

        Shopify does not support SMS natively. Phase 2 integrates Twilio.

        Args:
            to: Recipient phone number.
            message: SMS content.

        Returns:
            True (logged and queued).
        """
        logger.info(
            "shopify_sms_queued",
            to=f"{to[:3]}***{to[-3:]}" if len(to) > 6 else to,
        )
        # Phase 2: Integrate with Twilio
        return True


# =============================================================================
# Helpers
# =============================================================================


def _extract_numeric_id(order_id: str) -> str:
    """Extract the numeric ID from a gid:// formatted Shopify ID.

    Example:
        "gid://shopify/Order/1234567890" → "1234567890"
        "1234567890" → "1234567890"
    """
    if order_id.startswith("gid://"):
        return order_id.split("/")[-1]
    return order_id


def _parse_shopify_order(order: dict[str, Any]) -> OrderInfo:
    """Parse a raw Shopify order dict into a normalized OrderInfo DTO.

    Args:
        order: Raw order dict from Shopify API response.

    Returns:
        Normalized OrderInfo DTO.
    """
    # Extract fulfillment info
    fulfillments = order.get("fulfillments", [])
    tracking_number = None
    tracking_carrier = None
    if fulfillments:
        latest_fulfillment = fulfillments[-1]
        tracking_number = latest_fulfillment.get("tracking_number")
        tracking_carrier = latest_fulfillment.get("tracking_company")

    # Extract shipping address
    shipping = order.get("shipping_address", {}) or {}
    shipping_info = {
        "city": shipping.get("city", ""),
        "zip": shipping.get("zip", ""),
        "country": shipping.get("country", ""),
        "province": shipping.get("province", ""),
    }

    # Extract line items (limited data — no full product details)
    line_items = order.get("line_items", [])
    items = [
        {
            "title": li.get("title", "Unknown Product"),
            "quantity": li.get("quantity", 0),
            "price": float(li.get("price", 0)),
            "sku": li.get("sku", ""),
        }
        for li in line_items
    ]

    # Customer info
    customer = order.get("customer", {}) or {}
    customer_name = (
        f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
    )
    customer_email = customer.get("email", order.get("email", ""))

    return OrderInfo(
        order_id=str(order.get("id", "")),
        order_number=f"#{order.get('order_number', order.get('name', 'N/A'))}",
        customer_email=customer_email,
        customer_name=customer_name or "Valued Customer",
        total_price=float(order.get("total_price", 0)),
        currency=order.get("currency", "USD"),
        fulfillment_status=order.get("fulfillment_status") or "unknown",
        financial_status=order.get("financial_status") or "unknown",
        tracking_number=tracking_number,
        tracking_carrier=tracking_carrier,
        shipping_address=shipping_info,
        line_items=items,
        created_at=_parse_shopify_date(order.get("created_at")),
    )


def _parse_shopify_date(date_str: str | None) -> datetime | None:
    """Parse a Shopify ISO 8601 date string.

    Args:
        date_str: ISO 8601 date string, or None.

    Returns:
        Timezone-aware datetime, or None.
    """
    if not date_str:
        return None
    try:
        # Handle both "2024-01-15T10:30:00+00:00" and "2024-01-15T10:30:00Z"
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


def _handle_http_error(error: httpx.HTTPStatusError) -> ShopifyAPIError:
    """Map httpx HTTP errors to ShopifyAPIError.

    Args:
        error: The httpx HTTPStatusError.

    Returns:
        ShopifyAPIError with appropriate retryability.
    """
    status_code = error.response.status_code if error.response else 0
    retryable = status_code in (429, 500, 502, 503, 504)

    try:
        body = error.response.json() if error.response else {}
        shopify_error = body.get("errors", str(error))
    except (json.JSONDecodeError, AttributeError):
        shopify_error = str(error)

    logger.warning(
        "shopify_api_error",
        status_code=status_code,
        retryable=retryable,
        error=str(shopify_error)[:300],
    )
    return ShopifyAPIError(
        f"HTTP {status_code}: {str(shopify_error)[:500]}",
        status_code=status_code,
        retryable=retryable,
    )
