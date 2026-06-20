"""
ForgeFlow AI - Sentry Error Monitoring.

Initializes Sentry SDK for error tracking and performance monitoring.
Sentry is optional — if no DSN is provided, this is a no-op.
"""


import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


def setup_sentry(dsn: str, environment: str = "development") -> None:
    """Initialize Sentry SDK.

    Args:
        dsn: Sentry project DSN.
        environment: Environment tag for Sentry (development/staging/production).

    If DSN is empty or None, Sentry is not initialized (no-op).
    """
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=1.0 if environment == "development" else 0.1,
        profiles_sample_rate=0.1,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,  # Never send PII to Sentry
    )
