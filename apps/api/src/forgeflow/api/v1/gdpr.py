"""
ForgeFlow AI - GDPR API Endpoints.

GDPR Art.15 (Data Export) and Art.17 (Right to Erasure).
Also implements the three Shopify-mandatory GDPR webhook receivers
required for App Store listing.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from forgeflow.db.session import DBSession, OptionalDBSession
from forgeflow.monitoring.logger import get_logger
from forgeflow.security import DataMasker
from forgeflow.security.audit import AuditEvent, AuditLogger
from forgeflow.services import GDRPService
from forgeflow.services.shopify_webhooks import verify_shopify_webhook_hmac

router = APIRouter(prefix="/gdpr", tags=["gdpr"])

logger = get_logger(component="api.gdpr")

# Dependency shorthand for Shopify GDPR webhooks (HMAC-authenticated)
_GdprWebhookPayload = Depends(verify_shopify_webhook_hmac)


@router.get("/export")
async def export_customer_data(
    customer_email: str,
    tenant_id: str,
    db: DBSession,
) -> dict[str, Any]:
    """GDPR Art.15: Export all personal data for a customer."""
    service = GDRPService(db)

    try:
        result = await service.export_customer_data(customer_email, tenant_id)
    except Exception as e:
        logger.error(
            "gdpr_export_failed", email=DataMasker.mask_email(customer_email), error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Export failed: {e}") from e

    return {
        "code": 0,
        "message": "Data export completed",
        "data": result.data,
    }


@router.delete("/forget")
async def forget_customer(
    customer_email: str,
    tenant_id: str,
    request: Request,
    db: DBSession,
) -> dict[str, Any]:
    """GDPR Art.17: Right to erasure (be forgotten)."""
    service = GDRPService(db)

    try:
        result = await service.anonymize_customer_data(customer_email, tenant_id)
    except Exception as e:
        logger.error(
            "gdpr_forget_failed", email=DataMasker.mask_email(customer_email), error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Anonymization failed: {e}") from e

    # Audit log
    audit = AuditLogger(db)
    await audit.log(
        AuditEvent(
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
        )
    )

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
) -> dict[str, Any]:
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


# =============================================================================
# Shopify GDPR Webhook Receivers (mandatory for App Store listing)
# =============================================================================
# These endpoints receive GDPR requests from Shopify and verify the
# HMAC signature before processing.  They are public (no JWT required)
# because Shopify uses HMAC authentication for webhooks.


@router.post("/customers/data_request")
async def gdpr_customers_data_request(
    payload: dict[str, Any] = _GdprWebhookPayload,
    db: OptionalDBSession = None,
) -> dict[str, Any]:
    """GDPR: Shopify requests all stored data for a customer.

    Shopify sends this webhook when a customer submits a data access
    request.  The app must return all personal data stored for the
    customer (orders, tickets, agent logs).

    In production, the exported data should be sent to Shopify's GDPR
    submission endpoint within the required time window.  Phase 1 logs
    the data availability.
    """
    shop_domain = payload.get("shop_domain", "")
    customer_data = payload.get("customer", {}) if isinstance(payload.get("customer"), dict) else {}
    customer_email = customer_data.get("email", "")

    logger.info(
        "gdpr_webhook_customers_data_request",
        shop=shop_domain,
        email=DataMasker.mask_email(customer_email) if customer_email else "unknown",
    )

    if customer_email and shop_domain:
        assert db is not None  # OptionalDBSession guaranteed by FastAPI DI
        service = GDRPService(db)
        try:
            result = await service.export_customer_data(customer_email, shop_domain)
            logger.info(
                "gdpr_webhook_data_exported",
                shop=shop_domain,
                customers_found=len(result.data.get("customers", [])) if result.data else 0,
            )
        except Exception as exc:
            logger.error(
                "gdpr_webhook_export_failed",
                shop=shop_domain,
                error=str(exc)[:300],
            )

    return {"code": 0, "message": "Data request received", "data": None}


@router.post("/customers/redact")
async def gdpr_customers_redact(
    payload: dict[str, Any] = _GdprWebhookPayload,
    db: OptionalDBSession = None,
) -> dict[str, Any]:
    """GDPR: Shopify requests deletion of customer personal data.

    Shopify sends this webhook when a customer requests deletion of
    their personal data.  The app must redact/anonymize all PII for
    that customer within the required time window.
    """
    shop_domain = payload.get("shop_domain", "")
    customer_data = payload.get("customer", {}) if isinstance(payload.get("customer"), dict) else {}
    customer_email = customer_data.get("email", "")

    logger.info(
        "gdpr_webhook_customers_redact",
        shop=shop_domain,
        email=DataMasker.mask_email(customer_email) if customer_email else "unknown",
    )

    if customer_email and shop_domain:
        assert db is not None  # OptionalDBSession guaranteed by FastAPI DI
        service = GDRPService(db)
        try:
            result = await service.anonymize_customer_data(customer_email, shop_domain)
            logger.info(
                "gdpr_webhook_customer_redacted",
                shop=shop_domain,
                tickets_anonymized=result.tickets_anonymized,
                orders_anonymized=result.orders_anonymized,
            )
        except Exception as exc:
            logger.error(
                "gdpr_webhook_redact_failed",
                shop=shop_domain,
                error=str(exc)[:300],
            )

    return {"code": 0, "message": "Redaction request received", "data": None}


@router.post("/shop/redact")
async def gdpr_shop_redact(
    payload: dict[str, Any] = _GdprWebhookPayload,
    db: OptionalDBSession = None,
) -> dict[str, Any]:
    """GDPR: Shopify requests deletion of all store data.

    Shopify sends this webhook 48 hours after a merchant uninstalls
    the app.  The app must delete ALL stored data for this shop.

    Phase 1: Soft-delete the session (mark as uninstalled) to
    immediately disable API access.
    Phase 2: Hard-delete all tenant data: tickets, orders, customers,
    agent logs, LLM calls, and the session row itself.
    """
    shop_domain = payload.get("shop_domain", "")

    logger.info("gdpr_webhook_shop_redact", shop=shop_domain)

    if shop_domain:
        assert db is not None  # OptionalDBSession guaranteed by FastAPI DI
        from forgeflow.crud.shopify_session import mark_uninstalled

        await mark_uninstalled(db, shop_domain)
        await db.commit()

        logger.info("gdpr_webhook_shop_redacted", shop=shop_domain)

    return {"code": 0, "message": "Shop redaction request received", "data": None}
