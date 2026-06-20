"""
ForgeFlow AI - Providers Package.

Multi-platform abstraction layer with:
- Abstract base classes (OrderProvider, LogisticsProvider, NotificationProvider)
- Normalized DTOs (OrderInfo, RefundResult, TrackingInfo)
- Provider registry for platform routing
- Shopify provider (stub in Phase 0, full in Phase 1)
- Mock provider for testing

Usage:
    from forgeflow.providers import ProviderRegistry, MockPlatformProvider

    # In tests:
    mock = MockPlatformProvider()
    order = await mock.get_order("test_123")

    # In production (Phase 1+):
    provider = ProviderRegistry.get("shopify", shop_domain="...", access_token="...")
"""

from forgeflow.providers.base import (
    LogisticsProvider,
    NotificationProvider,
    OrderProvider,
    PlatformProvider,
)
from forgeflow.providers.dto import OrderInfo, RefundResult, TrackingInfo
from forgeflow.providers.mock import MockPlatformProvider
from forgeflow.providers.registry import ProviderRegistry

# Register providers
from forgeflow.providers.shopify.client import ShopifyProvider

ProviderRegistry.register("shopify", ShopifyProvider)
ProviderRegistry.register("mock", MockPlatformProvider)

__all__ = [
    # Interfaces
    "OrderProvider",
    "LogisticsProvider",
    "NotificationProvider",
    "PlatformProvider",
    # DTOs
    "OrderInfo",
    "RefundResult",
    "TrackingInfo",
    # Registry
    "ProviderRegistry",
    # Implementations
    "ShopifyProvider",
    "MockPlatformProvider",
]
