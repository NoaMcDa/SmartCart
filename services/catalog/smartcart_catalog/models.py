"""Internal model for the catalog and matching layer.

The only types that cross module boundaries between normalization, extraction, embedding, the
judge, the review UI and the evaluation harness. Nothing here imports a model provider.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

FlexLevel = Literal["exact", "any_brand", "close"]
"""exact = that barcode only; any_brand = same canonical, critical attributes equal;
close = soft attributes may differ. See docs/decisions.md D4."""

BaseUnit = Literal["100g", "100ml", "unit", "kg"]
ProductState = Literal["fresh", "frozen", "chilled", "canned", "dry"]
MatchSource = Literal["rule", "model", "human"]
PlantBase = Literal["soy", "almond", "oat", "rice", "coconut"]
"""What a plant-based drink (or other milk alternative) is made from (issue #92)."""
AttributeKey = Literal[
    "category_path",
    "product_type",
    "brand",
    "is_private_label",
    "fat_pct",
    "state",
    "flavor",
    "kosher",
    "diet_flags",
    "pack_size",
    "unit",
    "base",
    "variety",
]

ALWAYS_UNVERIFIED: frozenset[str] = frozenset({"kosher", "diet_flags"})
"""Keys that stay unverified unless a human confirmed them (issue #25)."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Attributes(_Frozen):
    """Structured attributes of one chain item, extracted once (issue #25)."""

    category_path: str | None = None
    product_type: str | None = None
    brand: str | None = None
    is_private_label: bool | None = None
    fat_pct: Decimal | None = None
    state: ProductState | None = None
    flavor: str | None = None
    kosher: str | None = None
    diet_flags: tuple[str, ...] = ()
    pack_size: Decimal | None = None
    unit: str | None = None
    base: PlantBase | None = None
    """Plant-drink base (soy, almond, oat, rice, coconut); critical for the plant drink types."""
    variety: str | None = None
    """A named variety that is not a flavor (barista, protein, ...); a soft attribute."""
    verified_keys: tuple[str, ...] = ()
    """Keys a human confirmed. Everything else is unverified and shown as such."""
    confidence: float = Field(default=0.0, ge=0, le=1)

    def value(self, key: str) -> Any:
        return getattr(self, key)


class ExtractionError(_Frozen):
    item_id: int
    reason: str
    retryable: bool = True


class NormalizedItem(_Frozen):
    """Output of rule normalization (issue #20).

    The source fields (``chain_id`` .. ``raw_name``) are copied from the ``items`` row so that
    extractors and judges read everything about an item from the item itself (issue #92).
    ``issues`` is what normalization found ambiguous or could not parse."""

    item_id: int
    clean_name: str
    quantity: Decimal | None = None
    unit: str | None = None
    pack_count: int = 1
    total_quantity: Decimal | None = None
    base_unit: BaseUnit | None = None
    is_weighed: bool = False
    chain_id: str | None = None
    chain_name: str | None = None
    manufacturer: str | None = None
    barcode: str | None = None
    raw_name: str | None = None
    issues: tuple[str, ...] = ()


class CanonicalProduct(_Frozen):
    id: int | None = None
    taxonomy_id: str
    slug: str
    display_name_he: str
    product_type: str
    base_unit: BaseUnit
    critical_attrs: dict[str, Any] = Field(default_factory=dict)
    soft_attrs: dict[str, Any] = Field(default_factory=dict)
    is_mvp: bool = False
    rank: int | None = None
    reference_barcodes: tuple[str, ...] = ()
    """Barcodes that are this canonical exactly (``canonical_products.reference_barcodes``);
    an item with one of them matches at ``exact`` (decision D4)."""

    @field_validator("reference_barcodes", mode="before")
    @classmethod
    def _barcodes_as_text(cls, value: Any) -> Any:
        if value is None:
            return ()
        if isinstance(value, str | int):
            value = [value]
        return tuple(str(v).strip() for v in value)


class ProductTypeRule(_Frozen):
    product_type: str
    critical_keys: tuple[str, ...]
    soft_keys: tuple[str, ...]


class Candidate(_Frozen):
    canonical_id: int
    similarity: float
    canonical: CanonicalProduct | None = None


class MatchDecision(_Frozen):
    item_id: int
    canonical_id: int | None
    flex_level: FlexLevel | None
    confidence: float = Field(ge=0, le=1)
    source: MatchSource
    needs_review: bool
    reason: str = ""
    """Why: which critical attributes matched or blocked, in plain words for the review UI."""


class EvaluationMetrics(_Frozen):
    run_id: int | None = None
    computed_at: datetime | None = None
    precision: dict[str, float] = Field(default_factory=dict)  # per flex level
    recall: dict[str, float] = Field(default_factory=dict)
    recall_at_k: float | None = None
    support: dict[str, int] = Field(default_factory=dict)


@runtime_checkable
class Extractor(Protocol):
    name: str
    model: str | None

    def extract(self, items: list[NormalizedItem]) -> list[Attributes | ExtractionError]: ...


@runtime_checkable
class Embedder(Protocol):
    model_name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class Judge(Protocol):
    name: str

    def judge(
        self,
        item: NormalizedItem,
        attrs: Attributes,
        candidates: list[Candidate],
        rules: dict[str, ProductTypeRule],
    ) -> MatchDecision: ...
