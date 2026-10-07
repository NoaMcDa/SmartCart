"""Runtime configuration, read from environment variables.

Variable names match ``.env.example`` (DATABASE_URL, S3_*) and add the ingestion knobs listed in
``docs/ingestion.md``. On the VPS they come from ``/etc/smartcart/ingest.env`` through the systemd
units; no ``.env`` file is read, so a developer's local file cannot leak into tests.

Per-chain overrides are JSON objects keyed by chain id::

    QUALITY_OVERRIDES='{"7290027600007": {"price_jump_factor": 4}}'
    DELTA_INTERVAL_MINUTES='{"7290058140886": 120}'
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class Thresholds:
    """Quality-gate thresholds for one chain (issue #42), plus the soft warnings' (issue #16)."""

    stale_file_max_age_hours: float
    price_jump_factor: float
    item_count_drop_ratio: float
    gap_report_pressure_min: int = 3
    """Confirmed price mismatches reported for a store in 7 days before a warning; 0 disables."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    # --- database ------------------------------------------------------------------------------
    database_url: str | None = None

    # --- raw archive: a local directory, or S3/R2 when S3_BUCKET is set ----------------------------
    raw_store_path: Path | None = None
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # --- alerts ---------------------------------------------------------------------------------
    alert_webhook_url: str | None = None

    # --- quality gates (defaults from issue #42) -------------------------------------------------
    stale_file_max_age_hours: float = Field(default=36, gt=0)
    price_jump_factor: float = Field(default=3, gt=1)
    item_count_drop_ratio: float = Field(default=0.5, ge=0, le=1)
    quality_overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    # soft warning, never quarantines (issue #16); the default is a placeholder, not a decision
    gap_report_pressure_min: int = Field(default=3, ge=0)

    # --- scheduler and portal backoff (issue #49) ------------------------------------------------
    delta_interval_minutes: dict[str, int] = Field(default_factory=dict)
    portal_max_attempts: int = Field(default=5, ge=1)
    portal_backoff_base_seconds: float = Field(default=2.0, ge=0)
    portal_backoff_cap_seconds: float = Field(default=120.0, ge=0)

    @field_validator(
        "database_url",
        "s3_endpoint_url",
        "s3_bucket",
        "s3_region",
        "s3_access_key_id",
        "s3_secret_access_key",
        "alert_webhook_url",
        "raw_store_path",
        mode="before",
    )
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        # .env.example lists names with empty values; an empty string means "not configured".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("quality_overrides")
    @classmethod
    def _known_threshold_names(cls, value: dict[str, dict[str, float]]) -> dict:
        allowed = {
            "stale_file_max_age_hours",
            "price_jump_factor",
            "item_count_drop_ratio",
            "gap_report_pressure_min",
        }
        for chain_id, overrides in value.items():
            unknown = set(overrides) - allowed
            if unknown:
                raise ValueError(f"unknown threshold(s) for chain {chain_id}: {sorted(unknown)}")
        return value

    def thresholds_for(self, chain_id: str) -> Thresholds:
        """Global defaults, overridden by ``QUALITY_OVERRIDES[chain_id]`` when present."""
        base = {
            "stale_file_max_age_hours": self.stale_file_max_age_hours,
            "price_jump_factor": self.price_jump_factor,
            "item_count_drop_ratio": self.item_count_drop_ratio,
            "gap_report_pressure_min": self.gap_report_pressure_min,
        }
        base.update(self.quality_overrides.get(chain_id, {}))
        return Thresholds(
            stale_file_max_age_hours=float(base["stale_file_max_age_hours"]),
            price_jump_factor=float(base["price_jump_factor"]),
            item_count_drop_ratio=float(base["item_count_drop_ratio"]),
            gap_report_pressure_min=int(base["gap_report_pressure_min"]),
        )


def load_settings(**overrides: object) -> Settings:
    """Read the environment; keyword arguments win over it (used by tests)."""
    return Settings(**overrides)  # type: ignore[arg-type]
