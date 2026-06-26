"""
ForgeFlow AI - Prometheus Metrics.

Exposes application metrics at /api/metrics for Prometheus scraping.
Includes standard HTTP metrics and custom business metrics.
"""

from fastapi import APIRouter, Response
from prometheus_client import REGISTRY, Counter, Histogram, generate_latest

# --- HTTP Metrics ---
http_requests_total = Counter(
    "forgeflow_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "forgeflow_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# --- LLM Metrics ---
llm_calls_total = Counter(
    "forgeflow_llm_calls_total",
    "Total LLM API calls",
    ["provider", "model", "status"],
)

llm_call_duration_seconds = Histogram(
    "forgeflow_llm_call_duration_seconds",
    "LLM call duration in seconds",
    ["provider", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

llm_tokens_total = Counter(
    "forgeflow_llm_tokens_total",
    "Total tokens consumed",
    ["provider", "model", "type"],  # "type" dimension: input or output
)

llm_cost_total = Counter(
    "forgeflow_llm_cost_total",
    "Total LLM cost in USD",
    ["provider", "model"],
)

# --- Business Metrics ---
tickets_created_total = Counter(
    "forgeflow_tickets_created_total",
    "Total tickets created",
    ["intent", "platform"],
)

tickets_resolved_total = Counter(
    "forgeflow_tickets_resolved_total",
    "Total tickets resolved",
    ["resolution_type"],  # auto | approved | escalated
)

agent_node_duration_seconds = Histogram(
    "forgeflow_agent_node_duration_seconds",
    "Agent node execution duration",
    ["node_name", "status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

fallback_triggered_total = Counter(
    "forgeflow_fallback_triggered_total",
    "Total LLM fallback triggers",
    ["node", "layer"],  # layer: layer1_json | layer2_regex | layer3_static
)

# --- Metrics Router ---
router = APIRouter()


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint.

    Returns all registered metrics in Prometheus text format.
    Scraped by Prometheus at the configured interval.
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; charset=utf-8",
    )
