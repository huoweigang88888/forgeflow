"""
ForgeFlow AI - Exception Hierarchy.

All application exceptions inherit from ForgeFlowError for consistent error handling.
"""

from typing import Any


class ForgeFlowError(Exception):
    """Base exception for all ForgeFlow errors."""

    def __init__(self, message: str, *, code: str = "INTERNAL_ERROR", details: dict[str, Any] | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


# --- Resource Errors ---

class NotFoundError(ForgeFlowError):
    """Requested resource does not exist."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            f"{resource} not found: {resource_id}",
            code="NOT_FOUND",
            details={"resource": resource, "id": resource_id},
        )


class AlreadyExistsError(ForgeFlowError):
    """Resource already exists."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            f"{resource} already exists: {resource_id}",
            code="ALREADY_EXISTS",
            details={"resource": resource, "id": resource_id},
        )


# --- Auth Errors ---

class AuthenticationError(ForgeFlowError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="UNAUTHORIZED")


class PermissionDeniedError(ForgeFlowError):
    """User lacks required permissions."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, code="FORBIDDEN")


# --- Provider Errors ---

class ProviderError(ForgeFlowError):
    """External provider (Shopify, Logistics) error."""

    def __init__(self, provider: str, message: str, *, retryable: bool = False):
        super().__init__(
            f"[{provider}] {message}",
            code="PROVIDER_ERROR",
            details={"provider": provider, "retryable": retryable},
        )
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    """Provider request timed out."""

    def __init__(self, provider: str, timeout_s: int):
        super().__init__(
            provider,
            f"Request timed out after {timeout_s}s",
            retryable=True,
        )


# --- LLM Errors ---

class LLMError(ForgeFlowError):
    """LLM provider error."""

    def __init__(self, provider: str, message: str, *, retryable: bool = True):
        super().__init__(
            f"[LLM:{provider}] {message}",
            code="LLM_ERROR",
            details={"provider": provider, "retryable": retryable},
        )


class LLMParseError(LLMError):
    """Failed to parse LLM response."""

    def __init__(self, provider: str, raw_response: str):
        super().__init__(
            provider,
            f"Failed to parse response: {raw_response[:200]}...",
            retryable=True,
        )


# --- Validation Errors ---

class ValidationError(ForgeFlowError):
    """Input validation failed."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            details={"field": field} if field else {},
        )


# --- Agent Errors ---

class AgentError(ForgeFlowError):
    """Agent runtime error."""

    def __init__(self, node: str, message: str):
        super().__init__(
            f"[Agent:{node}] {message}",
            code="AGENT_ERROR",
            details={"node": node},
        )
