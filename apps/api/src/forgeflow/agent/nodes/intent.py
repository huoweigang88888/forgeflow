"""
ForgeFlow AI - Intent Detection Node.

First node in the agent pipeline. Uses LLM to classify the customer's
issue into one of 6 intent categories.

From PRD Section 7.3.1: Intent Detection Node.
"""

from typing import Any

from forgeflow.agent.prompts import INTENT_PROMPT
from forgeflow.agent.state import AgentState
from forgeflow.core.config import get_settings
from forgeflow.llm.fallbacks import FALLBACK_INTENT
from forgeflow.llm.resilience import LLMResilienceWrapper
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="agent.intent")


async def detect_intent_node(state: AgentState) -> dict[str, Any]:
    """Detect the customer's intent from their issue text.

    Uses LLM classification with 3-layer fallback. The node:
    1. Extracts intent, confidence, urgency, sentiment
    2. Extracts order ID from text if present
    3. Falls back to FALLBACK_INTENT if LLM fails

    Args:
        state: Current AgentState with at least issue_text populated.

    Returns:
        Partial state update with intent fields.
    """
    settings = get_settings()
    issue_text = state.get("issue_text", "")
    order_id = state.get("order_id", "Not provided")

    if not issue_text.strip():
        logger.warning("intent_empty_issue", ticket_id=state.get("ticket_id"))
        return dict(FALLBACK_INTENT, current_step="intent_done")

    wrapper = LLMResilienceWrapper(
        provider=settings.llm.default_provider,
        model=settings.llm.default_model,
        fallback_value=FALLBACK_INTENT,
    )

    try:
        prompt = INTENT_PROMPT.format(issue=issue_text, order_id=order_id)
        result = await wrapper.call(prompt)

        if result.data:
            data = dict(result.data)
            # Ensure all expected fields are present
            data.setdefault("intent", FALLBACK_INTENT["intent"])
            data.setdefault("confidence", FALLBACK_INTENT["confidence"])
            data.setdefault("extracted_order_id", None)
            data.setdefault("urgency", FALLBACK_INTENT["urgency"])
            data.setdefault("sentiment", FALLBACK_INTENT["sentiment"])
            data["current_step"] = "intent_done"
            data["llm_call_count"] = state.get("llm_call_count", 0) + 1
            data["fallback_used"] = result.fallback_used

            logger.info(
                "intent_detected",
                ticket_id=state.get("ticket_id"),
                intent=data["intent"],
                confidence=data["confidence"],
                fallback_used=result.fallback_used,
            )
            return data

    except Exception as e:
        logger.error(
            "intent_failed",
            ticket_id=state.get("ticket_id"),
            error=str(e)[:200],
        )
        # Re-raise so LangGraph routes to handle_error node
        raise

    # Should not reach here, but safe fallback
    return dict(FALLBACK_INTENT, current_step="intent_done")
