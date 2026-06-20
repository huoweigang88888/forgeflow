"""
ForgeFlow AI - Provider Registry.

Global registry that maps platform names to their Provider implementations.
The Agent Runtime uses this to resolve the correct provider for each tenant.

From PRD Section 17.3: Provider Registry.
"""

from typing import Any

from forgeflow.providers.base import PlatformProvider


class ProviderRegistry:
    """Registry for platform provider implementations.

    Providers register at import time. The runtime resolves the correct
    provider instance based on the tenant's platform.

    Usage:
        # Registration (at import time)
        ProviderRegistry.register("shopify", ShopifyProvider)
        ProviderRegistry.register("woocommerce", WooCommerceProvider)

        # Resolution (at runtime)
        provider = ProviderRegistry.get("shopify", api_key=..., domain=...)
        order = await provider.get_order("12345")
    """

    _providers: dict[str, type[PlatformProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[PlatformProvider]) -> None:
        """Register a platform provider class.

        Args:
            name: Platform identifier ('shopify', 'woocommerce', 'amazon').
            provider_cls: Provider class implementing PlatformProvider.

        Raises:
            ValueError: If the platform name is already registered.
            TypeError: If provider_cls doesn't implement PlatformProvider.
        """
        if name in cls._providers:
            raise ValueError(
                f"Provider '{name}' already registered. "
                f"Available: {list(cls._providers.keys())}"
            )
        if not issubclass(provider_cls, PlatformProvider):
            raise TypeError(
                f"{provider_cls.__name__} must implement PlatformProvider"
            )
        cls._providers[name] = provider_cls

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> PlatformProvider:
        """Get a configured provider instance.

        Args:
            name: Platform identifier.
            **kwargs: Constructor arguments for the provider.

        Returns:
            Configured PlatformProvider instance.

        Raises:
            ValueError: If the platform is not registered.
        """
        if name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(
                f"Unknown platform '{name}'. "
                f"Available providers: {available}"
            )
        return cls._providers[name](**kwargs)

    @classmethod
    def available_platforms(cls) -> list[str]:
        """Return list of all registered platform names."""
        return list(cls._providers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a platform is registered."""
        return name in cls._providers
