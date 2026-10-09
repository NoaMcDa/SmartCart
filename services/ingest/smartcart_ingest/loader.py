"""Load one parsed file into Postgres in a single transaction (issue #37).

``load(conn, parsed, adapter)`` writes, in this order and inside one ``conn.transaction()``:

1. ``chains``: the adapter's chain (name, portal).
2. ``stores``: the file's store records, with ``channel`` from ``smartcart_ingest.channel``
   (source declaration, the adapter's ``online_store_rule``, then the shared heuristic);
   location goes to ``stores.geog`` when that column exists (it
   needs PostGIS): the record's own lat/lon, else the geocode / locality tables of
   ``data/geo`` (``_set_locations``, docs/geocoding.md). A price or promo file that names a store the
   Stores file has not delivered yet gets a placeholder row (name = store code) that the next
   Stores file fills in.
3. ``items``: upsert on ``(chain_id, item_code)``.
4. ``ensure_price_partition`` for every distinct month of the price events, then ``prices``:
   change events only. A store event is written when the price, unit price, unit or estimate
   flag differs from the latest event for that item and store, including a return to an
   earlier price. Records older than the latest known event are skipped (the newer event
   already supersedes them). Upsert on the ``prices_event_key`` constraint.
5. ``promos`` (upsert on ``promos_source_key``) and ``promo_items`` (replaced by the file's
   item list for that promo; item codes the chain has never priced are skipped and counted).
6. ``file_tracking``: the file goes to ``loaded`` with its record count.

Any exception rolls the whole transaction back (no row of the file remains, the file is not
loaded) and the file is marked ``failed`` with the reason; the exception is re-raised as
LoadError.

Chain base prices (issue #80): a ``PriceRecord`` with ``store_code=None`` is the chain's base
price and is written with ``store_id NULL``; ``current_price()`` falls back to it for every store
without an exception in force. A store record is written as a store event only when it changes
that store's price in force: against the store's latest exception when it has one (including a
return to the base price, which must supersede the exception), otherwise against the base price
in force at that time. A store price equal to the base is counted in ``prices_same_as_base`` and
not stored, so per-store exceptions stay small.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import partial
from typing import Any

import psycopg
import structlog
from psycopg.types.json import Jsonb

from smartcart_ingest import tracking
from smartcart_ingest.adapters.base import ChainAdapter
from smartcart_ingest.channel import tag_channel
from smartcart_ingest.geocode.resolve import load_index as load_geo_index
from smartcart_ingest.models import ParsedFile, PriceRecord, PromoRecord, StoreRecord

log = structlog.get_logger("smartcart_ingest.loader")

_HUNDRED = Decimal(100)
_TEN = Decimal(10)


class LoadError(RuntimeError):
    def __init__(self, file_id: int | None, reason: str) -> None:
        self.file_id = file_id
        self.reason = reason
        super().__init__(f"file {file_id}: {reason}")


@dataclass
class LoadResult:
    file_id: int
    skipped: bool = False
    record_count: int = 0
    stores: int = 0
    items: int = 0
    prices_written: int = 0
    prices_unchanged: int = 0
    prices_stale: int = 0
    prices_same_as_base: int = 0
    base_prices_written: int = 0
    promos: int = 0
    promo_items: int = 0
    promo_items_unknown: int = 0
    stores_located: dict[str, int] = field(default_factory=dict)
    """Stores that got a location from this file, by precision (docs/geocoding.md)."""
    warnings: list[str] = field(default_factory=list)


def record_count(parsed: ParsedFile) -> int:
    """What the item-count gate compares: price records, promos, or stores, by file kind."""
    kind = parsed.raw.kind
    if kind in {"price_full", "price"}:
        return len(parsed.prices)
    if kind in {"promo_full", "promo"}:
        return len(parsed.promos)
    return len(parsed.stores)


# --- unit prices -------------------------------------------------------------------------------

_QUOTES = re.compile(r"[\"'`׳״“”’]")
_SPACE = re.compile(r"\s+")

# normalized spelling -> (internal uom, factor to multiply the published unit price by)
_UNIT_TABLE: dict[str, tuple[str, Decimal]] = {}
for _names, _uom, _factor in (
    (("100g", "100גרם", "100גר", "100ג", "100gr", "100gram"), "100g", Decimal(1)),
    (("g", "gr", "gram", "גרם", "גר", "ג"), "100g", _HUNDRED),
    (("100ml", "100מל", "100מיליליטר"), "100ml", Decimal(1)),
    (("ml", "מל", "מיליליטר"), "100ml", _HUNDRED),
    (("l", "lt", "ltr", "liter", "litre", "ליטר", "ל", "1ליטר"), "100ml", 1 / _TEN),
    (("unit", "units", "יחידה", "יחידות", "יח", "1יחידה"), "unit", Decimal(1)),
):
    for _n in _names:
        _UNIT_TABLE[_n] = (_uom, _factor)
_KG_NAMES = frozenset({"kg", "קג", "קילו", "קילוגרם", "1קג", "1קילו"})


def _normalize_unit_name(raw: str) -> str:
    s = _QUOTES.sub("", raw.strip().lower())
    s = _SPACE.sub("", s)
    # "ל-100 גרם", "לק"ג": a leading ל ("per") in front of a unit name
    known = _UNIT_TABLE.keys() | _KG_NAMES
    if s.startswith("ל-"):
        s = s[2:]
    elif s not in known and s.startswith("ל") and s[1:] in known:
        s = s[1:]
    return s.lstrip("-")


def normalize_unit_price(
    price: Decimal,
    unit_price: Decimal | None,
    unit_of_measure: str | None,
    is_weighed: bool,
) -> tuple[Decimal | None, str | None, bool]:
    """Return ``(unit_price, uom, is_estimated)`` with uom one of ``100g``, ``100ml``, ``unit``,
    ``kg`` (CLAUDE.md conventions). Weighed produce is per kg and estimated; a weighed item
    without a published unit price uses its price, which chains publish per kg. An unknown unit
    gives ``(None, None, is_weighed)`` and the shelf price is still stored."""
    name = _normalize_unit_name(unit_of_measure) if unit_of_measure else ""
    if is_weighed:
        if unit_price is None or not name or name in _KG_NAMES:
            return (unit_price if unit_price is not None else price), "kg", True
    if unit_price is None:
        return None, None, is_weighed
    if name in _KG_NAMES:
        return unit_price / _TEN, "100g", False
    hit = _UNIT_TABLE.get(name)
    if hit is None:
        return None, None, is_weighed
    uom, factor = hit
    return unit_price * factor, uom, is_weighed


# --- helpers ------------------------------------------------------------------------------------


def _month(ts: datetime) -> date:
    utc = ts.astimezone(UTC)
    return date(utc.year, utc.month, 1)


def _has_column(conn: psycopg.Connection, table: str, column: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pg_attribute WHERE attrelid = %s::regclass AND attname = %s"
        " AND NOT attisdropped",
        (table, column),
    ).fetchone()
    return row is not None


def _jsonb(value: dict[str, Any]) -> Jsonb:
    return Jsonb(value, dumps=partial(json.dumps, ensure_ascii=False, default=str))


def _channel(adapter: ChainAdapter, store: StoreRecord) -> str:
    """Channel per ``smartcart_ingest.channel`` (#53): declared by the source, else the chain's
    ``online_store_rule``, else the shared keyword heuristic."""
    return tag_channel(adapter, store).channel


# --- the steps ---------------------------------------------------------------------------------


def _upsert_chains(conn: psycopg.Connection, parsed: ParsedFile, adapter: ChainAdapter) -> None:
    chain_ids = {parsed.raw.chain_id}
    for group in (parsed.stores, parsed.items, parsed.prices, parsed.promos):
        chain_ids.update(r.chain_id for r in group)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO chains (id, name, portal) VALUES (%s, %s, %s)"
            " ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, portal = EXCLUDED.portal"
            " WHERE (chains.name, chains.portal) IS DISTINCT FROM (EXCLUDED.name, EXCLUDED.portal)",
            [(cid, adapter.display_name, adapter.portal) for cid in sorted(chain_ids)],
        )


_RANK_SQL = "coalesce(array_position(ARRAY['address','street','locality'], {col}), 99)"


def _set_locations(
    conn: psycopg.Connection,
    cur: psycopg.Cursor,
    records: list[StoreRecord],
    online: set[tuple[str, str]],
    result: LoadResult,
) -> None:
    """Set ``stores.geog`` (and its precision and source) for the file's stores.

    Order of preference (docs/geocoding.md): coordinates the chain published in this file
    (``chain``, precision ``address``); else a row of ``data/geo/store_geocodes.csv``; else the
    centroid of the store's CBS locality; else the column stays as it was (NULL for a new store,
    listed by the ``stores_missing_geo`` view). A lookup never replaces a better location than
    it finds: a chain-published point is kept, and a locality centroid does not overwrite a
    street or address.
    """
    labelled = _has_column(conn, "stores", "geo_precision")
    counts: dict[str, int] = {}
    published = [s for s in records if s.lat is not None and s.lon is not None]
    if published:
        if labelled:
            cur.executemany(
                "UPDATE stores SET geog = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,"
                "   geo_precision = 'address', geo_source = 'chain'"
                " WHERE chain_id = %s AND store_code = %s",
                [(s.lon, s.lat, s.chain_id, s.store_code) for s in published],
            )
        else:
            cur.executemany(
                "UPDATE stores SET geog = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"
                " WHERE chain_id = %s AND store_code = %s",
                [(s.lon, s.lat, s.chain_id, s.store_code) for s in published],
            )
        counts["address"] = len(published)
    # An online store (delivery channel) has no place to be found at: it gets no looked-up location.
    rest = [
        s
        for s in records
        if (s.lat is None or s.lon is None) and (s.chain_id, s.store_code) not in online
    ]
    if rest and labelled:
        try:
            index = load_geo_index()
        except OSError as exc:  # an unreadable data/geo must not fail a price load
            log.warning("geo_index_unreadable", error=str(exc))
            index = None
        if index is not None:
            for s in rest:
                point = index.resolve(s.chain_id, s.store_code, s.city)
                if point is None:
                    continue
                cur.execute(
                    "UPDATE stores SET geog = ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography,"
                    "   geo_precision = %(precision)s, geo_source = %(source)s"
                    " WHERE chain_id = %(chain)s AND store_code = %(code)s"
                    "   AND geo_source IS DISTINCT FROM 'chain'"
                    f"   AND {_RANK_SQL.format(col='geo_precision')}"
                    f"       >= {_RANK_SQL.format(col='%(precision)s::text')}",
                    {
                        "lon": point.lon,
                        "lat": point.lat,
                        "precision": point.precision,
                        "source": point.source,
                        "chain": s.chain_id,
                        "code": s.store_code,
                    },
                )
                if cur.rowcount:
                    counts[point.precision] = counts.get(point.precision, 0) + 1
    result.stores_located = counts


def _upsert_stores(
    conn: psycopg.Connection, parsed: ParsedFile, adapter: ChainAdapter, result: LoadResult
) -> dict[tuple[str, str], int]:
    records: dict[tuple[str, str], StoreRecord] = {}
    for s in parsed.stores:
        records[(s.chain_id, s.store_code)] = s
    rows = [
        (s.chain_id, s.store_code, s.name, s.address, s.city, _channel(adapter, s))
        for s in records.values()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO stores (chain_id, store_code, name, address, city, channel)"
            " VALUES (%s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (chain_id, store_code) DO UPDATE SET name = EXCLUDED.name,"
            "   address = EXCLUDED.address, city = EXCLUDED.city, channel = EXCLUDED.channel"
            " WHERE (stores.name, stores.address, stores.city, stores.channel)"
            "   IS DISTINCT FROM (EXCLUDED.name, EXCLUDED.address, EXCLUDED.city, EXCLUDED.channel)",
            rows,
        )
        if _has_column(conn, "stores", "geog"):
            online = {(r[0], r[1]) for r in rows if r[5] == "online"}
            _set_locations(conn, cur, list(records.values()), online, result)
        # Stores named by price or promo records but not (yet) delivered by a Stores file.
        referenced = {(p.chain_id, p.store_code) for p in parsed.prices if p.store_code is not None}
        referenced |= {(p.chain_id, p.store_code) for p in parsed.promos}
        missing = sorted(referenced - set(records))
        if missing:
            placeholders = [
                StoreRecord(chain_id=c, store_code=code, name=code) for c, code in missing
            ]
            cur.executemany(
                "INSERT INTO stores (chain_id, store_code, name, channel)"
                " VALUES (%s, %s, %s, %s) ON CONFLICT (chain_id, store_code) DO NOTHING",
                [(s.chain_id, s.store_code, s.name, _channel(adapter, s)) for s in placeholders],
            )
    result.stores = len(records)
    wanted = set(records) | referenced
    ids: dict[tuple[str, str], int] = {}
    by_chain: dict[str, list[str]] = defaultdict(list)
    for chain_id, code in wanted:
        by_chain[chain_id].append(code)
    for chain_id, codes in by_chain.items():
        for sid, code in conn.execute(
            "SELECT id, store_code FROM stores WHERE chain_id = %s AND store_code = ANY(%s)",
            (chain_id, codes),
        ).fetchall():
            ids[(chain_id, code)] = sid
    return ids


def _upsert_items(conn: psycopg.Connection, parsed: ParsedFile, result: LoadResult) -> None:
    records = {(i.chain_id, i.item_code): i for i in parsed.items}
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO items (chain_id, item_code, barcode, raw_name, manufacturer, quantity,"
            "   unit, is_weighed)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (chain_id, item_code) DO UPDATE SET barcode = EXCLUDED.barcode,"
            "   raw_name = EXCLUDED.raw_name, manufacturer = EXCLUDED.manufacturer,"
            "   quantity = EXCLUDED.quantity, unit = EXCLUDED.unit, is_weighed = EXCLUDED.is_weighed"
            " WHERE (items.barcode, items.raw_name, items.manufacturer, items.quantity, items.unit,"
            "        items.is_weighed)"
            "   IS DISTINCT FROM (EXCLUDED.barcode, EXCLUDED.raw_name, EXCLUDED.manufacturer,"
            "        EXCLUDED.quantity, EXCLUDED.unit, EXCLUDED.is_weighed)",
            [
                (
                    i.chain_id,
                    i.item_code,
                    i.barcode,
                    i.raw_name,
                    i.manufacturer,
                    i.quantity,
                    i.unit,
                    i.is_weighed,
                )
                for i in records.values()
            ],
        )
    result.items = len(records)


def _item_ids(
    conn: psycopg.Connection, codes: set[tuple[str, str]]
) -> dict[tuple[str, str], tuple[int, bool]]:
    """(chain_id, item_code) -> (item id, is_weighed) for the codes that exist."""
    by_chain: dict[str, list[str]] = defaultdict(list)
    for chain_id, code in codes:
        by_chain[chain_id].append(code)
    out: dict[tuple[str, str], tuple[int, bool]] = {}
    for chain_id, chain_codes in by_chain.items():
        for iid, code, weighed in conn.execute(
            "SELECT id, item_code, is_weighed FROM items WHERE chain_id = %s"
            " AND item_code = ANY(%s)",
            (chain_id, chain_codes),
        ).fetchall():
            out[(chain_id, code)] = (iid, weighed)
    return out


def _insert_prices(
    conn: psycopg.Connection,
    parsed: ParsedFile,
    file_id: int,
    store_ids: dict[tuple[str, str], int],
    result: LoadResult,
) -> None:
    if not parsed.prices:
        return
    items = _item_ids(conn, {(p.chain_id, p.item_code) for p in parsed.prices})
    unknown = sorted({p.item_code for p in parsed.prices if (p.chain_id, p.item_code) not in items})
    if unknown:
        raise LoadError(
            file_id, f"{len(unknown)} price records for unknown items, e.g. {unknown[:5]}"
        )

    # (item_id, store_id or None for the base price) -> records, last one wins per valid_from
    events: dict[tuple[int, int | None], dict[datetime, tuple[PriceRecord, bool]]] = defaultdict(
        dict
    )
    for p in parsed.prices:
        item_id, weighed = items[(p.chain_id, p.item_code)]
        sid = None if p.store_code is None else store_ids[(p.chain_id, p.store_code)]
        events[(item_id, sid)][p.observed_at] = (p, weighed)

    for month in sorted({_month(p.observed_at) for p in parsed.prices}):
        conn.execute("SELECT ensure_price_partition(%s::date)", (month,))

    store_list = sorted({s for _, s in events if s is not None})
    item_list = sorted({i for i, _ in events})
    latest: dict[tuple[int, int | None], tuple[datetime, tuple]] = {}
    # The latest store event of each (item, store) in the file, and the latest base event of
    # each item in the file: the base decides whether a store record is an exception at all.
    for item_id, store_id, price, unit_price, uom, est, valid_from in conn.execute(
        "SELECT DISTINCT ON (item_id, store_id) item_id, store_id, price, unit_price, uom,"
        "   is_estimated, valid_from"
        " FROM prices WHERE (store_id = ANY(%s) OR store_id IS NULL) AND item_id = ANY(%s)"
        " ORDER BY item_id, store_id, valid_from DESC",
        (store_list, item_list),
    ).fetchall():
        latest[(item_id, store_id)] = (valid_from, (price, unit_price, uom, est))

    rows: list[tuple] = []
    # Base events first, so store records compare against the base this file delivers.
    base_timeline: dict[int, list[tuple[datetime, tuple]]] = defaultdict(list)
    for key in sorted(events, key=lambda k: (k[1] is not None, k[0], k[1] or 0)):
        by_time = events[key]
        item_id, store_id = key
        last = latest.get(key)
        if store_id is None and last is not None:
            base_timeline[item_id].append(last)
        for observed_at in sorted(by_time):
            p, weighed = by_time[observed_at]
            unit_price, uom, est = normalize_unit_price(
                p.price, p.unit_price, p.unit_of_measure, weighed
            )
            values = (p.price, unit_price, uom, est)
            if last is not None:
                last_at, last_values = last
                if observed_at < last_at:
                    result.prices_stale += 1
                    continue
                if values == last_values:
                    result.prices_unchanged += 1
                    continue
            elif store_id is not None:
                base = _base_in_force(base_timeline.get(item_id, []), observed_at)
                if base is not None and values == base:
                    result.prices_same_as_base += 1
                    continue
            rows.append((item_id, store_id, *values, observed_at, file_id))
            last = (observed_at, values)
            if store_id is None:
                base_timeline[item_id].append(last)
                result.base_prices_written += 1
    if rows:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO prices"
                " (item_id, store_id, price, unit_price, uom, is_estimated, valid_from, file_id)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT ON CONSTRAINT prices_event_key DO UPDATE SET"
                "   price = EXCLUDED.price, unit_price = EXCLUDED.unit_price, uom = EXCLUDED.uom,"
                "   is_estimated = EXCLUDED.is_estimated, file_id = EXCLUDED.file_id",
                rows,
            )
    result.prices_written = len(rows)


def _base_in_force(timeline: list[tuple[datetime, tuple]], at: datetime) -> tuple | None:
    """The values of the latest base event at or before ``at`` among ``timeline``."""
    best: tuple[datetime, tuple] | None = None
    for ts, values in timeline:
        if ts <= at and (best is None or ts >= best[0]):
            best = (ts, values)
    return best[1] if best else None


def _upsert_promos(
    conn: psycopg.Connection,
    parsed: ParsedFile,
    file_id: int,
    store_ids: dict[tuple[str, str], int],
    result: LoadResult,
) -> None:
    if not parsed.promos:
        return
    # Some chains split one promotion over several rows; merge their item lists.
    merged: dict[tuple[str, str, str], PromoRecord] = {}
    codes: dict[tuple[str, str, str], dict[str, None]] = defaultdict(dict)
    for p in parsed.promos:
        key = (p.chain_id, p.store_code, p.promo_id)
        merged[key] = p
        for code in p.item_codes:
            codes[key][code] = None
    keys = list(merged)
    params = []
    for key in keys:
        p = merged[key]
        params.append(
            (
                p.chain_id,
                store_ids[(p.chain_id, p.store_code)],
                p.promo_id,
                p.description,
                p.starts_at,
                p.ends_at,
                p.hours,
                p.club_only,
                p.club_name,
                p.min_qty,
                p.max_qty,
                p.reward_type,
                p.reward_value,
                _jsonb(p.raw),
                file_id,
            )
        )
    promo_ids: list[int] = []
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO promos (chain_id, store_id, promo_id, description, starts_at, ends_at,"
            "   hours, club_only, club_name, min_qty, max_qty, reward_type, reward_value, raw,"
            "   file_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT ON CONSTRAINT promos_source_key DO UPDATE SET"
            "   description = EXCLUDED.description, starts_at = EXCLUDED.starts_at,"
            "   ends_at = EXCLUDED.ends_at, hours = EXCLUDED.hours,"
            "   club_only = EXCLUDED.club_only, club_name = EXCLUDED.club_name,"
            "   min_qty = EXCLUDED.min_qty, max_qty = EXCLUDED.max_qty,"
            "   reward_type = EXCLUDED.reward_type, reward_value = EXCLUDED.reward_value,"
            "   raw = EXCLUDED.raw, file_id = EXCLUDED.file_id"
            " RETURNING id",
            params,
            returning=True,
        )
        while True:
            row = cur.fetchone()
            if row is not None:
                promo_ids.append(row[0])
            if not cur.nextset():
                break

    all_codes = {(k[0], c) for k in keys for c in codes[k]}
    items = _item_ids(conn, all_codes)
    links: list[tuple[int, int]] = []
    keep: dict[int, list[int]] = {}
    for key, pid in zip(keys, promo_ids, strict=True):
        ids = []
        for code in codes[key]:
            hit = items.get((key[0], code))
            if hit is None:
                result.promo_items_unknown += 1
                continue
            ids.append(hit[0])
        keep[pid] = ids
        links.extend((pid, iid) for iid in ids)
    with conn.cursor() as cur:
        cur.executemany(
            "DELETE FROM promo_items WHERE promo_id = %s AND NOT (item_id = ANY(%s))",
            [(pid, ids) for pid, ids in keep.items()],
        )
        cur.executemany(
            "INSERT INTO promo_items (promo_id, item_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            links,
        )
    result.promos = len(keys)
    result.promo_items = len(links)


# --- entry point -------------------------------------------------------------------------------


def load(
    conn: psycopg.Connection,
    parsed: ParsedFile,
    adapter: ChainAdapter,
) -> LoadResult:
    """Load ``parsed`` (whose file must be tracked) in one transaction; see the module doc."""
    row = tracking.get_by_sha(conn, parsed.raw.sha256)
    if row is None:
        raise LoadError(None, f"file {parsed.raw.sha256} is not in file_tracking")
    if row.status == "loaded":
        log.info("skipped: already loaded", file_id=row.id, sha256=row.sha256)
        return LoadResult(file_id=row.id, skipped=True)
    if row.status == "quarantined":
        raise LoadError(row.id, "file is quarantined and must never be loaded")

    result = LoadResult(file_id=row.id, record_count=record_count(parsed))
    try:
        with conn.transaction():
            if row.status != "loading":
                tracking.mark_loading(conn, row.id)
            _upsert_chains(conn, parsed, adapter)
            store_ids = _upsert_stores(conn, parsed, adapter, result)
            _upsert_items(conn, parsed, result)
            _insert_prices(conn, parsed, row.id, store_ids, result)
            _upsert_promos(conn, parsed, row.id, store_ids, result)
            tracking.mark_loaded(conn, row.id, result.record_count, parsed.raw.schema_version)
    except Exception as exc:
        reason = exc.reason if isinstance(exc, LoadError) else f"{type(exc).__name__}: {exc}"
        reason = f"load failed: {reason}"
        tracking.mark_failed(conn, row.id, reason)
        log.error("load failed", file_id=row.id, chain_id=parsed.raw.chain_id, reason=reason)
        raise LoadError(row.id, reason) from exc
    log.info(
        "loaded",
        file_id=row.id,
        chain_id=parsed.raw.chain_id,
        kind=parsed.raw.kind,
        store_code=parsed.raw.store_code,
        records=result.record_count,
        prices_written=result.prices_written,
        prices_unchanged=result.prices_unchanged,
        promos=result.promos,
        promo_items_unknown=result.promo_items_unknown,
    )
    return result
