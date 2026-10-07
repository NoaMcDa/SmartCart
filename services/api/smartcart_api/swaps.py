"""Smart-cart swap suggestions (issue #45): the single change to the list that saves the most.

For one store, each canonical's current line (priced by basket.py at the level the user chose)
is compared with the line the same store would give at that level or a looser one:

* ``exact`` with a chosen barcode: the cheapest other exact match, then ``any_brand``, then
  ``close``;
* ``exact`` without a barcode, or ``any_brand``: the looser levels;
* ``close``: nothing looser.

The alternatives come from the same pricing as /compare (``basket.price_baskets``), so they only
contain mappings the matching layer accepted at that level and not flagged ``needs_review``, and
club deals are gated the same way. On top of that a candidate is dropped when one of the
canonical's critical attributes is known on the item and differs (D5: precision over recall; at
``any_brand`` and ``close`` the critical attributes are fixed by D4). The saving is for the
requested quantity, the difference of the two line totals (promos and weight included).

At most one swap per canonical (its largest saving), so the swaps never overlap and the total
is exactly the basket difference after applying all of them. Swaps are suggestions: nothing is
applied, and the user's flexibility level is not changed. Dismissals, undo and the "not a good
substitute" signal are client-side and go through ``/feedback/substitution``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

import psycopg

from smartcart_api import schemas
from smartcart_api.basket import ZERO, StoreInfo, _tags, money, price_baskets
from smartcart_api.precompute import FLEX_ORDER

LOOSER: dict[str, tuple[str, ...]] = {
    "exact": ("any_brand", "close"),
    "any_brand": ("close",),
    "close": (),
}


def _requested(items: list[schemas.BasketItem]) -> dict[int, tuple[str, int | None, Decimal]]:
    """canonical_id -> (level, exact item, total quantity). The first entry of a canonical sets
    the level (basket.py merges repeated canonicals the same way); quantities add up."""
    out: dict[int, tuple[str, int | None, Decimal]] = {}
    for it in items:
        exact = it.exact_item_id if it.flex_level == "exact" else None
        if it.canonical_id in out:
            lvl, ex, qty = out[it.canonical_id]
            out[it.canonical_id] = (lvl, ex, qty + it.quantity)
        else:
            out[it.canonical_id] = (it.flex_level, exact, it.quantity)
    return out


def _candidate_levels(level: str, exact_item: int | None) -> tuple[str, ...]:
    if level == "exact" and exact_item is not None:
        return ("exact", *LOOSER["exact"])  # another barcode of the same exact product, or looser
    return LOOSER[level]


def suggest_swaps(
    conn: psycopg.Connection, req: schemas.CompareRequest, store: StoreInfo
) -> schemas.SwapSuggestionResponse:
    sid = store.store_id
    current = price_baskets(conn, req.items, [store], req.clubs)[sid]
    wanted = _requested(req.items)

    # One pricing call per alternative level, every canonical that may move to it at once.
    by_level: dict[str, list[schemas.BasketItem]] = defaultdict(list)
    for cid, (level, exact, qty) in wanted.items():
        if cid not in current.lines:
            continue  # not sold here at the chosen level: a gap, not a saving
        for alt in _candidate_levels(level, exact):
            by_level[alt].append(schemas.BasketItem(canonical_id=cid, quantity=qty, flex_level=alt))
    alt_lines: dict[tuple[int, str], schemas.PricedItem] = {}
    for alt, items in by_level.items():
        for cid, li in price_baskets(conn, items, [store], req.clubs)[sid].lines.items():
            alt_lines[(cid, alt)] = li

    attrs = _attributes(conn, {li.item_id for li in alt_lines.values()}, set(wanted))
    best: dict[int, schemas.SwapSuggestion] = {}
    for (cid, alt), li in sorted(alt_lines.items(), key=lambda kv: (kv[0][0], FLEX_ORDER[kv[0][1]])):
        cur = current.lines[cid]
        if li.item_id == cur.item_id:
            continue
        saving = money(cur.line_total - li.line_total)
        if saving <= 0:
            continue
        item_attrs, verified, critical, soft, rule_keys, critical_keys = attrs(li.item_id, cid)
        tags = _tags(item_attrs, verified, critical, soft, rule_keys)
        if any(t.status == "differs" and t.key in critical_keys for t in tags):
            continue  # never propose a critical-attribute mismatch
        prev = best.get(cid)
        if prev is None or saving > prev.saving:  # ties keep the stricter level
            best[cid] = schemas.SwapSuggestion(
                canonical_id=cid,
                from_item_id=cur.item_id,
                to_item_id=li.item_id,
                to_display_name_he=li.display_name_he,
                flex_level=alt,
                saving=saving,
                confidence=li.confidence,
                tags=tags,
            )
    swaps = sorted(best.values(), key=lambda s: (-s.saving, s.canonical_id))
    return schemas.SwapSuggestionResponse(
        store_id=sid,
        swaps=swaps,
        top_swap=swaps[0] if swaps else None,
        total_saving=money(sum((s.saving for s in swaps), ZERO)),
        generated_at=datetime.now(UTC),
    )


def _attributes(conn: psycopg.Connection, item_ids: set[int], canonical_ids: set[int]):
    """A lookup (item_id, canonical_id) -> (item attrs, verified keys, canonical critical attrs,
    soft attrs, rule keys, critical keys)."""
    items = {
        r[0]: (r[1], list(r[2]))
        for r in conn.execute(
            "SELECT i.id, COALESCE(a.attrs, '{}'), COALESCE(a.verified_keys, '{}')"
            " FROM items AS i LEFT JOIN item_attributes AS a ON a.item_id = i.id"
            " WHERE i.id = ANY(%s)",
            (sorted(item_ids),),
        )
    }
    canon = {
        r[0]: (r[1], r[2], list(r[3]) + list(r[4]), set(r[1]) | set(r[3]))
        for r in conn.execute(
            "SELECT c.id, c.critical_attrs, c.soft_attrs, COALESCE(r.critical_keys, '{}'),"
            " COALESCE(r.soft_keys, '{}')"
            " FROM canonical_products AS c"
            " LEFT JOIN product_type_rules AS r ON r.product_type = c.product_type"
            " WHERE c.id = ANY(%s)",
            (sorted(canonical_ids),),
        )
    }

    def lookup(item_id: int, cid: int):
        item_attrs, verified = items.get(item_id, ({}, []))
        critical, soft, rule_keys, critical_keys = canon[cid]
        return item_attrs, verified, critical, soft, rule_keys, critical_keys

    return lookup
