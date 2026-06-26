"""
ForgeFlow AI - Structured Logging.

Uses structlog for JSON-formatted, key-value structured logging.
Log entries include request_id, tenant, and component context for
distributed tracing correlation.
"""

import logging
import sys
import typing

import structlog


def setup_logging(app_env: str = "development", log_level: str = "INFO") -> None:
    """Configure structlog for the application.

    - Development: Pretty console output with colors
    - Staging/Production: JSON output for log aggregation

    Args:
        app_env: The application environment (development/staging/production).
        log_level: Minimum log level to emit.
    """
    # Determine processor chain based on environment
    if app_env == "development":
        renderer: structlog.typing.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer(serializer=json.dumps, default=str)

    # Shared processors (before renderer)
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        typing.cast(
            structlog.typing.Processor,
            structlog.stdlib.PositionalArgumentsFormatter(),
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(**initial_context: str) -> structlog.BoundLogger:
    """Get a bound logger with initial context.

    Usage:
        logger = get_logger(component="agent", ticket_id="tkt_123")
        logger.info("decision_made", action="auto_refund", amount=45.60)
    """
    return typing.cast(
        structlog.BoundLogger,
        structlog.get_logger().bind(**initial_context),
    )


# Import json at module level for the default serializer
import json  # noqa: E402
