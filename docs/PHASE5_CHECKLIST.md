# ForgeFlow AI — Phase 5 Pilot Launch Checklist

> **Phase**: 5 (Week 12-13)  
> **Milestone**: 正式发布 (Official Launch)  
> **Target Date**: End of Week 13  
> **PRD Reference**: Section 10.1

---

## Week 12: Deployment & Pilot Prep

### Infrastructure

- [ ] Production environment provisioned (Fly.io / VM)
- [ ] `.env.production` configured with real secrets
- [ ] PostgreSQL database created and migrated
- [ ] Redis instance running and reachable
- [ ] SSL certificates installed and valid
- [ ] Nginx reverse proxy configured
- [ ] Docker images built and pushed to registry
- [ ] Health check endpoint verified (`GET /api/health`)
- [ ] WebSocket endpoint verified (`/ws/v1/tickets/{id}`)

### Monitoring

- [ ] Prometheus scraping API metrics
- [ ] Grafana dashboard accessible
- [ ] Alert rules configured (API down, error rate, cost spike)
- [ ] Sentry receiving errors
- [ ] LLM cost tracking operational
- [ ] Database backup schedule configured
- [ ] Uptime monitoring configured (e.g., Better Uptime)

### Data & Configuration

- [ ] Default prompt versions seeded (v1.0.0)
- [ ] Default knowledge base policies seeded
- [ ] Per-tenant budget limits set
- [ ] Rate limiting configured
- [ ] Shopify OAuth app approved and keys set

### Performance Validation

- [ ] All 30 Golden Test Cases pass
- [ ] Intent detection accuracy ≥ 92%
- [ ] API P95 latency ≤ 500ms
- [ ] Agent end-to-end ≤ 5 seconds
- [ ] Load test: 50 concurrent users, no 5xx errors
- [ ] LLM JSON parse success rate ≥ 99%

---

## Week 13: Pilot Launch & Tuning

### Customer Onboarding (3 pilot customers)

- [ ] **Pilot Customer #1** onboarded
  - [ ] Tenant setup complete
  - [ ] Knowledge base seeded with their policies
  - [ ] First ticket processed end-to-end
  - [ ] Feedback collected

- [ ] **Pilot Customer #2** onboarded
  - [ ] Tenant setup complete
  - [ ] Knowledge base seeded with their policies
  - [ ] First ticket processed end-to-end
  - [ ] Feedback collected

- [ ] **Pilot Customer #3** onboarded
  - [ ] Tenant setup complete
  - [ ] Knowledge base seeded with their policies
  - [ ] First ticket processed end-to-end
  - [ ] Feedback collected

### Prompt Fine-Tuning

- [ ] Review pilot intent classification accuracy
- [ ] Review pilot decision accuracy
- [ ] Analyze false positives (auto-refund when shouldn't)
- [ ] Analyze false negatives (escalate when could auto-resolve)
- [ ] Tune prompt templates based on real data
- [ ] Register improved prompt versions (v1.1.0)
- [ ] Run prompt regression tests on new versions
- [ ] A/B test new prompts against baseline

### Go-Live Verification

- [ ] Auto-resolve rate ≥ 60% (measured across all pilots)
- [ ] Approval rate ≤ 40%
- [ ] Average processing time ≤ 5 seconds
- [ ] Customer satisfaction feedback positive
- [ ] No critical bugs found in 48 hours
- [ ] LLM cost per ticket ≤ $0.005 (weighted average)
- [ ] Data pipeline working (ticket → agent → DB → dashboard)
- [ ] Real-time WebSocket updates working for pilot tenants

### Documentation

- [ ] Deployment guide complete and tested
- [ ] Operations runbook delivered
- [ ] API docs accessible at `/docs`
- [ ] Tenant onboarding script documented
- [ ] Rollback procedures documented and tested

---

## Release Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| **Platform Lead** | _______ | _______ | ___ |
| **ML Engineer** | _______ | _______ | ___ |
| **Backend Developer** | _______ | _______ | ___ |
| **Frontend Developer** | _______ | _______ | ___ |
| **Product Owner** | _______ | _______ | ___ |

---

## Success Metrics (to measure 30 days post-launch)

| Metric | V1 Target | Actual | Status |
|--------|-----------|--------|--------|
| Auto-resolve rate | ≥ 60% | ___% | |
| Average processing time | ≤ 5s | ___s | |
| LLM cost per ticket | ≤ $0.005 | $___ | |
| Intent accuracy | ≥ 92% | ___% | |
| JSON parse success | ≥ 99% | ___% | |
| Pilot customer satisfaction | ≥ 4.5/5 | ___ | |
| Hours saved per store/week | ≥ 10 | ___ | |
| System uptime | ≥ 99.5% | ___% | |

---

> **Phase 5 Complete** ✅ → Proceed to V2 Planning (Multi-platform, 5-8 scenarios, 75% resolve rate)
