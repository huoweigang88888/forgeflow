# ForgeFlow AI — Deployment Guide (Phase 5)

> **Target audience**: DevOps / Platform engineers deploying ForgeFlow AI to production.

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start (Fly.io)](#2-quick-start-flyio)
3. [Docker Compose Deployment](#3-docker-compose-deployment)
4. [Environment Configuration](#4-environment-configuration)
5. [Database Setup](#5-database-setup)
6. [SSL & Domain Setup](#6-ssl--domain-setup)
7. [Monitoring Setup](#7-monitoring-setup)
8. [Post-Deployment Checklist](#8-post-deployment-checklist)
9. [Rollback Procedure](#9-rollback-procedure)
10. [Scaling Guide](#10-scaling-guide)

---

## 1. Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **CPU** | 1 vCPU | 2 vCPU |
| **RAM** | 512 MB | 1 GB |
| **Disk** | 10 GB | 20 GB SSD |
| **Docker** | 24+ | Latest |
| **Domain** | 1 | With SSL cert |
| **LLM API Key** | DeepSeek or OpenAI | Both (fallback) |

**External services needed**:
- PostgreSQL 16+ with pgvector extension
- Redis 7.2+
- SMTP server (SendGrid recommended)
- (Optional) Sentry account for error tracking

---

## 2. Quick Start (Fly.io)

Fly.io is the recommended platform for V1. Simple, affordable, auto-scaling.

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Login
flyctl auth login

# 3. Launch the API
cd forgeflow
flyctl launch --name forgeflow-api --dockerfile apps/api/Dockerfile

# 4. Set secrets
flyctl secrets import < .env.production

# 5. Set volume for persistent data (if needed)
flyctl volumes create forgeflow_data --size 10

# 6. Deploy
flyctl deploy

# 7. Check status
flyctl status
flyctl logs
```

**Scale up:**
```bash
flyctl scale count 2          # 2 instances
flyctl scale vm shared-cpu-2x # More CPU
flyctl scale memory 1024      # 1 GB RAM
```

---

## 3. Docker Compose Deployment

For self-hosted or single-VM deployments:

```bash
# 1. Clone and configure
cp .env.production.example .env.production
# Edit .env.production with real values

# 2. Start all services
docker compose -f docker-compose.prod.yml up -d

# 3. Run database migrations
docker compose -f docker-compose.prod.yml exec api \
  alembic upgrade head

# 4. Seed default data (prompts, policies)
docker compose -f docker-compose.prod.yml exec api \
  python -c "
import asyncio
from forgeflow.db.session import AsyncSessionLocal
from forgeflow.prompts.registry import PromptRegistry

async def seed():
    async with AsyncSessionLocal() as session:
        registry = PromptRegistry(session)
        await registry.seed_default_prompts()

asyncio.run(seed())
"

# 5. Verify
curl http://localhost:8000/api/health
```

**View logs:**
```bash
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker
```

---

## 4. Environment Configuration

All configuration via environment variables. See `.env.production.example` for full list.

### Critical Variables (must be set)

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | App secret (64+ random chars) | `openssl rand -hex 32` |
| `DB_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://:password@host:6379/0` |
| `LLM_DEEPSEEK_API_KEY` | DeepSeek API key | `sk-xxx` |
| `SHOPIFY_CLIENT_ID` | Shopify app client ID | From Shopify Partners |
| `SHOPIFY_CLIENT_SECRET` | Shopify app secret | From Shopify Partners |
| `JWT_SECRET_KEY` | JWT signing key | `openssl rand -hex 32` |
| `AES_ENCRYPTION_KEY` | Field-level encryption key | `openssl rand -base64 32` |

### LLM Provider Configuration

The system uses **DeepSeek as primary** (cost-effective) with **OpenAI as fallback**:

```bash
LLM_DEFAULT_PROVIDER=deepseek
LLM_DEFAULT_MODEL=deepseek-chat
LLM_COMPLEX_MODEL=deepseek-chat
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_OPENAI_API_KEY=sk-xxx      # Fallback for complex decisions
```

To use OpenAI as primary instead:
```bash
LLM_DEFAULT_PROVIDER=openai
LLM_DEFAULT_MODEL=gpt-4o-mini
LLM_COMPLEX_MODEL=gpt-4o
```

---

## 5. Database Setup

### Option A: Managed PostgreSQL (Recommended)

Use Supabase, Railway, or AWS RDS with pgvector:

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create database
CREATE DATABASE forgeflow;
```

Then run migrations:
```bash
cd apps/api
uv run alembic upgrade head
```

### Option B: Self-hosted with Docker

Already included in `docker-compose.prod.yml`. Data persists in Docker volumes.

**Backup:**
```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U forgeflow forgeflow > backup_$(date +%Y%m%d).sql
```

**Restore:**
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U forgeflow forgeflow < backup_20260619.sql
```

**Backup schedule (crontab):**
```cron
0 2 * * * cd /opt/forgeflow && docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U forgeflow forgeflow > /backups/forgeflow_$(date +\%Y\%m\%d).sql
```

---

## 6. SSL & Domain Setup

### With Fly.io
SSL certificates are automatically provisioned via Let's Encrypt. No manual setup needed.

### With Docker + Nginx

1. Obtain SSL certificates (Let's Encrypt):
```bash
certbot certonly --standalone -d app.forgeflow.ai
```

2. Copy certs to the Nginx SSL directory:
```bash
cp /etc/letsencrypt/live/app.forgeflow.ai/fullchain.pem docker/nginx/ssl/
cp /etc/letsencrypt/live/app.forgeflow.ai/privkey.pem docker/nginx/ssl/
```

3. Auto-renewal cron:
```cron
0 3 * * * certbot renew --quiet && docker compose -f /opt/forgeflow/docker-compose.prod.yml restart nginx
```

---

## 7. Monitoring Setup

### Prometheus + Grafana (included in docker-compose.prod.yml)

Add to `docker-compose.prod.yml`:

```yaml
prometheus:
  image: prom/prometheus:v2.52
  volumes:
    - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    - ./docker/prometheus/alerts.yml:/etc/prometheus/alerts.yml
    - prometheus_data:/prometheus
  ports:
    - "127.0.0.1:9090:9090"

grafana:
  image: grafana/grafana:11.0
  volumes:
    - ./docker/grafana/datasources:/etc/grafana/provisioning/datasources
    - grafana_data:/var/lib/grafana
  ports:
    - "127.0.0.1:3001:3000"
  environment:
    GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
```

### Key Alerts (see `docker/prometheus/alerts.yml`)

| Alert | Severity | Threshold |
|-------|----------|-----------|
| API Down | Critical | 2 min unreachable |
| High 5xx Error Rate | Critical | > 5% |
| P95 Latency > 1s | Warning | 5 min sustained |
| Agent Fallback > 10% | Warning | 10 min sustained |
| LLM JSON Parse Failure > 2% | Critical | 10 min sustained |
| DB Pool > 85% | Warning | 5 min sustained |
| LLM Cost Spike > $5/hr | Warning | 15 min sustained |

---

## 8. Post-Deployment Checklist

After initial deployment, verify:

- [ ] `GET /api/health` returns 200
- [ ] `GET /api/v1/policies` returns policies list
- [ ] `POST /api/v1/tickets` creates a ticket and returns 201
- [ ] Agent pipeline completes (check ticket status goes to `resolved` or `pending_approval`)
- [ ] WebSocket `/ws/v1/tickets/{id}` connects successfully
- [ ] Grafana dashboard shows API metrics
- [ ] Prometheus targets are all UP
- [ ] SSL certificate is valid (check in browser)
- [ ] Email notifications work (SendGrid / SMTP)
- [ ] Shopify OAuth flow works end-to-end
- [ ] Database backups are scheduled
- [ ] Sentry is receiving errors (if configured)
- [ ] Run golden tests: `pytest tests/evaluation/golden/runner.py -v`
- [ ] All 30 golden test cases pass

### Pilot Customer Verification

For each pilot customer:

- [ ] Tenant onboarding script runs successfully
- [ ] Tenant can access the API with their JWT
- [ ] Knowledge base has been seeded with their policies
- [ ] First real ticket is processed end-to-end
- [ ] LLM costs are being tracked
- [ ] Approval flow works (if applicable)

---

## 9. Rollback Procedure

### Application Rollback

```bash
# Fly.io
flyctl deploy --image registry.fly.io/forgeflow-api:previous-tag

# Docker Compose
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d  # Uses :latest from last build
```

### Prompt Rollback (Hot — No Redeploy Required)

```bash
# Rollback intent detection prompt to previous version via API
curl -X POST https://app.forgeflow.ai/api/v1/prompts/rollback \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{"prompt_name": "intent_detection", "to_version": "v1.0.0"}'
```

### Database Rollback

```bash
# Rollback last migration
docker compose -f docker-compose.prod.yml exec api alembic downgrade -1

# Restore from backup (emergency)
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U forgeflow forgeflow < backup.sql
```

---

## 10. Scaling Guide

### Vertical Scaling (Bigger VMs)

| Scale | Users | Tickets/day | VM Spec | Cost/mo (est.) |
|-------|-------|-------------|---------|----------------|
| Pilot | 1-3 | < 50 | 1 CPU, 512MB | $25-50 |
| Small | 5-10 | 50-200 | 2 CPU, 1GB | $50-100 |
| Medium | 10-50 | 200-1000 | 2-4 CPU, 2GB | $100-300 |
| Large | 50+ | 1000+ | 4+ CPU, 4GB | $300-800+ |

### Horizontal Scaling

The API is stateless — scale by adding more instances behind a load balancer:

```bash
# Fly.io
flyctl scale count 3

# Docker Compose
docker compose -f docker-compose.prod.yml up -d --scale api=3
```

**Stateful components to scale separately:**
- PostgreSQL: Use managed (Supabase/RDS) with read replicas
- Redis: Use managed (Upstash) or Redis Cluster
- Celery workers: Scale independently from API

### Database Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM tickets WHERE shopify_domain = 'mystore' AND status = 'pending';

-- Add indexes if missing
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tickets_tenant_status
  ON tickets(shopify_domain, status);

-- Vacuum regularly (add to cron)
VACUUM ANALYZE tickets;
```

### Caching Strategy

```yaml
# Redis cache TTLs
- Order data: 1 hour
- Logistics tracking: 30 minutes
- Policy embeddings: 24 hours
- LLM semantic cache: 1 hour
- Dashboard stats: 5 minutes
```

---

## Appendix: Troubleshooting

### Common Issues

**Problem**: Agent returns `escalate_to_human` for everything
- Check LLM API key is valid
- Check `LLM_DEFAULT_PROVIDER` is correct
- Check API rate limits (DeepSeek: 60 RPM, OpenAI: varies)

**Problem**: WebSocket connections drop frequently
- Check Nginx `proxy_read_timeout` (should be 86400 for WS)
- Check load balancer timeout settings
- Frontend should auto-reconnect with exponential backoff

**Problem**: High database latency
- Check `DB_POOL_SIZE` (increase to 20-40 for production)
- Add connection pool monitoring
- Consider read replicas for dashboard queries

**Problem**: Embedding generation fails
- Check OpenAI API key (embeddings use OpenAI)
- Verify `LLM_EMBEDDING_PROVIDER` and `LLM_EMBEDDING_MODEL`

---

## Support

- **PRD**: `ForgeFlow_AI_PRD_V1.1.md`
- **Code**: `CLAUDE.md` (AI assistant context)
- **API Docs**: `http://localhost:8000/docs` (when running)
- **Phase 5 Checklist**: See Section 8 above
