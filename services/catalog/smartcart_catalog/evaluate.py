"""Evaluation harness: precision and recall per flexibility level on the gold set (issue #38).

One command (``smartcart-catalog evaluate``) loads the gold set, embeds what is missing, runs
blocking, retrieval and the judge over every gold item, prints precision and recall per level
as separate numbers plus recall@k of the retrieval stage, and stores the result in
``match_runs`` (kind ``evaluate``) so runs can be compared over time.

Metric definitions. Levels nest: an item that qualifies at ``exact`` also qualifies at
``any_brand`` and ``close``. For a level L, ``qualifies(L)`` is {exact} for exact,
{exact, any_brand} for any_brand and all three for close.

* Served predictions are the judge's auto-accepted decisions (confidence >= 0.90, not
  ``needs_review``). Review-queue and rejected decisions are abstentions: a human or nobody
  decides those, so they cannot make a false match reach a user.
* precision@L = served predictions whose level is in qualifies(L) and whose gold label for
  (item, predicted canonical) is in qualifies(L), divided by served predictions whose level is in
  qualifies(L). A prediction to a canonical with no gold pair for that item counts as wrong.
* recall@L = items recalled at L (as in the numerator above) divided by items with at least one
  gold pair labeled in qualifies(L).
* recall@k (retrieval) = items with at least one positive gold pair (label not no_match) whose
  positive canonical is among the k candidates retrieved inside the item's block, divided by
  those items.

A level with no served predictions has no precision (printed n/a); the ``--fail-below`` gate
treats a missing any_brand precision as a failure.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
import yaml

from smartcart_catalog.block import configure_session
from smartcart_catalog.embed import embed_canonicals, embed_items
from smartcart_catalog.match import (
    Lexicon,
    finish_run,
    load_items,
    load_rules,
    match_item,
    start_run,
)
from smartcart_catalog.models import Embedder as EmbedderProtocol
from smartcart_catalog.models import EvaluationMetrics, FlexLevel, Judge

LEVELS: tuple[FlexLevel, ...] = ("exact", "any_brand", "close")
QUALIFIES: dict[str, frozenset[str]] = {
    "exact": frozenset({"exact"}),
    "any_brand": frozenset({"exact", "any_brand"}),
    "close": frozenset({"exact", "any_brand", "close"}),
}
GOLD_CHAIN = "gold"
DEFAULT_GOLD_DIR = Path(__file__).resolve().parents[3] / "data" / "gold"
RECALL_AT_K_TRIGGER = 0.95
"""If recall@k on the gold set (real embedder) is below this, plan contrastive fine-tuning."""


@dataclass(frozen=True)
class Prediction:
    item_id: int
    canonical_id: int | None
    flex_level: str | None
    needs_review: bool = False

    @property
    def served(self) -> bool:
        return (
            self.canonical_id is not None and self.flex_level is not None and not self.needs_review
        )


@dataclass
class Report:
    metrics: EvaluationMetrics
    extra: dict[str, Any] = field(default_factory=dict)


# --- metric arithmetic (pure) -------------------------------------------------------------------


def compute_metrics(
    gold: Mapping[tuple[int, int], str],
    predictions: Sequence[Prediction],
    retrieved: Mapping[int, Sequence[int]] | None = None,
) -> Report:
    """Precision/recall per level and recall@k from gold labels keyed by (item, canonical)."""
    items_by_level: dict[str, set[int]] = {lvl: set() for lvl in LEVELS}
    positives: dict[int, set[int]] = defaultdict(set)
    gold_items: set[int] = set()
    for (item, canon), lab in gold.items():
        gold_items.add(item)
        for lvl in LEVELS:
            if lab in QUALIFIES[lvl]:
                items_by_level[lvl].add(item)
        if lab != "no_match":
            positives[item].add(canon)

    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    support: dict[str, int] = {}
    served = [p for p in predictions if p.served]
    for lvl in LEVELS:
        q = QUALIFIES[lvl]
        predicted = [p for p in served if p.flex_level in q]
        correct = [p for p in predicted if gold.get((p.item_id, p.canonical_id)) in q]  # type: ignore[arg-type]
        if predicted:
            precision[lvl] = len(correct) / len(predicted)
        if items_by_level[lvl]:
            recalled = {p.item_id for p in correct if p.item_id in items_by_level[lvl]}
            recall[lvl] = len(recalled) / len(items_by_level[lvl])
        support[lvl] = len(items_by_level[lvl])
        support[f"predicted_{lvl}"] = len(predicted)
        support[f"correct_{lvl}"] = len(correct)

    support["items"] = len(gold_items)
    support["pairs"] = len(gold)
    support["served"] = len(served)
    support["review"] = sum(1 for p in predictions if p.canonical_id is not None and p.needs_review)
    support["unmapped"] = sum(1 for p in predictions if p.canonical_id is None)

    recall_at_k = None
    if retrieved is not None:
        with_pos = [i for i in positives if i in retrieved]
        if with_pos:
            hits = sum(1 for i in with_pos if positives[i] & set(retrieved[i]))
            recall_at_k = hits / len(with_pos)

    # What precision would be if the review queue were auto-accepted (shows what review buys).
    unrouted = [p for p in predictions if p.canonical_id is not None and p.flex_level]
    q = QUALIFIES["any_brand"]
    ab = [p for p in unrouted if p.flex_level in q]
    extra = {
        "any_brand_precision_if_review_auto_accepted": (
            sum(1 for p in ab if gold.get((p.item_id, p.canonical_id)) in q) / len(ab)  # type: ignore[arg-type]
            if ab else None
        ),
    }  # fmt: skip
    metrics = EvaluationMetrics(
        precision=precision, recall=recall, recall_at_k=recall_at_k, support=support
    )
    return Report(metrics, extra)


def passes(metrics: EvaluationMetrics, threshold: float, level: str = "any_brand") -> bool:
    value = metrics.precision.get(level)
    return value is not None and value >= threshold


# --- gold set loading ---------------------------------------------------------------------------


def read_gold(gold_dir: Path = DEFAULT_GOLD_DIR) -> tuple[dict[str, Any], list[dict[str, str]]]:
    catalog = yaml.safe_load((gold_dir / "gold_catalog.yaml").read_text(encoding="utf-8"))
    with (gold_dir / "gold_pairs.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return catalog, rows


def load_gold(conn: psycopg.Connection, gold_dir: Path = DEFAULT_GOLD_DIR) -> dict[str, int]:
    """Insert the gold set: chain 'gold', its items, missing taxonomy nodes, product type rules
    and canonicals (an existing canonical with the same slug is left as it is), and
    ``gold_pairs`` (labels updated on re-load). Idempotent."""
    catalog, rows = read_gold(gold_dir)
    conn.execute(
        "INSERT INTO chains (id, name, portal) VALUES (%s, 'Gold set (synthetic)', 'other')"
        " ON CONFLICT (id) DO NOTHING",
        (GOLD_CHAIN,),
    )
    with conn.cursor() as cur:
        for node in sorted(catalog["taxonomy"], key=lambda n: n["level"]):
            cur.execute(
                "INSERT INTO taxonomy (id, parent_id, level, name_he, name_en)"
                " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (
                    node["id"],
                    node["parent_id"],
                    node["level"],
                    node["name_he"],
                    node.get("name_en"),
                ),
            )
        cur.executemany(
            "INSERT INTO product_type_rules (product_type, critical_keys, soft_keys)"
            " VALUES (%s, %s, %s) ON CONFLICT (product_type) DO NOTHING",
            [(r["product_type"], r["critical_keys"], r["soft_keys"])
             for r in catalog["product_type_rules"]],
        )  # fmt: skip
        # An existing canonical keeps its row; it only gains the gold reference barcodes when it
        # has none (the exact rule reads canonical_products.reference_barcodes).
        cur.executemany(
            "INSERT INTO canonical_products AS cp (taxonomy_id, slug, display_name_he,"
            " product_type, base_unit, critical_attrs, soft_attrs, reference_barcodes)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (slug) DO UPDATE SET reference_barcodes = EXCLUDED.reference_barcodes"
            " WHERE cp.reference_barcodes = '{}' AND EXCLUDED.reference_barcodes <> '{}'",
            [(c["taxonomy_id"], c["slug"], c["display_name_he"], c["product_type"],
              c["base_unit"], json.dumps(c["critical_attrs"], ensure_ascii=False),
              json.dumps(c["soft_attrs"], ensure_ascii=False),
              [str(b) for b in c.get("reference_barcodes") or []])
             for c in catalog["canonicals"]],
        )  # fmt: skip
        items: dict[str, tuple[str, str, bool]] = {}
        for r in rows:
            items[r["item_key"]] = (r["item_text"], r["barcode"], r["is_weighed"] == "True")
        cur.executemany(
            "INSERT INTO items (chain_id, item_code, barcode, raw_name, is_weighed)"
            " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (chain_id, item_code) DO UPDATE SET"
            " barcode = EXCLUDED.barcode, raw_name = EXCLUDED.raw_name,"
            " is_weighed = EXCLUDED.is_weighed"
            " WHERE (items.barcode, items.raw_name, items.is_weighed)"
            "   IS DISTINCT FROM (EXCLUDED.barcode, EXCLUDED.raw_name, EXCLUDED.is_weighed)",
            [(GOLD_CHAIN, key, bc, text, w) for key, (text, bc, w) in items.items()],
        )
    item_ids = dict(conn.execute(
        "SELECT item_code, id FROM items WHERE chain_id = %s", (GOLD_CHAIN,)).fetchall())  # fmt: skip
    canon_ids = dict(conn.execute("SELECT slug, id FROM canonical_products").fetchall())
    missing = sorted({r["canonical_slug"] for r in rows} - set(canon_ids))
    if missing:
        raise ValueError(f"gold pairs reference unknown canonicals: {missing[:5]}")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO gold_pairs (item_id, canonical_id, label, category, note)"
            " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (item_id, canonical_id) DO UPDATE SET"
            " label = EXCLUDED.label, category = EXCLUDED.category, note = EXCLUDED.note",
            [(item_ids[r["item_key"]], canon_ids[r["canonical_slug"]], r["label"],
              r["category"], r["note"]) for r in rows],
        )  # fmt: skip
    return {"items": len(items), "pairs": len(rows), "canonicals": len(catalog["canonicals"])}


def gold_lexicon(gold_dir: Path = DEFAULT_GOLD_DIR) -> Lexicon:
    catalog, _ = read_gold(gold_dir)
    return Lexicon.from_mapping(catalog.get("lexicon"))


def gold_labels(conn: psycopg.Connection) -> dict[tuple[int, int], str]:
    return {(i, c): lab for i, c, lab in conn.execute(
        "SELECT item_id, canonical_id, label FROM gold_pairs").fetchall()}  # fmt: skip


# --- the harness --------------------------------------------------------------------------------


def run_evaluation(
    conn: psycopg.Connection,
    judge: Judge,
    embedder: EmbedderProtocol,
    *,
    k: int = 10,
    gold_dir: Path | None = DEFAULT_GOLD_DIR,
    load: bool = True,
    lexicon: Lexicon | None = None,
    depth: int = 1,
) -> Report:
    """Run retrieval and the judge over every item in ``gold_pairs`` and store the metrics."""
    if load and gold_dir is not None:
        load_gold(conn, gold_dir)
    if lexicon is None and gold_dir is not None:
        lexicon = gold_lexicon(gold_dir)
    configure_session(conn)
    gold = gold_labels(conn)
    item_ids = sorted({i for i, _ in gold})
    embed_canonicals(conn, embedder)
    embed_items(conn, embedder, item_ids)
    run_id = start_run(conn, "evaluate")
    rules = load_rules(conn)
    contexts = load_items(conn, item_ids, lexicon)
    predictions: list[Prediction] = []
    retrieved: dict[int, list[int]] = {}
    sources: Counter[str] = Counter()
    for iid in item_ids:
        ctx = contexts[iid]
        res = match_item(conn, ctx, judge, rules, k=k, depth=depth)
        sources[res.attrs_source] += 1
        retrieved[iid] = [c.canonical_id for c in res.candidates]
        d = res.decision
        predictions.append(Prediction(iid, d.canonical_id, d.flex_level, d.needs_review))
    report = compute_metrics(gold, predictions, retrieved)

    categories = _per_category(conn, gold, predictions)
    report.extra.update({
        "judge": getattr(judge, "name", type(judge).__name__),
        "embedder": embedder.model_name,
        "k": k,
        "block_depth": depth,
        "attrs_source": dict(sources),
        "synthetic_gold_set": _is_synthetic(gold_dir),
        "any_brand_precision_by_category": categories,
        "recall_at_k_trigger": RECALL_AT_K_TRIGGER,
    })  # fmt: skip
    computed_at = datetime.now(UTC)
    report.metrics = report.metrics.model_copy(
        update={"run_id": run_id, "computed_at": computed_at}
    )
    finish_run(conn, run_id, {**report.metrics.model_dump(mode="json"), **report.extra})
    return report


def _is_synthetic(gold_dir: Path | None) -> bool:
    if gold_dir is None:
        return False
    catalog, _ = read_gold(gold_dir)
    return bool(catalog.get("synthetic"))


def _per_category(
    conn: psycopg.Connection, gold: Mapping[tuple[int, int], str], predictions: Sequence[Prediction]
) -> dict[str, float | None]:
    cat_of = {i: c for i, c in conn.execute(
        "SELECT DISTINCT ON (item_id) item_id, category FROM gold_pairs ORDER BY item_id, id"
    ).fetchall()}  # fmt: skip
    q = QUALIFIES["any_brand"]
    total: Counter[str] = Counter()
    good: Counter[str] = Counter()
    for p in predictions:
        if p.served and p.flex_level in q:
            cat = cat_of.get(p.item_id) or "?"
            total[cat] += 1
            good[cat] += gold.get((p.item_id, p.canonical_id)) in q  # type: ignore[arg-type]
    return {cat: good[cat] / total[cat] for cat in sorted(total)}


def format_report(report: Report) -> str:
    m = report.metrics
    lines = []
    if report.extra.get("synthetic_gold_set"):
        lines.append(
            "NOTE: synthetic placeholder gold set (data/gold/build_gold.py), not real data"
        )
    lines.append(f"{'level':<10} {'precision':>9} {'recall':>7} {'served':>7} {'gold items':>10}")
    for lvl in LEVELS:
        p = m.precision.get(lvl)
        r = m.recall.get(lvl)
        lines.append(
            f"{lvl:<10} {(f'{p:.4f}' if p is not None else 'n/a'):>9}"
            f" {(f'{r:.4f}' if r is not None else 'n/a'):>7}"
            f" {m.support.get(f'predicted_{lvl}', 0):>7} {m.support.get(lvl, 0):>10}"
        )
    rak = f"{m.recall_at_k:.4f}" if m.recall_at_k is not None else "n/a"
    lines.append(f"retrieval recall@{report.extra.get('k', 'k')}: {rak}")
    lines.append(
        f"items {m.support.get('items', 0)}, pairs {m.support.get('pairs', 0)}, served "
        f"{m.support.get('served', 0)}, review queue {m.support.get('review', 0)}, unmapped "
        f"{m.support.get('unmapped', 0)}"
    )
    alt = report.extra.get("any_brand_precision_if_review_auto_accepted")
    if alt is not None:
        lines.append(f"any_brand precision if the review queue were auto-accepted: {alt:.4f}")
    if m.run_id is not None:
        lines.append(f"saved as match_runs.id = {m.run_id}")
    return "\n".join(lines)
