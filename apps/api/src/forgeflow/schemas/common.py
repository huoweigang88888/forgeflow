"""
ForgeFlow AI - Common Schemas.

Shared Pydantic models used across all API endpoints.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Standard pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        alias="pageSize",
        description="Items per page",
    )


class ErrorResponse(BaseModel):
    """Standard error response body."""

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error context",
    )
    request_id: str | None = Field(
        default=None,
        description="X-Request-ID for tracing",
    )


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T] = Field(description="List of items for the current page")
    total: int = Field(description="Total number of items across all pages")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")
