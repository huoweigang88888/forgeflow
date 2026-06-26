# ForgeFlow AI — Operations Runbook

> **Version:** 0.1.0-pilot  
> **Last Updated:** 2026-06-25  
> **Audience:** SRE / On-call engineers / Operations team

---

## Incident Severity Levels

| Level | Name | Definition | Response Time |
|-------|------|-----------|---------------|
| P0 | Critical | API is down, ALL tenants affected, refunds/exchanges failing | 15 min |
| P1 | Major | Single tenant affected, or >5% error rate | 30 min |
| P2 | Minor | Non-critical feature degraded (e.g., WebSocket not updating) | 2 hours |
| P3 | Cosmetic | Dashboard UI issue, non-blocking | Next business day |

---

## Alert Reference

### Alert: `forgeflow_api_down`
**Severity:** P0  
**Source:** Health check fails 3 consecutive times (Grafana / UptimeRobot)  
**Impact:** All API endpoints unavailable. No tickets processed.

**Runbook:**
1. Check Fly.io status: `fly status -a forgeflow-api`
2. Check recent deploys: `fly releases -a forgeflow-api`
3. Check logs: `fly logs -a forgeflow-api | tail -100`
4. If OOM: scale memory: `fly scale memory 512 -a forgeflow-api`
5. If crash loop: rollback: `fly deploy --image <previous-image> -a forgeflow-api`
6. If DB connection: check `DB_URL` secret and PostgreSQL status

### Alert: `forgeflow_high_error_rate`
**Severity:** P1  
**Source:** Error rate >5% over 5 minutes (Prometheus / Grafana)  
**Impact:** Some tickets failing. Customers may not get responses.

**Runbook:**
1. Check error breakdown: Grafana → ForgeFlow → Error Rate by Endpoint
2. Check LLM provider status (DeepSeek/OpenAI status pages)
3. Check Shopify API status: https://status.shopify.com/
4. If LLM rate limited: increase fallback retry budget or switch provider
5. If Shopify API errors: automatic retry handles transient; escalate if sustained

### Alert: `forgeflow_rate_limit_triggered`
**Severity:** P2  
**Source:** Rate limit middleware returns 429 responses  
**Impact:** Single tenant / IP being rate-limited. Others unaffected.

**Runbook:**
1. Check which tenant is being rate-limited (logs contain `shop=`)
2. Verify it's legitimate traffic (not a bug in the frontend)
3. If legitimate: increase `RATE_LIMIT_PER_MINUTE` for that tenant
4. If abusive: block the IP at the load balancer level

### Alert: `forgeflow_llm_cost_spike`
**Severity:** P2  
**Source:** Daily LLM cost >$50 threshold (cost_tracker module)  
**Impact:** Budget overrun risk. Service still functional.

**Runbook:**
1. Check Grafana → ForgeFlow → LLM Cost by Model
2. Look for long-context or high-temperature responses
3. Check if any golden tests are running with expensive models
4. Tune `LLM_DEFAULT_MODEL` to a cheaper variant if needed

### Alert: `forgeflow_db_connection_pool_exhausted`
**Severity:** P1  
**Source:** PostgreSQL connection count near `max_connections`  
**Impact:** New requests fail or queue. Existing connections work.

**Runbook:**
1. Check active connections: Grafana → PostgreSQL → Connections
2. If long-running queries: find and kill them
3. If connection leak: restart API instances
4. Increase pool: adjust `DB_POOL_SIZE` and `DB_MAX_OVERFLOW`

---

## Common Operational Procedures

### Deploy a New Version

```bash
# 1. Verify CI passed on the release branch
git log --oneline -5

# 2. Deploy to staging first
fly deploy -a forgeflow-api-staging

# 3. Run smoke tests against staging
pytest tests/ -m "smoke" --base-url https://staging.forgeflow.ai

# 4. If smoke tests pass, deploy to production
fly deploy -a forgeflow-api

# 5. Verify health
curl https://api.forgeflow.ai/api/health

# 6. Monitor for 5 minutes
fly logs -a forgeflow-api | grep -E "ERROR|CRITICAL"
```

### Rollback

```bash
# List recent releases
fly releases -a forgeflow-api

# Rollback to the previous stable version
fly deploy --image registry.fly.io/forgeflow-api:v<N-1> -a forgeflow-api

# Verify
curl https://api.forgeflow.ai/api/health
```

### Restart API Instances

```bash
# Graceful restart (one at a time)
fly machines restart -a forgeflow-api --force

# Check all machines are running
fly machines list -a forgeflow-api
```

### Run Database Migrations

```bash
# Connect to the API instance
fly ssh console -a forgeflow-api

# Run Alembic migrations
cd /app
alembic upgrade head

# Verify migration version
alembic current
```

### Check Database Status

```bash
fly pg connect -a forgeflow-db

# Check connections
SELECT count(*) FROM pg_stat_activity;

# Check RLS is enabled on all tables
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
  AND rowsecurity = true;
```

### Rotate Secrets

```bash
# 1. Generate new secret
openssl rand -hex 32

# 2. Update in Fly.io (triggers rolling restart)
fly secrets set SECRET_KEY=<new-secret> -a forgeflow-api

# 3. Verify app comes back healthy
fly logs -a forgeflow-api | grep "forgeflow_api_starting"
```

---

## Data Recovery Procedures

### Restore from Backup

Fly.io PostgreSQL includes point-in-time recovery:

```bash
# 1. Create a new database from backup
fly pg create --name forgeflow-db-restore --fork-from forgeflow-db

# 2. Attach to the app
fly pg attach forgeflow-db-restore -a forgeflow-api

# 3. Point app to the restored database (or copy data back)
fly secrets set DB_URL=<new-db-url> -a forgeflow-api
```

### GDPR Data Request

When a customer requests their data (GDPR `/api/v1/gdpr/customers/data_request`):

1. The webhook handler logs the request to `audit_logs`
2. Automatically queries all tables for the customer's data
3. Returns a JSON dump within 30 days (GDPR requirement)

Manual override:
```bash
# List all data for a customer
fly pg connect -a forgeflow-db
SELECT * FROM tickets WHERE customer_email = 'user@example.com';
SELECT * FROM orders WHERE id IN (SELECT order_id FROM tickets WHERE customer_email = 'user@example.com');
```

### GDPR Data Redaction

When a customer requests deletion (GDPR `/api/v1/gdpr/customers/redact`):

1. The webhook handler redacts PII (email, name, address) from all tables
2. Order/ticket metadata is preserved for analytics (anonymized)
3. The operation is logged to `audit_logs`

When a shop uninstalls (`/api/v1/gdpr/shop/redact`):
1. All shop data is marked for deletion
2. A 48-hour grace period allows for accidental uninstalls
3. After 48 hours, data is permanently deleted

---

## Performance Baseline

### Expected Metrics (from load testing)

| Metric | Target | P50 | P95 | P99 |
|--------|--------|-----|-----|-----|
| API latency (health) | <10ms | 5ms | 10ms | 20ms |
| API latency (ticket create) | <500ms | 200ms | 400ms | 800ms |
| Agent pipeline (full) | <30s | 8s | 20s | 30s |
| LLM call latency | <10s | 2s | 6s | 10s |
| Shopify API call | <5s | 500ms | 2s | 5s |
| DB query | <100ms | 20ms | 50ms | 100ms |

### Resource Allocation

| Resource | Development | Staging | Production |
|----------|------------|---------|------------|
| API instances | 1 | 1 | 2 |
| CPU per instance | 0.5 | 0.5 | 1 |
| Memory per instance | 256MB | 512MB | 1GB |
| PostgreSQL | 1 shared | 1 shared | 2 dedicated (primary + replica) |
| Redis | 1 shared | 1 shared | 1 dedicated |

---

## Contact & Escalation

### Pilot Phase

| Role | Name | Contact |
|------|------|---------|
| Primary On-call | [name] | [phone] / [email] |
| Engineering Lead | [name] | [phone] / [email] |
| Shopify Partner Support | — | https://help.shopify.com/ |

### Escalation Path

```
P3 → File GitHub issue
P2 → Notify #forgeflow-ops on Slack
P1 → Page on-call engineer (PagerDuty)
P0 → Page on-call + engineering lead + notify all-hands
```

---

## Appendix: Useful Queries

### Top 10 tickets by processing time

```sql
SELECT id, intent, processing_duration_ms, created_at
FROM tickets
WHERE created_at > now() - interval '24 hours'
ORDER BY processing_duration_ms DESC
LIMIT 10;
```

### Daily auto-resolution rate

```sql
SELECT 
    date_trunc('day', created_at) as day,
    count(*) as total,
    count(*) FILTER (WHERE status = 'resolved') as auto_resolved,
    count(*) FILTER (WHERE status = 'escalated') as escalated,
    round(100.0 * count(*) FILTER (WHERE status = 'resolved') / count(*), 1) as auto_rate_pct
FROM tickets
WHERE created_at > now() - interval '7 days'
GROUP BY day
ORDER BY day DESC;
```

### LLM cost by day

```sql
SELECT 
    date_trunc('day', created_at) as day,
    provider,
    model,
    count(*) as calls,
    sum(cost_usd) as total_cost,
    avg(duration_ms) as avg_latency_ms
FROM llm_calls
WHERE created_at > now() - interval '7 days'
GROUP BY day, provider, model
ORDER BY day DESC, total_cost DESC;
```

### Active Shopify stores

```sql
SELECT shop_domain, installed_at, scopes
FROM shopify_sessions
WHERE is_active = true 
  AND uninstalled_at IS NULL
ORDER BY installed_at DESC;
```
