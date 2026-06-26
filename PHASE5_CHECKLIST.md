# ForgeFlow AI — Phase 5 Launch Checklist

> Last updated: 2026-06-25 | Status: V1 features complete, preparing for pilot

---

## ✅ Phase 0-4: Infrastructure & Core (COMPLETE)

| Area | Status | Notes |
|------|--------|-------|
| Docker (PG 16 + pgvector + Redis 7.2) | ✅ | Running |
| DB Migrations (Alembic) | ✅ | Latest: a1b2c3d4e5f6 |
| API Server (FastAPI, port 8001) | ✅ | DB ✅, Redis ✅ |
| Web Frontend (Next.js 14, port 3000) | ✅ | Compiling (Win perf bottleneck) |
| Agent Graph (LangGraph) | ✅ | 7 nodes + error handling |
| Provider ABC (Shopify/Woo/Amazon/Mock) | ✅ | All 4 providers |
| LLM Abstraction (OpenAI/Anthropic) | ✅ | 3-layer fallback |
| Golden Tests (29/30, 96.7%) | ✅ | 1 known boundary issue |
| API Unit Tests (112/112, 100%) | ✅ | All passing |
| E2E API Tests (6/6, 100%) | ✅ | Ticket lifecycle verified |

---

## ✅ Phase 5: V1 Feature Completion (JUST COMPLETED)

| Feature | File(s) | Status |
|---------|---------|--------|
| **auto_exchange** | `providers/dto.py`, `base.py`, `mock.py`, `shopify/client.py`, `woocommerce/client.py`, `amazon/client.py`, `agent/nodes/execute.py` | ✅ Implemented |
| **Webhook 异步处理** | `api/v1/webhooks.py` → `worker/tasks.py:process_shopify_webhook` | ✅ Celery dispatch |
| **通知重试** | `providers/notifications/dispatcher.py` (tenacity 3-retry + exponential backoff) | ✅ Implemented |
| **Feed 轮询** | `worker/tasks.py:poll_shopify_order_feed` | ✅ Periodic task |
| **Batch Embeddings** | `worker/tasks.py:batch_update_embeddings` (pgvector) | ✅ Implemented |
| **WebSocket Step Push** | `agent/nodes/execute.py:_publish_step_event` → Redis Pub/Sub | ✅ Implemented |
| **NotificationLog Model** | `models/notification.py` (NEW) | ✅ Created |

---

## 🟡 Pre-Launch: Before First Pilot Customer

### Security
- [ ] Enable RLS (Row-Level Security) on all tenant-scoped tables
- [ ] Run `gitleaks` scan on full commit history
- [ ] Review all `.env` files — ensure no secrets committed
- [ ] Rotate all dev API keys before production deployment
- [ ] Add rate limiting to `/api/v1/tickets` (Redis sliding window)
- [ ] Enable CORS whitelist (currently `*` in dev)

### Observability
- [ ] Set up Sentry/Grafana for production error tracking
- [ ] Configure Slack alerts for: SLA breach, provider outage, budget 80%+
- [ ] Set up CloudWatch/Datadog dashboard for: latency p50/p99, error rate, LLM cost
- [ ] Add structured log sampling (1% of success, 100% of errors)

### Data
- [ ] Run GDPR data retention policy audit (`purge_expired_data` task)
- [ ] Verify `customers/data_request` and `customers/redact` webhooks work
- [ ] Set up automated DB backups (daily, 30-day retention)
- [ ] Test DB restore procedure

### LLM
- [ ] Fine-tune intent classification prompt with golden_006 fix
- [ ] Run 100-sample eval suite and verify >95% intent accuracy
- [ ] Set up cost tracking dashboard per tenant
- [ ] Configure Anthropic + OpenAI API keys with usage limits

### Infrastructure
- [ ] Set up CI/CD: GitHub Actions → Fly.io or Railway
- [ ] Configure Celery worker with proper concurrency (not solo pool for prod)
- [ ] Set up Redis persistence (AOF) for production
- [ ] Load test: 100 concurrent tickets, verify <5s p95 latency

### Pilot Customer Readiness
- [ ] Create onboarding doc for first pilot customer
- [ ] Set up Shopify OAuth app listing (draft)
- [ ] Configure test store for end-to-end Shopify integration
- [ ] Write runbook: incident response, rollback procedure

---

## 🔵 Phase 6+ Roadmap (Post-Pilot)

| Priority | Feature | Effort |
|----------|---------|--------|
| 🔴 P0 | Fix golden_006 intent boundary (other→pre_sale) | 1h |
| 🔴 P0 | Real Shopify E2E test (not mock) | 4h |
| 🟡 P1 | LLM fine-tuning pipeline for intent classification | 1w |
| 🟡 P1 | AfterShip/17Track real logistics integration | 3d |
| 🟡 P1 | Multi-language LLM translation (zh, ja, ko, es) | 2d |
| 🟡 P1 | Amazon SP-API full exchange/refund (IAM+STS+SigV4) | 1w |
| 🟢 P2 | Dashboard analytics (ticket volume, resolution rate, cost) | 2w |
| 🟢 P2 | Customer self-service portal (Next.js) | 3w |
| 🟢 P2 | Slack/Teams bot for approval workflow | 1w |
| 🟢 P3 | WooCommerce full integration | 1w |

---

## 📊 Current Quality Baseline

```
API Unit Tests:  ████████████████████ 112/112  100.0%
Golden Tests:    ███████████████████░  29/30   96.7%
E2E API Tests:   ████████████████████   6/6    100.0%
V1 Features:     ████████████████████   6/6    100.0%
Pilot Readiness: ██████████░░░░░░░░░░  40%     Checklist above
```

**综合得分: ~93%** (API 层面 100%，V1 功能补齐 100%)
