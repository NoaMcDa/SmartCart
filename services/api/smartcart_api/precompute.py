"""Nightly effective-price precompute (issue #47, docs/architecture.md section 4, layer 3).

For every (canonical product, store, flexibility level) pick the item with the lowest effective
unit price and store it in ``effective_prices``. ``/compare`` and ``/optimize`` only read that
table.

Which items compete (decision D4): an item mapped in ``item_canonical`` at level ``m``
qualifies for a requested level ``L`` when ``m`` is at or below ``L`` in exact < any_brand <
close. So ``exact`` rows use only exact mappings, ``any_brand`` adds any_brand mappings and
``close`` adds close substitutes. Mappings flagged ``needs_review`` (uncertain model matches,
or a "not good" substitution report) are left out until a human reviews them.

The price of an item at a store is the store's latest event, else the chain base price (the
semantics of ``current_price()``), as of ``as_of``. Only price and promo rows from files whose
``file_tracking.status`` is ``loaded`` count (rows with no ``file_id``, written by hand or by
tests, count too): a quarantined or failed file never feeds a price.

Promo folding, per promo active at ``as_of`` (``starts_at <= as_of < ends_at``, open ends allowed)
for that store or chain-wide, linked to the item in ``promo_items``. The reward mapping follows
the adapters' provisional mapping (docs/adapters.md) and is not yet verified on real files:

| reward_type | reading | effective price per pack | promo_min_qty |
|---|---|---|---|
| price | ``reward_value`` is the promo price of one unit | reward_value | min_qty or 1 |
| percent | ``reward_value`` is the discount, 20 = 20 %, 0.2 = 20 % | shelf * (1 - rate) | min_qty or 1 |
| buy_x_get_y | buy X = ``min_qty`` (default 1), get Y = ``reward_value`` free | shelf * X / (X + Y) | X + Y |
| bundle | N = ``min_qty`` for ``reward_value`` in total ("3 for 20"); a value below one shelf price is read as a per-unit price | reward_value / N | N |
| other | not applied | | |

A promo that would not lower the price is ignored. ``max_qty`` and daily ``hours`` windows are
not applied (phase 2 MILP, with cross-item promos). The effective unit price is the item's unit
price (per 100 g, 100 ml, unit, or kg for weighed goods, converted to the canonical's base unit)
scaled by effective price / shelf price.

Club promos (``club_only``) can win; the row then has ``club_required``/``club_name`` and the
best option without any club promo in ``noclub``, which ``/compare`` uses for users who did not
mark that club. A club promo is never applied for them.

The job is idempotent: it upserts on the primary key and deletes rows of the processed chains
that this run did not produce. A ``match_runs`` row (kind ``precompute``) records the counts.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

import psycopg
import structlog
from psycopg.types.json import Jsonb

log = structlog.get_logger("smartcart_api.precompute")

FLEX_ORDER = {"exact": 0, "any_brand": 1, "close": 2}
LEVELS = ("exact", "any_brand", "close")
_Q4 = Decimal("0.0001")
_ONE = Decimal(1)
_HUNDRED = Decimal(100)


@dataclass(frozen=True)
class PromoTerms:
    id: int
    store_id: int | None
    description: str
    club_only: bool
    club_name: str | None
    min_qty: Decimal | None
    reward_type: str
    reward_value: Decimal | None


@dataclass(frozen=True)
class Option:
    """One way to buy an item at a store: the shelf price, or the shelf price folded with a promo."""

    item_id: int
    shelf_price: Decimal
    effective_price: Decimal
    effective_unit_price: Decimal
    uom: str
    price_valid_from: datetime
    is_estimated: bool = False
    promo_id: int | None = None
    promo_min_qty: Decimal | None = None
    promo_description: str | None = None
    club_required: bool = False
    club_name: str | None = None

    def key(self) -> tuple:
        return (self.effective_unit_price, self.effective_price, self.item_id, self.promo_id or 0)

    def as_json(self) -> dict:
        return {
            "item_id": self.item_id,
            "shelf_price": str(self.shelf_price),
            "effective_price": str(self.effective_price),
            "effective_unit_price": str(self.effective_unit_price),
            "uom": self.uom,
            "promo_id": self.promo_id,
            "promo_min_qty": None if self.promo_min_qty is None else str(self.promo_min_qty),
            "price_valid_from": self.price_valid_from.isoformat(),
            "is_estimated": self.is_estimated,
        }


def fold_promo(shelf: Decimal, promo: PromoTerms) -> tuple[Decimal, Decimal] | None:
    """(effective price per pack, quantity needed) for ``promo`` on an item with shelf price
    ``shelf``, or None when the promo does not apply or does not lower the price."""
    v = promo.reward_value
    min_qty = promo.min_qty if promo.min_qty is not None and promo.min_qty > 0 else None
    eff: Decimal
    need: Decimal
    match promo.reward_type:
        case "price":
            if v is None:
                return None
            eff, need = v, max(_ONE, min_qty or _ONE)
        case "percent":
            if v is None or v <= 0:
                return None
            rate = v / _HUNDRED if v > 1 else v
            if rate >= 1:
                return None
            eff, need = shelf * (_ONE - rate), max(_ONE, min_qty or _ONE)
        case "buy_x_get_y":
            x = min_qty or _ONE
            y = v if v is not None and v > 0 else _ONE
            eff, need = shelf * x / (x + y), x + y
        case "bundle":
            if v is None or v <= 0:
                return None
            n = min_qty or _ONE
            if n <= 1:
                eff, need = v, _ONE
            elif v < shelf:  # published per unit, not per bundle
                eff, need = v, n
            else:
                eff, need = v / n, n
        case _:
            return None
    eff = eff.quantize(_Q4, rounding=ROUND_HALF_UP)
    if eff < 0 or eff >= shelf:
        return None
    return eff, need


# --- units -----------------------------------------------------------------------------------

_GRAM = {"g", "gr", "gram", "גרם", "גר", "ג"}
_KG = {"kg", "קג", "קילו", "קילוגרם"}
_ML = {"ml", "מל", "מיליליטר"}
_LITER = {"l", "lt", "ltr", "liter", "litre", "ליטר", "ל"}
_UNIT = {"unit", "units", "יחידה", "יחידות", "יח"}


def derive_unit_price(
    price: Decimal, quantity: Decimal | None, unit: str | None
) -> tuple[Decimal, str] | None:
    """Unit price from the pack size when the file published none: per 100 g, 100 ml or unit."""
    if quantity is None or quantity <= 0 or not unit:
        return None
    u = "".join(ch for ch in unit.strip().lower() if ch not in "\"'׳״. ")
    if u in _GRAM:
        return price * _HUNDRED / quantity, "100g"
    if u in _KG:
        return price * _HUNDRED / (quantity * 1000), "100g"
    if u in _ML:
        return price * _HUNDRED / quantity, "100ml"
    if u in _LITER:
        return price * _HUNDRED / (quantity * 1000), "100ml"
    if u in _UNIT:
        return price / quantity, "unit"
    return None


def to_base_unit(unit_price: Decimal, uom: str, base_unit: str) -> Decimal | None:
    """Convert a unit price to the canonical's base unit, or None when they are incompatible."""
    if uom == base_unit:
        return unit_price
    if uom == "kg" and base_unit == "100g":
        return unit_price / 10
    if uom == "100g" and base_unit == "kg":
        return unit_price * 10
    return None


# --- options per (store, item) ----------------------------------------------------------------


@dataclass(frozen=True)
class PricedItem:
    store_id: int
    item_id: int
    price: Decimal
    unit_price: Decimal | None
    uom: str | None
    is_estimated: bool
    valid_from: datetime
    quantity: Decimal | None
    unit: str | None


_PRICES_SQL = """
WITH ok AS (
  SELECT p.item_id, p.store_id, p.price, p.unit_price, p.uom, p.is_estimated, p.valid_from
  FROM prices AS p
  LEFT JOIN file_tracking AS f ON f.id = p.file_id
  WHERE p.item_id = ANY(%(items)s)
    AND p.valid_from <= %(as_of)s
    AND (p.file_id IS NULL OR f.status = 'loaded')
    AND (p.store_id IS NULL OR p.store_id = ANY(%(stores)s))
),
latest AS (
  SELECT DISTINCT ON (item_id, store_id) *
  FROM ok ORDER BY item_id, store_id, valid_from DESC
)
SELECT s.id, i.id,
       CASE WHEN sp.item_id IS NOT NULL THEN sp.price ELSE bp.price END,
       CASE WHEN sp.item_id IS NOT NULL THEN sp.unit_price ELSE bp.unit_price END,
       CASE WHEN sp.item_id IS NOT NULL THEN sp.uom ELSE bp.uom END,
       CASE WHEN sp.item_id IS NOT NULL THEN sp.is_estimated ELSE bp.is_estimated END,
       CASE WHEN sp.item_id IS NOT NULL THEN sp.valid_from ELSE bp.valid_from END,
       i.quantity, i.unit
FROM stores AS s
JOIN items AS i ON i.chain_id = s.chain_id AND i.id = ANY(%(items)s)
LEFT JOIN latest AS sp ON sp.item_id = i.id AND sp.store_id = s.id
LEFT JOIN latest AS bp ON bp.item_id = i.id AND bp.store_id IS NULL
WHERE s.id = ANY(%(stores)s)
  AND (sp.item_id IS NOT NULL OR bp.item_id IS NOT NULL)
"""

_PROMOS_SQL = """
SELECT p.id, p.store_id, p.description, p.club_only, p.club_name, p.min_qty, p.reward_type,
       p.reward_value, pi.item_id
FROM promos AS p
JOIN promo_items AS pi ON pi.promo_id = p.id
LEFT JOIN file_tracking AS f ON f.id = p.file_id
WHERE p.chain_id = %(chain)s
  AND pi.item_id = ANY(%(items)s)
  AND (p.store_id IS NULL OR p.store_id = ANY(%(stores)s))
  AND (p.starts_at IS NULL OR p.starts_at <= %(as_of)s)
  AND (p.ends_at IS NULL OR p.ends_at > %(as_of)s)
  AND (p.file_id IS NULL OR f.status = 'loaded')
"""


def item_options(
    conn: psycopg.Connection,
    chain_id: str,
    store_ids: list[int],
    item_ids: list[int],
    as_of: datetime,
    base_units: dict[int, str] | None = None,
) -> dict[tuple[int, int], tuple[Option, Option]]:
    """(store_id, item_id) -> (best option overall, best option without a club promo).

    ``base_units`` maps item_id to the base unit its unit price is expressed in (the canonical's);
    items whose unit cannot be converted are left out. Without it the item's own uom is kept.
    """
    if not store_ids or not item_ids:
        return {}
    params = {"items": item_ids, "stores": store_ids, "as_of": as_of, "chain": chain_id}
    priced = [PricedItem(*r) for r in conn.execute(_PRICES_SQL, params).fetchall()]
    promos: dict[int, list[PromoTerms]] = defaultdict(list)
    for r in conn.execute(_PROMOS_SQL, params).fetchall():
        promos[r[8]].append(PromoTerms(*r[:8]))

    out: dict[tuple[int, int], tuple[Option, Option]] = {}
    for p in priced:
        base = base_units.get(p.item_id) if base_units else None
        unit = _unit_price(p, base)
        if unit is None:
            continue
        unit_price, uom = unit
        plain = Option(
            item_id=p.item_id,
            shelf_price=p.price,
            effective_price=p.price,
            effective_unit_price=unit_price.quantize(_Q4, rounding=ROUND_HALF_UP),
            uom=uom,
            price_valid_from=p.valid_from,
            is_estimated=p.is_estimated,
        )
        best, best_noclub = plain, plain
        for promo in promos.get(p.item_id, ()):
            if promo.store_id is not None and promo.store_id != p.store_id:
                continue
            folded = fold_promo(p.price, promo)
            if folded is None:
                continue
            eff, need = folded
            ratio = eff / p.price if p.price else _ONE
            opt = replace(
                plain,
                effective_price=eff,
                effective_unit_price=(unit_price * ratio).quantize(_Q4, rounding=ROUND_HALF_UP),
                promo_id=promo.id,
                promo_min_qty=need,
                promo_description=promo.description,
                club_required=promo.club_only,
                club_name=promo.club_name if promo.club_only else None,
            )
            if opt.key() < best.key():
                best = opt
            if not promo.club_only and opt.key() < best_noclub.key():
                best_noclub = opt
        out[(p.store_id, p.item_id)] = (best, best_noclub)
    return out


def _unit_price(p: PricedItem, base_unit: str | None) -> tuple[Decimal, str] | None:
    if p.unit_price is not None and p.uom:
        unit_price, uom = p.unit_price, p.uom
    else:
        derived = derive_unit_price(p.price, p.quantity, p.unit)
        if derived is None:
            if base_unit in (None, "unit"):
                return p.price, "unit"  # no size known: compared per pack
            return None
        unit_price, uom = derived
    if base_unit is None:
        return unit_price, uom
    converted = to_base_unit(unit_price, uom, base_unit)
    if converted is None:
        return None
    return converted, base_unit


# --- the job ---------------------------------------------------------------------------------


@dataclass
class PrecomputeResult:
    run_id: int
    as_of: datetime
    chains: int = 0
    stores: int = 0
    items_priced: int = 0
    rows_written: int = 0
    rows_deleted: int = 0
    rows_by_flex: dict[str, int] | None = None
    rows_with_promo: int = 0
    rows_club_required: int = 0
    seconds: float = 0.0

    def metrics(self) -> dict:
        return {
            "as_of": self.as_of.isoformat(),
            "chains": self.chains,
            "stores": self.stores,
            "items_priced": self.items_priced,
            "rows_written": self.rows_written,
            "rows_deleted": self.rows_deleted,
            "rows_by_flex": self.rows_by_flex or {},
            "rows_with_promo": self.rows_with_promo,
            "rows_club_required": self.rows_club_required,
            "seconds": round(self.seconds, 3),
        }


def _chain_rows(
    conn: psycopg.Connection, chain_id: str, as_of: datetime
) -> tuple[list[tuple], int, int]:
    mappings = conn.execute(
        "SELECT ic.item_id, ic.canonical_id, ic.flex_level, cp.base_unit"
        " FROM item_canonical AS ic"
        " JOIN items AS i ON i.id = ic.item_id"
        " JOIN canonical_products AS cp ON cp.id = ic.canonical_id"
        " WHERE i.chain_id = %s AND NOT ic.needs_review",
        (chain_id,),
    ).fetchall()
    store_ids = [
        r[0] for r in conn.execute("SELECT id FROM stores WHERE chain_id = %s", (chain_id,))
    ]
    if not mappings or not store_ids:
        return [], len(store_ids), 0
    # One base unit per item for the conversion; an item mapped to canonicals with different
    # base units is priced once per base unit.
    by_base: dict[str, set[int]] = defaultdict(set)
    for item_id, _cid, _lvl, base in mappings:
        by_base[base].add(item_id)
    options: dict[tuple[str, int, int], tuple[Option, Option]] = {}
    for base, items in by_base.items():
        got = item_options(
            conn, chain_id, store_ids, sorted(items), as_of, {i: base for i in items}
        )
        for (sid, iid), opts in got.items():
            options[(base, sid, iid)] = opts
    by_item: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for item_id, cid, lvl, base in mappings:
        by_item[item_id].append((cid, lvl, base))

    best: dict[tuple[int, int, str], tuple[Option, Option]] = {}
    for (base, sid, iid), (opt, noclub) in options.items():
        for cid, lvl, cbase in by_item[iid]:
            if cbase != base:
                continue
            for level in LEVELS:
                if FLEX_ORDER[lvl] > FLEX_ORDER[level]:
                    continue
                key = (cid, sid, level)
                cur = best.get(key)
                if cur is None:
                    best[key] = (opt, noclub)
                else:
                    best[key] = (
                        opt if opt.key() < cur[0].key() else cur[0],
                        noclub if noclub.key() < cur[1].key() else cur[1],
                    )
    rows = []
    for (cid, sid, level), (opt, noclub) in best.items():
        rows.append(
            (
                cid,
                sid,
                opt.item_id,
                level,
                opt.shelf_price,
                opt.effective_unit_price,
                opt.uom,
                opt.promo_id,
                opt.club_required,
                opt.club_name,
                opt.price_valid_from,
                opt.effective_price,
                opt.promo_min_qty,
                opt.is_estimated,
                json.dumps(noclub.as_json()) if opt.club_required else None,
            )
        )
    return rows, len(store_ids), len({iid for (_b, _s, iid) in options})


def precompute_effective_prices(
    conn: psycopg.Connection,
    as_of: datetime | None = None,
    chains: Iterable[str] | None = None,
) -> PrecomputeResult:
    """Recompute ``effective_prices`` for ``chains`` (default: every chain) as of ``as_of``
    (default: now) in one transaction, and record a ``match_runs`` row."""
    as_of = as_of or datetime.now(UTC)
    started = time.monotonic()
    with conn.transaction():
        run_id = conn.execute(
            "INSERT INTO match_runs (kind, metrics) VALUES ('precompute', %s) RETURNING id",
            (Jsonb({"as_of": as_of.isoformat(), "status": "running"}),),
        ).fetchone()[0]
        computed_at = conn.execute("SELECT clock_timestamp()").fetchone()[0]
        chain_ids = (
            sorted(set(chains))
            if chains is not None
            else [r[0] for r in conn.execute("SELECT id FROM chains ORDER BY id")]
        )
        result = PrecomputeResult(run_id=run_id, as_of=as_of, rows_by_flex=dict.fromkeys(LEVELS, 0))
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _ep (LIKE effective_prices INCLUDING DEFAULTS)"
            " ON COMMIT DROP"
        )
        for chain_id in chain_ids:
            rows, n_stores, n_items = _chain_rows(conn, chain_id, as_of)
            result.chains += 1
            result.stores += n_stores
            result.items_priced += n_items
            conn.execute("TRUNCATE _ep")
            with conn.cursor().copy(
                "COPY _ep (canonical_id, store_id, item_id, flex_level, shelf_price,"
                " effective_unit_price, uom, promo_id, club_required, club_name,"
                " price_valid_from, effective_price, promo_min_qty, is_estimated, noclub)"
                " FROM STDIN"
            ) as copy:
                for r in rows:
                    copy.write_row(r)
            conn.execute(
                "INSERT INTO effective_prices (canonical_id, store_id, item_id, flex_level,"
                "   shelf_price, effective_unit_price, uom, promo_id, club_required, club_name,"
                "   price_valid_from, computed_at, effective_price, promo_min_qty, is_estimated,"
                "   noclub)"
                " SELECT canonical_id, store_id, item_id, flex_level, shelf_price,"
                "   effective_unit_price, uom, promo_id, club_required, club_name,"
                "   price_valid_from, %s, effective_price, promo_min_qty, is_estimated, noclub"
                " FROM _ep"
                " ON CONFLICT (canonical_id, store_id, flex_level) DO UPDATE SET"
                "   item_id = EXCLUDED.item_id, shelf_price = EXCLUDED.shelf_price,"
                "   effective_unit_price = EXCLUDED.effective_unit_price, uom = EXCLUDED.uom,"
                "   promo_id = EXCLUDED.promo_id, club_required = EXCLUDED.club_required,"
                "   club_name = EXCLUDED.club_name, price_valid_from = EXCLUDED.price_valid_from,"
                "   computed_at = EXCLUDED.computed_at, effective_price = EXCLUDED.effective_price,"
                "   promo_min_qty = EXCLUDED.promo_min_qty, is_estimated = EXCLUDED.is_estimated,"
                "   noclub = EXCLUDED.noclub",
                (computed_at,),
            )
            result.rows_deleted += conn.execute(
                "DELETE FROM effective_prices AS e USING stores AS s"
                " WHERE s.id = e.store_id AND s.chain_id = %s AND e.computed_at <> %s",
                (chain_id, computed_at),
            ).rowcount
            result.rows_written += len(rows)
            for r in rows:
                result.rows_by_flex[r[3]] += 1
                result.rows_with_promo += r[7] is not None
                result.rows_club_required += bool(r[8])
        result.seconds = time.monotonic() - started
        conn.execute(
            "UPDATE match_runs SET finished_at = clock_timestamp(), metrics = %s WHERE id = %s",
            (Jsonb(result.metrics()), run_id),
        )
    log.info("precompute done", run_id=run_id, **result.metrics())
    return result
