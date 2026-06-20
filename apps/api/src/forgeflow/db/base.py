"""
ForgeFlow AI - SQLAlchemy Declarative Base + Shared Mixins.

All ORM models inherit from Base and use the provided mixins
for consistent tenant isolation, timestamps, and UUID primary keys.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


class UUIDMixin:
    """Provides a UUID primary key with server-side generation."""

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        doc="Unique identifier",
    )


class TimestampMixin:
    """Provides created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last update timestamp",
    )


class TenantMixin:
    """Provides multi-tenant isolation fields.

    All tenant-scoped tables must include shopify_domain and platform.
    This enables the shared-database-with-tenant-isolation pattern from day one.
    """

    shopify_domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Shopify store domain (tenant identifier)",
    )
    platform: Mapped[str] = mapped_column(
        String(20),
        default="shopify",
        nullable=False,
        doc="E-commerce platform: shopify | woocommerce | amazon",
    )


class SoftDeleteMixin:
    """Provides soft-delete capability via deleted_at timestamp."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Soft delete timestamp. NULL = not deleted.",
    )
