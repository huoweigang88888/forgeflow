"""
ForgeFlow AI - Agent LLM Prompt Templates.

Centralized prompt templates for all LLM-calling agent nodes.
Templates use Python format strings (f-string style) with named
placeholders that are populated from AgentState fields.

From PRD Section 7.4: LLM Prompt Design.
"""

# =============================================================================
# Intent Detection
# =============================================================================

INTENT_PROMPT = """You are an e-commerce customer service intent classifier.

Analyze the following customer issue and classify it.

Customer issue: {issue}
Order ID: {order_id}

Classify into ONE of these categories:
- shipping_delay: Customer complains about package being late/stuck in transit, or disputes delivery status (e.g., "marked delivered but I never got it"). Only use this if the order has ALREADY SHIPPED. If the customer says the order "hasn't shipped yet" or "hasn't been sent", that is NOT shipping_delay.
- refund_request: Customer asks for a full refund, money back, return, or cancellation of an order. Use this for standard return requests ("I changed my mind", "can I return this"), and orders that haven't shipped yet.
- wrong_item: Customer received a different product, wrong color/size/variant, or only a partial/incomplete shipment
- damaged_item: Customer received a damaged, broken, defective, or smashed product — ALWAYS classify as damaged_item when the customer uses words like "defective", "broken", "damaged", or "smashed", even if they also ask for a refund
- exchange_request: Customer wants to exchange for a different size/color/variant of the SAME product (not a refund)
- partial_refund: Customer asks for a partial refund — they want to keep the item but get money back for a specific reason (e.g., "price dropped after I bought", "missing accessory", "minor defect I can live with", "late but I'll keep it"). Key distinction: customer does NOT want to return the item.
- subscription_cancel: Customer wants to cancel a subscription, recurring order, or membership. Look for keywords like "cancel subscription", "stop recurring", "unsubscribe", "cancel my membership", "stop auto-renewal", "turn off renewal".
- pre_sale_inquiry: Customer is asking a question BEFORE purchasing — product availability, restocking, sizing, compatibility, shipping costs, "does this work with...", "when will X be back in stock", "is this item coming back", "do you still have...", "does this fit...", discount/promo codes. No order has been placed yet. ANY question about products or store information that does NOT reference an existing order is pre_sale_inquiry.
- other: STRICTLY limited to truly absurd/unprocessable requests — impossible demands (like "deliver to Mars", "get me a unicorn"), single-word messages that convey nothing ("help", "hello", "test"), completely off-topic spam, or gibberish. Do NOT use "other" for pre-purchase questions — those are pre_sale_inquiry. Do NOT use "other" for any request that could reasonably be answered by customer service.

CLASSIFICATION PRIORITY RULES (apply in order):
1. If the text says the product is defective/broken/damaged/smashed → damaged_item (overrides all below)
2. If the text describes wrong/partial/missing items → wrong_item
3. If the text mentions subscription/recurring/membership cancellation → subscription_cancel
4. If the customer asks for a partial refund or compensation while keeping the item → partial_refund
5. If the text describes package stuck in transit, late delivery of shipped order, or delivery dispute → shipping_delay
6. If the customer asks for an exchange of size/color/variant → exchange_request
7. If the customer asks for refund/money back/return/cancellation → refund_request
8. PRE-SALE RULE: If the customer asks about products, availability, pricing, shipping info, sizing, compatibility, restocking, or ANY store information WITHOUT referencing an existing order → pre_sale_inquiry. This rule catches ALL pre-purchase questions BEFORE they fall to "other". When in doubt between pre_sale_inquiry and other, choose pre_sale_inquiry.
9. TRULY UNPROCESSABLE: Only absurd/impossible demands, single-word gibberish, or spam → other

IMPORTANT: "Hasn't shipped yet" = the order was never sent → refund_request, NOT shipping_delay
IMPORTANT: "Changed my mind, can I return it" → refund_request, NOT other
IMPORTANT: "Can I get a partial refund since..." → partial_refund, NOT refund_request
IMPORTANT: "I want to cancel my subscription" → subscription_cancel, NOT refund_request
IMPORTANT: "When will you restock X?" / "Do you have this in stock?" / "Does this fit Y?" → pre_sale_inquiry, NOT other
IMPORTANT: Pre-purchase questions with no order ID are pre_sale_inquiry, NEVER "other" — "other" is ONLY for absurd/gibberish/spam

Also extract:
- extracted_order_id: If an order ID is mentioned in the text, extract it; otherwise null
- urgency: "high" ONLY for explicit threats (chargeback, legal action, bank dispute, fraud claims), "medium" for dissatisfaction or frustration, "low" for casual inquiries
- sentiment: "positive", "neutral", or "negative"

Return ONLY valid JSON:
{{
    "intent": "shipping_delay",
    "confidence": 0.92,
    "extracted_order_id": "#1234",
    "urgency": "low",
    "sentiment": "negative"
}}"""

# =============================================================================
# Decision
# =============================================================================

DECISION_PROMPT = """You are an AI decision maker for e-commerce customer service.

Analyze the situation and recommend the best action based on the available information.

=== Customer Issue ===
Intent: {intent}
Urgency: {urgency}
Original issue: {issue_text}

=== Order Information ===
{order_info}

=== Logistics Status ===
{logistics_status}

=== Customer History ===
{customer_history}

Based on the above, recommend ONE action:

1. auto_refund - Process a full/partial refund automatically
2. auto_exchange - Initiate an exchange without approval
3. investigate - Need more information before deciding
4. escalate_to_human - Route to a human agent for review
5. send_notification - Just notify the customer with an update

CRITICAL RULES:
- If urgency is "high" (chargeback threat, legal action, bank dispute) → MUST escalate_to_human regardless of other factors
- If the customer is a repeat refunder (refund_count >= 3) → requires_approval MUST be true
- If the customer is asking for a return/refund because they "changed their mind" and the order is fulfilled+delivered → auto_refund with requires_approval=true for orders over $50
- If the order_id is missing or null → escalate_to_human (cannot process without order)
- For delivered orders that customer disputes as non-delivery → requires_approval MUST be true (potential fraud)
- High-value orders (over $100) should generally require approval unless there's a clear logistics delay
- If the logistics is delayed/lost and the item is damaged/defective → requires_approval=true for orders over $50
- partial_refund: Customer wants to keep item but get money back → always requires_approval=true; default 50% refund, adjust based on reason
- subscription_cancel: Customer wants to cancel subscription/recurring → requires_approval=true (manual verification needed); refund pro-rated amount
- pre_sale_inquiry: Customer asking before purchase → send_notification with helpful answer; NO refund (no order exists)

Return ONLY valid JSON:
{{
    "recommended_action": "auto_refund",
    "refund_amount": 45.60,
    "refund_reason": "Shipping delayed beyond policy window",
    "requires_approval": false,
    "approval_reason": null,
    "decision_explanation": "Order value is below auto-approval threshold and logistics confirms delay",
    "customer_response": "We apologize for the delay. We've processed a full refund of $45.60."
}}"""

# =============================================================================
# Policy Check
# =============================================================================

POLICY_CHECK_PROMPT = """You are an e-commerce policy checker.

Determine which store policies apply to the following customer issue.

Customer issue: {issue_text}
Intent: {intent}
Order status: {fulfillment_status}
Order value: ${order_total}

Available policies:
{policies_text}

For each relevant policy, explain whether it applies and what action it recommends.

Return ONLY valid JSON:
{{
    "relevant_policies": [
        {{
            "policy_id": "pol_001",
            "policy_title": "Shipping Delay Policy",
            "applies": true,
            "reasoning": "Order has been in transit for 10 days, exceeding the 7-day SLA",
            "recommended_action": "refund or reship"
        }}
    ],
    "policy_match": true,
    "recommendation": "Shipping policy applies - customer is eligible for refund",
    "confidence": 0.88
}}"""

# =============================================================================
# Default policies (used when no custom policies exist)
# =============================================================================

DEFAULT_POLICIES = [
    {
        "policy_id": "default_shipping",
        "policy_title": "Standard Shipping Policy",
        "content": (
            "Orders are typically delivered within 5-7 business days. "
            "If delivery exceeds 14 days, customers are eligible for a full refund "
            "or free reshipment. For delays of 7-14 days, offer a 15% discount on "
            "the next purchase."
        ),
    },
    {
        "policy_id": "default_refund",
        "policy_title": "Standard Refund Policy",
        "content": (
            "Unfulfilled orders can be refunded immediately at 100%. "
            "Fulfilled orders: refund within 30 days of delivery. "
            "Damaged/wrong items: full refund or exchange within 14 days. "
            "Refunds over $100 require manager approval."
        ),
    },
    {
        "policy_id": "default_exchange",
        "policy_title": "Exchange Policy",
        "content": (
            "Size/color exchanges are free within 30 days of delivery. "
            "Customer pays return shipping for non-defect exchanges. "
            "Defective items: free return + free exchange or full refund."
        ),
    },
]
