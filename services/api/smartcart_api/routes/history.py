"""Price history, ``GET /history/{canonical_id}?store_id=&days=`` (issue #28).

Which item's prices make the series:

* with ``store_id``: the item of the store's chain mapped to the canonical at ``exact`` when there
  is one (the product itself), else the store's best ``any_brand`` item in ``effective_prices``;
* without ``store_id``: the best ``any_brand`` item over all stores in ``effective_prices``
  (lowest effective unit price), and the series is that chain's base price;
* when ``effective_prices`` has no row, the mapped (exact or any_brand, not ``needs_review``,
  not ``human_rejected``) item with the highest confidence that has price events.

The ``prices`` table stores change events. The daily series is rebuilt from them: for each day of
the range, the price in force at the end of the day, with ``current_price()`` semantics (the
store's latest event overrides the chain base price; ``store_id`` on a point says which one
applied, null for the chain base price). Only events of loaded files count. Days before the first
known event are left out (a gap, never a flat line drawn backwards). ``unit_price`` is the shelf
unit price in the canonical's base unit (D6); promos are reported as windows, not folded in.

Promo windows: promos linked to the item (``promo_items``), chain-wide or for the store, from
loaded files, whose dates overlap the range; with type, club restriction and parsing confidence.

Query plan: both price queries filter on ``item_id`` and ``store_id`` with a ``valid_from`` range,
so the planner prunes to the monthly partitions of the range and uses ``prices_event_key``
(``item_id, store_id, valid_from``) in each; the "price in force at the start" lookup is an
ordered backward scan with ``LIMIT 1``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from smartcart_api import schemas
from smartcart_api.basket import promo_confidence
from smartcart_api.db import get_conn
from smartcart_api.precompute import unit_price_in

router = APIRouter(prefix="/history", tags=["history"])
_Q4 = Decimal("0.0001")

_OK = "(p.file_id IS NULL OR EXISTS (SELECT 1 FROM file_tracking f WHERE f.id = p.file_id AND f.status = 'loaded'))"

_EVENTS_SQL = """
(SELECT p.store_id, p.price, p.unit_price, p.uom, p.valid_from FROM prices AS p
 WHERE p.item_id = %(item)s AND {store} AND p.valid_from < %(start)s AND {ok}
 ORDER BY p.valid_from DESC LIMIT 1)
UNION ALL
(SELECT p.store_id, p.price, p.unit_price, p.uom, p.valid_from FROM prices AS p
 WHERE p.item_id = %(item)s AND {store}
   AND p.valid_from >= %(start)s AND p.valid_from <= %(now)s AND {ok})
"""
_BASE_EVENTS = _EVENTS_SQL.format(store="p.store_id IS NULL", ok=_OK)
_STORE_EVENTS = _EVENTS_SQL.format(store="p.store_id = %(sid)s", ok=_OK)

_PROMOS_SQL = f"""
SELECT p.starts_at, p.ends_at, p.description, p.reward_type, p.club_only, p.club_name,
       p.raw->>'confidence'
FROM promos AS p JOIN promo_items AS pi ON pi.promo_id = p.id
WHERE pi.item_id = %(item)s AND p.chain_id = %(chain)s
  AND (p.store_id IS NULL OR p.store_id = %(store)s)
  AND (p.starts_at IS NULL OR p.starts_at <= %(now)s)
  AND (p.ends_at IS NULL OR p.ends_at >= %(start)s)
  AND {_OK}
ORDER BY p.starts_at NULLS FIRST, p.id
"""

_MAPPED = (
    " ic.canonical_id = %(cid)s AND NOT ic.needs_review AND NOT ic.human_rejected"
)


def _pick_item(conn: psycopg.Connection, cid: int, store_id: int | None) -> int | None:
    if store_id is not None:
        row = conn.execute(
            "SELECT ic.item_id FROM item_canonical AS ic JOIN items AS i ON i.id = ic.item_id"
            " JOIN stores AS s ON s.chain_id = i.chain_id AND s.id = %(sid)s"
            f" WHERE {_MAPPED} AND ic.flex_level = 'exact'"
            " ORDER BY ic.confidence DESC NULLS LAST, ic.item_id LIMIT 1",
            {"cid": cid, "sid": store_id},
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT item_id FROM effective_prices"
                " WHERE canonical_id = %s AND store_id = %s AND flex_level = 'any_brand'",
                (cid, store_id),
            ).fetchone()
    else:
        row = conn.execute(
            "SELECT item_id FROM effective_prices WHERE canonical_id = %s AND flex_level = 'any_brand'"
            " ORDER BY effective_unit_price, effective_price, item_id LIMIT 1",
            (cid,),
        ).fetchone()
    if row is None:  # nothing precomputed: the most confident mapped item with prices
        row = conn.execute(
            "SELECT ic.item_id FROM item_canonical AS ic JOIN items AS i ON i.id = ic.item_id"
            f" WHERE {_MAPPED} AND ic.flex_level IN ('exact', 'any_brand')"
            "   AND (%(sid)s::bigint IS NULL OR i.chain_id = (SELECT chain_id FROM stores WHERE id = %(sid)s))"
            "   AND EXISTS (SELECT 1 FROM prices AS p WHERE p.item_id = ic.item_id)"
            " ORDER BY ic.confidence DESC NULLS LAST, ic.item_id LIMIT 1",
            {"cid": cid, "sid": store_id},
        ).fetchone()
    return row[0] if row else None


def daily_series(
    events: list[tuple], start: datetime, now: datetime, unit: Callable[[tuple], Decimal]
) -> list[schemas.PricePoint]:
    """One point per day from ``start`` to ``now``: the price in force at the end of the day.

    ``events`` are (store_id, price, unit_price, uom, valid_from); a store event overrides the
    chain base price (store_id None). Days before the first event are left out.
    """
    store_ev = sorted((e for e in events if e[0] is not None), key=lambda e: e[4])
    base_ev = sorted((e for e in events if e[0] is None), key=lambda e: e[4])
    points: list[schemas.PricePoint] = []
    day = start
    si = bi = -1
    while day <= now:
        cutoff = min(day + timedelta(days=1), now + timedelta(microseconds=1))
        while si + 1 < len(store_ev) and store_ev[si + 1][4] < cutoff:
            si += 1
        while bi + 1 < len(base_ev) and base_ev[bi + 1][4] < cutoff:
            bi += 1
        ev = store_ev[si] if si >= 0 else (base_ev[bi] if bi >= 0 else None)
        if ev is not None:
            points.append(schemas.PricePoint(
                date=day, unit_price=unit(ev), shelf_price=ev[1], store_id=ev[0],
            ))
        day += timedelta(days=1)
    return points


@router.get("/{canonical_id}", response_model=schemas.PriceHistoryResponse)
def price_history(
    canonical_id: int,
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    store_id: int | None = None,
    days: Annotated[int, Query(ge=1, le=365, description="Days back from today, 90 by default")] = 90,
) -> schemas.PriceHistoryResponse:
    canon = conn.execute(
        "SELECT base_unit FROM canonical_products WHERE id = %s", (canonical_id,)
    ).fetchone()
    if canon is None:
        raise HTTPException(status_code=404, detail="canonical product not found")
    if store_id is not None and conn.execute(
        "SELECT 1 FROM stores WHERE id = %s", (store_id,)
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail="store not found")
    now = datetime.now(UTC)
    start = datetime.combine(now.date() - timedelta(days=days - 1), time.min, tzinfo=UTC)
    item_id = _pick_item(conn, canonical_id, store_id)
    resp = schemas.PriceHistoryResponse(
        canonical_id=canonical_id, store_id=store_id, days=days, points=[], generated_at=now,
    )
    if item_id is None:
        return resp
    chain_id, name, qty, unit = conn.execute(
        "SELECT chain_id, raw_name, quantity, unit FROM items WHERE id = %s", (item_id,)
    ).fetchone()
    params = {"item": item_id, "start": start, "now": now}
    events = conn.execute(_BASE_EVENTS, params).fetchall()
    if store_id is not None:
        events += conn.execute(_STORE_EVENTS, {**params, "sid": store_id}).fetchall()

    def unit_of(ev: tuple) -> Decimal:
        got = unit_price_in(ev[1], ev[2], ev[3], qty, unit, canon[0])
        return got[0].quantize(_Q4) if got else ev[1]

    points = daily_series(events, start, now, unit_of)
    windows = [
        schemas.PromoWindow(
            starts_at=r[0], ends_at=r[1], description=r[2], promo_type=r[3], club_only=r[4],
            club_name=r[5] if r[4] else None, confidence=promo_confidence(r[6]),
        )
        for r in conn.execute(
            _PROMOS_SQL, {**params, "chain": chain_id, "store": store_id}
        ).fetchall()
    ]
    for p in points:  # the promo of each day, a non-club one first
        day_end = p.date + timedelta(days=1)
        active = [
            w for w in windows
            if (w.starts_at is None or w.starts_at < day_end)
            and (w.ends_at is None or w.ends_at > p.date)
        ]
        active.sort(key=lambda w: w.club_only)
        if active:
            w = active[0]
            p.promo_description = (
                f"{w.description} (מועדון: {w.club_name or 'לא ידוע'})" if w.club_only else w.description
            )
    resp.points = points
    resp.promos = windows
    resp.item_id = item_id
    resp.display_name_he = name
    return resp
