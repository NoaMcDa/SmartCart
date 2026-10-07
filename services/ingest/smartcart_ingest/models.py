"""Internal model shared by every ingestion module.

These are the only types that cross module boundaries. Upstream library objects
(il_supermarket_scarper, il_supermarket_parsers) never leave the adapter layer.
All models are frozen pydantic v2 models.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FileKind = Literal["stores", "price_full", "price", "promo_full", "promo"]
"""Transparency file types. *_full are the daily complete files; price/promo are deltas."""

SchemaVersion = Literal["v1", "v2", "unknown"]
"""v1 = the 2015 regulation format; v2 = the consumer authority's improved reporting model
(rolling out through 2026); unknown = must not be loaded, raises an alert."""

Channel = Literal["physical", "online"]
Portal = Literal["cerberus", "shufersal", "matrix", "bina", "web", "other"]
RewardType = Literal["price", "percent", "buy_x_get_y", "bundle", "other"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RawFile(_Frozen):
    """One downloaded transparency file, before parsing."""

    chain_id: str
    store_code: str | None = None
    kind: FileKind
    published_at: datetime
    sha256: str = Field(min_length=64, max_length=64)
    path: str
    schema_version: SchemaVersion = "unknown"


class StoreRecord(_Frozen):
    chain_id: str
    store_code: str
    name: str
    address: str | None = None
    city: str | None = None
    lat: float | None = None
    lon: float | None = None
    channel: Channel = "physical"
    store_type: str | None = None
    """Raw StoreType from the Stores file, when the chain publishes one."""
    sub_chain_name: str | None = None
    """Raw SubChainName from the Stores file, when the chain publishes one."""


class ItemRecord(_Frozen):
    chain_id: str
    item_code: str
    barcode: str | None = None
    raw_name: str
    manufacturer: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    is_weighed: bool = False


class PriceRecord(_Frozen):
    chain_id: str
    store_code: str
    item_code: str
    price: Decimal
    unit_price: Decimal | None = None
    unit_of_measure: str | None = None
    observed_at: datetime


class PromoRecord(_Frozen):
    chain_id: str
    store_code: str
    promo_id: str
    description: str
    item_codes: list[str] = Field(default_factory=list)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    hours: str | None = None
    club_only: bool = False
    club_name: str | None = None
    min_qty: Decimal | None = None
    max_qty: Decimal | None = None
    reward_type: RewardType = "other"
    reward_value: Decimal | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ParsedFile(_Frozen):
    """The adapter's output: everything found in one file, in internal types."""

    raw: RawFile
    stores: list[StoreRecord] = Field(default_factory=list)
    items: list[ItemRecord] = Field(default_factory=list)
    prices: list[PriceRecord] = Field(default_factory=list)
    promos: list[PromoRecord] = Field(default_factory=list)
