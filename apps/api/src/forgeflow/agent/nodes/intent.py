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


# ── Pre-Sale Inquiry Keyword Patterns ──
# Fast-path detection for pre-purchase questions that require zero LLM cost.
# These are NOT after-sales issues — they have no order context and should
# trigger an informational notification, not escalation.
_PRE_SALE_PATTERNS: list[tuple[str, float]] = [
    # Restock / availability
    (r"\b(restock|re[ -]?stock)\b", 0.95),
    (r"\bwhen\s+will\s+(you\s+)?(have|get)\b", 0.90),
    (r"\b(back\s+in\s+stock|come\s+back\s+in\s+stock|coming\s+back)\b", 0.95),
    (
        r"\b(is|are)\s+(this|that|the|these|those|it|they)\s+(still\s+)?(available|in\s+stock)\b",
        0.88,
    ),
    (r"\bdo\s+you\s+(still\s+)?(have|carry|sell|stock)\b", 0.88),
    (r"\bwhen\s+(is|are)\s+(this|that|the|these|those|it|they)\s+(available|back|coming)\b", 0.88),
    # Sizing / fit questions
    (r"\b(what|which)\s+size\s+(should|do|would|is\s+right|is\s+best)\b", 0.92),
    (r"\b(does|will)\s+(this|that|it)\s+(fit|work\s+with|match)\b", 0.90),
    (r"\b(size\s+chart|sizing\s+guide|measurements?\s+for)\b", 0.92),
    # Compatibility / product info
    (r"\b(is|are)\s+(this|that|these|those|it|they)\s+compatible\b", 0.90),
    (r"\b(does|do)\s+(this|that|these|those|it|they)\s+(work|come)\s+with\b", 0.88),
    (r"\b(how\s+(much|many)|what\s+is\s+the)\s+(does|do)\b", 0.85),
    # Shipping cost / delivery time inquiries (pre-purchase context)
    (r"\bhow\s+(much|long)\s+(is|does|would|will)\s+shipping\b", 0.90),
    (r"\bdo\s+you\s+ship\s+(to|internationally)\b", 0.92),
    # Discount / promo inquiries (any pattern with coupon/discount/promo)
    (r"\b(coupon|discount|promo)\s+(code|offer|available|for)\b", 0.90),
    (r"\bany\s+(coupon|discount|promo)", 0.90),
    (r"\b(discount|promo)\s+for\b", 0.88),
]


def _check_pre_sale_hard_rules(issue_text: str, order_id: str | None) -> dict[str, Any] | None:
    """Fast-path hard-rule check for pre-sale inquiries.

    When a customer asks a pre-purchase question with no order context,
    we can bypass the LLM entirely. This saves cost AND eliminates
    classification boundary errors (golden_006).

    Safety: patterns are conservative to avoid false positives.
    If the text contains purchase-indicating words (my order, my package,
    my shipment, refund, tracking), we skip the hard rule and let the
    LLM decide — these are likely after-sales issues.

    Returns:
        Intent data dict if pre-sale is detected, None otherwise.
    """
    order_id_str = order_id if order_id else ""
    has_order = bool(
        order_id_str and order_id_str.lower() not in ("not provided", "unknown", "", "null", "none")
    )

    # If the customer has an order, this is NOT a pre-sale inquiry
    if has_order:
        return None

    import re

    text_lower = issue_text.lower().strip()

    # ── Safety filter: skip hard rule if text contains purchase-indicating terms ──
    # These suggest the customer already has an order and needs after-sales service.
    _PURCHASE_INDICATORS = [
        r"\bmy\s+order\b",
        r"\bmy\s+package\b",
        r"\bmy\s+shipment\b",
        r"\bmy\s+parcel\b",
        r"\bmy\s+delivery\b",
        r"\b(refund|money\s+back|return)\b",
        r"\btracking\s*(number|#|id)",
        r"\bwhere\s+is\s+my\b",
    ]
    for indicator_pattern in _PURCHASE_INDICATORS:
        if re.search(indicator_pattern, text_lower):
            logger.info(
                "intent_pre_sale_skipped_purchase_indicator",
                indicator=indicator_pattern,
            )
            return None

    for pattern, confidence in _PRE_SALE_PATTERNS:
        if re.search(pattern, text_lower):
            logger.info(
                "intent_pre_sale_hard_rule",
                pattern=pattern,
                confidence=confidence,
            )
            return {
                "intent": "pre_sale_inquiry",
                "confidence": confidence,
                "extracted_order_id": None,
                "urgency": "low",
                "sentiment": "neutral",
                "current_step": "intent_done",
                "llm_call_count": 0,
                "fallback_used": False,
            }

    return None


async def detect_intent_node(state: AgentState) -> dict[str, Any]:
    """Detect the customer's intent from their issue text.

    Uses a multi-layered approach:
    1. Hard-rule keyword matching for pre-sale inquiries (zero LLM cost)
    2. LLM classification with 3-layer fallback for all other intents
    3. Language detection via langdetect

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

    # === Layer 0: Hard-rule pre-sale detection (golden_006 fix) ===
    pre_sale_result = _check_pre_sale_hard_rules(issue_text, order_id)
    if pre_sale_result is not None:
        pre_sale_result["issue_language"] = detected_language
        logger.info(
            "intent_detected_fast_path",
            ticket_id=state.get("ticket_id"),
            intent="pre_sale_inquiry",
            method="hard_rule",
        )
        return pre_sale_result

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
