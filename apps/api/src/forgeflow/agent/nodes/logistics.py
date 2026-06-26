"""
ForgeFlow AI - Logistics Check Node.

Third node in the agent pipeline. Checks shipment tracking status
for orders that have been fulfilled.

Uses LogisticsProvider from the platform abstraction layer.
"""

from typing import Any

from forgeflow.agent.state import AgentState
from forgeflow.core.exceptions import ProviderError
from forgeflow.monitoring.logger import get_logger
from forgeflow.providers.registry import ProviderRegistry

logger = get_logger(component="agent.logistics")


def _build_provider_kwargs(state: AgentState) -> dict[str, Any]:
    """Build the kwargs dict for ProviderRegistry.get() from agent state."""
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


async def check_logistics_node(state: AgentState) -> dict[str, Any]:
    """Check shipment tracking status for the order.

    Only queries logistics if the order has a tracking number.
    If the order is unfulfilled, skips with empty logistics status.

    Args:
        state: AgentState with order_info, tracking_number populated.

    Returns:
        Partial state update with logistics_status.
    """
    ticket_id = state.get("ticket_id", "unknown")
    platform = state.get("platform", "mock")
    order_info = state.get("order_info") or {}
    tracking_number = state.get("tracking_number")

    # No tracking number = nothing to check
    if not tracking_number:
        logger.info(
            "logistics_skipped",
            ticket_id=ticket_id,
            reason="no_tracking_number",
        )
        return {
            "logistics_status": {
                "status": "unknown",
                "status_detail": "No tracking number available",
                "tracking_number": None,
                "carrier": None,
                "days_in_transit": 0,
            },
            "current_step": "logistics_done",
        }

    # Unfulfilled = no shipment yet
    fulfillment_status = order_info.get("fulfillment_status", "")
    if fulfillment_status == "unfulfilled":
        logger.info(
            "logistics_skipped",
            ticket_id=ticket_id,
            reason=f"order_{fulfillment_status}",
        )
        return {
            "logistics_status": {
                "status": "unknown",
                "status_detail": f"Order is {fulfillment_status}",
                "tracking_number": tracking_number,
                "carrier": state.get("tracking_carrier"),
                "days_in_transit": 0,
            },
            "current_step": "logistics_done",
        }

    try:
        kwargs = _build_provider_kwargs(state)
        provider = ProviderRegistry.get(platform, **kwargs)
        carrier = state.get("tracking_carrier")
        tracking = await provider.track_shipment(
            tracking_number=tracking_number,
            carrier=carrier,
        )

        logger.info(
            "logistics_checked",
            ticket_id=ticket_id,
            tracking_status=tracking.status,
            days_in_transit=tracking.days_in_transit,
        )

        return {
            "logistics_status": {
                "tracking_number": tracking.tracking_number,
                "carrier": tracking.carrier,
                "status": tracking.status,
                "status_detail": tracking.status_detail,
                "estimated_delivery": tracking.estimated_delivery.isoformat()
                if tracking.estimated_delivery
                else None,
                "days_in_transit": tracking.days_in_transit,
                "last_update": tracking.last_update.isoformat() if tracking.last_update else None,
                "events": tracking.events,
            },
            "current_step": "logistics_done",
        }

    except (ValueError, ProviderError) as e:
        # Provider not found or API error
        logger.warning(
            "logistics_failed",
            ticket_id=ticket_id,
            error=str(e)[:200],
        )
        raise
