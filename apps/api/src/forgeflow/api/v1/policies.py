"""
ForgeFlow AI - Policy Document API Endpoints.

REST API for managing policy documents with pgvector semantic search.
All endpoints are mounted at /api/v1/policies.
"""

from fastapi import APIRouter, Depends, Query

from forgeflow.core.config import get_settings
from forgeflow.crud import policy as policy_crud
from forgeflow.db.session import DBSession
from forgeflow.llm.base import LLMFactory
from forgeflow.monitoring.logger import get_logger
from forgeflow.schemas.policy import (
    PolicyCreateRequest,
    PolicyCreateResponse,
    PolicyDeleteResponse,
    PolicyDetailResponse,
    PolicyListResponse,
    PolicySearchRequest,
    PolicySearchResponse,
    PolicyUpdateRequest,
    PolicyUpdateResponse,
)

logger = get_logger(component="api.policies")

router = APIRouter(prefix="/policies", tags=["policies"])


def _get_embedding_provider():
    """Create an embedding provider on demand.

    Uses the configured embedding provider (defaults to OpenAI since
    text-embedding-3-small is the only model with embedding support).
    """
    settings = get_settings()
    return LLMFactory.create(settings.llm.embedding_provider, model=settings.llm.embedding_model)


def _policy_to_dict(policy) -> dict:
    """Convert a PolicyDocument ORM object to a dict for API responses."""
    return {
        "id": str(policy.id),
        "title": policy.title,
        "content": policy.content,
        "content_hash": policy.content_hash,
        "chunk_index": policy.chunk_index,
        "source_document_id": policy.source_document_id,
        "category": policy.category,
        "tags": policy.tags or [],
        "is_active": policy.is_active,
        "version": policy.version,
        "uploaded_by": policy.uploaded_by,
        "uploaded_at": policy.uploaded_at.isoformat() if policy.uploaded_at else None,
        "created_at": policy.created_at.isoformat() if hasattr(policy, "created_at") and policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if hasattr(policy, "updated_at") and policy.updated_at else None,
    }


# ── POST /policies ──


@router.post("", status_code=201)
async def create_policy_endpoint(
    body: PolicyCreateRequest,
    db: DBSession,
) -> PolicyCreateResponse:
    """Upload a new policy document.

    Text is automatically chunked, each chunk is embedded via
    OpenAI text-embedding-3-small, and stored with pgvector.
    """
    # Create policy chunks
    policies = await policy_crud.create_policy_with_chunks(
        db,
        title=body.title,
        content=body.content,
        category=body.category,
        tags=body.tags,
        shopify_domain=body.shopify_domain,
        platform=body.platform,
    )

    # Generate embeddings for each chunk
    embed_failures = 0
    try:
        embed_provider = _get_embedding_provider()
        for p in policies:
            result = await embed_provider.embed(p.content)
            if result.success and result.embedding:
                await policy_crud.set_embedding(db, p, result.embedding)
            else:
                embed_failures += 1
                logger.warning(
                    "policy_embed_failed",
                    policy_id=str(p.id),
                    error=result.error or "unknown",
                )
    except Exception as e:
        logger.error(
            "embed_provider_init_failed",
            error=str(e)[:200],
        )

    await db.commit()

    # Return the first chunk as representative
    first = policies[0] if policies else None
    return PolicyCreateResponse(
        code=0,
        message=(
            f"Policy created with {len(policies)} chunks"
            + (f" ({embed_failures} embedding failures)" if embed_failures else "")
        ),
        data={"policy": _policy_to_dict(first) if first else None},
    )


# ── GET /policies ──


@router.get("")
async def list_policies_endpoint(
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category: str | None = Query(default=None),
) -> PolicyListResponse:
    """List policy documents with pagination and optional category filter."""
    offset = (page - 1) * page_size
    policies, total = await policy_crud.list_policies(
        db,
        category=category,
        offset=offset,
        limit=page_size,
    )

    return PolicyListResponse(
        code=0,
        data={
            "policies": [_policy_to_dict(p) for p in policies],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


# ── POST /policies/search ──


@router.post("/search")
async def search_policies_endpoint(
    body: PolicySearchRequest,
    db: DBSession,
) -> PolicySearchResponse:
    """Semantic search over policy documents.

    Embeds the query text, then performs pgvector cosine similarity search.
    Returns policies ranked by similarity, filtered by threshold.
    """
    # Generate query embedding
    try:
        embed_provider = _get_embedding_provider()
        embed_result = await embed_provider.embed(body.query)
    except Exception as e:
        logger.error("search_embed_failed", error=str(e)[:200])
        return PolicySearchResponse(
            code=0,
            data={"hits": [], "query": body.query, "total": 0},
        )

    if not embed_result.success or not embed_result.embedding:
        return PolicySearchResponse(
            code=0,
            data={"hits": [], "query": body.query, "total": 0},
        )

    # Search pgvector
    hits = await policy_crud.search_by_vector(
        db,
        query_embedding=embed_result.embedding,
        shopify_domain=body.shopify_domain,
        category=body.category,
        limit=body.limit,
        threshold=body.threshold,
    )

    return PolicySearchResponse(
        code=0,
        data={
            "hits": [
                {
                    "policy": _policy_to_dict(hit["policy"]),
                    "similarity": hit["similarity"],
                }
                for hit in hits
            ],
            "query": body.query,
            "total": len(hits),
        },
    )


# ── GET /policies/{id} ──


@router.get("/{policy_id}")
async def get_policy_endpoint(
    policy_id: str,
    db: DBSession,
) -> PolicyDetailResponse:
    """Get a single policy document by ID."""
    policy = await policy_crud.get_policy(db, policy_id)

    if not policy:
        return PolicyDetailResponse(
            code=404,
            data={"policy": None},
        )

    return PolicyDetailResponse(
        code=0,
        data={"policy": _policy_to_dict(policy)},
    )


# ── PUT /policies/{id} ──


@router.put("/{policy_id}")
async def update_policy_endpoint(
    policy_id: str,
    body: PolicyUpdateRequest,
    db: DBSession,
) -> PolicyUpdateResponse:
    """Update a policy document.

    If content is changed, the embedding is regenerated.
    """
    policy = await policy_crud.get_policy(db, policy_id)
    if not policy:
        return PolicyUpdateResponse(
            code=404,
            message="Policy not found",
            data={"policy": None},
        )

    update_data = body.model_dump(exclude_none=True)
    updated = await policy_crud.update_policy(db, policy_id, **update_data)

    # Re-embed if content changed
    if updated and body.content is not None:
        try:
            embed_provider = _get_embedding_provider()
            result = await embed_provider.embed(body.content)
            if result.success and result.embedding:
                await policy_crud.set_embedding(db, updated, result.embedding)
            else:
                logger.warning(
                    "policy_reembed_failed",
                    policy_id=policy_id,
                    error=result.error or "unknown",
                )
        except Exception as e:
            logger.error("reembed_provider_failed", error=str(e)[:200])

    await db.commit()

    return PolicyUpdateResponse(
        code=0,
        message="Policy updated",
        data={"policy": _policy_to_dict(updated) if updated else None},
    )


# ── DELETE /policies/{id} ──


@router.delete("/{policy_id}")
async def delete_policy_endpoint(
    policy_id: str,
    db: DBSession,
) -> PolicyDeleteResponse:
    """Soft-delete a policy document (sets is_active=False)."""
    deleted = await policy_crud.delete_policy(db, policy_id)

    if not deleted:
        return PolicyDeleteResponse(
            code=404,
            message="Policy not found",
            data={"id": policy_id},
        )

    await db.commit()

    return PolicyDeleteResponse(
        code=0,
        message="Policy deleted",
        data={"id": policy_id},
    )
