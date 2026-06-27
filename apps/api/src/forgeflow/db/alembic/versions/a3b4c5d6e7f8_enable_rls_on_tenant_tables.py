"""enable_rls_on_tenant_tables

Revision ID: a3b4c5d6e7f8
Revises: 1a2b3c4d5e6f
Create Date: 2026-06-27 10:50:00.000000

Enable Row-Level Security (RLS) on all tenant-scoped tables for defense-in-depth
multi-tenant data isolation.

This migration applies the same RLS policies defined in db/init/03-enable-rls.sql
so that RLS is active for both fresh Docker starts AND incremental migrations.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables with direct tenant columns (shopify_domain or tenant_id)
_TENANT_TABLES: dict[str, str] = {
    "tickets": "shopify_domain",
    "customers": "shopify_domain",
    "orders": "shopify_domain",
    "policy_documents": "shopify_domain",
    "audit_logs": "tenant_id",
    "notifications": "tenant_id",
    "shopify_sessions": "shop_domain",
}

# Tables without direct tenant columns (join through parent tables)
_JOIN_TABLES: dict[str, str] = {
    "agent_logs": "ticket_id IN (SELECT id FROM tickets WHERE shopify_domain = current_setting('app.current_tenant', true))",
    "llm_calls": "log_id IN (SELECT al.id FROM agent_logs al JOIN tickets t ON al.ticket_id = t.id WHERE t.shopify_domain = current_setting('app.current_tenant', true))",
}


def upgrade() -> None:
    """Enable RLS and create tenant isolation policies on all tenant-scoped tables."""

    # 1. Direct tenant-scoped tables
    for table_name, tenant_column in _TENANT_TABLES.items():
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")

        # Read/Update/Delete policy
        op.execute(f"""
            CREATE POLICY {table_name}_tenant_isolation ON {table_name}
                FOR ALL
                USING ({tenant_column} = current_setting('app.current_tenant', true))
                WITH CHECK ({tenant_column} = current_setting('app.current_tenant', true))
        """)

        # Insert policy (allows bypass when tenant context is not set — for migrations/seed)
        op.execute(f"""
            CREATE POLICY {table_name}_tenant_insert ON {table_name}
                FOR INSERT
                WITH CHECK (
                    {tenant_column} = current_setting('app.current_tenant', true)
                    OR current_setting('app.current_tenant', true) IS NULL
                )
        """)

    # 2. Join-based tables (tenant inherited from parent)
    for table_name, join_condition in _JOIN_TABLES.items():
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")

        op.execute(f"""
            CREATE POLICY {table_name}_tenant_isolation ON {table_name}
                FOR ALL
                USING (
                    {join_condition}
                    OR current_setting('app.current_tenant', true) IS NULL
                )
        """)


def downgrade() -> None:
    """Remove RLS policies and disable RLS on all tables.

    This is safe — it just removes the defense-in-depth layer. Application-level
    tenant filtering via the tenant middleware continues to function.
    """

    all_tables = list(_TENANT_TABLES.keys()) + list(_JOIN_TABLES.keys())

    for table_name in all_tables:
        # Drop all policies on this table
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_insert ON {table_name}")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")
