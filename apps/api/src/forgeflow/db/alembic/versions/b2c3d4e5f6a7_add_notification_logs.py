"""add_notification_logs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-25 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_logs",
        # Foreign key to tickets (nullable — notifications may exist without a ticket)
        sa.Column(
            "ticket_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        # Multi-tenant isolation
        sa.Column(
            "tenant_id",
            sa.String(length=255),
            nullable=True,
        ),
        # Recipient
        sa.Column(
            "recipient",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default="email",
        ),
        # Content
        sa.Column(
            "subject",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "body",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "template_name",
            sa.String(length=100),
            nullable=True,
        ),
        # Delivery tracking
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "max_retries",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "is_customer_facing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # Provider info
        sa.Column(
            "provider",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "provider_message_id",
            sa.String(length=255),
            nullable=True,
        ),
        # Timing
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_retry_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Error tracking
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        # UUID primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Indexes
    op.create_index(
        op.f("ix_notification_logs_status"), "notification_logs", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_notification_logs_tenant_id"), "notification_logs", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_notification_logs_ticket_id"), "notification_logs", ["ticket_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_logs_ticket_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_tenant_id"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_status"), table_name="notification_logs")
    op.drop_table("notification_logs")
