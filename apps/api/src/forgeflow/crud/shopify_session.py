"""
ForgeFlow AI - ShopifySession CRUD Operations.

Async SQLAlchemy CRUD for the ShopifySession model.  All functions accept
an ``AsyncSession`` and follow the same patterns as ``crud/ticket.py``.

Usage::

    from forgeflow.crud.shopify_session import create_session, get_session_by_domain
    from forgeflow.db.session import DBSession

    @router.post("/auth/shopify/callback")
    async def callback(db: DBSession):
        session = await create_session(db, shop_domain="...", ...)
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forgeflow.models.shopify_session import ShopifySession
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="crud.shopify_session")


# =============================================================================
# CREATE
# =============================================================================


async def create_session(
    db: AsyncSession,
    *,
    shop_domain: str,
    encrypted_token: str,
    scopes: str = "",
) -> ShopifySession:
    """Create a new ShopifySession row.

    Called after successful OAuth callback and token exchange.

    Args:
        db: Async database session.
        shop_domain: Shopify store domain (e.g., mystore.myshopify.com).
        encrypted_token: AES-256-GCM encrypted access token.
        scopes: Comma-separated OAuth scope list.

    Returns:
        The newly created ShopifySession instance.
    """
    now = datetime.now(UTC)
    session = ShopifySession(
        id=uuid4(),
        shop_domain=shop_domain,
        access_token_encrypted=encrypted_token,
        scopes=scopes,
        is_active=True,
        installed_at=now,
    )
    db.add(session)
    await db.flush()
    logger.info("shopify_session_created", shop_domain=shop_domain)
    return session


# =============================================================================
# READ
# =============================================================================


async def get_session_by_domain(db: AsyncSession, shop_domain: str) -> ShopifySession | None:
    """Look up a ShopifySession by store domain.

    Args:
        db: Async database session.
        shop_domain: Shopify store domain.

    Returns:
        The ShopifySession instance, or None if not found.
    """
    result = await db.execute(
        select(ShopifySession).where(ShopifySession.shop_domain == shop_domain)
    )
    return result.scalar_one_or_none()


async def list_active_sessions(db: AsyncSession) -> Sequence[ShopifySession]:
    """Return all currently active (installed) sessions.

    Args:
        db: Async database session.

    Returns:
        Sequence of active ShopifySession instances.
    """
    result = await db.execute(
        select(ShopifySession).where(
            ShopifySession.is_active == True,  # noqa: E712
            ShopifySession.uninstalled_at.is_(None),
        )
    )
    return result.scalars().all()


# =============================================================================
# UPDATE
# =============================================================================


async def update_session_token(
    db: AsyncSession,
    shop_domain: str,
    encrypted_token: str,
    scopes: str = "",
) -> ShopifySession | None:
    """Update the access token for an existing session.

    Used when a store re-authenticates (token rotation / re-install).

    Args:
        db: Async database session.
        shop_domain: Shopify store domain.
        encrypted_token: New encrypted access token.
        scopes: Updated OAuth scope list.

    Returns:
        The updated ShopifySession, or None if the session doesn't exist.
    """
    session = await get_session_by_domain(db, shop_domain)
    if session is None:
        return None
    session.access_token_encrypted = encrypted_token
    session.scopes = scopes
    session.is_active = True
    session.uninstalled_at = None
    await db.flush()
    logger.info("shopify_session_token_updated", shop_domain=shop_domain)
    return session


async def mark_uninstalled(db: AsyncSession, shop_domain: str) -> None:
    """Soft-delete a session by marking it uninstalled.

    The access token is NOT deleted — it's kept for audit trail purposes
    but ``is_active`` is set to False and ``uninstalled_at`` is set.

    Args:
        db: Async database session.
        shop_domain: Shopify store domain.
    """
    session = await get_session_by_domain(db, shop_domain)
    if session is None:
        logger.warning(
            "shopify_session_uninstall_unknown",
            shop_domain=shop_domain,
        )
        return
    session.is_active = False
    session.uninstalled_at = datetime.now(UTC)
    await db.flush()
    logger.info("shopify_session_uninstalled", shop_domain=shop_domain)


# =============================================================================
# DELETE (hard delete — for testing/cleanup only)
# =============================================================================


async def delete_session(db: AsyncSession, shop_domain: str) -> None:
    """Hard-delete a session from the database.

    Prefer ``mark_uninstalled`` for production use.  This is used for
    the ``DELETE /auth/session`` endpoint (explicit disconnect).

    Args:
        db: Async database session.
        shop_domain: Shopify store domain.
    """
    session = await get_session_by_domain(db, shop_domain)
    if session is not None:
        await db.delete(session)
        await db.flush()
        logger.info("shopify_session_deleted", shop_domain=shop_domain)
