"""Match judges: which canonical an item belongs to, and at which flexibility level (issue #33).

Hard rules on critical attributes run after embedding similarity and are never replaced by it
(decision D5). The rules, per candidate:

1. **Exact.** The item's barcode (``NormalizedItem.barcode``) is one of the canonical's
   reference barcodes (``CanonicalProduct.reference_barcodes``, the
   ``canonical_products.reference_barcodes`` column): flex level ``exact``, confidence 1.0.
2. **Critical veto.** The product type and every critical key of the candidate's product type
   (``product_type_rules.critical_keys``) that the canonical defines in ``critical_attrs`` are
   compared with the item's extracted attributes. Any known value that differs blocks the
   candidate outright: it can never qualify at ``any_brand`` (or at all). 3% vs 1% milk, fresh
   vs frozen salmon and soy vs almond drink are vetoed here, however similar the names are.
3. **Soft check.** Soft keys (``soft_keys``) the canonical defines are compared; brand keys are
   ignored because "any brand" means the brand may differ. All equal or unknown: ``any_brand``.
   Any difference (pack size 500 g vs 250 g, another flavor): ``close``.

Confidence (0..1) mixes embedding similarity and attribute agreement::

    sim_score  = clamp((similarity - sim_floor) / (sim_ceil - sim_floor), 0, 1)
    attr_score = (agreed + 0.4 * unknown) / checked      # checked = product type + critical keys
    confidence = 0.4 * sim_score + 0.6 * attr_score

The confidence is capped at 0.85 (so the mapping goes to review, never auto-accepted) when a
critical value of the item is unknown (the rules could not verify it), when the product type has
no rule, or when a second candidate at the same level is within ``ambiguity_margin`` (the judge
cannot tell them apart). Bands:

* confidence >= 0.90: auto-accepted (``needs_review`` false)
* 0.60 <= confidence < 0.90: mapped with ``needs_review`` true (the review queue)
* confidence < 0.60: rejected, no mapping (``canonical_id`` None)

``LLMJudge`` asks Claude to choose among the candidates that survived the hard rules; it can
never pick a vetoed candidate nor a tighter level than the rules allow.

The decision's ``reason`` is stored in ``item_canonical.reason`` by ``match.apply_decisions``,
so the review UI shows the judge's own words instead of recomputing them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from smartcart_catalog.models import (
    Attributes,
    Candidate,
    FlexLevel,
    MatchDecision,
    NormalizedItem,
    ProductTypeRule,
)

ACCEPT_THRESHOLD = 0.90
REVIEW_THRESHOLD = 0.60
UNKNOWN_CREDIT = 0.4
SIM_WEIGHT = 0.4
ATTR_WEIGHT = 0.6
REVIEW_CAP = 0.85
BRAND_KEYS = frozenset({"brand", "is_private_label"})
LEVEL_ORDER: dict[str, int] = {"exact": 0, "any_brand": 1, "close": 2}
_ATTR_FIELDS = frozenset(Attributes.model_fields) - {"verified_keys", "confidence"}

Route = Literal["accept", "review", "reject"]


def route(confidence: float) -> Route:
    """The documented confidence bands."""
    if confidence >= ACCEPT_THRESHOLD:
        return "accept"
    if confidence >= REVIEW_THRESHOLD:
        return "review"
    return "reject"


def looser(a: FlexLevel, b: FlexLevel) -> FlexLevel:
    """The more permissive of two levels (exact < any_brand < close)."""
    return a if LEVEL_ORDER[a] >= LEVEL_ORDER[b] else b


# --- value comparison ---------------------------------------------------------------------------

_TO_BASE = {
    "g": ("g", 1), "gr": ("g", 1), "gram": ("g", 1), "גרם": ("g", 1), "ג": ("g", 1),
    "kg": ("g", 1000), "ק\"ג": ("g", 1000), "קג": ("g", 1000), "קילו": ("g", 1000),
    "ml": ("ml", 1), "מ\"ל": ("ml", 1), "מל": ("ml", 1),
    "l": ("ml", 1000), "liter": ("ml", 1000), "ליטר": ("ml", 1000), "ל": ("ml", 1000),
    "unit": ("unit", 1), "יח": ("unit", 1), "יחידה": ("unit", 1), "יחידות": ("unit", 1),
}  # fmt: skip


def _decimal(v: Any) -> Decimal | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def quantity_in_base(value: Any, unit: str | None) -> tuple[str, Decimal] | None:
    """(g|ml|unit, amount) for a pack size, or None if not comparable."""
    amount = _decimal(value)
    if amount is None:
        return None
    if not unit:
        return ("?", amount)
    base = _TO_BASE.get(unit.strip().lower().rstrip(".'"))
    if base is None:
        return (unit.strip().lower(), amount)
    return (base[0], amount * base[1])


def _norm_scalar(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    d = _decimal(v) if isinstance(v, int | float | Decimal) else None
    if d is not None:
        return d.normalize()
    if isinstance(v, str):
        s = v.strip().lower()
        d = _decimal(s)
        return d.normalize() if d is not None else s
    return v


def values_equal(key: str, item_value: Any, canonical_value: Any) -> bool:
    if key == "diet_flags" or isinstance(canonical_value, list | tuple | set):
        a = {_norm_scalar(x) for x in (item_value or ())}
        b = {_norm_scalar(x) for x in (canonical_value or ())}
        return a == b
    return _norm_scalar(item_value) == _norm_scalar(canonical_value)


def _is_unknown(v: Any) -> bool:
    return v is None or v == "" or v == () or v == []


def item_value(attrs: Attributes, key: str) -> Any:
    return attrs.value(key) if key in _ATTR_FIELDS else None


def _fmt(v: Any) -> str:
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    if isinstance(v, list | tuple):
        return "+".join(str(x) for x in v) or "none"
    return str(v)


# --- name guards: derived forms, preparations, baby, diet ---------------------------------------
#
# First audit of the real chain items (docs/matching.md, "Real items, first audit") found that the
# product word of a canonical often appears in an item that is something else: a tomato nectar,
# beans in sauce, a baby soap, a bar flavored with honey. The extractor picks the product type from
# a keyword, so the judge re-checks the name against the canonical it is about to serve. These
# are hard rules like the critical veto: the item's own words say it is a different product form.
#
# A word is exempt when the canonical's own display name has a word that starts like it (a
# canonical called "מיץ ענבים" is a juice, "טונה בשמן" is in oil), so the tables only list words
# that turn a product into another one. They are lists of Hebrew words as chains write them.

_TOKEN = re.compile(r"[א-תA-Za-z][א-תA-Za-z'\"]*")
_PREFIX_LETTERS = "בהולמשכו"

# The product is a derived form of the word that follows or precedes it (a snack, a sauce, a
# nectar, candy, a dough, flour of something); the canonical must be that form itself.
DERIVED_HEADS: frozenset[str] = frozenset({
    "חטיף", "חטיפי", "חטיפים", "רוטב", "רטבים", "נקטר", "ג'לי", "סוכריות", "סוכרייה",
    "קורנפלקס", "בצק", "קמח", "חליטת", "מחית", "מיץ", "אבקת", "מקמח",
    "דגני", "דגן", "עוגת", "עוגיות", "ריבת", "קראנצי",
})  # fmt: skip

# The item is prepared, preserved, smoked or free of an animal ingredient: not the base product.
FORM_MODIFIERS: frozenset[str] = frozenset({
    "מעושן", "מעושנת", "מעושנים", "מעושנות", "בעישון", "מיובש", "מיובשת", "מיובשים",
    "מיובשות", "כבוש", "כבושים", "כבושה", "ברוטב", "בשמן", "בחומץ", "פולפה", "מרוסק",
    "מרוסקת", "מרוסקים", "מרוסקות", "רסק", "ממולא", "ממולאים", "מטוגן", "מטוגנים",
})  # fmt: skip
PLANT_BASED_MODIFIERS: frozenset[str] = frozenset({
    "צמחוני", "צמחונית", "צמחוניים", "טבעוני", "טבעונית", "טבעוניים", "vegan", "ביונד",
})  # fmt: skip
BABY_MODIFIERS: frozenset[str] = frozenset({
    "לתינוק", "לתינוקות", "תינוק", "תינוקות", "בייבי", "baby", "לפעוטות",
})  # fmt: skip
# Phrases (matched in the name as written, after abbreviation expansion) that make a diet
# variant of the product: a close substitute at most, never "any brand". They name one family
# (diet, zero, light, no sugar): a canonical that carries any word of the family in its own name
# is that variant ("קולה זירו" for a "קולה דיאט"), and a fat claim ("לייט", "דל שומן") next to a
# canonical split by fat percentage is already decided by the fat percentage.
DIET_PHRASES: tuple[str, ...] = (
    "דיאט", "לייט", "light", "זירו", "zero", "ללא סוכר", "ללא תוספת סוכר", "דל שומן",
    "דל סוכר", "דל קלוריות", "ללא שומן",
)  # fmt: skip
FAT_CLAIMS: frozenset[str] = frozenset({"לייט", "light", "דל שומן", "ללא שומן"})
OTHER_DIET_PHRASES: tuple[str, ...] = ("ללא גלוטן",)
_ANIMAL_ROOTS = ("meat", "fish", "dairy", "deli", "frozen")
_FLAVOR_MARK = "בטעם"


def _name_tokens(text: str) -> list[str]:
    return [t.replace("'", "").replace('"', "").lower() for t in _TOKEN.findall(text or "")]


def _stem(token: str) -> str:
    return token[:3]


def _has_stem(tokens: Sequence[str], word: str) -> bool:
    w = word.replace("'", "").lower()
    return any(t == w or (len(t) >= 3 and len(w) >= 3 and _stem(t) == _stem(w)) for t in tokens)


def _in_tokens(tokens: Sequence[str], word: str) -> bool:
    """``word`` is a token of the name, or the token with one prefix letter (ב, ה, ל, ...)."""
    w = word.replace("'", "").lower()
    return any(t == w or (len(t) > len(w) and t[1:] == w and t[0] in _PREFIX_LETTERS)
               for t in tokens)  # fmt: skip


def name_guard(name: str, canonical: Any) -> tuple[list[str], list[str]]:
    """``(vetoes, soft differences)`` of a cleaned item name against a canonical.

    Veto reasons say which word turns the item into another product; a soft difference is a
    diet variant. Both are empty when the canonical's own name accounts for the word."""
    tokens = _name_tokens(name)
    canon_tokens = _name_tokens(canonical.display_name_he)
    root = (canonical.taxonomy_id or "").split(".")[0]
    veto: list[str] = []
    soft: list[str] = []
    for head in sorted(DERIVED_HEADS):
        if _in_tokens(tokens, head) and not _has_stem(canon_tokens, head):
            veto.append(
                f"name has {head!r} (a derived product), canonical is {canonical.display_name_he!r}"
            )
            break
    for mod in sorted(FORM_MODIFIERS):
        if _in_tokens(tokens, mod) and not _has_stem(canon_tokens, mod):
            veto.append(f"name has {mod!r} (prepared or preserved), canonical is not")
            break
    if root in _ANIMAL_ROOTS and "base" not in canonical.critical_attrs:
        for mod in sorted(PLANT_BASED_MODIFIERS):
            if _in_tokens(tokens, mod) and not _has_stem(canon_tokens, mod):
                veto.append(
                    f"name has {mod!r} (plant-based), canonical is {canonical.display_name_he!r}"
                )
                break
    if root != "baby":
        for mod in sorted(BABY_MODIFIERS):
            if _in_tokens(tokens, mod) and not _has_stem(canon_tokens, mod):
                veto.append(f"name has {mod!r} (a baby product), canonical is not")
                break
    if _FLAVOR_MARK in tokens:
        head_tokens: list[str] = []
        for t in tokens:
            if t == _FLAVOR_MARK:
                break
            head_tokens.append(t)
        content = [t for t in canon_tokens if len(t) >= 3]
        if content and head_tokens and not any(_has_stem(head_tokens, t) for t in content):
            veto.append("the canonical's words come only after 'בטעם' (a flavor, not the product)")
    text = " ".join(tokens)
    canon_text = " ".join(canon_tokens)
    family_in_canon = any(p.lower() in canon_text for p in DIET_PHRASES)
    for phrase in (*DIET_PHRASES, *OTHER_DIET_PHRASES):
        p = phrase.lower()
        if not re.search(rf"(?<![א-תa-z]){re.escape(p)}", text):
            continue
        if phrase in OTHER_DIET_PHRASES:
            exempt = p in canon_text
        else:
            exempt = family_in_canon or (
                phrase in FAT_CLAIMS and "fat_pct" in canonical.critical_attrs
            )
        if not exempt:
            soft.append(f"diet variant {phrase!r}")
            break
    return veto, soft


# --- assessment of one candidate ----------------------------------------------------------------


@dataclass
class Assessment:
    candidate: Candidate
    eligible: bool
    flex_level: FlexLevel | None
    confidence: float
    sim_score: float
    attr_score: float
    agreed: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    soft_diff: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def canonical_id(self) -> int:
        return self.candidate.canonical_id

    def reason(self) -> str:
        c = self.candidate.canonical
        name = f"{c.slug} ({c.display_name_he})" if c else f"canonical {self.canonical_id}"
        parts = [f"{name}: similarity {self.candidate.similarity:.2f}"]
        if self.mismatched:
            parts.append("critical mismatch " + "; ".join(self.mismatched))
        if self.agreed:
            parts.append("critical match " + ", ".join(self.agreed))
        if self.unknown:
            parts.append("critical unknown " + ", ".join(self.unknown))
        if self.soft_diff:
            parts.append("soft differs " + "; ".join(self.soft_diff))
        parts.extend(self.notes)
        if self.eligible and self.flex_level:
            parts.append(f"level {self.flex_level}, confidence {self.confidence:.2f}")
        return " | ".join(parts)


class RuleJudge:
    """Deterministic judge: hard rules on attributes plus calibrated similarity.

    ``sim_floor``/``sim_ceil`` map raw cosine similarity onto 0..1 and depend on the embedder.
    The defaults suit ``HashEmbedder``; recalibrate on the gold set for BGE-M3.
    The exact rule reads the barcode from the item (``NormalizedItem.barcode``).
    """

    name = "rule-v1"
    source = "rule"

    def __init__(
        self,
        *,
        sim_floor: float = 0.25,
        sim_ceil: float = 0.75,
        ambiguity_margin: float = 0.03,
    ) -> None:
        if sim_ceil <= sim_floor:
            raise ValueError("sim_ceil must be above sim_floor")
        self.sim_floor = sim_floor
        self.sim_ceil = sim_ceil
        self.ambiguity_margin = ambiguity_margin

    # -- per candidate

    def assess(
        self,
        attrs: Attributes,
        candidate: Candidate,
        rules: Mapping[str, ProductTypeRule],
        normalized: NormalizedItem | None = None,
    ) -> Assessment:
        sim = candidate.similarity
        sim_score = min(max((sim - self.sim_floor) / (self.sim_ceil - self.sim_floor), 0.0), 1.0)
        canon = candidate.canonical
        if canon is None:
            return Assessment(candidate, False, None, 0.0, sim_score, 0.0,
                              notes=["canonical not loaded"])  # fmt: skip

        barcode = normalized.barcode if normalized is not None else None
        if barcode and barcode in canon.reference_barcodes:
            return Assessment(candidate, True, "exact", 1.0, sim_score, 1.0,
                              agreed=["barcode"], notes=["barcode equals a reference barcode"])  # fmt: skip

        rule = rules.get(canon.product_type)
        a = Assessment(candidate, True, None, 0.0, sim_score, 0.0)
        # Product type is always critical.
        if _is_unknown(attrs.product_type):
            a.unknown.append("product_type")
        elif values_equal("product_type", attrs.product_type, canon.product_type):
            a.agreed.append(f"product_type={canon.product_type}")
        else:
            a.mismatched.append(f"product_type {attrs.product_type} vs {canon.product_type}")

        critical = rule.critical_keys if rule else tuple(canon.critical_attrs)
        for key in critical:
            if key == "product_type" or key not in canon.critical_attrs:
                continue
            cv = canon.critical_attrs[key]
            iv = item_value(attrs, key)
            if _is_unknown(iv):
                a.unknown.append(key)
            elif values_equal(key, iv, cv):
                a.agreed.append(f"{key}={_fmt(cv)}")
            else:
                a.mismatched.append(f"{key} {_fmt(iv)} vs {_fmt(cv)}")

        guard_soft: list[str] = []
        if normalized is not None:
            name = normalized.clean_name or normalized.raw_name or ""
            guard_veto, guard_soft = name_guard(name, canon)
            a.mismatched.extend(guard_veto)

        if a.mismatched:
            a.eligible = False
            return a
        a.soft_diff.extend(guard_soft)

        soft = rule.soft_keys if rule else tuple(canon.soft_attrs)
        for key in soft:
            if key in BRAND_KEYS or key in {"unit", "barcodes"} or key not in canon.soft_attrs:
                continue
            cv = canon.soft_attrs[key]
            if key == "pack_size":
                iv_q = quantity_in_base(attrs.pack_size, attrs.unit)
                if iv_q is None and normalized is not None:
                    iv_q = quantity_in_base(normalized.total_quantity or normalized.quantity,
                                            normalized.unit)  # fmt: skip
                cv_q = quantity_in_base(cv, canon.soft_attrs.get("unit"))
                if iv_q is None or cv_q is None:
                    continue
                if iv_q[0] == cv_q[0] and iv_q[1] != cv_q[1]:
                    a.soft_diff.append(f"pack_size {_fmt(iv_q[1])} vs {_fmt(cv_q[1])} {cv_q[0]}")
                continue
            iv = item_value(attrs, key)
            if not _is_unknown(iv) and not values_equal(key, iv, cv):
                a.soft_diff.append(f"{key} {_fmt(iv)} vs {_fmt(cv)}")

        checked = len(a.agreed) + len(a.unknown)
        a.attr_score = (len(a.agreed) + UNKNOWN_CREDIT * len(a.unknown)) / max(checked, 1)
        a.flex_level = "close" if a.soft_diff else "any_brand"
        a.confidence = SIM_WEIGHT * sim_score + ATTR_WEIGHT * a.attr_score
        if a.unknown:
            a.confidence = min(a.confidence, REVIEW_CAP)
        if rule is None:
            a.confidence = min(a.confidence, REVIEW_CAP)
            a.notes.append(f"no product_type_rules row for {canon.product_type}")
        return a

    def assess_all(
        self,
        item: NormalizedItem,
        attrs: Attributes,
        candidates: Sequence[Candidate],
        rules: Mapping[str, ProductTypeRule],
    ) -> list[Assessment]:
        out = [self.assess(attrs, c, rules, item) for c in candidates]
        eligible = [a for a in out if a.eligible]
        # Rank: tighter level first, then confidence, then similarity.
        eligible.sort(key=lambda a: (LEVEL_ORDER[a.flex_level or "close"], -a.confidence,
                                     -a.candidate.similarity))  # fmt: skip
        if len(eligible) >= 2:
            best, second = eligible[0], eligible[1]
            if (
                best.flex_level != "exact"
                and second.flex_level == best.flex_level
                and best.confidence - second.confidence < self.ambiguity_margin
            ):
                best.confidence = min(best.confidence, REVIEW_CAP)
                c2 = second.candidate.canonical
                best.notes.append(f"ambiguous with {c2.slug if c2 else second.canonical_id}")
        return eligible + [a for a in out if not a.eligible]

    # -- protocol

    def judge(
        self,
        item: NormalizedItem,
        attrs: Attributes,
        candidates: list[Candidate],
        rules: dict[str, ProductTypeRule],
    ) -> MatchDecision:
        assessments = self.assess_all(item, attrs, candidates, rules)
        return decide(item.item_id, assessments, self.source)


def decide(item_id: int, assessments: Sequence[Assessment], source: str) -> MatchDecision:
    """Route the best eligible assessment through the confidence bands."""
    eligible = [a for a in assessments if a.eligible]
    vetoed = [a for a in assessments if not a.eligible]
    veto_note = ""
    if vetoed:
        veto_note = " | vetoed: " + " ; ".join(a.reason() for a in vetoed[:3])
    if not eligible:
        reason = "no candidates in block" if not assessments else "every candidate vetoed"
        return MatchDecision(item_id=item_id, canonical_id=None, flex_level=None, confidence=0.0,
                             source=source, needs_review=False, reason=reason + veto_note)  # fmt: skip
    best = eligible[0]
    conf = round(min(max(best.confidence, 0.0), 1.0), 4)
    band = route(conf)
    src = "rule" if best.flex_level == "exact" else source
    if band == "reject":
        return MatchDecision(item_id=item_id, canonical_id=None, flex_level=None, confidence=conf,
                             source=src, needs_review=False,
                             reason=f"rejected (confidence {conf:.2f} < {REVIEW_THRESHOLD}): "
                             + best.reason() + veto_note)  # fmt: skip
    return MatchDecision(
        item_id=item_id,
        canonical_id=best.canonical_id,
        flex_level=best.flex_level,
        confidence=conf,
        source=src,  # type: ignore[arg-type]
        needs_review=band == "review",
        reason=f"{band}: " + best.reason() + veto_note,
    )


# --- LLM judge ----------------------------------------------------------------------------------


class LLMVerdict(BaseModel):
    """Structured output the LLM judge must return."""

    model_config = ConfigDict(extra="forbid")

    canonical_id: int | None = Field(description="Chosen candidate id, or null if none fits.")
    flex_level: Literal["exact", "any_brand", "close"] | None
    confidence: float = Field(ge=0, le=1)
    reason: str


VERDICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "canonical_id": {"type": ["integer", "null"]},
        "flex_level": {"type": ["string", "null"], "enum": ["exact", "any_brand", "close", None]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["canonical_id", "flex_level", "confidence", "reason"],
    "additionalProperties": False,
}

LLM_SYSTEM = """You match Israeli supermarket items to canonical products for a price-comparison \
app. Precision matters more than recall: a wrong match (3% milk shown as 1%) costs more trust \
than a missed one. You receive one chain item (Hebrew name and extracted attributes) and \
candidate canonical products that already passed hard rules on critical attributes. Choose the \
single candidate the item is an instance of, or null if none is. flex_level: "any_brand" when \
only the brand differs, "close" when a soft attribute such as pack size or flavor differs. \
confidence is your probability that the choice is correct. Keep the reason to one sentence."""


class LLMJudge:
    """Claude as the judge, behind the same ``Judge`` protocol, with the hard rules kept.

    The rule judge filters candidates first (vetoed candidates are never shown to the model);
    the model chooses among the survivors with structured output; its level is loosened to the
    rule level if it claims a tighter one; the confidence goes through the same bands.
    ``client`` is an ``anthropic.Anthropic`` (created lazily) or any object with the same
    ``beta.messages.create``; tests pass a stub that replays recorded responses.
    """

    name = "llm-claude"
    source = "model"

    def __init__(
        self,
        client: Any = None,
        *,
        model: str = "claude-sonnet-5-5",
        effort: str = "low",
        max_tokens: int = 2048,
        server_fallback: bool = True,
        rule_judge: RuleJudge | None = None,
    ) -> None:
        self._client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.server_fallback = server_fallback
        self.rules_judge = rule_judge or RuleJudge()
        self.name = f"llm-{model}"

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def build_prompt(
        self, item: NormalizedItem, attrs: Attributes, eligible: Sequence[Assessment]
    ) -> str:
        item_attrs = attrs.model_dump(mode="json", exclude_defaults=True)
        cands = []
        for a in eligible:
            c = a.candidate.canonical
            cands.append({
                "canonical_id": a.canonical_id,
                "name": c.display_name_he if c else None,
                "product_type": c.product_type if c else None,
                "critical_attrs": c.critical_attrs if c else {},
                "soft_attrs": {k: v for k, v in (c.soft_attrs if c else {}).items()
                               if k != "barcodes"},
                "rule_level": a.flex_level,
                "similarity": round(a.candidate.similarity, 3),
            })  # fmt: skip
        payload = {"item": {"name": item.clean_name, "attributes": item_attrs},
                   "candidates": cands}  # fmt: skip
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _request(self, prompt: str) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": LLM_SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
            },
        }
        if self.server_fallback:
            # Server-side fallback on a refusal (Claude API only; not on Bedrock/Vertex/Foundry).
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        return self.client.beta.messages.create(**kwargs)

    def judge(
        self,
        item: NormalizedItem,
        attrs: Attributes,
        candidates: list[Candidate],
        rules: dict[str, ProductTypeRule],
    ) -> MatchDecision:
        assessments = self.rules_judge.assess_all(item, attrs, candidates, rules)
        eligible = [a for a in assessments if a.eligible]
        if not eligible or eligible[0].flex_level == "exact":
            # Nothing to ask, or the barcode rule already decided.
            return decide(item.item_id, assessments, self.source)
        response = self._request(self.build_prompt(item, attrs, eligible))
        if getattr(response, "stop_reason", None) == "refusal":
            return MatchDecision(item_id=item.item_id, canonical_id=None, flex_level=None,
                                 confidence=0.0, source="model", needs_review=False,
                                 reason="model declined the request (refusal)")  # fmt: skip
        text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
        try:
            verdict = LLMVerdict.model_validate_json(text)
        except ValueError as exc:
            return MatchDecision(item_id=item.item_id, canonical_id=None, flex_level=None,
                                 confidence=0.0, source="model", needs_review=False,
                                 reason=f"invalid model output: {exc.__class__.__name__}")  # fmt: skip
        by_id = {a.canonical_id: a for a in eligible}
        chosen = by_id.get(verdict.canonical_id) if verdict.canonical_id is not None else None
        if chosen is None:
            why = ("model chose none" if verdict.canonical_id is None
                   else f"model chose {verdict.canonical_id}, not an eligible candidate")  # fmt: skip
            return MatchDecision(item_id=item.item_id, canonical_id=None, flex_level=None,
                                 confidence=0.0, source="model", needs_review=False,
                                 reason=f"{why}: {verdict.reason}")  # fmt: skip
        level: FlexLevel = chosen.flex_level or "close"
        if verdict.flex_level is not None and verdict.flex_level != "exact":
            level = looser(level, verdict.flex_level)
        conf = min(max(verdict.confidence, 0.0), 1.0)
        if chosen.unknown:
            conf = min(conf, REVIEW_CAP)  # unverified critical values always go to review
        conf = round(conf, 4)
        band = route(conf)
        if band == "reject":
            return MatchDecision(item_id=item.item_id, canonical_id=None, flex_level=None,
                                 confidence=conf, source="model", needs_review=False,
                                 reason=f"rejected by model confidence: {verdict.reason}")  # fmt: skip
        return MatchDecision(
            item_id=item.item_id,
            canonical_id=chosen.canonical_id,
            flex_level=level,
            confidence=conf,
            source="model",
            needs_review=band == "review",
            reason=f"{band}: {verdict.reason} | rules: {chosen.reason()}",
        )
