"""
ForgeFlow AI - Execution Node.

Sixth and final main node in the agent pipeline. Executes the
recommended action:

- auto_refund: Process refund via OrderProvider
- auto_exchange: Initiate exchange via OrderProvider
- send_notification: Send status update to customer
- escalate_to_human / investigate: Ends the pipeline (handled in graph)

Notifications are dispatched via the NotificationDispatcher (SendGrid/Twilio).
Customer messages are rendered via the template system with optional LLM
translation for non-English languages.

Step-level events are published to Redis Pub/Sub for real-time WebSocket
updates to the frontend.
"""

import json
from datetime import UTC, datetime
from typing import Any

from forgeflow.agent.state import AgentState
from forgeflow.core.exceptions import ProviderError
from forgeflow.messaging.templates import get_subject, render_template, translate_message
from forgeflow.monitoring.logger import get_logger
from forgeflow.providers.dto import RefundResult
from forgeflow.providers.notifications.dispatcher import get_dispatcher
from forgeflow.providers.registry import ProviderRegistry

logger = get_logger(component="agent.execute")


async def _publish_step_event(
    state: AgentState,
    event_type: str,
    step: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Publish a step-level event to Redis Pub/Sub for WebSocket delivery.

    This enables the frontend to show real-time progress during agent
    execution (e.g., "Processing refund...", "Sending notification...").

    Args:
        state: Current agent state (must contain ``redis_client`` for actual publish).
        event_type: Event type (``step_update``, ``execution_result``, etc.).
        step: Current step name.
        data: Optional additional event data.
    """
    redis_client = state.get("redis_client")
    if redis_client is None:
        return

    ticket_id = state.get("ticket_id", "unknown")
    try:
        message = {
            "type": event_type,
            "ticket_id": ticket_id,
            "step": step,
            "status": "processing",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data or {},
        }
        await redis_client.publish(
            f"ticket:{ticket_id}",
            json.dumps(message),
        )
    except Exception:
        # Never let publish failures affect the main flow
        pass


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


async def _dispatch_customer_notification(
    state: AgentState,
    template_name: str,
    body: str,
) -> bool:
    """Send the rendered customer response via email (and SMS if phone available).

    Uses the NotificationDispatcher (SendGrid) for email delivery.
    Falls back gracefully if no notification provider is configured.

    Args:
        state: Agent state containing customer info.
        template_name: Template key for subject lookup.
        body: Rendered message body.

    Returns:
        True if at least one notification was sent.
    """
    customer_email = state.get("customer_email", "")
    language = state.get("issue_language", "en")
    subject = get_subject(template_name, language=language)

    if not customer_email:
        logger.info("notification_skipped_no_email")
        return False

    dispatcher = get_dispatcher()
    sent = await dispatcher.send_email(
        to=customer_email,
        subject=subject,
        body=body,
    )

    # Optionally send SMS if phone is available
    customer_phone = state.get("customer_phone", "")
    shopify_domain = state.get("shopify_domain", "")
    if customer_phone and sent:
        sms_body = (
            f"[{shopify_domain or 'ForgeFlow'}] {subject}: " f"{body.split(chr(10))[0][:120]}"
        )
        await dispatcher.send_sms(to=customer_phone, message=sms_body)

    return sent


async def _send_customer_message(
    state: AgentState,
    template_name: str,
    **template_kwargs: object,
) -> str:
    """Render a customer message with LLM translation if needed, then send it.

    For non-English languages, the template body is translated via LLM
    before sending. The original English template is used as the base,
    and the LLM produces a localized version.

    Args:
        state: Agent state.
        template_name: Template key.
        **template_kwargs: Template variables.

    Returns:
        The rendered (and possibly translated) message body.
    """
    language = state.get("issue_language", "en")

    # First render the English template as the canonical message
    body = render_template(template_name, language="en", **template_kwargs)

    # If non-English, translate via LLM
    if language and language != "en":
        try:
            body = await translate_message(body, target_language=language)
        except Exception:
            logger.warning(
                "translation_failed_falling_back",
                language=language,
                template=template_name,
            )
            # Fall back to static template if LLM translation fails
            body = render_template(template_name, language=language, **template_kwargs)
            if not body:
                body = render_template("fallback", language=language, **template_kwargs)

    # Dispatch via email/SMS
    await _dispatch_customer_notification(state, template_name, body)

    return body


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
    language = state.get("issue_language", "en")

    order_id = order_info.get("order_id") or state.get("order_id", "")
    order_number = order_info.get("order_number", "N/A")
    customer_name = state.get("customer_name", "Valued Customer")
    _customer_email = state.get("customer_email", "")
    shopify_domain = state.get("shopify_domain", "")

    # =========================================================================
    # auto_refund: Process refund via platform provider
    # =========================================================================
    if action == "auto_refund":
        refund_amount = state.get("refund_amount", 0.0) or 0.0
        refund_reason = state.get("refund_reason", "After-sales request") or "After-sales request"

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

        # Publish step event — processing refund
        await _publish_step_event(
            state,
            "step_update",
            "execute",
            {"action": "auto_refund", "message": "Processing refund..."},
        )

        try:
            kwargs = _build_provider_kwargs(state)
            provider = ProviderRegistry.get(platform, **kwargs)
            refund: RefundResult = await provider.create_refund(
                order_id=order_id,
                amount=refund_amount,
                reason=refund_reason,
                notify_customer=False,  # We'll send our own notification
            )

            if refund.success:
                # Generate and send customer notification
                customer_response = await _send_customer_message(
                    state,
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
                    "completed_at": _now_utc(),
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
        # Publish step event — sending notification
        await _publish_step_event(
            state,
            "step_update",
            "execute",
            {"action": "send_notification", "message": "Sending customer notification..."},
        )
        customer_response = await _send_customer_message(
            state,
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
            "completed_at": _now_utc(),
        }

    # =========================================================================
    # auto_exchange: Initiate exchange/return with platform provider
    # =========================================================================
    if action == "auto_exchange":
        exchange_reason = (
            state.get("refund_reason", state.get("issue_text", "Exchange requested"))
            or "Exchange requested"
        )

        if not order_id:
            logger.error(
                "execute_no_order_id_exchange",
                ticket_id=ticket_id,
            )
            return {
                "execution_status": "failed",
                "execution_result": {"error": "No order ID available for exchange"},
                "current_step": "execute_done",
            }

        # Publish step event — processing exchange
        await _publish_step_event(
            state,
            "step_update",
            "execute",
            {"action": "auto_exchange", "message": "Initiating exchange..."},
        )

        try:
            kwargs = _build_provider_kwargs(state)
            provider = ProviderRegistry.get(platform, **kwargs)
            exchange = await provider.create_exchange(
                order_id=order_id,
                reason=exchange_reason,
                exchange_items=None,  # Default to all items
                notify_customer=False,  # We'll send our own notification
            )

            if exchange.success:
                customer_response = await _send_customer_message(
                    state,
                    "exchange_initiated",
                    customer_name=customer_name,
                    order_number=order_number,
                    explanation=exchange_reason,
                    store_name=shopify_domain,
                )

                logger.info(
                    "execute_exchange_success",
                    ticket_id=ticket_id,
                    exchange_id=exchange.exchange_id,
                    replacement_order_id=exchange.replacement_order_id,
                )

                return {
                    "execution_status": "success",
                    "execution_result": {
                        "exchange_id": exchange.exchange_id,
                        "return_label_url": exchange.return_label_url,
                        "replacement_order_id": exchange.replacement_order_id,
                        "action": "auto_exchange",
                    },
                    "customer_response": customer_response,
                    "current_step": "execute_done",
                    "completed_at": _now_utc(),
                }
            else:
                logger.error(
                    "execute_exchange_failed",
                    ticket_id=ticket_id,
                    error=exchange.error,
                )
                return {
                    "execution_status": "failed",
                    "execution_result": {"error": exchange.error},
                    "current_step": "execute_done",
                }

        except (ValueError, ProviderError) as e:
            logger.error(
                "execute_exchange_error",
                ticket_id=ticket_id,
                error=str(e)[:200],
            )
            raise

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


def _now_utc() -> datetime:
    """Return current UTC datetime."""
    from datetime import datetime

    return datetime.now(UTC)
