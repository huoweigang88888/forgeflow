"""
ForgeFlow AI - PromptVersion Model.

Manages prompt template versioning for A/B testing and safe rollback.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from forgeflow.db.base import Base, UUIDMixin


class PromptVersion(Base, UUIDMixin):
    """Versioned prompt template for A/B testing and rollback."""

    __tablename__ = "prompt_versions"

    prompt_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        doc="Logical prompt name: intent_detection | decision | policy_check"
    )
    version: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="Semantic version: v1.0.0, v1.2.0"
    )
    template: Mapped[str] = mapped_column(Text, nullable=False, doc="Prompt template with {placeholders}")
    description: Mapped[str | None] = mapped_column(Text, doc="What changed in this version")
    is_active: Mapped[bool] = mapped_column(default=False, doc="Currently deployed version")
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    # --- Performance (updated by evaluation pipeline) ---
    accuracy: Mapped[float | None] = mapped_column(default=None, doc="Measured accuracy on eval set")
    avg_latency_ms: Mapped[int | None] = mapped_column(default=None)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
