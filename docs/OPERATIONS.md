# ForgeFlow AI — Operations Runbook (Phase 5)

> On-call reference for production incidents. Keep this open during pilot.

## Service Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Nginx   │───→│   API    │───→│  Worker  │───→│  Redis   │
│  :80/443 │    │  :8000   │    │ (Celery) │    │  :6379   │
└──────────┘    └────┬─────┘    └──────────┘    └──────────┘
                     │
              ┌──────▼─────┐
              │ PostgreSQL │
              │   :5432    │
              └────────────┘
```

## Health Check URLs

| Service | Endpoint | Expected |
|---------|----------|----------|
| API | `GET /api/health` | `{"status": "healthy"}` |
| Metrics | `GET /metrics` | Prometheus metrics |
| API Docs | `GET /docs` | Swagger UI |

## Common Incidents

### 1. API is down / not responding

**Symptoms**: Health check fails, 502 from Nginx
**Check**:
```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Check API logs
docker compose -f docker-compose.prod.yml logs --tail=100 api

# Check resource usage
docker stats
```

**Common causes**:
- Database unreachable → check `DB_URL`, network
- Redis unreachable → check `REDIS_URL`, Redis memory
- Out of memory → increase VM memory or add swap
- Port conflict → check port 8000 availability

**Fix**:
```bash
docker compose -f docker-compose.prod.yml restart api
```

### 2. Agent returns only "escalate_to_human"

**Symptoms**: All tickets go to human review, auto-resolve rate drops to 0
**Check**:
```bash
# Check LLM API status
curl -X POST https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"Hello"}]}'

# Check LLM cost (spike may indicate retry loops)
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a $REDIS_PASSWORD HGETALL "cost:tenant:*"
```

**Common causes**:
- LLM API key expired or rate-limited
- LLM returning non-JSON responses → fallback layer triggers
- Prompt template corrupted → rollback to v1.0.0

**Fix**:
```bash
# Rollback prompts to known-good version
curl -X POST http://localhost:8000/api/v1/prompts/rollback \
  -H "Content-Type: application/json" \
  -d '{"prompt_name": "intent_detection", "to_version": "v1.0.0"}'

curl -X POST http://localhost:8000/api/v1/prompts/rollback \
  -H "Content-Type: application/json" \
  -d '{"prompt_name": "decision", "to_version": "v1.0.0"}'
```

### 3. WebSocket connections failing

**Symptoms**: Frontend shows "Connection lost", falls back to polling
**Check**:
```bash
# Check Nginx WebSocket config
docker compose -f docker-compose.prod.yml exec nginx nginx -t

# Check Redis Pub/Sub
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a $REDIS_PASSWORD PUBSUB CHANNELS
```

**Fix**:
- Verify Nginx has `proxy_read_timeout 86400s` for `/ws/` location
- Check load balancer doesn't strip `Upgrade` header
- Restart Nginx: `docker compose -f docker-compose.prod.yml restart nginx`

### 4. LLM cost spike

**Symptoms**: Daily cost > $50, budget alerts firing
**Check**:
```bash
# Check per-tenant cost
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a $REDIS_PASSWORD HGETALL "cost:tenant:*:$(date +%Y-%m)"

# Check which model is consuming
# Query llm_calls table for recent high-token calls
```

**Fix**:
- Ensure semantic cache is enabled
- Check if complex decisions are routing to gpt-4o too frequently
- Temporarily lower `LLM_AUTO_REFUND_THRESHOLD` to let more cases hit hard rules
- Set per-tenant budget caps

### 5. Database connection pool exhausted

**Symptoms**: API returns 500 errors, logs show "queue pool exhausted"
**Check**:
```bash
# Check active connections
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U forgeflow -c "SELECT count(*) FROM pg_stat_activity;"

# Check pool config
grep POOL_SIZE .env.production
```

**Fix**:
- Increase `DB_POOL_SIZE` (default 5 → 20) and `DB_MAX_OVERFLOW` (default 10 → 40)
- Check for connection leaks (ensure sessions are properly closed)
- Restart API: `docker compose -f docker-compose.prod.yml restart api`

## Daily Operations

### Morning Checklist

```bash
# 1. Check all services are running
docker compose -f docker-compose.prod.yml ps

# 2. Check yesterday's metrics
# - Auto-resolve rate (target: ≥ 60%)
# - Average processing time (target: ≤ 5s)
# - Error rate (target: ≤ 1%)

# 3. Check LLM cost (yesterday)
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a $REDIS_PASSWORD HGETALL "cost:tenant:*:$(date -d yesterday +%Y-%m)"

# 4. Check for new errors in Sentry

# 5. Verify database backups ran
ls -la /backups/forgeflow_$(date +%Y%m%d)*.sql
```

### Weekly Tasks

- [ ] Review prompt performance metrics (accuracy, latency)
- [ ] Analyze intent distribution for drift (KL divergence check)
- [ ] Review approval rate trends (should be decreasing as Agent improves)
- [ ] Check database size and disk usage
- [ ] Rotate logs if needed
- [ ] Apply security patches (`docker compose pull`)

## Backup & Recovery

### Database Backup
```bash
# Manual backup
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U forgeflow -Fc forgeflow > forgeflow_$(date +%Y%m%d_%H%M%S).dump

# Verify backup
pg_restore --list forgeflow_20260619_120000.dump | head
```

### Redis Backup
```bash
# Redis appends to AOF file automatically (configured in docker-compose)
# Manual trigger
docker compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD BGSAVE
```

### Full System Restore
```bash
# 1. Stop services
docker compose -f docker-compose.prod.yml down

# 2. Restore database
docker compose -f docker-compose.prod.yml up -d postgres
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U forgeflow -d forgeflow --clean < forgeflow_backup.dump

# 3. Start all services
docker compose -f docker-compose.prod.yml up -d

# 4. Verify
curl http://localhost:8000/api/health
```

## Alert Response Matrix

| Alert | Response Time | Action |
|-------|--------------|--------|
| **API Down** | < 5 min | Restart API; escalate if > 10 min |
| **High Error Rate** | < 15 min | Check logs; rollback if recent deploy |
| **LLM JSON Parse Failure** | < 15 min | Rollback prompt; switch LLM provider |
| **Agent Fallback > 10%** | < 30 min | Investigate LLM quality; check prompts |
| **DB Pool > 85%** | < 30 min | Increase pool size; restart |
| **LLM Cost Spike** | < 1 hour | Enable budget cap; check for loops |
| **Intent Drift** | < 4 hours | Review recent tickets; update baseline |

## Escalation Path

1. **L1: Developer on-call** — Restart services, check logs, rollback prompts
2. **L2: ML Engineer** — LLM issues, prompt degradation, model switching
3. **L3: Platform Lead** — Infrastructure issues, database, deployment

## Emergency Contacts (Fill In)

| Role | Name | Phone | Notes |
|------|------|-------|-------|
| Platform Lead | _______ | _______ | Infrastructure, deployment |
| ML Engineer | _______ | _______ | LLM, prompts, agent |
| Backend Developer | _______ | _______ | API, database |
| Frontend Developer | _______ | _______ | Web dashboard |
| Customer Success | _______ | _______ | Pilot customer communication |
