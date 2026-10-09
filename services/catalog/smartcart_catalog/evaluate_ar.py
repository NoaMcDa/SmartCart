"""Arabic list-entry evaluation (issue #73): precision and recall over ``POST /parse-list``.

The Hebrew harness (``evaluate.py``) judges item-to-canonical matching on a gold set of chain
items. Arabic shoppers do not meet chain items: they type a list line, so this harness judges the
step they see, the resolution of a list line to a canonical product, with the API's own code
(``smartcart_api.routes.search.parse_list``: list splitting, quantities, Arabic retrieval, hard
checks, confidence, ambiguity). Lines come from ``data/gold/arabic_queries.yaml``: each has the
canonical slug it must resolve to, or ``none`` (not in the catalog, too general, or stating an
attribute no canonical has), and the flexibility level the shopper set.

Metric definitions (the set is SYNTHETIC: not evidence of real precision):

* A line is *served* when its row has a canonical and a confidence at or above ``floor``
  (default: the API's ``CONFIRM_BELOW``, 0.75, the point at which the app stops asking the user to
  confirm). A row below that is shown as a suggestion, never as an answer.
* A served line is *correct* when its canonical is the expected slug. A served line whose
  expectation is ``none`` is wrong.
* precision = correct / served; recall = correct / lines that expect a slug. Per flexibility level
  (the level the line was sent with; ``flex_defaults`` set to it for every taxonomy node) and
  overall. A level with no served line has no precision (``n/a``) and fails the gate.
* The *shown* precision uses the lower ``NOT_FOUND_BELOW`` floor (0.35): it includes the
  suggestions the app asks the user to confirm. It is reported, not gated.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
import yaml

from smartcart_catalog.embed import embed_canonicals
from smartcart_catalog.seed import load_catalog, seed_all

LEVELS: tuple[str, ...] = ("exact", "any_brand", "close")
DEFAULT_QUERIES = Path(__file__).resolve().parents[3] / "data" / "gold" / "arabic_queries.yaml"


@dataclass(frozen=True)
class ArLine:
    q: str
    expect: str  # a canonical slug, or "none"
    flex: str = "any_brand"
    holdout: bool = False
    """Written after the rules were tuned and run once before any further change; reported
    separately because it is the less optimistic number."""


@dataclass(frozen=True)
class Outcome:
    line: ArLine
    slug: str | None  # the canonical the row resolved to, when it has one
    confidence: float
    rows: int
    served: bool
    shown: bool
    correct: bool
    in_candidates: bool

    @property
    def wrong(self) -> bool:
        return self.served and not self.correct


@dataclass
class ArReport:
    outcomes: list[Outcome]
    precision: dict[str, float] = field(default_factory=dict)
    recall: dict[str, float] = field(default_factory=dict)
    support: dict[str, int] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "synthetic": True,
            "precision": self.precision,
            "recall": self.recall,
            "support": self.support,
            **self.extra,
            "wrong": [
                {"q": o.line.q, "expect": o.line.expect, "got": o.slug,
                 "confidence": o.confidence, "flex": o.line.flex}
                for o in self.outcomes if o.wrong
            ],
        }  # fmt: skip


# --- loading ---------------------------------------------------------------------------------------


def load_lines(path: Path = DEFAULT_QUERIES) -> list[ArLine]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    default = doc.get("default_flex", "any_brand")
    lines = [
        ArLine(str(e["q"]), str(e["expect"]), str(e.get("flex", default)), bool(e.get("holdout")))
        for e in doc["queries"]
    ]
    bad = [ln for ln in lines if ln.flex not in LEVELS]
    if bad:
        raise ValueError(f"unknown flex in {path}: {[(b.q, b.flex) for b in bad]}")
    return lines


# --- metrics (pure) ---------------------------------------------------------------------------------


def compute(outcomes: list[Outcome]) -> ArReport:
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    support: Counter[str] = Counter()
    groups: dict[str, list[Outcome]] = defaultdict(list)
    for o in outcomes:
        groups[o.line.flex].append(o)
        groups["all"].append(o)
    for level in (*LEVELS, "all"):
        group = groups.get(level, [])
        served = [o for o in group if o.served]
        correct = [o for o in served if o.correct]
        positives = [o for o in group if o.line.expect != "none"]
        if served:
            precision[level] = len(correct) / len(served)
        if positives:
            recall[level] = len(correct) / len(positives)
        support[f"lines_{level}"] = len(group)
        support[f"served_{level}"] = len(served)
        support[f"correct_{level}"] = len(correct)
        support[f"positives_{level}"] = len(positives)
    shown = [o for o in outcomes if o.shown]
    held = [o for o in outcomes if o.line.holdout]
    held_served = [o for o in held if o.served]
    held_positives = [o for o in held if o.line.expect != "none"]
    extra = {
        "holdout_lines": len(held),
        "holdout_served": len(held_served),
        "holdout_precision": (
            sum(1 for o in held_served if o.correct) / len(held_served) if held_served else None
        ),
        "holdout_recall": (
            sum(1 for o in held_served if o.correct) / len(held_positives)
            if held_positives
            else None
        ),
        "shown_precision": (sum(1 for o in shown if o.correct) / len(shown)) if shown else None,
        "recall_with_candidates": (
            sum(1 for o in outcomes if o.correct or o.in_candidates)
            / max(1, sum(1 for o in outcomes if o.line.expect != "none"))
        ),
        "split_lines": sum(1 for o in outcomes if o.rows != 1),
        "none_lines_served": sum(1 for o in outcomes if o.line.expect == "none" and o.served),
    }
    return ArReport(outcomes, precision, recall, dict(support), extra)


def passes(report: ArReport, threshold: float, level: str = "any_brand") -> bool:
    value = report.precision.get(level)
    return value is not None and value >= threshold


def _fmt(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "n/a"


def format_report(report: ArReport, show_errors: int = 30) -> str:
    out = ["NOTE: synthetic Arabic query set (data/gold/arabic_queries.yaml), not evidence"]
    out.append(f"{'level':<10} {'precision':>9} {'recall':>7} {'served':>7} {'correct':>8}"
               f" {'lines':>6} {'expect a slug':>14}")  # fmt: skip
    s = report.support
    for level in (*LEVELS, "all"):
        out.append(
            f"{level:<10} {_fmt(report.precision.get(level)):>9}"
            f" {_fmt(report.recall.get(level)):>7}"
            f" {s.get('served_' + level, 0):>7} {s.get('correct_' + level, 0):>8}"
            f" {s.get('lines_' + level, 0):>6} {s.get('positives_' + level, 0):>14}"
        )
    e = report.extra
    out.append(
        "shown precision (confidence >= 0.35, incl. suggestions to confirm): "
        f"{_fmt(e['shown_precision'])}; recall counting suggestions: "
        f"{_fmt(e['recall_with_candidates'])}"
    )
    out.append(
        f"expect-none lines served: {e['none_lines_served']}; lines with other than one row: {e['split_lines']}"
    )
    if e["holdout_lines"]:
        out.append(
            f"held-out lines ({e['holdout_lines']}, written after tuning): precision "
            f"{_fmt(e['holdout_precision'])}, recall {_fmt(e['holdout_recall'])}, "
            f"served {e['holdout_served']}"
        )
    for o in [o for o in report.outcomes if o.wrong][:show_errors]:
        out.append(f"  WRONG {o.line.q!r}: expected {o.line.expect}, got {o.slug}"
                   f" ({o.confidence:.2f}, {o.line.flex})")  # fmt: skip
    missed = [o for o in report.outcomes if o.line.expect != "none" and not o.served]
    for o in missed[:show_errors]:
        out.append(f"  MISSED {o.line.q!r}: expected {o.line.expect}, got {o.slug}"
                   f" ({o.confidence:.2f}, {o.line.flex})")  # fmt: skip
    return "\n".join(out)


# --- running over the API ---------------------------------------------------------------------------


def run_lines(
    conn: psycopg.Connection, lines: list[ArLine], floor: float | None = None
) -> list[Outcome]:
    """Resolve every line with the API's ``parse_list`` and judge it. The database must hold the
    seeded canonicals (``smartcart-catalog seed``)."""
    try:
        from smartcart_api import schemas
        from smartcart_api.routes.search import CONFIRM_BELOW, NOT_FOUND_BELOW, parse_list
    except ImportError as exc:  # the API package is part of the uv workspace
        raise RuntimeError("evaluate-ar needs smartcart-api installed (uv sync)") from exc

    floor = CONFIRM_BELOW if floor is None else floor
    ids = {slug: cid for cid, slug in conn.execute("SELECT id, slug FROM canonical_products")}
    slugs = {cid: slug for slug, cid in ids.items()}
    taxonomy = [r[0] for r in conn.execute("SELECT id FROM taxonomy")]
    out: list[Outcome] = []
    for line in lines:
        resp = parse_list(
            schemas.ParseListRequest(text=line.q, flex_defaults={t: line.flex for t in taxonomy}),
            conn,
        )
        rows = resp.rows
        row = next((r for r in rows if r.canonical is not None and r.confidence >= floor), None)
        row = row or (rows[0] if rows else None)
        if row is None or row.canonical is None or row.not_found:
            slug, conf = None, (row.confidence if row else 0.0)
        else:
            slug, conf = slugs.get(row.canonical.canonical_id), row.confidence
        served = slug is not None and conf >= floor
        wanted = ids.get(line.expect)
        candidates = {c.canonical_id for r in rows for c in r.candidates}
        out.append(
            Outcome(
                line=line,
                slug=slug,
                confidence=conf,
                rows=len(rows),
                served=served,
                shown=slug is not None and conf >= NOT_FOUND_BELOW,
                correct=served and line.expect != "none" and slug == line.expect,
                in_candidates=wanted is not None and wanted in candidates,
            )
        )
    return out


def run_evaluation(
    conn: psycopg.Connection,
    lines: list[ArLine] | None = None,
    *,
    seed: bool = True,
    embed: bool = True,
    floor: float | None = None,
) -> ArReport:
    """Seed the canonicals, embed their names, send every line through ``/parse-list``.

    ``embed`` runs ``embed_canonicals`` with the API's query embedder (``$API_QUERY_EMBEDDER``,
    ``hash`` when unset), which also writes the Arabic name vectors the Arabic vector retriever
    reads (issue #73): the measured retrieval is then what production runs, with vectors.
    """
    if seed:
        seed_all(conn, load_catalog())
    if embed:
        from smartcart_api.embedding import query_embedder

        embed_canonicals(conn, query_embedder().inner)
    return compute(run_lines(conn, lines if lines is not None else load_lines(), floor))
