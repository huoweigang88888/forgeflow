"""
ForgeFlow AI - Execution Node.

Sixth and final main node in the agent pipeline. Executes the
recommended action:

- auto_refund: Process refund via OrderProvider
- auto_exchange: Initiate exchange (Phase 2+)
- send_notification: Send status update to customer
- escalate_to_human / investigate: Ends the pipeline (handled in graph)

From PRD Section 7: Agent Nodes.
"""

from datetime import UTC
from typing import Any

from forgeflow.agent.state import AgentState
from forgeflow.core.exceptions import ProviderError
from forgeflow.messaging.templates import render_template
from forgeflow.monitoring.logger import get_logger
from forgeflow.providers.dto import RefundResult
from forgeflow.providers.registry import ProviderRegistry

logger = get_logger(component="agent.execute")


async def execute_action_node(state: AgentState) -> dict[str, Any]:
    """Execute the recommended action.

    Handles auto_refund, auto_exchange, and send_notification actions.
    For escalate_to_human and investigate, the pipeline ends before
    reaching this node (routed in the graph).

    Args:
        state: AgentState with decision fields populated.

    Returns:
        Partial state update with execution result.
    """
    ticket_id = state.get("ticket_id", "unknown")
    platform = state.get("platform", "mock")
    action = state.get("recommended_action", "escalate_to_human")
    order_info = state.get("order_info") or {}

    order_id = order_info.get("order_id") or state.get("order_id", "")
    order_number = order_info.get("order_number", "N/A")
    customer_name = state.get("customer_name", "Valued Customer")
    _customer_email = state.get("customer_email", "")
    shopify_domain = state.get("shopify_domain", "")

    # =========================================================================
    # auto_refund: Process refund via platform provider
    # =========================================================================
    if action == "auto_refund":
        refund_amount = state.get("refund_amount", 0.0)
        refund_reason = state.get("refund_reason", "After-sales request")

        if not order_id:
            logger.error(
                "execute_no_order_id",
                ticket_id=ticket_id,
            )
            return {
                "execution_status": "failed",
                "execution_result": {"error": "No order ID available"},
                "current_step": "execute_done",
            }

        try:
            provider = ProviderRegistry.get(platform)
            refund: RefundResult = await provider.create_refund(
                order_id=order_id,
                amount=refund_amount,
                reason=refund_reason,
                notify_customer=False,  # We'll send our own notification
            )

            if refund.success:
                # Generate customer notification
                customer_response = render_template(
                    "auto_refund_success",
                    customer_name=customer_name,
                    order_number=order_number,
                    refund_amount=refund_amount,
                    explanation=refund_reason,
                    store_name=shopify_domain,
                )

                logger.info(
                    "execute_refund_success",
                    ticket_id=ticket_id,
                    refund_id=refund.refund_id,
                    amount=refund_amount,
                )

                return {
                    "execution_status": "success",
                    "execution_result": {
                        "refund_id": refund.refund_id,
                        "amount": refund.amount,
                        "action": "auto_refund",
                    },
                    "customer_response": customer_response,
                    "current_step": "execute_done",
                    "completed_at": _now_iso(),
                }
            else:
                logger.error(
                    "execute_refund_failed",
                    ticket_id=ticket_id,
                    error=refund.error,
                )
                return {
                    "execution_status": "failed",
                    "execution_result": {"error": refund.error},
                    "current_step": "execute_done",
                }

        except (ValueError, ProviderError) as e:
            logger.error(
                "execute_refund_error",
                ticket_id=ticket_id,
                error=str(e)[:200],
            )
            raise

    # =========================================================================
    # send_notification: Just notify the customer
    # =========================================================================
    if action == "send_notification":
        customer_response = render_template(
            "shipping_update",
            customer_name=customer_name,
            order_number=order_number,
            status_message="Your order is being processed.",
            tracking_number=order_info.get("tracking_number", "N/A"),
            tracking_url="",
            estimated_delivery="Updating",
            store_name=shopify_domain,
        )
        return {
            "execution_status": "success",
            "execution_result": {
                "action": "send_notification",
                "sent": True,
            },
            "customer_response": customer_response,
            "current_step": "execute_done",
            "completed_at": _now_iso(),
        }

    # =========================================================================
    # auto_exchange: Phase 2+
    # =========================================================================
    if action == "auto_exchange":
        logger.info(
            "execute_exchange_placeholder",
            ticket_id=ticket_id,
        )
        customer_response = render_template(
            "pending_approval",
            customer_name=customer_name,
            order_number=order_number,
            ticket_id=ticket_id,
            store_name=shopify_domain,
        )
        return {
            "execution_status": "pending_manual",
            "execution_result": {
                "action": "auto_exchange",
                "note": "Exchange processing not yet implemented (Phase 2)",
            },
            "customer_response": customer_response,
            "current_step": "execute_done",
        }

    # Unknown action
    logger.warning(
        "execute_unknown_action",
        ticket_id=ticket_id,
        action=action,
    )
    return {
        "execution_status": "failed",
        "execution_result": {"error": f"Unknown action: {action}"},
        "current_step": "execute_done",
    }


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import datetime

    return datetime.now(UTC).isoformat()
