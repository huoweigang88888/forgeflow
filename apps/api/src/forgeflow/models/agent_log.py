"""
ForgeFlow AI - AgentLog Model.

Records each step of the Agent Runtime execution for a ticket.
Enables debugging, auditing, and cost analysis.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forgeflow.db.base import Base, UUIDMixin


class AgentLog(Base, UUIDMixin):
    """Execution log for each agent graph node in a ticket's lifecycle."""

    __tablename__ = "agent_logs"

    ticket_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Node name: detect_intent | lookup_order | check_logistics | check_policy | make_decision | execute",
    )
    step_order: Mapped[int] = mapped_column(
        Integer, default=0, doc="Execution order within the ticket"
    )

    # --- I/O ---
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)

    # --- Status ---
    status: Mapped[str] = mapped_column(
        String(50),
        default="running",
        doc="running | success | failed | skipped",
    )

    # --- Timing ---
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # --- Error ---
    error_message: Mapped[str | None] = mapped_column(Text)
    fallback_used: Mapped[bool] = mapped_column(default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(100))

    # --- Timing ---
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    # --- Relationships ---
    ticket = relationship("Ticket", back_populates="agent_logs")
