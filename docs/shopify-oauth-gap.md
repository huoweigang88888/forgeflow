# Shopify OAuth & Webhook Gap Analysis

**Date:** 2026-06-20
**Status:** Phase 0 — documented, to be implemented in Phase 1

---

## What Exists

### Shopify REST Client (`apps/api/src/forgeflow/providers/shopify/client.py`)

A fully functional Shopify Admin REST API client (~800 lines) implementing the `PlatformProvider` ABC:

| Method | Description | Shopify API Endpoint |
|--------|-------------|---------------------|
| `get_order(order_id)` | Fetch order details + line items + customer | `GET /admin/api/2024-01/orders/{id}.json` |
| `get_customer_orders(customer_id)` | Fetch all orders by customer | `GET /admin/api/2024-01/customers/{id}/orders.json` |
| `create_refund(order_id, line_items, ...)` | Create a refund | `POST /admin/api/2024-01/orders/{id}/refunds.json` |
| `get_fulfillment_status(order_id)` | Get fulfillment/shipping info | `GET /admin/api/2024-01/orders/{id}/fulfillments.json` |
| `track_shipment(tracking_number, ...)` | Track a shipment via fulfillment events | (wraps fulfillment endpoints) |
| `get_customer_history(customer_id)` | Get customer lifetime order history | (wraps order listing) |

**Features:**
- httpx async client with configurable timeouts
- tenacity exponential backoff retry (3 attempts)
- Proper error handling and logging
- Constructs `OrderInfo`, `RefundResult`, `TrackingInfo` DTOs

**Limitations:**
- Constructor requires a raw `access_token` — token must be obtained externally
- No automatic token refresh
- `send_email()` and `send_sms()` are no-ops (log + return True)

---

## What's Missing

### 1. OAuth Install Flow

The Shopify App installation process requires a server-side OAuth flow:

```
Merchant clicks "Install" → Redirect to Shopify OAuth → 
User approves scopes → Shopify redirects to callback →
App exchanges code for access_token → Store access_token → Redirect to app
```

**Missing endpoints:**
- `GET /api/v1/auth/shopify/install` — constructs Shopify OAuth URL with required params:
  - `client_id` (API key)
  - `scope` (read_orders, write_orders, read_fulfillments, write_fulfillments, read_customers)
  - `redirect_uri` (callback URL)
  - `state` (anti-CSRF nonce, stored in Redis with TTL)
- `GET /api/v1/auth/shopify/callback` — handles OAuth callback:
  - Validates HMAC signature
  - Verifies `state` matches stored nonce
  - Exchanges `code` for permanent `access_token` via `POST /admin/oauth/access_token`
  - Stores encrypted token in DB (see Token Storage below)

### 2. Token Storage

Access tokens must be stored per-tenant (per-Shopify-store).

**Schema addition needed:**
```sql
-- Add to tenants table or create a new table
ALTER TABLE tenants ADD COLUMN shopify_access_token TEXT;  -- encrypted
ALTER TABLE tenants ADD COLUMN shopify_domain VARCHAR(255);
ALTER TABLE tenants ADD COLUMN shopify_installed_at TIMESTAMPTZ;
ALTER TABLE tenants ADD COLUMN shopify_scopes TEXT[];
```

Tokens must be encrypted at rest (use the existing `AES_KEY` from settings).

### 3. Webhook Registration & Handling

Shopify requires webhooks for real-time event processing.

**Missing webhook endpoints:**
- `POST /api/v1/webhooks/shopify/orders/create` — new order placed
- `POST /api/v1/webhooks/shopify/orders/updated` — order status changed
- `POST /api/v1/webhooks/shopify/fulfillments/create` — item shipped
- `POST /api/v1/webhooks/shopify/fulfillments/update` — tracking updated

**Required: HMAC verification middleware**
Every Shopify webhook request must have its HMAC-SHA256 signature verified against the app's client secret.

**Webhook registration:**
After OAuth install, register webhook topics via Shopify REST API (`POST /admin/api/2024-01/webhooks.json`).

### 4. GDPR Mandatory Endpoints

Required for Shopify App Store listing:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/gdpr/customers/data_request` | Return all data for a customer (order_id → orders, tickets, agent_logs) |
| `POST /api/v1/gdpr/customers/redact` | Delete all PII for a customer |
| `POST /api/v1/gdpr/shop/redact` | Delete all data for a shop (when merchant uninstalls) |

Note: A `POST /api/v1/gdpr` endpoint already exists in `apps/api/src/forgeflow/api/v1/gdpr.py` — verify it handles all three required webhook types.

### 5. Session/Tenant Middleware Integration

The existing `TenantMiddleware` extracts `X-Shopify-Shop-Domain` from headers. The OAuth flow must:
1. After successful OAuth callback, set shop domain in session/JWT
2. The `TenantMiddleware` then loads the correct `ShopifyProvider(token_for_this_shop)` from the `ProviderRegistry`

### 6. App Proxy (Optional but Recommended)

Shopify App Proxy enables embedding the ForgeFlow dashboard inside the Shopify Admin. Requires:
- Proxy route configuration in Shopify App settings
- HMAC signature verification on proxy requests
- Liquid template for admin UI extension (if embedding in Shopify Admin)

---

## Phase 1 Implementation Plan (Estimate: 3-4 days)

| Task | Days | Dependencies |
|------|------|--------------|
| OAuth install + callback endpoints | 1d | settings (SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET) |
| Token storage (DB migration + encryption) | 0.5d | OAuth flow |
| Webhook HMAC verification middleware | 0.5d | — |
| Webhook endpoints (4 topics) | 1d | HMAC middleware, token storage |
| GDPR endpoint audit + fixes | 0.5d | Token storage |
| Webhook registration on install | 0.5d | Webhook endpoints |

---

## Design Notes

### ProviderRegistry Per-Tenant Pattern

The existing `ProviderRegistry` pattern already supports named providers:

```python
# Current usage (single global instance)
provider = ProviderRegistry.get("shopify", access_token=token)

# Phase 1: per-tenant instances
ProviderRegistry.get_or_create(
    platform="shopify",
    tenant_id=tenant_id,
    access_token=token_for_this_shop,
)
```

The `ProviderRegistry` should cache one `ShopifyProvider` instance per `(platform, tenant_id)` pair, keyed on `shopify_domain`.

### Environment Variables Needed

```env
SHOPIFY_CLIENT_ID=          # From Shopify Partner Dashboard
SHOPIFY_CLIENT_SECRET=      # From Shopify Partner Dashboard
SHOPIFY_APP_URL=            # https://app.forgeflow.ai
SHOPIFY_SCOPES=             # read_orders,write_orders,read_fulfillments,write_fulfillments,read_customers
```
