"""Runtime configuration, read from environment variables.

Variable names match ``.env.example`` (DATABASE_URL, S3_*) and add the ingestion knobs listed in
``docs/ingestion.md``. On the VPS they come from ``/etc/smartcart/ingest.env`` through the systemd
units; no ``.env`` file is read, so a developer's local file cannot leak into tests.

Per-chain overrides are JSON objects keyed by chain id::

    QUALITY_OVERRIDES='{"7290027600007": {"price_jump_factor": 4, "stale_stores_max_age_hours": 336}}'
    DELTA_INTERVAL_MINUTES='{"7290058140886": 120}'
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Estimates, not measured values: see docs/ingestion.md, "Quality gates".
DEFAULT_STALE_STORES_HOURS = 240.0
DEFAULT_PRICE_DROP_FACTOR = 8.0
DEFAULT_PRICE_DROP_MIN_PREVIOUS = 1.0


@dataclass(frozen=True)
class Thresholds:
    """Quality-gate thresholds for one chain (issue #42), plus the soft warnings' (issue #16)."""

    stale_file_max_age_hours: float
    price_jump_factor: float
    item_count_drop_ratio: float
    gap_report_pressure_min: int = 3
    """Confirmed price mismatches reported for a store in 7 days before a warning; 0 disables."""
    stale_stores_max_age_hours: float = DEFAULT_STALE_STORES_HOURS
    """Stale limit of a Stores file. Chains publish the store list much less often than prices
    (the newest Stores file on four Cerberus portals was 60 to 68 hours old on 2026-10-21), so
    it has its own, longer limit; ``stale_file_max_age_hours`` covers every other kind."""
    price_drop_factor: float = DEFAULT_PRICE_DROP_FACTOR
    """A price below the previous price divided by this factor fails the file; 0 disables."""
    price_drop_min_previous: float = DEFAULT_PRICE_DROP_MIN_PREVIOUS
    """The drop gate ignores items whose previous price is below this many shekels."""


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
    # a Stores file is published much less often than prices (#60): its own, longer stale limit
    stale_stores_max_age_hours: float = Field(default=DEFAULT_STALE_STORES_HOURS, gt=0)
    # a price below previous / factor quarantines the file (shekels read as agorot); 0 disables
    price_drop_factor: float = Field(default=DEFAULT_PRICE_DROP_FACTOR, ge=0)
    price_drop_min_previous: float = Field(default=DEFAULT_PRICE_DROP_MIN_PREVIOUS, ge=0)
    # soft warning, never quarantines (issue #16); the default is a placeholder, not a decision
    gap_report_pressure_min: int = Field(default=3, ge=0)

    # --- scheduler and portal backoff (issue #49) ------------------------------------------------
    delta_interval_minutes: dict[str, int] = Field(default_factory=dict)
    portal_max_attempts: int = Field(default=5, ge=1)
    portal_backoff_base_seconds: float = Field(default=2.0, ge=0)
    portal_backoff_cap_seconds: float = Field(default=120.0, ge=0)
    # Time budgets in the download path (#60). One request (a listing, which is a whole scrape
    # upstream, or a fetch) never runs longer than the request timeout, and a chain's whole run
    # (listing, downloads, backoff sleeps) never longer than its budget; a chain that runs out is
    # reported and the next one starts. ``None`` takes the per-mode default in scheduler.py.
    portal_request_timeout_seconds: float = Field(default=900.0, gt=0)
    chain_budget_seconds: float | None = Field(default=None, gt=0)
    # The whole run, so it ends by itself before the systemd unit's TimeoutStartSec kills it.
    run_budget_seconds: float | None = Field(default=None, gt=0)

    # --- late full files (#60) -------------------------------------------------------------------
    # A chain counts as complete for the day when it has loaded at least this share of the
    # PriceFull and PromoFull files it loaded the day before (scheduler.pending_full_chains).
    late_full_complete_ratio: float = Field(default=0.98, gt=0, le=1)
    # ``run --mode late`` touches this file when it loaded a PriceFull or PromoFull; the late
    # precompute unit runs only while it exists (infra/vps/smartcart-precompute-late.service).
    late_load_marker: Path | None = None

    @field_validator(
        "database_url",
        "s3_endpoint_url",
        "s3_bucket",
        "s3_region",
        "s3_access_key_id",
        "s3_secret_access_key",
        "alert_webhook_url",
        "raw_store_path",
        "late_load_marker",
        "chain_budget_seconds",
        "run_budget_seconds",
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
            "stale_stores_max_age_hours",
            "price_drop_factor",
            "price_drop_min_previous",
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
            "stale_stores_max_age_hours": self.stale_stores_max_age_hours,
            "price_drop_factor": self.price_drop_factor,
            "price_drop_min_previous": self.price_drop_min_previous,
        }
        base.update(self.quality_overrides.get(chain_id, {}))
        return Thresholds(
            stale_file_max_age_hours=float(base["stale_file_max_age_hours"]),
            price_jump_factor=float(base["price_jump_factor"]),
            item_count_drop_ratio=float(base["item_count_drop_ratio"]),
            gap_report_pressure_min=int(base["gap_report_pressure_min"]),
            stale_stores_max_age_hours=float(base["stale_stores_max_age_hours"]),
            price_drop_factor=float(base["price_drop_factor"]),
            price_drop_min_previous=float(base["price_drop_min_previous"]),
        )


def load_settings(**overrides: object) -> Settings:
    """Read the environment; keyword arguments win over it (used by tests)."""
    return Settings(**overrides)  # type: ignore[arg-type]
