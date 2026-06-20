"""
ForgeFlow AI - Customer Messaging Templates.

All customer-facing messages go through this template system to ensure
consistent, professional communication even when LLM generation fails.

From PRD Section 14.4: Fallback Message Template System.
"""

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
}


def render_template(template_name: str, **kwargs: object) -> str:
    """Render a customer message template.

    Args:
        template_name: Key in CUSTOMER_RESPONSE_TEMPLATES.
        **kwargs: Template variables (customer_name, order_number, etc.).

    Returns:
        Rendered message body string with variables substituted.
    """
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


def get_subject(template_name: str) -> str:
    """Get the subject line for a template.

    Args:
        template_name: Key in CUSTOMER_RESPONSE_TEMPLATES.

    Returns:
        Subject line string.
    """
    template = CUSTOMER_RESPONSE_TEMPLATES.get(template_name)
    if template is None:
        return "Update on Your Inquiry"
    return template["subject"]
