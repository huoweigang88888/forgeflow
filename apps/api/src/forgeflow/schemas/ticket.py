"""
ForgeFlow AI - Ticket API Schemas.

Pydantic models for ticket API request/response validation.
Matches the API design from PRD Section 9.
"""


from pydantic import BaseModel, Field

# ── Request Schemas ──


class TicketCreateRequest(BaseModel):
    """Request to create a new after-sales ticket."""

    customer_email: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["buyer@example.com"],
        description="Customer's email address",
    )
    issue_text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        examples=["My order #1234 hasn't arrived, it's been 2 weeks"],
        description="The customer's issue description",
    )
    order_id: str | None = Field(
        default=None,
        max_length=255,
        examples=["gid://shopify/Order/1234567890"],
        description="Platform order ID if known",
    )
    customer_name: str | None = Field(
        default=None,
        max_length=200,
        description="Customer's display name",
    )
    attachments: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="List of attachment URLs",
    )
    platform: str = Field(
        default="mock",
        max_length=50,
        description="Platform identifier (mock, shopify, etc.)",
    )


class ApprovalRequest(BaseModel):
    """Request to approve or reject a pending ticket."""

    approved: bool = Field(
        ...,
        description="True to approve, False to reject",
    )
    note: str = Field(
        default="",
        max_length=1000,
        description="Optional note from the approver",
    )
    approver_id: str = Field(
        default="system",
        max_length=100,
        description="ID of the user performing the approval",
    )


# ── Response Schemas ──


class StepInfo(BaseModel):
    """Information about a single completed step."""

    step: str = Field(..., description="Step name (e.g., 'detect_intent')")
    status: str = Field(..., description="Step status: 'done', 'failed', 'skipped'")
    result: str | None = Field(default=None, description="Summary of step result")


class PendingApprovalInfo(BaseModel):
    """Details about an approval that is pending."""

    action: str = Field(..., description="The action requiring approval")
    amount: float | None = Field(default=None, description="Refund amount if applicable")
    reason: str = Field(default="", description="Reason for the proposed action")
    decision_explanation: str = Field(default="", description="Agent's reasoning")
    deadline: str | None = Field(default=None, description="ISO 8601 deadline for approval")


class TicketCreateResponse(BaseModel):
    """Response after creating a ticket."""

    code: int = 0
    message: str = "Ticket created"
    data: dict = Field(
        default_factory=lambda: {
            "ticket_id": "",
            "status": "received",
        }
    )


class TicketStatusResponse(BaseModel):
    """Response for ticket status endpoint (REST poll fallback)."""

    code: int = 0
    data: dict = Field(
        default_factory=lambda: {
            "ticket_id": "",
            "status": "received",
            "progress": 0.0,
            "steps": [],
            "pending_approval": None,
        }
    )


class TicketDetailResponse(BaseModel):
    """Full ticket detail response."""

    code: int = 0
    data: dict = Field(default_factory=lambda: {"ticket": {}})


class TicketListResponse(BaseModel):
    """Paginated ticket list response."""

    code: int = 0
    data: dict = Field(
        default_factory=lambda: {
            "tickets": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }
    )


class ApprovalResponse(BaseModel):
    """Response after processing an approval decision."""

    code: int = 0
    message: str = ""
    data: dict = Field(
        default_factory=lambda: {
            "ticket_id": "",
            "status": "",
            "execution_id": None,
        }
    )


class DashboardStatsResponse(BaseModel):
    """Response for dashboard statistics."""

    code: int = 0
    data: dict = Field(
        default_factory=lambda: {
            "total_tickets": 0,
            "resolved": 0,
            "escalated": 0,
            "pending_approval": 0,
            "avg_processing_time_ms": 0,
            "auto_resolution_rate": 0.0,
        }
    )


# ── Shared Response Wrapper ──


class APIResponse(BaseModel):
    """Generic API response wrapper matching common format."""

    code: int = 0
    message: str = "OK"
    data: dict | None = None
