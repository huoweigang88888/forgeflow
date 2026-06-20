"""
ForgeFlow AI - LLM Fallback Values.

Static fallback values for each agent node when all LLM attempts fail.
These ensure the system always produces a reasonable output, even if
not optimal. The fallback values are conservative (safe defaults).

From PRD Section 14.1, Layer 3: Safe Fallback Templates.
"""

# ── Intent Detection Fallback ──
FALLBACK_INTENT = {
    "intent": "other",
    "confidence": 0.0,
    "extracted_order_id": None,
    "urgency": "medium",
    "sentiment": "neutral",
}

# ── Decision Fallback ──
FALLBACK_DECISION = {
    "recommended_action": "escalate_to_human",
    "refund_amount": 0.0,
    "refund_reason": "Unable to determine automatically",
    "requires_approval": True,
    "approval_reason": "Automated decision failed — requires human review",
    "decision_explanation": (
        "The AI system was unable to make a confident decision. "
        "The ticket has been escalated for human review to ensure accuracy."
    ),
    "customer_response": (
        "Thank you for your patience. Your request requires additional review. "
        "Our team will get back to you shortly."
    ),
}

# ── Policy Check Fallback ──
FALLBACK_POLICY_CHECK = {
    "relevant_policies": [],
    "policy_match": False,
    "recommendation": "No matching policy found — escalate for manual review",
    "confidence": 0.0,
}

# ── Node-Specific Fallbacks Map ──
NODE_FALLBACKS = {
    "detect_intent": FALLBACK_INTENT,
    "make_decision": FALLBACK_DECISION,
    "check_policy": FALLBACK_POLICY_CHECK,
}

# ── Default catch-all ──
DEFAULT_FALLBACK = {
    "error": "fallback_triggered",
    "message": "Automated processing failed. Escalating to human agent.",
}
