# ForgeFlow AI — V2 Planning

> Status: Draft for discussion | Target: Q3 2026

## Executive Summary

V1 (current Phase 0–5) delivers a single-platform (Shopify), 5-scenario AI after-sales
agent with ~60% auto-resolution rate. V2 expands to **multi-platform**, **8 scenarios**,
**75% auto-resolution**, and **multi-language support** — making ForgeFlow viable for
mid-market merchants across Shopify, WooCommerce, and Amazon.

---

## 1. V2 Goals & Success Metrics

| Metric | V1 Target | V2 Target |
|--------|-----------|-----------|
| Auto-resolution rate | 60% | **75%** |
| Supported platforms | 1 (Shopify) | **3 (Shopify + WooCommerce + Amazon)** |
| After-sales scenarios | 5 | **8** |
| Supported languages | English only | **English + Chinese + Spanish** |
| P95 Agent latency | < 5s | **< 4s** |
| P95 API latency | < 500ms | **< 300ms** |
| Concurrent users | 50 | **200** |
| Knowledge base size | ~100 docs | **1,000+ docs with hybrid search** |
| Human approval rate | ~15% | **< 8%** |

---

## 2. Multi-Platform Architecture

### 2.1 Platform Provider Abstraction (already designed in V1)

The `PlatformProvider` ABC in `providers/base.py` defines:
- `OrderProvider` — order lookup, refund, fulfillment status
- `LogisticsProvider` — tracking, carrier status
- `NotificationProvider` — email/SMS templates

V2 implements concrete providers for each platform:

```
src/forgeflow/providers/
├── base.py              # ABCs (exists)
├── registry.py          # ProviderRegistry (exists)
├── dto.py               # Platform DTOs (exists)
├── mock.py              # Mock provider (exists)
├── shopify/             # Shopify (exists — V1)
│   ├── __init__.py
│   └── client.py
├── woocommerce/         # WooCommerce (V2 NEW)
│   ├── __init__.py
│   ├── client.py        # WooCommerce REST API v3
│   ├── order_provider.py
│   └── logistics_provider.py
└── amazon/              # Amazon (V2 NEW)
    ├── __init__.py
    ├── client.py        # Amazon SP-API
    ├── order_provider.py
    └── logistics_provider.py
```

### 2.2 Platform-Specific Considerations

| Capability | Shopify | WooCommerce | Amazon |
|-----------|---------|-------------|--------|
| Order lookup | REST Admin API | REST API v3 | SP-API (Orders) |
| Refund | REST + GraphQL | REST API | SP-API (Finances) |
| Fulfillment status | Native | Plugin-dependent | FBA / MFN |
| Tracking | CarrierService | Plugin-dependent | SP-API (Fulfillment) |
| Auth | OAuth 2.0 | OAuth 1.0a / 2.0 | IAM + STS |
| Webhook | Native | Custom / WP | SQS / SNS |

### 2.3 Unified Data Model

Platform-specific order/funding data is normalized at the DTO layer into
platform-agnostic `OrderDTO` and `LogisticsDTO` objects. The agent pipeline
never sees platform-specific fields.

---

## 3. Extended Scenario Coverage (5 → 8)

### V1 Scenarios (keep & improve)
1. **Shipping Delay** — auto-refund below threshold, escalate above
2. **Refund Request** — check fulfillment, auto-refund if unfulfilled
3. **Wrong Item** — auto-exchange + return label
4. **Damaged Item** — escalate with photo evidence
5. **Exchange Request** — auto-exchange with inventory check

### V2 NEW Scenarios
6. **Partial Refund** — calculate proportional refund for partial returns
7. **Subscription Cancellation** — detect subscription orders, cancel recurring
8. **Pre-sale Inquiry** — answer product questions from knowledge base (no order ID)

### Scenario Routing

```
Ticket → Intent Detection (8-way classifier)
       ├─ shipping_delay     → logistics check → auto_refund / escalate
       ├─ refund_request     → fulfillment check → auto_refund / escalate
       ├─ wrong_item         → auto_exchange + return
       ├─ damaged_item       → escalate + photo request
       ├─ exchange_request   → auto_exchange + inventory
       ├─ partial_refund     → calculate amount → auto_partial_refund
       ├─ subscription_cancel→ cancel recurring → confirmation
       └─ pre_sale_inquiry   → KB search → auto_reply
```

---

## 4. Multi-Language Support

### 4.1 Language Detection
- Auto-detect from customer message (fastText or simple langdetect)
- Store `issue_language` in AgentState (field already exists)

### 4.2 Prompt Localization
- V1: English-only prompts
- V2: Prompt registry supports `prompt_<node>_<lang>` templates
- Fallback to English if translation unavailable

### 4.3 Language-Specific Models
- Chinese tickets → Qwen (lower cost, better Chinese understanding)
- English tickets → OpenAI/Anthropic (default)
- Spanish tickets → OpenAI (multilingual GPT-4o)

### 4.4 Supported Languages Phase 1
| Language | Intent | Decision | Customer Reply |
|----------|--------|----------|----------------|
| English (en) | ✅ | ✅ | ✅ |
| Chinese (zh) | ✅ | ✅ | ✅ |
| Spanish (es) | ✅ | ✅ | ⚠️ (English reply) |

---

## 5. Knowledge Base Enhancements

### 5.1 Hybrid Search (Phase 3 → V2 Production)
- **pgvector cosine similarity** (implemented)
- **Full-text keyword search** with `forgeflow_en` config
- **Hybrid scoring**: 70% vector + 30% keyword (adjustable)
- **Multi-language embedding**: use multilingual model for zh/es docs

### 5.2 Policy Lifecycle
- Version history (already modeled: `version` column)
- Draft/published states
- Bulk upload via CSV/JSON
- Auto-expiration for time-sensitive policies

### 5.3 Policy Impact Analysis
- Track which policies are matched most frequently
- Measure resolution rate before/after policy changes
- Alert on stale or never-matched policies

---

## 6. LLM Provider Strategy

### 6.1 Provider Matrix (V2)
| Provider | Use Case | Models |
|----------|----------|--------|
| **OpenAI** | Default, high-quality decisions | gpt-4o-mini, gpt-4o |
| **Anthropic** | Complex reasoning, safety-critical | claude-haiku-4-5, claude-sonnet-4-6 |
| **DeepSeek** | Low-cost, Chinese-language | deepseek-chat, deepseek-reasoner |
| **Qwen** | Chinese data locality, DashScope | qwen-turbo, qwen-plus, qwen-max |

### 6.2 Routing Strategy (V2)
```
cheap_model (95% of traffic):
  English → gpt-4o-mini / claude-haiku-4-5
  Chinese → deepseek-chat / qwen-turbo

complex_model (5% of traffic):
  English → gpt-4o / claude-sonnet-4-6
  Chinese → deepseek-reasoner / qwen-max

cost_cap: $0.01/ticket average
```

### 6.3 Fallback Chain
```
Primary → Secondary → Cross-Provider → Safe Static Fallback
  ↓          ↓              ↓                  ↓
OpenAI    Anthropic    DeepSeek/Qwen     Hard-coded values
```

---

## 7. Analytics & Observability

### 7.1 V2 Dashboard
- Resolution rate by scenario, platform, language
- Cost per ticket ($ / ticket, trending)
- LLM call latency distribution (P50 / P95 / P99)
- Intent distribution pie chart
- Human approval queue metrics

### 7.2 Alerting (additions)
- Intent drift detection (>20% distribution shift → alert)
- LLM cost anomaly (>2x baseline → alert)
- Platform API error rate spike (>5% → alert)
- Knowledge base staleness (>30 days no update → warn)

### 7.3 A/B Prompt Testing
- `prompt_versions` table exists — activate it
- Route 5% of traffic to alternate prompt version
- Compare: resolution rate, confidence, latency
- Auto-promote winning prompt

---

## 8. Reliability & Scale

### 8.1 Infrastructure
| Component | V1 | V2 |
|-----------|----|----|
| App server | 1× shared-cpu-1x | 2× dedicated-cpu-2x |
| PostgreSQL | Single | Primary + read replica |
| Redis | Single | Sentinel (HA) |
| Queue | — | Celery + Redis broker |
| CDN | — | CloudFront (dashboard assets) |

### 8.2 Database
- Read replica for dashboard queries (reduce load on primary)
- Connection pooling: increase pool_size to 20
- Query optimization: add indexes on (shopify_domain, category, created_at)
- Archive tickets > 90 days to cold storage

### 8.3 Resilience
- Circuit breaker for platform APIs (5 failures → 30s cooldown)
- Request rate limiting per tenant (100 req/min)
- Graceful degradation: if KB search fails, use policy cache

---

## 9. Migration Path (V1 → V2)

### Phase 1: Platform Expansion (Weeks 1–4)
- [ ] Implement WooCommerce provider
- [ ] Multi-platform routing in API layer
- [ ] Platform-aware dashboard (show platform column)

### Phase 2: Scenario Expansion (Weeks 5–8)
- [ ] Add partial_refund, subscription_cancel, pre_sale_inquiry intents
- [ ] Update intent detection prompt (5-way → 8-way)
- [ ] Add new decision rules for new scenarios
- [ ] Golden test cases for new scenarios

### Phase 3: Language & Knowledge Base (Weeks 9–12)
- [ ] Language detection + prompt localization
- [ ] Activate hybrid search in production
- [ ] Policy lifecycle management UI
- [ ] Multi-language embedding

### Phase 4: Scale & Analytics (Weeks 13–16)
- [ ] Infrastructure upgrade (replicas, queue)
- [ ] Analytics dashboard
- [ ] A/B prompt testing
- [ ] Circuit breakers + rate limiting

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| WooCommerce plugin fragmentation | Logistics status unavailable on some stores | Dynamic capability detection per store |
| Amazon SP-API complexity | Long integration time | Start read-only (order lookup only), add write later |
| Multi-language quality | Bad decisions for non-English | Language-specific golden tests, human review for non-English |
| LLM cost at scale | >$0.01/ticket target | Aggressive model routing, cache frequent queries |
| Platform API rate limits | Ticket processing delays | Per-platform rate limiter, backoff queue |

---

## 11. Open Questions

1. **Amazon SP-API**: Full IAM+STS auth or start with Marketplace Web Service (MWS)?
2. **Chinese market**: Deploy separate instance in Alibaba Cloud for data locality?
3. **Pricing model V2**: Per-ticket pricing vs. monthly subscription vs. usage-based?
4. **White-label**: Allow agencies to rebrand ForgeFlow for their merchant clients?
5. **Mobile app**: Customer-facing mobile app for ticket status tracking?

---

*Last updated: 2026-06-20 | Discussion with stakeholders before finalizing.*
