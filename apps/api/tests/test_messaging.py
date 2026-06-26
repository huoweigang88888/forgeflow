"""
Tests for the LLM-powered message translation in messaging/templates.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════
# Template rendering (existing functionality)
# ═══════════════════════════════════════════════════════════════════════════


class TestRenderTemplate:
    def test_renders_english_template(self):
        from forgeflow.messaging.templates import render_template

        result = render_template(
            "auto_refund_success",
            language="en",
            customer_name="Jane",
            order_number="113-1234567-1234567",
            refund_amount=49.99,
            explanation="Customer requested refund.",
            store_name="Test Store",
        )

        assert "Jane" in result
        assert "49.99" in result
        assert "113-1234567-1234567" in result
        assert "Test Store" in result

    def test_falls_back_to_english_when_language_unknown(self):
        from forgeflow.messaging.templates import render_template

        result = render_template(
            "auto_refund_success",
            language="xx",  # Unknown language
            customer_name="Jane",
            order_number="113-1234567-1234567",
            refund_amount=49.99,
            explanation="Test",
            store_name="Test Store",
        )

        # Should return English (fallback)
        assert "Dear Jane" in result
        assert "refund" in result.lower()

    def test_renders_fallback_template_for_unknown_key(self):
        from forgeflow.messaging.templates import render_template

        result = render_template(
            "nonexistent_template",
            language="en",
            customer_name="Jane",
            order_number="N/A",
            ticket_id="TKT-001",
            store_name="Test Store",
        )

        assert "Jane" in result
        assert "24 hours" in result

    def test_handles_missing_kwargs_gracefully(self):
        from forgeflow.messaging.templates import render_template

        result = render_template(
            "auto_refund_success",
            language="en",
            # Missing most kwargs
        )

        # Should fall back to safe default
        assert "Dear Customer" in result

    def test_get_subject_english(self):
        from forgeflow.messaging.templates import get_subject

        subject = get_subject("auto_refund_success", language="en")
        assert "Refund" in subject

    def test_get_subject_fallback(self):
        from forgeflow.messaging.templates import get_subject

        subject = get_subject("nonexistent", language="en")
        assert len(subject) > 0


# ═══════════════════════════════════════════════════════════════════════════
# LLM Translation (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════


class TestTranslateMessage:
    @pytest.mark.asyncio
    async def test_returns_original_for_english(self):
        """Should return the message unchanged when target is 'en'."""
        from forgeflow.messaging.templates import translate_message

        result = await translate_message(
            "Dear Jane, your refund has been processed.",
            target_language="en",
        )
        assert result == "Dear Jane, your refund has been processed."

    @pytest.mark.asyncio
    async def test_returns_original_for_empty_language(self):
        """Should return the message unchanged when target is empty."""
        from forgeflow.messaging.templates import translate_message

        result = await translate_message(
            "Dear Jane, your refund has been processed.",
            target_language="",
        )
        assert "Dear Jane" in result

    @pytest.mark.asyncio
    async def test_translates_to_chinese(self):
        """Should call LLM and return translated text."""
        from forgeflow.messaging.templates import translate_message

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="尊敬的 Jane，您的退款已处理。")

        # Patch at the source modules since imports are local inside translate_message()
        with patch("forgeflow.llm.base.LLMFactory") as mock_factory:
            mock_factory.create.return_value = mock_llm

            with patch("forgeflow.core.config.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock()
                mock_settings.return_value.llm.default_provider = "deepseek"
                mock_settings.return_value.llm.default_model = "deepseek-chat"

                result = await translate_message(
                    "Dear Jane, your refund has been processed.",
                    target_language="zh",
                )

        # Should have called LLM with low temperature
        call_kwargs = mock_llm.complete.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.3
        assert "Jane" in result  # Name preserved
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_falls_back_on_llm_error(self):
        """Should return original message when LLM call fails."""
        from forgeflow.messaging.templates import translate_message

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=Exception("LLM unavailable"))

        with patch("forgeflow.llm.base.LLMFactory") as mock_factory:
            mock_factory.create.return_value = mock_llm

            with patch("forgeflow.core.config.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock()
                mock_settings.return_value.llm.default_provider = "deepseek"
                mock_settings.return_value.llm.default_model = "deepseek-chat"

                result = await translate_message(
                    "Dear Jane, your refund has been processed.",
                    target_language="ja",
                )

        # Should return original on error
        assert "Dear Jane" in result

    @pytest.mark.asyncio
    async def test_rejects_too_short_translation(self):
        """Should return original if translation is suspiciously short."""
        from forgeflow.messaging.templates import translate_message

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value="OK")

        original = (
            "Dear Jane, your refund of $49.99 for order #113-1234567-1234567 has been processed."
        )

        with patch("forgeflow.llm.base.LLMFactory") as mock_factory:
            mock_factory.create.return_value = mock_llm

            with patch("forgeflow.core.config.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock()
                mock_settings.return_value.llm.default_provider = "deepseek"
                mock_settings.return_value.llm.default_model = "deepseek-chat"

                result = await translate_message(
                    original,
                    target_language="zh",
                )

        # Too short (2 chars vs 90+ chars) — should reject and return original
        assert result == original

    @pytest.mark.asyncio
    async def test_preserves_placeholders_in_prompt(self):
        """Should instruct LLM to preserve template variables."""
        from forgeflow.messaging.templates import translate_message

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(
            return_value="Estimada {customer_name}, su reembolso de ${refund_amount:.2f} ha sido procesado."
        )

        with patch("forgeflow.llm.base.LLMFactory") as mock_factory:
            mock_factory.create.return_value = mock_llm

            with patch("forgeflow.core.config.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock()
                mock_settings.return_value.llm.default_provider = "deepseek"
                mock_settings.return_value.llm.default_model = "deepseek-chat"

                result = await translate_message(
                    "Dear {customer_name}, your refund of ${refund_amount:.2f} has been processed.",
                    target_language="es",
                )

        assert "{customer_name}" in result
        assert "{refund_amount:.2f}" in result
