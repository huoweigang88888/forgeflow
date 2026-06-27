"""enable_rls_on_tenant_tables

Revision ID: a3b4c5d6e7f8
Revises: c3d4e5f6a7b8
Create Date: 2026-06-27 10:50:00.000000

No-op migration — RLS was already enabled by c3d4e5f6a7b8 (enable_row_level_security).
This migration exists to maintain a linear revision chain so fresh installs using
db/init/03-enable-rls.sql are also covered.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op — RLS policies already applied by c3d4e5f6a7b8."""


def downgrade() -> None:
    """No-op — RLS policies managed by c3d4e5f6a7b8."""
