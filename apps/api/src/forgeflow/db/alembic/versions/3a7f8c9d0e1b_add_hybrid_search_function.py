"""add_hybrid_search_function

Revision ID: 3a7f8c9d0e1b
Revises: 2540639b85a9
Create Date: 2026-06-21 00:00:00.000000

Adds the hybrid_search() PL/pgSQL function that combines pgvector
cosine similarity with PostgreSQL full-text search for ranked
policy document retrieval.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3a7f8c9d0e1b"
down_revision: str | None = "2540639b85a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_HYBRID_SEARCH_FUNCTION = """
CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    p_shopify_domain text DEFAULT 'default',
    similarity_weight float DEFAULT 0.7,
    keyword_weight float DEFAULT 0.3,
    match_limit int DEFAULT 10,
    match_threshold float DEFAULT 0.1
)
RETURNS TABLE(
    id uuid,
    title varchar(500),
    content text,
    content_hash varchar(64),
    chunk_index int,
    source_document_id varchar(36),
    embedding vector(1536),
    category varchar(100),
    tags jsonb,
    is_active boolean,
    version int,
    uploaded_by varchar(100),
    uploaded_at timestamptz,
    created_at timestamptz,
    updated_at timestamptz,
    shopify_domain varchar(255),
    platform varchar(20),
    similarity float,
    text_relevance float,
    hybrid_score float
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    query_tsvector tsvector;
    query_tsquery tsquery;
BEGIN
    -- 1. Build tsquery from plain text: convert to plainto_tsquery for simpler matching
    query_tsquery := plainto_tsquery('english', query_text);

    -- 2. If query_text is empty or yields no meaningful tsquery, fall back to
    --    vector-only search (keyword_weight = 0, similarity_weight = 1)
    IF query_tsquery IS NULL OR numnode(query_tsquery) = 0 THEN
        similarity_weight := 1.0;
        keyword_weight := 0.0;
        -- Use a dummy tsquery that never matches
        query_tsquery := to_tsquery('english', 'zzz_no_match_placeholder');
    END IF;

    -- 3. Execute the hybrid query
    RETURN QUERY
    SELECT
        pd.id,
        pd.title,
        pd.content,
        pd.content_hash,
        pd.chunk_index,
        pd.source_document_id,
        pd.embedding,
        pd.category,
        pd.tags,
        pd.is_active,
        pd.version,
        pd.uploaded_by,
        pd.uploaded_at,
        pd.created_at,
        pd.updated_at,
        pd.shopify_domain,
        pd.platform,
        -- Cosine similarity: 1.0 - cosine_distance
        (1.0 - (pd.embedding <=> query_embedding))::float AS similarity,
        -- Text relevance via ts_rank (normalized)
        COALESCE(
            ts_rank(to_tsvector('english', pd.content), query_tsquery, 32)::float,
            0.0
        ) AS text_relevance,
        -- Hybrid score: weighted combination
        (
            similarity_weight * (1.0 - (pd.embedding <=> query_embedding))::float
            + keyword_weight * COALESCE(
                ts_rank(to_tsvector('english', pd.content), query_tsquery, 32)::float,
                0.0
            )
        )::float AS hybrid_score
    FROM policy_documents pd
    WHERE
        pd.is_active = TRUE
        AND pd.shopify_domain = hybrid_search.p_shopify_domain
        AND pd.embedding IS NOT NULL
        AND (
            -- Either vector similarity meets threshold, or text match exists
            (1.0 - (pd.embedding <=> query_embedding))::float >= match_threshold
            OR to_tsvector('english', pd.content) @@ query_tsquery
        )
    ORDER BY hybrid_score DESC
    LIMIT match_limit;
END;
$$;
"""

_DROP_HYBRID_SEARCH_FUNCTION = """
DROP FUNCTION IF EXISTS hybrid_search(
    query_embedding vector(1536),
    query_text text,
    shopify_domain text,
    similarity_weight float,
    keyword_weight float,
    match_limit int,
    match_threshold float
);
"""


def upgrade() -> None:
    """Create the hybrid_search() PL/pgSQL function."""
    # Drop first — CREATE OR REPLACE cannot change return types in PostgreSQL.
    # This makes the migration idempotent across function signature changes.
    op.execute("DROP FUNCTION IF EXISTS hybrid_search CASCADE;")
    op.execute(_HYBRID_SEARCH_FUNCTION)


def downgrade() -> None:
    """Drop the hybrid_search() function."""
    op.execute(_DROP_HYBRID_SEARCH_FUNCTION)
