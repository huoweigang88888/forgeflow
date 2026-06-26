"""
ForgeFlow AI - DeepSeek Provider.

DeepSeek API is fully OpenAI-compatible, so we extend OpenAIProvider
with a custom base_url. Supports deepseek-chat (V3) and deepseek-reasoner (R1).

NOTE: DeepSeek does NOT support response_format={"type": "json_object"}.
complete_structured() is overridden to request JSON via prompt instructions
instead of the API-level parameter.
"""

import json
import time
from typing import Any

from openai import AsyncOpenAI

from forgeflow.core.config import get_settings
from forgeflow.llm.base import EmbeddingResult, LLMCallResult
from forgeflow.llm.providers.openai_provider import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek provider — OpenAI-compatible API with custom base_url.

    Models:
    - deepseek-chat: General-purpose (DeepSeek-V3)
    - deepseek-reasoner: Reasoning-focused (DeepSeek-R1)
    """

    def __init__(self, model: str, **kwargs: Any):
        # Skip OpenAIProvider.__init__ to avoid creating a default AsyncOpenAI client
        # We must set our own client with DeepSeek's base_url.
        from forgeflow.llm.base import LLMProvider

        LLMProvider.__init__(self, model, **kwargs)  # type: ignore[arg-type]
        settings = get_settings()
        api_key = settings.llm.deepseek_api_key
        base_url = settings.llm.deepseek_base_url

        if api_key:
            self.client = AsyncOpenAI(
                api_key=api_key.get_secret_value(),
                base_url=base_url,
            )
        else:
            self.client = AsyncOpenAI(base_url=base_url)

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def complete_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        *,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        **kwargs: Any,
    ) -> LLMCallResult:
        """Request structured JSON output via prompt instructions.

        DeepSeek does not support ``response_format={"type": "json_object"}``,
        so we inject explicit JSON formatting instructions into the system
        message and parse the response manually.

        The outer LLMResilienceWrapper provides additional safety via
        regex extraction and fallback values if parsing still fails.
        """
        start_time = time.perf_counter()

        # Build a JSON schema description for the system message
        schema_desc = json.dumps(output_schema, indent=2)

        system_msg = (
            "You must respond with a single valid JSON object and nothing else. "
            "Do not include markdown fences, code blocks, or explanatory text. "
            "Your response must conform to this schema:\n"
            f"{schema_desc}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
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
            input_toks = usage.prompt_tokens if usage else 0
            output_toks = usage.completion_tokens if usage else 0
            cost = self._estimate_cost(
                prompt_tokens=input_toks,
                completion_tokens=output_toks,
            )

            return LLMCallResult(
                success=True,
                data=parsed,
                raw_response=raw,
                latency_ms=latency_ms,
                tokens_used=tokens,
                input_tokens=input_toks,
                output_tokens=output_toks,
                cost=cost,
            )

        except json.JSONDecodeError:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            # Save the raw text for the resilience wrapper's regex fallback
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
        """DeepSeek pricing (per 1M tokens).

        - deepseek-chat (V3): $0.27 input / $1.10 output
        - deepseek-reasoner (R1): $0.55 input / $2.19 output
        """
        if "reasoner" in self.model:
            input_price = 0.55 / 1_000_000
            output_price = 2.19 / 1_000_000
        else:
            input_price = 0.27 / 1_000_000
            output_price = 1.10 / 1_000_000

        return (prompt_tokens * input_price) + (completion_tokens * output_price)

    async def embed(self, text: str, **kwargs: Any) -> EmbeddingResult:
        """Embedding is not supported by DeepSeek.

        DeepSeek API is OpenAI-compatible for chat but does not offer
        an embeddings endpoint. Use OpenAI provider instead.
        """
        return EmbeddingResult(
            success=False,
            error="Embedding not supported by DeepSeek provider. Use OpenAI.",
        )
