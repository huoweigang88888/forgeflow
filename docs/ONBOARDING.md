# ForgeFlow AI — Onboarding Guide (Pilot Phase)

> **Version:** 0.1.0-pilot  
> **Last Updated:** 2026-06-25  
> **Intended Audience:** Pilot merchants, internal support team, developers

---

## 目录

1. [What is ForgeFlow AI?](#1-what-is-forgeflow-ai)
2. [Quick Start (5 minutes)](#2-quick-start)
3. [Architecture Overview](#3-architecture-overview)
4. [Shopify App Installation](#4-shopify-app-installation)
5. [Daily Operations](#5-daily-operations)
6. [Troubleshooting](#6-troubleshooting)
7. [FAQ](#7-faq)

---

## 1. What is ForgeFlow AI?

ForgeFlow AI is an **AI-powered after-sales workforce** for Shopify merchants. It automatically:

- **Detects intent** from customer messages (refund, exchange, shipping inquiry, etc.)
- **Looks up orders** in your Shopify store
- **Checks logistics** status and delivery estimates
- **Evaluates policies** and auto-refund thresholds
- **Makes decisions** — auto-refund, auto-exchange, escalate to human
- **Sends notifications** to keep customers informed

The goal: **resolve 80%+ of after-sales tickets without human intervention**, so your support team focuses on complex cases.

### Key Numbers

| Metric | Target |
|--------|--------|
| Auto-resolution rate | 80%+ |
| Average ticket handling time | < 30s |
| Auto-refund threshold | $50 (configurable) |
| Human escalation accuracy | > 95% |

---

## 2. Quick Start (5 minutes)

### Prerequisites

- A Shopify store (any plan)
- Admin access to install apps
- 5 minutes

### Step 1: Install the App

Go to the installation URL provided by your ForgeFlow contact:

```
https://api.forgeflow.ai/api/v1/auth/shopify/install?shop=YOUR-STORE.myshopify.com
```

Replace `YOUR-STORE` with your actual Shopify store domain.

### Step 2: Authorize Permissions

Shopify will show a permission screen. Click **"Install"** to grant:

- `read_orders` — to look up order details
- `write_orders` — to create refunds/exchanges
- `read_customers` — to check customer history
- `read_fulfillments` — to track shipments

### Step 3: Verify Installation

After installation, you'll be redirected to:

```
https://app.forgeflow.ai/dashboard
```

You should see your store name and "Connected" status. 🎉

### Step 4: Send a Test Ticket

From the dashboard, click **"Test Ticket"** and enter:

```
Customer Email: test@yourstore.com
Issue: Where is my order #1001?
```

ForgeFlow will process it and show the result within seconds.

---

## 3. Architecture Overview

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Shopify     │────▶│  ForgeFlow API   │────▶│  LLM         │
│  Webhooks    │     │  (FastAPI)       │     │  (DeepSeek)  │
└─────────────┘     └────────┬─────────┘     └─────────────┘
                             │
                    ┌────────▼─────────┐
                    │  Agent Runtime    │
                    │  (LangGraph)      │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──┐  ┌───────▼───┐  ┌───────▼───┐
     │ Refund     │  │ Exchange  │  │ Escalate  │
     │ (Shopify)  │  │ (Shopify) │  │ (Human)   │
     └────────────┘  └───────────┘  └───────────┘
```

### Agent Pipeline Steps

1. **Intent Detection** — LLM classifies the customer's message
2. **Order Lookup** — Fetches order data from Shopify API
3. **Logistics Check** — Tracks shipment status
4. **Policy Check** — Evaluates store policies and thresholds
5. **Decision** — Recommends action (auto-refund / exchange / escalate)
6. **Execute** — Performs the action via Shopify API

### Technology Stack

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL 15 with pgvector |
| Agent Runtime | LangGraph (state machine) |
| LLM | DeepSeek (primary), OpenAI/Anthropic (fallback) |
| Cache | Redis |
| Monitoring | OpenTelemetry → Grafana |
| Deployment | Fly.io / Railway |

---

## 4. Shopify App Installation

### 4.1 OAuth Flow

ForgeFlow uses Shopify OAuth 2.0:

```
1. Merchant clicks install link
     ↓
2. Redirected to Shopify authorization page
     ↓
3. Merchant approves scopes
     ↓
4. Shopify redirects to ForgeFlow callback
     ↓
5. ForgeFlow exchanges code for permanent access token
     ↓
6. Token is AES-256-GCM encrypted and stored
     ↓
7. Webhooks are registered automatically
```

### 4.2 Required Environment Variables

For the ForgeFlow API server:

```bash
# Shopify OAuth (REQUIRED)
SHOPIFY_CLIENT_ID=your_shopify_api_key
SHOPIFY_CLIENT_SECRET=your_shopify_api_secret
SHOPIFY_SCOPES=read_orders,write_orders,read_customers,read_fulfillments
SHOPIFY_OAUTH_REDIRECT_URI=https://api.forgeflow.ai/api/v1/auth/shopify/callback

# Database (REQUIRED)
DB_URL=postgresql+asyncpg://user:pass@host:5432/forgeflow

# LLM (REQUIRED)
LLM_DEFAULT_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx

# Security (REQUIRED for production)
SECRET_KEY=generate-a-random-64-char-string-here
CORS_ORIGINS=https://app.forgeflow.ai

# Observability (recommended)
SENTRY_DSN=https://xxx@sentry.io/xxx
OTEL_ENDPOINT=grpc://tempo:4317
```

### 4.3 Creating a Shopify App

1. Go to [Shopify Partners](https://partners.shopify.com/)
2. Create a new **Custom App** (not public app for pilot)
3. Under "Configuration" → "Admin API integration":
   - Set the **Admin API access scopes** to the scopes above
   - Set the **Callback URL** to `https://api.forgeflow.ai/api/v1/auth/shopify/callback`
4. Copy the **API key** and **API secret** → set as `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`

---

## 5. Daily Operations

### 5.1 Monitoring the Dashboard

The operations dashboard shows:

- **Active tickets** — currently being processed
- **Pending approval** — tickets requiring human review
- **Resolved today** — auto-resolved tickets
- **Escalated** — tickets that need human attention

### 5.2 Handling Escalated Tickets

When a ticket is escalated:

1. Review the ticket details in the dashboard
2. Read the AI's recommendation and explanation
3. Make a decision:
   - **Approve** — the AI's recommended action is executed
   - **Modify** — change the action (e.g., partial refund instead of full)
   - **Reject** — provide a manual response to the customer

### 5.3 Configuring Auto-Refund Threshold

```bash
# In .env or deployment config:
LLM__AUTO_REFUND_THRESHOLD=50.0   # Orders ≤ $50 auto-refunded
```

Set to `0` to require manual approval for ALL refunds.

### 5.4 Updating Policies

Policy documents control how ForgeFlow makes decisions:

1. Go to **Settings → Policies** in the dashboard
2. Upload or edit policy documents in Markdown
3. Changes take effect within 5 minutes (cache TTL)
4. Example policy:

```markdown
## Refund Policy
- Orders under $50: auto-refund within 24 hours of report
- Orders $50-$200: require photo evidence of damage
- Orders over $200: escalate to manager

## Shipping Policy
- Domestic: 3-7 business days
- International: 7-21 business days
- Delays over 14 days qualify for partial refund
```

---

## 6. Troubleshooting

### Common Issues

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| "Shopify connection failed" | Access token expired or revoked | Re-install the app from Shopify admin |
| Tickets stuck in "processing" | LLM API rate limit or timeout | Check LLM provider status; increase timeout |
| Webhooks not received | Webhook registration failed | Re-install app; verify webhook URL is publicly accessible |
| "Rate limited" error (429) | Too many requests per minute | Wait 60s; default limit is 60 req/min per store |
| CORS errors in browser | CORS_ORIGINS not configured | Set `CORS_ORIGINS=https://app.forgeflow.ai` |

### Health Check

```bash
# Check API health
curl https://api.forgeflow.ai/api/health

# Expected response:
# {"status": "healthy", "version": "0.1.0", "db": "connected", "redis": "connected"}
```

### Logs

All agent decisions are logged with full context. Check:

- **Agent Logs** — each step of the pipeline (intent, lookup, decision, execute)
- **Audit Logs** — all human actions (approvals, modifications)
- **LLM Call Logs** — prompt/response pairs with cost tracking

---

## 7. FAQ

### Q: Does ForgeFlow actually refund money without my approval?
**A:** Only for orders below the auto-refund threshold (default $50). You can set this to $0 to require approval for all refunds. Orders above the threshold are always escalated.

### Q: What happens if the LLM makes a wrong decision?
**A:** Every decision includes an explanation. Escalated tickets are always reviewed by a human. We recommend monitoring the first 100 tickets before enabling auto-execution.

### Q: Can I customize the intent categories?
**A:** Yes. Edit the prompts in **Settings → Prompts** or upload custom policy documents that define how specific scenarios should be handled.

### Q: Is my customer data secure?
**A:** Yes:
- All access tokens are AES-256-GCM encrypted at rest
- Row-Level Security ensures each store's data is isolated at the database level
- GDPR webhooks (data_request, redact, shop/redact) are fully supported
- All API communication is HTTPS-only

### Q: What platforms are supported beyond Shopify?
**A:** WooCommerce and Amazon are on the roadmap for Phase 2. The architecture supports multi-platform from day one.

### Q: How do I get support?
**A:** During the pilot:
- Email: pilot-support@forgeflow.ai
- Slack: #forgeflow-pilot (invite provided during onboarding)
- Emergency: +1-XXX-XXX-XXXX (business hours)
