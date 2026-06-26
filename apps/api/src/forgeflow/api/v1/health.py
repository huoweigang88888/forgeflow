"""
ForgeFlow API - Health Check Endpoint.

Provides liveness/readiness probes for orchestration and monitoring.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check — returns OK if the API process is running.

    This is a liveness probe. For readiness (DB + Redis connectivity),
    see /health/ready.
    """
    return {
        "status": "ok",
        "version": "0.1.0",
        "service": "forgeflow-api",
    }


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe — verifies database and Redis connectivity.

    Returns 200 if all dependencies are available, 503 otherwise.
    """
    from fastapi import Response
    from sqlalchemy import text

    from forgeflow.db.engine import engine

    checks = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check Redis
    try:
        import redis.asyncio as redis

        from forgeflow.core.config import get_settings

        r = redis.from_url(get_settings().redis_url)
        await r.ping()
        await r.close()
        checks["redis"] = True
    except Exception:
        pass

    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503

    return Response(
        content=str({"status": "ready" if all_ready else "not_ready", "checks": checks}),
        status_code=status_code,
        media_type="application/json",
    )
