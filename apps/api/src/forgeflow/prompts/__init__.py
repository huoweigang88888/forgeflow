"""
ForgeFlow AI - Prompt Registry Service.

Database-backed prompt version management with A/B testing support.
Implements PRD Section 18: Prompt Engineering & Version Management.

Usage:
    registry = PromptRegistry(db_session)
    prompt = await registry.get_active("intent_detection")
    rendered = prompt.render(issue="...", order_id="...")
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forgeflow.models.prompt_version import PromptVersion
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="prompts.registry")


@dataclass
class RenderedPrompt:
    """A prompt template rendered with variables."""

    prompt_name: str
    version: str
    rendered: str
    model: str  # recommended model for this prompt


class PromptRegistry:
    """Central registry for all LLM prompt templates.

    Features:
    - Database-backed versioning (not file-based)
    - Atomic activation (only one version active per prompt_name)
    - A/B testing with hash-based routing
    - Real-time hot-swap (no restart needed)
    - Performance metrics per version

    Usage:
        registry = PromptRegistry(db_session)

        # Production: get active version
        prompt = await registry.get_active("intent_detection")

        # A/B test: deterministic routing
        prompt = await registry.get_for_ticket("intent_detection", ticket_id)

        # Register new version
        await registry.register(
            prompt_name="intent_detection",
            version="v1.2.0",
            template="...",
            activate=True,
        )

        # Rollback
        await registry.rollback("intent_detection", "v1.0.0")
    """

    # Fallback templates (used when database is unavailable)
    FALLBACK_TEMPLATES: dict[str, str] = {
        "intent_detection": (
            "Classify: {issue}\nOrder: {order_id}\n"
            "Return JSON: {{intent, confidence, urgency, sentiment}}"
        ),
        "decision": (
            "Intent: {intent}\nOrder: {order_info}\n"
            "Logistics: {logistics_status}\nHistory: {customer_history}\n"
            "Return JSON: {{recommended_action, refund_amount, requires_approval, ...}}"
        ),
        "policy_check": (
            "Issue: {issue_text}\nIntent: {intent}\n"
            "Policies: {policies_text}\n"
            "Return JSON: {{relevant_policies, policy_match, recommendation}}"
        ),
    }

    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session
        self._cache: dict[str, PromptVersion] = {}

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def get_active(self, prompt_name: str) -> RenderedPrompt:
        """Get the currently active version of a prompt.

        Falls back to in-code templates if no DB version is active.
        """
        # Check cache first
        if prompt_name in self._cache:
            pv = self._cache[prompt_name]
            return RenderedPrompt(
                prompt_name=pv.prompt_name,
                version=pv.version,
                rendered=pv.template,
                model="deepseek-chat",
            )

        # Query database
        stmt = (
            select(PromptVersion)
            .where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.is_active == True,  # noqa: E712
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is not None:
            self._cache[prompt_name] = row
            return RenderedPrompt(
                prompt_name=row.prompt_name,
                version=row.version,
                rendered=row.template,
                model="deepseek-chat",
            )

        # Fallback to in-code templates
        logger.warning("prompt_fallback_used", prompt_name=prompt_name)
        fallback = self.FALLBACK_TEMPLATES.get(prompt_name, "{input}")
        return RenderedPrompt(
            prompt_name=prompt_name,
            version="fallback",
            rendered=fallback,
            model="deepseek-chat",
        )

    async def get_version(
        self, prompt_name: str, version: str
    ) -> RenderedPrompt | None:
        """Get a specific version of a prompt."""
        stmt = select(PromptVersion).where(
            PromptVersion.prompt_name == prompt_name,
            PromptVersion.version == version,
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return RenderedPrompt(
            prompt_name=row.prompt_name,
            version=row.version,
            rendered=row.template,
            model="deepseek-chat",
        )

    # ------------------------------------------------------------------
    # A/B Testing
    # ------------------------------------------------------------------

    async def get_for_ticket(
        self, prompt_name: str, ticket_id: str
    ) -> RenderedPrompt:
        """Get prompt for a ticket, respecting active A/B test routing.

        Hash-based deterministic routing ensures the same ticket always
        gets the same prompt version.
        """
        from hashlib import md5

        # Check for active A/B test
        ab_test = await self._get_active_ab_test(prompt_name)
        if ab_test is None:
            return await self.get_active(prompt_name)

        # Deterministic routing
        hash_val = int(md5(ticket_id.encode()).hexdigest()[:8], 16)
        is_variant = (hash_val % 100) < int(ab_test["traffic_split"] * 100)

        if is_variant:
            return await self.get_version(prompt_name, ab_test["variant_version"])

        return await self.get_version(prompt_name, ab_test["control_version"])

    # ------------------------------------------------------------------
    # Version Management
    # ------------------------------------------------------------------

    async def register(
        self,
        prompt_name: str,
        version: str,
        template: str,
        description: str = "",
        created_by: str = "system",
        activate: bool = False,
    ) -> PromptVersion:
        """Register a new prompt version.

        If activate=True, deactivates the current active version first.
        """
        pv = PromptVersion(
            prompt_name=prompt_name,
            version=version,
            template=template,
            description=description,
            created_by=created_by,
            is_active=activate,
        )

        if activate:
            # Deactivate current active version
            await self.db.execute(
                update(PromptVersion)
                .where(
                    PromptVersion.prompt_name == prompt_name,
                    PromptVersion.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )

        self.db.add(pv)
        await self.db.commit()
        await self.db.refresh(pv)

        # Update cache
        if activate:
            self._cache[prompt_name] = pv

        logger.info(
            "prompt_registered",
            prompt_name=prompt_name,
            version=version,
            active=activate,
        )
        return pv

    async def rollback(self, prompt_name: str, to_version: str) -> PromptVersion:
        """Rollback to a previous version and activate it.

        This is a critical safety mechanism — if a new prompt version
        causes issues in production, rollback is instant and doesn't
        require a redeploy.
        """
        # Verify target version exists
        target = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.version == to_version,
            )
        )
        target_pv = target.scalar_one_or_none()

        if target_pv is None:
            raise ValueError(
                f"Prompt '{prompt_name}' version '{to_version}' not found. "
                f"Cannot rollback."
            )

        # Deactivate current
        await self.db.execute(
            update(PromptVersion)
            .where(
                PromptVersion.prompt_name == prompt_name,
                PromptVersion.is_active == True,  # noqa: E712
            )
            .values(is_active=False)
        )

        # Activate target
        target_pv.is_active = True
        await self.db.commit()
        await self.db.refresh(target_pv)

        # Update cache
        self._cache[prompt_name] = target_pv

        logger.info(
            "prompt_rollback",
            prompt_name=prompt_name,
            to_version=to_version,
        )
        return target_pv

    async def list_versions(self, prompt_name: str) -> list[dict[str, Any]]:
        """List all versions of a prompt, sorted by creation date (newest first)."""
        stmt = (
            select(PromptVersion)
            .where(PromptVersion.prompt_name == prompt_name)
            .order_by(PromptVersion.created_at.desc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "version": r.version,
                "description": r.description,
                "is_active": r.is_active,
                "accuracy": r.accuracy,
                "avg_latency_ms": r.avg_latency_ms,
                "sample_count": r.sample_count,
                "created_by": r.created_by,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def update_metrics(
        self,
        prompt_name: str,
        version: str,
        accuracy: float | None = None,
        avg_latency_ms: int | None = None,
        sample_count: int | None = None,
    ) -> None:
        """Update performance metrics for a prompt version.

        Called by the evaluation pipeline after running regression tests.
        """
        values: dict[str, Any] = {}
        if accuracy is not None:
            values["accuracy"] = accuracy
        if avg_latency_ms is not None:
            values["avg_latency_ms"] = avg_latency_ms
        if sample_count is not None:
            values["sample_count"] = sample_count
        values["updated_at"] = datetime.now(UTC)

        if values:
            await self.db.execute(
                update(PromptVersion)
                .where(
                    PromptVersion.prompt_name == prompt_name,
                    PromptVersion.version == version,
                )
                .values(**values)
            )
            await self.db.commit()

    # ------------------------------------------------------------------
    # A/B Test State (stored in Redis in production, in-memory for now)
    # ------------------------------------------------------------------

    _ab_tests: dict[str, dict[str, Any]] = {}

    async def start_ab_test(
        self,
        prompt_name: str,
        control_version: str,
        variant_version: str,
        traffic_split: float = 0.5,
    ) -> dict[str, Any]:
        """Start an A/B test for a prompt."""
        test_config = {
            "prompt_name": prompt_name,
            "control_version": control_version,
            "variant_version": variant_version,
            "traffic_split": traffic_split,
            "started_at": datetime.now(UTC).isoformat(),
        }
        self._ab_tests[prompt_name] = test_config
        logger.info(
            "ab_test_started",
            prompt_name=prompt_name,
            control=control_version,
            variant=variant_version,
            split=traffic_split,
        )
        return test_config

    async def stop_ab_test(self, prompt_name: str) -> None:
        """Stop an A/B test and clean up."""
        self._ab_tests.pop(prompt_name, None)
        logger.info("ab_test_stopped", prompt_name=prompt_name)

    async def _get_active_ab_test(
        self, prompt_name: str
    ) -> dict[str, Any] | None:
        """Get active A/B test config, if any."""
        return self._ab_tests.get(prompt_name)

    async def seed_default_prompts(self) -> list[PromptVersion]:
        """Seed the database with default prompt versions from code.

        Call this once during initial deployment or when resetting.
        """
        from forgeflow.agent.prompts import (
            DECISION_PROMPT,
            INTENT_PROMPT,
            POLICY_CHECK_PROMPT,
        )

        defaults = [
            {
                "prompt_name": "intent_detection",
                "version": "v1.0.0",
                "template": INTENT_PROMPT,
                "description": "Initial intent detection prompt — 6-class classifier",
            },
            {
                "prompt_name": "decision",
                "version": "v1.0.0",
                "template": DECISION_PROMPT,
                "description": "Initial decision prompt — hard rules + LLM fallback",
            },
            {
                "prompt_name": "policy_check",
                "version": "v1.0.0",
                "template": POLICY_CHECK_PROMPT,
                "description": "Initial policy check prompt — relevance matching",
            },
        ]

        created: list[PromptVersion] = []
        for d in defaults:
            # Check if already exists
            existing = await self.db.execute(
                select(PromptVersion).where(
                    PromptVersion.prompt_name == d["prompt_name"],
                    PromptVersion.version == d["version"],
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            pv = await self.register(
                prompt_name=d["prompt_name"],
                version=d["version"],
                template=d["template"],
                description=d["description"],
                created_by="seed_default_prompts",
                activate=True,
            )
            created.append(pv)

        logger.info("prompts_seeded", count=len(created))
        return created
