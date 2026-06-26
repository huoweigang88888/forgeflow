"""enable_row_level_security

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-25 16:00:00.000000

Enable Row-Level Security (RLS) on all tenant-scoped tables.

RLS ensures that even if application code has a bug that omits the
WHERE clause on shopify_domain/tenant_id, PostgreSQL will block the
query at the database level.  This is defense-in-depth for multi-tenant
data isolation.

How it works:
1. The application sets ``app.current_tenant`` at the start of each
   database session (via a SQLAlchemy event listener).
2. Each table gets a SELECT/INSERT/UPDATE/DELETE policy that compares
   the row's tenant column against ``current_setting('app.current_tenant')``.
3. If ``app.current_tenant`` is not set, the query returns 0 rows
   (fail-closed).

Tables covered:
- tickets          (shopify_domain)
- customers        (shopify_domain)
- orders           (shopify_domain)
- policy_documents (shopify_domain)
- audit_logs       (tenant_id)
- notification_logs(tenant_id)
- shopify_sessions (shop_domain)
- agent_logs       (joined via tickets.shopify_domain)
- llm_calls        (joined via tickets.shopify_domain)
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── Tables with a direct tenant column ──
# (table_name, tenant_column)
_DIRECT_TENANT_TABLES: list[tuple[str, str]] = [
    ("tickets", "shopify_domain"),
    ("customers", "shopify_domain"),
    ("orders", "shopify_domain"),
    ("policy_documents", "shopify_domain"),
    ("audit_logs", "tenant_id"),
    ("notification_logs", "tenant_id"),
    ("shopify_sessions", "shop_domain"),
]

# ── Tables that join to tickets for tenant context ──
_JOINED_TENANT_TABLES: list[tuple[str, str]] = [
    ("agent_logs", "ticket_id"),
    ("llm_calls", "ticket_id"),
]

# ── Tables that are globally readable (no tenant isolation) ──
# prompt_versions — shared prompt library
_GLOBAL_TABLES = ("prompt_versions",)


def _enable_rls_for(table: str, tenant_col: str) -> None:
    """Enable RLS and create per-operation policies for one table."""
    # Enable RLS on the table
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # Force RLS on table owner as well (defense in depth)
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    tenant_check = f"{tenant_col} = current_setting('app.current_tenant', true)"

    # SELECT policy
    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_select" ON {table}
            FOR SELECT
            USING ({tenant_check})
    """)

    # INSERT policy — ensure new rows have the correct tenant
    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_insert" ON {table}
            FOR INSERT
            WITH CHECK ({tenant_check})
    """)

    # UPDATE policy
    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_update" ON {table}
            FOR UPDATE
            USING ({tenant_check})
            WITH CHECK ({tenant_check})
    """)

    # DELETE policy
    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_delete" ON {table}
            FOR DELETE
            USING ({tenant_check})
    """)


def _enable_rls_for_joined(table: str, fk_col: str) -> None:
    """Enable RLS on a table that joins to tickets for tenant context."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    join_check = (
        f"EXISTS (SELECT 1 FROM tickets WHERE tickets.id = {table}.{fk_col} "
        f"AND tickets.shopify_domain = current_setting('app.current_tenant', true))"
    )

    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_select" ON {table}
            FOR SELECT
            USING ({join_check})
    """)

    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_insert" ON {table}
            FOR INSERT
            WITH CHECK ({join_check})
    """)

    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_update" ON {table}
            FOR UPDATE
            USING ({join_check})
            WITH CHECK ({join_check})
    """)

    op.execute(f"""
        CREATE POLICY "{table}_tenant_isolation_delete" ON {table}
            FOR DELETE
            USING ({join_check})
    """)


def upgrade() -> None:
    """Enable RLS on all tenant-scoped tables."""
    for table, tenant_col in _DIRECT_TENANT_TABLES:
        _enable_rls_for(table, tenant_col)

    for table, fk_col in _JOINED_TENANT_TABLES:
        _enable_rls_for_joined(table, fk_col)


def downgrade() -> None:
    """Disable RLS on all tables (undo the upgrade)."""
    all_tables = [t for t, _ in _DIRECT_TENANT_TABLES] + [t for t, _ in _JOINED_TENANT_TABLES]

    for table in all_tables:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        # Drop all policies on this table
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_isolation_select" ON {table}')
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_isolation_insert" ON {table}')
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_isolation_update" ON {table}')
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_isolation_delete" ON {table}')
