"""
ForgeFlow AI - LLMCall Model.

Records every LLM API call for cost tracking, debugging, and evaluation.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forgeflow.db.base import Base, UUIDMixin


class LLMCall(Base, UUIDMixin):
    """Audit record for each LLM API invocation."""

    __tablename__ = "llm_calls"

    ticket_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), index=True
    )
    agent_log_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_logs.id"), index=True
    )
    model: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, doc="e.g. gpt-4o-mini, claude-haiku-4-5"
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, doc="openai | anthropic | qwen"
    )

    # --- Prompt & Response ---
    prompt: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(
        String(20), doc="Prompt version used (e.g. v1.2.0)"
    )
    response: Mapped[str | None] = mapped_column(Text)
    parsed_output: Mapped[dict | None] = mapped_column(JSONB)

    # --- Token Usage ---
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)

    # --- Cost ---
    cost: Mapped[float | None] = mapped_column(Float, doc="Cost in USD")

    # --- Status ---
    status: Mapped[str] = mapped_column(
        String(50), default="success",
        doc="success | json_parse_error | fallback_used | failed",
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Timing ---
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    # --- Relationships ---
    ticket = relationship("Ticket", back_populates="llm_calls")
