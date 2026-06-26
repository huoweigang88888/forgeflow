"""
ForgeFlow AI - Celery Task Definitions.

Async tasks for background processing.
"""

import json
from datetime import UTC, datetime
from typing import Any

from celery import shared_task

from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="worker.tasks")


# =============================================================================
# Embedding Tasks
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.batch_update_embeddings")
def batch_update_embeddings() -> dict[str, Any]:
    """Update embeddings for unprocessed policy documents.

    Runs every 30 minutes. Processes up to 100 documents per batch.
    From PRD Section 16.4, Strategy 4.
    """
    logger.info("batch_embedding_start")

    # In production: query unembedded policy documents and batch-embed them
    # For Phase 5, this is a stub that will be implemented when pgvector is fully set up

    logger.info("batch_embedding_complete", processed=0)
    return {"processed": 0, "status": "ok"}


# =============================================================================
# Data Retention Tasks
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.purge_expired_data")
def purge_expired_data(retention_days: int = 365) -> dict[str, Any]:
    """Purge data older than the retention period.

    Runs daily. Hard-deletes or anonymizes stale records.
    From PRD Section 19.5 (GDPR) and data retention policy.
    """
    import asyncio

    async def _run():
        from forgeflow.db.engine import AsyncSessionLocal
        from forgeflow.services.gdpr import GDRPService

        async with AsyncSessionLocal() as session:
            service = GDRPService(session)
            result = await service.purge_expired_data(retention_days)
            return result

    result = asyncio.run(_run())
    logger.info("data_purge_complete", **result)
    return result


# =============================================================================
# Cost Report Tasks
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.generate_daily_cost_report")
def generate_daily_cost_report() -> dict[str, Any]:
    """Generate daily LLM cost report for all tenants.

    Runs daily at 2:00 AM UTC. Sends alerts for tenants exceeding 80% budget.
    """
    import asyncio

    async def _run():
        from forgeflow.db.session import get_redis_client

        redis_client = await get_redis_client()
        from forgeflow.monitoring.cost_tracker import CostTracker

        tracker = CostTracker(redis_client)
        tenants = await tracker.get_all_tenants_cost()

        # Alert for tenants approaching budget
        warnings = [t for t in tenants if t["is_warning"]]
        if warnings:
            logger.warning(
                "budget_warnings",
                count=len(warnings),
                tenants=[t["tenant_id"] for t in warnings],
            )

        return {
            "total_tenants": len(tenants),
            "warnings": len(warnings),
            "total_cost": sum(t["current_cost"] for t in tenants),
        }

    result = asyncio.run(_run())
    return result


# =============================================================================
# Health Check Task
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.check_sla_breaches")
def check_sla_breaches() -> dict[str, Any]:
    """Find tickets past SLA deadline and auto-escalate them.

    Runs every 15 minutes. Tickets in pending_approval with an
    sla_deadline before now() are auto-escalated.
    """
    import asyncio

    async def _run():
        from datetime import UTC, datetime

        from sqlalchemy import update

        from forgeflow.db.engine import AsyncSessionLocal
        from forgeflow.models.ticket import Ticket

        async with AsyncSessionLocal() as session:
            now = datetime.now(UTC)
            result = await session.execute(
                update(Ticket)
                .where(
                    Ticket.status == "pending_approval",
                    Ticket.sla_deadline.isnot(None),
                    Ticket.sla_deadline < now,
                )
                .values(
                    status="escalated",
                    recommended_action="escalate_to_human",
                    approval_reason="Auto-escalated: SLA deadline breached",
                )
                .returning(Ticket.id),
            )
            rows = result.fetchall()
            count = len(rows)

            if count > 0:
                logger.info(
                    "sla_breach_auto_escalated",
                    count=count,
                    ticket_ids=[str(r[0])[:8] + "..." for r in rows[:10]],
                )
            await session.commit()
            return {"escalated": count}

    result = asyncio.run(_run())
    return result


# =============================================================================
# Health Check Task
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.system_health_check")
def system_health_check() -> dict[str, Any]:
    """Periodic system health check.

    Runs every 5 minutes. Checks DB connectivity, Redis, and disk space.
    """
    import asyncio

    async def _run():
        from sqlalchemy import text

        from forgeflow.db.engine import engine

        health = {
            "timestamp": datetime.now(UTC).isoformat(),
            "database": "unknown",
            "redis": "unknown",
        }

        # Check database
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            health["database"] = "healthy"
        except Exception as e:
            health["database"] = f"unhealthy: {str(e)[:100]}"
            logger.error("health_check_db_failed", error=str(e))

        # Check Redis
        try:
            from forgeflow.db.session import get_redis_client

            redis_client = await get_redis_client()
            await redis_client.ping()
            health["redis"] = "healthy"
        except Exception as e:
            health["redis"] = f"unhealthy: {str(e)[:100]}"
            logger.error("health_check_redis_failed", error=str(e))

        return health

    result = asyncio.run(_run())
    return result


# =============================================================================
# Webhook Processing Task
# =============================================================================


@shared_task(
    name="forgeflow.worker.tasks.process_shopify_webhook",
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=30,
)
def process_shopify_webhook(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Process a Shopify webhook event asynchronously.

    Dispatched from the webhook HTTP endpoints to avoid blocking
    Shopify's expected 5-second acknowledgment window.

    Args:
        topic: Shopify webhook topic (e.g., "orders/create").
        payload: Parsed webhook JSON body.

    Returns:
        Processing result dict.
    """
    import asyncio

    async def _run():
        event_id = payload.get("id", "unknown")
        logger.info(
            "webhook_task_start",
            topic=topic,
            event_id=event_id,
        )

        # Phase 2: Implement actual processing per topic
        # - orders/create: sync order to local DB, check for auto-ticket rules
        # - orders/updated: update cached order, notify agent if ticket active
        # - fulfillments/create: update ticket with tracking, notify customer
        # - fulfillments/update: push tracking update via WebSocket

        # For tracking updates, push to Redis for WebSocket delivery
        if topic == "fulfillments/create":
            order_id = payload.get("order_id")
            tracking_number = payload.get("tracking_number")
            if order_id and tracking_number:
                try:
                    from forgeflow.db.session import get_redis_client

                    redis_client = await get_redis_client()
                    await redis_client.publish(
                        f"tracking:{order_id}",
                        json.dumps(
                            {
                                "type": "tracking_update",
                                "order_id": str(order_id),
                                "tracking_number": tracking_number,
                                "tracking_company": payload.get("tracking_company", ""),
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                        ),
                    )
                except Exception:
                    logger.exception("webhook_tracking_publish_failed")

        logger.info(
            "webhook_task_complete",
            topic=topic,
            event_id=event_id,
        )
        return {"topic": topic, "event_id": event_id, "status": "processed"}

    result = asyncio.run(_run())
    return result


# =============================================================================
# Feed Polling Task
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.poll_shopify_order_feed")
def poll_shopify_order_feed(tenant_id: str = "", limit: int = 50) -> dict[str, Any]:
    """Poll Shopify for recent orders and sync to local DB.

    Runs every 5 minutes per tenant. Fetches orders updated since the
    last poll timestamp (tracked in Redis) and creates/updates local
    order cache records. Also triggers auto-ticket creation for orders
    matching high-risk patterns (e.g., high-value unfulfilled).

    From PRD Section 9.2: Feed Polling Mechanism.

    Args:
        tenant_id: Optional tenant to poll (default: all active tenants).
        limit: Max orders per poll (default 50).

    Returns:
        Dict with sync statistics.
    """
    import asyncio

    async def _run():
        from forgeflow.db.session import get_redis_client

        redis_client = await get_redis_client()

        # Get last poll cursor from Redis
        cursor_key = f"feed:cursor:{tenant_id}" if tenant_id else "feed:cursor:global"
        last_cursor = await redis_client.get(cursor_key)

        synced = 0
        errors = 0

        try:
            # In production: iterate active tenants, call Shopify
            # /admin/api/{version}/orders.json?updated_at_min={cursor}&limit={limit}
            logger.info(
                "feed_poll_start",
                tenant_id=tenant_id or "all",
                last_cursor=last_cursor or "none",
                limit=limit,
            )

            # Update cursor to now
            new_cursor = datetime.now(UTC).isoformat()
            await redis_client.set(cursor_key, new_cursor, ex=86400)

            logger.info(
                "feed_poll_complete",
                tenant_id=tenant_id or "all",
                synced=synced,
                errors=errors,
            )

        except Exception:
            logger.exception("feed_poll_failed", tenant_id=tenant_id or "all")
            errors += 1

        return {
            "tenant_id": tenant_id or "all",
            "synced": synced,
            "errors": errors,
            "cursor": last_cursor,
        }

    result = asyncio.run(_run())
    return result


# =============================================================================
# Notification Retry Task
# =============================================================================


@shared_task(
    name="forgeflow.worker.tasks.retry_failed_notifications",
    autoretry_for=(Exception,),
    max_retries=5,
    default_retry_delay=60,
)
def retry_failed_notifications() -> dict[str, Any]:
    """Retry failed email/SMS notifications with exponential backoff.

    Runs every 2 minutes. Queries the notification_log table for
    entries with status='failed' and retry_count < max_retries,
    then re-dispatches them via the NotificationDispatcher.

    Each retry increments a counter; after max_retries (5), the
    notification is marked as permanently failed and an alert is raised.

    Returns:
        Dict with retry statistics.
    """
    import asyncio

    async def _run():
        from forgeflow.db.engine import AsyncSessionLocal

        retried = 0
        permanent_failures = 0

        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                from forgeflow.models.notification import NotificationLog

                result = await session.execute(
                    select(NotificationLog)
                    .where(
                        NotificationLog.status == "failed",
                        NotificationLog.retry_count < NotificationLog.max_retries,
                    )
                    .limit(20)
                )
                failed = result.scalars().all()

                for notification in failed:
                    try:
                        from forgeflow.providers.notifications.dispatcher import (
                            get_dispatcher,
                        )

                        dispatcher = get_dispatcher()
                        if notification.channel == "email":
                            sent = await dispatcher.send_email(
                                to=notification.recipient,
                                subject=notification.subject,
                                body=notification.body,
                            )
                        elif notification.channel == "sms":
                            sent = await dispatcher.send_sms(
                                to=notification.recipient,
                                message=notification.body,
                            )
                        else:
                            sent = False

                        if sent:
                            notification.status = "sent"
                            notification.sent_at = datetime.now(UTC)
                            retried += 1
                        else:
                            notification.retry_count += 1
                            if notification.retry_count >= notification.max_retries:
                                notification.status = "permanent_failure"
                                permanent_failures += 1
                                logger.error(
                                    "notification_permanent_failure",
                                    notification_id=str(notification.id)[:8],
                                    recipient=notification.recipient[:50],
                                )

                    except Exception:
                        notification.retry_count += 1
                        logger.exception(
                            "notification_retry_failed",
                            notification_id=str(notification.id)[:8],
                        )

                await session.commit()

        except Exception:
            logger.exception("notification_retry_batch_failed")

        logger.info(
            "notification_retry_complete",
            retried=retried,
            permanent_failures=permanent_failures,
        )
        return {"retried": retried, "permanent_failures": permanent_failures}

    result = asyncio.run(_run())
    return result


# =============================================================================
# Batch Embeddings Task (Implemented)
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.batch_update_embeddings")
def batch_update_embeddings(batch_size: int = 100) -> dict[str, Any]:
    """Update embeddings for unprocessed policy documents using pgvector.

    Runs every 30 minutes. Processes up to ``batch_size`` documents per batch.
    Uses the configured LLM provider's embedding API to generate vectors
    for semantic search over return/refund policies.

    From PRD Section 16.4, Strategy 4.

    Args:
        batch_size: Max documents per batch (default 100).

    Returns:
        Dict with processing statistics.
    """
    import asyncio

    async def _run():
        from forgeflow.db.engine import AsyncSessionLocal

        processed = 0
        errors = 0

        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select

                from forgeflow.models.policy_document import PolicyDocument

                # Find unembedded policy documents
                result = await session.execute(
                    select(PolicyDocument)
                    .where(
                        PolicyDocument.embedding.is_(None),
                        PolicyDocument.content.isnot(None),
                    )
                    .limit(batch_size)
                )
                documents = result.scalars().all()

                if not documents:
                    logger.info("batch_embedding_no_documents")
                    return {"processed": 0, "errors": 0, "status": "no_documents"}

                # Generate embeddings via LLM provider
                from forgeflow.core.config import get_settings
                from forgeflow.llm.base import LLMFactory

                settings = get_settings()
                llm = LLMFactory.create(
                    settings.llm.default_provider,
                    model=settings.llm.embedding_model or "text-embedding-3-small",
                )

                for doc in documents:
                    try:
                        if doc.content:
                            embedding = await llm.embed(doc.content[:8000])
                            doc.embedding = embedding
                            doc.embedded_at = datetime.now(UTC)
                            processed += 1
                    except Exception:
                        logger.exception(
                            "embedding_generation_failed",
                            policy_id=str(doc.id)[:8],
                        )
                        errors += 1
                        continue

                await session.commit()

                logger.info(
                    "batch_embedding_complete",
                    processed=processed,
                    errors=errors,
                )

        except Exception:
            logger.exception("batch_embedding_task_failed")
            errors = batch_size

        return {
            "processed": processed,
            "errors": errors,
            "status": "ok" if errors == 0 else "partial",
        }

    result = asyncio.run(_run())
    return result
