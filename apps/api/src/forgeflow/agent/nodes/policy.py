"""
ForgeFlow AI - Policy Check Node.

Fourth node in the agent pipeline. Checks which store policies apply
to the customer's issue.

Phase 1: Uses default industry-standard policies (hardcoded).
Phase 3: Three-tier policy resolution:
  Tier 1 — Hard rules (zero cost, instant)
  Tier 2 — pgvector semantic search over custom policies
  Tier 3 — DEFAULT_POLICIES + LLM judgment (fallback)
"""

from __future__ import annotations

import json
from typing import Any

from forgeflow.agent.prompts import DEFAULT_POLICIES, POLICY_CHECK_PROMPT
from forgeflow.agent.state import AgentState
from forgeflow.core.config import get_settings
from forgeflow.llm.base import LLMFactory
from forgeflow.llm.fallbacks import FALLBACK_POLICY_CHECK
from forgeflow.llm.resilience import LLMResilienceWrapper
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="agent.policy")


async def check_policy_node(state: AgentState) -> dict[str, Any]:
    """Check which store policies apply to the current issue.

    Three-tier resolution:
    1. Hard rules — instant match for common intents (zero LLM cost)
    2. pgvector semantic search — find custom policies uploaded by merchant
    3. DEFAULT_POLICIES + LLM — fallback for complex/ambiguous cases

    Args:
        state: AgentState with intent, order_info, logistics_status populated.

    Returns:
        Partial state update with relevant_policies and policy_match.
    """
    ticket_id = state.get("ticket_id", "unknown")
    intent = state.get("intent", "other")
    order_info = state.get("order_info") or {}

    settings = get_settings()

    # Build context for policy matching
    issue_text = state.get("issue_text", "")
    shopify_domain = state.get("shopify_domain", "default")
    fulfillment_status = order_info.get("fulfillment_status", "unknown")
    order_total = float(order_info.get("total_price", 0))
    intent_str = intent if isinstance(intent, str) else "other"

    # ── Tier 1: Hard rules (existing, unchanged) ──
    hard_matches = _hard_rule_policy_match(intent_str, fulfillment_status, order_total)
    if hard_matches and not _should_search_custom_policies(intent_str):
        logger.info(
            "policy_hard_rule_match",
            ticket_id=ticket_id,
            match_count=len(hard_matches),
        )
        return {
            "relevant_policies": hard_matches,
            "policy_match": True,
            "current_step": "policy_done",
        }

    # ── Tier 2: pgvector semantic search over custom policies ──
    custom_matches: list[dict[str, Any]] = []
    try:
        custom_matches = await _search_custom_policies(
            issue_text=issue_text,
            shopify_domain=shopify_domain,
            intent=intent_str,
        )
        if custom_matches:
            logger.info(
                "policy_custom_search_hits",
                ticket_id=ticket_id,
                hit_count=len(custom_matches),
            )
    except Exception as e:
        logger.warning(
            "policy_custom_search_failed",
            ticket_id=ticket_id,
            error=str(e)[:200],
        )

    # ── Tier 3: LLM judgment with merged policies ──
    # Merge custom matches with DEFAULT_POLICIES as fallback context
    policies_text = _build_policy_context(hard_matches or [], custom_matches)

    wrapper = LLMResilienceWrapper(
        provider=settings.llm.default_provider,
        model=settings.llm.default_model,
        fallback_value=FALLBACK_POLICY_CHECK,
    )

    try:
        prompt = POLICY_CHECK_PROMPT.format(
            issue_text=issue_text,
            intent=intent,
            fulfillment_status=fulfillment_status,
            order_total=order_total,
            policies_text=policies_text,
        )
        result = await wrapper.call(prompt)

        if result.data:
            data = dict(result.data)
            data["current_step"] = "policy_done"
            if not data.get("relevant_policies"):
                data["relevant_policies"] = []
            data["policy_match"] = len(data.get("relevant_policies", [])) > 0

            # If we found custom policies, annotate matches with source info
            if custom_matches and data.get("relevant_policies"):
                data["relevant_policies"] = _merge_custom_into_matches(
                    data["relevant_policies"], custom_matches
                )

            logger.info(
                "policy_check_done",
                ticket_id=ticket_id,
                match_count=len(data.get("relevant_policies", [])),
                custom_policies_searched=len(custom_matches) > 0,
                fallback_used=result.fallback_used,
            )
            return data

    except Exception as e:
        logger.error(
            "policy_check_failed",
            ticket_id=ticket_id,
            error=str(e)[:200],
        )
        raise

    return dict(FALLBACK_POLICY_CHECK, current_step="policy_done")


# ── Tier 1: Hard Rules ──


def _hard_rule_policy_match(
    intent: str,
    fulfillment_status: str,
    order_total: float,
) -> list[dict[str, Any]] | None:
    """Apply hardcoded policy matching rules (no LLM cost).

    Returns:
        List of matching policies, or None if no hard-rule match.
    """
    matches = []

    # Shipping delay → shipping policy always applies
    if intent == "shipping_delay":
        matches.append(
            {
                "policy_id": "default_shipping",
                "policy_title": "Standard Shipping Policy",
                "applies": True,
                "reasoning": "Customer reports shipping delay",
                "recommended_action": "refund or reship",
            }
        )

    # Refund request → refund policy applies
    if intent in ("refund_request", "damaged_item", "wrong_item"):
        matches.append(
            {
                "policy_id": "default_refund",
                "policy_title": "Standard Refund Policy",
                "applies": True,
                "reasoning": f"Customer requesting refund for {intent}",
                "recommended_action": "refund",
            }
        )

    # Exchange → exchange policy applies
    if intent == "exchange_request":
        matches.append(
            {
                "policy_id": "default_exchange",
                "policy_title": "Exchange Policy",
                "applies": True,
                "reasoning": "Customer requesting exchange",
                "recommended_action": "exchange",
            }
        )

    return matches if matches else None


def _should_search_custom_policies(intent: str) -> bool:
    """Determine if custom policy search is warranted.

    For straightforward intents like shipping_delay, hard rules usually
    suffice. For complex or ambiguous cases, search custom policies.
    """
    # Always search for these — merchants often have custom rules
    return intent in ("other", "damaged_item", "wrong_item", "exchange_request", "refund_request")


# ── Tier 2: pgvector Semantic Search ──


async def _search_custom_policies(
    issue_text: str,
    shopify_domain: str,
    intent: str,
) -> list[dict[str, Any]]:
    """Search for relevant custom policies using pgvector similarity.

    Opens its own short-lived DB session and embedding provider.
    Failures are caught by the caller — this function should not
    crash the pipeline.

    Returns:
        List of matching policy dicts with similarity scores.
    """
    from forgeflow.crud.policy import search_by_vector
    from forgeflow.db.engine import AsyncSessionLocal

    settings = get_settings()

    # Build a richer search query from the issue context
    search_query = _build_search_query(issue_text, intent)

    # Get embedding for the query
    try:
        embed_provider = LLMFactory.create(
            settings.llm.embedding_provider,
            model=settings.llm.embedding_model,
        )
        embed_result = await embed_provider.embed(search_query)
    except Exception:
        logger.warning("custom_policy_embed_provider_unavailable")
        return []

    if not embed_result.success or not embed_result.embedding:
        return []

    # Search the database
    try:
        async with AsyncSessionLocal() as db:
            hits = await search_by_vector(
                db,
                query_embedding=embed_result.embedding,
                shopify_domain=shopify_domain,
                limit=5,
                threshold=settings.llm.similarity_threshold,
            )
            # Convert ORM objects to dicts
            results: list[dict[str, Any]] = []
            for hit in hits:
                policy = hit["policy"]
                results.append(
                    {
                        "policy_id": str(policy.id),
                        "policy_title": policy.title,
                        "content": policy.content,
                        "category": policy.category,
                        "similarity": hit["similarity"],
                        "source": "custom",
                    }
                )
            return results
    except Exception:
        logger.warning("custom_policy_db_unavailable")
        return []


def _build_search_query(issue_text: str, intent: str) -> str:
    """Build an enriched search query from the issue context.

    Combines the original issue text with intent-specific keywords
    to improve retrieval relevance.
    """
    intent_keywords = {
        "shipping_delay": "shipping delay delivery time refund policy",
        "refund_request": "refund return money back policy",
        "damaged_item": "damaged defective product refund exchange policy",
        "wrong_item": "wrong item incorrect order exchange refund policy",
        "exchange_request": "exchange swap size color policy",
    }
    extra = intent_keywords.get(intent, "")
    return f"{issue_text} {extra}".strip()


# ── Tier 3 helpers ──


def _build_policy_context(
    hard_matches: list[dict[str, Any]],
    custom_matches: list[dict[str, Any]],
) -> str:
    """Merge hard rules and custom policy results into JSON for the LLM prompt.

    Custom policies take priority over DEFAULT_POLICIES. If custom matches
    exist, they are placed first in the context so the LLM considers them
    before falling back to defaults.
    """
    all_policies: list[dict[str, Any]] = []

    # Custom policies first (higher priority)
    for cm in custom_matches:
        all_policies.append(
            {
                "policy_id": cm["policy_id"],
                "policy_title": cm["policy_title"],
                "content": cm["content"][:1000],  # Truncate for LLM context window
                "category": cm.get("category"),
                "source": "custom",
                "similarity": cm.get("similarity"),
            }
        )

    # DEFAULT_POLICIES as fallback
    all_policies.extend(DEFAULT_POLICIES)

    return json.dumps(all_policies, indent=2, ensure_ascii=False)


def _merge_custom_into_matches(
    llm_matches: list[dict[str, Any]],
    custom_matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Annotate LLM-returned matches with custom policy source info.

    When the LLM references a policy that matches a custom policy by ID
    or title, attach the similarity score and source='custom' flag.
    """
    custom_by_id = {cm["policy_id"]: cm for cm in custom_matches}
    custom_by_title = {cm["policy_title"].lower(): cm for cm in custom_matches}

    for match in llm_matches:
        pid = match.get("policy_id", "")
        ptitle = (match.get("policy_title") or "").lower()

        if pid in custom_by_id:
            match["source"] = "custom"
            match["similarity"] = custom_by_id[pid].get("similarity")
        elif ptitle in custom_by_title:
            match["source"] = "custom"
            match["similarity"] = custom_by_title[ptitle].get("similarity")

    return llm_matches
