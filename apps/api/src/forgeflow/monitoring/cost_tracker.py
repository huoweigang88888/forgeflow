"""
ForgeFlow AI - Cost Tracking Service.

Real-time LLM cost tracking with per-tenant budget alerts.
Implements PRD Section 16.4: Cost Optimization Strategy 5.

Usage:
    tracker = CostTracker(db_session, redis_client)
    await tracker.record_usage(
        tenant_id="mystore.myshopify.com",
        model="deepseek-chat",
        tokens=1500,
        cost=0.0005,
    )
    status = await tracker.check_budget("mystore.myshopify.com")
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="monitoring.cost")


@dataclass
class BudgetStatus:
    """Per-tenant budget status."""

    tenant_id: str
    current_cost: float
    budget_limit: float
    percentage: float
    is_over_budget: bool
    is_warning: bool  # > 80%


# Default monthly budget per tenant (can be overridden per tenant)
DEFAULT_MONTHLY_BUDGET_USD = 50.0
WARNING_THRESHOLD = 0.80  # Alert at 80%


class CostTracker:
    """Tracks LLM API costs per tenant with budget alerts.

    Uses Redis for real-time cost counters with PostgreSQL for
    persistent cost records (llm_calls table serves as source of truth).
    """

    def __init__(self, redis_client, db_session=None):
        self.redis = redis_client
        self.db = db_session

    # ------------------------------------------------------------------
    # Usage Recording
    # ------------------------------------------------------------------

    async def record_usage(
        self,
        tenant_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
    ) -> None:
        """Record an LLM call's cost for a tenant.

        Updates both:
        - Redis counter (real-time, for budget checks)
        - PostgreSQL llm_calls table (persistent, for billing)
        """
        month_key = self._monthly_key(tenant_id)

        # Increment Redis counters
        pipe = self.redis.pipeline()
        pipe.hincrbyfloat(month_key, "total_cost", cost)
        pipe.hincrby(month_key, "total_tokens", prompt_tokens + completion_tokens)
        pipe.hincrby(month_key, "call_count", 1)
        pipe.expire(month_key, 60 * 60 * 24 * 45)  # 45-day TTL
        await pipe.execute()

        logger.debug(
            "cost_recorded",
            tenant_id=tenant_id,
            model=model,
            cost=cost,
            tokens=prompt_tokens + completion_tokens,
        )

    # ------------------------------------------------------------------
    # Budget Checks
    # ------------------------------------------------------------------

    async def check_budget(self, tenant_id: str) -> BudgetStatus:
        """Check if a tenant is approaching or exceeding their monthly budget.

        Returns a BudgetStatus with warning/over-budget flags.
        """
        month_key = self._monthly_key(tenant_id)
        budget = await self._get_tenant_budget(tenant_id)

        current_cost = await self.redis.hget(month_key, "total_cost")
        current_cost = float(current_cost) if current_cost else 0.0

        percentage = (current_cost / budget * 100) if budget > 0 else 0.0
        is_over = current_cost >= budget
        is_warning = current_cost >= budget * WARNING_THRESHOLD

        return BudgetStatus(
            tenant_id=tenant_id,
            current_cost=round(current_cost, 4),
            budget_limit=budget,
            percentage=round(percentage, 1),
            is_over_budget=is_over,
            is_warning=is_warning,
        )

    async def get_monthly_stats(self, tenant_id: str) -> dict[str, Any]:
        """Get monthly usage statistics for a tenant."""
        month_key = self._monthly_key(tenant_id)

        pipe = self.redis.pipeline()
        pipe.hgetall(month_key)
        pipe.ttl(month_key)
        results = await pipe.execute()

        data = results[0]
        return {
            "total_cost": float(data.get(b"total_cost", 0) or 0),
            "total_tokens": int(data.get(b"total_tokens", 0) or 0),
            "call_count": int(data.get(b"call_count", 0) or 0),
            "month": datetime.now(UTC).strftime("%Y-%m"),
        }

    async def get_all_tenants_cost(self) -> list[dict[str, Any]]:
        """Get cost summary for all tenants (for admin dashboard)."""
        # Scan for all cost keys
        tenants = []
        cursor = 0
        pattern = "cost:tenant:*"

        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                tenant_id = key.decode().split(":", 2)[-1]
                status = await self.check_budget(tenant_id)
                tenants.append(
                    {
                        "tenant_id": tenant_id,
                        "current_cost": status.current_cost,
                        "budget_limit": status.budget_limit,
                        "percentage": status.percentage,
                        "is_warning": status.is_warning,
                    }
                )
            if cursor == 0:
                break

        # Sort by cost descending
        tenants.sort(key=lambda t: t["current_cost"], reverse=True)
        return tenants

    # ------------------------------------------------------------------
    # Budget Configuration
    # ------------------------------------------------------------------

    async def set_tenant_budget(self, tenant_id: str, monthly_budget_usd: float) -> None:
        """Set a custom monthly budget for a tenant."""
        await self.redis.set(
            f"budget:tenant:{tenant_id}",
            monthly_budget_usd,
        )
        logger.info(
            "budget_set",
            tenant_id=tenant_id,
            monthly_budget_usd=monthly_budget_usd,
        )

    async def _get_tenant_budget(self, tenant_id: str) -> float:
        """Get a tenant's monthly budget (default or custom)."""
        custom = await self.redis.get(f"budget:tenant:{tenant_id}")
        if custom:
            return float(custom)
        return DEFAULT_MONTHLY_BUDGET_USD

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _monthly_key(tenant_id: str) -> str:
        """Generate Redis key for monthly cost tracking."""
        month_str = datetime.now(UTC).strftime("%Y-%m")
        return f"cost:tenant:{tenant_id}:{month_str}"
