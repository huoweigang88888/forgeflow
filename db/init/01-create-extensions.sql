-- =============================================================================
-- ForgeFlow AI - Database Extensions
-- =============================================================================
-- This script runs automatically when the PostgreSQL container starts
-- for the first time (via /docker-entrypoint-initdb.d).

-- UUID generation support
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Vector similarity search (for knowledge base, Phase 3)
CREATE EXTENSION IF NOT EXISTS vector;

-- Case-insensitive text search
CREATE EXTENSION IF NOT EXISTS citext;

-- Check installed extensions
SELECT extname, extversion FROM pg_extension;
