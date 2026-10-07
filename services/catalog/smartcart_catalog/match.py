"""The matching pipeline: load an item, block, retrieve top-k, judge, write ``item_canonical``.

Item attributes come from ``item_attributes`` (the extraction pipeline, issue #25). When an item
has no row there yet, ``fallback_attributes`` derives a minimal set from the name with regexes
and an optional keyword ``Lexicon`` (fat percent, fresh/frozen, pack size, product type). It is
a stand-in so the evaluation harness can run before extraction lands; real extraction wins
whenever it exists.

``apply_decisions`` is the only writer of machine mappings. It is idempotent, stores the
judge's reason in ``item_canonical.reason``, never touches a mapping a human decided
(``source = 'human'``), and keeps ``needs_review`` set while a user's "not a good substitute"
report on that mapping is unresolved (issue #43).

A human "not this canonical" is a row with ``human_rejected = true`` (issue #92). The pipeline
drops those canonicals from the item's candidates before the judge runs, so the judge never
proposes them again and picks among the others; ``apply_decisions`` refuses them as well.
``gold_pairs`` is for evaluation only and plays no part here.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import psycopg
from pydantic import ValidationError

from smartcart_catalog.block import (
    Block,
    base_unit_for,
    block_prefix,
    normalize_text,
    top_k,
)
from smartcart_catalog.models import (
    Attributes,
    Candidate,
    Judge,
    MatchDecision,
    NormalizedItem,
    ProductTypeRule,
)

# --- match_runs ---------------------------------------------------------------------------------


def start_run(conn: psycopg.Connection, kind: str) -> int:
    return conn.execute(
        "INSERT INTO match_runs (kind, started_at) VALUES (%s, clock_timestamp()) RETURNING id",
        (kind,),
    ).fetchone()[0]


def finish_run(conn: psycopg.Connection, run_id: int, metrics: Mapping[str, Any]) -> None:
    conn.execute(
        "UPDATE match_runs SET finished_at = clock_timestamp(), metrics = %s::jsonb WHERE id = %s",
        (json.dumps(metrics, ensure_ascii=False, default=str), run_id),
    )


# --- rules --------------------------------------------------------------------------------------


def load_rules(conn: psycopg.Connection) -> dict[str, ProductTypeRule]:
    rows = conn.execute(
        "SELECT product_type, critical_keys, soft_keys FROM product_type_rules"
    ).fetchall()
    return {
        pt: ProductTypeRule(product_type=pt, critical_keys=tuple(ck), soft_keys=tuple(sk))
        for pt, ck, sk in rows
    }


# --- fallback attribute extraction --------------------------------------------------------------


@dataclass(frozen=True)
class Lexicon:
    """Keywords for the fallback extractor: product type keywords (with the taxonomy id that
    gives the block, and attributes the type implies, such as a plant drink's ``base``) and
    flavor/variety keywords. Keywords are matched as whole words on ``normalize_text`` output;
    the longest match wins."""

    product_types: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    categories: Mapping[str, str] = field(default_factory=dict)
    flavors: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    implied: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> Lexicon:
        data = data or {}
        pts: dict[str, tuple[str, ...]] = {}
        cats: dict[str, str] = {}
        implied: dict[str, dict[str, Any]] = {}
        for pt, spec in (data.get("product_types") or {}).items():
            pts[pt] = tuple(normalize_text(k) for k in spec.get("keywords", []))
            if spec.get("taxonomy_id"):
                cats[pt] = spec["taxonomy_id"]
            if spec.get("implied"):
                implied[pt] = dict(spec["implied"])
        flavors = {
            v: tuple(normalize_text(k) for k in kws)
            for v, kws in (data.get("flavors") or {}).items()
        }
        return cls(product_types=pts, categories=cats, flavors=flavors, implied=implied)


def _longest_keyword(text: str, table: Mapping[str, tuple[str, ...]]) -> str | None:
    padded = f" {text} "
    best: tuple[int, str] | None = None
    for value, keywords in table.items():
        for kw in keywords:
            if kw and f" {kw} " in padded and (best is None or len(kw) > best[0]):
                best = (len(kw), value)
    return best[1] if best else None


_STATE_WORDS = {
    "frozen": ("קפוא", "קפואה", "קפואים", "קפואות", "מוקפא", "מוקפאת", "מוקפאים"),
    "fresh": ("טרי", "טריה", "טרייה", "טריים", "טריות"),
    "canned": ("שימורים", "בשימורים", "קופסת שימורים"),
    "chilled": ("מצונן", "מצוננת", "מקורר"),
}
_SUGAR_FREE = ("זירו", "zero", "דיאט", "diet", "ללא סוכר")
_FAT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_MULTI = re.compile(r"(\d+)\s*[x×*]\s*(\d+(?:[.,]\d+)?)\s*(" r"[^\d\s]+)?", re.IGNORECASE)
_QTY = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(ק\"ג|קג|קילו|גרם|גר'|גר|ג'|ג|מ\"ל|מל|ליטר|ל'|ל|יח'|יחידות|kg|g|ml|l)"
    r"(?=$|[\s,.])",
    re.IGNORECASE,
)
_UNIT_CANON = {
    "ק\"ג": "kg", "קג": "kg", "קילו": "kg", "kg": "kg",
    "גרם": "g", "גר'": "g", "גר": "g", "ג'": "g", "g": "g",
    "מ\"ל": "ml", "מל": "ml", "ml": "ml",
    "ג": "g", "ליטר": "l", "ל'": "l", "ל": "l", "l": "l",
    "יח'": "unit", "יחידות": "unit",
}  # fmt: skip


def parse_quantity(name: str) -> tuple[Decimal | None, str | None, int]:
    """(quantity per pack, canonical unit g|kg|ml|l|unit, pack count) from an item name."""
    text = name.replace("״", '"').replace("׳", "'")
    m = _MULTI.search(text)
    if m:
        unit = _UNIT_CANON.get((m.group(3) or "").lower())
        return Decimal(m.group(2).replace(",", ".")), unit, int(m.group(1))
    m = _QTY.search(text)
    if m:
        return Decimal(m.group(1).replace(",", ".")), _UNIT_CANON.get(m.group(2).lower()), 1
    return None, None, 1


def fallback_attributes(raw_name: str, lexicon: Lexicon | None = None) -> Attributes:
    """Minimal rule extraction from the name alone (see the module docstring)."""
    lexicon = lexicon or Lexicon()
    text = normalize_text(raw_name)
    padded = f" {text} "
    fat = None
    m = _FAT.search(raw_name)
    if m:
        fat = Decimal(m.group(1).replace(",", "."))
    state = None
    for value, words in _STATE_WORDS.items():
        if any(f" {normalize_text(w)} " in padded for w in words):
            state = value
            break
    qty, unit, count = parse_quantity(raw_name)
    pack = qty * count if qty is not None else None
    ptype = _longest_keyword(text, lexicon.product_types)
    diet = ("sugar_free",) if any(f" {normalize_text(w)} " in padded for w in _SUGAR_FREE) else ()
    implied = dict(lexicon.implied.get(ptype, {})) if ptype else {}
    return Attributes(
        category_path=lexicon.categories.get(ptype) if ptype else None,
        product_type=ptype,
        fat_pct=fat,
        state=state,  # type: ignore[arg-type]
        flavor=_longest_keyword(text, lexicon.flavors),
        diet_flags=diet,
        pack_size=pack,
        unit=unit,
        base=implied.get("base"),
        variety=implied.get("variety"),
        confidence=0.5,
    )


# --- loading items ------------------------------------------------------------------------------


@dataclass
class ItemContext:
    item: NormalizedItem
    attrs: Attributes
    raw_name: str
    barcode: str | None
    attrs_source: str  # "item_attributes" | "fallback"
    rejected: frozenset[int] = frozenset()
    """Canonicals a human said this item is not (``item_canonical.human_rejected``)."""


def _attributes_from_row(
    attrs: Mapping[str, Any], verified: Sequence[str], conf: Any
) -> Attributes:
    allowed = set(Attributes.model_fields)
    data = {k: v for k, v in attrs.items() if k in allowed}
    if "diet_flags" in data and isinstance(data["diet_flags"], list):
        data["diet_flags"] = tuple(data["diet_flags"])
    data["verified_keys"] = tuple(verified or ())
    if conf is not None:
        data["confidence"] = float(conf)
    return Attributes.model_validate(data)


def load_items(
    conn: psycopg.Connection, item_ids: Iterable[int], lexicon: Lexicon | None = None
) -> dict[int, ItemContext]:
    ids = list(item_ids)
    rows = conn.execute(
        "SELECT i.id, i.raw_name, i.barcode, i.quantity, i.unit, i.is_weighed,"
        "       a.attrs, a.verified_keys, a.confidence, i.chain_id, i.manufacturer"
        " FROM items i LEFT JOIN item_attributes a ON a.item_id = i.id AND a.status = 'ok'"
        " WHERE i.id = ANY(%s)",
        (ids,),
    ).fetchall()
    rejected = rejected_canonicals(conn, ids)
    out: dict[int, ItemContext] = {}
    for (iid, raw_name, barcode, quantity, unit, is_weighed, attrs, verified, conf, chain_id,
         manufacturer) in rows:  # fmt: skip
        source = "fallback"
        parsed = fallback_attributes(raw_name, lexicon)
        a = parsed
        if attrs is not None:
            try:
                a = _attributes_from_row(attrs, verified, conf)
                source = "item_attributes"
            except ValidationError:
                a = parsed
        qty = quantity if quantity is not None else None
        u = unit
        if qty is None or not u:
            q2, u2, count = parse_quantity(raw_name)
            qty = q2 * count if q2 is not None else None
            u = u2
        base = base_unit_for(a.unit or u, is_weighed=bool(is_weighed))
        item = NormalizedItem(
            item_id=iid,
            clean_name=raw_name,
            quantity=qty,
            unit=u,
            total_quantity=qty,
            base_unit=base,
            is_weighed=bool(is_weighed),
            chain_id=chain_id,
            manufacturer=manufacturer,
            barcode=barcode,
            raw_name=raw_name,
        )
        out[iid] = ItemContext(item, a, raw_name, barcode, source, rejected.get(iid, frozenset()))
    return out


def rejected_canonicals(
    conn: psycopg.Connection, item_ids: Sequence[int]
) -> dict[int, frozenset[int]]:
    """item id -> canonicals a human rejected for it (``item_canonical.human_rejected``)."""
    rows = conn.execute(
        "SELECT item_id, array_agg(canonical_id) FROM item_canonical"
        " WHERE human_rejected AND item_id = ANY(%s) GROUP BY item_id",
        (list(item_ids),),
    ).fetchall()
    return {iid: frozenset(cids) for iid, cids in rows}


def block_for(ctx: ItemContext, depth: int = 1) -> Block:
    return Block(prefix=block_prefix(ctx.attrs.category_path, depth), base_unit=ctx.item.base_unit)


# --- the pipeline -------------------------------------------------------------------------------


@dataclass
class MatchResult:
    decision: MatchDecision
    candidates: list[Candidate]
    block: Block
    attrs_source: str


def match_item(
    conn: psycopg.Connection,
    ctx: ItemContext,
    judge: Judge,
    rules: dict[str, ProductTypeRule],
    *,
    k: int = 10,
    depth: int = 1,
) -> MatchResult:
    block = block_for(ctx, depth)
    # Human rejections are removed before the judge sees the candidates, so it never proposes
    # them again; fetch extra rows so k candidates remain.
    candidates = top_k(conn, ctx.item.item_id, k + len(ctx.rejected), block.prefix,
                       block.base_unit)  # fmt: skip
    candidates = [c for c in candidates if c.canonical_id not in ctx.rejected][:k]
    decision = judge.judge(ctx.item, ctx.attrs, candidates, rules)
    if not candidates:
        decision = decision.model_copy(
            update={"reason": f"no candidates in block {block.describe()}"}
        )
    return MatchResult(decision, candidates, block, ctx.attrs_source)


def run_matching(
    conn: psycopg.Connection,
    judge: Judge,
    item_ids: Sequence[int] | None = None,
    *,
    k: int = 10,
    lexicon: Lexicon | None = None,
    apply: bool = True,
    depth: int = 1,
) -> list[MatchResult]:
    """Judge every embedded item (or ``item_ids``) and, with ``apply``, write the decisions."""
    if item_ids is None:
        item_ids = [r[0] for r in conn.execute(
            "SELECT item_id FROM item_embeddings ORDER BY item_id").fetchall()]  # fmt: skip
    run_id = start_run(conn, "judge")
    rules = load_rules(conn)
    contexts = load_items(conn, item_ids, lexicon)
    results = [
        match_item(conn, contexts[i], judge, rules, k=k, depth=depth)
        for i in item_ids
        if i in contexts
    ]
    applied = apply_decisions(conn, [r.decision for r in results]) if apply else {}
    bands = Counter(
        "rejected" if r.decision.canonical_id is None
        else ("review" if r.decision.needs_review else "accepted")
        for r in results
    )  # fmt: skip
    levels = Counter(r.decision.flex_level for r in results if r.decision.canonical_id)
    finish_run(conn, run_id, {
        "judge": getattr(judge, "name", type(judge).__name__),
        "k": k,
        "items": len(results),
        "bands": dict(bands),
        "levels": dict(levels),
        "applied": applied,
    })  # fmt: skip
    return results


def apply_decisions(conn: psycopg.Connection, decisions: Sequence[MatchDecision]) -> dict[str, int]:
    """Upsert machine decisions into ``item_canonical`` with the judge's reason (idempotent,
    never over a human decision, never onto a pair a human rejected)."""
    counts = Counter[str]()
    if not decisions:
        return dict(counts)
    ids = sorted({d.item_id for d in decisions})
    human = {r[0] for r in conn.execute(
        "SELECT DISTINCT item_id FROM item_canonical"
        " WHERE source = 'human' AND NOT human_rejected AND item_id = ANY(%s)",
        (ids,)).fetchall()}  # fmt: skip
    rejected = {(r[0], r[1]) for r in conn.execute(
        "SELECT item_id, canonical_id FROM item_canonical"
        " WHERE human_rejected AND item_id = ANY(%s)",
        (ids,)).fetchall()}  # fmt: skip
    for d in decisions:
        if d.item_id in human:
            counts["skipped_human"] += 1
            continue
        if d.canonical_id is None or d.flex_level is None:
            cur = conn.execute(
                "DELETE FROM item_canonical WHERE item_id = %s AND source <> 'human'", (d.item_id,)
            )
            counts["unmapped"] += 1
            counts["deleted"] += cur.rowcount
            continue
        if (d.item_id, d.canonical_id) in rejected:
            conn.execute(
                "DELETE FROM item_canonical WHERE item_id = %s AND source <> 'human'", (d.item_id,)
            )
            counts["skipped_rejected_by_human"] += 1
            continue
        cur = conn.execute(
            "DELETE FROM item_canonical WHERE item_id = %s AND canonical_id <> %s"
            " AND source <> 'human'",
            (d.item_id, d.canonical_id),
        )
        counts["deleted"] += cur.rowcount
        conn.execute(
            """
            INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,
                                        needs_review, reason)
            VALUES (%(item)s, %(canon)s, %(level)s, %(conf)s, %(source)s,
                    %(review)s OR EXISTS (
                      SELECT 1 FROM substitution_feedback f
                      WHERE f.substitute_item_id = %(item)s AND f.canonical_id = %(canon)s
                        AND f.verdict = 'not_good'),
                    %(reason)s)
            ON CONFLICT (item_id, canonical_id) DO UPDATE SET
              flex_level = EXCLUDED.flex_level,
              confidence = EXCLUDED.confidence,
              source = EXCLUDED.source,
              needs_review = EXCLUDED.needs_review,
              reason = EXCLUDED.reason
            WHERE item_canonical.source <> 'human' AND NOT item_canonical.human_rejected
            """,
            {"item": d.item_id, "canon": d.canonical_id, "level": d.flex_level,
             "conf": d.confidence, "source": d.source, "review": d.needs_review,
             "reason": d.reason or None},
        )  # fmt: skip
        counts["review" if d.needs_review else "accepted"] += 1
    return dict(counts)
