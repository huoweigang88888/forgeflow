"""
ForgeFlow AI - Mock Platform Provider.

Deterministic mock provider for testing agent nodes without real API calls.
Returns fake but realistic data for all provider methods.

Usage in tests:
    mock = MockPlatformProvider()
    order = await mock.get_order("order_123")
    assert order.total_price == 45.60
"""

from datetime import UTC, datetime, timedelta

from forgeflow.providers.base import PlatformProvider
from forgeflow.providers.dto import OrderInfo, RefundResult, TrackingInfo


class MockPlatformProvider(PlatformProvider):
    """Mock provider returning deterministic test data.

    Used for:
    - Unit tests for individual agent nodes
    - Integration tests without real API dependencies
    - CI/CD pipeline (no external service dependencies)
    """

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._overrides = kwargs.get("mock_overrides", {})

    @property
    def platform_name(self) -> str:
        return "mock"

    @property
    def platform_version(self) -> str:
        return "1.0.0-test"

    # =========================================================================
    # OrderProvider
    # =========================================================================

    async def get_order(self, order_id: str) -> OrderInfo:
        """Return a mock order with realistic data, respecting overrides."""
        order_override = self._overrides.get("order", {})
        customer_override = self._overrides.get("customer_history", {})
        return OrderInfo(
            order_id=order_id,
            order_number=f"#{order_id[-5:]}",
            customer_email=customer_override.get("email", "customer@example.com"),
            customer_name=customer_override.get("name", "John Doe"),
            total_price=order_override.get("total_price", 45.60),
            currency=order_override.get("currency", "USD"),
            fulfillment_status=order_override.get("fulfillment_status", "fulfilled"),
            financial_status=order_override.get("financial_status", "paid"),
            tracking_number=order_override.get("tracking_number", "TRACK123456789"),
            tracking_carrier=order_override.get("tracking_carrier", "UPS"),
            shipping_address=order_override.get("shipping_address", {
                "city": "New York",
                "zip": "10001",
                "country": "US",
            }),
            line_items=order_override.get("line_items", [
                {"title": "Test Product", "quantity": 1, "price": 45.60},
            ]),
            created_at=datetime.now(UTC) - timedelta(days=5),
        )

    async def get_customer_orders(
        self, customer_id: str, limit: int = 10
    ) -> list[OrderInfo]:
        """Return mock customer order history."""
        return [
            await self.get_order(f"order_{i:03d}")
            for i in range(min(limit, 3))
        ]

    async def create_refund(
        self,
        order_id: str,
        amount: float,
        reason: str,
        notify_customer: bool = True,
    ) -> RefundResult:
        """Return a successful mock refund."""
        return RefundResult(
            success=True,
            refund_id=f"refund_{order_id}",
            amount=amount,
        )

    async def get_fulfillment_status(self, order_id: str) -> str:
        """Return mock fulfillment status."""
        return "fulfilled"

    async def get_customer_history(
        self, customer_email: str, order_id: str | None = None
    ) -> dict:
        """Return mock customer history, respecting overrides."""
        hist_override = self._overrides.get("customer_history", {})
        return {
            "total_orders": hist_override.get("total_orders", 3),
            "total_spent": hist_override.get("total_spent", 156.75),
            "refund_count": hist_override.get("refund_count", 0),
            "previous_tickets": hist_override.get("previous_tickets", []),
            "average_order_value": hist_override.get("average_order_value", 52.25),
            "is_vip": hist_override.get("is_vip", False),
            "account_age_days": hist_override.get("account_age_days", 180),
        }

    # =========================================================================
    # LogisticsProvider
    # =========================================================================

    async def track_shipment(
        self, tracking_number: str, carrier: str | None = None
    ) -> TrackingInfo:
        """Return mock tracking info, respecting overrides."""
        logistics_override = self._overrides.get("logistics", {})
        now = datetime.now(UTC)
        status = logistics_override.get("status", "in_transit")
        days = logistics_override.get("days_in_transit", 2)
        return TrackingInfo(
            tracking_number=tracking_number,
            carrier=carrier or "UPS",
            status=status,
            status_detail=logistics_override.get("status_detail", "Package is on its way"),
            estimated_delivery=now + timedelta(days=max(0, 7 - days)),
            days_in_transit=days,
            last_update=now - timedelta(hours=4),
            events=[
                {
                    "timestamp": (now - timedelta(days=2)).isoformat(),
                    "location": "Los Angeles, CA",
                    "status": "Package departed facility",
                },
                {
                    "timestamp": (now - timedelta(hours=4)).isoformat(),
                    "location": "Kansas City, MO",
                    "status": "Package in transit",
                },
            ],
        )

    async def get_delivery_estimate(self, order_id: str) -> datetime | None:
        """Return mock delivery estimate."""
        return datetime.now(UTC) + timedelta(days=3)

    # =========================================================================
    # NotificationProvider
    # =========================================================================

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Mock: always succeeds."""
        return True

    async def send_sms(self, to: str, message: str) -> bool:
        """Mock: always succeeds."""
        return True
