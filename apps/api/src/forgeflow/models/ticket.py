"""
ForgeFlow AI - Ticket Model (Core Entity).

The central entity in the system. Each ticket represents one customer
after-sales request that flows through the Agent Runtime state machine.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forgeflow.db.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class Ticket(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """After-sales ticket — the core processing unit."""

    __tablename__ = "tickets"

    # --- Relationships ---
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("customers.id"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id"), index=True
    )

    # --- Customer Input ---
    platform: Mapped[str] = mapped_column(
        String(20),
        default="mock",
        nullable=False,
        doc="Platform: shopify | woocommerce | amazon | mock",
    )
    issue_text: Mapped[str] = mapped_column(Text, nullable=False, doc="Original customer message")
    issue_language: Mapped[str] = mapped_column(String(10), default="en")
    attachments: Mapped[Any | None] = mapped_column(JSONB, doc="Array of attachment URLs")
    extra_data: Mapped[dict | None] = mapped_column(
        JSONB, doc="Arbitrary extra state (order_info, logistics_status, etc.)"
    )

    # --- Intent Detection ---
    intent: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        doc="shipping_delay | refund_request | wrong_item | damaged_item | exchange_request | partial_refund | subscription_cancel | pre_sale_inquiry | other",
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    extracted_order_id: Mapped[str | None] = mapped_column(
        String(50), doc="Order ID extracted from customer text"
    )
    urgency: Mapped[str | None] = mapped_column(String(10), doc="high | medium | low")
    sentiment: Mapped[str | None] = mapped_column(String(10), doc="positive | neutral | negative")

    # --- Agent Decision ---
    recommended_action: Mapped[str | None] = mapped_column(
        String(50),
        doc="auto_refund | auto_exchange | investigate | escalate_to_human | send_notification",
    )
    refund_amount: Mapped[float | None] = mapped_column(Float)
    refund_reason: Mapped[str | None] = mapped_column(Text)
    requires_approval: Mapped[bool] = mapped_column(default=False)
    approval_reason: Mapped[str | None] = mapped_column(Text)
    decision_explanation: Mapped[str | None] = mapped_column(Text)

    # --- Execution ---
    execution_status: Mapped[str | None] = mapped_column(
        String(50),
        doc="pending | running | success | failed",
    )
    execution_result: Mapped[dict | None] = mapped_column(JSONB)

    # --- State ---
    current_step: Mapped[str | None] = mapped_column(
        String(50),
        doc="Current agent graph node",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="received",
        index=True,
        doc="received | processing | pending_approval | resolved | escalated | failed",
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Timestamps ---
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        doc="SLA deadline for pending approval tickets (entered_approval_at + 24h)",
    )

    # --- Tracking ---
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer, doc="Total processing time")
    llm_call_count: Mapped[int] = mapped_column(Integer, default=0)
    llm_cost_total: Mapped[float | None] = mapped_column(
        Float, doc="Total LLM cost for this ticket"
    )

    # --- Relationships ---
    customer = relationship("Customer", back_populates="tickets")
    order = relationship("Order", back_populates="tickets")
    agent_logs = relationship("AgentLog", back_populates="ticket", lazy="raise")
    llm_calls = relationship("LLMCall", back_populates="ticket", lazy="raise")
