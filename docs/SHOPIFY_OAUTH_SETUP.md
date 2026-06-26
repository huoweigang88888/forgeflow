# Shopify OAuth App — Configuration Guide

> **Version:** 0.1.0-pilot  
> **Last Updated:** 2026-06-25  
> **Audience:** Developers setting up ForgeFlow for a pilot merchant

---

## Overview

This guide walks through creating and configuring a Shopify **Custom App** for ForgeFlow AI. Custom apps are the simplest setup for pilot/testing — they don't require Shopify's public app review process.

> **Note for production:** After the pilot phase, ForgeFlow will transition to a **Public App** listed on the Shopify App Store. The OAuth flow is identical — only the app creation process differs.

---

## Step-by-Step: Create a Custom App

### 1. Create a Shopify Partner Account

1. Go to [https://partners.shopify.com/](https://partners.shopify.com/)
2. Click **"Join now"** and fill in your details
3. Verify your email

### 2. Create a Development Store (or use an existing one)

For testing, create a development store:

1. From your Partner dashboard, click **"Stores"** → **"Add store"**
2. Choose **"Development store"**
3. Fill in store name and address
4. Click **"Save"**

> Development stores are free and have all features enabled. They can't process real payments but are perfect for testing.

### 3. Create the Custom App

1. From your Partner dashboard, go to **"Apps"**
2. Click **"Create app"**
3. Choose **"Custom app"** (for a single store)
4. Name it **"ForgeFlow AI"**
5. Click **"Create app"**

### 4. Configure Admin API Scopes

Under **"Configuration"** → **"Admin API integration"**:

Click **"Configure"** and add these scopes:

| Scope | Why ForgeFlow Needs It |
|-------|----------------------|
| `read_orders` | Look up order details when a customer inquires |
| `write_orders` | Create refunds and exchanges |
| `read_customers` | Check customer history for fraud prevention |
| `read_fulfillments` | Track shipment status and delivery estimates |

> **Important:** These are **read/write** scopes. Make sure to grant both read AND write for `orders` — write is required for refunds and exchanges.

### 5. Configure Callback URL

Under **"Configuration"** → **"Admin API integration"**:

- **Callback URL:** `https://api.forgeflow.ai/api/v1/auth/shopify/callback`

For local development:

```
http://localhost:8000/api/v1/auth/shopify/callback
```

> Shopify only allows `https://` URLs for production apps. For local development, use `https://localhost:8000/...` with a self-signed cert, or use a tunnel (ngrok, Cloudflare Tunnel).

### 6. Get API Credentials

After saving:

1. Copy **API key** — this is `SHOPIFY_CLIENT_ID`
2. Copy **API secret** — this is `SHOPIFY_CLIENT_SECRET`
3. Copy **Admin API access token** — this is the token for direct API access (used during development/testing)

### 7. Install the App on Your Store

1. Go to **"Overview"** → **"Test your app"**
2. Select your development store
3. Click **"Install"**

Or use the OAuth flow URL:

```
https://YOUR-STORE.myshopify.com/admin/oauth/authorize?
  client_id=YOUR_API_KEY&
  scope=read_orders,write_orders,read_customers,read_fulfillments&
  redirect_uri=https://api.forgeflow.ai/api/v1/auth/shopify/callback&
  state=NONCE&
  grant_options[]=per-user
```

---

## Environment Variables Setup

### For Local Development (.env file)

Create `.env` in the `forgeflow/` monorepo root:

```bash
# ── Shopify OAuth ──
SHOPIFY_CLIENT_ID=your_api_key_here
SHOPIFY_CLIENT_SECRET=your_api_secret_here
SHOPIFY_SCOPES=read_orders,write_orders,read_customers,read_fulfillments
SHOPIFY_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/auth/shopify/callback

# ── Database ──
DB_URL=postgresql+asyncpg://forgeflow:forgeflow_dev@localhost:5432/forgeflow

# ── LLM ──
LLM_DEFAULT_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-deepseek-key

# ── Security ──
SECRET_KEY=dev-secret-change-in-production-use-openssl-rand-hex-32

# ── Other ──
APP_ENV=development
DEBUG=true
```

### For Fly.io Deployment

```bash
fly secrets set \
  SHOPIFY_CLIENT_ID=your_api_key_here \
  SHOPIFY_CLIENT_SECRET=your_api_secret_here \
  SHOPIFY_SCOPES="read_orders,write_orders,read_customers,read_fulfillments" \
  SHOPIFY_OAUTH_REDIRECT_URI=https://api.forgeflow.ai/api/v1/auth/shopify/callback \
  SECRET_KEY=$(openssl rand -hex 32) \
  -a forgeflow-api
```

---

## Webhook Configuration

### Automatic Registration

When a merchant installs ForgeFlow, webhooks are registered automatically:

```python
# In services/shopify_oauth.py callback handler:
asyncio.create_task(
    register_shopify_webhooks(
        shop_domain=shop_domain,
        access_token=decrypted_token,
        webhook_base_url="https://api.forgeflow.ai",
    )
)
```

### Registered Webhook Topics

| Topic | Path | Purpose |
|-------|------|---------|
| `orders/create` | `/api/v1/webhooks/shopify/orders/create` | New orders placed |
| `orders/updated` | `/api/v1/webhooks/shopify/orders/updated` | Order status changes |
| `fulfillments/create` | `/api/v1/webhooks/shopify/fulfillments/create` | New shipments created |
| `fulfillments/update` | `/api/v1/webhooks/shopify/fulfillments/update` | Shipment status updates |
| `customers/data_request` | `/api/v1/gdpr/customers/data_request` | GDPR data access request |
| `customers/redact` | `/api/v1/gdpr/customers/redact` | GDPR data deletion request |
| `shop/redact` | `/api/v1/gdpr/shop/redact` | GDPR store data deletion |

### Manual Webhook Registration (if needed)

```bash
curl -X POST "https://YOUR-STORE.myshopify.com/admin/api/2024-01/webhooks.json" \
  -H "X-Shopify-Access-Token: shpat_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "topic": "orders/create",
      "address": "https://api.forgeflow.ai/api/v1/webhooks/shopify/orders/create",
      "format": "json"
    }
  }'
```

---

## Testing the Integration

### 1. Verify OAuth Flow

```bash
# Step 1: Get the install URL
curl "http://localhost:8000/api/v1/auth/shopify/install?shop=test-store.myshopify.com"

# Response: {"install_url": "https://test-store.myshopify.com/admin/oauth/authorize?...", ...}

# Step 2: Open the install_url in a browser
# Step 3: After approval, you should be redirected to your callback
```

### 2. Test API Connection

```bash
# Create a test ticket
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt_token>" \
  -d '{
    "platform": "shopify",
    "issue_text": "Where is my order #1001?",
    "customer_email": "test@example.com",
    "order_id": "gid://shopify/Order/1234567890"
  }'
```

### 3. Simulate a Webhook

```bash
# Compute HMAC first (use the test helper)
python -c "
import base64, hashlib, hmac, json
body = json.dumps({'id': 12345, 'order_number': 1001}).encode()
secret = b'your_client_secret'
h = base64.b64encode(hmac.new(secret, body, hashlib.sha256).digest()).decode()
print(f'X-Shopify-Hmac-Sha256: {h}')
"

# Send webhook
curl -X POST http://localhost:8000/api/v1/webhooks/shopify/orders/create \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Hmac-Sha256: <computed_hmac>" \
  -H "X-Shopify-Shop-Domain: test-store.myshopify.com" \
  -d '{"id": 12345, "order_number": 1001}'
```

---

## Troubleshooting

### "OAuth error: invalid_request: The redirect_uri is not whitelisted"

**Cause:** The redirect URI in your code doesn't match what's configured in Shopify.

**Fix:** 
1. Go to your Shopify Partner dashboard → App → Configuration
2. Under "Allowed redirection URL(s)", add your exact callback URL
3. Make sure it includes the full path: `https://api.forgeflow.ai/api/v1/auth/shopify/callback`

### "Access token is invalid or does not have required scopes"

**Cause:** The stored access token is wrong or expired.

**Fix:**
1. Custom app tokens are permanent but can be revoked
2. Re-install the app to get a new token
3. Verify the token is stored encrypted in `shopify_sessions.access_token_encrypted`

### "Webhook registration failed: 403 Forbidden"

**Cause:** The access token doesn't have `write_orders` scope.

**Fix:**
1. Verify scopes include `write_orders`
2. Re-install the app with updated scopes
3. Check Shopify Admin → Settings → Apps → ForgeFlow AI → App permissions

---

## Production Checklist

Before going live with a pilot merchant:

- [ ] Custom app created with all 4 scopes
- [ ] `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET` set in production
- [ ] Callback URL set to production API URL (HTTPS)
- [ ] `SECRET_KEY` is a strong random value (NOT the default)
- [ ] `CORS_ORIGINS` set to the production dashboard URL
- [ ] `APP_ENV=production` and `DEBUG=false`
- [ ] Rate limiting enabled (`RATE_LIMIT_ENABLED=true`)
- [ ] RLS enabled (run `alembic upgrade head`)
- [ ] Webhook base URL is publicly accessible (not localhost)
- [ ] Health check endpoint returns 200 at production URL
- [ ] Send a test ticket and verify it resolves correctly
- [ ] Monitor logs for 24 hours before full rollout
