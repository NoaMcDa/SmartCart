"""Scoring for the OCR evaluation (issues #61, #68): pure functions, no I/O, no model.

Receipts are scored per field against the ground truth ``render.py`` writes:

* ``text``: a truth item is right when some parsed item has the same normalized name (the printed
  name through the same abbreviation expansion the pipeline applies; exact match after that);
* ``quantity`` and ``price``: the item aligned to a truth item has the same value (a missing
  quantity counts as 1; weights compare in kg);
* ``total`` and ``chain``: the printed total and the GS1 chain id;
* items also get a precision: parsed items that align to no truth item are spurious.

Lists are scored as read lines (exact after normalization) and, with a catalog, as rows:
``recall`` (the expected canonical is the row's top hit), ``recall with candidates`` (top hit or a
suggested alternative), ``precision of rows the user is not asked to confirm`` (the D5 metric: a
wrong auto-accepted row) and ``distractors kept out of rows`` (a line that is not a product must
not become a row).

All numbers are measured on synthetic images (docs/ocr.md).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from smartcart_catalog.receipt import clean_line, expand_name

_BIDI = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮⁦⁧⁨⁩"))


def norm(text: str) -> str:
    """Comparable form of a line: marks and quotes unified, punctuation and case dropped."""
    s = text.translate(_BIDI)
    s = clean_line(s)
    s = re.sub(r"[^\w\s%]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def norm_name(text: str) -> str:
    return norm(expand_name(text))


def _dec(v: Any) -> Decimal | None:
    return None if v is None else Decimal(str(v))


@dataclass
class Tally:
    """Counts per metric: ``hit`` of ``total``."""

    hit: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, metric: str, ok: bool, n: int = 1) -> None:
        self.total[metric] += n
        self.hit[metric] += n if ok else 0

    def count(self, metric: str, hit: int, total: int) -> None:
        self.total[metric] += total
        self.hit[metric] += hit

    def rate(self, metric: str) -> float | None:
        t = self.total.get(metric, 0)
        return self.hit[metric] / t if t else None

    def merge(self, other: Tally) -> None:
        for m in other.total:
            self.count(m, other.hit[m], other.total[m])


def _align(truth: list[str], parsed: list[str]) -> list[int | None]:
    """For each truth name the index of the parsed name it is aligned with: exact first, then the
    closest at ratio >= 0.7, each parsed name used once."""
    used: set[int] = set()
    out: list[int | None] = [None] * len(truth)
    for i, t in enumerate(truth):
        for j, p in enumerate(parsed):
            if j not in used and p == t:
                out[i] = j
                used.add(j)
                break
    for i, t in enumerate(truth):
        if out[i] is not None:
            continue
        best, best_j = 0.7, None
        for j, p in enumerate(parsed):
            if j in used:
                continue
            r = SequenceMatcher(None, t, p).ratio()
            if r >= best:
                best, best_j = r, j
        if best_j is not None:
            out[i] = best_j
            used.add(best_j)
    return out


def score_receipt(truth: dict[str, Any], receipt: Any) -> Tally:
    """``receipt`` is a ``smartcart_catalog.receipt.Receipt``."""
    t = Tally()
    items = truth["items"]
    truth_names = [norm_name(i["printed"]) for i in items]
    parsed_names = [norm(i.text) for i in receipt.items]
    aligned = _align(truth_names, parsed_names)
    for item, name, j in zip(items, truth_names, aligned, strict=True):
        p = receipt.items[j] if j is not None else None
        t.add("item text", p is not None and parsed_names[j] == name)
        want_q = _dec(item["quantity"])
        got_q = None if p is None else (p.quantity if p.quantity is not None else Decimal(1))
        t.add("quantity", p is not None and got_q == want_q)
        t.add("price", p is not None and _dec(item["price"]) == p.price)
    n_aligned = sum(1 for j in aligned if j is not None)
    t.count("item recall (aligned)", n_aligned, len(items))
    t.count("item precision (aligned)", n_aligned, len(receipt.items))
    t.add("total", receipt.total == _dec(truth["total"]))
    t.add("chain", receipt.chain_id == truth["chain_id"])
    return t


def score_list_lines(truth: dict[str, Any], lines: list[str]) -> Tally:
    """Read lines versus written lines, exact after normalization (row-level reading accuracy)."""
    t = Tally()
    got = {norm(ln) for ln in lines}
    for item in truth["items"]:
        t.add("list line read", norm(item["written"]) in got)
    return t


def score_rows(truth: dict[str, Any], rows: list[dict[str, Any]]) -> Tally:
    """Rows from the real matcher. Each row is ``{"name", "input_text", "needs_confirmation", "candidates"}``."""
    t = Tally()
    expected = {i["canonical"] for i in truth["items"]}
    top = [r["name"] for r in rows]
    for item in truth["items"]:
        want = item["canonical"]
        t.add("catalog recall", want in top)
        t.add("catalog recall (top or candidate)", want in top or any(want in r["candidates"] for r in rows))
    auto = [r for r in rows if not r["needs_confirmation"]]
    t.count("auto-accepted row precision", sum(1 for r in auto if r["name"] in expected), len(auto))
    t.count("all-row precision", sum(1 for r in rows if r["name"] in expected), len(rows))
    distractors = truth.get("distractors", [])
    if distractors:
        norm_d = {norm(d) for d in distractors}
        leaked = sum(1 for r in rows if norm(r.get("input_text", "")) in norm_d)
        t.count("distractors kept out of rows", len(distractors) - leaked, len(distractors))
    return t


METRIC_ORDER = [
    "chain", "total", "item text", "quantity", "price", "item recall (aligned)",
    "item precision (aligned)", "list line read", "catalog recall",
    "catalog recall (top or candidate)", "auto-accepted row precision", "all-row precision",
    "distractors kept out of rows",
]


def table(tally: Tally, title: str) -> str:
    rows = ["", f"#### {title}", "", "| metric | right | of | rate |", "|---|---:|---:|---:|"]
    for m in METRIC_ORDER:
        if tally.total.get(m):
            rows.append(f"| {m} | {tally.hit[m]} | {tally.total[m]} | {tally.hit[m] / tally.total[m]:.1%} |")
    return "\n".join(rows)
