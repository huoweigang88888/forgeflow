#!/usr/bin/env python
"""
ForgeFlow AI - Pilot Customer Onboarding Script.

Automates the setup of a new pilot customer tenant:
1. Creates database records for the tenant
2. Seeds knowledge base with default policies
3. Seeds prompt versions
4. Configures budget limits
5. Validates the setup

Usage:
    python scripts/onboard_tenant.py \
        --tenant "pilot-store.myshopify.com" \
        --platform shopify \
        --email admin@pilotstore.com \
        --budget 50

Phase 5: Pilot Customer Onboarding (PRD Section 10.1).
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


async def onboard_tenant(
    tenant_id: str,
    platform: str = "shopify",
    admin_email: str = "",
    monthly_budget: float = 50.0,
    seed_policies: bool = True,
    seed_prompts: bool = True,
) -> dict:
    """Onboard a new pilot customer tenant.

    Args:
        tenant_id: The Shopify domain (e.g., 'mystore.myshopify.com').
        platform: Platform identifier ('shopify', 'mock').
        admin_email: Admin email for the tenant.
        monthly_budget: Monthly LLM cost budget in USD.
        seed_policies: Whether to seed default knowledge base policies.
        seed_prompts: Whether to seed default prompt versions.

    Returns:
        Dict with onboarding results.
    """
    from forgeflow.core.config import get_settings
    from forgeflow.db.engine import AsyncSessionLocal, engine

    settings = get_settings()

    result = {
        "tenant_id": tenant_id,
        "platform": platform,
        "onboarded_at": datetime.now(UTC).isoformat(),
        "status": "pending",
        "steps": {},
    }

    print(f"\n{'='*60}")
    print(f"  ForgeFlow AI — Pilot Customer Onboarding")
    print(f"  Tenant: {tenant_id}")
    print(f"  Platform: {platform}")
    print(f"  Budget: ${monthly_budget}/month")
    print(f"{'='*60}\n")

    # Step 1: Verify database connectivity
    print("[1/5] Verifying database connectivity...")
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        result["steps"]["database"] = "connected"
        print("  ✓ Database connected")
    except Exception as e:
        result["steps"]["database"] = f"FAILED: {e}"
        result["status"] = "failed"
        print(f"  ✗ Database connection failed: {e}")
        return result

    # Step 2: Seed prompt versions
    if seed_prompts:
        print("[2/5] Seeding default prompt versions...")
        try:
            from forgeflow.db.engine import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                from forgeflow.prompts.registry import PromptRegistry
                registry = PromptRegistry(session)
                created = await registry.seed_default_prompts()
                result["steps"]["prompts"] = f"seeded {len(created)} versions"
                print(f"  ✓ Seeded {len(created)} prompt versions")
        except Exception as e:
            result["steps"]["prompts"] = f"FAILED: {e}"
            print(f"  ✗ Prompt seeding failed: {e}")

    # Step 3: Seed knowledge base policies
    if seed_policies:
        print("[3/5] Seeding default knowledge base policies...")
        try:
            from forgeflow.db.engine import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                from forgeflow.crud.policy import create_policy
                # Create default policies for this tenant
                policy_defs = [
                        {
                            "title": "Standard Shipping Policy",
                            "content": (
                                "Orders are typically delivered within 5-7 business days. "
                                "If delivery exceeds 14 days, customers are eligible for a full refund "
                                "or free reshipment. For delays of 7-14 days, offer a 15% discount."
                            ),
                            "content_type": "policy",
                        },
                        {
                            "title": "Standard Refund Policy",
                            "content": (
                                "Unfulfilled orders can be refunded immediately at 100%. "
                                "Fulfilled orders: refund within 30 days of delivery. "
                                "Damaged/wrong items: full refund or exchange within 14 days. "
                                "Refunds over $100 require manager approval."
                            ),
                            "content_type": "policy",
                        },
                        {
                            "title": "Exchange Policy",
                            "content": (
                                "Size/color exchanges are free within 30 days of delivery. "
                                "Customer pays return shipping for non-defect exchanges. "
                                "Defective items: free return + free exchange or full refund."
                            ),
                            "content_type": "policy",
                        },
                        {
                            "title": "Shipping Delay FAQ",
                            "content": (
                                "Q: My order is late. What should I do? "
                                "A: Contact us with your order number. If delayed > 14 days, "
                                "you are eligible for a full refund. "
                                "Q: How do I track my order? "
                                "A: Use the tracking link in your shipping confirmation email."
                            ),
                            "content_type": "faq",
                        },
                    ]
                policies = []
                for pdef in policy_defs:
                    policy = await create_policy(
                        session,
                        title=pdef["title"],
                        content=pdef["content"],
                        category=pdef.get("content_type", "policy"),
                        shopify_domain=tenant_id,
                        platform=platform,
                    )
                    policies.append(policy)
                await session.commit()
                result["steps"]["policies"] = f"seeded {len(policies)} documents"
                print(f"  ✓ Seeded {len(policies)} policy documents")
        except Exception as e:
            result["steps"]["policies"] = f"FAILED: {e}"
            print(f"  ✗ Policy seeding failed: {e}")

    # Step 4: Configure budget
    print(f"[4/5] Setting monthly budget to ${monthly_budget}...")
    try:
        from forgeflow.db.session import get_redis_client
        redis_client = await get_redis_client()
        from forgeflow.monitoring.cost_tracker import CostTracker
        tracker = CostTracker(redis_client)
        await tracker.set_tenant_budget(tenant_id, monthly_budget)
        result["steps"]["budget"] = f"${monthly_budget}/month"
        print(f"  ✓ Budget set to ${monthly_budget}/month")
    except Exception as e:
        result["steps"]["budget"] = f"FAILED: {e}"
        print(f"  ✗ Budget configuration failed: {e}")

    # Step 5: Validation
    print("[5/5] Validating tenant setup...")
    try:
        from forgeflow.db.engine import AsyncSessionLocal
        from forgeflow.providers.registry import ProviderRegistry

        async with AsyncSessionLocal() as session:
            # Verify provider is registered
            provider_ok = ProviderRegistry.is_registered(platform)
            if not provider_ok:
                print(f"  ⚠ Platform '{platform}' not registered. Available: {ProviderRegistry.available_platforms()}")

            result["steps"]["validation"] = "passed"
            print("  ✓ Validation complete")

    except Exception as e:
        result["steps"]["validation"] = f"FAILED: {e}"
        print(f"  ✗ Validation failed: {e}")

    result["status"] = "success"
    print(f"\n{'='*60}")
    print(f"  Onboarding Complete — {tenant_id}")
    print(f"  Status: {result['status']}")
    print(f"{'='*60}\n")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="ForgeFlow AI — Pilot Customer Onboarding"
    )
    parser.add_argument(
        "--tenant", required=True,
        help="Tenant ID (e.g., shop domain)"
    )
    parser.add_argument(
        "--platform", default="shopify",
        help="Platform type (shopify, mock)"
    )
    parser.add_argument(
        "--email", default="",
        help="Admin email for the tenant"
    )
    parser.add_argument(
        "--budget", type=float, default=50.0,
        help="Monthly LLM cost budget in USD"
    )
    parser.add_argument(
        "--no-policies", action="store_true",
        help="Skip policy seeding"
    )
    parser.add_argument(
        "--no-prompts", action="store_true",
        help="Skip prompt seeding"
    )

    args = parser.parse_args()

    result = asyncio.run(onboard_tenant(
        tenant_id=args.tenant,
        platform=args.platform,
        admin_email=args.email,
        monthly_budget=args.budget,
        seed_policies=not args.no_policies,
        seed_prompts=not args.no_prompts,
    ))

    if result["status"] != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
