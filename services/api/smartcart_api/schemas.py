"""Request and response models: the contract between the API and the web app.

The web app generates TypeScript types from the OpenAPI document this module produces
(apps/web/src/api/openapi.json). Change these models only together with that file.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FlexLevel = Literal["exact", "any_brand", "close"]
TravelMode = Literal["car", "walk_transit", "delivery"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- parse-list ------------------------------------------------------------------------------

class ParseListRequest(_Model):
    text: str = Field(min_length=1, max_length=4000, description="Free text, Hebrew, comma or newline separated")
    flex_defaults: dict[str, FlexLevel] = Field(default_factory=dict, description="taxonomy_id -> flex level")


class CanonicalRef(_Model):
    canonical_id: int
    display_name_he: str
    taxonomy_id: str
    base_unit: Literal["100g", "100ml", "unit", "kg"]


class ParsedRow(_Model):
    input_text: str
    canonical: CanonicalRef | None = None
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    flex_level: FlexLevel = "any_brand"
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool
    candidates: list[CanonicalRef] = Field(default_factory=list, description="Alternatives when confidence is low")
    not_found: bool = False
    is_weighed: bool = False


class ParseListResponse(_Model):
    rows: list[ParsedRow]
    generated_at: datetime


# --- search ----------------------------------------------------------------------------------

class SearchHit(_Model):
    canonical: CanonicalRef
    score: float
    matched_by: list[Literal["trigram", "fts", "vector"]]


class SearchResponse(_Model):
    query: str
    hits: list[SearchHit]


# --- compare ---------------------------------------------------------------------------------

class BasketItem(_Model):
    canonical_id: int
    quantity: Decimal = Field(gt=0)
    flex_level: FlexLevel = "any_brand"
    exact_item_id: int | None = Field(default=None, description="Required when flex_level is exact")


class Location(_Model):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    radius_m: int = Field(default=5000, ge=500, le=15000)


class CompareRequest(_Model):
    items: list[BasketItem] = Field(min_length=1, max_length=200)
    location: Location
    clubs: list[str] = Field(default_factory=list)
    home_store_id: int | None = Field(default=None, description="The user's usual store; savings are measured against it only")
    include_online: bool = False


class AttributeTag(_Model):
    key: str
    value: str | None = None
    status: Literal["matched", "differs", "unverified"]


class PricedItem(_Model):
    canonical_id: int
    item_id: int
    display_name_he: str
    quantity: Decimal
    shelf_price: Decimal
    effective_unit_price: Decimal
    uom: str
    line_total: Decimal
    is_substitute: bool
    is_estimated: bool = Field(default=False, description="Weighed goods")
    promo_description: str | None = None
    club_required: bool = False
    club_name: str | None = None
    price_valid_from: datetime
    confidence: float | None = Field(default=None, description="Match confidence when is_substitute")
    tags: list[AttributeTag] = Field(default_factory=list)
    original_item_id: int | None = None


class StoreResult(_Model):
    store_id: int
    chain_id: str
    chain_name: str
    store_name: str
    city: str | None = None
    distance_m: int
    channel: Literal["physical", "online"]
    total: Decimal
    found_count: int
    missing: list[int] = Field(description="canonical_ids not available at this store; never ignored")
    substituted_count: int
    items: list[PricedItem]
    prices_updated_at: datetime
    saving_vs_home: Decimal | None = Field(default=None, description="Positive means cheaper than the home store; null when no home store")


class CompareResponse(_Model):
    stores: list[StoreResult] = Field(description="Sorted: complete baskets first, then by total")
    home_store_id: int | None
    home_store_total: Decimal | None
    generated_at: datetime
    disclaimer_he: str = "המחיר הקובע הוא בקופה."


# --- optimize --------------------------------------------------------------------------------

class TravelSettings(_Model):
    mode: TravelMode = "car"
    cost_per_km: Decimal = Field(default=Decimal("1.2"), ge=0)
    extra_stop_value: Decimal = Field(default=Decimal(25), ge=0, le=50, description="What one more stop is worth to the user, ILS")


class OptimizeRequest(CompareRequest):
    max_stores: int = Field(default=2, ge=1, le=3)
    min_split_saving: Decimal = Field(default=Decimal(25), ge=0, description="A split is recommended only above this net saving")
    travel: TravelSettings = Field(default_factory=TravelSettings)


class SavingBreakdown(_Model):
    basket_saving: Decimal = Field(description="Home store total minus this plan's basket total")
    travel_cost: Decimal
    extra_stop_cost: Decimal
    net_saving: Decimal = Field(description="basket_saving - travel_cost - extra_stop_cost; the hero number")


class StoreAssignment(_Model):
    store: StoreResult
    item_ids: list[int] = Field(description="item ids bought at this store")


class Plan(_Model):
    kind: Literal["single", "split", "minimum_effort"]
    stores: list[StoreAssignment]
    total: Decimal
    extra_minutes: int = 0
    breakdown: SavingBreakdown | None = Field(default=None, description="null when there is no home store to compare with")
    recommended: bool
    missing: list[int] = Field(default_factory=list)
    substituted_count: int = 0


class OptimizeResponse(_Model):
    single: Plan
    split: Plan | None = Field(default=None, description="null when no split beats min_split_saving")
    minimum_effort: Plan | None = Field(default=None, description="The home store itself; null without a home store")
    subsets_evaluated: int
    generated_at: datetime
    disclaimer_he: str = "המחיר הקובע הוא בקופה."


# --- feedback --------------------------------------------------------------------------------

class SubstitutionFeedbackRequest(_Model):
    canonical_id: int
    original_item_id: int | None = None
    substitute_item_id: int
    verdict: Literal["not_good", "kept_original", "accepted"]


class GapReportRequest(_Model):
    store_id: int
    item_id: int | None = None
    canonical_id: int | None = None
    shown_price: Decimal | None = None
    actual_price: Decimal | None = None
    note: str | None = Field(default=None, max_length=500)


class Ack(_Model):
    ok: bool = True
    id: int | None = None


class Health(_Model):
    status: Literal["ok"]
    version: str
