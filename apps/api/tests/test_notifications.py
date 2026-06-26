"""
Tests for the Notification Providers (SendGrid + Twilio) and Dispatcher.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════
# SendGrid Provider
# ═══════════════════════════════════════════════════════════════════════════


class TestSendGridProvider:
    def test_not_configured_without_api_key(self):
        """is_configured should be False when API key is empty."""
        from forgeflow.providers.notifications.sendgrid_provider import (
            SendGridProvider,
        )

        with patch("forgeflow.providers.notifications.sendgrid_provider.get_settings") as mock:
            mock_settings = MagicMock()
            mock_settings.sendgrid_api_key.get_secret_value.return_value = ""
            mock.return_value = mock_settings

            provider = SendGridProvider()
            assert provider.is_configured is False

    def test_configured_with_api_key(self):
        """is_configured should be True when API key is provided."""
        from forgeflow.providers.notifications.sendgrid_provider import (
            SendGridProvider,
        )

        provider = SendGridProvider(api_key="SG.test_key")
        assert provider.is_configured is True

    @pytest.mark.asyncio
    async def test_send_email_returns_false_when_not_configured(self):
        """Should return False when no API key is set."""
        from forgeflow.providers.notifications.sendgrid_provider import (
            SendGridProvider,
        )

        provider = SendGridProvider(api_key="")
        result = await provider.send_email(
            to="test@example.com",
            subject="Test",
            body="Test body",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_send_email_success(self):
        """Should send email and return True on success."""
        from forgeflow.providers.notifications.sendgrid_provider import (
            SendGridProvider,
        )

        provider = SendGridProvider(api_key="SG.test_key")

        mock_response = MagicMock()
        mock_response.status_code = 202

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.send_email(
                to="customer@example.com",
                subject="Refund Processed",
                body="Dear Customer, your refund has been processed.",
            )

        assert result is True
        # Verify the payload structure
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"]
        assert payload["personalizations"][0]["to"][0]["email"] == "customer@example.com"
        assert payload["personalizations"][0]["subject"] == "Refund Processed"
        assert payload["from"]["email"] == "noreply@forgeflow.dev"

    @pytest.mark.asyncio
    async def test_send_email_handles_api_error(self):
        """Should return False on 4xx errors."""
        from forgeflow.providers.notifications.sendgrid_provider import (
            SendGridProvider,
        )

        provider = SendGridProvider(api_key="SG.invalid")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"errors": [{"message": "Unauthorized"}]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.send_email(
                to="test@example.com",
                subject="Test",
                body="Test",
            )

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# Twilio Provider
# ═══════════════════════════════════════════════════════════════════════════


class TestTwilioProvider:
    def test_not_configured_without_credentials(self):
        """is_configured should be False when credentials are empty."""
        from forgeflow.providers.notifications.twilio_provider import (
            TwilioProvider,
        )

        provider = TwilioProvider(account_sid="", auth_token="", from_number="")
        assert provider.is_configured is False

    def test_configured_with_all_credentials(self):
        """is_configured should be True when all credentials are set."""
        from forgeflow.providers.notifications.twilio_provider import (
            TwilioProvider,
        )

        provider = TwilioProvider(
            account_sid="AC123",
            auth_token="token123",
            from_number="+1234567890",
        )
        assert provider.is_configured is True

    @pytest.mark.asyncio
    async def test_send_sms_returns_false_when_not_configured(self):
        """Should return False when credentials are missing."""
        from forgeflow.providers.notifications.twilio_provider import (
            TwilioProvider,
        )

        provider = TwilioProvider(account_sid="", auth_token="", from_number="")
        result = await provider.send_sms(to="+1234567890", message="Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_sms_success(self):
        """Should send SMS and return True on success."""
        from forgeflow.providers.notifications.twilio_provider import (
            TwilioProvider,
        )

        provider = TwilioProvider(
            account_sid="AC123",
            auth_token="token123",
            from_number="+1234567890",
        )

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"sid": "SM12345"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_get_client", return_value=mock_client):
            result = await provider.send_sms(
                to="+1987654321",
                message="Your refund has been processed.",
            )

        assert result is True


# ═══════════════════════════════════════════════════════════════════════════
# Notification Dispatcher
# ═══════════════════════════════════════════════════════════════════════════


class TestNotificationDispatcher:
    def test_email_not_enabled_without_config(self):
        """email_enabled should be False when SendGrid is not configured."""
        from forgeflow.providers.notifications.dispatcher import (
            NotificationDispatcher,
        )

        dispatcher = NotificationDispatcher()

        with patch("forgeflow.providers.notifications.sendgrid_provider.get_settings") as mock:
            mock_settings = MagicMock()
            mock_settings.sendgrid_api_key.get_secret_value.return_value = ""
            mock.return_value = mock_settings

            assert dispatcher.email_enabled is False

    def test_sms_not_enabled_without_config(self):
        """sms_enabled should be False when Twilio is not configured."""
        from forgeflow.providers.notifications.dispatcher import (
            NotificationDispatcher,
        )

        dispatcher = NotificationDispatcher()

        with patch.object(dispatcher, "_get_twilio") as mock_twilio:
            mock_twilio.return_value = MagicMock(is_configured=False)
            assert dispatcher.sms_enabled is False

    @pytest.mark.asyncio
    async def test_send_email_skips_without_config(self):
        """Should return False when SendGrid is not configured."""
        from forgeflow.providers.notifications.dispatcher import (
            NotificationDispatcher,
        )

        dispatcher = NotificationDispatcher()

        with patch.object(dispatcher, "_get_sendgrid") as mock_sg:
            mock_sg.return_value = MagicMock(is_configured=False)
            result = await dispatcher.send_email(
                to="test@example.com",
                subject="Test",
                body="Test",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_send_sms_skips_without_config(self):
        """Should return False when Twilio is not configured."""
        from forgeflow.providers.notifications.dispatcher import (
            NotificationDispatcher,
        )

        dispatcher = NotificationDispatcher()

        with patch.object(dispatcher, "_get_twilio") as mock_twilio:
            mock_twilio.return_value = MagicMock(is_configured=False)
            result = await dispatcher.send_sms(
                to="+1234567890",
                message="Test",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_send_email_skips_when_no_recipient(self):
        """Should return False when 'to' is empty."""
        from forgeflow.providers.notifications.dispatcher import (
            NotificationDispatcher,
        )

        dispatcher = NotificationDispatcher()
        result = await dispatcher.send_email(to="", subject="Test", body="Test")
        assert result is False

    def test_get_dispatcher_singleton(self):
        """get_dispatcher should return the same instance."""
        from forgeflow.providers.notifications.dispatcher import (
            get_dispatcher,
        )

        d1 = get_dispatcher()
        d2 = get_dispatcher()
        assert d1 is d2
