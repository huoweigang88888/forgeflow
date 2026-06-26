"""
ForgeFlow AI - Twilio SMS Notification Provider.

Sends customer SMS notifications via the Twilio Programmable Messaging API.

Configuration (via Settings / env):
    TWILIO_ACCOUNT_SID  — Twilio account SID.
    TWILIO_AUTH_TOKEN   — Twilio auth token.
    TWILIO_FROM_NUMBER  — Twilio phone number to send from (E.164 format).

Reference: https://www.twilio.com/docs/messaging/api
"""

from __future__ import annotations

import httpx

from forgeflow.core.config import get_settings
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="notifications.twilio")

# Twilio API base URL pattern
_TWILIO_API_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"


class TwilioError(Exception):
    """Twilio API error."""

    def __init__(self, message: str, *, status_code: int = 0, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class TwilioProvider:
    """Twilio SMS notification provider.

    Usage:
        twilio = TwilioProvider()
        success = await twilio.send_sms(
            to="+1234567890",
            message="Your refund has been processed.",
        )
    """

    def __init__(
        self,
        account_sid: str = "",
        auth_token: str = "",
        from_number: str = "",
    ):
        """Initialize Twilio provider.

        Args:
            account_sid: Twilio account SID. Reads from TWILIO_ACCOUNT_SID if empty.
            auth_token: Twilio auth token. Reads from TWILIO_AUTH_TOKEN if empty.
            from_number: Sender phone number (E.164). Reads from TWILIO_FROM_NUMBER if empty.
        """
        settings = get_settings()

        self._account_sid = account_sid or settings.twilio_account_sid
        self._auth_token = auth_token or settings.twilio_auth_token.get_secret_value()
        self._from_number = from_number or settings.twilio_from_number

        self._api_url = _TWILIO_API_TEMPLATE.format(account_sid=self._account_sid)
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if the provider has valid credentials."""
        return bool(self._account_sid and self._auth_token and self._from_number)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client with Twilio auth."""
        if self._client is None:
            import base64

            auth_str = base64.b64encode(f"{self._account_sid}:{self._auth_token}".encode()).decode()

            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Basic {auth_str}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )
        return self._client

    async def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS via Twilio.

        Args:
            to: Recipient phone number (E.164 format recommended: +1234567890).
            message: SMS body content (max 1600 chars, segmented at 160).

        Returns:
            True if sent successfully.

        Raises:
            TwilioError: If the API call fails and is not retryable.
        """
        if not self.is_configured:
            logger.warning(
                "twilio_not_configured",
            )
            return False

        # Truncate message to Twilio max (1600 characters)
        truncated = message[:1600]

        form_data = {
            "To": to,
            "From": self._from_number,
            "Body": truncated,
        }

        try:
            client = await self._get_client()
            response = await client.post(self._api_url, data=form_data)

            if response.status_code in (200, 201):
                data = response.json()
                sid = data.get("sid", "unknown")
                logger.info(
                    "twilio_sms_sent",
                    sid=sid,
                    to=f"{to[:3]}***{to[-3:]}" if len(to) > 6 else to,
                )
                return True

            # Twilio returns 4xx for errors
            retryable = response.status_code in (429, 500, 502, 503, 504)
            error_msg = f"Twilio HTTP {response.status_code}"

            try:
                body_data = response.json()
                error_msg = body_data.get("message", error_msg)
            except (ValueError, KeyError):
                error_msg = response.text[:300] or error_msg

            logger.error(
                "twilio_api_error",
                status_code=response.status_code,
                error=error_msg[:300],
            )

            if retryable:
                raise TwilioError(error_msg, status_code=response.status_code, retryable=True)

            return False

        except httpx.TimeoutException:
            logger.error("twilio_timeout")
            raise TwilioError("Twilio request timed out", retryable=True) from None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
