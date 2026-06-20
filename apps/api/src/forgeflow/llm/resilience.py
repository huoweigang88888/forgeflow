"""
ForgeFlow AI - LLM Resilience Wrapper.

Implements the 3-layer fallback strategy from PRD Section 14.1:

Layer 1: JSON Mode + Pydantic validation → catches 95% of cases
Layer 2: Regex extraction + format repair  → catches 4% of edge cases
Layer 3: Safe fallback template (static)   → catches last 1%

Design principle: Every LLM call MUST produce a reasonable output.
The system never fails because of an LLM parsing error.
"""

import json
import re
import time
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from forgeflow.llm.base import LLMCallResult, LLMFactory
from forgeflow.monitoring.logger import get_logger
from forgeflow.monitoring.metrics import (
    fallback_triggered_total,
    llm_call_duration_seconds,
    llm_calls_total,
    llm_tokens_total,
)

logger = get_logger(component="llm_resilience")


class LLMResilienceWrapper:
    """Wraps all LLM calls with 3-layer fallback protection.

    Usage:
        wrapper = LLMResilienceWrapper(
            provider="openai",
            model="gpt-4o-mini",
            fallback_value=FALLBACK_INTENT,
        )
        result = await wrapper.call(prompt, output_schema)
    """

    def __init__(
        self,
        provider: str,
        model: str,
        fallback_value: dict,
    ) -> None:
        self.provider_name = provider
        self.model = model
        self.fallback_value = fallback_value

    async def call(
        self,
        prompt: str,
        output_schema: dict | None = None,
        **kwargs: Any,
    ) -> LLMCallResult:
        """Execute an LLM call with 3-layer resilience.

        Args:
            prompt: The full prompt to send.
            output_schema: Expected JSON schema for structured output.
            **kwargs: Additional provider parameters.

        Returns:
            LLMCallResult — guaranteed to have data (from fallback if needed).
        """
        retry_count = 0
        overall_start = time.perf_counter()

        # =====================================================================
        # Layer 1: JSON Mode + Native structured output
        # =====================================================================
        try:
            provider = LLMFactory.create(self.provider_name, model=self.model)
            result = await self._call_with_retry(provider, prompt, output_schema or {}, **kwargs)

            if result.success and result.data:
                result.latency_ms = int((time.perf_counter() - overall_start) * 1000)
                self._record_metrics(result)
                return result

            retry_count += result.retry_count

        except Exception as e:
            logger.warning(
                "llm_layer1_failed",
                provider=self.provider_name,
                model=self.model,
                error=str(e)[:200],
            )
            retry_count += 1

        # =====================================================================
        # Layer 2: Regex extraction + format repair
        # =====================================================================
        try:
            provider = LLMFactory.create(self.provider_name, model=self.model)
            raw = await provider.complete(prompt, **kwargs)

            extracted = self._regex_extract(raw)
            if extracted:
                logger.info(
                    "llm_layer2_recovered",
                    provider=self.provider_name,
                    extracted_fields=list(extracted.keys()),
                )
                latency_ms = int((time.perf_counter() - overall_start) * 1000)
                result = LLMCallResult(
                    success=True,
                    data=extracted,
                    raw_response=raw,
                    fallback_used=True,
                    fallback_reason="layer2_regex_fix",
                    retry_count=retry_count,
                    latency_ms=latency_ms,
                )
                self._record_metrics(result)
                return result

        except Exception as e:
            logger.warning(
                "llm_layer2_failed",
                provider=self.provider_name,
                error=str(e)[:200],
            )
            retry_count += 1

        # =====================================================================
        # Layer 3: Safe fallback (static template)
        # =====================================================================
        logger.warning(
            "llm_layer3_fallback_used",
            provider=self.provider_name,
            fallback_value=self.fallback_value,
        )

        latency_ms = int((time.perf_counter() - overall_start) * 1000)
        result = LLMCallResult(
            success=False,
            data=self.fallback_value,
            fallback_used=True,
            fallback_reason="layer3_static_fallback",
            retry_count=retry_count,
            latency_ms=latency_ms,
        )

        # --- Record Metrics ---
        self._record_metrics(result)
        return result

    def _record_metrics(self, result: LLMCallResult) -> None:
        """Record Prometheus metrics for an LLM call result."""
        status = "success" if result.success else "failure"
        llm_calls_total.labels(
            provider=self.provider_name,
            model=self.model,
            status=status,
        ).inc()

        llm_call_duration_seconds.labels(
            provider=self.provider_name,
            model=self.model,
        ).observe(result.latency_ms / 1000.0)

        if result.input_tokens:
            llm_tokens_total.labels(
                provider=self.provider_name,
                model=self.model,
                type="input",
            ).inc(result.input_tokens)

        if result.output_tokens:
            llm_tokens_total.labels(
                provider=self.provider_name,
                model=self.model,
                type="output",
            ).inc(result.output_tokens)

        if result.fallback_used:
            layer = (
                "layer3_static" if "static" in (result.fallback_reason or "") else "layer2_regex"
            )
            fallback_triggered_total.labels(
                node="llm_call",
                layer=layer,
            ).inc()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        reraise=True,
    )
    async def _call_with_retry(
        self,
        provider: Any,
        prompt: str,
        output_schema: dict,
        **kwargs: Any,
    ) -> LLMCallResult:
        """Call complete_structured with retry on transient failures."""
        return await provider.complete_structured(prompt, output_schema, **kwargs)

    def _regex_extract(self, raw_text: str) -> dict | None:
        """Try to extract structured data from non-standard LLM output.

        Handles common LLM output quirks:
        - ```json ... ``` markdown code blocks
        - Leading/trailing text around JSON
        - Single quotes instead of double quotes
        - Trailing commas in objects
        """
        if not raw_text:
            return None

        # 1. Try extracting from markdown code block
        code_block = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```",
            raw_text,
            re.DOTALL | re.IGNORECASE,
        )
        if code_block:
            candidate = code_block.group(1).strip()
            result = self._safe_json_parse(candidate)
            if result:
                return result

        # 2. Try finding JSON object in text
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if json_match:
            candidate = json_match.group(0)
            result = self._safe_json_parse(candidate)
            if result:
                return result

        # 3. Try with single-to-double quote conversion
        candidate = raw_text.replace("'", '"')
        result = self._safe_json_parse(candidate)
        if result:
            return result

        return None

    @staticmethod
    def _safe_json_parse(text: str) -> dict | None:
        """Safely attempt to parse JSON, returning None on failure."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            # Try removing trailing commas
            try:
                cleaned = re.sub(r",\s*([}\]])", r"\1", text)
                return json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                return None
