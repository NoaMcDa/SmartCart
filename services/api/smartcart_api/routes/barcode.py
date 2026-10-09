"""Barcode lookup for in-store scanning, ``GET /items/barcode/{barcode}`` (issue #39).

1. The scanned code is looked up in ``items.barcode`` of every chain (also without leading zeros
   and padded to EAN-13, since chains publish both). Some chain codes are internal, not real
   barcodes; an unknown code answers ``found = false``.
2. The product is mapped to its canonical through ``item_canonical`` at ``exact`` or
   ``any_brand`` (not ``needs_review``, not ``human_rejected``), exact first, then confidence. An
   item with no such mapping answers ``found = false`` with its name: never a guess (D5). A code
   listed in ``canonical_products.reference_barcodes`` resolves to that canonical without prices.
3. ``here`` (with ``store_id``) and ``cheapest_nearby`` price the scanned product itself, live,
   at the store and at the physical stores within ``radius_m``, with the precompute's unit price
   and promo rules and the club rule of /compare (``clubs``; club deals only for members).
4. ``cheaper_substitute``: the lowest ``any_brand`` effective unit price nearby in
   ``effective_prices`` for another product (a different barcode), only when it beats the scanned
   product's unit price (``here``, else ``cheapest_nearby``). It is labeled ``is_substitute`` with
   its mapping confidence and attribute ``tags`` against the scanned product (D10), and compared
   per unit (D6).

Every price carries ``price_valid_from``; the response carries the checkout disclaimer. The scan
is logged with found / not found and the time to answer, never with the location.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Annotated

import psycopg
import structlog
from fastapi import APIRouter, Depends, Query

from smartcart_api import schemas
from smartcart_api.basket import (
    StoreInfo,
    _Choice,
    _from_option,
    _tags,
    chain_clubs,
    club_member,
    gate_club,
    store_info,
    stores_in_radius,
)
from smartcart_api.db import get_conn
from smartcart_api.precompute import item_options
from smartcart_api.search import category_paths

log = structlog.get_logger("smartcart_api.barcode")
router = APIRouter(prefix="/items", tags=["barcode"])

_CODE = re.compile(r"^\d{4,14}$")


def barcode_variants(code: str) -> list[str]:
    code = code.strip()
    out = [code]
    stripped = code.lstrip("0")
    if stripped and stripped != code:
        out.append(stripped)
    if len(code) < 13:
        out.append(code.zfill(13))
    return list(dict.fromkeys(out))


def _store_ref(s: StoreInfo) -> schemas.StoreRef:
    return schemas.StoreRef(
        store_id=s.store_id, chain_id=s.chain_id, chain_name=s.chain_name, store_name=s.store_name,
        city=s.city, distance_m=s.distance_m, geo_precision=s.geo_precision,
        distance_approximate=s.distance_approximate, lat=s.lat, lon=s.lon, channel=s.channel,
    )


def _canonical_ref(conn: psycopg.Connection, cid: int) -> schemas.CanonicalRef:
    cid, name, name_ar, tax, base = conn.execute(
        "SELECT id, display_name_he, names_ar[1], taxonomy_id, base_unit FROM canonical_products"
        " WHERE id = %s",
        (cid,),
    ).fetchone()
    return schemas.CanonicalRef(
        canonical_id=cid, display_name_he=name, display_name_ar=name_ar, taxonomy_id=tax,
        base_unit=base,
        category_path_he=category_paths(conn, [tax]).get(tax, []),
    )


def _price(
    s: StoreInfo, c: _Choice, name: str, promo_desc: dict[int, str], **extra: object
) -> schemas.StorePrice:
    extra.setdefault("is_substitute", False)
    return schemas.StorePrice(
        store=_store_ref(s), item_id=c.item_id, display_name_he=name, shelf_price=c.shelf_price,
        unit_price=c.effective_unit_price, uom=c.uom, price_valid_from=c.price_valid_from,
        promo_description=promo_desc.get(c.promo_id) if c.promo_id else None,
        club_required=c.club_required, club_name=c.club_name, **extra,
    )


@router.get("/barcode/{barcode}", response_model=schemas.BarcodeLookupResponse)
def lookup_barcode(
    barcode: str,
    lon: Annotated[float, Query(ge=-180, le=180)],
    lat: Annotated[float, Query(ge=-90, le=90)],
    conn: Annotated[psycopg.Connection, Depends(get_conn, scope="function")],
    radius_m: Annotated[int, Query(ge=500, le=15000)] = 5000,
    store_id: int | None = None,
    clubs: Annotated[list[str] | None, Query(description="The user's clubs, as in /compare")] = None,
) -> schemas.BarcodeLookupResponse:
    started = time.monotonic()
    now = datetime.now(UTC)
    resp = schemas.BarcodeLookupResponse(barcode=barcode, found=False, generated_at=now)
    try:
        _lookup(conn, resp, barcode, lon, lat, radius_m, store_id, clubs or [], now)
    finally:
        log.info("barcode lookup", found=resp.found, has_here=resp.here is not None,
                 has_substitute=resp.cheaper_substitute is not None,
                 ms=round((time.monotonic() - started) * 1000, 1))
    return resp


def _lookup(
    conn: psycopg.Connection, resp: schemas.BarcodeLookupResponse, barcode: str, lon: float,
    lat: float, radius_m: int, store_id: int | None, clubs: list[str], now: datetime,
) -> None:
    if not _CODE.match(barcode.strip()):
        return
    codes = barcode_variants(barcode)
    items = conn.execute(
        "SELECT id, chain_id, raw_name FROM items WHERE barcode = ANY(%s) ORDER BY id", (codes,)
    ).fetchall()
    if not items:
        ref = conn.execute(
            "SELECT id FROM canonical_products WHERE reference_barcodes && %s::text[]"
            " ORDER BY id LIMIT 1",
            (codes,),
        ).fetchone()
        if ref is not None:
            resp.found = True
            resp.canonical = _canonical_ref(conn, ref[0])
            resp.display_name_he = resp.canonical.display_name_he
        return
    item_ids = [r[0] for r in items]
    names = {r[0]: r[2] for r in items}
    resp.display_name_he = items[0][2]
    mapped = conn.execute(
        "SELECT item_id, canonical_id FROM item_canonical"
        " WHERE item_id = ANY(%s) AND flex_level IN ('exact', 'any_brand')"
        "   AND NOT needs_review AND NOT human_rejected"
        " ORDER BY (flex_level = 'exact') DESC, confidence DESC NULLS LAST, item_id LIMIT 1",
        (item_ids,),
    ).fetchone()
    if mapped is None:
        return  # not found: report-a-gap and manual entry in the app, never a guess
    scanned_item, cid = mapped
    resp.found = True
    resp.canonical = _canonical_ref(conn, cid)
    resp.display_name_he = names[scanned_item]
    base_unit = resp.canonical.base_unit

    loc = schemas.Location(lon=lon, lat=lat, radius_m=radius_m)
    stores = stores_in_radius(conn, loc, include_online=False)
    here_info = None
    if store_id is not None:
        here_info = next((s for s in stores if s.store_id == store_id), None) or store_info(
            conn, store_id, loc
        )
    priced_stores = stores + ([here_info] if here_info and here_info not in stores else [])
    chains = chain_clubs(conn, {s.chain_id for s in priced_stores})
    by_id = {s.store_id: s for s in priced_stores}

    # The scanned product itself, live, at every store of a chain that sells it.
    prices: dict[int, tuple[_Choice, str]] = {}
    for chain_id in sorted({r[1] for r in items}):
        chain_items = [r[0] for r in items if r[1] == chain_id]
        sids = [s.store_id for s in priced_stores if s.chain_id == chain_id]
        chain_name, chain_club_names = chains.get(chain_id, (None, []))
        per_club: dict[tuple[int, int], dict] = {}
        opts = item_options(conn, chain_id, sids, chain_items, now,
                            {i: base_unit for i in chain_items}, per_club)
        for (sid, iid), (best, noclub) in opts.items():
            pick = best
            if best.club_required and not club_member(best.club_name, clubs, chain_name, chain_club_names):
                pick = noclub
                for name, alt in per_club.get((sid, iid), {}).items():
                    if club_member(name, clubs, chain_name, chain_club_names) and alt.key() < pick.key():
                        pick = alt
            c = _from_option(pick)
            cur = prices.get(sid)
            if cur is None or c.key() < cur[0].key():
                prices[sid] = (c, names[iid])

    rows = conn.execute(
        "SELECT store_id, item_id, shelf_price, COALESCE(effective_price, shelf_price),"
        " effective_unit_price, uom, promo_id, promo_min_qty, club_required, club_name,"
        " price_valid_from, is_estimated, noclub"
        " FROM effective_prices WHERE canonical_id = %s AND flex_level = 'any_brand'"
        "   AND store_id = ANY(%s)",
        (cid, [s.store_id for s in stores]),
    ).fetchall()
    subs: list[tuple[_Choice, int]] = []
    for r in rows:
        c = _Choice(*r[1:12])
        pick, _offer = gate_club(c, r[12], clubs, chains.get(by_id[r[0]].chain_id))
        if pick is not None:
            subs.append((pick, r[0]))

    promo_ids = {c.promo_id for c, _ in prices.values() if c.promo_id} | {
        c.promo_id for c, _ in subs if c.promo_id
    }
    promo_desc = dict(conn.execute(
        "SELECT id, description FROM promos WHERE id = ANY(%s)", (sorted(promo_ids),)
    ).fetchall())

    if store_id is not None and store_id in prices:
        c, name = prices[store_id]
        resp.here = _price(by_id[store_id], c, name, promo_desc)
    nearby = [(c, name, sid) for sid, (c, name) in prices.items() if any(s.store_id == sid for s in stores)]
    if nearby:
        c, name, sid = min(nearby, key=lambda t: (t[0].key(), by_id[t[2]].distance_m))
        resp.cheapest_nearby = _price(by_id[sid], c, name, promo_desc)

    reference = resp.here or resp.cheapest_nearby
    if reference is None:
        return
    same = {r[0] for r in conn.execute(
        "SELECT id FROM items WHERE barcode = ANY(%s)", (codes,)
    ).fetchall()}
    better = [
        (c, sid) for c, sid in subs
        if c.item_id not in same and c.effective_unit_price < reference.unit_price
    ]
    if not better:
        return
    c, sid = min(better, key=lambda t: (t[0].key(), by_id[t[1]].distance_m))
    resp.cheaper_substitute = _substitute(conn, by_id[sid], c, cid, scanned_item, promo_desc)


def _substitute(
    conn: psycopg.Connection, s: StoreInfo, c: _Choice, cid: int, scanned_item: int,
    promo_desc: dict[int, str],
) -> schemas.StorePrice:
    critical, soft, rule_keys = conn.execute(
        "SELECT c.critical_attrs, c.soft_attrs,"
        " COALESCE(r.critical_keys, '{}') || COALESCE(r.soft_keys, '{}')"
        " FROM canonical_products AS c"
        " LEFT JOIN product_type_rules AS r ON r.product_type = c.product_type WHERE c.id = %s",
        (cid,),
    ).fetchone()
    attrs = {
        r[0]: (r[1], list(r[2]))
        for r in conn.execute(
            "SELECT item_id, attrs, verified_keys FROM item_attributes WHERE item_id = ANY(%s)",
            ([c.item_id, scanned_item],),
        ).fetchall()
    }
    name, conf = conn.execute(
        "SELECT i.raw_name, ic.confidence FROM items AS i"
        " LEFT JOIN item_canonical AS ic ON ic.item_id = i.id AND ic.canonical_id = %s"
        "   AND NOT ic.human_rejected"
        " WHERE i.id = %s",
        (cid, c.item_id),
    ).fetchone()
    sub_attrs, verified = attrs.get(c.item_id, ({}, []))
    scanned_attrs = attrs.get(scanned_item, ({}, []))[0]
    # Soft attributes are compared with the scanned product, so the tag says what differs
    # from what is in the shopper's hand (the brand, the pack size).
    soft_vs = {**soft, **{k: v for k, v in scanned_attrs.items() if k in set(rule_keys) | set(soft)}}
    soft_vs = {k: v for k, v in soft_vs.items() if k not in critical}
    tags = _tags(sub_attrs, verified, critical, soft_vs, list(rule_keys))
    return _price(
        s, c, name, promo_desc, is_substitute=True,
        confidence=float(conf) if conf is not None else None, tags=tags,
    )
