-- =============================================================================
-- ForgeFlow AI - Full-Text Search Configuration
-- =============================================================================
-- Sets up PostgreSQL full-text search for English e-commerce queries.
-- This is the foundation for hybrid search (vector + keyword) in Phase 3.

-- Custom text search configuration for e-commerce support queries
DO $$
BEGIN
    -- Drop existing config if re-running
    IF EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'forgeflow_en') THEN
        DROP TEXT SEARCH CONFIGURATION forgeflow_en;
    END IF;
END $$;

CREATE TEXT SEARCH CONFIGURATION forgeflow_en (
    COPY = pg_catalog.english
);

-- Improve word matching for e-commerce terms
-- (unaccent extension may not exist; use simple instead if unavailable)
DO $$
BEGIN
    ALTER TEXT SEARCH CONFIGURATION forgeflow_en
        ALTER MAPPING FOR hword, hword_part, word
        WITH simple;
EXCEPTION WHEN OTHERS THEN
    -- unaccent not available, use simple (no stemming but works everywhere)
    NULL;
END $$;

-- =============================================================================
-- Hybrid Search Function (Phase 3 — Knowledge Base)
-- =============================================================================
-- Combines pgvector cosine similarity with full-text search relevance.
-- This provides the foundation for the knowledge-base semantic + keyword search.
--
-- Usage:
--   SELECT * FROM hybrid_search(
--       query_embedding := '[0.1, 0.2, ...]'::vector(1536),
--       query_text := 'refund policy for damaged items',
--       shopify_domain := 'test.myshopify.com',
--       similarity_weight := 0.7,
--       keyword_weight := 0.3,
--       match_limit := 10
--   );
-- =============================================================================

CREATE OR REPLACE FUNCTION hybrid_search(
    query_embedding vector(1536),
    query_text text,
    shopify_domain text DEFAULT 'default',
    similarity_weight float DEFAULT 0.7,
    keyword_weight float DEFAULT 0.3,
    match_limit int DEFAULT 10,
    match_threshold float DEFAULT 0.1
)
RETURNS TABLE(
    id uuid,
    title text,
    content text,
    category text,
    tags jsonb,
    chunk_index int,
    source_document_id text,
    uploaded_by text,
    uploaded_at timestamptz,
    similarity float,
    text_relevance float,
    hybrid_score float
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    normalized_query text;
    ts_query tsquery;
BEGIN
    -- Normalize the query text for full-text search
    normalized_query := lower(trim(query_text));

    -- Build tsquery: join words with OR for broader matching
    -- plainto_tsquery would AND them, which is too strict for short queries
    ts_query := websearch_to_tsquery('forgeflow_en', normalized_query);

    -- If websearch_to_tsquery fails (e.g., empty input), fall back to plainto_tsquery
    IF ts_query IS NULL THEN
        ts_query := plainto_tsquery('forgeflow_en', normalized_query);
    END IF;

    RETURN QUERY
    WITH vector_scores AS (
        SELECT
            pd.id,
            pd.title,
            pd.content,
            pd.category,
            pd.tags,
            pd.chunk_index,
            pd.source_document_id::text,
            pd.uploaded_by,
            pd.uploaded_at,
            -- Cosine similarity: 1 - distance (distance range 0-2, so similarity range -1 to 1)
            -- We clamp negative values to 0 since cos similarity below 0 isn't meaningful
            GREATEST(0.0, 1.0 - (pd.embedding <=> query_embedding)) AS similarity,
            -- Full-text search relevance
            CASE
                WHEN ts_query IS NOT NULL THEN
                    COALESCE(ts_rank(
                        to_tsvector('forgeflow_en', pd.content),
                        ts_query
                    ), 0.0)
                ELSE 0.0
            END AS text_relevance
        FROM policy_documents pd
        WHERE
            pd.embedding IS NOT NULL
            AND pd.is_active = TRUE
            AND pd.shopify_domain = hybrid_search.shopify_domain
    )
    SELECT
        vs.id,
        vs.title,
        vs.content,
        vs.category,
        vs.tags,
        vs.chunk_index,
        vs.source_document_id,
        vs.uploaded_by,
        vs.uploaded_at,
        ROUND(vs.similarity::numeric, 4)::float AS similarity,
        ROUND(vs.text_relevance::numeric, 4)::float AS text_relevance,
        -- Hybrid score: weighted combination of similarity and text relevance
        -- Both scores are normalized to [0, 1] before combining
        ROUND(
            ((similarity_weight * vs.similarity) + (keyword_weight * vs.text_relevance))::numeric,
            4
        )::float AS hybrid_score
    FROM vector_scores vs
    WHERE
        -- At least one signal must be above the match threshold
        (vs.similarity >= match_threshold OR vs.text_relevance > 0)
    ORDER BY
        hybrid_score DESC
    LIMIT match_limit;
END;
$$;

COMMENT ON FUNCTION hybrid_search IS
'Hybrid search combining vector similarity (pgvector cosine distance) and keyword relevance (full-text search with forgeflow_en config).
Phase 3 — Knowledge Base: powers the policy search with semantic + keyword matching.
Weighted scoring: similarity_weight * cos_sim + keyword_weight * ts_rank.
Defaults to 70/30 vector/keyword split, adjustable per query.';
