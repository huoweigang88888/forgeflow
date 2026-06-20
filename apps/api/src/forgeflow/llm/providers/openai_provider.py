"""
ForgeFlow AI - OpenAI Provider.

Implements LLMProvider for OpenAI models (GPT-4o, GPT-4o-mini).
Uses the official openai Python SDK with async support.
"""

import json
import time
from typing import Any

from openai import AsyncOpenAI

from forgeflow.core.config import get_settings
from forgeflow.llm.base import EmbeddingResult, LLMCallResult, LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider using the official SDK."""

    def __init__(self, model: str, **kwargs: Any):
        super().__init__(model, **kwargs)
        settings = get_settings()
        api_key = settings.llm.openai_api_key
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key.get_secret_value())
        else:
            self.client = AsyncOpenAI()  # Falls back to OPENAI_API_KEY env var

    @property
    def provider_name(self) -> str:
        return "openai"

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Send a simple prompt and return text."""
        temperature = kwargs.pop("temperature", 0.1)
        max_tokens = kwargs.pop("max_tokens", 1000)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def complete_structured(
        self,
        prompt: str,
        output_schema: dict,
        **kwargs: Any,
    ) -> LLMCallResult:
        """Send a prompt expecting structured JSON output.

        Uses OpenAI's response_format={"type": "json_object"} for
        guaranteed valid JSON (Layer 1 of the 3-layer resilience strategy).
        """
        temperature = kwargs.pop("temperature", 0.1)
        max_tokens = kwargs.pop("max_tokens", 2000)

        start_time = time.perf_counter()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Always respond with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                **kwargs,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)

            # Extract usage
            usage = response.usage
            tokens = usage.total_tokens if usage else 0
            cost = self._estimate_cost(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            )

            return LLMCallResult(
                success=True,
                data=parsed,
                raw_response=raw,
                latency_ms=latency_ms,
                tokens_used=tokens,
                cost=cost,
            )

        except json.JSONDecodeError:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return LLMCallResult(
                success=False,
                raw_response=raw if "raw" in dir() else None,
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
        """Estimate cost based on model pricing.

        Pricing (per 1M tokens):
        - gpt-4o: $2.50 input / $10.00 output
        - gpt-4o-mini: $0.15 input / $0.60 output
        """
        if "mini" in self.model:
            input_price = 0.15 / 1_000_000
            output_price = 0.60 / 1_000_000
        else:
            input_price = 2.50 / 1_000_000
            output_price = 10.00 / 1_000_000

        return (prompt_tokens * input_price) + (completion_tokens * output_price)

    async def embed(self, text: str, **kwargs: Any) -> EmbeddingResult:
        """Generate embedding using OpenAI's text-embedding-3-small.

        Args:
            text: The text to embed.
            **kwargs: Can include model and dimensions overrides.

        Returns:
            EmbeddingResult with the embedding vector.
        """
        settings = get_settings()
        model = kwargs.pop("model", settings.llm.embedding_model)
        dimensions = kwargs.pop("dimensions", settings.llm.embedding_dimensions)

        start_time = time.perf_counter()

        try:
            response = await self.client.embeddings.create(
                model=model,
                input=text,
                dimensions=dimensions,
                **kwargs,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            embedding = response.data[0].embedding
            tokens = response.usage.total_tokens if response.usage else 0

            return EmbeddingResult(
                success=True,
                embedding=embedding,
                dimensions=len(embedding),
                tokens_used=tokens,
                cost=self._estimate_embedding_cost(tokens),
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return EmbeddingResult(
                success=False,
                error=str(e)[:200],
                latency_ms=latency_ms,
            )

    def _estimate_embedding_cost(self, tokens: int) -> float:
        """text-embedding-3-small: $0.02 per 1M tokens."""
        return tokens * 0.02 / 1_000_000
