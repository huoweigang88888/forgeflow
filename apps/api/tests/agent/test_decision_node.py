"""
ForgeFlow AI - Decision Node Tests.

Tests the make_decision_node with hard rules (no LLM needed) and
complex cases (LLM required). Uses mock providers.

From PRD Section 15.3: Decision Accuracy Evaluation.
"""

import pytest

from forgeflow.agent.nodes.decision import make_decision_node
from forgeflow.agent.state import AgentState
from forgeflow.core.config import get_settings


def _make_state(
    intent: str = "shipping_delay",
    fulfillment_status: str = "fulfilled",
    total_price: float = 45.60,
    logistics_status: str = "delayed",
    platform: str = "mock",
) -> AgentState:
    """Build a realistic mid-pipeline AgentState for decision tests."""
    return AgentState(
        ticket_id="test_decision_001",
        platform=platform,
        shopify_domain="test.myshopify.com",
        customer_email="buyer@test.com",
        issue_text="Where is my order? It's been 2 weeks!",
        order_id="order_123",
        intent=intent,
        confidence=0.92,
        order_info={
            "order_id": "order_123",
            "order_number": "#12345",
            "customer_email": "buyer@test.com",
            "customer_name": "John Doe",
            "total_price": total_price,
            "currency": "USD",
            "fulfillment_status": fulfillment_status,
            "financial_status": "paid",
            "tracking_number": "TRACK123",
            "tracking_carrier": "UPS",
        },
        logistics_status={
            "status": logistics_status,
            "status_detail": "Package delayed at sorting facility",
            "days_in_transit": 12,
        },
        relevant_policies=[
            {
                "policy_id": "default_shipping",
                "policy_title": "Standard Shipping Policy",
                "applies": True,
                "recommended_action": "refund or reship",
            }
        ],
        current_step="make_decision",
        retry_count=0,
        fallback_used=False,
        status="processing",
        llm_call_count=0,
        requires_approval=False,
    )


settings = get_settings()
THRESHOLD = settings.llm.auto_refund_threshold


# =============================================================================
# Hard Rule 1: Unfulfilled → auto_refund (no approval)
# =============================================================================


@pytest.mark.asyncio
async def test_decision_unfulfilled_order_auto_refund():
    """Unfulfilled order with refund request → auto_refund without approval."""
    state = _make_state(
        intent="refund_request",
        fulfillment_status="unfulfilled",
        total_price=150.00,  # Above threshold, but unfulfilled rules bypass
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is False
    assert result["refund_amount"] == 150.00


@pytest.mark.asyncio
async def test_decision_unfulfilled_damaged_item_auto_refund():
    """Unfulfilled + damaged item report → auto_refund without approval."""
    state = _make_state(
        intent="damaged_item",
        fulfillment_status="unfulfilled",
        total_price=200.00,
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is False


# =============================================================================
# Hard Rule 2: Low value → auto_refund (no approval)
# =============================================================================


@pytest.mark.asyncio
async def test_decision_low_value_auto_refund():
    """Low-value fulfilled order → auto_refund without approval."""
    state = _make_state(
        intent="refund_request",
        fulfillment_status="fulfilled",
        total_price=THRESHOLD - 1.0,  # Just below threshold
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is False
    assert result["refund_amount"] == THRESHOLD - 1.0


@pytest.mark.asyncio
async def test_decision_low_value_shipping_delay_auto_refund():
    """Low-value shipping delay → auto_refund without approval."""
    state = _make_state(
        intent="shipping_delay",
        fulfillment_status="fulfilled",
        total_price=10.00,  # Well below threshold
        logistics_status="in_transit",
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is False


# =============================================================================
# Hard Rule 3: Logistics delay + high value → auto_refund (with approval)
# =============================================================================


@pytest.mark.asyncio
async def test_decision_high_value_logistics_delay_requires_approval():
    """High-value delayed order → auto_refund with manager approval."""
    state = _make_state(
        intent="shipping_delay",
        fulfillment_status="fulfilled",
        total_price=THRESHOLD + 50.0,
        logistics_status="delayed",
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is True
    assert result["approval_reason"] is not None
    assert "threshold" in result.get("approval_reason", "").lower()


@pytest.mark.asyncio
async def test_decision_lost_shipment_requires_approval():
    """Lost shipment (high value) → auto_refund with approval."""
    state = _make_state(
        intent="refund_request",
        fulfillment_status="fulfilled",
        total_price=THRESHOLD + 100.0,
        logistics_status="lost",
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is True


# =============================================================================
# Hard Rule 4b: pre_sale_inquiry → send_notification
# =============================================================================


@pytest.mark.asyncio
async def test_decision_pre_sale_inquiry_notify():
    """Pre-sale inquiry → send_notification (no order context)."""
    state = _make_state(intent="pre_sale_inquiry")
    result = await make_decision_node(state)

    assert result["recommended_action"] == "send_notification"
    assert result["requires_approval"] is False
    assert result["refund_amount"] == 0.0


# =============================================================================
# Hard Rule 4c: subscription_cancel → auto_refund with approval
# =============================================================================


@pytest.mark.asyncio
async def test_decision_subscription_cancel_requires_approval():
    """Subscription cancel → auto_refund with approval."""
    state = _make_state(
        intent="subscription_cancel",
        fulfillment_status="fulfilled",
        total_price=29.99,
        logistics_status="delivered",
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is True
    assert result["approval_reason"] is not None
    assert "subscription" in result.get("approval_reason", "").lower()


# =============================================================================
# Hard Rule 4d: partial_refund → auto_refund with approval
# =============================================================================


@pytest.mark.asyncio
async def test_decision_partial_refund_requires_approval():
    """Partial refund → auto_refund with approval (default 50%)."""
    state = _make_state(
        intent="partial_refund",
        fulfillment_status="fulfilled",
        total_price=80.00,
        logistics_status="delivered",
    )
    result = await make_decision_node(state)

    assert result["recommended_action"] == "auto_refund"
    assert result["requires_approval"] is True
    # Default 50% of 80.00 = 40.00
    assert result["refund_amount"] == 40.00


# =============================================================================
# Hard Rule 5: "other" intent → escalate
# =============================================================================


@pytest.mark.asyncio
async def test_decision_other_intent_escalates():
    """Non-standard inquiry → escalate_to_human."""
    state = _make_state(intent="other")
    result = await make_decision_node(state)

    assert result["recommended_action"] == "escalate_to_human"
    assert result["requires_approval"] is False


# =============================================================================
# Output field validation
# =============================================================================


@pytest.mark.asyncio
async def test_decision_all_required_fields_present():
    """Decision result must include all expected fields."""
    state = _make_state(intent="damaged_item", total_price=20.0)
    result = await make_decision_node(state)

    required_fields = [
        "recommended_action",
        "refund_amount",
        "refund_reason",
        "requires_approval",
        "decision_explanation",
        "current_step",
    ]
    for field in required_fields:
        assert field in result, f"Missing required field: {field}"


@pytest.mark.asyncio
async def test_decision_approval_reason_set_when_required():
    """When requires_approval is True, approval_reason must be set."""
    state = _make_state(
        intent="shipping_delay",
        total_price=THRESHOLD + 100.0,
        logistics_status="delayed",
    )
    result = await make_decision_node(state)

    if result["requires_approval"]:
        assert result.get(
            "approval_reason"
        ), "approval_reason must be set when requires_approval is True"
