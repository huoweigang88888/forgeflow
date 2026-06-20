# =============================================================================
# ForgeFlow API - Makefile
# =============================================================================

.PHONY: help setup dev lint typecheck test clean db-migrate db-rollback db-seed

help:
	@echo "ForgeFlow API Commands"
	@echo "======================"
	@echo "  make setup         Install dependencies"
	@echo "  make dev           Start development server"
	@echo "  make lint          Run ruff linter"
	@echo "  make typecheck     Run mypy"
	@echo "  make test          Run pytest"
	@echo "  make clean         Clean build artifacts"
	@echo "  make db-migrate    Run alembic migrations"
	@echo "  make db-rollback   Rollback last migration"
	@echo "  make db-seed       Seed database"

setup:
	uv sync --group dev

dev:
	uv run uvicorn forgeflow.main:app --reload --host 0.0.0.0 --port 8000

lint:
	uv run ruff check src/
	uv run ruff format --check src/

lint-fix:
	uv run ruff check --fix src/
	uv run ruff format src/

typecheck:
	uv run mypy src/forgeflow --check-untyped-defs

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=forgeflow --cov-report=html --cov-report=term

test-integration:
	uv run pytest tests/ -v -m integration

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache htmlcov .coverage 2>/dev/null || true

db-migrate:
	uv run alembic upgrade head

db-rollback:
	uv run alembic downgrade -1

db-migrate-new:
	@read -p "Migration message: " msg; \
	uv run alembic revision --autogenerate -m "$$msg"

db-seed:
	uv run python scripts/seed_data.py
