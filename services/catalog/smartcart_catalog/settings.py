"""Catalog runtime configuration, read from environment variables (no .env file is read).

=========================  =======================  =========================================
Variable                   Default                  Meaning
=========================  =======================  =========================================
DATABASE_URL               (none)                   Postgres DSN
ANTHROPIC_API_KEY          (none)                   needed only for EXTRACTOR=claude
EXTRACTOR                  rule                     rule | claude
EXTRACTION_MODEL           claude-sonnet-5-5        model for EXTRACTOR=claude (decision D14)
EXTRACTION_BATCH_SIZE      500                      items per Message Batch / per DB round trip
EXTRACTION_MAX_TOKENS      1024                     max_tokens per item request
EXTRACTION_EFFORT          low                      output_config.effort per item request
EXTRACTION_POLL_SECONDS    60                       batch status poll interval
EXTRACTION_MAX_ATTEMPTS    3                        retries before an item is marked failed
CATALOG_DATA_DIR           <repo>/data              taxonomy, rules and canonicals YAML
=========================  =======================  =========================================
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from smartcart_catalog.taxonomy import default_data_dir


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    database_url: str | None = None
    anthropic_api_key: SecretStr | None = None
    extractor: Literal["rule", "claude"] = "rule"
    extraction_model: str = "claude-sonnet-5-5"
    extraction_batch_size: int = Field(default=500, ge=1, le=100_000)
    extraction_max_tokens: int = Field(default=1024, ge=256)
    extraction_effort: Literal["low", "medium", "high"] = "low"
    extraction_poll_seconds: float = Field(default=60, gt=0)
    extraction_max_attempts: int = Field(default=3, ge=1)
    catalog_data_dir: Path = Field(default_factory=default_data_dir)

    @field_validator("database_url", "anthropic_api_key", mode="before")
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


def load_settings(**overrides: object) -> Settings:
    """Read the environment; keyword arguments win over it (used by tests)."""
    return Settings(**overrides)  # type: ignore[arg-type]
