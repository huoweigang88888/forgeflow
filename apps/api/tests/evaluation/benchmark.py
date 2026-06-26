"""
ForgeFlow AI - Performance Benchmarks.

Measures agent processing time against the <= 5s target and
identifies bottlenecks per node.

From PRD Section 11.2: API P95 <= 500ms, Agent E2E <= 5s.
"""

import time
from dataclasses import dataclass
from typing import Any

from forgeflow.agent.graph import get_agent_graph
from forgeflow.agent.nodes import detect_intent_node
from forgeflow.agent.state import AgentState, get_initial_state
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="benchmark")

P95_TARGET_MS = 5_000  # 5 seconds
NUM_RUNS = 20  # Enough for a reasonable p95 estimate


@dataclass
class BenchmarkReport:
    """Aggregate benchmark results."""

    total_runs: int
    avg_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    passed: bool  # p95 <= 5s
    per_node_ms: dict[str, float]
    total_time_ms: float


async def benchmark_full_pipeline(num_runs: int = NUM_RUNS) -> BenchmarkReport:
    """Benchmark the full agent pipeline end-to-end.

    Uses mock provider to eliminate external API latency. Measures
    LangGraph overhead + node processing time.
    """
    graph = get_agent_graph()
    durations: list[float] = []

    state = get_initial_state(
        ticket_id="benchmark",
        platform="mock",
        shopify_domain="benchmark.myshopify.com",
        customer_email="benchmark@test.com",
        issue_text="Where is my order #12345? It's been 2 weeks!",
        order_id="benchmark_order_001",
    )

    # Warm-up run (LangGraph compiles on first invoke)
    _ = await graph.ainvoke(state)

    for i in range(num_runs):
        state_i = get_initial_state(
            ticket_id=f"benchmark_{i}",
            platform="mock",
            shopify_domain="benchmark.myshopify.com",
            customer_email=f"benchmark_{i}@test.com",
            issue_text="Where is my order #12345? It's been 2 weeks!",
            order_id="benchmark_order_001",
        )
        start = time.perf_counter()
        _ = await graph.ainvoke(state_i)
        elapsed = (time.perf_counter() - start) * 1000
        durations.append(elapsed)

    return _build_report(durations, num_runs)


async def benchmark_per_node() -> dict[str, float]:
    """Benchmark each primary node individually.

    Returns {node_name: avg_latency_ms}.
    """
    nodes = {
        "detect_intent": detect_intent_node,
        # Other nodes require LLM context; measured via full pipeline
    }

    per_node: dict[str, float] = {}

    state: AgentState = {
        "ticket_id": "bench_node",
        "platform": "mock",
        "issue_text": "Where is my order? It's been 2 weeks!",
        "order_id": "BM_001",
        "current_step": "detect_intent",
    }

    for name, node_fn in nodes.items():
        durations: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            await node_fn(state)
            durations.append((time.perf_counter() - start) * 1000)
        per_node[name] = sum(durations) / len(durations)

    return per_node


async def benchmark_llm_latency() -> dict[str, Any]:
    """Measure LLM call latency per provider.

    Requires valid API keys. Skipped in CI if keys are not set.
    """
    from forgeflow.core.config import get_settings
    from forgeflow.llm.base import LLMFactory

    settings = get_settings()
    results: dict[str, Any] = {}

    test_prompt = (
        "Classify this customer issue into one of: "
        "shipping_delay, refund_request, wrong_item, damaged_item, "
        "exchange_request, other.\n\n"
        "Issue: My order hasn't arrived for 15 days. Where is it?"
    )

    for provider_name in ("deepseek", "openai"):
        try:
            provider = LLMFactory.create(provider_name, model=settings.llm.default_model)
        except Exception:
            results[provider_name] = {"status": "unavailable"}
            continue

        durations: list[float] = []
        errors = 0
        for _ in range(5):
            try:
                start = time.perf_counter()
                _ = await provider.complete(test_prompt)
                durations.append((time.perf_counter() - start) * 1000)
            except Exception:
                errors += 1

        if durations:
            results[provider_name] = {
                "status": "ok",
                "avg_ms": round(sum(durations) / len(durations), 1),
                "min_ms": round(min(durations), 1),
                "max_ms": round(max(durations), 1),
                "errors": errors,
            }
        else:
            results[provider_name] = {"status": "all_failed", "errors": errors}

    return results


# =============================================================================
# Helpers
# =============================================================================


def _build_report(durations: list[float], runs: int) -> BenchmarkReport:
    """Build a BenchmarkReport from raw duration list."""
    if not durations:
        return BenchmarkReport(
            total_runs=0,
            avg_ms=0,
            median_ms=0,
            p95_ms=0,
            p99_ms=0,
            min_ms=0,
            max_ms=0,
            passed=False,
            per_node_ms={},
            total_time_ms=0,
        )

    sorted_d = sorted(durations)
    p95_idx = int(len(sorted_d) * 0.95)
    p99_idx = int(len(sorted_d) * 0.99)

    return BenchmarkReport(
        total_runs=runs,
        avg_ms=round(sum(durations) / len(durations), 1),
        median_ms=round(sorted_d[len(sorted_d) // 2], 1),
        p95_ms=round(sorted_d[min(p95_idx, len(sorted_d) - 1)], 1),
        p99_ms=round(sorted_d[min(p99_idx, len(sorted_d) - 1)], 1),
        min_ms=round(min(durations), 1),
        max_ms=round(max(durations), 1),
        passed=sorted_d[min(p95_idx, len(sorted_d) - 1)] <= P95_TARGET_MS,
        per_node_ms={},
        total_time_ms=round(sum(durations), 1),
    )
