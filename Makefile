# =============================================================================
# ForgeFlow AI - Unified Makefile
# =============================================================================
# Provides a single entry point for common development commands.
# Usage: make <target>

.PHONY: help dev setup lint typecheck test clean db-migrate db-rollback db-seed

# Default target
help:
	@echo "ForgeFlow AI Development Commands"
	@echo "================================="
	@echo ""
	@echo "  make dev          Start all services (API + Web)"
	@echo "  make dev-api      Start API server only"
	@echo "  make dev-web      Start frontend only"
	@echo "  make setup        Install all dependencies"
	@echo "  make lint         Run all linters"
	@echo "  make typecheck    Run type checkers"
	@echo "  make test         Run all tests"
	@echo "  make clean        Clean build artifacts"
	@echo ""
	@echo "  make db-migrate   Run database migrations"
	@echo "  make db-rollback  Rollback last migration"
	@echo "  make db-seed      Seed database with sample data"
	@echo ""

dev: dev-api dev-web

dev-api:
	$(MAKE) -C apps/api dev

dev-web:
	pnpm --filter @forgeflow/web dev

setup:
	pnpm install
	$(MAKE) -C apps/api setup

lint:
	$(MAKE) -C apps/api lint
	pnpm --filter @forgeflow/web lint

typecheck:
	$(MAKE) -C apps/api typecheck
	pnpm --filter @forgeflow/web typecheck

test:
	$(MAKE) -C apps/api test
	pnpm --filter @forgeflow/web test

clean:
	$(MAKE) -C apps/api clean
	pnpm --filter @forgeflow/web clean

db-migrate:
	$(MAKE) -C apps/api db-migrate

db-rollback:
	$(MAKE) -C apps/api db-rollback

db-seed:
	$(MAKE) -C apps/api db-seed
