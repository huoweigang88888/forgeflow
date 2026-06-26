"""
ForgeFlow AI - Platform Provider Abstract Interfaces.

Defines the abstract base classes for all e-commerce platform providers.
The Agent Runtime depends ONLY on these interfaces, never on concrete
implementations. This enables:

- V1: Shopify only
- V2: Add WooCommerce, Amazon (zero Agent code changes)
- Testing: Mock providers for deterministic tests

From PRD Section 17: Multi-Platform Abstraction Design.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from forgeflow.providers.dto import ExchangeResult, OrderInfo, RefundResult, TrackingInfo

# =============================================================================
# Sub-Providers (can be implemented independently)
# =============================================================================


class OrderProvider(ABC):
    """Order data source abstraction.

    Implementations: ShopifyOrderProvider, WooCommerceOrderProvider, etc.
    """

    @abstractmethod
    async def get_order(self, order_id: str) -> OrderInfo:
        """Retrieve a single order by its platform-native ID.

        Args:
            order_id: Platform order ID (e.g., Shopify order ID).

        Returns:
            Normalized OrderInfo DTO.

        Raises:
            ProviderError: If the order is not found or the API fails.
        """
        ...

    @abstractmethod
    async def get_customer_orders(self, customer_id: str, limit: int = 10) -> list[OrderInfo]:
        """Retrieve recent orders for a customer.

        Args:
            customer_id: Platform customer ID.
            limit: Maximum number of orders to return.

        Returns:
            List of normalized OrderInfo DTOs, most recent first.
        """
        ...

    @abstractmethod
    async def create_refund(
        self,
        order_id: str,
        amount: float,
        reason: str,
        notify_customer: bool = True,
    ) -> RefundResult:
        """Process a refund for an order.

        Args:
            order_id: Platform order ID.
            amount: Refund amount in order currency.
            reason: Reason for the refund.
            notify_customer: Whether to send notification email.

        Returns:
            RefundResult indicating success/failure.
        """
        ...

    @abstractmethod
    async def get_fulfillment_status(self, order_id: str) -> str:
        """Get the fulfillment status of an order.

        Args:
            order_id: Platform order ID.

        Returns:
            Status string: unfulfilled | fulfilled | partial | unknown.
        """
        ...

    @abstractmethod
    async def create_exchange(
        self,
        order_id: str,
        reason: str,
        exchange_items: list[dict[str, Any]] | None = None,
        notify_customer: bool = True,
    ) -> ExchangeResult:
        """Initiate an exchange/return for an order.

        Creates a return label and (optionally) a replacement order.

        Args:
            order_id: Platform order ID.
            reason: Reason for the exchange.
            exchange_items: Optional list of line items to exchange
                (defaults to all items).
            notify_customer: Whether to send notification email.

        Returns:
            ExchangeResult with return label and replacement info.
        """
        ...

    @abstractmethod
    async def get_customer_history(
        self, customer_email: str, order_id: str | None = None
    ) -> dict[str, Any]:
        """Retrieve customer history for decision-making.

        Args:
            customer_email: Customer email address.
            order_id: Optional related order ID for context.

        Returns:
            Dict with keys:
                total_orders (int), total_spent (float), refund_count (int),
                previous_tickets (list), average_order_value (float),
                is_vip (bool), account_age_days (int|None).
        """
        ...


class LogisticsProvider(ABC):
    """Logistics/shipment tracking abstraction.

    Implementations: AfterShipProvider, 17TrackProvider, etc.
    """

    @abstractmethod
    async def track_shipment(
        self, tracking_number: str, carrier: str | None = None
    ) -> TrackingInfo:
        """Query shipment tracking status.

        Args:
            tracking_number: Carrier tracking number.
            carrier: Carrier identifier (optional, auto-detected if not provided).

        Returns:
            Normalized TrackingInfo DTO.
        """
        ...

    @abstractmethod
    async def get_delivery_estimate(self, order_id: str) -> datetime | None:
        """Get estimated delivery date for an order.

        Args:
            order_id: Platform order ID.

        Returns:
            Estimated delivery datetime, or None if unavailable.
        """
        ...


class NotificationProvider(ABC):
    """Customer notification abstraction.

    Implementations: EmailProvider, SMSProvider, WeChatProvider, etc.
    """

    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email notification.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Email body (plain text or HTML).

        Returns:
            True if sent successfully.
        """
        ...

    @abstractmethod
    async def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS notification.

        Args:
            to: Recipient phone number.
            message: SMS content.

        Returns:
            True if sent successfully.
        """
        ...


# =============================================================================
# Combined Platform Interface
# =============================================================================


class PlatformProvider(OrderProvider, LogisticsProvider, NotificationProvider, ABC):
    """Complete platform interface — combines all sub-provider capabilities.

    Each e-commerce platform (Shopify, WooCommerce, Amazon) implements this
    full interface. The Agent Runtime resolves the correct provider via
    ProviderRegistry based on the tenant's platform.

    Usage in agent nodes:
        # Node depends on narrow interface for testability
        async def lookup_order_node(state, order_provider: OrderProvider):
            order = await order_provider.get_order(state["order_id"])

        # Runtime resolves full PlatformProvider
        provider = registry.get("shopify", api_key=..., domain=...)
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier: 'shopify' | 'woocommerce' | 'amazon'."""
        ...

    @property
    @abstractmethod
    def platform_version(self) -> str:
        """Return the API version string (e.g., '2024-01')."""
        ...
