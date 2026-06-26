"""
ForgeFlow AI - Order Lookup Node.

Second node in the agent pipeline. Retrieves order details from the
platform provider (Shopify, WooCommerce, etc.) based on the order ID.

Uses the Provider abstraction so it works with any platform without
code changes.
"""

from typing import Any

from forgeflow.agent.state import AgentState
from forgeflow.core.exceptions import ProviderError
from forgeflow.monitoring.logger import get_logger
from forgeflow.providers.registry import ProviderRegistry

logger = get_logger(component="agent.order_lookup")


def _build_provider_kwargs(state: AgentState) -> dict[str, Any]:
    """Build the kwargs dict for ProviderRegistry.get() from agent state.

    Includes shop_domain and access_token when available so the
    ShopifyProvider can make authenticated API calls.
    """
    kwargs: dict[str, Any] = {}
    # mock_overrides only applies to MockPlatformProvider
    if state.get("platform", "mock") == "mock":
        kwargs["mock_overrides"] = state.get("mock_overrides", {})
    shop_domain = state.get("shopify_domain", "")
    access_token = state.get("access_token", "")
    if shop_domain:
        kwargs["shop_domain"] = shop_domain
    if access_token:
        kwargs["access_token"] = access_token
    return kwargs


async def lookup_order_node(state: AgentState) -> dict[str, Any]:
    """Look up order details from the platform provider.

    Resolves the correct PlatformProvider from the state's platform,
    retrieves the order, and returns normalized order info.

    Args:
        state: AgentState with order_id and platform populated.

    Returns:
        Partial state update with order_info and customer details.

    Raises:
        ProviderError: If the order cannot be found or API fails.
    """
    ticket_id = state.get("ticket_id", "unknown")
    platform = state.get("platform", "mock")

    # Resolve the order ID from intent extraction or direct input
    order_id = state.get("extracted_order_id") or state.get("order_id")
    if not order_id:
        logger.warning(
            "order_lookup_no_order_id",
            ticket_id=ticket_id,
            platform=platform,
        )
        return {
            "order_info": None,
            "current_step": "order_lookup_done",
        }

    try:
        kwargs = _build_provider_kwargs(state)
        provider = ProviderRegistry.get(platform, **kwargs)
        order_info = await provider.get_order(order_id)

        # Fetch customer history for downstream decision-making
        customer_email = order_info.customer_email or state.get("customer_email", "")
        customer_history = await provider.get_customer_history(customer_email, order_id=order_id)

        logger.info(
            "order_lookup_success",
            ticket_id=ticket_id,
            order_id=order_id,
            order_number=order_info.order_number,
            total_price=order_info.total_price,
        )

        return {
            "order_info": {
                "order_id": order_info.order_id,
                "order_number": order_info.order_number,
                "customer_email": order_info.customer_email,
                "customer_name": order_info.customer_name,
                "total_price": order_info.total_price,
                "currency": order_info.currency,
                "fulfillment_status": order_info.fulfillment_status,
                "financial_status": order_info.financial_status,
                "tracking_number": order_info.tracking_number,
                "tracking_carrier": order_info.tracking_carrier,
                "shipping_address": order_info.shipping_address,
                "line_items": order_info.line_items,
                "created_at": order_info.created_at.isoformat() if order_info.created_at else None,
            },
            "customer_history": customer_history,
            "tracking_number": order_info.tracking_number,
            "tracking_carrier": order_info.tracking_carrier,
            "customer_name": order_info.customer_name,
            "current_step": "order_lookup_done",
        }

    except ValueError as e:
        # Provider not registered
        logger.error(
            "order_lookup_provider_not_found",
            ticket_id=ticket_id,
            platform=platform,
            error=str(e),
        )
        raise ProviderError(
            provider=platform,
            message=f"Platform '{platform}' not registered",
            retryable=False,
        ) from e

    except ProviderError:
        # Re-raise provider errors for retry/fallback handling
        raise
