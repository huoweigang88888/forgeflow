"""
ForgeFlow AI - Customer Model.

Represents an e-commerce customer synced from Shopify (or other platforms).
"""

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forgeflow.db.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class Customer(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Customer entity — synced from the e-commerce platform."""

    __tablename__ = "customers"

    shopify_customer_id: Mapped[str] = mapped_column(
        String(50), nullable=False, doc="Platform-native customer ID"
    )
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, doc="Customer email"
    )
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    refund_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    orders = relationship("Order", back_populates="customer", lazy="raise")
    tickets = relationship("Ticket", back_populates="customer", lazy="raise")
