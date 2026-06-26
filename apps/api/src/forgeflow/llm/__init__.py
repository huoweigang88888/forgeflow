"""
ForgeFlow AI - LLM Package.

Multi-provider LLM abstraction layer with:
- LLMProvider ABC + Factory pattern
- OpenAI, Anthropic, and Qwen (stub) providers
- ModelRouter for cost-optimized two-tier decisions
- LLMResilienceWrapper for 3-layer fallback protection
- Static fallback values for every agent node

Usage:
    from forgeflow.llm import LLMFactory

    provider = LLMFactory.create("openai", model="gpt-4o-mini")
    result = await provider.complete_structured(prompt, schema)
"""

from forgeflow.llm.base import LLMCallResult, LLMFactory, LLMProvider
from forgeflow.llm.fallbacks import (
    DEFAULT_FALLBACK,
    FALLBACK_DECISION,
    FALLBACK_INTENT,
    NODE_FALLBACKS,
)
from forgeflow.llm.providers.anthropic_provider import AnthropicProvider
from forgeflow.llm.providers.deepseek_provider import DeepSeekProvider

# Register all providers at import time
from forgeflow.llm.providers.openai_provider import OpenAIProvider
from forgeflow.llm.providers.qwen_provider import QwenProvider
from forgeflow.llm.resilience import LLMResilienceWrapper
from forgeflow.llm.router import ModelRouter

LLMFactory.register("openai", OpenAIProvider)
LLMFactory.register("anthropic", AnthropicProvider)
LLMFactory.register("qwen", QwenProvider)
LLMFactory.register("deepseek", DeepSeekProvider)

__all__ = [
    "DEFAULT_FALLBACK",
    "FALLBACK_DECISION",
    # Fallbacks
    "FALLBACK_INTENT",
    "NODE_FALLBACKS",
    "LLMCallResult",
    "LLMFactory",
    # Core
    "LLMProvider",
    # Resilience
    "LLMResilienceWrapper",
    # Routing
    "ModelRouter",
]
