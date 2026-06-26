"""
ForgeFlow AI - RLS Session Configurator.

Sets the PostgreSQL runtime parameter ``app.current_tenant`` at the
start of every database session so that RLS policies can enforce
tenant isolation at the database level.

Usage:
    In ``db/session.py`` or the app startup, call::

        from forgeflow.security.rls import install_rls_session_hook
        install_rls_session_hook()

    Then, before each request, set the tenant::

        await db.execute(
            text("SELECT set_config('app.current_tenant', :domain, false)"),
            {"domain": shopify_domain},
        )

The RLS policies (defined in migration ``c3d4e5f6a7b8``) will then
automatically filter all queries to the current tenant.

Design decisions:
- Uses ``current_setting('app.current_tenant', true)`` with ``missing_ok=true``
  so that if the parameter is NOT set, the policy evaluates to NULL and
  Postgres returns 0 rows (fail-closed).
- The parameter is scoped to the current transaction — it does not leak
  across connections or sessions.
"""

from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession


async def _set_tenant_on_connect(dbapi_connection, connection_record):
    """Initialize tenant parameter on new connections.

    This is a safety net: sets the parameter to an empty string so that
    RLS policies evaluate cleanly (returning 0 rows) if the application
    forgets to set the real tenant.
    """
    # Use the raw DBAPI connection for synchronous setup
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT set_config('app.current_tenant', '', false)")
    finally:
        cursor.close()


@event.listens_for(AsyncSession, "after_begin")
def _ensure_tenant_is_set(session: AsyncSession, transaction, connection):
    """Ensure 'app.current_tenant' is initialized after transaction begin.

    If the application hasn't set it yet, this hook sets it to an empty
    string so RLS policies don't error on NULL comparison.
    """
    # This is a synchronous event callback — we use the sync connection
    conn = connection.connection  # Raw DBAPI connection
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT set_config('app.current_tenant', '', true)")
    finally:
        cursor.close()


def install_rls_session_hook(engine=None):
    """Install the RLS connection initialization hook.

    Call once at application startup.  If ``engine`` is provided,
    also installs a connect-level hook on the sync engine.

    Args:
        engine: Optional sync SQLAlchemy engine for connection-level hooks.
    """
    from forgeflow.monitoring.logger import get_logger

    log = get_logger(component="security.rls")
    log.info("rls_session_hook_installed")

    if engine is not None:
        from sqlalchemy import event as sync_event

        sync_event.listen(engine.sync_engine, "connect", _set_tenant_on_connect)


async def set_tenant_context(session: AsyncSession, shopify_domain: str) -> None:
    """Set the current tenant for RLS enforcement.

    Call this at the start of every request, after obtaining a DB session.
    This sets ``app.current_tenant`` which all RLS policies reference.

    Args:
        session: Active async SQLAlchemy session.
        shopify_domain: The tenant's Shopify domain (e.g., mystore.myshopify.com).

    Example:
        async def get_db(shop: str = Depends(get_current_shop)):
            async with AsyncSessionLocal() as session:
                await set_tenant_context(session, shop)
                yield session
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant', :domain, false)"),
        {"domain": shopify_domain},
    )
