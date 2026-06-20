"""
ForgeFlow AI — Seed Policy Documents.

Populates the policy_documents table with sample store policies
for development and testing. Embedding generation requires an
active OpenAI API key.

Usage:
    cd apps/api
    python -m scripts.seed_policies
"""

from __future__ import annotations

import asyncio

from forgeflow.core.config import get_settings
from forgeflow.crud.policy import create_policy, set_embedding
from forgeflow.db.engine import AsyncSessionLocal
from forgeflow.llm.base import LLMFactory

# ── Sample Policy Documents ──

SAMPLE_POLICIES = [
    {
        "title": "Premium Shipping Guarantee",
        "content": (
            "Premium shipping customers receive guaranteed delivery within "
            "3 business days from the ship date. If delivery exceeds 3 business "
            "days, the customer is entitled to a 25% refund of shipping costs "
            "plus a $10 store credit. After 7 business days, customers qualify "
            "for a full shipping refund and free reshipment via express delivery. "
            "Customers must contact support within 14 days of the expected "
            "delivery date to claim this guarantee. This policy does not apply "
            "to delays caused by weather events, natural disasters, or incorrect "
            "shipping addresses provided by the customer."
        ),
        "category": "shipping",
        "tags": ["premium", "guarantee", "express", "refund"],
    },
    {
        "title": "Standard Return & Refund Policy",
        "content": (
            "Customers may return most new, unopened items within 30 days of "
            "delivery for a full refund. Items must be in original packaging "
            "with all accessories included. Opened software, games, and digital "
            "downloads are not eligible for return. For defective or damaged "
            "items, customers must report the issue within 7 days of delivery "
            "with photo evidence. Approved refunds are processed within 5-10 "
            "business days to the original payment method. Return shipping is "
            "free for defective items; for change-of-mind returns, the customer "
            "pays return shipping. Items returned without prior authorization "
            "may be subject to a 15% restocking fee."
        ),
        "category": "refund",
        "tags": ["return", "refund", "30-day", "restocking"],
    },
    {
        "title": "Electronics Warranty Policy",
        "content": (
            "All electronics sold through our store include a standard 1-year "
            "manufacturer warranty covering defects in materials and workmanship. "
            "Warranty claims must be submitted within 12 months of the purchase "
            "date with proof of purchase. Covered defects include: failure to "
            "power on, screen defects (dead pixels exceeding 5), battery failure "
            "below 80% capacity within 6 months, and non-functional ports. "
            "The warranty does NOT cover: accidental damage (drops, liquid spills), "
            "unauthorized modifications, normal wear and tear, or damage from "
            "using non-approved accessories. Warranty service may include repair, "
            "replacement with equivalent or newer model, or store credit at our "
            "discretion."
        ),
        "category": "refund",
        "tags": ["electronics", "warranty", "1-year", "repair"],
    },
    {
        "title": "Size & Color Exchange Policy",
        "content": (
            "Clothing and footwear items can be exchanged for a different size "
            "or color within 14 days of delivery. Items must be unworn, unwashed, "
            "and with all original tags attached. The first exchange per order is "
            "free — we cover shipping both ways. Subsequent exchanges incur a "
            "flat $5.99 shipping fee. Exchanges are processed within 2-3 business "
            "days of receiving the returned item. If the requested size or color "
            "is out of stock, we will issue a full refund or store credit at the "
            "customer's choice. Final sale items, intimates, and swimwear are "
            "not eligible for exchange unless defective."
        ),
        "category": "exchange",
        "tags": ["clothing", "size", "color", "free-exchange"],
    },
    {
        "title": "Damaged or Wrong Item Policy",
        "content": (
            "If you receive a damaged, defective, or incorrect item, contact us "
            "within 48 hours of delivery. We require clear photos showing the "
            "damage or the wrong item received alongside the packaging. Upon "
            "verification, we will ship a replacement within 1 business day at "
            "no cost to you. Alternatively, you may choose a full refund "
            "including original shipping costs. For high-value items (over $200), "
            "we may require the damaged item to be returned before processing "
            "the replacement. A prepaid return label will be provided. Claims "
            "submitted after 48 hours may still be honored but are reviewed on "
            "a case-by-case basis."
        ),
        "category": "exchange",
        "tags": ["damaged", "wrong-item", "replacement", "48-hour"],
    },
    {
        "title": "High-Value Order Verification Policy",
        "content": (
            "Orders with a total value exceeding $500 are flagged as high-value "
            "and require additional verification before processing refunds or "
            "exchanges. For high-value refund requests, our policy requires: "
            "(1) verification that the item has been returned and inspected, "
            "(2) supervisor approval for refunds over $200, (3) mandatory "
            "signature confirmation on return shipments. High-value orders "
            "disputing shipping delays are escalated to a human agent for "
            "manual tracking investigation before any refund is issued. "
            "This policy exists to prevent fraud and ensure large transactions "
            "receive appropriate scrutiny."
        ),
        "category": "general",
        "tags": ["high-value", "verification", "approval", "fraud-prevention"],
    },
    {
        "title": "International Shipping Policy",
        "content": (
            "International orders (outside the contiguous United States) are "
            "shipped via standard international post with an estimated delivery "
            "time of 10-21 business days. Express international shipping (5-10 "
            "business days) is available for an additional fee at checkout. "
            "International customers are responsible for any customs duties, "
            "taxes, or import fees imposed by their country. Shipping delays "
            "caused by customs processing are not eligible for shipping refunds. "
            "Lost international packages are eligible for a refund or reshipment "
            "after 30 business days from the ship date. Tracking may be limited "
            "for certain destination countries."
        ),
        "category": "shipping",
        "tags": ["international", "customs", "delivery-time"],
    },
    {
        "title": "Customer Loyalty Exception Policy",
        "content": (
            "Customers with a lifetime purchase history exceeding $1,000 or "
            "more than 5 completed orders are considered loyalty members. For "
            "loyalty members, the following exceptions apply: (1) extended "
            "return window of 45 days instead of 30, (2) free return shipping "
            "on all returns regardless of reason, (3) one courtesy refund per "
            "year for items up to $50 without requiring a return, and (4) "
            "priority processing for all support tickets. These benefits are "
            "automatically applied based on the customer's order history in "
            "our system. Loyalty status is reviewed monthly."
        ),
        "category": "general",
        "tags": ["loyalty", "vip", "exception", "priority"],
    },
]


async def seed(embed: bool = False) -> None:
    """Insert sample policy documents into the database.

    Args:
        embed: If True, generate embeddings via OpenAI API.
               Requires a valid OPENAI_API_KEY.
    """
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        print(f"Seeding {len(SAMPLE_POLICIES)} policy documents...")

        if embed:
            try:
                provider = LLMFactory.create(
                    "openai", model=settings.llm.embedding_model
                )
                print(f"  Embedding provider: openai / {settings.llm.embedding_model}")
            except Exception as e:
                print(f"  Embedding unavailable: {e}")
                print("  Continuing without embeddings...")
                embed = False

        created_count = 0
        embed_count = 0

        for i, data in enumerate(SAMPLE_POLICIES):
            policy = await create_policy(
                db,
                title=data["title"],
                content=data["content"],
                category=data["category"],
                tags=data["tags"],
            )
            created_count += 1

            if embed and provider:
                try:
                    result = await provider.embed(data["content"])
                    if result.success and result.embedding:
                        await set_embedding(db, policy, result.embedding)
                        embed_count += 1
                        print(f"  [{i+1}/{len(SAMPLE_POLICIES)}] {data['title']} "
                              f"— embedded ({result.latency_ms}ms)")
                    else:
                        print(f"  [{i+1}/{len(SAMPLE_POLICIES)}] {data['title']} "
                              f"— embed FAILED: {result.error}")
                except Exception as e:
                    print(f"  [{i+1}/{len(SAMPLE_POLICIES)}] {data['title']} "
                          f"— embed ERROR: {e}")
            else:
                print(f"  [{i+1}/{len(SAMPLE_POLICIES)}] {data['title']} — stored (no embed)")

        await db.commit()
        print(f"\nDone. Created {created_count} policies ({embed_count} with embeddings).")


if __name__ == "__main__":
    import sys

    do_embed = "--embed" in sys.argv
    asyncio.run(seed(embed=do_embed))
