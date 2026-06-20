"""
ForgeFlow AI - Ticket CRUD Operations.

Async SQLAlchemy CRUD for the Ticket model.  Replaces the Phase 1
in-memory ``_ticket_store`` dict with persistent database storage.

All functions expect an async ``AsyncSession`` injected via the
``DBSession`` FastAPI dependency.
"""

from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from forgeflow.models.ticket import Ticket
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="crud.ticket")


# =============================================================================
# CREATE
# =============================================================================


async def create_ticket(
    db: AsyncSession,
    *,
    customer_email: str,
    issue_text: str,
    platform: str = "mock",
    order_id: str | None = None,
    customer_name: str | None = None,
    attachments: list[str] | None = None,
    tenant_id: str = "default",
) -> Ticket:
    """Create a new ticket row and return it.

    The caller is responsible for flushing/committing the session.
    """
    now = datetime.now(UTC)
    ticket = Ticket(
        id=uuid4(),
        tenant_id=tenant_id,
        issue_text=issue_text,
        issue_language="en",
        attachments=attachments or [],
        platform=platform,
        status="processing",
        started_at=now,
        created_at=now,
        updated_at=now,
        # Store extra metadata the old dict had
        extra_data={
            "customer_email": customer_email,
            "customer_name": customer_name,
            "order_id": order_id,
        },
    )
    db.add(ticket)
    await db.flush()
    logger.info("ticket_created_db", ticket_id=str(ticket.id), platform=platform)
    return ticket


# =============================================================================
# READ
# =============================================================================


async def get_ticket(db: AsyncSession, ticket_id: str) -> Ticket | None:
    """Fetch a single ticket by its UUID PK (as str)."""
    from uuid import UUID as PyUUID

    try:
        uid = PyUUID(ticket_id)
    except ValueError:
        return None
    return await db.get(Ticket, uid)


async def list_tickets(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    tenant_id: str = "default",
) -> tuple[Sequence[Ticket], int]:
    """Return (items, total_count) for paginated ticket listing.

    Results are sorted by ``created_at`` descending.
    """
    base = select(Ticket).where(Ticket.tenant_id == tenant_id)

    if status:
        base = base.where(Ticket.status == status)

    # Total count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginated query
    offset = (page - 1) * page_size
    items_q = base.order_by(Ticket.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(items_q)
    items = result.scalars().all()

    return items, total


# =============================================================================
# UPDATE
# =============================================================================


async def update_ticket(
    db: AsyncSession,
    ticket_id: str,
    updates: dict[str, Any],
) -> Ticket | None:
    """Apply a dict of field updates to an existing ticket.

    Only keys that match Ticket columns are written; the rest are
    stored in ``extra_data`` (JSONB).
    """
    from uuid import UUID as PyUUID

    try:
        uid = PyUUID(ticket_id)
    except ValueError:
        return None

    ticket = await db.get(Ticket, uid)
    if not ticket:
        return None

    # Known columns that can be updated directly
    _column_fields = {
        "intent",
        "confidence",
        "extracted_order_id",
        "urgency",
        "sentiment",
        "recommended_action",
        "refund_amount",
        "refund_reason",
        "requires_approval",
        "approval_reason",
        "decision_explanation",
        "execution_status",
        "execution_result",
        "current_step",
        "status",
        "error_message",
        "retry_count",
        "processing_duration_ms",
        "llm_call_count",
        "llm_cost_total",
        "started_at",
        "completed_at",
        "issue_language",
    }

    extra: dict[str, Any] = dict(ticket.extra_data or {})

    for key, value in updates.items():
        if key in _column_fields:
            setattr(ticket, key, value)
        elif key not in ("ticket_id", "customer_email", "customer_name",
                         "order_id", "attachments", "platform", "created_at",
                         "processing_duration_ms"):
            # Collect non-column, non-metadata fields (e.g. order_info,
            # logistics_status, customer_history, relevant_policies, etc.)
            extra[key] = value

    ticket.extra_data = extra
    ticket.updated_at = datetime.now(UTC)
    await db.flush()
    return ticket


# =============================================================================
# DASHBOARD STATS
# =============================================================================


async def get_dashboard_stats(
    db: AsyncSession,
    tenant_id: str = "default",
) -> dict[str, Any]:
    """Return aggregate dashboard statistics."""
    base = select(Ticket).where(Ticket.tenant_id == tenant_id)

    # Total
    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar_one()

    # Per-status counts
    statuses = ("resolved", "escalated", "pending_approval", "failed", "processing")
    counts: dict[str, int] = {}
    for s in statuses:
        q = select(func.count()).select_from(
            select(Ticket).where(Ticket.tenant_id == tenant_id, Ticket.status == s).subquery()
        )
        counts[s] = (await db.execute(q)).scalar_one()

    # Avg duration
    dur_q = select(func.avg(Ticket.processing_duration_ms)).where(
        Ticket.tenant_id == tenant_id,
        Ticket.processing_duration_ms.isnot(None),
    )
    avg_duration = (await db.execute(dur_q)).scalar() or 0

    resolved_count = counts.get("resolved", 0)
    auto_rate = (resolved_count / total * 100) if total > 0 else 0.0

    return {
        "total_tickets": total,
        "resolved": resolved_count,
        "escalated": counts.get("escalated", 0),
        "pending_approval": counts.get("pending_approval", 0),
        "failed": counts.get("failed", 0),
        "processing": counts.get("processing", 0),
        "avg_processing_time_ms": int(avg_duration),
        "auto_resolution_rate": round(auto_rate, 1),
    }


# =============================================================================
# TICKET → DICT (for API responses)
# =============================================================================


def ticket_to_dict(ticket: Ticket) -> dict[str, Any]:
    """Convert a Ticket ORM object into the dict shape the API returns.

    Merges column values with ``extra_data`` so the response matches
    the original in-memory store shape.
    """
    base: dict[str, Any] = {
        "ticket_id": str(ticket.id),
        "status": ticket.status,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        # Intent
        "intent": ticket.intent,
        "confidence": ticket.confidence,
        "extracted_order_id": ticket.extracted_order_id,
        "urgency": ticket.urgency,
        "sentiment": ticket.sentiment,
        # Decision
        "recommended_action": ticket.recommended_action,
        "refund_amount": ticket.refund_amount,
        "refund_reason": ticket.refund_reason,
        "requires_approval": ticket.requires_approval,
        "approval_reason": ticket.approval_reason,
        "decision_explanation": ticket.decision_explanation,
        # Execution
        "execution_status": ticket.execution_status,
        "execution_result": ticket.execution_result,
        # State
        "current_step": ticket.current_step,
        "error_message": ticket.error_message,
        "retry_count": ticket.retry_count,
        # Tracking
        "processing_duration_ms": ticket.processing_duration_ms,
        "llm_call_count": ticket.llm_call_count,
        "llm_cost_total": ticket.llm_cost_total,
        "started_at": ticket.started_at.isoformat() if ticket.started_at else None,
        "completed_at": ticket.completed_at.isoformat() if ticket.completed_at else None,
    }

    # Merge extra data (order_info, logistics_status, customer_history, etc.)
    extra = ticket.extra_data or {}
    base.update(extra)

    return base
