"""
ForgeFlow AI - Agent State Definition.

Defines the AgentState TypedDict that flows through all LangGraph nodes.
Every node reads and returns a partial update to this state.

From PRD Section 7.1: Agent State Definition.
"""

from typing import Literal, TypedDict

# ── Intent types ──
IntentType = Literal[
    "shipping_delay",
    "refund_request",
    "wrong_item",
    "damaged_item",
    "exchange_request",
    "other",
]

# ── Recommended actions ──
ActionType = Literal[
    "auto_refund",
    "auto_exchange",
    "investigate",
    "escalate_to_human",
    "send_notification",
]

# ── Execution status ──
ExecutionStatus = Literal["pending", "running", "success", "failed", "pending_manual"]

# ── Ticket lifecycle status ──
TicketStatus = Literal[
    "received",
    "processing",
    "pending_approval",
    "resolved",
    "escalated",
    "failed",
]

# ── Urgency / Sentiment ──
Urgency = Literal["high", "medium", "low"]
Sentiment = Literal["positive", "neutral", "negative"]

# ── Logistics status ──
LogisticsStatus = Literal["in_transit", "delivered", "delayed", "lost", "unknown"]


class AgentState(TypedDict, total=False):
    """Complete state for the after-sales agent state machine.

    Fields are optional (total=False) because nodes add data incrementally
    as the ticket flows through the pipeline.
    """

    # === Input (set on ticket creation) ===
    ticket_id: str
    platform: str  # "shopify" | "woocommerce" | "amazon" | "mock"
    shopify_domain: str  # tenant identifier
    customer_email: str
    customer_name: str | None
    order_id: str | None  # platform-native order ID
    issue_text: str
    issue_language: str
    attachments: list[str]

    # === Mock overrides (for testing) ===
    mock_overrides: dict | None

    # === Intent Detection ===
    intent: IntentType | None
    confidence: float | None
    extracted_order_id: str | None
    urgency: Urgency | None
    sentiment: Sentiment | None

    # === Order Lookup ===
    order_info: dict | None

    # === Logistics Check ===
    logistics_status: dict | None
    tracking_number: str | None
    tracking_carrier: str | None

    # === Policy Check ===
    relevant_policies: list[dict] | None
    policy_match: bool | None

    # === Customer History ===
    customer_history: dict | None

    # === Decision ===
    recommended_action: ActionType | None
    refund_amount: float | None
    refund_reason: str | None
    requires_approval: bool
    approval_reason: str | None
    decision_explanation: str | None
    customer_response: str | None

    # === Execution ===
    execution_status: ExecutionStatus | None
    execution_result: dict | None

    # === Control ===
    current_step: str
    retry_count: int
    error_message: str | None
    fallback_used: bool
    started_at: str | None  # ISO 8601
    completed_at: str | None

    # === Status ===
    status: TicketStatus
    processing_duration_ms: int | None
    llm_call_count: int


def get_initial_state(
    ticket_id: str,
    platform: str,
    shopify_domain: str,
    customer_email: str,
    issue_text: str,
    order_id: str | None = None,
    customer_name: str | None = None,
    attachments: list[str] | None = None,
    mock_overrides: dict | None = None,
) -> AgentState:
    """Build initial state for a new ticket.

    Args:
        ticket_id: UUID of the created ticket.
        platform: Platform identifier (shopify, mock, etc.).
        shopify_domain: Tenant domain.
        customer_email: Customer's email address.
        issue_text: The customer's message.
        order_id: Optional platform order ID.
        customer_name: Optional customer display name.
        attachments: Optional list of attachment URLs.
        mock_overrides: Optional mock provider overrides (for testing).

    Returns:
        Initialized AgentState ready for the LangGraph pipeline.
    """
    return AgentState(
        ticket_id=ticket_id,
        platform=platform,
        shopify_domain=shopify_domain,
        customer_email=customer_email,
        customer_name=customer_name,
        order_id=order_id,
        issue_text=issue_text,
        issue_language="en",
        attachments=attachments or [],
        mock_overrides=mock_overrides or {},
        # All other fields start unset; nodes add them
        current_step="detect_intent",
        retry_count=0,
        fallback_used=False,
        status="processing",
        llm_call_count=0,
        requires_approval=False,
    )
