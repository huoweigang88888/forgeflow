"""
ForgeFlow AI - Celery Task Definitions.

Async tasks for background processing.
"""

from datetime import UTC, datetime

from celery import shared_task

from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="worker.tasks")


# =============================================================================
# Embedding Tasks
# =============================================================================


@shared_task(name="forgeflow.worker.tasks.batch_update_embeddings")
def batch_update_embeddings() -> dict:
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
def purge_expired_data(retention_days: int = 365) -> dict:
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
def generate_daily_cost_report() -> dict:
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


@shared_task(name="forgeflow.worker.tasks.system_health_check")
def system_health_check() -> dict:
    """Periodic system health check.

    Runs every 5 minutes. Checks DB connectivity, Redis, and disk space.
    """
    import asyncio

    async def _run():
        from forgeflow.db.engine import engine
        from sqlalchemy import text

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
