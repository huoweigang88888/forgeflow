"""
ForgeFlow AI - Agent Node Retry Configuration.

Defines per-node retry policies (timeout, max retries, backoff, fallback)
based on the strategy matrix from PRD Section 14.2.

Also provides error classification for the unified error handler node.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from forgeflow.llm.fallbacks import (
    FALLBACK_DECISION,
    FALLBACK_INTENT,
    FALLBACK_POLICY_CHECK,
)


class ErrorType(Enum):
    """Classification of error types for the error handler node."""

    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    LLM_ERROR = "llm_error"
    UNKNOWN = "unknown"


@dataclass
class NodeRetryConfig:
    """Retry and fallback configuration for a single agent node.

    Defines how many times to retry, with what backoff, and what value to
    use as a safe fallback if all retries are exhausted.
    """

    node_name: str
    timeout_seconds: int
    max_retries: int
    retry_backoff_seconds: list[int]  # e.g., [1, 2, 4] = 1s, 2s, 4s delays
    fallback_value: dict[str, Any]


# ── Per-node configurations (from PRD §14.2) ──

NODE_RETRY_CONFIGS: dict[str, NodeRetryConfig] = {
    "detect_intent": NodeRetryConfig(
        node_name="detect_intent",
        timeout_seconds=3,
        max_retries=2,
        retry_backoff_seconds=[1, 2],
        fallback_value=FALLBACK_INTENT,
    ),
    "lookup_order": NodeRetryConfig(
        node_name="lookup_order",
        timeout_seconds=5,
        max_retries=3,
        retry_backoff_seconds=[1, 2, 4],
        fallback_value={
            "order_info": None,
            "source": "cache_fallback",
        },
    ),
    "check_logistics": NodeRetryConfig(
        node_name="check_logistics",
        timeout_seconds=8,
        max_retries=2,
        retry_backoff_seconds=[2, 4],
        fallback_value={
            "logistics_status": {"status": "unknown"},
            "tracking_number": None,
        },
    ),
    "check_policy": NodeRetryConfig(
        node_name="check_policy",
        timeout_seconds=3,
        max_retries=2,
        retry_backoff_seconds=[1, 2],
        fallback_value=FALLBACK_POLICY_CHECK,
    ),
    "make_decision": NodeRetryConfig(
        node_name="make_decision",
        timeout_seconds=10,
        max_retries=1,
        retry_backoff_seconds=[2],
        fallback_value=FALLBACK_DECISION,
    ),
    "execute": NodeRetryConfig(
        node_name="execute",
        timeout_seconds=15,
        max_retries=3,
        retry_backoff_seconds=[2, 4, 8],
        fallback_value={
            "execution_status": "pending_manual",
            "execution_result": {
                "error": "Execution failed, requires manual intervention"
            },
        },
    ),
}


def classify_error(error_message: str) -> ErrorType:
    """Classify an error message into a standard error type.

    Used by the error handler node to determine the appropriate
    recovery strategy (retry vs. fallback vs. escalate).

    Args:
        error_message: The error message or exception string to classify.

    Returns:
        The classified ErrorType.
    """
    if not error_message:
        return ErrorType.UNKNOWN

    error_lower = error_message.lower()

    if "timeout" in error_lower or "timed out" in error_lower:
        return ErrorType.TIMEOUT

    if any(kw in error_lower for kw in ("api", "rate limit", "5xx", "4xx", "connection")):
        return ErrorType.API_ERROR

    if any(kw in error_lower for kw in ("validation", "schema", "json", "parse")):
        return ErrorType.VALIDATION_ERROR

    if any(kw in error_lower for kw in ("llm", "openai", "anthropic", "model", "token")):
        return ErrorType.LLM_ERROR

    return ErrorType.UNKNOWN
