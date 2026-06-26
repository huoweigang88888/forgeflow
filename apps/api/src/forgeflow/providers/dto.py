"""
ForgeFlow AI - Provider Data Transfer Objects (DTOs).

Platform-agnostic data structures for the Provider abstraction layer.
All DTOs are frozen dataclasses for immutability safety — agent nodes
cannot accidentally mutate provider responses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class OrderInfo:
    """Normalized order data from any e-commerce platform."""

    order_id: str
    order_number: str
    customer_email: str
    customer_name: str
    total_price: float
    currency: str
    fulfillment_status: str  # unfulfilled | fulfilled | partial
    financial_status: str
    tracking_number: str | None = None
    tracking_carrier: str | None = None
    shipping_address: dict[str, Any] = field(default_factory=dict)
    line_items: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass(frozen=True)
class RefundResult:
    """Result of a refund operation."""

    success: bool
    refund_id: str | None = None
    amount: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class ExchangeResult:
    """Result of an exchange/return operation."""

    success: bool
    exchange_id: str | None = None
    return_label_url: str | None = None
    replacement_order_id: str | None = None
    amount: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class TrackingInfo:
    """Normalized tracking/shipment data."""

    tracking_number: str
    carrier: str
    status: str  # in_transit | delivered | delayed | lost | unknown
    status_detail: str = ""
    estimated_delivery: datetime | None = None
    days_in_transit: int = 0
    last_update: datetime | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
