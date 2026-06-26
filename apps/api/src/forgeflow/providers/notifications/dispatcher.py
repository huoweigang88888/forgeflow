"""
ForgeFlow AI - Notification Dispatcher.

Routes notification requests (email/SMS) to the appropriate provider
(SendGrid, Twilio) based on configuration availability.

The dispatcher is the single entry point for all customer-facing
notifications from the agent execute node and worker tasks.

Usage:
    from forgeflow.providers.notifications import NotificationDispatcher

    dispatcher = NotificationDispatcher()
    await dispatcher.send_email(
        to="customer@example.com",
        subject="Refund Processed",
        body="Your refund has been processed.",
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forgeflow.monitoring.logger import get_logger

if TYPE_CHECKING:
    from forgeflow.providers.notifications.sendgrid_provider import SendGridProvider
    from forgeflow.providers.notifications.twilio_provider import TwilioProvider

logger = get_logger(component="notifications.dispatcher")


class NotificationDispatcher:
    """Dispatches notifications to the configured providers.

    Lazy-loads providers on first use so that missing credentials
    don't crash the app — they just result in logged warnings.
    """

    def __init__(self):
        self._sendgrid: SendGridProvider | None = None
        self._twilio: TwilioProvider | None = None

    @property
    def email_enabled(self) -> bool:
        """Check if email sending is configured."""
        return self._get_sendgrid().is_configured

    @property
    def sms_enabled(self) -> bool:
        """Check if SMS sending is configured."""
        return self._get_twilio().is_configured

    def _get_sendgrid(self) -> SendGridProvider:
        """Lazy-load the SendGrid provider."""
        if self._sendgrid is None:
            from forgeflow.providers.notifications.sendgrid_provider import (
                SendGridProvider,
            )

            self._sendgrid = SendGridProvider()
        return self._sendgrid

    def _get_twilio(self) -> TwilioProvider:
        """Lazy-load the Twilio provider."""
        if self._twilio is None:
            from forgeflow.providers.notifications.twilio_provider import (
                TwilioProvider,
            )

            self._twilio = TwilioProvider()
        return self._twilio

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str = "",
        from_name: str = "",
        html: bool = False,
    ) -> bool:
        """Send an email notification with retry on transient failures.

        Retries up to 3 times with exponential backoff (1s → 2s → 4s)
        for transient provider errors (timeouts, rate limits, 5xx).
        Non-retryable errors (4xx, auth failures) fail immediately.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Email body.
            from_email: Optional sender email override.
            from_name: Optional sender name override.
            html: If True, body is HTML.

        Returns:
            True if sent, False if not configured or failed after retries.
        """
        if not to:
            logger.warning("notification_no_recipient_email")
            return False

        provider = self._get_sendgrid()
        if not provider.is_configured:
            logger.info(
                "sendgrid_skipped_not_configured",
                to=to[:50],
            )
            return False

        return await _retry_send(
            provider.send_email,
            to=to,
            subject=subject,
            body=body,
            from_email=from_email,
            from_name=from_name,
            html=html,
        )

    async def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS notification with retry on transient failures.

        Retries up to 3 times with exponential backoff for transient
        provider errors. Non-retryable errors fail immediately.

        Args:
            to: Recipient phone number (E.164 format recommended).
            message: SMS body.

        Returns:
            True if sent, False if not configured or failed after retries.
        """
        if not to:
            logger.warning("notification_no_recipient_phone")
            return False

        provider = self._get_twilio()
        if not provider.is_configured:
            logger.info("twilio_skipped_not_configured")
            return False

        return await _retry_send(
            provider.send_sms,
            to=to,
            message=message,
        )

    async def close(self) -> None:
        """Close all provider clients."""
        if self._sendgrid:
            await self._sendgrid.close()
        if self._twilio:
            await self._twilio.close()


# =============================================================================
# Retry helper — shared across send_email and send_sms
# =============================================================================

# Retryable exception types for notification providers
_RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Covers socket errors, DNS failures
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    reraise=False,  # Return False instead of raising after all retries exhausted
)
async def _retry_send(send_fn, **kwargs) -> bool:
    """Call a notification send function with retry on transient failures.

    The tenacity decorator handles the retry loop — this function just
    calls the provider method. On exhaustion, tenacity raises RetryError
    which we catch and convert to False.

    Args:
        send_fn: Async callable (provider.send_email or provider.send_sms).
        **kwargs: Arguments forwarded to send_fn.

    Returns:
        True if sent successfully, False after all retries exhausted.
    """
    try:
        return await send_fn(**kwargs)
    except Exception:
        logger.exception("notification_send_attempt_failed")
        raise  # Let tenacity handle the retry


# Module-level singleton for convenience
_dispatcher: NotificationDispatcher | None = None


def get_dispatcher() -> NotificationDispatcher:
    """Get or create the module-level NotificationDispatcher singleton."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
