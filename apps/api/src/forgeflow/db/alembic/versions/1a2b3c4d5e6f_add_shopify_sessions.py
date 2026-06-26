"""add shopify_sessions

Revision ID: 1a2b3c4d5e6f
Revises: 0c4527b6cc41
Create Date: 2026-06-20 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: str | None = "0c4527b6cc41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create shopify_sessions table for OAuth token storage."""
    op.create_table(
        "shopify_sessions",
        # UUIDMixin
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Identity
        sa.Column(
            "shop_domain",
            sa.String(length=255),
            nullable=False,
        ),
        # Encrypted token
        sa.Column(
            "access_token_encrypted",
            sa.Text(),
            nullable=False,
        ),
        # OAuth scopes
        sa.Column(
            "scopes",
            sa.String(length=500),
            nullable=False,
            server_default=sa.text("''"),
        ),
        # Status
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # Timestamps
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "uninstalled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unique index on shop_domain (one session per store)
    op.create_index(
        "ix_shopify_sessions_shop_domain",
        "shopify_sessions",
        ["shop_domain"],
        unique=True,
    )
    # Index for active session queries
    op.create_index(
        "ix_shopify_sessions_is_active",
        "shopify_sessions",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the shopify_sessions table."""
    op.drop_index("ix_shopify_sessions_is_active", table_name="shopify_sessions")
    op.drop_index("ix_shopify_sessions_shop_domain", table_name="shopify_sessions")
    op.drop_table("shopify_sessions")
