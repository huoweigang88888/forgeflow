"""
ForgeFlow AI - Audit Logging.

Implements PRD Section 19.3: Audit Logs.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AuditEvent:
    """A single audit log event."""

    tenant_id: str
    actor_id: str
    actor_role: str
    action: str  # "ticket.approve", "refund.execute", "gdpr.forget"
    resource_type: str  # "ticket", "order", "policy", "customer"
    resource_id: str
    details: dict = field(default_factory=dict)
    ip_address: str = "unknown"
    user_agent: str = "unknown"
    created_at: datetime = field(default_factory=datetime.utcnow)


class AuditLogger:
    """Writes audit events to the database.

    Every security-sensitive action should be audited:
    - Ticket approvals/rejections
    - Refund executions
    - Settings changes
    - GDPR requests
    - User role changes

    Usage:
        audit = AuditLogger(db_session)
        await audit.log(AuditEvent(
            tenant_id="mystore.myshopify.com",
            actor_id="user_123",
            actor_role="manager",
            action="ticket.approve",
            resource_type="ticket",
            resource_id="tkt_abc",
            details={"amount": 45.60},
        ))
    """

    def __init__(self, db_session):
        self.db = db_session

    async def log(self, event: AuditEvent) -> None:
        """Write an audit event to the database."""
        from sqlalchemy import text

        await self.db.execute(
            text("""
                INSERT INTO audit_logs
                    (tenant_id, actor_id, actor_role, action,
                     resource_type, resource_id, details,
                     ip_address, user_agent, created_at)
                VALUES
                    (:tenant_id, :actor_id, :actor_role, :action,
                     :resource_type, :resource_id, :details,
                     :ip_address, :user_agent, :created_at)
            """),
            {
                "tenant_id": event.tenant_id,
                "actor_id": event.actor_id,
                "actor_role": event.actor_role,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "details": event.details,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "created_at": event.created_at,
            },
        )
        await self.db.commit()
