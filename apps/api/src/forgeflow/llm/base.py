"""
ForgeFlow AI - LLM Provider Abstraction.

Defines the abstract interface for all LLM providers and a factory
for instantiation. This is the single most important architectural
decision in Phase 0 — it sets the pattern for all external integrations.

Design principles:
1. NOT dependent on LangChain's BaseChatModel (too heavy/opinionated)
2. Two calling modes: complete() for text, complete_structured() for JSON
3. Factory pattern for provider discovery and instantiation
4. All providers return standardized LLMCallResult for telemetry
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class LLMCallResult:
    """Standardized result from any LLM provider call.

    This is the universal return type that all providers must produce.
    It enables consistent telemetry, cost tracking, and fallback handling
    regardless of which provider was used.
    """

    success: bool
    data: dict[str, Any] | None = None
    raw_response: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    retry_count: int = 0
    latency_ms: int = 0
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


@dataclass
class EmbeddingResult:
    """Standardized result from an embedding provider call.

    Separate from LLMCallResult because embeddings have a different
    output shape (vector instead of text/JSON).
    """

    success: bool
    embedding: list[float] | None = None
    dimensions: int = 0
    tokens_used: int = 0
    cost: float = 0.0
    latency_ms: int = 0
    error: str | None = None


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.

    To add a new provider (e.g., DeepSeek, Qwen):
    1. Subclass LLMProvider
    2. Implement complete() and complete_structured()
    3. Register with LLMFactory.register("name", YourProvider)

    Example:
        LLMFactory.create("openai", model="gpt-4o-mini")
        LLMFactory.create("anthropic", model="claude-haiku-4-5-20251001")
    """

    def __init__(self, model: str, **kwargs: Any):
        self.model = model
        self.kwargs = kwargs

    @abstractmethod
    async def complete(self, prompt: str, **kwargs: Any) -> str:
        """Send a prompt and return raw text completion.

        Args:
            prompt: The full prompt string to send.
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Raw text response from the LLM.
        """
        ...

    @abstractmethod
    async def complete_structured(
        self,
        prompt: str,
        output_schema: dict[str, Any],
        **kwargs: Any,
    ) -> LLMCallResult:
        """Send a prompt and return structured (JSON) output.

        Args:
            prompt: The full prompt string to send.
            output_schema: JSON Schema for the expected output.
            **kwargs: Provider-specific parameters.

        Returns:
            LLMCallResult with parsed data, tokens, cost, and timing.
        """
        ...

    @abstractmethod
    async def embed(self, text: str, **kwargs: Any) -> EmbeddingResult:
        """Generate an embedding vector for the given text.

        Args:
            text: The text to embed.
            **kwargs: Provider-specific parameters (model override, etc.)

        Returns:
            EmbeddingResult with the embedding vector, token usage, and cost.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier: 'openai', 'anthropic', etc."""
        ...

    def __repr__(self) -> str:
        return f"{self.provider_name}:{self.model}"


class LLMFactory:
    """Factory for creating LLM provider instances.

    Providers register themselves at import time. Usage:

        provider = LLMFactory.create("openai", model="gpt-4o-mini")
        result = await provider.complete_structured(prompt, schema)
    """

    _registry: ClassVar[dict[str, type[LLMProvider]]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[LLMProvider]) -> None:
        """Register a provider class.

        Args:
            name: Provider identifier (e.g., 'openai', 'anthropic').
            provider_cls: Provider class (must subclass LLMProvider).

        Raises:
            ValueError: If the name is already registered.
        """
        if name in cls._registry:
            raise ValueError(f"Provider '{name}' already registered")
        if not issubclass(provider_cls, LLMProvider):
            raise TypeError(f"{provider_cls} must subclass LLMProvider")
        cls._registry[name] = provider_cls

    @classmethod
    def create(cls, provider: str, model: str, **kwargs: Any) -> LLMProvider:
        """Create a provider instance.

        Args:
            provider: Provider name ('openai', 'anthropic', 'qwen').
            model: Model name/ID for this provider.
            **kwargs: Additional provider-specific arguments.

        Returns:
            Configured LLMProvider instance.

        Raises:
            ValueError: If the provider is not registered.
        """
        if provider not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(f"Unknown provider '{provider}'. Available: {available}")
        return cls._registry[provider](model=model, **kwargs)

    @classmethod
    def available_providers(cls) -> list[str]:
        """Return list of registered provider names."""
        return list(cls._registry.keys())
