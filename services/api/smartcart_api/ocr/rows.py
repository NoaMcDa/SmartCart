"""OCR lines to list rows, resolved like ``/parse-list`` and ``/parse-recipe`` (issues #61, #68).

* A list photo: lines -> ``listparse.split_items`` -> quantity/``ו`` handling as in
  ``routes.search.parse_list`` -> ``routes.search.resolve``.
* A receipt: ``smartcart_catalog.receipt`` gives item lines with a printed quantity; the names
  (abbreviations expanded; also tried without the printed pack size and brand, which the "any
  brand" catalog does not carry) go through the same resolver and the receipt's quantity is kept.

The floor is the recipe route's: a best hit under ``MIN_CONFIDENCE`` (0.70, the ambiguity cap)
goes to ``unresolved`` with the line as read. Never a guess (D5). Reading the photo adds a second
way to be wrong (a misread letter can spell another product), so the matcher's thresholds are the
minimum, not the whole answer: rows the OCR engine is not trusted on (a handwritten list read by
Tesseract) are all marked ``needs_confirmation``.
"""

from __future__ import annotations

import re
from decimal import Decimal

import psycopg

from smartcart_api import schemas
from smartcart_api.listparse import MAX_QUANTITY, Fragment, parse_fragment, split_items, split_vav
from smartcart_api.routes.search import AMBIGUOUS_CAP, _row, resolve
from smartcart_api.search import ancestors
from smartcart_catalog.receipt import Receipt, query_variants

MIN_CONFIDENCE = AMBIGUOUS_CAP  # 0.70, as /parse-recipe
MAX_LINES = 200  # a photo of a long receipt; more is noise
_LETTERS = re.compile(r"[א-תA-Za-z]{2}")


def _readable(text: str) -> bool:
    return bool(_LETTERS.search(text))


def _fragments(conn: psycopg.Connection, text: str) -> list[tuple[Fragment, list, float]]:
    """Split ``text`` into fragments and resolve each, as parse_list does."""
    resolved: list[tuple[Fragment, list, float]] = []
    for part in split_items(text):
        if not _readable(part):
            continue
        pieces = split_vav(part)
        parsed = []
        for piece in pieces:
            frag = parse_fragment(piece)
            parsed.append((frag, *resolve(conn, frag.text)))
        if len(pieces) > 1:
            whole = parse_fragment(part)
            w_hits, w_conf = resolve(conn, whole.text)
            if w_conf > min(c for _, _, c in parsed):
                resolved.append((whole, w_hits, w_conf))
                continue
        resolved.extend(parsed)
    return resolved


def _finish(
    conn: psycopg.Connection,
    resolved: list[tuple[Fragment, list, float]],
    *,
    confirm_all: bool,
) -> tuple[list[schemas.ParsedRow], list[str]]:
    found = [(f, h, c) for f, h, c in resolved if h and c >= MIN_CONFIDENCE]
    unresolved = [f.input_text.strip() for f, h, c in resolved if not h or c < MIN_CONFIDENCE]
    chains = ancestors(conn, {h[0].taxonomy_id for _, h, _ in found}) if found else {}
    rows = [_row(conn, f, h, c, {}, chains) for f, h, c in found]
    if confirm_all:
        rows = [
            r if r.needs_confirmation else r.model_copy(update={"needs_confirmation": True})
            for r in rows
        ]
    return rows, unresolved


def rows_from_list_lines(
    conn: psycopg.Connection, lines: list[str], *, confirm_all: bool = False
) -> tuple[list[schemas.ParsedRow], list[str]]:
    """A handwritten (or printed) list: one product per line, quantities as typed."""
    text = "\n".join(lines[:MAX_LINES])
    return _finish(conn, _fragments(conn, text), confirm_all=confirm_all)


def rows_from_receipt(
    conn: psycopg.Connection, receipt: Receipt
) -> tuple[list[schemas.ParsedRow], list[str]]:
    """Receipt items: the printed quantity is kept; repeated products are merged."""
    merged: dict[tuple[str, str | None], tuple[str, Decimal]] = {}
    for item in receipt.items[:MAX_LINES]:
        if not _readable(item.text):
            continue
        key = (item.text, item.unit)
        qty = item.quantity if item.quantity and item.quantity > 0 else Decimal(1)
        if key in merged:
            merged[key] = (merged[key][0], merged[key][1] + qty)
        else:
            merged[key] = (item.raw or item.text, qty)
    resolved = []
    for (text, unit), (raw, qty) in merged.items():
        hits, conf = [], 0.0
        for variant in query_variants(text):  # fuller name first; a tie keeps the fuller name
            v_hits, v_conf = resolve(conn, variant)
            if v_hits and v_conf > conf:
                hits, conf = v_hits, v_conf
        quantity = min(qty, MAX_QUANTITY)
        resolved.append((Fragment(raw, text, quantity, unit), hits, conf))
    return _finish(conn, resolved, confirm_all=False)
