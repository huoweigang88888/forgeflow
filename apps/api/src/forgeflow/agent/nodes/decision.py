"""
ForgeFlow AI - Decision Node.

Fifth and most critical node in the agent pipeline. Determines the
recommended action (auto_refund, escalate, etc.) based on:

1. Hard rules (75% of cases, zero LLM cost):
   - No order_id → escalate
   - High urgency (chargeback/legal threat) → escalate
   - Unfulfilled order → auto_refund
   - Low value (< threshold) → auto_refund
   - Logistics delay/lost → auto_refund with approval
   - Fulfilled+delivered return/dispute → auto_refund with approval
   - Non-standard intent → escalate

2. LLM decision (25% of cases):
   - Complex cases where hard rules don't apply
   - Uses ModelRouter for cost-optimized model selection

From PRD Section 7.3.2: Decision Node.
"""

import json
from typing import Any

from forgeflow.agent.prompts import DECISION_PROMPT
from forgeflow.agent.state import AgentState
from forgeflow.core.config import get_settings
from forgeflow.llm.fallbacks import FALLBACK_DECISION
from forgeflow.llm.router import ModelRouter
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="agent.decision")


async def make_decision_node(state: AgentState) -> dict[str, Any]:
    """Make a decision on how to handle the ticket.

    Fast path: Hard rules determine the decision (70% of cases).
    Slow path: LLM weighs in for complex situations (30% of cases).

    Args:
        state: AgentState with all prior step data populated.

    Returns:
        Partial state update with decision fields.
    """
    ticket_id = state.get("ticket_id", "unknown")
    intent = state.get("intent", "other")
    order_info = state.get("order_info") or {}
    logistics_status = state.get("logistics_status") or {}
    llm_call_count = state.get("llm_call_count", 0)
    urgency = state.get("urgency", "low")
    customer_history = state.get("customer_history", {})

    settings = get_settings()
    auto_threshold = settings.llm.auto_refund_threshold
    order_total = order_info.get("total_price", 0)
    fulfillment_status = order_info.get("fulfillment_status", "unknown")
    logistics_state = logistics_status.get("status", "unknown")

    # =========================================================================
    # FAST PATH: Hard Rules (~70% of cases) — zero LLM cost
    # =========================================================================

    # Rule 0: No order_id → escalate (cannot process without an order)
    order_id_from_info = order_info.get("order_id") if order_info else None
    order_id_from_state = state.get("order_id")
    effective_order_id = order_id_from_info or order_id_from_state
    if not effective_order_id or (isinstance(effective_order_id, str) and effective_order_id.lower() in ("not provided", "unknown", "")):
        logger.info("decision_no_order_id", ticket_id=ticket_id)
        return _build_decision(
            action="escalate_to_human",
            amount=0.0,
            reason="No order ID provided — cannot process",
            requires_approval=False,
            explanation="The customer did not provide a valid order ID. Escalating for manual lookup.",
        )

    # Rule 0b: Chargeback / legal threat → escalate (keyword-based, no LLM cost)
    chargeback_keywords = [
        "chargeback", "charge back", "dispute with my bank", "file a dispute",
        "fraud", "lawsuit", "sue you", "legal action", "attorney", "lawyer",
        "better business bureau", "bbb", "ftc", "consumer protection",
    ]
    issue_text_lower = state.get("issue_text", "").lower()
    if any(kw in issue_text_lower for kw in chargeback_keywords):
        logger.info("decision_chargeback_threat", ticket_id=ticket_id)
        return _build_decision(
            action="escalate_to_human",
            amount=0.0,
            reason="Chargeback or legal threat detected — requires human handling",
            requires_approval=False,
            explanation=(
                "Customer has expressed a chargeback threat or legal action. "
                "Escalating to human for careful handling."
            ),
        )

    # Rule 1: Unfulfilled → auto_refund (no approval)
    if fulfillment_status == "unfulfilled" and intent in (
        "refund_request", "wrong_item", "damaged_item", "exchange_request",
    ):
        return _build_decision(
            action="auto_refund",
            amount=order_total,
            reason="Order not yet fulfilled",
            requires_approval=False,
            explanation=f"Order #{order_info.get('order_number', 'N/A')} is unfulfilled. "
            "Eligible for automatic refund.",
        )

    # Rule 2: Small amount → auto_refund (no approval)
    if order_total < auto_threshold and intent in (
        "refund_request", "shipping_delay", "damaged_item", "wrong_item",
    ):
        reason = _build_refund_reason(intent, logistics_state)
        return _build_decision(
            action="auto_refund",
            amount=order_total,
            reason=reason,
            requires_approval=False,
            explanation=(
                f"Order total ${order_total:.2f} is below auto-approval "
                f"threshold of ${auto_threshold:.2f}. Automatic refund approved."
            ),
        )

    # Rule 3: Logistics delay or lost → auto_refund with approval (if above threshold)
    # Covers shipping_delay, refund_request, damaged_item, wrong_item
    if logistics_state in ("delayed", "lost") and intent in (
        "shipping_delay", "refund_request", "damaged_item", "wrong_item",
    ):
        return _build_decision(
            action="auto_refund",
            amount=order_total,
            reason=f"Shipment {logistics_state} — {logistics_status.get('status_detail', 'no details')}",
            requires_approval=True,
            approval_reason=(
                f"Order value ${order_total:.2f} exceeds auto-approval "
                f"threshold of ${auto_threshold:.2f}"
            ),
            explanation=(
                f"Logistics confirms shipment is {logistics_state}. "
                f"Refund requires manager approval due to order value."
            ),
        )

    # Rule 4: Intent is irrelevant → escalate or notify
    if intent == "other":
        return _build_decision(
            action="escalate_to_human",
            amount=0.0,
            reason="Non-standard inquiry — requires human review",
            requires_approval=False,
            explanation="The customer's issue does not match standard after-sales categories.",
        )

    # Rule 5: High-value change-of-mind return or delivered dispute
    # (fulfilled + delivered + refund_request) → auto_refund with approval
    if (fulfillment_status == "fulfilled" and logistics_state == "delivered"
            and intent in ("refund_request", "shipping_delay", "damaged_item", "wrong_item")):
        # Repeat refunder check
        refund_count = customer_history.get("refund_count", 0)
        needs_approval = order_total >= auto_threshold or refund_count >= 3
        approval_reason = None
        if needs_approval:
            reasons = []
            if order_total >= auto_threshold:
                reasons.append(f"Order value ${order_total:.2f} >= threshold ${auto_threshold:.2f}")
            if refund_count >= 3:
                reasons.append(f"Customer has {refund_count} prior refunds (high risk)")
            approval_reason = "; ".join(reasons)

        return _build_decision(
            action="auto_refund",
            amount=order_total,
            reason="Customer disputes delivery or requests return",
            requires_approval=needs_approval,
            approval_reason=approval_reason,
            explanation=(
                f"Order is fulfilled and marked delivered. "
                f"Customer disputes delivery or requests return. "
                f"{'Approval required.' if needs_approval else 'Auto-approved.'}"
            ),
        )

    # =========================================================================
    # SLOW PATH: LLM Decision (~30% of cases)
    # Uses ModelRouter for two-tier cost optimization:
    #   1. Default (cheaper) model first
    #   2. Upgrade to complex model only if confidence < 0.7 (~5% of cases)
    # =========================================================================

    router = ModelRouter()

    try:
        prompt = DECISION_PROMPT.format(
            intent=intent,
            urgency=urgency,
            issue_text=state.get("issue_text", ""),
            order_info=json.dumps(order_info, indent=2),
            logistics_status=json.dumps(logistics_status, indent=2),
            customer_history=json.dumps(customer_history, indent=2),
        )
        result = await router.route_decision(prompt, {})

        if result.data:
            data = dict(result.data)
            # Validate and normalize
            data.setdefault("recommended_action", FALLBACK_DECISION["recommended_action"])
            data.setdefault("refund_amount", 0.0)
            data.setdefault("refund_reason", "")
            data.setdefault("requires_approval", False)
            data.setdefault("approval_reason", None)
            data.setdefault("decision_explanation", "")
            data.setdefault("customer_response", "")
            data["current_step"] = "decision_done"
            data["llm_call_count"] = llm_call_count + 1
            data["fallback_used"] = result.fallback_used

            logger.info(
                "decision_made",
                ticket_id=ticket_id,
                action=data["recommended_action"],
                requires_approval=data["requires_approval"],
                fallback_used=result.fallback_used,
            )
            return data

    except Exception as e:
        logger.error(
            "decision_failed",
            ticket_id=ticket_id,
            error=str(e)[:200],
        )
        raise

    return dict(FALLBACK_DECISION, current_step="decision_done")


def _build_refund_reason(intent: str, logistics_state: str) -> str:
    """Build a human-readable refund reason."""
    reason_map = {
        "shipping_delay": f"Shipping {logistics_state} — customer eligible for refund",
        "refund_request": "Customer requested refund",
        "damaged_item": "Customer reported damaged item",
        "wrong_item": "Customer received wrong item",
        "exchange_request": "Exchange requested — refunding original order",
    }
    return reason_map.get(intent, "Customer after-sales request")


def _build_decision(
    action: str,
    amount: float,
    reason: str,
    requires_approval: bool,
    explanation: str,
    approval_reason: str | None = None,
) -> dict[str, Any]:
    """Build a decision result dict consistently."""
    return {
        "recommended_action": action,
        "refund_amount": amount,
        "refund_reason": reason,
        "requires_approval": requires_approval,
        "approval_reason": approval_reason,
        "decision_explanation": explanation,
        "customer_response": "",
        "current_step": "decision_done",
    }
