"""
ForgeFlow AI - Policy Document CRUD Operations.

Data access layer for policy_documents table with pgvector semantic search.
All functions accept an async SQLAlchemy session as the first argument.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from forgeflow.models.policy_document import PolicyDocument

# ── Text Chunking ──


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split long policy text into overlapping chunks for embedding.

    Strategy (V1): Split by paragraphs first. If a paragraph exceeds
    chunk_size, split at sentence boundaries. Overlap ensures context
    continuity between chunks.

    Args:
        text: The full document text.
        chunk_size: Target max characters per chunk.
        overlap: Overlap characters from previous chunk end.

    Returns:
        List of text chunks.
    """
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    # Split into paragraphs first
    paragraphs = re.split(r"\n\s*\n", text)

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}".strip() if current else para
        else:
            # Current chunk is full — save it
            if current:
                chunks.append(current)

            # If the paragraph itself exceeds chunk_size, split further
            if len(para) > chunk_size:
                # CJK punctuation is intentional for Chinese text support
                sentences = re.split(r"(?<=[.!?。！？])\s+", para)  # noqa: RUF001
                current = ""
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    if len(current) + len(sent) + 1 <= chunk_size:
                        current = f"{current} {sent}".strip() if current else sent
                    else:
                        if current:
                            chunks.append(current)
                        # Carry overlap: last `overlap` chars
                        overlap_text = current[-overlap:] if current and overlap else ""
                        current = (overlap_text + " " + sent).strip() if overlap_text else sent
                if current:
                    chunks.append(current)
                    current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks if chunks else [text]


# ── CRUD ──


async def create_policy(
    db: AsyncSession,
    *,
    title: str,
    content: str,
    category: str | None = None,
    tags: list[str] | None = None,
    chunk_index: int = 0,
    source_document_id: str | None = None,
    uploaded_by: str | None = None,
    shopify_domain: str = "default",
    platform: str = "mock",
) -> PolicyDocument:
    """Create a single PolicyDocument row.

    Does NOT commit — caller is responsible for the transaction.
    """
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    policy = PolicyDocument(
        title=title,
        content=content,
        content_hash=content_hash,
        chunk_index=chunk_index,
        source_document_id=source_document_id,
        category=category,
        tags=tags or [],
        uploaded_by=uploaded_by,
        shopify_domain=shopify_domain,
        platform=platform,
        is_active=True,
        version=1,
    )
    db.add(policy)
    await db.flush()
    return policy


async def create_policy_with_chunks(
    db: AsyncSession,
    *,
    title: str,
    content: str,
    category: str | None = None,
    tags: list[str] | None = None,
    uploaded_by: str | None = None,
    shopify_domain: str = "default",
    platform: str = "mock",
) -> list[PolicyDocument]:
    """Create policy document(s) — chunks large text, creates one row per chunk.

    All chunks share the same source_document_id (the first chunk's id).
    Returns all created PolicyDocument rows.

    Does NOT commit — caller is responsible for the transaction.
    """
    chunks = chunk_text(content)
    source_id: str | None = None
    created: list[PolicyDocument] = []

    for i, chunk_text_val in enumerate(chunks):
        policy = await create_policy(
            db,
            title=title if i == 0 else f"{title} (chunk {i + 1}/{len(chunks)})",
            content=chunk_text_val,
            category=category,
            tags=tags,
            chunk_index=i,
            source_document_id=source_id,
            uploaded_by=uploaded_by,
            shopify_domain=shopify_domain,
            platform=platform,
        )
        created.append(policy)
        if i == 0:
            source_id = str(policy.id)

    # Set source_document_id on the first chunk to its own id
    if created and source_id:
        created[0].source_document_id = source_id
        await db.flush()

    return created


async def get_policy(db: AsyncSession, policy_id: str) -> PolicyDocument | None:
    """Get a single policy document by ID."""
    result = await db.execute(
        select(PolicyDocument).where(PolicyDocument.id == policy_id)
    )
    return result.scalar_one_or_none()


async def list_policies(
    db: AsyncSession,
    *,
    shopify_domain: str = "default",
    category: str | None = None,
    is_active: bool | None = True,
    offset: int = 0,
    limit: int = 20,
) -> tuple[Sequence[PolicyDocument], int]:
    """List policy documents with pagination.

    Returns:
        Tuple of (policies, total_count).
    """
    conditions: list = [PolicyDocument.shopify_domain == shopify_domain]
    if category:
        conditions.append(PolicyDocument.category == category)
    if is_active is not None:
        conditions.append(PolicyDocument.is_active == is_active)

    # Count total
    count_stmt = select(func.count(PolicyDocument.id)).where(and_(*conditions))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page
    stmt = (
        select(PolicyDocument)
        .where(and_(*conditions))
        .order_by(PolicyDocument.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    policies = result.scalars().all()

    return policies, total


async def update_policy(
    db: AsyncSession, policy_id: str, **kwargs
) -> PolicyDocument | None:
    """Update policy fields. Only non-None kwargs are applied.

    Returns updated policy or None if not found.
    Does NOT commit — caller is responsible for the transaction.
    """
    policy = await get_policy(db, policy_id)
    if not policy:
        return None

    for key, value in kwargs.items():
        if value is not None and hasattr(policy, key):
            setattr(policy, key, value)

    # Re-hash if content changed
    if "content" in kwargs and kwargs["content"] is not None:
        policy.content_hash = hashlib.sha256(kwargs["content"].encode()).hexdigest()

    await db.flush()
    return policy


async def delete_policy(db: AsyncSession, policy_id: str) -> bool:
    """Soft-delete a policy (sets is_active=False).

    Returns True if found and deleted, False if not found.
    Does NOT commit.
    """
    policy = await get_policy(db, policy_id)
    if not policy:
        return False
    policy.is_active = False
    await db.flush()
    return True


async def set_embedding(
    db: AsyncSession, policy: PolicyDocument, embedding: list[float]
) -> None:
    """Set the embedding vector on a policy document.

    Does NOT commit — caller is responsible for the transaction.
    """
    policy.embedding = embedding
    await db.flush()


# ── Similarity Search ──


async def search_by_vector(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    shopify_domain: str = "default",
    category: str | None = None,
    limit: int = 5,
    threshold: float = 0.7,
) -> list[dict]:
    """Search for policy documents by embedding similarity.

    Uses pgvector cosine distance (<=> operator). Similarity = 1 - distance.

    Args:
        db: Async database session.
        query_embedding: The embedding vector of the search query.
        shopify_domain: Tenant filter.
        category: Optional category filter.
        limit: Max results to return.
        threshold: Minimum cosine similarity (0.0 to 1.0).

    Returns:
        List of dicts with keys: "policy" (PolicyDocument), "similarity" (float).
    """
    # pgvector comparator: .cosine_distance() maps to <=> operator (range 0-2)
    # similarity = 1 - cosine_distance
    similarity_expr = 1.0 - PolicyDocument.embedding.cosine_distance(
        query_embedding
    )

    conditions: list = [
        PolicyDocument.shopify_domain == shopify_domain,
        PolicyDocument.embedding.is_not(None),
        PolicyDocument.is_active,
    ]
    if category:
        conditions.append(PolicyDocument.category == category)

    stmt = (
        select(PolicyDocument, similarity_expr.label("similarity"))
        .where(and_(*conditions))
        .order_by(PolicyDocument.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    hits: list[dict] = []
    for policy, similarity in rows:
        if similarity >= threshold:
            hits.append({"policy": policy, "similarity": round(float(similarity), 4)})

    return hits


async def hybrid_search(
    db: AsyncSession,
    *,
    query_embedding: list[float],
    query_text: str,
    shopify_domain: str = "default",
    similarity_weight: float = 0.7,
    keyword_weight: float = 0.3,
    limit: int = 10,
    threshold: float = 0.1,
) -> list[dict]:
    """Hybrid search: combines pgvector similarity with full-text keyword relevance.

    Calls the PostgreSQL hybrid_search() SQL function via raw SQL.

    Args:
        db: Async database session.
        query_embedding: The embedding vector of the search query.
        query_text: The raw text query for full-text search.
        shopify_domain: Tenant filter.
        similarity_weight: Weight for vector similarity (0.0 to 1.0).
        keyword_weight: Weight for text relevance (0.0 to 1.0).
        limit: Max results to return.
        threshold: Minimum match threshold (0.0 to 1.0).

    Returns:
        List of dicts with keys: "policy" (PolicyDocument), "similarity",
        "text_relevance", "hybrid_score".
    """
    from sqlalchemy import text

    # Format the embedding as a pgvector literal
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    stmt = text("""
        SELECT * FROM hybrid_search(
            query_embedding := :embedding::vector(1536),
            query_text := :query_text,
            shopify_domain := :shopify_domain,
            similarity_weight := :sim_weight,
            keyword_weight := :kw_weight,
            match_limit := :limit,
            match_threshold := :threshold
        )
    """)

    result = await db.execute(
        stmt,
        {
            "embedding": embedding_str,
            "query_text": query_text,
            "shopify_domain": shopify_domain,
            "sim_weight": similarity_weight,
            "kw_weight": keyword_weight,
            "limit": limit,
            "threshold": threshold,
        },
    )
    rows = result.mappings().all()

    hits: list[dict] = []
    for row in rows:
        hits.append({
            "policy_id": str(row["id"]),
            "title": row["title"],
            "content": row["content"],
            "category": row["category"],
            "tags": row["tags"],
            "chunk_index": row["chunk_index"],
            "source_document_id": row["source_document_id"],
            "similarity": row["similarity"],
            "text_relevance": row["text_relevance"],
            "hybrid_score": row["hybrid_score"],
        })

    return hits
