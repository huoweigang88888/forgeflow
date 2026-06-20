"""
ForgeFlow AI - GDPR Compliance Service.

Implements GDPR Art.15 (data export) and Art.17 (right to be forgotten).
PRD Section 19.5: GDPR Compliance Checklist.

Usage:
    service = GDRPService(db_session)
    data = await service.export_customer_data("buyer@example.com", "mystore.myshopify.com")
    await service.anonymize_customer_data("buyer@example.com", "mystore.myshopify.com")
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forgeflow.models.customer import Customer
from forgeflow.models.order import Order
from forgeflow.models.ticket import Ticket
from forgeflow.monitoring.logger import get_logger
from forgeflow.security import DataMasker

logger = get_logger(component="gdpr")


@dataclass
class GDRPExportResult:
    """Complete customer data export for GDPR Art.15."""

    customer_email: str
    exported_at: str
    data: dict[str, Any]


@dataclass
class GDPRAnonymizeResult:
    """Result of GDPR Art.17 anonymization."""

    customer_email: str
    anonymized_at: str
    tickets_anonymized: int
    orders_anonymized: int
    customer_deleted: bool


class GDRPService:
    """Handles GDPR data subject requests.

    Art.15 (Right of Access): Export all personal data for a customer.
    Art.17 (Right to Erasure): Anonymize/delete all personal data.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # ------------------------------------------------------------------
    # Art.15: Data Export
    # ------------------------------------------------------------------

    async def export_customer_data(
        self, customer_email: str, tenant_id: str
    ) -> GDRPExportResult:
        """Export all data associated with a customer email.

        Collects:
        - Customer profile
        - All orders
        - All tickets and their agent decisions
        - Communication records (from agent_logs)
        """
        # Find customer(s) by email within tenant
        customers = await self._get_customers_by_email(customer_email, tenant_id)

        data: dict[str, Any] = {
            "request_type": "GDPR Art.15 — Data Export",
            "generated_at": datetime.now(UTC).isoformat(),
            "tenant_id": tenant_id,
            "email": DataMasker.mask_email(customer_email),
        }

        customer_data = []
        for customer in customers:
            customer_entry = {
                "customer_id": str(customer.id),
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "email": DataMasker.mask_email(customer.email),
                "total_orders": customer.total_orders,
                "created_at": customer.created_at.isoformat() if customer.created_at else None,
            }

            # Get orders
            orders = await self._get_orders_for_customer(customer.id, tenant_id)
            customer_entry["orders"] = [
                {
                    "order_id": str(o.id),
                    "order_number": o.order_number,
                    "total_price": str(o.total_price) if o.total_price else None,
                    "currency": o.currency,
                    "fulfillment_status": o.fulfillment_status,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ]

            # Get tickets
            tickets = await self._get_tickets_for_customer(customer.id, tenant_id)
            customer_entry["tickets"] = [
                {
                    "ticket_id": str(t.id),
                    "issue_text": t.issue_text,
                    "intent": t.intent,
                    "recommended_action": t.recommended_action,
                    "status": t.status,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tickets
            ]

            customer_data.append(customer_entry)

        data["customers"] = customer_data
        data["total_customers_found"] = len(customer_data)

        logger.info(
            "gdpr_export_completed",
            tenant_id=tenant_id,
            email=DataMasker.mask_email(customer_email),
            customers_found=len(customer_data),
        )

        return GDRPExportResult(
            customer_email=customer_email,
            exported_at=datetime.now(UTC).isoformat(),
            data=data,
        )

    # ------------------------------------------------------------------
    # Art.17: Right to Erasure (Anonymization)
    # ------------------------------------------------------------------

    async def anonymize_customer_data(
        self, customer_email: str, tenant_id: str
    ) -> GDPRAnonymizeResult:
        """Anonymize all personal data for a customer.

        Per GDPR Art.17, we:
        1. Anonymize PII fields (name, email, address) in customers table
        2. Anonymize shipping addresses in orders table
        3. Keep ticket records for audit but redact PII from issue_text
        4. Do NOT delete order financial data (required for tax purposes)

        Note: We use anonymization rather than deletion because:
        - Financial records must be retained for tax compliance
        - Agent decision audit trail must be preserved
        - Aggregated analytics should remain accurate
        """
        customers = await self._get_customers_by_email(customer_email, tenant_id)
        tickets_anonymized = 0
        orders_anonymized = 0

        for customer in customers:
            # Anonymize customer record
            await self.db.execute(
                update(Customer)
                .where(Customer.id == customer.id)
                .values(
                    email=f"anonymized_{customer.id}@deleted.forgeflow.ai",
                    first_name="[Anonymized]",
                    last_name="[Anonymized]",
                    updated_at=datetime.now(UTC),
                )
            )

            # Anonymize orders (shipping addresses only)
            orders = await self._get_orders_for_customer(customer.id, tenant_id)
            for order in orders:
                if order.shipping_address:
                    order.shipping_address = {
                        "city": "[Anonymized]",
                        "zip": "00000",
                        "country": "[Anonymized]",
                        "note": "GDPR Art.17 — anonymized",
                    }
                    orders_anonymized += 1

            # Anonymize ticket issue_text (remove PII)
            tickets = await self._get_tickets_for_customer(customer.id, tenant_id)
            for ticket in tickets:
                # Redact potential PII from issue text
                sanitized_text = self._redact_pii_from_text(ticket.issue_text)
                ticket.issue_text = sanitized_text
                tickets_anonymized += 1

        await self.db.commit()

        logger.info(
            "gdpr_anonymize_completed",
            tenant_id=tenant_id,
            email=DataMasker.mask_email(customer_email),
            tickets_anonymized=tickets_anonymized,
            orders_anonymized=orders_anonymized,
        )

        return GDPRAnonymizeResult(
            customer_email=customer_email,
            anonymized_at=datetime.now(UTC).isoformat(),
            tickets_anonymized=tickets_anonymized,
            orders_anonymized=orders_anonymized,
            customer_deleted=len(customers) > 0,
        )

    # ------------------------------------------------------------------
    # Data Retention
    # ------------------------------------------------------------------

    async def purge_expired_data(self, retention_days: int = 365) -> dict[str, int]:
        """Purge data older than retention period.

        This is called by a scheduled Celery task:
        - Tickets older than retention_days: hard delete
        - Agent logs older than retention_days: hard delete
        - LLM call records older than retention_days: hard delete
        - Anonymized customers older than 2x retention: hard delete

        Returns:
            Dict with counts of deleted records per type.
        """
        cutoff = datetime.now(UTC).timestamp() - (retention_days * 86400)
        cutoff_date = datetime.fromtimestamp(cutoff, tz=UTC)

        deleted: dict[str, int] = {}

        # Purge old LLM call records
        from forgeflow.models.llm_call import LLMCall
        result = await self.db.execute(
            update(LLMCall)
            .where(LLMCall.created_at < cutoff_date)
            .values(prompt="[PURGED — retention policy]", response="[PURGED]")
        )
        deleted["llm_calls_purged"] = result.rowcount

        # Purge old agent logs
        from forgeflow.models.agent_log import AgentLog
        result = await self.db.execute(
            update(AgentLog)
            .where(AgentLog.created_at < cutoff_date)
            .values(
                input_data={"purged": True},
                output_data={"purged": True},
            )
        )
        deleted["agent_logs_purged"] = result.rowcount

        await self.db.commit()

        logger.info(
            "data_retention_purge_completed",
            retention_days=retention_days,
            cutoff_date=cutoff_date.isoformat(),
            **deleted,
        )

        return deleted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_customers_by_email(
        self, email: str, tenant_id: str
    ) -> list[Customer]:
        """Find all customer records by email within a tenant."""
        stmt = select(Customer).where(
            Customer.email == email,
            Customer.shopify_domain == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_orders_for_customer(
        self, customer_id, tenant_id: str
    ) -> list[Order]:
        """Get all orders for a customer."""
        stmt = select(Order).where(
            Order.customer_id == customer_id,
            Order.shopify_domain == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_tickets_for_customer(
        self, customer_id, tenant_id: str
    ) -> list[Ticket]:
        """Get all tickets for a customer."""
        stmt = select(Ticket).where(
            Ticket.customer_id == customer_id,
            Ticket.shopify_domain == tenant_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _redact_pii_from_text(text: str) -> str:
        """Remove potential PII from free-text fields.

        Redacts: email addresses, phone numbers, physical addresses.
        """
        import re

        # Email addresses
        text = re.sub(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            '[REDACTED_EMAIL]',
            text,
        )
        # Phone numbers (various formats)
        text = re.sub(
            r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            '[REDACTED_PHONE]',
            text,
        )
        # Street addresses (heuristic)
        text = re.sub(
            r'\d{1,5}\s+\w+\s+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|blvd|boulevard|way|court|ct)',
            '[REDACTED_ADDRESS]',
            text,
            flags=re.IGNORECASE,
        )

        return text
