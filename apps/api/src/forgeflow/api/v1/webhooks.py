"""
ForgeFlow AI - Shopify Business Webhook Endpoints.

Receives real-time events from Shopify for order and fulfillment
lifecycle changes.  Each endpoint verifies the HMAC signature before
processing.

Endpoints:
    POST /api/v1/webhooks/shopify/orders/create
    POST /api/v1/webhooks/shopify/orders/updated
    POST /api/v1/webhooks/shopify/fulfillments/create
    POST /api/v1/webhooks/shopify/fulfillments/update

Phase 2: Asynchronously dispatch webhook events via Celery tasks for
order sync, status updates, and ticket triggering.
Shopify expects fast acknowledgment (200 within 5s), so all heavy
processing is deferred to background workers.
"""

from typing import Any

from fastapi import APIRouter, Depends

from forgeflow.monitoring.logger import get_logger
from forgeflow.services.shopify_webhooks import verify_shopify_webhook_hmac

logger = get_logger(component="api.webhooks")

router = APIRouter(prefix="/webhooks/shopify", tags=["webhooks"])

# Dependency shorthand — cleaner route decorators
_WebhookPayload = Depends(verify_shopify_webhook_hmac)


# =============================================================================
# POST /orders/create — New order placed
# =============================================================================


@router.post("/orders/create")
async def orders_create(payload: dict[str, Any] = _WebhookPayload) -> dict[str, Any]:
    """Handle ``orders/create`` webhook — new order placed.

    Shopify sends this when a customer places a new order.
    Dispatches async order sync + auto-ticket triggering via Celery.
    """
    logger.info(
        "shopify_webhook_orders_create",
        order_id=payload.get("id"),
        order_number=payload.get("order_number"),
        total_price=payload.get("total_price"),
    )
    _dispatch_webhook_task("orders/create", payload)
    return {"code": 0, "message": "Webhook received", "data": None}


# =============================================================================
# POST /orders/updated — Order status changed
# =============================================================================


@router.post("/orders/updated")
async def orders_updated(payload: dict[str, Any] = _WebhookPayload) -> dict[str, Any]:
    """Handle ``orders/updated`` webhook — order status changed.

    Shopify sends this when order status, fulfilment status, or other
    fields change. Dispatches async order cache update + agent notification
    if a ticket is in progress.
    """
    logger.info(
        "shopify_webhook_orders_updated",
        order_id=payload.get("id"),
        fulfillment_status=payload.get("fulfillment_status"),
        financial_status=payload.get("financial_status"),
    )
    _dispatch_webhook_task("orders/updated", payload)
    return {"code": 0, "message": "Webhook received", "data": None}


# =============================================================================
# POST /fulfillments/create — Item shipped
# =============================================================================


@router.post("/fulfillments/create")
async def fulfillments_create(payload: dict[str, Any] = _WebhookPayload) -> dict[str, Any]:
    """Handle ``fulfillments/create`` webhook — item shipped.

    Shopify sends this when a fulfillment is created (items are packed
    and shipped). Dispatches async ticket status update + customer
    notification with tracking info.
    """
    logger.info(
        "shopify_webhook_fulfillments_create",
        fulfillment_id=payload.get("id"),
        order_id=payload.get("order_id"),
        tracking_number=payload.get("tracking_number"),
        tracking_company=payload.get("tracking_company"),
    )
    _dispatch_webhook_task("fulfillments/create", payload)
    return {"code": 0, "message": "Webhook received", "data": None}


# =============================================================================
# POST /fulfillments/update — Tracking updated
# =============================================================================


@router.post("/fulfillments/update")
async def fulfillments_update(payload: dict[str, Any] = _WebhookPayload) -> dict[str, Any]:
    """Handle ``fulfillments/update`` webhook — tracking updated.

    Shopify sends this when fulfillment details change (e.g., tracking
    number added or updated). Dispatches async real-time WebSocket push
    to any connected client.
    """
    logger.info(
        "shopify_webhook_fulfillments_update",
        fulfillment_id=payload.get("id"),
        order_id=payload.get("order_id"),
        tracking_number=payload.get("tracking_number"),
        tracking_url=payload.get("tracking_url"),
    )
    _dispatch_webhook_task("fulfillments/update", payload)
    return {"code": 0, "message": "Webhook received", "data": None}


# =============================================================================
# Async dispatch helper
# =============================================================================


def _dispatch_webhook_task(topic: str, payload: dict[str, Any]) -> None:
    """Fire-and-forget dispatch of webhook processing to Celery.

    Uses Celery .delay() to enqueue the webhook for background processing.
    Shopify expects a 200 within 5 seconds; all heavy processing
    (DB writes, agent invocations, notifications) runs in the background.

    Args:
        topic: Shopify webhook topic (e.g., "orders/create").
        payload: Parsed webhook JSON body.
    """
    try:
        from forgeflow.worker.tasks import process_shopify_webhook

        process_shopify_webhook.delay(topic=topic, payload=payload)
    except Exception:
        logger.exception(
            "webhook_dispatch_failed",
            topic=topic,
            order_id=payload.get("id"),
        )
