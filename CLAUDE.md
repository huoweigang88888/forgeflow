# CLAUDE.md — ForgeFlow AI

## Project Overview

ForgeFlow AI is an AI-powered after-sales service automation platform for e-commerce
(Shopify SMB merchants). Core value prop: automate 80% of after-sales tickets so
human agents only handle high-value or high-emotion interactions.

**Tech Stack**: FastAPI (Python 3.11+) + Next.js 14.2+ (TypeScript) + LangGraph +
PostgreSQL (pgvector) + Redis + Docker

## Monorepo Structure

```
forgeflow/
├── apps/
│   ├── api/          # Python FastAPI backend (src-layout, uv package manager)
│   └── web/          # Next.js frontend (pnpm workspace, shadcn/ui)
├── db/init/          # Database initialization SQL
├── docker-compose.yml
└── .github/workflows/
```

## Commands

| Task | Command |
|------|---------|
| Start all | `pnpm dev` (or `make dev`) |
| API only | `make dev-api` |
| Web only | `pnpm dev:web` |
| Docker up | `pnpm docker:up` |
| DB migrate | `pnpm db:migrate` |
| Lint all | `pnpm lint` |
| Test all | `pnpm test` |

## Development Conventions

### Python (apps/api/)
- **Package manager**: uv (NOT pip/poetry)
- **Linter/formatter**: ruff (replaces flake8+isort+black)
- **Type checker**: mypy (strict mode, gradual adoption)
- **Testing**: pytest + pytest-asyncio
- **Layout**: src-layout (`src/forgeflow/`), domain-oriented internals
- **Config**: pydantic-settings with `.env` file, nested via `__` delimiter

### TypeScript (apps/web/)
- **Package manager**: pnpm
- **Linter/formatter**: Biome (replaces ESLint+Prettier)
- **UI components**: shadcn/ui (copied, not installed)
- **Server state**: TanStack Query
- **Client state**: Zustand (UI-only concerns)
- **Routing**: Next.js App Router

### Database
- **Migrations**: Alembic (auto-generated from SQLAlchemy models)
- **Patterns**: UUID PKs, TimestampMixin, TenantMixin on all tenant-scoped tables
- **Multi-tenant**: shared DB + tenant_id isolation + RLS (Phase 1)

### LLM
- **Abstraction**: Custom `LLMProvider` ABC (NOT LangChain BaseChatModel)
- **Providers**: OpenAI, Anthropic (Phase 0), Qwen (Phase 1+)
- **Resilience**: 3-layer fallback (JSON mode → regex → safe fallback)

## Key Files

- `apps/api/src/forgeflow/core/config.py` — All settings
- `apps/api/src/forgeflow/llm/base.py` — LLM provider abstraction
- `apps/api/src/forgeflow/providers/base.py` — Platform provider interfaces
- `apps/api/src/forgeflow/db/base.py` — SQLAlchemy base + mixins
- `ForgeFlow_AI_PRD_V1.1.md` — Full PRD (2,966 lines)

## Phase 0 Goals

Establish complete development infrastructure:
monorepo, Docker, DB schema, LLM abstraction, provider interfaces,
CI/CD, observability, code quality tools.
