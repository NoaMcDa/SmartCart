"""API settings from the environment (pydantic-settings). Never commit real values.

| Variable | Default | Meaning |
|---|---|---|
| ``DATABASE_URL`` | none | Postgres connection string (service connection) |
| ``API_CORS_ORIGINS`` | ``http://localhost:3000`` | comma separated origins allowed by CORS |
| ``SUPABASE_JWT_SECRET`` | none | HS256 secret of the Supabase project (the legacy signing key); the fallback for tokens signed with it. Unset it once the project signs with an asymmetric key |
| ``SUPABASE_JWKS_URL`` | derived | where the project publishes its public signing keys; defaults to ``$SUPABASE_URL/auth/v1/.well-known/jwks.json`` when ``SUPABASE_URL`` is set, else asymmetric tokens (ES256, RS256) are refused |
| ``SUPABASE_URL`` | none | the project URL (also used by ``DELETE /me``) |
| ``SUPABASE_JWKS_TTL_S`` / ``SUPABASE_JWKS_MIN_REFRESH_S`` | 600 / 30 | how long a fetched key set is trusted, and the least time between two fetches (an unknown ``kid`` refreshes at most this often) |
| ``SUPABASE_JWT_AUDIENCE`` | ``authenticated`` | expected ``aud`` claim; empty disables the check |
| ``SUPABASE_JWT_ISSUER`` | none | expected ``iss`` claim (``https://<project>.supabase.co/auth/v1``); unset skips the check |
| ``API_RATE_LIMIT`` | ``1`` | ``0`` switches the per-client request limits off (load tests) |
| ``API_RATE_LIMIT_BACKEND`` | ``memory`` | ``memory`` counts per process; ``postgres`` counts in the database, shared by every worker and replica (docs/security-review.md R3) |
| ``API_RATE_LIMIT_POOL_MAX`` | 3 | connections per process of the limiter's own pool (``postgres`` backend) |
| ``API_MAX_BODY_BYTES`` | 262144 | largest request body except ``/parse-image`` (own 8 MB cap) |
| ``API_DB_USER_ROLE`` | ``smartcart_app`` | role switched to (SET LOCAL ROLE) for signed-in requests |
| ``API_POOL_MIN`` / ``API_POOL_MAX`` | 1 / 10 | connection pool size |
| ``API_WALK_TRANSIT_COST_PER_STORE`` | 11.0 | flat ILS per store visited on foot or by bus (estimate) |
| ``CART_HANDOFF_CHAINS`` | empty | comma separated chain ids whose "continue on the chain's site" handoff is on (#72); empty = all off |
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_VERSION = "0.3.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"], alias="API_CORS_ORIGINS"
    )
    jwt_secret: str | None = Field(default=None, alias="SUPABASE_JWT_SECRET")
    jwt_audience: str | None = Field(default="authenticated", alias="SUPABASE_JWT_AUDIENCE")
    jwt_issuer: str | None = Field(default=None, alias="SUPABASE_JWT_ISSUER")
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    jwks_url_setting: str | None = Field(default=None, alias="SUPABASE_JWKS_URL")
    jwks_ttl_s: float = Field(default=600.0, alias="SUPABASE_JWKS_TTL_S", ge=1)
    jwks_min_refresh_s: float = Field(default=30.0, alias="SUPABASE_JWKS_MIN_REFRESH_S", ge=0)
    rate_limit_enabled: bool = Field(default=True, alias="API_RATE_LIMIT")
    rate_limit_backend: Literal["memory", "postgres"] = Field(
        default="memory", alias="API_RATE_LIMIT_BACKEND"
    )
    rate_limit_pool_max: int = Field(default=3, alias="API_RATE_LIMIT_POOL_MAX", ge=1)
    max_body_bytes: int = Field(default=256 * 1024, alias="API_MAX_BODY_BYTES")
    db_user_role: str = Field(default="smartcart_app", alias="API_DB_USER_ROLE")
    pool_min: int = Field(default=1, alias="API_POOL_MIN")
    pool_max: int = Field(default=10, alias="API_POOL_MAX")
    walk_transit_cost_per_store: Decimal = Field(
        default=Decimal("11.0"), alias="API_WALK_TRANSIT_COST_PER_STORE"
    )

    cart_handoff_chains: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="CART_HANDOFF_CHAINS"
    )

    @property
    def jwks_url(self) -> str | None:
        """The key set URL: the explicit setting, else the project's well-known path."""
        if self.jwks_url_setting and self.jwks_url_setting.strip():
            return self.jwks_url_setting.strip()
        base = (self.supabase_url or "").strip().rstrip("/")
        return f"{base}/auth/v1/.well-known/jwks.json" if base else None

    @field_validator("rate_limit_backend", mode="before")
    @classmethod
    def _backend(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("cors_origins", "cart_handoff_chains", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
