"""
ForgeFlow AI - PolicyDocument Model.

Stores policy documents with vector embeddings for semantic search (Phase 3).
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from forgeflow.db.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class PolicyDocument(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Policy/FAQ document with vector embedding for similarity search."""

    __tablename__ = "policy_documents"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64), index=True, doc="SHA-256 hash for deduplication"
    )

    # --- Chunking ---
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, doc="Chunk position in source doc")
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), index=True, doc="Parent document ID for multi-chunk docs"
    )

    # --- Embedding (Phase 3) ---
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), doc="text-embedding-3-small embedding (1536 dimensions)"
    )

    # --- Metadata ---
    category: Mapped[str | None] = mapped_column(
        String(100), index=True, doc="Policy category: refund | shipping | exchange | general"
    )
    tags: Mapped[Any | None] = mapped_column(JSONB, default=[])
    is_active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[str | None] = mapped_column(String(100))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
