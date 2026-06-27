"""
ForgeFlow AI - Structured Logging.

Uses structlog for JSON-formatted, key-value structured logging.
Log entries include request_id, tenant, and component context for
distributed tracing correlation.

Supports log sampling: 100% of ERROR/WARNING, 1% of INFO/DEBUG.
"""

import json
import logging
import random
import sys
import typing

import structlog

# ── Log Sampling ──
# 100% of ERROR/WARNING, configurable sample rate for INFO/DEBUG.
# This dramatically reduces log volume in production while preserving
# full visibility into errors and anomalies.

_SUCCESS_LOG_SAMPLE_RATE: float = 0.01  # 1% of successful operations


def _should_sample(
    _logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Drop a fraction of non-error log events via sampling.

    Structlog processor — return event_dict to keep, raise DropEvent to drop.
    Uses method_name ("info"/"error"/...) because add_log_level runs AFTER this
    processor in the chain, so event_dict["level"] does not exist yet.

    Always emits ERROR/WARNING/CRITICAL; samples INFO/DEBUG at
    _SUCCESS_LOG_SAMPLE_RATE (default 1%).
    """
    if method_name in ("error", "critical", "warning"):
        return event_dict  # Never drop error/warning logs
    # Sample success logs
    if random.random() > _SUCCESS_LOG_SAMPLE_RATE:
        raise structlog.DropEvent
    return event_dict


class SamplingFilter(logging.Filter):
    """stdlib logging filter that drops a fraction of non-error log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True  # Always keep warnings and above
        return random.random() <= _SUCCESS_LOG_SAMPLE_RATE


def setup_logging(app_env: str = "development", log_level: str = "INFO") -> None:
    """Configure structlog for the application.

    - Development: Pretty console output with colors
    - Production: JSON output for log aggregation with sampling

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

    # In production, add log sampling (drop 99% of INFO/DEBUG, keep all ERROR/WARNING)
    if app_env != "development":
        shared_processors.insert(0, _should_sample)  # noqa: typed-argument

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
