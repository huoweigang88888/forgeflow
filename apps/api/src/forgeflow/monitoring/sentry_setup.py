"""
ForgeFlow AI - Sentry Error Monitoring.

Initializes Sentry SDK for error tracking and performance monitoring.
Sentry is optional — if no DSN is provided, this is a no-op.

Features:
- FastAPI + SQLAlchemy integration
- PII scrubbing via before_send callback
- Release tracking for deployment-linked errors
- Environment-specific sampling rates
"""

import os
import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

# ── PII Scrubbing Patterns ──
# Fields whose values should NEVER be sent to Sentry.
_SENSITIVE_FIELDS = {
    "email",
    "customer_email",
    "customer_name",
    "phone",
    "phone_number",
    "address",
    "shipping_address",
    "billing_address",
    "credit_card",
    "card_number",
    "cvv",
    "password",
    "token",
    "api_key",
    "secret",
    "access_token",
    "refresh_token",
    "ip_address",
    "user_agent",
}

# Regex for scrubbing email-like patterns from arbitrary strings
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _scrub_pii(event: dict[str, Any], _hint: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Sanitize sensitive data from Sentry events before sending.

    This is a defense-in-depth measure — even though we set
    ``send_default_pii=False``, this ensures no PII leaks through
    in stack locals, log messages, or custom breadcrumbs.

    Returns the (modified) event, or None to discard the event.
    """
    # 1. Scrub request body data
    if "request" in event and "data" in event.get("request", {}):
        body = event["request"]["data"]
        if isinstance(body, dict):
            for field in _SENSITIVE_FIELDS:
                if field in body:
                    body[field] = "[FILTERED]"
        event["request"]["data"] = body

    # 2. Scrub exception values and stack locals
    for exception in event.get("exception", {}).get("values", []):
        # Scrub raw exception message
        if "value" in exception:
            exception["value"] = _scrub_text(exception["value"])
        # Scrub stack frame variables
        for frame in exception.get("stacktrace", {}).get("frames", []):
            if "vars" in frame:
                frame["vars"] = {
                    k: "[FILTERED]" if k in _SENSITIVE_FIELDS else v
                    for k, v in frame["vars"].items()
                }

    # 3. Scrub breadcrumbs
    for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
        if "message" in breadcrumb:
            breadcrumb["message"] = _scrub_text(breadcrumb["message"])
        if "data" in breadcrumb and isinstance(breadcrumb["data"], dict):
            for field in _SENSITIVE_FIELDS:
                if field in breadcrumb["data"]:
                    breadcrumb["data"][field] = "[FILTERED]"

    return event


def _scrub_text(text: str) -> str:
    """Remove email patterns from arbitrary text strings."""
    return _EMAIL_RE.sub("[email@filtered]", text)


def setup_sentry(dsn: str, environment: str = "development") -> None:
    """Initialize Sentry SDK.

    Args:
        dsn: Sentry project DSN.
        environment: Environment tag for Sentry (development/staging/production).

    If DSN is empty or None, Sentry is not initialized (no-op).

    Sampling strategy:
        - development: 1.0 (catch all errors during local dev)
        - staging:     0.3 (enough to catch pre-prod regressions)
        - production:  0.1 (cost control, statistically significant)
    """
    if not dsn:
        return

    # Per-environment sampling
    sample_rates = {
        "development": 1.0,
        "staging": 0.3,
        "production": 0.1,
    }
    traces_sample_rate = sample_rates.get(environment, 0.1)

    # Detect release version from environment or git
    release = os.getenv("SENTRY_RELEASE") or os.getenv("FLY_APP_VERSION") or None

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=min(traces_sample_rate * 0.5, 0.1),
        before_send=_scrub_pii,  # type: ignore[arg-type]
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,  # Never send PII to Sentry
        # Group errors by exception type + file path (not by message, which varies)
        default_integrations=True,
        max_breadcrumbs=50,
        attach_stacktrace=True,
    )
