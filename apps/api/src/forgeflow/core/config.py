"""
ForgeFlow AI - Application Configuration.

Uses pydantic-settings for type-safe, environment-variable-driven configuration.
All settings are loaded from environment variables or .env file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── .env file discovery (deferred to first get_settings() call) ──
# The .env file lives at the monorepo root (forgeflow/.env).
# We compute the path once, but only load it inside get_settings()
# to avoid filesystem access at module import time.

_ENV_PATH: Path | None = None


def _find_env_path() -> Path:
    """Find the .env file relative to this source file.

    Walks up from config.py to the monorepo root.
    Cached after first call.
    """
    global _ENV_PATH
    if _ENV_PATH is not None:
        return _ENV_PATH
    candidate = Path(__file__).resolve().parent.parent.parent.parent.parent.parent / ".env"
    _ENV_PATH = candidate if candidate.exists() else Path("/nonexistent/.env")
    return _ENV_PATH


def _load_env_if_present() -> None:
    """Load .env if it exists (called once inside get_settings)."""
    env_path = _find_env_path()
    if env_path.exists():
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    url: str = "postgresql+asyncpg://forgeflow:forgeflow_dev@localhost:5432/forgeflow"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class LLMSettings(BaseSettings):
    """LLM provider settings."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    default_provider: Literal["openai", "anthropic", "qwen", "deepseek"] = "deepseek"
    default_model: str = "deepseek-chat"
    complex_model: str = "deepseek-chat"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    qwen_api_key: SecretStr | None = None
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    embedding_provider: Literal["openai"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Agent thresholds
    auto_refund_threshold: float = 50.0
    similarity_threshold: float = 0.85


class Settings(BaseSettings):
    """Root settings — all configuration flows from here."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: SecretStr = SecretStr("change-me-in-production")

    database: DatabaseSettings = DatabaseSettings()
    llm: LLMSettings = LLMSettings()

    redis_url: str = "redis://:redis_dev@localhost:6379/0"

    # Observability
    sentry_dsn: str | None = None
    otel_endpoint: str | None = None

    # ── Security ──
    cors_origins: str = "http://localhost:3000"  # Comma-separated allowed origins
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60  # Per-tenant requests per minute
    rate_limit_per_ip_minute: int = 120  # Per-IP requests per minute

    # ── Shopify OAuth ──
    shopify_client_id: str = ""
    shopify_client_secret: SecretStr = SecretStr("")
    shopify_scopes: str = "read_orders,write_orders,read_customers,read_fulfillments"
    shopify_oauth_redirect_uri: str = "http://localhost:3000/auth/shopify/callback"

    # ── Amazon SP-API (Phase 2: IAM + STS for write operations) ──
    amazon_iam_access_key: str = ""
    amazon_iam_secret_key: str = ""
    amazon_role_arn: str = ""

    # ── Notifications (SendGrid / Twilio) ──
    sendgrid_api_key: SecretStr = SecretStr("")
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_from_number: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def validate_debug(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return False


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton.

    Loads .env file on first call, then caches the Settings instance.
    All subsequent calls return the cached singleton.

    Usage:
        from forgeflow.core.config import get_settings
        settings = get_settings()
    """
    _load_env_if_present()
    return Settings()
