"""
ForgeFlow AI - Qwen (Tongyi Qianwen) Provider.

Qwen models via Alibaba Cloud DashScope API. The DashScope API is
OpenAI-compatible, so we extend OpenAIProvider with a custom base_url
pointing to the DashScope international endpoint.

Models:
- qwen-turbo: Fast, cost-effective (Qwen3-Turbo)
- qwen-plus: Balanced performance and cost (Qwen3-Plus)
- qwen-max: Most capable Qwen model (Qwen3-Max)

Embedding:
- text-embedding-v3: 1024-dimension embedding model
- text-embedding-v4: 2048-dimension embedding model

Usage:
    provider = QwenProvider(model="qwen-turbo")
    result = await provider.complete_structured(prompt, schema)

Or via factory:
    provider = LLMFactory.create("qwen", model="qwen-plus")
"""

import json
import time
from typing import Any, ClassVar

from openai import AsyncOpenAI

from forgeflow.core.config import get_settings
from forgeflow.llm.base import EmbeddingResult, LLMCallResult, LLMProvider
from forgeflow.llm.providers.openai_provider import OpenAIProvider


class QwenProvider(OpenAIProvider):
    """Qwen provider — DashScope OpenAI-compatible API.

    Qwen is important for:
    - Chinese market compliance (data locality)
    - Lower cost for Chinese-language tickets
    - Multi-model redundancy
    """

    MODELS: ClassVar[dict[str, str]] = {
        "qwen-turbo": "Fast, cost-effective (Qwen3-Turbo)",
        "qwen-plus": "Balanced performance and cost (Qwen3-Plus)",
        "qwen-max": "Most capable Qwen model (Qwen3-Max)",
        "qwen-plus-latest": "Latest Qwen3-Plus snapshot",
        "qwen-max-latest": "Latest Qwen3-Max snapshot",
    }

    EMBEDDING_MODELS: ClassVar[dict[str, int]] = {
        "text-embedding-v3": 1024,
        "text-embedding-v4": 2048,
    }

    def __init__(self, model: str = "qwen-turbo", **kwargs: Any):
        # Skip OpenAIProvider.__init__ to avoid creating a default AsyncOpenAI client
        # We must set our own client with DashScope's base_url.
        LLMProvider.__init__(self, model, **kwargs)  # type: ignore[arg-type]
        settings = get_settings()
        api_key = settings.llm.qwen_api_key
        base_url = settings.llm.qwen_base_url

        if api_key:
            self.client = AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                base_url=base_url,
            )
        else:
            # Falls back to DASHSCOPE_API_KEY env var, or unauthenticated
            self.client = AsyncOpenAI(base_url=base_url)

    @property
    def provider_name(self) -> str:
        return "qwen"

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Send a simple prompt and return text completion.

        Uses the OpenAI-compatible chat completions endpoint.
        """
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

        Uses OpenAI's response_format={"type": "json_object"} which
        DashScope API supports (unlike DeepSeek).
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

            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            parsed = json.loads(raw)

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
            raw_val = raw if "raw" in locals() else None
            return LLMCallResult(
                success=False,
                raw_response=raw_val,
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
        """Estimate Qwen DashScope pricing (USD per 1M tokens).

        International pricing (approximate):
        - qwen-turbo: $0.05 input / $0.10 output
        - qwen-plus:  $0.15 input / $0.40 output
        - qwen-max:   $0.40 input / $1.20 output
        """
        if "max" in self.model:
            input_price = 0.40 / 1_000_000
            output_price = 1.20 / 1_000_000
        elif "plus" in self.model:
            input_price = 0.15 / 1_000_000
            output_price = 0.40 / 1_000_000
        else:
            # turbo and any future models default to turbo pricing
            input_price = 0.05 / 1_000_000
            output_price = 0.10 / 1_000_000

        return (prompt_tokens * input_price) + (completion_tokens * output_price)

    async def embed(self, text: str, **kwargs: Any) -> EmbeddingResult:
        """Generate embedding using Qwen's embedding model.

        Uses DashScope's text-embedding-v3 by default (1024 dimensions).
        Override with model= and dimensions= kwargs.

        Args:
            text: The text to embed.
            **kwargs: Can include model and dimensions overrides.

        Returns:
            EmbeddingResult with the embedding vector.
        """
        model = kwargs.pop("model", "text-embedding-v3")
        dimensions = kwargs.pop(
            "dimensions",
            self.EMBEDDING_MODELS.get(model, 1024),
        )

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
        """Qwen text-embedding-v3: ~$0.0005 per 1K tokens."""
        return tokens * 0.0005 / 1_000
