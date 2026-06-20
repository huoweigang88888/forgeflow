"""
ForgeFlow AI - GDPR API Endpoints.

GDPR Art.15 (Data Export) and Art.17 (Right to Erasure).
Requires admin role.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from forgeflow.db.session import DBSession
from forgeflow.monitoring.logger import get_logger
from forgeflow.security import DataMasker
from forgeflow.security.audit import AuditEvent, AuditLogger
from forgeflow.services import GDRPService

router = APIRouter(prefix="/gdpr", tags=["gdpr"])

logger = get_logger(component="api.gdpr")


@router.get("/export")
async def export_customer_data(
    customer_email: str,
    tenant_id: str,
    db: DBSession,
):
    """GDPR Art.15: Export all personal data for a customer."""
    service = GDRPService(db)

    try:
        result = await service.export_customer_data(customer_email, tenant_id)
    except Exception as e:
        logger.error("gdpr_export_failed", email=DataMasker.mask_email(customer_email), error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {e}") from e

    return JSONResponse(
        content={
            "code": 0,
            "message": "Data export completed",
            "data": result.data,
        },
        headers={
            "Content-Disposition": f"attachment; filename=gdpr_export_{customer_email}.json"
        },
    )


@router.delete("/forget")
async def forget_customer(
    customer_email: str,
    tenant_id: str,
    request: Request,
    db: DBSession,
):
    """GDPR Art.17: Right to erasure (be forgotten)."""
    service = GDRPService(db)

    try:
        result = await service.anonymize_customer_data(customer_email, tenant_id)
    except Exception as e:
        logger.error("gdpr_forget_failed", email=DataMasker.mask_email(customer_email), error=str(e))
        raise HTTPException(status_code=500, detail=f"Anonymization failed: {e}") from e

    # Audit log
    audit = AuditLogger(db)
    await audit.log(AuditEvent(
        tenant_id=tenant_id,
        actor_id="admin",
        actor_role="admin",
        action="gdpr.forget",
        resource_type="customer",
        resource_id=customer_email,
        details={
            "email": DataMasker.mask_email(customer_email),
            "tickets_anonymized": result.tickets_anonymized,
            "orders_anonymized": result.orders_anonymized,
        },
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
    ))

    return {
        "code": 0,
        "message": f"All personal data for {DataMasker.mask_email(customer_email)} has been anonymized.",
        "data": {
            "tickets_anonymized": result.tickets_anonymized,
            "orders_anonymized": result.orders_anonymized,
            "customer_deleted": result.customer_deleted,
        },
    }


@router.post("/purge")
async def trigger_data_purge(
    db: DBSession,
    retention_days: int = 365,
):
    """Manually trigger data retention purge (admin only)."""
    if retention_days < 90:
        raise HTTPException(
            status_code=400,
            detail="Retention period must be at least 90 days",
        )

    service = GDRPService(db)
    result = await service.purge_expired_data(retention_days)

    return {
        "code": 0,
        "message": f"Data retention purge completed ({retention_days} days)",
        "data": result,
    }
