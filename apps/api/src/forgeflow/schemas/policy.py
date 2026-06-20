"""
ForgeFlow AI - Policy API Schemas.

Pydantic models for policy document API request/response validation.
Matches the policy_documents table from the initial schema migration.
"""

from pydantic import BaseModel, ConfigDict, Field


# ── Request Schemas ──


class PolicyCreateRequest(BaseModel):
    """Request to upload a new policy document (plain text input)."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        examples=["Premium Shipping Guarantee"],
        description="Human-readable policy title",
    )
    content: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        examples=["Customers who purchase premium shipping are guaranteed..."],
        description="Full policy text",
    )
    category: str | None = Field(
        default=None,
        max_length=100,
        examples=["shipping"],
        description="Policy category: refund, shipping, exchange, general",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags for filtering",
    )
    shopify_domain: str = Field(
        default="default",
        max_length=255,
        description="Tenant identifier",
    )
    platform: str = Field(
        default="mock",
        max_length=20,
        description="Platform identifier",
    )


class PolicyUpdateRequest(BaseModel):
    """Request to update an existing policy document."""

    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, min_length=10, max_length=50000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = None
    is_active: bool | None = None


class PolicySearchRequest(BaseModel):
    """Semantic search over policy documents."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["shipping delay refund"],
        description="Natural-language search query",
    )
    category: str | None = Field(
        default=None,
        max_length=100,
        description="Optional category filter",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max results to return",
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold",
    )
    shopify_domain: str = Field(
        default="default",
        max_length=255,
    )


# ── Response Schemas ──


class PolicyDocumentOut(BaseModel):
    """Single policy document in API responses."""

    id: str
    title: str
    content: str
    content_hash: str = ""
    chunk_index: int = 0
    source_document_id: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    version: int = 1
    uploaded_by: str | None = None
    uploaded_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PolicySearchHit(BaseModel):
    """A single search result with similarity score."""

    policy: PolicyDocumentOut
    similarity: float = Field(..., ge=0.0, le=1.0)


class PolicyListResponse(BaseModel):
    """Paginated policy list response."""

    code: int = 0
    data: dict = Field(
        default_factory=lambda: {
            "policies": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }
    )


class PolicyDetailResponse(BaseModel):
    """Single policy detail response."""

    code: int = 0
    data: dict = Field(default_factory=lambda: {"policy": None})


class PolicyCreateResponse(BaseModel):
    """Response after creating a policy."""

    code: int = 0
    message: str = "Policy created"
    data: dict = Field(default_factory=lambda: {"policy": None})


class PolicyUpdateResponse(BaseModel):
    """Response after updating a policy."""

    code: int = 0
    message: str = "Policy updated"
    data: dict = Field(default_factory=lambda: {"policy": None})


class PolicySearchResponse(BaseModel):
    """Response for semantic search."""

    code: int = 0
    data: dict = Field(
        default_factory=lambda: {
            "hits": [],
            "query": "",
            "total": 0,
        }
    )


class PolicyDeleteResponse(BaseModel):
    """Response after deleting a policy."""

    code: int = 0
    message: str = "Policy deleted"
    data: dict = Field(default_factory=lambda: {"id": ""})
