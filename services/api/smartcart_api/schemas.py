"""Request and response models: the contract between the API and the web app.

The web app generates TypeScript types from the OpenAPI document this module produces
(apps/web/src/api/openapi.json). Change these models only together with that file.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    display_name_ar: str | None = Field(
        default=None,
        description="The canonical's first Arabic name (names_ar[1], machine drafted, pending native "
        "review); null when it has none. Hebrew stays the primary name.",
    )
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


# --- parse-recipe (phase 3, issue #71) -------------------------------------------------------

class ParseRecipeRequest(_Model):
    text: str | None = Field(default=None, min_length=1, max_length=20000, description="A pasted recipe, Hebrew")
    url: str | None = Field(
        default=None, min_length=8, max_length=2000,
        description="A recipe page (http or https). Only this page is fetched: 5 s timeout, 2 MB cap",
    )
    servings: int | None = Field(
        default=None, ge=1, le=100,
        description="Scale the amounts to this many servings (needs the recipe's own yield)",
    )

    @model_validator(mode="after")
    def _one_source(self) -> ParseRecipeRequest:
        if (self.text is None) == (self.url is None):
            raise ValueError("send exactly one of text or url")
        return self


class ParseRecipeResponse(_Model):
    title: str | None
    servings: int | None = Field(description="The servings the quantities are for; null when the recipe's yield is unknown (then nothing was scaled)")
    items: list[ParsedRow] = Field(description="One row per ingredient, resolved like /parse-list; quantity counts packs (rounded up to the canonical's typical pack size) or kg when unit is kg")
    unresolved: list[str] = Field(description="Ingredient lines left to the user: not a supermarket product, to taste, optional, or not found in the catalog")


# --- parse-image: receipt or handwritten list photo (phase 3, issues #61, #68) ------------------
# POST /parse-image is multipart/form-data: ``kind`` ("receipt" | "list") and ``image`` (JPEG, PNG
# or WebP, at most 8 MB). The image is processed in memory and never stored (D11); raw OCR text is
# not stored either. Needs the receipt-processing consent (``X-Image-Consent: 1``), else 403.

class ReceiptLine(_Model):
    text: str = Field(description="The line as read, after normalization")
    quantity: Decimal | None = Field(default=None, description="Units or kg when printed")
    price: Decimal | None = Field(default=None, description="Line total in ILS when printed")


class ReceiptSummary(_Model):
    chain_hint: str | None = Field(default=None, description="Chain id guessed from the header; null when unsure")
    store_hint: str | None = None
    total: Decimal | None = Field(default=None, description="The printed total, ILS")
    lines: list[ReceiptLine] = Field(default_factory=list)


class ParseImageResponse(_Model):
    kind: Literal["receipt", "list"]
    provider: str = Field(description="The OCR provider that read the image: fake, tesseract or claude")
    items: list[ParsedRow] = Field(description="Resolved like /parse-list; low-confidence rows carry needs_confirmation")
    unresolved: list[str] = Field(description="Lines read but not matched to a catalog product (never guessed)")
    receipt: ReceiptSummary | None = Field(default=None, description="Receipt structure; null for a list photo")
    deleted: Literal[True] = Field(default=True, description="The image and the raw text were discarded before responding")


# --- cart handoff to chain online stores (phase 3, issue #72) ---------------------------------

class ChainOnline(_Model):
    chain_id: str
    chain_name: str
    online_url: str | None = Field(default=None, description="The chain's own online-store home page")
    search_url_template: str | None = Field(
        default=None,
        description="The chain's public site-search URL with {q} for the query; a link only, nothing is fetched",
    )
    enabled: bool = Field(description="Feature flag (CART_HANDOFF_CHAINS); disabled chains show no handoff")
    referral: bool = Field(default=False, description="True when the link carries a referral; always labeled in the UI")


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
    canonical_name_ar: str | None = Field(
        default=None,
        description="The canonical's first Arabic name. display_name_he is the chain's own item name "
        "and stays Hebrew; this is what the shopper asked for, not a translation of the item.",
    )
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
    monthly_budget: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2,
        description="Monthly grocery budget, ILS (#70). Omitted keeps the stored value; null clears it",
    )


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
    # phase 3 surfaces
    "voice_started",
    "voice_completed",
    # finish round (issues #56, #61, #68, #72, #73)
    "pwa_installed",
    "push_prompt_shown",
    "push_opt_in",
    "push_opened",
    "store_mode_used",
    "image_parsed",
    "cart_handoff",
    "locale_changed",
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
    canonical_name_ar: str | None = Field(default=None, description="The canonical's first Arabic name, null when none")


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
    canonical_name_ar: str | None = Field(default=None, description="The canonical's first Arabic name, null when none")
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


# --- budget and spend (phase 3, issue #70) ---------------------------------------------------

class SpendEntryIn(_Model):
    date: Date = Field(description="The shopping day")
    store_id: int
    store_name: str = Field(min_length=1, max_length=200)
    total: Decimal = Field(ge=0, max_digits=10, decimal_places=2, description="ILS; the user's actual total overrides the app's estimate")
    item_count: int = Field(ge=0, le=1000)
    plan: Literal["single", "split"]
    client_id: UUID | None = Field(
        default=None,
        description="Random id the browser makes per entry; a repeated POST with the same id returns the stored entry instead of a duplicate",
    )


class SpendEntry(SpendEntryIn):
    id: int


class SpendMonth(_Model):
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")
    entries: list[SpendEntry] = Field(description="Oldest first")
    total: Decimal
    budget: Decimal | None = Field(description="profiles.monthly_budget; null when not set")


class SpendExport(_Model):
    budget: Decimal | None
    entries: list[SpendEntry] = Field(description="Every entry of the user, oldest first")
    generated_at: datetime


# --- promo cycles (phase 3, issue #69) -------------------------------------------------------

class PromoCycleChain(_Model):
    chain_id: str
    chain_name: str
    cycles_seen: int = Field(ge=0, description="Gaps between consecutive promo windows observed")
    median_gap_days: float | None = Field(description="Median days from one promo start to the next; null with no gap")
    confidence: float = Field(ge=0, le=1, description="cycles_seen / (cycles_seen + 1.5) x max(0, 1 - coefficient of variation of the gaps)")
    last_promo_ends: Date | None = Field(description="End of the latest promo window seen")
    next_expected_from: Date | None = Field(description="null unless the prediction passes the gate (3 cycles, confidence 0.6)")
    next_expected_to: Date | None
    advice: Literal["buy_now", "wait", "unknown"] = Field(description="A hint, never a promise; unknown below the gate")


class PromoCycleResponse(_Model):
    canonical_id: int
    chains: list[PromoCycleChain]


# --- closed beta (issue #40): invite codes, membership, feedback -----------------------------

BetaSegment = Literal["large_family", "kosher", "periphery", "general"]


class BetaJoinRequest(_Model):
    code: str = Field(
        min_length=6, max_length=32, pattern=r"^[A-Za-z0-9-]+$",
        description="Invite code from a join link (case does not matter)",
    )


class BetaMembership(_Model):
    member: bool
    segment: BetaSegment | None = Field(default=None, description="null when not a member")


class BetaFeedbackIn(_Model):
    rating: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=1000, description="Free text; stored with the segment only, never with the user")
