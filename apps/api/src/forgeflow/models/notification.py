"""
ForgeFlow AI - NotificationLog Model.

Tracks every outbound customer notification (email/SMS) with delivery
status, retry count, and timing for audit and retry purposes.

Used by the notification retry worker to re-dispatch failed notifications
with exponential backoff.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from forgeflow.db.base import Base, UUIDMixin


class NotificationLog(Base, UUIDMixin):
    """Audit log for every customer notification sent by the system."""

    __tablename__ = "notification_logs"

    ticket_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Related ticket ID, if any.",
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="Tenant identifier for multi-tenant isolation.",
    )

    # --- Recipient ---
    recipient: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Recipient address (email or phone number).",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="email",
        doc="Notification channel: email | sms.",
    )

    # --- Content ---
    subject: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Email subject line (null for SMS).",
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Notification body content.",
    )
    template_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Template key used to generate the message.",
    )

    # --- Delivery ---
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
        doc="Delivery status: pending | sent | failed | permanent_failure.",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of retry attempts made.",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        doc="Maximum retry attempts before marking as permanent_failure.",
    )
    is_customer_facing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether this notification was shown to the customer.",
    )

    # --- Provider ---
    provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Provider used: sendgrid | twilio.",
    )
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Provider-side message ID for delivery tracking.",
    )

    # --- Timing ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        doc="When the notification was created.",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the notification was successfully sent.",
    )
    last_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the last retry attempt was made.",
    )

    # --- Error ---
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Error message from the most recent failed attempt.",
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id!r}, channel={self.channel!r}, "
            f"status={self.status!r}, retries={self.retry_count})>"
        )
