"""
ForgeFlow AI - Model Router.

Implements the two-tier model selection strategy from PRD Section 16.4:
1. gpt-4o-mini (or equivalent) for most cases (~95%)
2. Upgrade to full model only when confidence is low (~5%)

This reduces LLM costs by avoiding expensive model calls when a cheaper
model is sufficiently confident.
"""

from typing import Any

from forgeflow.core.config import get_settings
from forgeflow.llm.base import LLMCallResult, LLMFactory


class ModelRouter:
    """Routes decisions to mini or full model based on complexity.

    Strategy:
    1. First attempt with the default (cheaper) model
    2. If confidence < threshold, retry with the complex (expensive) model
    3. Only ~5% of cases reach the expensive model

    Usage:
        router = ModelRouter()
        result = await router.route_decision(prompt, output_schema)
    """

    DECISION_THRESHOLD = 0.7  # Minimum confidence before upgrading

    def __init__(self) -> None:
        settings = get_settings()
        self.default_provider = settings.llm.default_provider
        self.default_model = settings.llm.default_model
        self.complex_model = settings.llm.complex_model

    async def route_decision(
        self, prompt: str, output_schema: dict, **kwargs: Any
    ) -> LLMCallResult:
        """Two-tier model routing for decision-making.

        Args:
            prompt: The decision prompt.
            output_schema: Expected JSON schema for the output.
            **kwargs: Additional provider parameters.

        Returns:
            LLMCallResult from either the default or complex model.
        """
        # Tier 1: Default (cheaper) model
        provider = LLMFactory.create(self.default_provider, model=self.default_model)
        result = await provider.complete_structured(prompt, output_schema, **kwargs)

        # If the default model is confident enough, return immediately
        if result.success and self._is_confident(result.data):
            return result

        # Tier 2: Complex (expensive) model — only ~5% of cases
        provider = LLMFactory.create(self.default_provider, model=self.complex_model)
        complex_result = await provider.complete_structured(prompt, output_schema, **kwargs)

        # Mark the upgrade in the result
        if complex_result.success:
            return complex_result

        # If even the complex model failed, return the original result
        return result

    def _is_confident(self, data: dict | None) -> bool:
        """Check if the model output meets the confidence threshold."""
        if data is None:
            return False
        confidence = data.get("confidence", 0.0)
        if isinstance(confidence, (int, float)):
            return confidence >= self.DECISION_THRESHOLD
        return True  # No confidence field means we trust it
