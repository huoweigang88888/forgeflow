"""
ForgeFlow AI - Customer Messaging Templates.

All customer-facing messages go through this template system to ensure
consistent, professional communication even when LLM generation fails.

Phase 2: LLM-powered multi-language translation replaces static i18n templates.
The English templates serve as canonical base messages; translate_message()
uses the LLM to produce localized versions for any language on the fly.

From PRD Section 14.4: Fallback Message Template System.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from forgeflow.monitoring.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(component="messaging.templates")

CUSTOMER_RESPONSE_TEMPLATES = {
    "auto_refund_success": {
        "subject": "Refund Processed for Order {order_number}",
        "body": """Dear {customer_name},

We've processed a full refund of ${refund_amount:.2f} for your order #{order_number}.

{explanation}

The refund will appear in your account within 3-5 business days.

If you have any questions, please don't hesitate to contact us.

Best regards,
{store_name} Customer Service""",
    },
    "shipping_update": {
        "subject": "Shipping Update for Order {order_number}",
        "body": """Dear {customer_name},

{status_message}

Your tracking number: {tracking_number}
You can track your package here: {tracking_url}

Estimated delivery: {estimated_delivery}

Best regards,
{store_name} Customer Service""",
    },
    "pending_approval": {
        "subject": "Update on Your Request - Order {order_number}",
        "body": """Dear {customer_name},

We've received your request regarding order #{order_number}.

Our team is reviewing your case and will get back to you within 24 hours.

Reference: {ticket_id}

Best regards,
{store_name} Customer Service""",
    },
    "fallback": {
        "subject": "Your Inquiry - Order {order_number}",
        "body": """Dear {customer_name},

Thank you for contacting us regarding your order #{order_number}.

We've received your inquiry and our team is reviewing it. We'll respond within 24 hours.

Reference: {ticket_id}

Best regards,
{store_name} Customer Service""",
    },
    "escalated": {
        "subject": "Your Case Has Been Escalated - Order {order_number}",
        "body": """Dear {customer_name},

Your case regarding order #{order_number} has been escalated to our senior support team for priority handling.

Our team will review your situation and reach out within 24 hours with a resolution.

Reference: {ticket_id}

We appreciate your patience.

Best regards,
{store_name} Customer Service""",
    },
    "exchange_initiated": {
        "subject": "Exchange Initiated for Order {order_number}",
        "body": """Dear {customer_name},

We've initiated an exchange for your order #{order_number}.

{explanation}

You will receive a confirmation with return shipping instructions shortly.

Best regards,
{store_name} Customer Service""",
    },
    # =========================================================================
    # Chinese (Simplified) translations — _zh variants
    # =========================================================================
    "auto_refund_success_zh": {
        "subject": "订单 {order_number} 退款已处理",
        "body": """尊敬的 {customer_name}，

我们已为您的订单 #{order_number} 处理了 ${refund_amount:.2f} 的全额退款。

{explanation}

退款将在 3-5 个工作日内到账。

如有任何疑问，请随时联系我们。

此致
{store_name} 客服团队""",
    },
    "shipping_update_zh": {
        "subject": "订单 {order_number} 物流更新",
        "body": """尊敬的 {customer_name}，

{status_message}

您的追踪单号：{tracking_number}
您可以通过以下链接追踪包裹：{tracking_url}

预计送达时间：{estimated_delivery}

此致
{store_name} 客服团队""",
    },
    "pending_approval_zh": {
        "subject": "您的请求更新 - 订单 {order_number}",
        "body": """尊敬的 {customer_name}，

我们已收到您关于订单 #{order_number} 的请求。

我们的团队正在审核您的案例，将在 24 小时内回复。

参考编号：{ticket_id}

此致
{store_name} 客服团队""",
    },
    "fallback_zh": {
        "subject": "您的咨询 - 订单 {order_number}",
        "body": """尊敬的 {customer_name}，

感谢您就订单 #{order_number} 联系我们。

我们已收到您的咨询，团队正在审核中。我们将在 24 小时内回复。

参考编号：{ticket_id}

此致
{store_name} 客服团队""",
    },
    "escalated_zh": {
        "subject": "您的案例已升级 - 订单 {order_number}",
        "body": """尊敬的 {customer_name}，

您关于订单 #{order_number} 的案例已升级至高级支持团队进行优先处理。

我们的团队将审核您的情况并在 24 小时内联系您并提供解决方案。

参考编号：{ticket_id}

感谢您的耐心等待。

此致
{store_name} 客服团队""",
    },
    "exchange_initiated_zh": {
        "subject": "订单 {order_number} 换货已启动",
        "body": """尊敬的 {customer_name}，

我们已为您的订单 #{order_number} 启动换货流程。

{explanation}

您将很快收到退货运输说明的确认信息。

此致
{store_name} 客服团队""",
    },
    # =========================================================================
    # Japanese translations — _ja variants
    # =========================================================================
    "auto_refund_success_ja": {
        "subject": "ご注文 {order_number} の返金が処理されました",
        "body": """{customer_name} 様

ご注文 #{order_number} について、${refund_amount:.2f} の全額返金を処理いたしました。

{explanation}

返金は 3〜5 営業日以内に口座に反映されます。

ご不明な点がございましたら、お気軽にお問い合わせください。

敬具
{store_name} カスタマーサービス""",
    },
    "shipping_update_ja": {
        "subject": "ご注文 {order_number} の配送状況のお知らせ",
        "body": """{customer_name} 様

{status_message}

追跡番号：{tracking_number}
以下のリンクから荷物を追跡できます：{tracking_url}

配達予定日：{estimated_delivery}

敬具
{store_name} カスタマーサービス""",
    },
    "pending_approval_ja": {
        "subject": "リクエストの更新について - ご注文 {order_number}",
        "body": """{customer_name} 様

ご注文 #{order_number} に関するリクエストを承りました。

担当チームが内容を確認中です。24 時間以内にご連絡いたします。

参照番号：{ticket_id}

敬具
{store_name} カスタマーサービス""",
    },
    "fallback_ja": {
        "subject": "お問い合わせについて - ご注文 {order_number}",
        "body": """{customer_name} 様

ご注文 #{order_number} についてのお問い合わせをいただき、ありがとうございます。

お問い合わせを承り、担当チームが確認中です。24 時間以内にご返信いたします。

参照番号：{ticket_id}

敬具
{store_name} カスタマーサービス""",
    },
    "escalated_ja": {
        "subject": "お客様のケースは優先対応に引き継がれました - ご注文 {order_number}",
        "body": """{customer_name} 様

ご注文 #{order_number} に関するケースは、優先対応のため上級サポートチームに引き継がれました。

担当チームが内容を確認し、24 時間以内に解決策をご連絡いたします。

参照番号：{ticket_id}

お待たせして申し訳ございません。

敬具
{store_name} カスタマーサービス""",
    },
    "exchange_initiated_ja": {
        "subject": "ご注文 {order_number} の交換手続きを開始しました",
        "body": """{customer_name} 様

ご注文 #{order_number} の交換手続きを開始いたしました。

{explanation}

返送手順のご案内をまもなくお送りいたします。

敬具
{store_name} カスタマーサービス""",
    },
}


def render_template(template_name: str, language: str = "en", **kwargs: object) -> str:
    """Render a customer message template.

    Args:
        template_name: Key in CUSTOMER_RESPONSE_TEMPLATES.
        language: ISO 639-1 language code (en, zh, ja). Falls back to en.
        **kwargs: Template variables (customer_name, order_number, etc.).

    Returns:
        Rendered message body string with variables substituted.
    """
    # Try language-specific variant first
    if language and language != "en":
        localized_key = f"{template_name}_{language}"
        template = CUSTOMER_RESPONSE_TEMPLATES.get(localized_key)
        if template is not None:
            body = template["body"]
            try:
                return body.format(**kwargs)
            except (KeyError, ValueError):
                pass  # Fall through to default

    template = CUSTOMER_RESPONSE_TEMPLATES.get(template_name)
    if template is None:
        template = CUSTOMER_RESPONSE_TEMPLATES["fallback"]

    body = template["body"]
    try:
        return body.format(**kwargs)
    except (KeyError, ValueError):
        # If formatting fails, return a safe default
        return (
            f"Dear Customer,\n\n"
            f"Thank you for contacting us. Your inquiry has been received "
            f"and our team will respond within 24 hours.\n\n"
            f"Reference: {kwargs.get('ticket_id', 'N/A')}\n\n"
            f"Best regards,\n"
            f"{kwargs.get('store_name', 'Customer Service')}"
        )


def get_subject(template_name: str, language: str = "en") -> str:
    """Get the subject line for a template.

    Args:
        template_name: Key in CUSTOMER_RESPONSE_TEMPLATES.
        language: ISO 639-1 language code (en, zh, ja). Falls back to en.

    Returns:
        Subject line string.
    """
    # Try language-specific variant first
    if language and language != "en":
        localized_key = f"{template_name}_{language}"
        template = CUSTOMER_RESPONSE_TEMPLATES.get(localized_key)
        if template is not None:
            return template["subject"]

    template = CUSTOMER_RESPONSE_TEMPLATES.get(template_name)
    if template is None:
        return "Update on Your Inquiry"
    return template["subject"]


# ── LLM-powered translation (Phase 2) ──

# Language name mapping for LLM prompts
_LANGUAGE_NAMES: dict[str, str] = {
    "zh": "Simplified Chinese (zh-CN)",
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese (zh-TW)",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "ar": "Arabic",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
}


async def translate_message(
    message: str,
    target_language: str,
    *,
    preserve_placeholders: bool = True,
) -> str:
    """Translate a customer message using the LLM.

    Replaces the static i18n template system with real-time LLM translation.
    The English templates serve as canonical base messages; this function
    produces natural, localized translations for any supported language.

    Falls back to static templates (via render_template) if the LLM is
    unavailable or translation fails.

    Args:
        message: The English message body to translate.
        target_language: ISO 639-1 language code (zh, ja, ko, es, etc.).
        preserve_placeholders: If True, preserve {variable} placeholders.

    Returns:
        Translated message string, or the original if translation fails.
    """
    if not target_language or target_language == "en":
        return message

    language_name = _LANGUAGE_NAMES.get(target_language, target_language)

    # Build a translation prompt optimized for customer service messages
    system_prompt = (
        "You are a professional customer service translator for an e-commerce "
        "platform. Translate the following message into "
        f"{language_name}. "
        "Maintain a polite, professional tone appropriate for customer service. "
        "Preserve all formatting, line breaks, and the overall structure of "
        "the message."
    )

    if preserve_placeholders:
        system_prompt += (
            " IMPORTANT: Preserve all {placeholder_variables} exactly as-is "
            "(e.g., {customer_name}, {order_number}, {refund_amount:.2f}, "
            "{tracking_number}). Do NOT translate text inside curly braces."
        )

    user_prompt = f"Translate this customer service message to {language_name}:\n\n{message}"

    try:
        from forgeflow.core.config import get_settings
        from forgeflow.llm.base import LLMFactory

        settings = get_settings()
        llm = LLMFactory.create(
            settings.llm.default_provider,
            model=settings.llm.default_model,
        )

        translated = await llm.complete(
            f"{system_prompt}\n\n{user_prompt}",
            temperature=0.3,  # Low temperature for consistent translations
        )

        # Basic validation: translation should be roughly similar length
        if translated and len(translated) > len(message) * 0.3:
            logger.info(
                "translation_success",
                target_language=target_language,
                original_length=len(message),
                translated_length=len(translated),
            )
            return translated.strip()

        logger.warning(
            "translation_too_short",
            target_language=target_language,
            original_length=len(message),
            translated_length=len(translated) if translated else 0,
        )
        return message

    except Exception:
        logger.exception(
            "translation_llm_error",
            target_language=target_language,
        )
        return message
