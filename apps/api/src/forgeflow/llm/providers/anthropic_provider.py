"""
ForgeFlow AI - Anthropic Provider.

Implements LLMProvider for Anthropic Claude models.
"""

import json
import time
from typing import Any

from anthropic import AsyncAnthropic

from forgeflow.core.config import get_settings
from forgeflow.llm.base import EmbeddingResult, LLMCallResult, LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self, model: str, **kwargs: Any):
        super().__init__(model, **kwargs)
        settings = get_settings()
        api_key = settings.llm.anthropic_api_key
        if api_key:
            self.client = AsyncAnthropic(api_key=api_key.get_secret_value())
        else:
            self.client = AsyncAnthropic()  # Falls back to ANTHROPIC_API_KEY env var

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Send a simple prompt and return text."""
        temperature = kwargs.pop("temperature", 0.1)
        max_tokens = kwargs.pop("max_tokens", 1000)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        # Extract text from the first content block
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""

    async def complete_structured(
        self,
        prompt: str,
        output_schema: dict,
        **kwargs: Any,
    ) -> LLMCallResult:
        """Send a prompt expecting structured JSON output.

        Anthropic doesn't have a native JSON mode, so we use the prefill
        technique: prepend '{' to the assistant message to force JSON start.
        """
        temperature = kwargs.pop("temperature", 0.1)
        max_tokens = kwargs.pop("max_tokens", 2000)

        start_time = time.perf_counter()

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system="Always respond with valid JSON. Do not include any text outside the JSON object.",
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "{"},  # Prefill to force JSON
                ],
                **kwargs,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Reconstruct the full JSON (prefill "{" + response text)
            raw = "{" + (response.content[0].text if response.content else "")
            parsed = json.loads(raw)

            # Estimate tokens (Anthropic returns input/output tokens)
            tokens = (
                response.usage.input_tokens + response.usage.output_tokens
                if hasattr(response, "usage") else 0
            )
            cost = self._estimate_cost(
                prompt_tokens=response.usage.input_tokens if hasattr(response, "usage") else 0,
                completion_tokens=response.usage.output_tokens if hasattr(response, "usage") else 0,
            )

            return LLMCallResult(
                success=True,
                data=parsed,
                raw_response=raw,
                latency_ms=latency_ms,
                tokens_used=tokens,
                cost=cost,
            )

        except (json.JSONDecodeError, AttributeError):
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return LLMCallResult(
                success=False,
                fallback_used=True,
                fallback_reason="json_parse_error",
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return LLMCallResult(
                success=False,
                fallback_used=True,
                fallback_reason=f"api_error: {str(e)[:100]}",
                latency_ms=latency_ms,
            )

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost based on Claude model pricing.

        Pricing (per 1M tokens):
        - Claude Haiku 4.5: $1.00 input / $5.00 output
        - Claude Sonnet 4.6: $3.00 input / $15.00 output
        - Claude Opus 4.8: $15.00 input / $75.00 output
        """
        if "haiku" in self.model:
            input_price = 1.00 / 1_000_000
            output_price = 5.00 / 1_000_000
        elif "sonnet" in self.model:
            input_price = 3.00 / 1_000_000
            output_price = 15.00 / 1_000_000
        elif "opus" in self.model:
            input_price = 15.00 / 1_000_000
            output_price = 75.00 / 1_000_000
        else:
            # Default to Sonnet pricing
            input_price = 3.00 / 1_000_000
            output_price = 15.00 / 1_000_000

        return (prompt_tokens * input_price) + (completion_tokens * output_price)

    async def embed(self, text: str, **kwargs: Any) -> EmbeddingResult:
        """Embedding is not supported by Anthropic.

        Use OpenAI provider (text-embedding-3-small) for embeddings.
        """
        return EmbeddingResult(
            success=False,
            error="Embedding not supported by Anthropic provider. Use OpenAI.",
        )
