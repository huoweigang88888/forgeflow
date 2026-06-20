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

# Pre-load .env file explicitly — pydantic-settings env_file= may fail on
# Windows paths containing non-ASCII characters (e.g., Chinese).
_ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)


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
        env_file=".env",
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

    Usage:
        from forgeflow.core.config import get_settings
        settings = get_settings()
    """
    return Settings()
