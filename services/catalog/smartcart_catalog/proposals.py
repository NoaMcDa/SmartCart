"""Proposals for new canonical products from real unmapped items (issue #52).

On one real day about 99,600 items were loaded and about 21,500 mapped to the 245 canonicals
(`docs/real-day-dry-run.md`). The expansion backlog (`active.catalog_backlog`) ranks unmapped
products by barcode; nothing proposed *a canonical* from what the chains sell. This module does:
it finds the frequent unmapped products, groups them, and derives for each top group a canonical
definition **from the members' own data and the existing rule extractor**. A proposal is a
suggestion for a person (`proposals_packet.py` renders the review packet and imports the answers);
nothing here edits `data/canonicals.yaml`, and no number here is a measured precision.

Method (every step is deterministic and has no network):

1. **Items.** The unmapped items: no ``item_canonical`` row that a human has not rejected (the same
   definition as the backlog), from the database (``items_from_db``) or from the committed real
   fixtures (``items_from_fixtures``, offline, for tests and a first look). Each item carries the
   stores that sell it (a chain base price counts every physical store of the chain, as in
   ``supabase/queries/catalog_backlog.sql``), its latest price and its number of price events.
2. **Prepare.** ``normalize`` and the rule extractor (the same code as ``smartcart-catalog
   normalize`` and ``extract --extractor rule``) give the size, the base unit and the attributes.
   The *core name* is the cleaned name without sizes, units, packaging words, the brand and the
   chain's own name; a percentage stays (it is part of the product).
3. **Barcode first.** Items with the same valid barcode (8, 12, 13 or 14 digits and a correct
   GS1 check digit; a chain-internal code is not a barcode) form one product (an SKU cluster), across
   chains. A member whose name has nothing in common with the others is split off and counted
   (``barcode_conflicts``), because a wrong barcode in one chain's file must not merge two products.
4. **Concept groups.** A canonical is a concept, not an SKU: the same product type and critical
   attributes at any brand. SKU clusters that the extractor typed with the same product type, the
   same critical values and the same base unit are one group (the catalog's own definition of "same
   at any brand"). Untyped clusters are grouped by exact core name, then near duplicates (a
   spelling variant, a name a chain cut at a fixed width) are merged when the hash embedding's cosine is
   at least ``near_duplicate`` (0.90) or the shorter name is a cut prefix of the other.
5. **Not a catalog gap.** A group whose product type already has a canonical with those critical
   values is *not* proposed: its items are unmapped because of the judge or the blocking, a
   matching question, and they are counted (``matching_gaps``). A typed group whose critical value
   is not stated by its members is not proposed either (a canonical needs it); it is counted
   (``missing_critical``) or says only "something else" (``unspecific_critical``, a flavor
   ``other`` or ``milk+other``). Precision over recall: a proposal must at least be a well-formed canonical.
6. **Rank.** ``priority`` is a documented score, an **estimate** (the weights are a judgement; the
   components are measured and every one is shown): chains selling the group (0.30), barcodes sold
   at two or more chains (0.15), stores (0.20), the basket weight of its department (0.15, a
   judgement), price events (0.10) and search misses that name it (0.10).
7. **Derive the definition.** Hebrew name = the most common core name of the group (percent kept);
   taxonomy node, product type, critical attributes and the base unit from the extractor's own
   output on the members, by majority; the typical pack size from the members' own sizes. A value
   no member states is left empty and listed in ``uncertain`` with the reason. Nothing is
   invented: no Arabic name, no brand, no kosher flag, no critical value that the names do not say.

A proposal has one of two kinds: ``variant`` (an existing product type, critical values no
canonical has yet: valid for ``seed`` once an Arabic name is added) or ``new_type`` (the
extractor knows no product type for these names: it needs a new product type rule and a taxonomy
node, which a reviewer chooses).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from smartcart_catalog.block import normalize_text
from smartcart_catalog.embed import HashEmbedder, _bucket
from smartcart_catalog.extract.rule import KNOWN_BRANDS, PRIVATE_LABELS, RuleExtractor
from smartcart_catalog.models import Attributes, ExtractionError, NormalizedItem
from smartcart_catalog.normalize import clean_name, is_full_width, is_truncated, normalize
from smartcart_catalog.seed import Catalog

REPO = Path(__file__).resolve().parents[3]

TOP = 150
MIN_CHAINS = 2
NEAR_DUPLICATE = 0.90
MIN_COHESION = 0.50
EXAMPLES_PER_CHAIN = 2
AGREEMENT = 0.60
"""A value is stated when at least this share of the members that could state it agree."""
SIZE_AGREEMENT = 0.35

# Weights of the priority score: an estimate (a judgement), not a measurement. docs/catalog.md.
WEIGHTS: dict[str, float] = {
    "chains": 0.30, "shared_barcodes": 0.15, "stores": 0.20, "basket": 0.15,
    "events": 0.10, "misses": 0.10,
}  # fmt: skip

# How much of a typical Israeli weekly basket a department is: a judgement (estimate), used only to
# order proposals. Unknown or unmatched departments get the last value.
BASKET_WEIGHT: dict[str, float] = {
    "dairy": 1.0, "meat": 1.0, "produce": 1.0, "bakery": 1.0, "pantry": 1.0,
    "canned": 0.8, "frozen": 0.8, "beverages": 0.8, "deli": 0.8, "fish": 0.8,
    "snacks": 0.6, "cleaning": 0.6, "paper": 0.6, "baby": 0.6,
    "toiletries": 0.4, "health": 0.3, "pets": 0.3, "alcohol": 0.3, "holiday": 0.3,
}  # fmt: skip
UNKNOWN_BASKET_WEIGHT = 0.3

_HE = "א-ת"
_WORD = re.compile(rf"\d+(?:\.\d+)?%|[{_HE}]+(?:['\"][{_HE}]+)*'?|[A-Za-z]+(?:'[A-Za-z]+)*")
# Words that say how much, how packed or how sold, never what the product is. Kept short on
# purpose: a word wrongly dropped only merges two names, a word wrongly kept only splits a group.
NOISE_WORDS: frozenset[str] = frozenset(
    normalize_text(w)
    for w in (
        "גרם", "גרמים", "קילוגרם", "קילוגרמים", "קילו", "ליטר", "ליטרים", "מיליליטר", "מל",
        "יחידות", "יחידה", "יחי", "יח", "מארז", "מארזים", "חבילה", "חבילות", "שקית", "שקיות",
        "במשקל", "משקל", "משקלי", "חדש", "חדשה", "מבצע", "אריזה", "אריזת", "משפחתי", "חסכוני",
        "וואקום", "בוואקום", "בצורת", "קופסה", "קופסת",
    )
)  # fmt: skip
STOP_WORDS: frozenset[str] = frozenset(normalize_text(w) for w in ("של", "עם", "ו", "או", "את"))

# Weighted base unit of an item: the extractor's category and the item's own fields.
_UNIT_HE = {"g": "גרם", "ml": "מ״ל", "unit": "יח׳"}
_SIZE_UNIT_FOR_BASE = {"100g": "g", "100ml": "ml", "unit": "unit"}

_GS1_LENGTHS = (8, 12, 13, 14)
UNTYPED_KEYS = ("state", "base")
"""Attributes read for a name with no product type. A percentage in such a name stays in the name
but is not called a fat percentage: for an unknown type it can be sugar, tomato content or alcohol
("20% פחות סוכר", "רוטב עגבניות 22%")."""


def valid_barcode(code: str | None) -> str | None:
    """The barcode in a form that is equal for the same product (leading zeros stripped), or None.

    Only a GTIN counts: 8, 12, 13 or 14 digits with a correct GS1 check digit. A chain-internal
    item code, a PLU or a mistyped code is not a barcode and must not merge two products."""
    if not code:
        return None
    digits = code.strip()
    if not digits.isdigit() or len(digits) not in _GS1_LENGTHS:
        return None
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    if (10 - total % 10) % 10 != check:
        return None
    return digits.lstrip("0") or None


# --- items ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateItem:
    """One unmapped chain item with the signals the ranking needs."""

    chain_id: str
    chain_name: str
    item_code: str
    raw_name: str
    barcode: str | None = None
    manufacturer: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    is_weighed: bool = False
    stores: int = 0
    """Stores that carry it (a chain base price counts every physical store of the chain)."""
    price: Decimal | None = None
    price_events: int = 0
    item_id: int | None = None

    @property
    def key(self) -> str:
        return f"{self.chain_id}:{self.item_code}"


@dataclass
class ItemPool:
    """The items a run looks at and the totals around them."""

    items: list[CandidateItem]
    total_items: int
    mapped_items: int
    source: str
    chains: dict[str, str] = field(default_factory=dict)
    misses: list[tuple[str, int]] = field(default_factory=list)
    """``(normalized query, count)`` of recent search misses; empty without a database."""
    as_of: date | None = None

    @property
    def unmapped_items(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class Prepared:
    item: CandidateItem
    norm: NormalizedItem
    attrs: Attributes | None
    tokens: tuple[str, ...]
    """The core name's words, in name order (display form, final letters kept)."""
    folded: tuple[str, ...]
    truncated: bool
    barcode: str | None


# --- core name ------------------------------------------------------------------------------------


def name_words(name: str) -> list[str]:
    """Words of a cleaned name: Hebrew and Latin words and percentages; other numbers and
    one-letter words are dropped (sizes and unit letters)."""
    out = []
    for m in _WORD.finditer(clean_name(name)):
        w = m.group(0)
        if w.endswith("%") or len(w.strip("'\"")) >= 2:
            out.append(w)
    return out


@dataclass
class BrandLexicon:
    """Words that name a maker or a chain, never the product. Built from the data itself: the first
    word of a manufacturer that several items share, the extractor's known brands and the
    chains' private-label names, minus every word that is a product word (a product type
    keyword or a taxonomy name)."""

    words: frozenset[str]

    @classmethod
    def build(
        cls,
        items: Iterable[CandidateItem],
        catalog: Catalog | None = None,
        *,
        min_items: int = 3,
    ) -> BrandLexicon:
        first = Counter()
        chain_words: set[str] = set()
        for it in items:
            if it.manufacturer:
                ws = [normalize_text(w) for w in name_words(it.manufacturer) if "%" not in w]
                if ws:
                    first[ws[0]] += 1
            chain_words.update(normalize_text(w) for w in name_words(it.chain_name))
        words = {w for w, n in first.items() if n >= min_items}
        words |= {normalize_text(w) for b in KNOWN_BRANDS for w in name_words(b)}
        words |= {normalize_text(w) for labels in PRIVATE_LABELS.values() for p in labels
                  for w in name_words(p)}  # fmt: skip
        words |= chain_words
        if catalog is not None:
            product_words: set[str] = set()
            for extra in catalog.extras.values():
                for kw in extra.keywords:
                    product_words.update(normalize_text(w) for w in name_words(kw))
            for node in catalog.taxonomy.nodes:
                product_words.update(normalize_text(w) for w in name_words(node.name_he))
            words -= product_words
        return cls(frozenset(w for w in words if len(w) >= 2))


def core_tokens(
    item: CandidateItem, lexicon: BrandLexicon
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(words, folded words)`` of the product name: no size, packaging word, brand or chain."""
    maker = {normalize_text(w) for w in name_words(item.manufacturer or "") if "%" not in w}
    out: list[str] = []
    folded: list[str] = []
    words = name_words(item.raw_name)
    if is_full_width(item.chain_id, item.raw_name) and len(words) > 1:
        # a chain that cuts names at a fixed width leaves the last word of a full-width name as a
        # fragment ("סבון מוצק יר"); the rule extractor does not trust it either
        words = words[:-1]
    for w in words:
        f = normalize_text(w)
        if not f or f in NOISE_WORDS or f in STOP_WORDS or f in lexicon.words:
            continue
        # the whole manufacturer name written in the product name ("טרה" in a name "גבינה טרה")
        if f in maker and len(maker) <= 2 and f not in {"מים", "חלב"}:
            continue
        if f in folded:
            continue
        out.append(w)
        folded.append(f)
    return tuple(out), tuple(folded)


# --- sparse hash vectors (the same features as the hash embedder) ------------------------------------

_EMBEDDER = HashEmbedder()
_SPARSE_CACHE: dict[str, dict[int, float]] = {}


def sparse_hash_vector(text: str) -> dict[int, float]:
    """The hash embedder's vector of ``text`` as a sparse mapping (L2-normalized): identical to
    ``HashEmbedder().embed([text])[0]`` without a 1024-float list per name."""
    cached = _SPARSE_CACHE.get(text)
    if cached is not None:
        return cached
    vec: dict[int, float] = defaultdict(float)
    for feature, weight in _EMBEDDER._features(text):
        idx, sign = _bucket(feature, _EMBEDDER.dim)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec.values()))
    out = {i: v / norm for i, v in vec.items() if v} if norm else {0: 1.0}
    if len(_SPARSE_CACHE) > 400_000:
        _SPARSE_CACHE.clear()
    _SPARSE_CACHE[text] = out
    return out


def cosine(a: Mapping[int, float], b: Mapping[int, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(i, 0.0) for i, v in a.items())


# --- prepare --------------------------------------------------------------------------------------


def prepare(
    items: Sequence[CandidateItem], catalog: Catalog, lexicon: BrandLexicon | None = None
) -> list[Prepared]:
    """Normalize and extract (rule) every item, and cut its core name."""
    lexicon = lexicon or BrandLexicon.build(items, catalog)
    extractor = RuleExtractor(catalog)
    out: list[Prepared] = []
    for n, it in enumerate(items, start=1):
        row = {
            "id": n, "chain_id": it.chain_id, "chain_name": it.chain_name, "item_code": it.item_code,
            "barcode": it.barcode, "raw_name": it.raw_name, "manufacturer": it.manufacturer,
            "quantity": it.quantity, "unit": it.unit, "is_weighed": it.is_weighed,
        }  # fmt: skip
        norm = normalize(row, item_id=n)
        result = extractor.extract_one(norm)
        attrs = None if isinstance(result, ExtractionError) else result
        words, folded = core_tokens(it, lexicon)
        out.append(
            Prepared(
                item=it,
                norm=norm,
                attrs=attrs,
                tokens=words,
                folded=folded,
                truncated=is_truncated(it.chain_id, it.raw_name),
                barcode=valid_barcode(it.barcode),
            )
        )
    return out


# --- SKU clusters (barcode first) -------------------------------------------------------------------


@dataclass
class Cluster:
    """One product: the items that share a valid barcode, or one item with none."""

    members: list[Prepared]
    barcode: str | None = None

    @property
    def chains(self) -> set[str]:
        return {m.item.chain_id for m in self.members}


def _medoid(members: Sequence[Prepared]) -> Prepared:
    """The member whose core name is the most typical: the most common folded core among
    members, whole (not cut) names first."""
    counts = Counter(m.folded for m in members if m.folded)
    return max(
        members,
        key=lambda m: (
            not m.truncated,
            counts.get(m.folded, 0),
            len(m.folded),
            -len(m.item.raw_name),
            m.item.raw_name,
        ),
    )


def cluster_by_barcode(
    prepared: Sequence[Prepared], *, conflict_below: float = 0.20
) -> tuple[list[Cluster], int]:
    """Clusters by barcode across chains, plus the number of members split off because their
    name shares nothing with the others (a wrong barcode in one chain's file)."""
    by_code: dict[str, list[Prepared]] = defaultdict(list)
    singles: list[Prepared] = []
    for p in prepared:
        (by_code[p.barcode] if p.barcode else singles).append(p)
    clusters: list[Cluster] = []
    conflicts = 0
    for code, members in sorted(by_code.items()):
        keep = members
        if len(members) > 1:
            lead = _medoid(members)
            lead_vec = sparse_hash_vector(" ".join(lead.folded) or lead.item.raw_name)
            keep, split = [], []
            for m in members:
                vec = sparse_hash_vector(" ".join(m.folded) or m.item.raw_name)
                (keep if m is lead or cosine(lead_vec, vec) >= conflict_below else split).append(m)
            conflicts += len(split)
            singles.extend(split)
        clusters.append(Cluster(keep, code))
    clusters.extend(Cluster([p]) for p in singles)
    return clusters, conflicts


# --- votes -----------------------------------------------------------------------------------------


def _vote(values: Sequence[Any], agreement: float = AGREEMENT) -> tuple[Any, float]:
    """``(value, share)`` of the most common non-None value among the values that state one;
    ``(None, 0)`` when nobody states one or the winner's share of the stating members is under
    ``agreement``."""
    stated = [v for v in values if v is not None]
    if not stated:
        return None, 0.0
    value, n = Counter(stated).most_common(1)[0]
    share = n / len(stated)
    return (value, share) if share >= agreement else (None, share)


def _plain(value: Any) -> Any:
    """A Decimal as an int when whole, else a float; everything else as it is."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral() else float(value)
    return value


def critical_signature(
    prep: Prepared, catalog: Catalog
) -> tuple[str | None, tuple[tuple[str, Any], ...]]:
    """``(product type, critical values)`` of one item, as the extractor states them. For a typed
    item the keys are its type's critical keys; for an untyped one, what the name states
    (state and plant base; a flavor word or a percentage in an untyped name is part of the name,
    so it stays in the name and is not a key)."""
    a = prep.attrs
    if a is None:
        return None, ()
    pt = a.product_type
    keys = catalog.rules[pt].critical_keys if pt in catalog.rules else UNTYPED_KEYS
    return pt, tuple((k, _plain(a.value(k))) for k in keys)


# --- groups ----------------------------------------------------------------------------------------


@dataclass
class Group:
    clusters: list[Cluster]
    product_type: str | None
    signature: tuple[tuple[str, Any], ...]
    base_unit: str | None
    merged_by: str = "exact"

    @property
    def members(self) -> list[Prepared]:
        return [m for c in self.clusters for m in c.members]


def _cluster_attrs(
    c: Cluster, catalog: Catalog
) -> tuple[str | None, tuple[tuple[str, Any], ...], str | None]:
    """Majority product type, critical values and base unit of one cluster's members."""
    sigs = [critical_signature(m, catalog) for m in c.members]
    pt, _ = _vote([s[0] for s in sigs], agreement=0.5)
    keys: list[str] = []
    for s in sigs:
        if s[0] == pt:
            keys = [k for k, _ in s[1]]
            break
    values: list[tuple[str, Any]] = []
    for k in keys:
        v, _ = _vote([dict(s[1]).get(k) for s in sigs if s[0] == pt], agreement=0.5)
        values.append((k, v))
    base, _ = _vote([m.norm.base_unit for m in c.members], agreement=0.5)
    return pt, tuple(values), base


def build_groups(
    clusters: Sequence[Cluster], catalog: Catalog, *, near_duplicate: float = NEAR_DUPLICATE
) -> list[Group]:
    """Typed clusters with the same type, critical values and base unit are one group; untyped
    ones are grouped by exact core name and merged when near duplicates."""
    typed: dict[tuple, Group] = {}
    untyped: dict[tuple, list[tuple[Cluster, tuple[str, ...], tuple[str, ...]]]] = defaultdict(list)
    for c in clusters:
        pt, sig, base = _cluster_attrs(c, catalog)
        if pt is not None and pt in catalog.rules:
            key = (pt, sig, base)
            g = typed.get(key)
            if g is None:
                typed[key] = Group([c], pt, sig, base, "type")
            else:
                g.clusters.append(c)
            continue
        lead = _medoid(c.members)
        if not lead.folded:
            continue  # nothing but a brand, a size or a packaging word: no name to propose
        untyped[(sig, base)].append((c, lead.folded, lead.tokens))

    groups = list(typed.values())
    for (sig, base), entries in sorted(untyped.items(), key=lambda kv: str(kv[0])):
        groups.extend(_merge_untyped(entries, sig, base, near_duplicate))
    return groups


def _is_cut_prefix(short: tuple[str, ...], full: tuple[str, ...]) -> bool:
    """``short`` is ``full`` cut by a chain's name width: all but its last word equal, and its
    last word starts the matching word of ``full`` (at least 2 words, so one common word is not
    enough)."""
    if len(short) < 2 or len(short) > len(full):
        return False
    return short[:-1] == full[: len(short) - 1] and full[len(short) - 1].startswith(short[-1])


def _merge_untyped(
    entries: list[tuple[Cluster, tuple[str, ...], tuple[str, ...]]],
    sig: tuple[tuple[str, Any], ...],
    base: str | None,
    near_duplicate: float,
) -> list[Group]:
    # exact core name first
    exact: dict[tuple[str, ...], list[tuple[Cluster, tuple[str, ...]]]] = defaultdict(list)
    for c, folded, tokens in entries:
        exact[tuple(sorted(folded))].append((c, tokens))
    pieces = [
        (key, [c for c, _ in members], members[0][1]) for key, members in sorted(exact.items())
    ]
    # biggest first: a group is led by the most widely sold spelling
    pieces.sort(key=lambda p: (-len({ch for c in p[1] for ch in c.chains}), -len(p[1]), p[0]))
    leaders: list[dict[str, Any]] = []
    index: dict[str, list[int]] = defaultdict(list)
    for key, cls, _tokens in pieces:
        text = " ".join(key)
        vec = sparse_hash_vector(text)
        truncated = all(m.truncated for c in cls for m in c.members)
        candidates: set[int] = set()
        for tok in sorted(key, key=lambda t: len(index.get(t, ())))[:2]:
            candidates.update(index.get(tok, ()))
        best, best_sim = None, 0.0
        for i in sorted(candidates):
            lead = leaders[i]
            sim = cosine(vec, lead["vec"])
            if truncated and _is_cut_prefix(key, lead["key"]):
                sim = max(sim, 1.0)
            if sim >= near_duplicate and sim > best_sim:
                best, best_sim = i, sim
        if best is not None:
            leaders[best]["clusters"].extend(cls)
            leaders[best]["merged"] = True
            continue
        leaders.append({"key": key, "vec": vec, "clusters": list(cls), "merged": False})
        for tok in key:
            index[tok].append(len(leaders) - 1)
    return [
        Group(g["clusters"], None, sig, base, "near-duplicate" if g["merged"] else "exact")
        for g in leaders
    ]


# --- proposals --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ExampleItem:
    chain: str
    name: str
    barcode: str | None
    size: str
    price: str
    stores: int
    shared: bool
    """The item's barcode is sold at two or more chains."""


@dataclass
class Proposal:
    rank: int
    proposal_id: str
    kind: str  # variant | new_type
    display_name_he: str
    slug: str
    taxonomy_id: str | None
    taxonomy_candidates: list[tuple[str, float]]
    product_type: str | None
    suggested_product_type: str
    base_unit: str | None
    critical_attrs: dict[str, Any]
    soft_attrs: dict[str, Any]
    uncertain: list[str]
    department: str | None
    # coverage and ranking signals (all measured on the items given)
    chains: int
    chain_names: list[str]
    stores: int
    items: int
    skus: int
    shared_barcodes: int
    price_events: int
    miss_hits: int
    basket_weight: float
    cohesion: float
    priority: float
    components: dict[str, float]
    merged_by: str
    examples: list[ExampleItem]
    row_hash: str = ""


def _stores_per_chain(members: Iterable[Prepared]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for m in members:
        out[m.item.chain_id] = max(out[m.item.chain_id], m.item.stores)
    return out


def _normalized_critical(
    sig: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    return {k: v for k, v in sig if v is not None}


def _same_value(a: Any, b: Any) -> bool:
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:  # noqa: BLE001 - not numbers
        return str(a) == str(b)


def is_unspecific(value: Any) -> bool:
    """A critical value that says "something else" (``other``, ``milk+other``): the extractor saw
    an extra ingredient or a second flavor it has no word for. No canonical can be that."""
    text = str(value)
    return text == "other" or text.endswith("+other") or text.startswith("other+")


def covered_by(catalog: Catalog, product_type: str, critical: Mapping[str, Any]) -> str | None:
    """The slug of an existing canonical of ``product_type`` with exactly these critical values."""
    for c in catalog.canonicals:
        if c.product_type != product_type:
            continue
        have = c.critical_attrs
        if set(have) == set(critical) and all(_same_value(have[k], critical[k]) for k in have):
            return c.slug
    return None


def _size_of(m: Prepared) -> tuple[Decimal, str] | None:
    n = m.norm
    if m.item.is_weighed or n.total_quantity is None or n.unit is None:
        return None
    if n.unit not in _UNIT_HE:
        return None
    return n.total_quantity, n.unit


def size_text(m: Prepared) -> str:
    if m.item.is_weighed or m.norm.is_weighed:
        return "במשקל (לק״ג)"
    s = _size_of(m)
    if s is None:
        return ""
    qty, unit = s
    q = int(qty) if qty == qty.to_integral() else float(qty)
    return f"{q} {_UNIT_HE[unit]}"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


_TRANSLIT = {
    "א": "a", "ב": "b", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "kh", "ט": "t",
    "י": "y", "כ": "k", "ך": "k", "ל": "l", "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s",
    "ע": "a", "פ": "p", "ף": "p", "צ": "ts", "ץ": "ts", "ק": "k", "ר": "r", "ש": "sh", "ת": "t",
}  # fmt: skip


def transliterate(text: str) -> str:
    """A rough Latin spelling of a Hebrew name, for a slug suggestion only (a reviewer renames)."""
    return _slugify("".join(_TRANSLIT.get(ch, ch if ch.isascii() else " ") for ch in text))


def _taxonomy_candidates(
    catalog: Catalog, folded: Sequence[str], limit: int = 3
) -> list[tuple[str, float]]:
    """Product-type nodes (level 3 and 4) whose Hebrew name's words all or mostly appear in the
    name: ``(node id, share of the node's words found)``, best first. Only a hint."""
    words = set(folded)
    scored: list[tuple[float, int, str]] = []
    for node in catalog.taxonomy.nodes:
        if node.level < 3:
            continue
        node_words = {normalize_text(w) for w in name_words(node.name_he)} - STOP_WORDS
        if not node_words:
            continue
        share = len(node_words & words) / len(node_words)
        if share >= 0.5:
            scored.append((share, node.level, node.id))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [(nid, round(share, 2)) for share, _, nid in scored[:limit]]


def _department(taxonomy_id: str | None, candidates: Sequence[tuple[str, float]]) -> str | None:
    if taxonomy_id:
        return taxonomy_id.split(".")[0]
    if candidates and candidates[0][1] >= 1.0:
        return candidates[0][0].split(".")[0]
    return None


def _example_items(group: Group, per_chain: int, shared: set[str]) -> list[ExampleItem]:
    by_chain: dict[str, list[Prepared]] = defaultdict(list)
    for m in group.members:
        by_chain[m.item.chain_id].append(m)
    out: list[ExampleItem] = []
    for _chain, members in sorted(by_chain.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        ranked = sorted(
            members,
            key=lambda m: (
                m.barcode not in shared,
                m.truncated,
                -m.item.stores,
                len(m.item.raw_name),
                m.item.raw_name,
            ),
        )
        seen: set[str] = set()
        for m in ranked:
            if len(seen) == per_chain:
                break
            if m.item.raw_name in seen:
                continue
            seen.add(m.item.raw_name)
            out.append(
                ExampleItem(
                    chain=m.item.chain_name,
                    name=m.item.raw_name.strip(),
                    barcode=m.item.barcode,
                    size=size_text(m),
                    price="" if m.item.price is None else f"{m.item.price:.2f}",
                    stores=m.item.stores,
                    shared=m.barcode in shared,
                )
            )
    return out


def group_name(group: Group) -> tuple[str, tuple[str, ...], str | None]:
    """``(Hebrew name, folded words, note)``: the core name most widely sold among the group's
    products; for a typed group (a concept of many products) only the words that at least half of
    its products share, in the order of that name. The note is set when every name the choice
    rests on was cut by its chain."""
    leads = [(_medoid(c.members), c) for c in group.clusters]
    counts: Counter[tuple[str, ...]] = Counter()
    tokens: dict[tuple[str, ...], tuple[str, ...]] = {}
    whole: dict[tuple[str, ...], bool] = defaultdict(bool)
    for lead, c in leads:
        counts[lead.folded] += len(c.chains)
        tokens.setdefault(lead.folded, lead.tokens)
        whole[lead.folded] |= not lead.truncated
    best = max(counts, key=lambda f: (whole[f], counts[f], len(f), f))
    folded, words = best, tokens[best]
    if group.product_type is not None and len(leads) > 1:
        freq: Counter[str] = Counter()
        for lead, _ in leads:
            freq.update(set(lead.folded))
        keep = [(f, w) for f, w in zip(best, words, strict=True) if freq[f] * 2 >= len(leads)]
        if keep:
            folded = tuple(f for f, _ in keep)
            words = tuple(w for _, w in keep)
    note = None
    if not whole[best]:
        note = "display_name_he: taken from names that the chain cut at a fixed width"
    return " ".join(words), folded, note


def derive_definition(group: Group, catalog: Catalog) -> dict[str, Any]:
    """The canonical's fields from the members' own data. Never a value no member states: a
    missing one is None and named in ``uncertain`` with the reason."""
    members = group.members
    uncertain: list[str] = []
    name, lead_folded, name_note = group_name(group)
    if name_note:
        uncertain.append(name_note)
    if len(group.clusters) == 1:
        uncertain.append(
            "display_name_he: from a single product, it may carry its brand; generalize it"
        )

    pt = group.product_type
    # the group's key: what its products' names state (a value no name states is absent)
    critical: dict[str, Any] = _normalized_critical(group.signature)
    taxonomy_id: str | None = None
    candidates: list[tuple[str, float]] = []
    if pt is not None:
        rule = catalog.rules[pt]
        cat, _ = _vote([m.attrs.category_path if m.attrs else None for m in members])
        if cat and cat in catalog.taxonomy and catalog.taxonomy.get(cat).level >= 3:
            taxonomy_id = cat
        else:
            uncertain.append("taxonomy_id: the extractor gives no product-type node")
        soft_keys = set(rule.soft_keys)
    else:
        candidates = _taxonomy_candidates(catalog, lead_folded)
        if (
            candidates
            and candidates[0][1] >= 1.0
            and (len(candidates) == 1 or candidates[1][1] < 1.0)
        ):
            taxonomy_id = candidates[0][0]
            uncertain.append("taxonomy_id: chosen by the words of the node name only")
        else:
            uncertain.append("taxonomy_id: choose a node (candidates are hints)")
        uncertain.append("product_type: the extractor knows no type for these names")
        uncertain.append(
            "critical_attrs: only state and plant base are read for an unknown type; which"
            " attributes are critical (fat, flavor, a percentage kept in the name) is the"
            " reviewer's decision"
        )
        soft_keys = {"pack_size", "brand"}

    base_unit, _ = _vote([m.norm.base_unit for m in members])
    if base_unit is None:
        uncertain.append("base_unit: the members disagree or state none")

    soft: dict[str, Any] = {}
    sizes = [s for m in members if (s := _size_of(m))]
    if "pack_size" in soft_keys and base_unit in _SIZE_UNIT_FOR_BASE:
        unit = _SIZE_UNIT_FOR_BASE[base_unit]
        same_dim = [(q, u) for q, u in sizes if u == unit]
        size, share = _vote([(q, u) for q, u in same_dim], agreement=SIZE_AGREEMENT)
        if size is not None:
            soft = {"pack_size": _plain(size[0]), "unit": size[1]}
        elif same_dim:
            lo = min(q for q, _ in same_dim)
            hi = max(q for q, _ in same_dim)
            uncertain.append(
                f"soft_attrs.pack_size: sizes vary ({_plain(lo)} to {_plain(hi)} {unit})"
            )
        else:
            uncertain.append("soft_attrs.pack_size: no member states a size")

    # an attribute that only some members state is a doubt to show
    if pt is not None:
        for k in catalog.rules[pt].critical_keys:
            if k not in critical:
                uncertain.append(f"critical_attrs.{k}: no member states it")
    return {
        "name": name, "folded": lead_folded, "critical": critical, "taxonomy_id": taxonomy_id,
        "candidates": candidates, "base_unit": base_unit, "soft": soft, "uncertain": uncertain,
    }  # fmt: skip


def proposal_hash(fields: Mapping[str, Any]) -> str:
    """A short fingerprint of what the reviewer sees and edits, to notice a stale packet."""
    keep = {
        k: fields.get(k)
        for k in ("slug", "display_name_he", "taxonomy_id", "product_type", "base_unit",
                  "critical_attrs", "soft_attrs")
    }  # fmt: skip
    blob = json.dumps(keep, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:10]


@dataclass
class ProposalRun:
    proposals: list[Proposal]
    stats: dict[str, Any]


def _cohesion(group: Group) -> float:
    """Mean cosine of the clusters' core names to the group's most common one: how alike the
    members are (1.0 for one name)."""
    names = [" ".join(_medoid(c.members).folded) for c in group.clusters]
    names = [n for n in names if n]
    if len(names) < 2:
        return 1.0
    lead = sparse_hash_vector(Counter(names).most_common(1)[0][0])
    return sum(cosine(lead, sparse_hash_vector(n)) for n in names) / len(names)


def _miss_hits(groups_tokens: Sequence[set[str]], misses: Sequence[tuple[str, int]]) -> list[int]:
    """Search misses naming each group: a miss counts when every word of the query is one of the
    group's name words (an inverted index over the words)."""
    index: dict[str, list[int]] = defaultdict(list)
    for i, toks in enumerate(groups_tokens):
        for t in toks:
            index[t].append(i)
    hits = [0] * len(groups_tokens)
    for query, count in misses:
        words = [w for w in normalize_text(query).split(" ") if w and w not in STOP_WORDS]
        if not words or len(words) > 4:
            continue
        sets = [set(index.get(w, ())) for w in words]
        for i in set.intersection(*sets):
            hits[i] += count
    return hits


SAMPLES = 15


def _sample_order(g: Group) -> tuple[int, int, str]:
    return (-len({m.item.chain_id for m in g.members}), -len(g.members), g.product_type or "")


def _sample(g: Group) -> dict[str, Any]:
    """A short description of an excluded group, for the diagnostics."""
    name, _, _ = group_name(g)
    return {
        "name": name, "product_type": g.product_type,
        "critical": {k: v for k, v in g.signature if v is not None},
        "chains": len({m.item.chain_id for m in g.members}), "items": len(g.members),
        "example": g.members[0].item.raw_name,
    }  # fmt: skip


def propose(
    pool: ItemPool,
    catalog: Catalog,
    *,
    top: int = TOP,
    min_chains: int = MIN_CHAINS,
    min_cohesion: float = MIN_COHESION,
    near_duplicate: float = NEAR_DUPLICATE,
    per_chain: int = EXAMPLES_PER_CHAIN,
    progress: Callable[[str], None] | None = None,
) -> ProposalRun:
    """Group the pool's unmapped items and propose canonicals for the top ``top`` groups."""
    say = progress or (lambda _msg: None)
    existing_slugs = {c.slug for c in catalog.canonicals}
    prepared = prepare(pool.items, catalog)
    say(f"prepared {len(prepared)} items")
    clusters, conflicts = cluster_by_barcode(prepared)
    shared_codes = {c.barcode for c in clusters if c.barcode and len(c.chains) >= 2}
    groups = build_groups(clusters, catalog, near_duplicate=near_duplicate)
    say(f"{len(clusters)} products, {len(groups)} groups")

    stats: dict[str, Any] = {
        "source": pool.source,
        "as_of": pool.as_of.isoformat() if pool.as_of else None,
        "items_total": pool.total_items,
        "items_mapped": pool.mapped_items,
        "items_unmapped": len(pool.items),
        "chains_in_data": len(pool.chains) or len({p.item.chain_id for p in prepared}),
        "items_without_name": len(prepared) - sum(len(g.members) for g in groups),
        "barcodes_valid": sum(1 for p in prepared if p.barcode),
        "barcodes_shared_chains": len(shared_codes),
        "barcode_conflicts": conflicts,
        "products": len(clusters),
        "groups": len(groups),
        "matching_gaps": {"groups": 0, "items": 0, "top": []},
        "missing_critical": {"groups": 0, "items": 0},
        "unspecific_critical": {"groups": 0, "items": 0},
        "same_type_other_unit": {"groups": 0, "items": 0},
        "below_min_chains": {"groups": 0, "items": 0},
        "low_cohesion": {"groups": 0, "items": 0},
        "no_base_unit": {"groups": 0, "items": 0},
    }
    chains_in_data = max(stats["chains_in_data"], 1)

    kept: list[tuple[Group, dict[str, Any], dict[str, Any]]] = []
    gaps: list[tuple[int, str, str]] = []
    excluded: dict[str, list[Group]] = defaultdict(list)

    def skip(reason: str, group: Group) -> None:
        stats[reason]["groups"] += 1
        stats[reason]["items"] += len(group.members)
        excluded[reason].append(group)

    for g in groups:
        chains = {m.item.chain_id for m in g.members}
        crit = _normalized_critical(g.signature)
        if g.product_type is not None:
            rule = catalog.rules[g.product_type]
            if any(k not in crit for k in rule.critical_keys):
                skip("missing_critical", g)
                continue
            if any(is_unspecific(v) for v in crit.values()):
                skip("unspecific_critical", g)
                continue
            slug = covered_by(catalog, g.product_type, crit)
            if slug is not None:
                skip("matching_gaps", g)
                gaps.append((len(g.members), g.product_type, slug))
                continue
        if len(chains) < min_chains:
            skip("below_min_chains", g)
            continue
        coh = _cohesion(g)
        if coh < min_cohesion:
            skip("low_cohesion", g)
            continue
        definition = derive_definition(g, catalog)
        if definition["base_unit"] is None:
            skip("no_base_unit", g)
            continue
        kept.append((g, definition, {"cohesion": coh}))
    stats["matching_gaps"]["top"] = [
        {"product_type": pt, "canonical": slug, "items": n}
        for n, pt, slug in sorted(gaps, key=lambda t: (-t[0], t[1]))[:10]
    ]
    stats["excluded_samples"] = {
        reason: [_sample(g) for g in sorted(gs, key=_sample_order)[:SAMPLES]]
        for reason, gs in sorted(excluded.items())
    }
    say(f"{len(kept)} candidate groups")

    # ranking signals
    miss_hits = _miss_hits([set(d["folded"]) for _, d, _ in kept], pool.misses)
    raw: list[dict[str, Any]] = []
    for (g, d, _extra), misses in zip(kept, miss_hits, strict=True):
        members = g.members
        chains = {m.item.chain_id for m in members}
        stores = sum(_stores_per_chain(members).values())
        events = sum(m.item.price_events for m in members)
        shared = len({c.barcode for c in g.clusters if c.barcode in shared_codes})
        dept = _department(d["taxonomy_id"], d["candidates"])
        raw.append({
            "chains": len(chains), "stores": stores, "events": events, "shared": shared,
            "misses": misses, "dept": dept,
            "basket": BASKET_WEIGHT.get(dept or "", UNKNOWN_BASKET_WEIGHT),
        })  # fmt: skip
    max_stores = max((r["stores"] for r in raw), default=1) or 1
    max_events = max((r["events"] for r in raw), default=1) or 1
    scored: list[tuple[float, int]] = []
    comps: list[dict[str, float]] = []
    for i, r in enumerate(raw):
        c = {
            "chains": r["chains"] / chains_in_data,
            "shared_barcodes": min(1.0, r["shared"] / 5),
            "stores": r["stores"] / max_stores,
            "basket": r["basket"],
            "events": math.log1p(r["events"]) / math.log1p(max_events),
            "misses": min(1.0, r["misses"] / 10),
        }
        comps.append(c)
        scored.append((sum(WEIGHTS[k] * v for k, v in c.items()), i))

    order = sorted(
        range(len(kept)),
        key=lambda i: (
            -scored[i][0],
            -raw[i]["chains"],
            -len(kept[i][0].members),
            kept[i][1]["name"],
            i,
        ),
    )
    # `seed` allows one canonical per product type and critical values. Two groups that differ only
    # in the base unit (packaged per 100 g and weighed per kg) cannot both be canonicals: the wider
    # one is proposed and the other is named in its notes.
    first_of: dict[str, int] = {}
    other_unit: dict[int, list[str]] = defaultdict(list)
    ranked: list[int] = []
    for i in order:
        g, d, _extra = kept[i]
        if g.product_type is None:
            ranked.append(i)
            continue
        key = json.dumps([g.product_type, sorted(d["critical"].items(), key=str)], default=str)
        if key in first_of:
            keeper = first_of[key]
            other_unit[keeper].append(f"{d['base_unit']}: {len(g.members)} items")
            stats["same_type_other_unit"]["groups"] += 1
            stats["same_type_other_unit"]["items"] += len(g.members)
            continue
        first_of[key] = i
        ranked.append(i)
    proposals: list[Proposal] = []
    used_slugs = set(existing_slugs)
    for rank, i in enumerate(ranked[:top], start=1):
        g, d, extra = kept[i]
        r = raw[i]
        if other_unit.get(i):
            d["uncertain"].append(
                "base_unit: the same product type and critical values are also sold in another"
                f" unit ({'; '.join(other_unit[i])}), which `seed` cannot hold as a second"
                " canonical; decide which unit this canonical uses"
            )
        members = g.members
        pt = g.product_type
        suggested = pt or transliterate(d["name"]).replace("-", "_") or "new_type"
        if suggested[0].isdigit():
            suggested = "t_" + suggested
        base_slug = (
            _slugify(
                "-".join([suggested.replace("_", "-"), *[str(v) for v in d["critical"].values()]])
            )
            if pt
            else (transliterate(d["name"]) or "new")
        )
        slug, n = base_slug, 2
        while slug in used_slugs:
            slug, n = f"{base_slug}-{n}", n + 1
        used_slugs.add(slug)
        chain_names = sorted({m.item.chain_name for m in members})
        shared_ex = shared_codes
        fields = {
            "slug": slug, "display_name_he": d["name"], "taxonomy_id": d["taxonomy_id"],
            "product_type": pt, "base_unit": d["base_unit"],
            "critical_attrs": d["critical"], "soft_attrs": d["soft"],
        }  # fmt: skip
        pid_blob = json.dumps(
            [pt, sorted(d["critical"].items(), key=str), d["base_unit"], sorted(d["folded"])],
            ensure_ascii=False,
            default=str,
        )
        proposals.append(
            Proposal(
                rank=rank,
                proposal_id="P" + hashlib.sha256(pid_blob.encode("utf-8")).hexdigest()[:8],
                kind="variant" if pt else "new_type",
                display_name_he=d["name"],
                slug=slug,
                taxonomy_id=d["taxonomy_id"],
                taxonomy_candidates=d["candidates"],
                product_type=pt,
                suggested_product_type=suggested,
                base_unit=d["base_unit"],
                critical_attrs=d["critical"],
                soft_attrs=d["soft"],
                uncertain=d["uncertain"],
                department=r["dept"],
                chains=r["chains"],
                chain_names=chain_names,
                stores=r["stores"],
                items=len(members),
                skus=len(g.clusters),
                shared_barcodes=r["shared"],
                price_events=r["events"],
                miss_hits=r["misses"],
                basket_weight=r["basket"],
                cohesion=round(extra["cohesion"], 3),
                priority=round(scored[i][0], 4),
                components={k: round(v, 3) for k, v in comps[i].items()},
                merged_by=g.merged_by,
                examples=_example_items(g, per_chain, shared_ex),
                row_hash=proposal_hash(fields),
            )
        )
    stats["proposals"] = len(proposals)
    stats["proposal_items"] = sum(p.items for p in proposals)
    stats["proposal_stores"] = sum(p.stores for p in proposals)
    stats["candidate_groups"] = len(kept)
    stats["candidate_items"] = sum(len(kept[i][0].members) for i in range(len(kept)))
    stats["kinds"] = dict(Counter(p.kind for p in proposals))
    return ProposalRun(proposals, stats)


# --- sources ------------------------------------------------------------------------------------------

ITEMS_SQL = """
WITH unmapped AS (
  SELECT i.id, i.chain_id, i.item_code, i.barcode, i.raw_name, i.manufacturer, i.quantity,
         i.unit, i.is_weighed
  FROM items AS i
  WHERE i.chain_id <> 'gold'
    AND NOT EXISTS (
      SELECT 1 FROM item_canonical AS ic WHERE ic.item_id = i.id AND NOT ic.human_rejected)
), physical AS (
  SELECT chain_id, count(*) AS n FROM stores WHERE channel = 'physical' GROUP BY chain_id
), stats AS (
  SELECT p.item_id,
         count(*) AS events,
         bool_or(p.store_id IS NULL) AS has_base,
         count(DISTINCT p.store_id) AS store_rows
  FROM prices AS p JOIN unmapped AS u ON u.id = p.item_id
  GROUP BY p.item_id
), latest AS (
  SELECT DISTINCT ON (p.item_id) p.item_id, p.price
  FROM prices AS p JOIN unmapped AS u ON u.id = p.item_id
  ORDER BY p.item_id, (p.store_id IS NULL) DESC, p.valid_from DESC
)
SELECT u.id, u.chain_id, COALESCE(c.name, u.chain_id), u.item_code, u.barcode, u.raw_name,
       u.manufacturer, u.quantity, u.unit, u.is_weighed,
       CASE WHEN s.has_base THEN COALESCE(ph.n, 0) ELSE COALESCE(s.store_rows, 0) END AS stores,
       l.price, COALESCE(s.events, 0)
FROM unmapped AS u
LEFT JOIN chains AS c ON c.id = u.chain_id
LEFT JOIN physical AS ph ON ph.chain_id = u.chain_id
LEFT JOIN stats AS s ON s.item_id = u.id
LEFT JOIN latest AS l ON l.item_id = u.id
ORDER BY u.id
"""


def items_from_db(conn: Any, *, misses_days: int = 30) -> ItemPool:
    """The unmapped items of a loaded database, with stores, latest price and price events.
    Items that no price row refers to are kept (stores 0): they were loaded but never priced."""
    total = conn.execute("SELECT count(*) FROM items WHERE chain_id <> 'gold'").fetchone()[0]
    rows = conn.execute(ITEMS_SQL).fetchall()
    items = [
        CandidateItem(
            chain_id=r[1],
            chain_name=r[2],
            item_code=r[3],
            barcode=r[4] or None,
            raw_name=r[5],
            manufacturer=r[6],
            quantity=r[7],
            unit=r[8],
            is_weighed=bool(r[9]),
            stores=int(r[10]),
            price=r[11],
            price_events=int(r[12]),
            item_id=r[0],
        )  # fmt: skip
        for r in rows
    ]
    chains = {r[0]: r[1] for r in conn.execute("SELECT id, name FROM chains").fetchall()}
    try:
        with conn.transaction():
            misses = [
                (str(q), int(n))
                for q, n in conn.execute(
                    "SELECT query_norm, count(*) FROM search_misses"
                    " WHERE seen_at >= now() - make_interval(days => %s) GROUP BY 1",
                    (misses_days,),
                ).fetchall()
            ]
    except Exception:  # noqa: BLE001 - a database without the table (older migrations)
        misses = []
    return ItemPool(
        items=items, total_items=total, mapped_items=total - len(items), source="database",
        chains=chains, misses=misses, as_of=date.today(),
    )  # fmt: skip


def items_from_fixtures(catalog: Catalog, fixtures_dir: Path | None = None) -> ItemPool:
    """The committed real price files (``services/ingest/tests/fixtures/<chain>/real``, 200 rows
    per chain), no database: the items the rule pipeline cannot map are the unmapped ones.

    Offline and small; it is how the tests and a first look run. A fixture is one store's file, so
    ``stores`` is 1 and ``price_events`` is 1."""
    from smartcart_catalog.review_packet import FIXTURES_DIR, SourceItem, match_items
    from smartcart_ingest.adapters import REGISTRY

    fixtures_dir = fixtures_dir or FIXTURES_DIR
    by_slug = {getattr(c, "slug", None): c for c in REGISTRY.values()}
    found: list[tuple[SourceItem, Decimal | None]] = []
    chains: dict[str, str] = {}
    when: date | None = None
    for slug in sorted(s for s in by_slug if s):
        folder = fixtures_dir / slug / "real"
        if not folder.is_dir():
            continue
        adapter = by_slug[slug]()
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name == "MANIFEST.json":
                continue
            try:
                info = adapter.parse_filename(path.name)
            except Exception:  # noqa: BLE001 - not a portal file name
                continue
            if info.kind != "price_full":
                continue
            data = path.read_bytes()
            parsed = adapter.parse(adapter.raw_file_for(path.name, data), data)
            prices = {p.item_code: p.price for p in parsed.prices}
            seen: set[str] = set()
            for rec in parsed.items:
                if rec.item_code in seen:
                    continue
                seen.add(rec.item_code)
                chains[rec.chain_id] = adapter.display_name
                found.append((
                    SourceItem(
                        key=f"{slug}:{rec.item_code}", chain_id=rec.chain_id,
                        chain_name=adapter.display_name, raw_name=rec.raw_name, source="real",
                        barcode=rec.barcode, quantity=rec.quantity, unit=rec.unit,
                        is_weighed=rec.is_weighed, manufacturer=rec.manufacturer,
                        item_code=rec.item_code,
                    ),
                    prices.get(rec.item_code),
                ))  # fmt: skip
    matches = match_items(catalog, [s for s, _ in found]) if found else []
    items: list[CandidateItem] = []
    mapped = 0
    for (src, price), m in zip(found, matches, strict=True):
        if m.canonical_slug is not None:
            mapped += 1
            continue
        items.append(
            CandidateItem(
                chain_id=src.chain_id,
                chain_name=src.chain_name,
                item_code=src.item_code or "",
                raw_name=src.raw_name,
                barcode=src.barcode,
                manufacturer=src.manufacturer,
                quantity=src.quantity,
                unit=src.unit,
                is_weighed=src.is_weighed,
                stores=1,
                price=price,
                price_events=1,
            )  # fmt: skip
        )
    return ItemPool(items=items, total_items=len(found), mapped_items=mapped,
                    source="fixtures", chains=chains, as_of=when)  # fmt: skip
