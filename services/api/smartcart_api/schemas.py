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
    category_path_he: list[str] = Field(default_factory=list, description="Taxonomy names, root first")


class ParsedRow(_Model):
    input_text: str
    canonical: CanonicalRef | None = None
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    unit: Literal["kg"] | None = Field(default=None, description='"kg" when the user gave a weight; quantity is then in kg')
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
    score: float = Field(description="Reciprocal rank fusion score, normalized to [0, 1]")
    matched_by: list[Literal["trigram", "fts", "vector"]]
    confidence: float | None = Field(default=None, ge=0, le=1, description="Evidence for this hit; the parser's thresholds use it")


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
    promo_min_qty: Decimal | None = Field(default=None, description="Quantity the promo needs (2 for 1+1)")
    promo_applied: bool = Field(default=False, description="The requested quantity reaches the promo")
    promo_add_qty: Decimal | None = Field(default=None, description="Add this many to complete the promo")
    promo_add_saving: Decimal | None = Field(default=None, description="What completing the promo saves versus the shelf price")
    club_required: bool = False
    club_name: str | None = None
    price_valid_from: datetime
    confidence: float | None = Field(default=None, description="Match confidence when is_substitute")
    tags: list[AttributeTag] = Field(default_factory=list)
    original_item_id: int | None = None
    promo_confidence: float | None = Field(default=None, ge=0, le=1, description="Confidence that the promo was parsed correctly; null when unknown")
    club_offer_name: str | None = Field(default=None, description="A club deal on this line for a club the user did not mark; information only, never in a total or saving")
    club_offer_discount: Decimal | None = Field(default=None, description="What club_offer_name would save on this line, ILS; information only")


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
    lat: float | None = Field(default=None, description="Store latitude when known (phase 2)")
    lon: float | None = Field(default=None, description="Store longitude when known (phase 2)")


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
    candidate_stores: int = Field(default=10, ge=1, le=15, description="N nearest stores the subsets are drawn from")
    min_split_saving: Decimal = Field(default=Decimal(25), ge=0, description="A split is recommended only above this net saving")
    travel: TravelSettings = Field(default_factory=TravelSettings)
    solver: Literal["heuristic", "milp"] = Field(default="heuristic", description="milp handles cross-item promos and quantity rounding (phase 2)")


class PromoBundle(_Model):
    promo_description: str
    bundle_count: int = Field(ge=1)
    saving: Decimal
    add_qty: Decimal | None = Field(default=None, description="Quantity to add to complete one more bundle")


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
    travel_cost: Decimal = Field(default=Decimal(0), description="Round-trip travel to this plan's stores, ILS")
    extra_minutes: int = 0
    breakdown: SavingBreakdown | None = Field(default=None, description="null when there is no home store to compare with")
    recommended: bool
    missing: list[int] = Field(default_factory=list)
    substituted_count: int = 0
    promo_bundles: list[PromoBundle] = Field(default_factory=list, description="Cross-item promos the MILP solver exploited")


class OptimizeResponse(_Model):
    single: Plan
    split: Plan | None = Field(default=None, description="null when no split beats min_split_saving")
    minimum_effort: Plan | None = Field(default=None, description="The home store itself; null without a home store")
    subsets_evaluated: int
    solver: Literal["heuristic", "milp"] = "heuristic"
    generated_at: datetime
    disclaimer_he: str = "המחיר הקובע הוא בקופה."


# --- feedback --------------------------------------------------------------------------------

class SubstitutionFeedbackRequest(_Model):
    canonical_id: int
    original_item_id: int | None = None
    substitute_item_id: int
    verdict: Literal["not_good", "kept_original", "accepted"]
    source: Literal["substitution_card", "swap"] = Field(
        default="substitution_card",
        description="Where the verdict came from: the substitution card, or the smart-cart swap "
        "(apply = accepted, undo = kept_original, dismiss = not_good)",
    )
    list_item_id: int | None = None
    flex_level: FlexLevel | None = None
    match_confidence: float | None = Field(default=None, ge=0, le=1)


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


# --- signed-in user (Supabase JWT, row-level security) -----------------------------------------

class ProfileUpdate(_Model):
    home_store_id: int | None = None
    radius_m: int = Field(default=5000, ge=500, le=15000)
    neighborhood_lat: float | None = Field(default=None, ge=-90, le=90, description="Stored rounded to 3 decimals (about 100 m)")
    neighborhood_lon: float | None = Field(default=None, ge=-180, le=180)
    travel_mode: TravelMode = "car"
    cost_per_km: Decimal = Field(default=Decimal("1.2"), ge=0)
    extra_stop_value: Decimal = Field(default=Decimal(25), ge=0, le=50)
    max_stores: int = Field(default=2, ge=1, le=3)
    clubs: list[str] = Field(default_factory=list)
    diet_flags: list[str] = Field(default_factory=list)
    kosher_level: str | None = None
    flex_defaults: dict[str, FlexLevel] = Field(default_factory=dict)
    theme: Literal["system", "light", "dark"] = "system"
    consent_location: bool = Field(default=False, description="Required to store a neighborhood location")


class Profile(ProfileUpdate):
    user_id: str
    exists: bool = Field(description="false when nothing is stored yet and these are the defaults")


class ListItemIn(_Model):
    canonical_id: int | None = None
    input_text: str | None = Field(default=None, max_length=200)
    quantity: Decimal = Field(default=Decimal(1), gt=0)
    flex_level: FlexLevel = "any_brand"
    confirmed: bool = True
    checked: bool = Field(default=False, description="Ticked off in the store (shared lists, #101)")


class ListItem(ListItemIn):
    id: int
    sort: int


class ShoppingListIn(_Model):
    name: str = Field(min_length=1, max_length=100)
    is_recurring: bool = False
    items: list[ListItemIn] = Field(default_factory=list, max_length=200)


class ShoppingList(_Model):
    id: int
    name: str
    is_recurring: bool
    items: list[ListItem]
    created_at: datetime
    updated_at: datetime
    shared: bool = Field(
        default=False, description="true when another user owns the list and shared it with you"
    )
    role: Literal["owner", "editor", "viewer"] = Field(
        default="owner",
        description="Your access: owner, or your role as a member (editors change items, viewers "
        "only read)",
    )


class Health(_Model):
    status: Literal["ok"]
    version: str


# --- first-party events (closed beta, issue #40) ---------------------------------------------

EventName = Literal[
    "app_opened",
    "page_viewed",
    "list_pasted",
    "results_shown",
    "substitutions_shown",
    "substitution_verdict",
    "flex_changed",
    "split_viewed",
    "gap_reported",
    # phase 2 surfaces (issues #101, #102)
    "scan_started",
    "scan_completed",
    "alert_created",
    "swap_applied",
    "swap_undone",
    "swap_dismissed",
    "list_shared",
    "share_accepted",
]


class EventIn(_Model):
    name: EventName
    props: dict[str, int | str] = Field(
        default_factory=dict,
        description="Allowlisted keys per event name, values are integers or members of a fixed set; "
        "anything else is rejected with 422 (no free text, no personal data). See docs/beta-plan.md.",
    )
    session_id: str = Field(
        pattern=r"^[A-Za-z0-9_-]{8,64}$",
        description="Random id the browser keeps in localStorage; not derived from the person",
    )


class EventsRequest(_Model):
    events: list[EventIn] = Field(min_length=1, max_length=50)


class EventsAck(_Model):
    ok: bool = True
    accepted: int


# --- phase 2 contracts (issues #13, #23, #28, #34, #39, #45, #90) ----------------------------

class StoreRef(_Model):
    store_id: int
    chain_id: str
    chain_name: str
    store_name: str
    city: str | None = None
    distance_m: int | None = None
    lat: float | None = None
    lon: float | None = None
    channel: Literal["physical", "online"] = "physical"


class PricePoint(_Model):
    date: datetime
    unit_price: Decimal
    shelf_price: Decimal | None = None
    store_id: int | None = Field(default=None, description="null means the chain base price")
    promo_description: str | None = None


class PromoWindow(_Model):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    description: str
    promo_type: str | None = Field(default=None, description="reward_type: price, percent, buy_x_get_y, bundle, other")
    club_only: bool | None = Field(default=None, description="true when only club members (or card holders) get it")
    club_name: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1, description="Promo parsing confidence; null when unknown")


class PriceHistoryResponse(_Model):
    canonical_id: int
    store_id: int | None
    days: int
    points: list[PricePoint]
    promos: list[PromoWindow] = Field(default_factory=list)
    generated_at: datetime
    item_id: int | None = Field(default=None, description="The item whose price events make the series; null when none")
    display_name_he: str | None = None


class PriceAlertIn(_Model):
    canonical_id: int
    threshold_unit_price: Decimal = Field(gt=0)
    flex_level: FlexLevel = "any_brand"
    radius_m: int = Field(default=5000, ge=500, le=15000)
    active: bool = Field(default=True, description="false pauses the alert")


class PriceAlert(PriceAlertIn):
    id: int
    active: bool = True
    last_fired_at: datetime | None = None
    created_at: datetime


class PushSubscriptionIn(_Model):
    endpoint: str = Field(max_length=2000)
    p256dh: str
    auth: str
    user_agent: str | None = Field(default=None, max_length=300)


class ShareInvite(_Model):
    list_id: int
    token: str
    url: str
    role: Literal["editor", "viewer"] = "editor"


class ShareRequest(_Model):
    role: Literal["editor", "viewer"] = "editor"


class ListMember(_Model):
    user_id: str | None = Field(default=None, description="null while the invite is pending")
    role: Literal["editor", "viewer"]
    accepted_at: datetime | None = None
    is_owner: bool = False
    share_id: int | None = Field(
        default=None,
        description="Id of the list_shares row (null for the owner); revoke a pending invite or "
        "remove a member with DELETE /me/lists/{list_id}/shares/{share_id}",
    )


class StorePrice(_Model):
    store: StoreRef
    item_id: int
    display_name_he: str
    shelf_price: Decimal
    unit_price: Decimal
    uom: str
    price_valid_from: datetime
    promo_description: str | None = None
    club_required: bool | None = Field(default=None, description="true when the price is a club deal the user marked")
    club_name: str | None = None
    is_substitute: bool | None = Field(default=None, description="true: another product than the one scanned")
    confidence: float | None = Field(default=None, description="Mapping confidence of a substitute")
    tags: list[AttributeTag] | None = Field(default=None, description="Why it is a substitute: attributes against the scanned product")


class BarcodeLookupResponse(_Model):
    barcode: str
    found: bool
    display_name_he: str | None = None
    canonical: CanonicalRef | None = None
    here: StorePrice | None = Field(default=None, description="Price at the store the user is in, when store_id was given")
    cheapest_nearby: StorePrice | None = None
    cheaper_substitute: StorePrice | None = Field(default=None, description="A cheaper any-brand match nearby, labeled as a substitute")
    generated_at: datetime
    disclaimer_he: str = "המחיר הקובע הוא בקופה."


class SwapSuggestion(_Model):
    canonical_id: int
    from_item_id: int
    to_item_id: int
    to_display_name_he: str
    flex_level: FlexLevel
    saving: Decimal = Field(description="For the requested quantity, ILS")
    confidence: float | None = None
    tags: list[AttributeTag] = Field(default_factory=list)


class SwapSuggestionResponse(_Model):
    store_id: int
    swaps: list[SwapSuggestion] = Field(description="Sorted by saving, largest first")
    top_swap: SwapSuggestion | None = None
    total_saving: Decimal
    generated_at: datetime
