"""
ForgeFlow AI - Application Constants.

Central place for all magic numbers and configuration constants.
"""

# --- Auto-approval Thresholds ---
AUTO_REFUND_THRESHOLD_USD = 50.0  # Orders below this are auto-refunded

# --- LLM ---
LLM_DEFAULT_TEMPERATURE = 0.1  # Low temperature for deterministic decisions
LLM_REQUEST_TIMEOUT_S = 30  # Max wait for LLM response
LLM_MAX_RETRIES = 3  # Max retries for transient LLM failures

# --- Agent ---
AGENT_MAX_RETRIES = 3  # Max retries for agent node execution
AGENT_NODE_TIMEOUT_S = 60  # Max time per agent node

# --- Pagination ---
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# --- Rate Limiting ---
RATE_LIMIT_PER_MINUTE = 60  # Per-tenant API calls per minute

# --- WebSocket ---
WS_HEARTBEAT_INTERVAL_S = 30
WS_RECONNECT_BASE_DELAY_S = 1
WS_RECONNECT_MAX_DELAY_S = 30

# --- Cache ---
CACHE_DEFAULT_TTL_S = 300  # 5 minutes
CACHE_LONG_TTL_S = 3600  # 1 hour
