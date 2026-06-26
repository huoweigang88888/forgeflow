"""
ForgeFlow AI - Error Handler Node.

Unified error handler for all agent nodes. LangGraph routes to this
node when any node raises an exception.

Classifies errors and decides:
- Retry the failed node (transient errors with retries remaining)
- Use fallback value and continue (known error types)
- Escalate to human (unrecoverable errors)

From PRD Section 14.3: Global Error Handling State Machine.
"""

from typing import Any

from forgeflow.agent.retry_config import (
    NODE_RETRY_CONFIGS,
    ErrorType,
    classify_error,
)
from forgeflow.agent.state import AgentState
from forgeflow.llm.fallbacks import DEFAULT_FALLBACK
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="agent.error_handler")


async def handle_error_node(state: AgentState) -> dict[str, Any]:
    """Handle errors from any agent node.

    Called by LangGraph when a node raises an exception. Classifies
    the error and decides the recovery strategy.

    Args:
        state: Current AgentState (includes error_message).

    Returns:
        Partial state update with recovery action.
    """
    ticket_id = state.get("ticket_id", "unknown")
    current_step = state.get("current_step", "unknown")
    error_message = state.get("error_message") or "Unknown error"
    retry_count = state.get("retry_count", 0)
    config = NODE_RETRY_CONFIGS.get(current_step)

    error_type = classify_error(error_message)

    logger.warning(
        "agent_error_handler_invoked",
        ticket_id=ticket_id,
        current_step=current_step,
        error_type=error_type.value,
        error=error_message[:200],
        retry_count=retry_count,
    )

    # =========================================================================
    # No config → safe terminate (unknown node)
    # =========================================================================
    if not config:
        logger.error(
            "agent_error_no_config",
            ticket_id=ticket_id,
            current_step=current_step,
        )
        return {
            "execution_status": "failed",
            "recommended_action": "escalate_to_human",
            "decision_explanation": (
                f"Unexpected error in '{current_step}': {error_message[:200]}"
            ),
            "status": "failed",
            "error_message": error_message,
            "current_step": current_step,
        }

    # =========================================================================
    # Timeout or API error → retry if retries remain
    # =========================================================================
    if error_type in (ErrorType.TIMEOUT, ErrorType.API_ERROR) and retry_count < config.max_retries:
        logger.info(
            "agent_retrying",
            ticket_id=ticket_id,
            current_step=current_step,
            attempt=retry_count + 1,
            max_retries=config.max_retries,
        )
        return {
            "retry_count": retry_count + 1,
            "current_step": current_step,  # Re-run same node
            "error_message": None,
        }

    # =========================================================================
    # Validation error → escalate (data problem, retry won't help)
    # =========================================================================
    if error_type == ErrorType.VALIDATION_ERROR:
        return {
            "recommended_action": "escalate_to_human",
            "decision_explanation": f"Data validation failed: {error_message[:200]}",
            "status": "escalated",
            **{k: v for k, v in config.fallback_value.items() if k != "current_step"},
        }

    # =========================================================================
    # LLM error → use fallback value and continue
    # =========================================================================
    if error_type == ErrorType.LLM_ERROR:
        logger.info(
            "agent_using_fallback",
            ticket_id=ticket_id,
            current_step=current_step,
        )
        return {
            **{k: v for k, v in config.fallback_value.items() if k != "current_step"},
            "fallback_used": True,
            "error_message": error_message,
            "current_step": f"{current_step}_done",
        }

    # =========================================================================
    # Unknown error → safe terminate + escalate
    # =========================================================================
    logger.error(
        "agent_unknown_error_escalating",
        ticket_id=ticket_id,
        current_step=current_step,
        error=error_message[:200],
    )
    return {
        "execution_status": "failed",
        "recommended_action": "escalate_to_human",
        "decision_explanation": (
            f"Unexpected system error in '{current_step}'. "
            f"Manual review required. Error: {error_message[:200]}"
        ),
        "status": "failed",
        "error_message": error_message,
        **DEFAULT_FALLBACK,
    }
