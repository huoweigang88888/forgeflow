"""
ForgeFlow AI - Real Shopify End-to-End Tests.

These tests run against a REAL Shopify test store and validate the full
agent pipeline: intent detection → order lookup → decision → execution.

Prerequisites:
    Set these environment variables BEFORE running:
        SHOPIFY_E2E_ENABLED=true
        SHOPIFY_E2E_SHOP_DOMAIN=mystore.myshopify.com
        SHOPIFY_E2E_ACCESS_TOKEN=shpat_xxxxxxxxxxxx
        SHOPIFY_E2E_ORDER_ID=1234567890          (a real order ID in the store)
        SHOPIFY_E2E_CUSTOMER_EMAIL=test@test.com  (customer email for the order)

The tests are skipped if SHOPIFY_E2E_ENABLED is not set to "true".
This allows CI to skip them while developers run them locally.

Related:
    - tests/agent/test_end_to_end.py — mock-based golden tests (always run)
    - This file — real Shopify integration tests (opt-in)
"""

import os

import pytest

from forgeflow.agent.service import AgentService
from forgeflow.providers.registry import ProviderRegistry
from forgeflow.providers.shopify.client import ShopifyProvider

# ── E2E Gate ──
_E2E_ENABLED = os.getenv("SHOPIFY_E2E_ENABLED", "").lower() in ("true", "1", "yes")
_E2E_REASON = (
    "Shopify E2E tests require SHOPIFY_E2E_ENABLED=true and valid credentials. "
    "Set SHOPIFY_E2E_SHOP_DOMAIN, SHOPIFY_E2E_ACCESS_TOKEN, and "
    "SHOPIFY_E2E_ORDER_ID to run against a real store."
)

pytestmark = pytest.mark.skipif(not _E2E_ENABLED, reason=_E2E_REASON)


# ── Fixtures ──


@pytest.fixture(scope="module")
def shopify_credentials():
    """Load Shopify E2E credentials from environment."""
    shop_domain = os.getenv("SHOPIFY_E2E_SHOP_DOMAIN", "")
    access_token = os.getenv("SHOPIFY_E2E_ACCESS_TOKEN", "")
    order_id = os.getenv("SHOPIFY_E2E_ORDER_ID", "")
    customer_email = os.getenv("SHOPIFY_E2E_CUSTOMER_EMAIL", "")

    if not all([shop_domain, access_token, order_id]):
        pytest.skip(
            "Missing one or more required env vars: "
            "SHOPIFY_E2E_SHOP_DOMAIN, SHOPIFY_E2E_ACCESS_TOKEN, SHOPIFY_E2E_ORDER_ID"
        )

    return {
        "shop_domain": shop_domain,
        "access_token": access_token,
        "order_id": order_id,
        "customer_email": customer_email,
    }


@pytest.fixture(scope="module")
def shopify_provider(shopify_credentials):
    """Create a real ShopifyProvider connected to the test store."""
    provider = ShopifyProvider(
        shop_domain=shopify_credentials["shop_domain"],
        access_token=shopify_credentials["access_token"],
    )
    # Ensure the provider is registered for the agent service
    if not ProviderRegistry.is_registered("shopify"):
        ProviderRegistry.register("shopify", ShopifyProvider)
    return provider


# =============================================================================
# E2E: Order Lookup
# =============================================================================


@pytest.mark.asyncio
async def test_e2e_shopify_get_order(shopify_provider, shopify_credentials):
    """Fetch a real order from Shopify and verify the normalized DTO."""
    order = await shopify_provider.get_order(shopify_credentials["order_id"])

    assert order is not None
    assert order.order_id, "Order ID should not be empty"
    assert order.total_price > 0, "Order should have a positive total price"
    assert order.currency, "Order should have a currency"
    assert order.customer_email, "Order should have a customer email"


@pytest.mark.asyncio
async def test_e2e_shopify_get_customer_history(shopify_provider, shopify_credentials):
    """Fetch customer history from a real Shopify store."""
    history = await shopify_provider.get_customer_history(
        customer_email=shopify_credentials["customer_email"],
    )

    assert isinstance(history, dict)
    assert "total_orders" in history
    assert "total_spent" in history
    assert "refund_count" in history
    assert history["total_orders"] >= 0, "Total orders should be non-negative"


@pytest.mark.asyncio
async def test_e2e_shopify_fulfillment_status(shopify_provider, shopify_credentials):
    """Check fulfillment status for a real order."""
    status = await shopify_provider.get_fulfillment_status(shopify_credentials["order_id"])

    assert status in ("fulfilled", "unfulfilled", "partial", "unknown")


# =============================================================================
# E2E: Agent Pipeline with Real Shopify Provider
# =============================================================================


@pytest.mark.asyncio
async def test_e2e_agent_pipeline_real_order(shopify_credentials):
    """Run the full agent pipeline against a real Shopify order.

    This test validates the complete flow:
    1. Intent detection (LLM-powered)
    2. Order lookup (Shopify REST API)
    3. Logistics check
    4. Policy check
    5. Decision
    6. (Execution is SKIPPED — we don't want to create real refunds)
    """
    service = AgentService(redis_client=None)

    result = await service.run(
        ticket_id=f"e2e_{shopify_credentials['order_id']}",
        platform="shopify",
        shopify_domain=shopify_credentials["shop_domain"],
        customer_email=shopify_credentials["customer_email"],
        issue_text="My order hasn't arrived yet. Where is it?",
        order_id=shopify_credentials["order_id"],
        access_token=shopify_credentials["access_token"],
    )

    # Verify the pipeline completed
    assert result.get("status") in (
        "resolved",
        "pending_approval",
        "escalated",
        "failed",
    ), f"Unexpected status: {result.get('status')}"

    # Verify each node ran
    assert result.get("intent") is not None, "Intent detection did not run"
    assert result.get("order_info") is not None, "Order lookup did not run"
    assert result.get("recommended_action") is not None, "Decision did not run"


@pytest.mark.asyncio
async def test_e2e_agent_pipeline_refund_scenario(shopify_credentials):
    """Run agent pipeline with a refund request against real Shopify."""
    service = AgentService(redis_client=None)

    result = await service.run(
        ticket_id=f"e2e_refund_{shopify_credentials['order_id']}",
        platform="shopify",
        shopify_domain=shopify_credentials["shop_domain"],
        customer_email=shopify_credentials["customer_email"],
        issue_text="I received a damaged item. I want a full refund immediately!",
        order_id=shopify_credentials["order_id"],
        access_token=shopify_credentials["access_token"],
    )

    assert result.get("status") in ("resolved", "pending_approval", "escalated")
    action = result.get("recommended_action")
    assert action in (
        "auto_refund",
        "auto_exchange",
        "investigate",
        "escalate_to_human",
        "send_notification",
    ), f"Unexpected action: {action}"


@pytest.mark.asyncio
async def test_e2e_agent_pipeline_exchange_scenario(shopify_credentials):
    """Run agent pipeline with an exchange request against real Shopify."""
    service = AgentService(redis_client=None)

    result = await service.run(
        ticket_id=f"e2e_exchange_{shopify_credentials['order_id']}",
        platform="shopify",
        shopify_domain=shopify_credentials["shop_domain"],
        customer_email=shopify_credentials["customer_email"],
        issue_text="I ordered the wrong size. Can I exchange for a different size?",
        order_id=shopify_credentials["order_id"],
        access_token=shopify_credentials["access_token"],
    )

    assert result.get("status") in ("resolved", "pending_approval", "escalated")
    assert result.get("recommended_action") is not None
