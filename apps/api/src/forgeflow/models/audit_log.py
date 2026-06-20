"""
ForgeFlow AI - AuditLog Model.

Immutable audit trail for all sensitive operations.
Records who did what, when, and what changed.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from forgeflow.db.base import Base, UUIDMixin


class AuditLog(Base, UUIDMixin):
    """Immutable audit record for compliance and security."""

    __tablename__ = "audit_logs"

    tenant_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True, doc="Shopify domain"
    )
    actor_id: Mapped[str | None] = mapped_column(String(100), doc="User ID who performed the action")
    actor_role: Mapped[str | None] = mapped_column(String(50), doc="admin | manager | agent")

    # --- Action ---
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        doc="ticket.approve | refund.execute | settings.update | policy.create",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50), index=True, doc="ticket | order | setting | policy"
    )
    resource_id: Mapped[str | None] = mapped_column(String(100), index=True)

    # --- Details ---
    details: Mapped[dict | None] = mapped_column(
        JSONB, doc='Change details: {"before": {...}, "after": {...}}'
    )

    # --- Context ---
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)

    # --- Timestamp ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", index=True
    )
