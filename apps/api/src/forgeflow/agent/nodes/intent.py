"""
ForgeFlow AI - Intent Detection Node.

First node in the agent pipeline. Uses LLM to classify the customer's
issue into one of 9 intent categories. Also detects the language of
the customer's issue text using langdetect.

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


# Language detection — lazy import to avoid hard dependency at import time
def _detect_language(text: str) -> str:
    """Detect the language of the given text using langdetect.

    Returns a 2-letter ISO 639-1 language code (e.g., 'en', 'zh', 'ja').
    Falls back to 'en' on any detection failure.
    """
    if not text or not text.strip():
        return "en"
    try:
        from langdetect import DetectorFactory, detect  # type: ignore[import-untyped]

        # Set seed for consistent results
        DetectorFactory.seed = 0
        detected = detect(text[:500])  # First 500 chars is enough
        logger.info("language_detected", detected=detected, text_preview=text[:80])
        return detected
    except ImportError:
        logger.warning(
            "langdetect_not_installed",
            hint="Install with: uv add langdetect",
        )
        return "en"
    except Exception:
        # langdetect raises LangDetectException on short/ambiguous text
        return "en"


async def detect_intent_node(state: AgentState) -> dict[str, Any]:
    """Detect the customer's intent from their issue text.

    Uses LLM classification with 3-layer fallback. The node:
    1. Detects language of issue_text via langdetect
    2. Extracts intent, confidence, urgency, sentiment
    3. Extracts order ID from text if present
    4. Falls back to FALLBACK_INTENT if LLM fails

    Args:
        state: Current AgentState with at least issue_text populated.

    Returns:
        Partial state update with intent fields and issue_language.
    """
    settings = get_settings()
    issue_text = state.get("issue_text", "")
    order_id = state.get("order_id", "Not provided")

    # Detect language (always run, even if empty)
    detected_language = _detect_language(issue_text)

    if not issue_text.strip():
        logger.warning("intent_empty_issue", ticket_id=state.get("ticket_id"))
        result = dict(FALLBACK_INTENT, current_step="intent_done")
        result["issue_language"] = detected_language
        return result

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
            data["issue_language"] = detected_language

            logger.info(
                "intent_detected",
                ticket_id=state.get("ticket_id"),
                intent=data["intent"],
                confidence=data["confidence"],
                language=detected_language,
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
    result = dict(FALLBACK_INTENT, current_step="intent_done")
    result["issue_language"] = detected_language
    return result
