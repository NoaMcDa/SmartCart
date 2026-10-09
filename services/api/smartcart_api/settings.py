"""API settings from the environment (pydantic-settings). Never commit real values.

| Variable | Default | Meaning |
|---|---|---|
| ``DATABASE_URL`` | none | Postgres connection string (service connection) |
| ``API_CORS_ORIGINS`` | ``http://localhost:3000`` | comma separated origins allowed by CORS |
| ``SUPABASE_JWT_SECRET`` | none | HS256 secret of the Supabase project; user routes return 503 without it |
| ``SUPABASE_JWT_AUDIENCE`` | ``authenticated`` | expected ``aud`` claim; empty disables the check |
| ``API_DB_USER_ROLE`` | ``smartcart_app`` | role switched to (SET LOCAL ROLE) for signed-in requests |
| ``API_POOL_MIN`` / ``API_POOL_MAX`` | 1 / 10 | connection pool size |
| ``API_WALK_TRANSIT_COST_PER_STORE`` | 11.0 | flat ILS per store visited on foot or by bus (estimate) |
| ``CART_HANDOFF_CHAINS`` | empty | comma separated chain ids whose "continue on the chain's site" handoff is on (#72); empty = all off |
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Annotated

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
    db_user_role: str = Field(default="smartcart_app", alias="API_DB_USER_ROLE")
    pool_min: int = Field(default=1, alias="API_POOL_MIN")
    pool_max: int = Field(default=10, alias="API_POOL_MAX")
    walk_transit_cost_per_store: Decimal = Field(
        default=Decimal("11.0"), alias="API_WALK_TRANSIT_COST_PER_STORE"
    )

    cart_handoff_chains: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="CART_HANDOFF_CHAINS"
    )

    @field_validator("cors_origins", "cart_handoff_chains", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
