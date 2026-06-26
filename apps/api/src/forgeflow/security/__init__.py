"""
ForgeFlow AI - Security Module.

Data masking utilities for PII protection in logs and LLM inputs,
and AES-256-GCM encryption for Shopify OAuth access tokens.

Implements PRD Section 19.2.
"""

import json
import re
from typing import Any, ClassVar

from forgeflow.security.encryption import decrypt_token, encrypt_token  # noqa: F401 — re-exports


class DataMasker:
    """Sensitive data masking utilities.

    Used across:
    - Logging (structlog processors)
    - LLM prompt preparation (remove sensitive fields)
    - API responses (mask emails, phones)
    - GDPR export (controlled unmasking)
    """

    SENSITIVE_LOG_FIELDS: ClassVar[set[str]] = {
        "email",
        "phone",
        "address",
        "credit_card",
        "customer_name",
        "ip_address",
        "password",
    }

    # ------------------------------------------------------------------
    # Field Maskers
    # ------------------------------------------------------------------

    @staticmethod
    def mask_email(email: str) -> str:
        """Mask an email address for display/logging.

        john.doe@example.com → j***e@example.com
        """
        if not email or "@" not in email:
            return "[REDACTED]"
        local, domain = email.split("@", 1)
        masked_local = local[0] + "***" if len(local) <= 2 else local[0] + "***" + local[-1]
        return f"{masked_local}@{domain}"

    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask a phone number for display.

        +1234567890 → ***-***-7890
        """
        if not phone:
            return "[REDACTED]"
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 4:
            return f"***-***-{digits[-4:]}"
        return "***-***-****"

    @staticmethod
    def mask_api_key(key: str) -> str:
        """Mask an API key for safe logging/display.

        sk-9d5d36df937b49faa9f99269f685dbc2 → sk-9d5d...c2
        sk-ant-api03-xxxxx → sk-ant...xxxx
        """
        if not key or len(key) < 12:
            return "[REDACTED]"
        return f"{key[:7]}...{key[-4:]}"

    @staticmethod
    def mask_log_data(
        data: dict[str, Any], sensitive_fields: set[str] | None = None
    ) -> dict[str, Any]:
        """Recursively mask sensitive fields in log data.

        Args:
            data: The dictionary to mask.
            sensitive_fields: Set of field names to redact.

        Returns:
            A new dict with sensitive values masked.
        """
        if sensitive_fields is None:
            sensitive_fields = DataMasker.SENSITIVE_LOG_FIELDS

        result: dict[str, Any] = {}
        for key, value in data.items():
            if key in sensitive_fields:
                if "email" in key:
                    result[key] = DataMasker.mask_email(str(value))
                elif "phone" in key:
                    result[key] = DataMasker.mask_phone(str(value))
                else:
                    result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = DataMasker.mask_log_data(value, sensitive_fields)
            elif isinstance(value, list):
                result[key] = [
                    DataMasker.mask_log_data(v, sensitive_fields) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    @staticmethod
    def redact_for_llm(data: dict[str, Any]) -> dict[str, Any]:
        """Remove/minimize sensitive data before sending to LLM.

        LLMs don't need full PII to make decisions. We strip:
        - Full email → masked
        - Phone numbers → removed
        - Full address → city + country only
        - Credit cards → removed

        Args:
            data: The data being sent to the LLM.

        Returns:
            A copy with sensitive data minimized.
        """
        safe: dict[str, Any] = json.loads(json.dumps(data))  # Deep copy

        # Remove fields LLM never needs
        safe.pop("phone", None)
        safe.pop("full_address", None)
        safe.pop("credit_card", None)
        safe.pop("ip_address", None)

        # Mask email to just domain
        if "email" in safe:
            safe["email"] = DataMasker.mask_email(safe["email"])

        # Minimize shipping address to city + country
        if "shipping_address" in safe and isinstance(safe["shipping_address"], dict):
            addr = safe["shipping_address"]
            safe["shipping_address"] = {
                "city": addr.get("city", ""),
                "country": addr.get("country", ""),
            }

        return safe
