"""
ForgeFlow AI - ShopifySession Model.

Stores OAuth 2.0 session data for installed Shopify stores.  Each row
represents one store that has installed the ForgeFlow AI app via OAuth.

The access token is stored encrypted (AES-256-GCM) via the
``encrypt_token`` / ``decrypt_token`` utilities.  The model provides a
``decrypt_token()`` property for transparent decryption.

This model does NOT use TenantMixin — ``shop_domain`` IS the tenant
identity for OAuth sessions.  It also does NOT use TimestampMixin because
the ``installed_at`` / ``uninstalled_at`` semantics differ from the
generic ``created_at`` / ``updated_at`` pattern.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from forgeflow.db.base import Base, UUIDMixin
from forgeflow.security import decrypt_token as _decrypt_token


class ShopifySession(Base, UUIDMixin):
    """OAuth session for an installed Shopify store.

    One row per store.  Created on successful OAuth callback and
    soft-deleted (via ``is_active`` + ``uninstalled_at``) on uninstall.

    Usage:
        session = await get_session_by_domain(db, "mystore.myshopify.com")
        if session and session.is_installed:
            token = session.decrypt_token()
            provider = ShopifyProvider(
                shop_domain=session.shop_domain,
                access_token=token,
            )
    """

    __tablename__ = "shopify_sessions"

    # ── Identity ──
    shop_domain: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        doc="Shopify store domain (e.g., mystore.myshopify.com)",
    )

    # ── Tokens ──
    access_token_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="AES-256-GCM encrypted Shopify access token",
    )

    # ── Scope ──
    scopes: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
        doc="Comma-separated OAuth scope list granted by the merchant",
    )

    # ── Status ──
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="False if the store uninstalled the app",
    )

    # ── Timestamps ──
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="When the OAuth flow completed and tokens were stored",
    )
    uninstalled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the store uninstalled the app (NULL if still active)",
    )

    # ── Helpers ──

    @property
    def is_installed(self) -> bool:
        """Return True if the store is currently installed and active."""
        return self.is_active and self.uninstalled_at is None

    def decrypt_token(self) -> str:
        """Decrypt and return the plaintext Shopify access token.

        Returns:
            Decrypted access token string (e.g., ``shpat_xxxx``).

        Raises:
            ForgeFlowError: If decryption fails (e.g., SECRET_KEY rotation).
        """
        return _decrypt_token(self.access_token_encrypted)

    def __repr__(self) -> str:
        return f"<ShopifySession(shop_domain={self.shop_domain!r}, is_active={self.is_active})>"
