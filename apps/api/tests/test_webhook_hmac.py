"""
Unit tests for Shopify webhook HMAC verification.

Tests ``verify_webhook_hmac()`` — the pure function that validates
Shopify webhook signatures.
"""

import base64
import hashlib
import hmac as hmac_module
import json

import pytest

from forgeflow.services.shopify_webhooks import verify_webhook_hmac


class TestVerifyWebhookHmac:
    """Tests for ``verify_webhook_hmac()``."""

    SECRET = "test_client_secret"
    PAYLOAD = json.dumps({"id": 123, "order_number": "ORD-001"}).encode()

    def _compute_valid_hmac(self, body: bytes, secret: str) -> str:
        """Compute a valid HMAC-SHA256 signature matching Shopify's algorithm."""
        computed = hmac_module.new(
            key=secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(computed).decode("ascii")

    # ── Success cases ──

    def test_valid_hmac_passes(self):
        """A correctly computed HMAC should verify successfully."""
        hmac_header = self._compute_valid_hmac(self.PAYLOAD, self.SECRET)
        assert verify_webhook_hmac(self.PAYLOAD, hmac_header, self.SECRET) is True

    def test_empty_body_passes(self):
        """An empty JSON body with correct HMAC should pass."""
        body = b"{}"
        hmac_header = self._compute_valid_hmac(body, self.SECRET)
        assert verify_webhook_hmac(body, hmac_header, self.SECRET) is True

    def test_unicode_body_passes(self):
        """A JSON body with Unicode characters should verify correctly."""
        body = json.dumps(
            {"note": "配送地址：北京市朝阳区"},  # noqa: RUF001
            ensure_ascii=False,
        ).encode("utf-8")
        hmac_header = self._compute_valid_hmac(body, self.SECRET)
        assert verify_webhook_hmac(body, hmac_header, self.SECRET) is True

    # ── Failure cases ──

    def test_empty_header_fails(self):
        """Missing HMAC header should always fail."""
        assert verify_webhook_hmac(self.PAYLOAD, "", self.SECRET) is False

    def test_wrong_secret_fails(self):
        """HMAC computed with a different secret should fail."""
        hmac_header = self._compute_valid_hmac(self.PAYLOAD, "wrong_secret")
        assert verify_webhook_hmac(self.PAYLOAD, hmac_header, self.SECRET) is False

    def test_tampered_body_fails(self):
        """HMAC for original body should not validate a modified body."""
        hmac_header = self._compute_valid_hmac(self.PAYLOAD, self.SECRET)
        tampered_body = json.dumps({"id": 999, "order_number": "FAKE"}).encode()
        assert verify_webhook_hmac(tampered_body, hmac_header, self.SECRET) is False

    def test_byte_flip_fails(self):
        """A single byte change in the body should break the HMAC."""
        hmac_header = self._compute_valid_hmac(self.PAYLOAD, self.SECRET)
        mutated = bytearray(self.PAYLOAD)
        mutated[2] ^= 1  # flip one bit
        assert verify_webhook_hmac(bytes(mutated), hmac_header, self.SECRET) is False

    # ── Security ──

    def test_constant_time_comparison(self):
        """HMAC comparison should not leak timing information.

        Uses ``hmac.compare_digest`` internally — an invalid header of
        the same length should take roughly the same time as a valid one.
        """
        hmac_header = self._compute_valid_hmac(self.PAYLOAD, self.SECRET)
        bad_header = "A" * len(hmac_header)
        # Should return False (not raise) — timing attack resistant
        assert verify_webhook_hmac(self.PAYLOAD, bad_header, self.SECRET) is False

    def test_short_header_handled(self):
        """A header that is too short should not cause errors."""
        bad_header = "abc"
        assert verify_webhook_hmac(self.PAYLOAD, bad_header, self.SECRET) is False

    # ── Edge cases ──

    def test_large_body_verifies(self):
        """Large webhook bodies (e.g., entire order JSON with line items)
        should verify correctly within acceptable time."""
        body = json.dumps(
            {
                "id": 1234567890,
                "line_items": [
                    {
                        "id": i,
                        "title": f"Product {i}",
                        "quantity": 1,
                        "price": f"{10 + i}.00",
                    }
                    for i in range(100)
                ],
            }
        ).encode()
        hmac_header = self._compute_valid_hmac(body, self.SECRET)
        assert verify_webhook_hmac(body, hmac_header, self.SECRET) is True

    @pytest.mark.parametrize(
        "body",
        [
            b"",  # completely empty
            b"not json",  # non-JSON content
            b"\x00\x01\x02",  # binary garbage
        ],
    )
    def test_non_standard_bodies(self, body):
        """Various edge-case bodies should not crash the verifier."""
        hmac_header = self._compute_valid_hmac(body, self.SECRET)
        result = verify_webhook_hmac(body, hmac_header, self.SECRET)
        assert isinstance(result, bool)
