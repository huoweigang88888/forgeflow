"""
Tests for hybrid search (pgvector + full-text) policy retrieval.

Verifies that the hybrid_search Python wrapper correctly formats
the SQL call and processes results.  The actual PostgreSQL function
is tested via the Alembic migration's built-in test.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestHybridSearchWrapper:
    """Unit tests for the hybrid_search() CRUD function."""

    @pytest.mark.asyncio
    async def test_formats_embedding_and_calls_stored_function(self):
        """The wrapper should format the embedding as a pgvector literal
        and call the hybrid_search() stored function with all parameters."""
        from forgeflow.crud.policy import hybrid_search

        # Mock database session
        mock_db = AsyncMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_result

        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        await hybrid_search(
            mock_db,
            query_embedding=embedding,
            query_text="shipping delay refund",
            shopify_domain="test-store",
            similarity_weight=0.7,
            keyword_weight=0.3,
            limit=5,
            threshold=0.2,
        )

        # Verify execute was called once
        assert mock_db.execute.call_count == 1

        # Check the query uses the stored function
        call_args = mock_db.execute.call_args
        sql: str = str(call_args[0][0])
        assert "hybrid_search(" in sql.lower() or "hybrid_search" in sql
        assert "::vector" in sql

        # Check params
        params = call_args[0][1]
        assert params["query_text"] == "shipping delay refund"
        assert params["shopify_domain"] == "test-store"
        assert params["sim_weight"] == 0.7
        assert params["kw_weight"] == 0.3
        assert params["limit"] == 5
        assert params["threshold"] == 0.2
        # embedding should be a pgvector literal string
        assert params["embedding"] == "[0.1,0.2,0.3,0.4,0.5]"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_results(self):
        """Should return an empty list when the DB returns no rows."""
        from forgeflow.crud.policy import hybrid_search

        mock_db = AsyncMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_result

        result = await hybrid_search(
            mock_db,
            query_embedding=[0.0] * 1536,
            query_text="nonexistent query",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_parses_result_rows_correctly(self):
        """Should correctly parse DB result rows into hit dicts."""
        from forgeflow.crud.policy import hybrid_search

        mock_db = AsyncMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = [
            {
                "id": "uuid-1",
                "title": "Shipping Policy",
                "content": "Free returns within 30 days.",
                "category": "shipping",
                "tags": ["returns", "shipping"],
                "chunk_index": 0,
                "source_document_id": "doc-1",
                "similarity": 0.95,
                "text_relevance": 0.88,
                "hybrid_score": 0.929,
            },
        ]
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_result

        result = await hybrid_search(
            mock_db,
            query_embedding=[0.1] * 1536,
            query_text="shipping returns",
        )

        assert len(result) == 1
        hit = result[0]
        assert hit["policy_id"] == "uuid-1"
        assert hit["title"] == "Shipping Policy"
        assert hit["content"] == "Free returns within 30 days."
        assert hit["category"] == "shipping"
        assert hit["tags"] == ["returns", "shipping"]
        assert hit["chunk_index"] == 0
        assert hit["source_document_id"] == "doc-1"
        assert hit["similarity"] == 0.95
        assert hit["text_relevance"] == 0.88
        assert hit["hybrid_score"] == 0.929

    @pytest.mark.asyncio
    async def test_default_weights_and_threshold(self):
        """Should use sensible defaults: similarity=0.7, keyword=0.3, threshold=0.1."""
        from forgeflow.crud.policy import hybrid_search

        mock_db = AsyncMock()
        mock_mappings = MagicMock()
        mock_mappings.all.return_value = []
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        mock_db.execute.return_value = mock_result

        await hybrid_search(
            mock_db,
            query_embedding=[0.0] * 1536,
            query_text="test",
        )

        params = mock_db.execute.call_args[0][1]
        assert params["sim_weight"] == 0.7
        assert params["kw_weight"] == 0.3
        assert params["threshold"] == 0.1
        assert params["limit"] == 10
        assert params["shopify_domain"] == "default"
