"""
ForgeFlow AI - SendGrid Email Notification Provider.

Sends transactional customer emails via the SendGrid Mail Send API (v3).

Configuration (via Settings / env):
    SENDGRID_API_KEY — SendGrid API key with Mail Send permissions.

Reference: https://docs.sendgrid.com/api-reference/mail-send/mail-send
"""

from __future__ import annotations

import httpx

from forgeflow.core.config import get_settings
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="notifications.sendgrid")

# SendGrid Mail Send API endpoint
_SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class SendGridError(Exception):
    """SendGrid API error."""

    def __init__(self, message: str, *, status_code: int = 0, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class SendGridProvider:
    """SendGrid email notification provider.

    Usage:
        sg = SendGridProvider()
        success = await sg.send_email(
            to="customer@example.com",
            subject="Your Refund",
            body="Dear Customer, ...",
            from_email="support@mystore.com",
        )
    """

    def __init__(self, api_key: str = ""):
        """Initialize SendGrid provider.

        Args:
            api_key: SendGrid API key. If empty, reads from SENDGRID_API_KEY setting.
        """
        if not api_key:
            settings = get_settings()
            api_key = settings.sendgrid_api_key.get_secret_value()
        self._api_key = api_key
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if the provider has valid credentials."""
        return bool(self._api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx async client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.sendgrid.com",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str = "",
        from_name: str = "",
        html: bool = False,
    ) -> bool:
        """Send an email via SendGrid.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body content (plain text or HTML).
            from_email: Sender email. Defaults to "noreply@forgeflow.dev".
            from_name: Sender display name.
            html: If True, body is treated as HTML.

        Returns:
            True if sent successfully.

        Raises:
            SendGridError: If the API call fails and is not retryable.
        """
        if not self.is_configured:
            logger.warning(
                "sendgrid_not_configured",
                to=to[:50],
            )
            return False

        resolved_from = from_email or "noreply@forgeflow.dev"

        payload = {
            "personalizations": [
                {
                    "to": [{"email": to}],
                    "subject": subject,
                }
            ],
            "from": {
                "email": resolved_from,
                "name": from_name or "ForgeFlow Customer Service",
            },
            "content": [
                {
                    "type": "text/html" if html else "text/plain",
                    "value": body,
                }
            ],
        }

        try:
            client = await self._get_client()
            response = await client.post("/v3/mail/send", json=payload)

            if response.status_code in (200, 201, 202):
                logger.info(
                    "sendgrid_email_sent",
                    to=to[:50],
                    subject=subject[:100],
                )
                return True

            # SendGrid returns 202 for accepted, 4xx for errors
            retryable = response.status_code in (429, 500, 502, 503, 504)
            error_msg = f"SendGrid HTTP {response.status_code}"

            try:
                body_data = response.json()
                errors = body_data.get("errors", [])
                if errors:
                    error_msg = errors[0].get("message", error_msg)
            except (ValueError, KeyError):
                error_msg = response.text[:300] or error_msg

            logger.error(
                "sendgrid_api_error",
                status_code=response.status_code,
                error=error_msg[:300],
            )

            if retryable:
                raise SendGridError(error_msg, status_code=response.status_code, retryable=True)

            return False

        except httpx.TimeoutException:
            logger.error("sendgrid_timeout")
            raise SendGridError("SendGrid request timed out", retryable=True) from None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
