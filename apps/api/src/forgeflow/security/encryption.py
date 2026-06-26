"""
ForgeFlow AI - Token Encryption Utilities.

AES-256-GCM encryption for Shopify OAuth access tokens before database
storage.  Keys are derived from the application SECRET_KEY so no separate
encryption key management is required in Phase 1.

Security properties:
- AES-256-GCM provides authenticated encryption (confidentiality + integrity)
- Random 96-bit IV per encryption operation
- Key derived via SHA-256 from SECRET_KEY → 32 bytes
- Ciphertext is base64-encoded for TEXT column storage

Phase 2 backlog: key versioning to support SECRET_KEY rotation without
invalidating all stored tokens.
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from forgeflow.core.config import get_settings
from forgeflow.core.exceptions import ForgeFlowError

# ── Key derivation ──


def _derive_key() -> bytes:
    """Derive a 32-byte AES-256 key from the application SECRET_KEY.

    Uses SHA-256 to produce a fixed-length key regardless of the
    SECRET_KEY length.  The derived key is NOT persisted — it is
    recomputed on every encrypt/decrypt call.

    Returns:
        32-byte AES key.
    """
    settings = get_settings()
    secret = settings.secret_key.get_secret_value()
    return hashlib.sha256(secret.encode("utf-8")).digest()


# ── Public API ──


def encrypt_token(plaintext: str) -> str:
    """Encrypt a Shopify access token for database storage.

    Uses AES-256-GCM with a random 96-bit nonce.  The output is a
    base64-encoded string containing nonce + ciphertext (the nonce is
    prepended to the ciphertext before encoding).

    Args:
        plaintext: The Shopify access token to encrypt.

    Returns:
        Base64-encoded ciphertext (nonce prepended).

    Raises:
        ForgeFlowError: If encryption fails.
    """
    try:
        key = _derive_key()
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Prepend nonce to ciphertext for storage
        combined = nonce + ciphertext
        return base64.urlsafe_b64encode(combined).decode("ascii")
    except Exception as exc:
        raise ForgeFlowError(
            message=f"Token encryption failed: {exc}",
            code="ENCRYPTION_ERROR",
        ) from exc


def decrypt_token(ciphertext_b64: str) -> str:
    """Decrypt a Shopify access token from database storage.

    Expects a base64-encoded string where the first 12 bytes are the
    GCM nonce and the remainder is the ciphertext.

    Args:
        ciphertext_b64: Base64-encoded ciphertext (nonce + ciphertext).

    Returns:
        Decrypted plaintext access token.

    Raises:
        ForgeFlowError: If the ciphertext is invalid, tampered with, or
            cannot be decrypted (e.g., after SECRET_KEY rotation).
    """
    try:
        key = _derive_key()
        combined = base64.urlsafe_b64decode(ciphertext_b64.encode("ascii"))
        nonce = combined[:12]
        ciphertext = combined[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except ForgeFlowError:
        raise
    except Exception:
        raise ForgeFlowError(
            message=(
                "Token decryption failed. The token may have been encrypted "
                "with a different SECRET_KEY or the data may be corrupted. "
                "Re-authenticate the Shopify store to obtain a new token."
            ),
            code="DECRYPTION_ERROR",
        ) from None
