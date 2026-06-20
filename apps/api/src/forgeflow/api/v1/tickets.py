"""
ForgeFlow AI - Ticket Management API Endpoints.

REST API for ticket CRUD, status polling, and approval operations.
Now backed by the database (Phase 4) instead of the Phase 1 in-memory store.

Endpoints:
    POST   /api/v1/tickets           — Create ticket + start agent
    GET    /api/v1/tickets           — List tickets (paginated)
    GET    /api/v1/tickets/{id}      — Ticket detail
    GET    /api/v1/tickets/{id}/status — Current status (poll fallback)
    POST   /api/v1/tickets/{id}/approve — Approve a pending ticket
    POST   /api/v1/tickets/{id}/reject  — Reject a pending ticket
    POST   /api/v1/tickets/{id}/cancel  — Cancel a processing ticket
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from forgeflow.agent.service import AgentService
from forgeflow.api.v1.ws import get_redis
from forgeflow.crud import ticket as ticket_crud
from forgeflow.db.session import DBSession
from forgeflow.monitoring.logger import get_logger
from forgeflow.schemas.ticket import (
    ApprovalRequest,
    ApprovalResponse,
    DashboardStatsResponse,
    TicketCreateRequest,
    TicketCreateResponse,
    TicketDetailResponse,
    TicketListResponse,
    TicketStatusResponse,
)

logger = get_logger(component="api.tickets")

router = APIRouter(prefix="/tickets", tags=["tickets"])

# Agent service — lazily initialized with Redis on first use
_agent_service: AgentService | None = None


async def _get_agent_service() -> AgentService:
    """Return the AgentService singleton with a real Redis client."""
    global _agent_service
    if _agent_service is None:
        redis_client = await get_redis()
        _agent_service = AgentService(redis_client=redis_client)
    return _agent_service


def _ticket_not_found(ticket_id: str) -> HTTPException:
    """Standard 404 for missing tickets."""
    return HTTPException(
        status_code=404,
        detail=f"Ticket not found: {ticket_id}",
    )


# =============================================================================
# POST /tickets — Create + Start
# =============================================================================


@router.post("", response_model=TicketCreateResponse, status_code=201)
async def create_ticket(
    body: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> dict[str, Any]:
    """Create a new ticket and start the agent processing pipeline.

    The ticket is persisted to the database and queued for immediate
    processing.  Use the returned ticket_id to poll status or connect
    via WebSocket.
    """
    ticket = await ticket_crud.create_ticket(
        db,
        customer_email=body.customer_email,
        issue_text=body.issue_text,
        platform=body.platform,
        order_id=body.order_id,
        customer_name=body.customer_name,
        attachments=body.attachments,
    )
    await db.commit()

    ticket_id = str(ticket.id)

    logger.info(
        "ticket_created",
        ticket_id=ticket_id,
        platform=body.platform,
        issue_len=len(body.issue_text),
    )

    # Start agent processing in background
    background_tasks.add_task(
        _process_ticket_background,
        ticket_id=ticket_id,
        platform=body.platform,
        shopify_domain=body.customer_email.split("@")[-1]
        if "@" in body.customer_email
        else "unknown",
        customer_email=body.customer_email,
        customer_name=body.customer_name,
        issue_text=body.issue_text,
        order_id=body.order_id,
        attachments=body.attachments,
    )

    await db.commit()

    return {
        "code": 0,
        "message": "Ticket created",
        "data": {
            "ticket_id": ticket_id,
            "status": "processing",
            "estimated_completion": "5s",
            "ws_endpoint": f"/ws/v1/tickets/{ticket_id}",
            "status_url": f"/api/v1/tickets/{ticket_id}/status",
        },
    }


# =============================================================================
# GET /tickets — List (paginated)
# =============================================================================


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    db: DBSession,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: str | None = Query(default=None, description="Filter by status"),
) -> dict[str, Any]:
    """List tickets with optional status filter.

    Results are paginated and sorted by creation time (newest first).
    """
    items, total = await ticket_crud.list_tickets(
        db, page=page, page_size=page_size, status=status,
    )

    ticket_dicts = [ticket_crud.ticket_to_dict(t) for t in items]

    return {
        "code": 0,
        "data": {
            "tickets": ticket_dicts,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


# =============================================================================
# GET /tickets/{id} — Detail
# =============================================================================


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(
    ticket_id: str,
    db: DBSession,
) -> dict[str, Any]:
    """Get full details of a ticket including all agent steps."""
    ticket = await ticket_crud.get_ticket(db, ticket_id)
    if not ticket:
        raise _ticket_not_found(ticket_id)

    return {
        "code": 0,
        "data": {"ticket": ticket_crud.ticket_to_dict(ticket)},
    }


# =============================================================================
# GET /tickets/{id}/status — Status (REST poll fallback)
# =============================================================================


@router.get("/{ticket_id}/status", response_model=TicketStatusResponse)
async def get_ticket_status(
    ticket_id: str,
    db: DBSession,
) -> dict[str, Any]:
    """Get the current processing status of a ticket.

    Used by the frontend as a REST fallback when WebSocket is unavailable.
    Returns step-by-step progress and any pending approval details.

    From PRD Section 9.3: GET /api/v1/tickets/{id}/status.
    """
    ticket = await ticket_crud.get_ticket(db, ticket_id)
    if not ticket:
        raise _ticket_not_found(ticket_id)

    ticket_dict = ticket_crud.ticket_to_dict(ticket)

    # Build step list
    steps = _build_step_list(ticket_dict)
    progress = _calculate_progress(steps)

    # Build pending approval if applicable
    pending_approval = None
    if ticket.requires_approval or ticket.status == "pending_approval":
        pending_approval = {
            "action": ticket.recommended_action or "unknown",
            "amount": ticket.refund_amount,
            "reason": ticket.refund_reason or "",
            "decision_explanation": ticket.decision_explanation or "",
            "deadline": None,
        }

    return {
        "code": 0,
        "data": {
            "ticket_id": ticket_id,
            "status": ticket.status,
            "progress": progress,
            "steps": steps,
            "pending_approval": pending_approval,
        },
    }


# =============================================================================
# POST /tickets/{id}/approve — Approve
# =============================================================================


@router.post("/{ticket_id}/approve", response_model=ApprovalResponse)
async def approve_ticket(
    ticket_id: str,
    body: ApprovalRequest = ...,
    db: DBSession = None,
) -> dict[str, Any]:
    """Approve a ticket that is pending human review.

    Upon approval, the agent continues execution and processes the
    refund/exchange.
    """
    ticket = await ticket_crud.get_ticket(db, ticket_id)
    if not ticket:
        raise _ticket_not_found(ticket_id)

    if ticket.status != "pending_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Ticket is not pending approval (current status: {ticket.status})",
        )

    try:
        state = ticket_crud.ticket_to_dict(ticket)
        result = await (await _get_agent_service()).resume(
            ticket_id=ticket_id,
            state=state,
            approved=True,
            approver_note=body.note,
        )
        await ticket_crud.update_ticket(db, ticket_id, result)
        await db.commit()

    except Exception as e:
        logger.error("ticket_approve_failed", ticket_id=ticket_id, error=str(e)[:200])
        raise HTTPException(
            status_code=500, detail=f"Failed to process approval: {e!s}"
        ) from e

    # Re-read to get updated status
    ticket = await ticket_crud.get_ticket(db, ticket_id)
    return {
        "code": 0,
        "message": "Approved — execution started",
        "data": {
            "ticket_id": ticket_id,
            "status": ticket.status if ticket else "resolved",
            "execution_id": (ticket.execution_result or {}).get("refund_id") if ticket else None,
        },
    }


# =============================================================================
# POST /tickets/{id}/reject — Reject
# =============================================================================


@router.post("/{ticket_id}/reject", response_model=ApprovalResponse)
async def reject_ticket(
    ticket_id: str,
    body: ApprovalRequest = ...,
    db: DBSession = None,
) -> dict[str, Any]:
    """Reject a ticket that is pending human review.

    Upon rejection, the ticket is escalated for manual handling.
    """
    ticket = await ticket_crud.get_ticket(db, ticket_id)
    if not ticket:
        raise _ticket_not_found(ticket_id)

    if ticket.status != "pending_approval":
        raise HTTPException(
            status_code=409,
            detail=f"Ticket is not pending approval (current status: {ticket.status})",
        )

    try:
        state = ticket_crud.ticket_to_dict(ticket)
        result = await (await _get_agent_service()).resume(
            ticket_id=ticket_id,
            state=state,
            approved=False,
            approver_note=body.note,
        )
        await ticket_crud.update_ticket(db, ticket_id, result)
        await db.commit()

    except Exception as e:
        logger.error("ticket_reject_failed", ticket_id=ticket_id, error=str(e)[:200])
        raise HTTPException(
            status_code=500, detail=f"Failed to process rejection: {e!s}"
        ) from e

    ticket = await ticket_crud.get_ticket(db, ticket_id)
    return {
        "code": 0,
        "message": "Rejected — ticket escalated to human",
        "data": {
            "ticket_id": ticket_id,
            "status": ticket.status if ticket else "escalated",
            "execution_id": None,
        },
    }


# =============================================================================
# POST /tickets/{id}/cancel — Cancel
# =============================================================================


@router.post("/{ticket_id}/cancel")
async def cancel_ticket(
    ticket_id: str,
    db: DBSession = None,
) -> dict[str, Any]:
    """Cancel a ticket that is currently processing."""
    ticket = await ticket_crud.get_ticket(db, ticket_id)
    if not ticket:
        raise _ticket_not_found(ticket_id)

    valid_statuses = ("received", "processing", "pending_approval")
    if ticket.status not in valid_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Ticket cannot be cancelled (current status: {ticket.status})",
        )

    await ticket_crud.update_ticket(db, ticket_id, {
        "status": "failed",
        "recommended_action": "escalate_to_human",
        "decision_explanation": "Cancelled by user",
    })
    await db.commit()

    logger.info("ticket_cancelled", ticket_id=ticket_id)

    return {
        "code": 0,
        "message": "Ticket cancelled",
        "data": {"ticket_id": ticket_id, "status": "failed"},
    }


# =============================================================================
# Dashboard Stats
# =============================================================================


@router.get("/stats/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db: DBSession) -> dict[str, Any]:
    """Get aggregate dashboard statistics."""
    stats = await ticket_crud.get_dashboard_stats(db)
    return {"code": 0, "data": stats}


# =============================================================================
# Background Processing
# =============================================================================


async def _process_ticket_background(
    ticket_id: str,
    platform: str,
    shopify_domain: str,
    customer_email: str,
    issue_text: str,
    customer_name: str | None = None,
    order_id: str | None = None,
    attachments: list[str] | None = None,
) -> None:
    """Run the agent in background and persist the result to the database.

    Creates its own DB session since background tasks run outside the
    request scope.
    """
    from forgeflow.db.engine import AsyncSessionLocal

    try:
        result = await (await _get_agent_service()).run(
            ticket_id=ticket_id,
            platform=platform,
            shopify_domain=shopify_domain,
            customer_email=customer_email,
            issue_text=issue_text,
            order_id=order_id,
            customer_name=customer_name,
            attachments=attachments,
        )

        # Persist result to database
        async with AsyncSessionLocal() as db:
            try:
                await ticket_crud.update_ticket(db, ticket_id, result)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        logger.info(
            "ticket_processing_complete",
            ticket_id=ticket_id,
            status=result.get("status"),
            action=result.get("recommended_action"),
            duration_ms=result.get("processing_duration_ms"),
        )

    except Exception as e:
        logger.error(
            "ticket_processing_failed",
            ticket_id=ticket_id,
            error=str(e)[:500],
        )
        # Persist failure
        async with AsyncSessionLocal() as db:
            try:
                await ticket_crud.update_ticket(db, ticket_id, {
                    "status": "failed",
                    "error_message": str(e)[:1000],
                    "recommended_action": "escalate_to_human",
                })
                await db.commit()
            except Exception:
                await db.rollback()


# =============================================================================
# Helpers
# =============================================================================

_STEP_ORDER = [
    "detect_intent",
    "lookup_order",
    "check_logistics",
    "check_policy",
    "make_decision",
    "execute",
]


def _build_step_list(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the ordered list of completed/pending steps."""
    steps = []
    for step_name in _STEP_ORDER:
        if step_name == "detect_intent":
            done = ticket.get("intent") is not None
            result = ticket.get("intent") if done else None
        elif step_name == "lookup_order":
            done = ticket.get("order_info") is not None
            result = "found" if done and ticket.get("order_info") else None
        elif step_name == "check_logistics":
            done = ticket.get("logistics_status") is not None
            ls = ticket.get("logistics_status", {})
            result = ls.get("status") if done else None
        elif step_name == "check_policy":
            done = ticket.get("relevant_policies") is not None
            pl = ticket.get("relevant_policies") or []
            result = f"{len(pl)} policies matched" if done else None
        elif step_name == "make_decision":
            done = ticket.get("recommended_action") is not None
            result = ticket.get("recommended_action") if done else None
        elif step_name == "execute":
            done = ticket.get("execution_status") is not None
            result = ticket.get("execution_status") if done else None
        else:
            done = False
            result = None

        steps.append({
            "step": step_name,
            "status": "done" if done else "pending",
            "result": result,
        })

    return steps


def _calculate_progress(steps: list[dict[str, Any]]) -> float:
    """Calculate progress as a fraction (0.0 to 1.0) based on completed steps."""
    if not steps:
        return 0.0
    done = sum(1 for s in steps if s["status"] == "done")
    return round(done / len(steps), 2)
