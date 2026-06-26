"""
ForgeFlow AI - Ticket CRUD Operations.

Async SQLAlchemy CRUD for the Ticket model.  Replaces the Phase 1
in-memory ``_ticket_store`` dict with persistent database storage.

All functions expect an async ``AsyncSession`` injected via the
``DBSession`` FastAPI dependency.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

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
        shopify_domain=tenant_id,  # tenant_id alias → model's shopify_domain column
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
    try:
        uid = UUID(ticket_id)
    except ValueError:
        return None
    return await db.get(Ticket, uid)


async def list_tickets(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    platform: str | None = None,
    tenant_id: str | None = None,
) -> tuple[Sequence[Ticket], int]:
    """Return (items, total_count) for paginated ticket listing.

    Results are sorted by ``created_at`` descending.
    When tenant_id is provided, only tickets for that shop are returned.
    When None, all tickets are returned (admin use only).
    """
    base = select(Ticket)
    if tenant_id:
        base = base.where(Ticket.shopify_domain == tenant_id)

    if status:
        base = base.where(Ticket.status == status)

    if platform:
        base = base.where(Ticket.platform == platform)

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
    try:
        uid = UUID(ticket_id)
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
        "sla_deadline",
    }

    extra: dict[str, Any] = dict(ticket.extra_data or {})

    for key, value in updates.items():
        if key in _column_fields:
            setattr(ticket, key, value)
        elif key not in (
            "ticket_id",
            "customer_email",
            "customer_name",
            "order_id",
            "attachments",
            "platform",
            "created_at",
            "processing_duration_ms",
        ):
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
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Return aggregate dashboard statistics filtered by tenant."""
    base = select(Ticket)
    if tenant_id:
        base = base.where(Ticket.shopify_domain == tenant_id)

    # Total
    total_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_q)).scalar_one()

    # Per-status counts
    statuses = ("resolved", "escalated", "pending_approval", "failed", "processing")
    counts: dict[str, int] = {}
    for s in statuses:
        count_base = select(Ticket)
        if tenant_id:
            count_base = count_base.where(Ticket.shopify_domain == tenant_id)
        q = select(func.count()).select_from(count_base.where(Ticket.status == s).subquery())
        counts[s] = (await db.execute(q)).scalar_one()

    # Avg duration
    dur_base = select(Ticket).where(
        Ticket.processing_duration_ms.isnot(None),
    )
    if tenant_id:
        dur_base = dur_base.where(Ticket.shopify_domain == tenant_id)
    dur_q = select(func.avg(Ticket.processing_duration_ms)).select_from(dur_base.subquery())
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
# TICKET METRICS (for monitoring dashboard charts)
# =============================================================================


async def get_ticket_metrics(
    db: AsyncSession,
    days: int = 30,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Return time-series metrics for the monitoring dashboard.

    Returns processing rate, LLM cost, auto-resolve trend, and SLA
    compliance rate for the requested time window.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import case

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days)

    # Base filter
    def _tenant_filter(q: Any) -> Any:
        if tenant_id:
            return q.where(Ticket.shopify_domain == tenant_id)
        return q

    # ---- Processing rate: per-hour counts for last 24h ----
    rate_cutoff = now - timedelta(hours=24)
    rate_q = (
        select(
            func.date_trunc("hour", Ticket.created_at).label("hour"),
            func.count().label("count"),
        )
        .where(Ticket.created_at >= rate_cutoff)
        .group_by("hour")
        .order_by("hour")
    )
    rate_q = _tenant_filter(rate_q)
    rate_result = await db.execute(rate_q)
    processing_rate = [
        {"hour": row.hour.isoformat(), "count": row.count} for row in rate_result.all()
    ]

    # ---- LLM cost daily: sum llm_cost_total grouped by day ----
    cost_q = (
        select(
            func.date_trunc("day", Ticket.created_at).label("day"),
            func.coalesce(func.sum(Ticket.llm_cost_total), 0.0).label("cost"),
        )
        .where(Ticket.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )
    cost_q = _tenant_filter(cost_q)
    cost_result = await db.execute(cost_q)
    llm_cost = [
        {"date": row.day.isoformat()[:10], "cost": round(float(row.cost), 4)}
        for row in cost_result.all()
    ]

    # ---- Auto-resolve trend: per-day resolution rate ----
    trend_q = (
        select(
            func.date_trunc("day", Ticket.created_at).label("day"),
            func.count().label("total"),
            func.sum(case((Ticket.status == "resolved", 1), else_=0)).label("resolved_count"),
        )
        .where(Ticket.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )
    trend_q = _tenant_filter(trend_q)
    trend_result = await db.execute(trend_q)
    auto_resolve_trend = []
    for row in trend_result.all():
        rate = (row.resolved_count / row.total * 100) if row.total > 0 else 0.0
        auto_resolve_trend.append(
            {
                "date": row.day.isoformat()[:10],
                "rate": round(rate, 1),
                "total": row.total,
                "resolved": row.resolved_count,
            }
        )

    # ---- SLA compliance: % of resolved tickets that met SLA ----
    sla_q = select(
        func.count().label("total_resolved"),
        func.sum(
            case(
                (
                    (Ticket.sla_deadline.is_(None)) | (Ticket.completed_at <= Ticket.sla_deadline),
                    1,
                ),
                else_=0,
            )
        ).label("within_sla"),
    ).where(
        Ticket.status == "resolved",
        Ticket.completed_at.isnot(None),
    )
    sla_q = _tenant_filter(sla_q)
    sla_result = await db.execute(sla_q)
    sla_row = sla_result.one()
    sla_compliance = (
        round(sla_row.within_sla / sla_row.total_resolved * 100, 1)
        if sla_row.total_resolved > 0
        else 100.0
    )

    # ---- Weekly cumulative LLM cost ----
    weekly_q = (
        select(
            func.date_trunc("week", Ticket.created_at).label("week"),
            func.coalesce(func.sum(Ticket.llm_cost_total), 0.0).label("cost"),
        )
        .where(Ticket.created_at >= cutoff)
        .group_by("week")
        .order_by("week")
    )
    weekly_q = _tenant_filter(weekly_q)
    weekly_result = await db.execute(weekly_q)
    llm_cost_weekly = [
        {"week_start": row.week.isoformat()[:10], "cost": round(float(row.cost), 4)}
        for row in weekly_result.all()
    ]

    return {
        "processing_rate": processing_rate,
        "llm_cost_daily": llm_cost,
        "llm_cost_weekly": llm_cost_weekly,
        "auto_resolve_trend": auto_resolve_trend,
        "sla_compliance_rate": sla_compliance,
        "period_days": days,
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
        "platform": ticket.platform,
        "status": ticket.status,
        "issue_text": ticket.issue_text,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        # Intent
        "intent": ticket.intent,
        "confidence": ticket.confidence,
        "extracted_order_id": ticket.extracted_order_id,
        "urgency": ticket.urgency,
        "sentiment": ticket.sentiment,
        "issue_language": ticket.issue_language,
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
        "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
    }

    # Merge extra data (order_info, logistics_status, customer_history, etc.)
    extra = ticket.extra_data or {}
    base.update(extra)

    return base
