"""
ForgeFlow AI - Hybrid Search Tests.

Validates the hybrid_search() CRUD function and the underlying PostgreSQL
PL/pgSQL function structure. Full integration tests require a running
PostgreSQL instance with pgvector — these unit tests verify the code
structure and SQL function definition.
"""



def test_hybrid_search_migration_exists():
    """Verify the Alembic migration file for hybrid_search exists."""
    from pathlib import Path

    # tests/crud/ -> tests/ -> api/ -> src/forgeflow/db/alembic/versions/
    migration_dir = Path(__file__).parents[2] / "src" / "forgeflow" / "db" / "alembic" / "versions"
    migration_files = list(migration_dir.glob("*hybrid_search*"))
    assert len(migration_files) > 0, (
        f"No hybrid_search migration found in {migration_dir}. "
        f"Available: {[f.name for f in migration_dir.glob('*.py')]}"
    )


def test_hybrid_search_migration_has_function():
    """Verify the migration contains the hybrid_search function definition."""
    from pathlib import Path

    migration_dir = Path(__file__).parents[2] / "src" / "forgeflow" / "db" / "alembic" / "versions"
    migration_files = list(migration_dir.glob("*hybrid_search*"))
    assert migration_files

    content = migration_files[0].read_text(encoding="utf-8")

    # Check key components of the SQL function
    assert "CREATE OR REPLACE FUNCTION hybrid_search" in content
    assert "query_embedding vector(1536)" in content
    assert "similarity_weight" in content
    assert "keyword_weight" in content
    assert "cosine_distance" in content
    assert "ts_rank" in content
    assert "to_tsvector" in content
    assert "RETURNS TABLE" in content
    assert "LANGUAGE plpgsql" in content
    assert "DROP FUNCTION IF EXISTS hybrid_search" in content


def test_hybrid_search_crud_function_signature():
    """Verify the CRUD hybrid_search function accepts correct parameters."""
    import inspect

    from forgeflow.crud.policy import hybrid_search

    sig = inspect.signature(hybrid_search)
    params = list(sig.parameters.keys())

    assert "db" in params
    assert "query_embedding" in params
    assert "query_text" in params
    assert "shopify_domain" in params
    assert "similarity_weight" in params
    assert "keyword_weight" in params
    assert "limit" in params
    assert "threshold" in params


def test_hybrid_search_migration_revision_chain():
    """Verify the migration is properly chained to the latest revision."""
    import importlib.util
    from pathlib import Path

    migration_dir = Path(__file__).parents[2] / "src" / "forgeflow" / "db" / "alembic" / "versions"
    migration_files = list(migration_dir.glob("*hybrid_search*"))
    assert migration_files

    mod_path = migration_files[0]
    spec = importlib.util.spec_from_file_location("hybrid_migration", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Verify revision chain
    assert mod.revision == "3a7f8c9d0e1b"
    assert mod.down_revision == "2540639b85a9"  # make_ticket_platform_non_nullable
