"""
ForgeFlow AI - Notifications Package.

External notification providers for sending customer emails (SendGrid)
and SMS messages (Twilio). These operate independently of any specific
e-commerce platform provider.

Usage:
    from forgeflow.providers.notifications import NotificationDispatcher

    dispatcher = NotificationDispatcher()
    await dispatcher.send_email(to="...", subject="...", body="...")
"""

from forgeflow.providers.notifications.dispatcher import (
    NotificationDispatcher,
    get_dispatcher,
)
from forgeflow.providers.notifications.sendgrid_provider import (
    SendGridError,
    SendGridProvider,
)
from forgeflow.providers.notifications.twilio_provider import (
    TwilioError,
    TwilioProvider,
)

__all__ = [
    "get_dispatcher",
    "NotificationDispatcher",
    "SendGridError",
    "SendGridProvider",
    "TwilioError",
    "TwilioProvider",
]
