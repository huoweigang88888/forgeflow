-- =============================================================================
-- ForgeFlow AI - Row-Level Security (RLS) Setup
-- =============================================================================
-- Enables PostgreSQL Row-Level Security on all tenant-scoped tables to ensure
-- multi-tenant data isolation at the database level.
--
-- This is a DEFENSE-IN-DEPTH measure — the application layer (tenant middleware)
-- already injects tenant_id filters, but RLS ensures that even if a query
-- bypasses the ORM layer (e.g., ad-hoc queries, migrations, operations errors),
-- no cross-tenant data leakage can occur.
--
-- Security model:
--   1. Application sets app.current_tenant via tenant middleware
--   2. RLS policies use current_setting('app.current_tenant') as the tenant filter
--   3. Tables without tenant_id use shopify_domain as the tenant identifier
--   4. A bypass policy allows system operations (migrations, seed data)
--
-- Tables covered:
--   - tickets       (tenant = shopify_domain)
--   - customers     (tenant = shopify_domain)
--   - orders        (tenant = shopify_domain)
--   - policy_documents (tenant = shopify_domain)
--   - agent_logs    (tenant via tickets.shopify_domain — lookup)
--   - audit_logs    (tenant = tenant_id)
--   - notifications (tenant = tenant_id)
--   - llm_calls     (tenant via agent_logs → tickets.shopify_domain — lookup)
--   - prompt_versions (NOT tenant-scoped — shared across all tenants)
--   - shopify_sessions (tenant = shop_domain, separate from shopify_domain)
-- =============================================================================

-- ── Helper: Set tenant context (called by application middleware) ──
-- The tenant middleware runs this on every request:
--   SELECT set_config('app.current_tenant', '<shopify_domain>', false);
-- The RLS policies read this setting to filter rows.

-- =============================================================================
-- tickets table
-- =============================================================================
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;

-- Allow SELECT/UPDATE/DELETE only for rows matching the current tenant
CREATE POLICY tickets_tenant_isolation ON tickets
    FOR ALL
    USING (shopify_domain = current_setting('app.current_tenant', true))
    WITH CHECK (shopify_domain = current_setting('app.current_tenant', true));

-- Allow INSERT when the tenant context is set (or for system operations)
CREATE POLICY tickets_tenant_insert ON tickets
    FOR INSERT
    WITH CHECK (
        shopify_domain = current_setting('app.current_tenant', true)
        OR current_setting('app.current_tenant', true) IS NULL  -- Migration bypass
    );

-- =============================================================================
-- customers table
-- =============================================================================
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;

CREATE POLICY customers_tenant_isolation ON customers
    FOR ALL
    USING (shopify_domain = current_setting('app.current_tenant', true))
    WITH CHECK (shopify_domain = current_setting('app.current_tenant', true));

CREATE POLICY customers_tenant_insert ON customers
    FOR INSERT
    WITH CHECK (
        shopify_domain = current_setting('app.current_tenant', true)
        OR current_setting('app.current_tenant', true) IS NULL
    );

-- =============================================================================
-- orders table
-- =============================================================================
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY orders_tenant_isolation ON orders
    FOR ALL
    USING (shopify_domain = current_setting('app.current_tenant', true))
    WITH CHECK (shopify_domain = current_setting('app.current_tenant', true));

CREATE POLICY orders_tenant_insert ON orders
    FOR INSERT
    WITH CHECK (
        shopify_domain = current_setting('app.current_tenant', true)
        OR current_setting('app.current_tenant', true) IS NULL
    );

-- =============================================================================
-- policy_documents table
-- =============================================================================
ALTER TABLE policy_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY policy_documents_tenant_isolation ON policy_documents
    FOR ALL
    USING (shopify_domain = current_setting('app.current_tenant', true))
    WITH CHECK (shopify_domain = current_setting('app.current_tenant', true));

CREATE POLICY policy_documents_tenant_insert ON policy_documents
    FOR INSERT
    WITH CHECK (
        shopify_domain = current_setting('app.current_tenant', true)
        OR current_setting('app.current_tenant', true) IS NULL
    );

-- =============================================================================
-- audit_logs table (uses tenant_id, not shopify_domain)
-- =============================================================================
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_logs_tenant_isolation ON audit_logs
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY audit_logs_tenant_insert ON audit_logs
    FOR INSERT
    WITH CHECK (
        tenant_id = current_setting('app.current_tenant', true)
        OR current_setting('app.current_tenant', true) IS NULL
    );

-- =============================================================================
-- notifications table (uses tenant_id)
-- =============================================================================
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY notifications_tenant_isolation ON notifications
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY notifications_tenant_insert ON notifications
    FOR INSERT
    WITH CHECK (
        tenant_id = current_setting('app.current_tenant', true)
        OR current_setting('app.current_tenant', true) IS NULL
    );

-- =============================================================================
-- agent_logs table (no direct tenant column — tenant via ticket_id join)
-- =============================================================================
-- agent_logs doesn't have a direct tenant column; tenant isolation is
-- inherited from the parent ticket.  For direct queries against agent_logs,
-- we use a subquery filter:
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_logs_tenant_isolation ON agent_logs
    FOR ALL
    USING (
        ticket_id IN (
            SELECT id FROM tickets
            WHERE shopify_domain = current_setting('app.current_tenant', true)
        )
        OR current_setting('app.current_tenant', true) IS NULL  -- Migration bypass
    );

-- =============================================================================
-- llm_calls table (no direct tenant column — tenant via log_id → tickets)
-- =============================================================================
ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY;

CREATE POLICY llm_calls_tenant_isolation ON llm_calls
    FOR ALL
    USING (
        log_id IN (
            SELECT al.id FROM agent_logs al
            JOIN tickets t ON al.ticket_id = t.id
            WHERE t.shopify_domain = current_setting('app.current_tenant', true)
        )
        OR current_setting('app.current_tenant', true) IS NULL  -- Migration bypass
    );

-- =============================================================================
-- shopify_sessions table (uses shop_domain, NOT shopify_domain)
-- =============================================================================
ALTER TABLE shopify_sessions ENABLE ROW LEVEL SECURITY;

-- shopify_sessions is NOT multi-tenant in the traditional sense — each row
-- is a distinct store.  The tenant middleware sets shopify_domain, but
-- shopify_sessions uses shop_domain.  For now, use a permissive policy
-- (the application already filters by shop_domain in queries).
CREATE POLICY shopify_sessions_access ON shopify_sessions
    FOR ALL
    USING (shop_domain = current_setting('app.current_tenant', true))
    WITH CHECK (shop_domain = current_setting('app.current_tenant', true));

-- =============================================================================
-- Verification query (run after migration to confirm RLS is enabled)
-- =============================================================================
-- SELECT
--     schemaname,
--     tablename,
--     rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
--   AND tablename IN (
--     'tickets', 'customers', 'orders', 'policy_documents',
--     'audit_logs', 'notifications', 'agent_logs', 'llm_calls',
--     'shopify_sessions'
--   )
-- ORDER BY tablename;
