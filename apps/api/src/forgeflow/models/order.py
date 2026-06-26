"""
ForgeFlow AI - Order Model.

Stores e-commerce order data synced from the platform (Shopify, WooCommerce, etc.).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forgeflow.db.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class Order(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Order entity — synced from e-commerce platform."""

    __tablename__ = "orders"

    shopify_order_id: Mapped[str] = mapped_column(
        String(50), nullable=False, doc="Platform-native order ID"
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id"), index=True
    )
    order_number: Mapped[str | None] = mapped_column(String(50))
    total_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    fulfillment_status: Mapped[str | None] = mapped_column(
        String(50), doc="unfulfilled | fulfilled | partial"
    )
    financial_status: Mapped[str | None] = mapped_column(String(50))
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    tracking_carrier: Mapped[str | None] = mapped_column(String(50))
    shipping_address: Mapped[Any | None] = mapped_column(JSONB)
    line_items: Mapped[Any | None] = mapped_column(JSONB, doc="Array of line item objects")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Order creation time on platform"
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", doc="Last sync timestamp"
    )

    # Relationships
    customer = relationship("Customer", back_populates="orders")
    tickets = relationship("Ticket", back_populates="order")
