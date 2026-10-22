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
| buy_x_get_y | buy X = ``min_qty`` (default 1), get Y = ``reward_value`` free, or (``get_percent`` P, from ``raw``) P % off: "the second at 50 %" | shelf * (X + Y (1 - P/100)) / (X + Y) | X + Y |
| bundle | N = ``min_qty`` for ``reward_value`` in total ("3 for 20"); a value below one shelf price is read as a per-unit price | reward_value / N | N |
| other | not applied | | |

A promo that would not lower the price is ignored. ``max_qty`` and daily ``hours`` windows are
not applied (phase 2 MILP, with cross-item promos). The effective unit price is the item's unit
price (per 100 g, 100 ml, unit, or kg for weighed goods, converted to the canonical's base unit)
scaled by effective price / shelf price.

The unit price reads the pack from the item's name as well as the chain's fields (``read_unit_price``,
docs/optimizer.md "Packs"): a tray of 12 eggs that the chain files as ``1 יחידות`` is ``price / 12`` an
egg, ``6*1.5 ל'`` is 9000 ml, and when two readings disagree the dearer unit price is used and the
disagreement is recorded in the run's metrics. ``pack_units`` (units in the item, per-unit canonicals)
lets ``/compare`` buy whole packs for the quantity asked.

Club promos (``club_only``) can win; the row then has ``club_required``/``club_name`` and the
best option without any club promo in ``noclub``, which ``/compare`` uses for users who did not
mark that club. A club promo is never applied for them. ``noclub.clubs`` maps each club whose
own best option beats ``noclub`` to that option (issue #19), so a member of club A gets club A's
deal even when club B's deal won the row. Matching a user's clubs to a promo is
``basket.club_member``.

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

from smartcart_catalog.models import NormalizedItem
from smartcart_catalog.normalize import normalize
from smartcart_ingest.unitprice import MAX_BASE_AMOUNT

log = structlog.get_logger("smartcart_api.precompute")

MAX_PACK_SAMPLES = 20
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
    get_percent: Decimal | None = None
    """``buy_x_get_y`` only: the units "got" are this percentage off (100 or None: free)."""


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
    pack_units: Decimal | None = None
    """Units in one shelf item, for a per-unit canonical whose item states its count (12 for a
    tray of 12 eggs); None when the count is not stated or the unit is a weight or a volume."""

    def key(self) -> tuple:
        return (self.effective_unit_price, self.effective_price, self.item_id, self.promo_id or 0)

    def as_json(self) -> dict:
        return {
            "item_id": self.item_id,
            "club_required": self.club_required,
            "club_name": self.club_name,
            "shelf_price": str(self.shelf_price),
            "effective_price": str(self.effective_price),
            "effective_unit_price": str(self.effective_unit_price),
            "uom": self.uom,
            "promo_id": self.promo_id,
            "promo_min_qty": None if self.promo_min_qty is None else str(self.promo_min_qty),
            "price_valid_from": self.price_valid_from.isoformat(),
            "is_estimated": self.is_estimated,
            "pack_units": None if self.pack_units is None else str(self.pack_units),
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
            off = _ONE  # the units got are free ...
            if promo.get_percent is not None:  # ... or this much off ("the second at 50 %")
                if not 0 < promo.get_percent <= _HUNDRED:
                    return None
                off = promo.get_percent / _HUNDRED
            eff, need = shelf * (x + y * (_ONE - off)) / (x + y), x + y
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


_DIM = {"100g": "mass", "100ml": "volume", "unit": "unit"}


def sane_pack(amount: Decimal, base_unit: str) -> bool:
    """A pack of ``amount`` grams, milliliters or units (``base_unit`` 100g, 100ml or unit) that a
    real shelf item can be: positive and within the loader's limits (``unitprice.MAX_BASE_AMOUNT``:
    50 kg, 50 l, 10,000 units)."""
    dim = _DIM.get(base_unit)
    return dim is not None and 0 < amount <= MAX_BASE_AMOUNT[dim]


def derive_unit_price(
    price: Decimal, quantity: Decimal | None, unit: str | None
) -> tuple[Decimal, str] | None:
    """Unit price from the pack size when the file published none: per 100 g, 100 ml or unit.

    None when the pack is not sane (``sane_pack``): at most 50 kg, 50 l or 10,000 units. Mega's
    ``ליטר 1`` rows carry 80 to 686 "liters" of chips and spices; the loader gives them no unit
    price and this fallback must not invent one from the same field."""
    if quantity is None or quantity <= 0 or not unit:
        return None
    u = "".join(ch for ch in unit.strip().lower() if ch not in "\"'׳״. ")
    if u in _GRAM:
        base, dim = quantity, "100g"
    elif u in _KG:
        base, dim = quantity * 1000, "100g"
    elif u in _ML:
        base, dim = quantity, "100ml"
    elif u in _LITER:
        base, dim = quantity * 1000, "100ml"
    elif u in _UNIT:
        base, dim = quantity, "unit"
    else:
        return None
    if not sane_pack(base, dim):
        return None
    if dim == "unit":
        return price / base, "unit"
    return price * _HUNDRED / base, dim


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
    name: str | None = None
    is_weighed: bool = False
    item_code: str | None = None


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
       i.quantity, i.unit, i.raw_name, i.is_weighed, i.item_code
FROM stores AS s
JOIN items AS i ON i.chain_id = s.chain_id AND i.id = ANY(%(items)s)
LEFT JOIN latest AS sp ON sp.item_id = i.id AND sp.store_id = s.id
LEFT JOIN latest AS bp ON bp.item_id = i.id AND bp.store_id IS NULL
WHERE s.id = ANY(%(stores)s)
  AND (sp.item_id IS NOT NULL OR bp.item_id IS NOT NULL)
"""

GET_PERCENT_SQL = (
    "CASE WHEN p.raw->>'get_percent' ~ '^[0-9]+(\\.[0-9]+)?$'"
    " THEN (p.raw->>'get_percent')::numeric END"
)
"""``PromoTerms.get_percent`` from the promo row: the adapters write ``raw.get_percent`` for a
two-group "buy one, get one at P % off" promotion (docs/adapters.md)."""

_PROMOS_SQL = f"""
SELECT p.id, p.store_id, p.description, p.club_only, p.club_name, p.min_qty, p.reward_type,
       p.reward_value, {GET_PERCENT_SQL}, pi.item_id
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
    per_club: dict[tuple[int, int], dict[str, Option]] | None = None,
    notes: list[dict] | None = None,
) -> dict[tuple[int, int], tuple[Option, Option]]:
    """(store_id, item_id) -> (best option overall, best option without a club promo).

    ``base_units`` maps item_id to the base unit its unit price is expressed in (the canonical's);
    items whose unit cannot be converted are left out. Without it the item's own uom is kept.
    When ``per_club`` is given it receives, per (store_id, item_id), the best option of each club
    named by a club promo, when it beats the no-club option. Club promos without a club name are
    left out: they never apply (issue #19). ``notes`` receives one dict per item whose pack was
    read from the name against the fields, or whose readings disagreed (``UnitReading.note``).
    """
    if not store_ids or not item_ids:
        return {}
    params = {"items": item_ids, "stores": store_ids, "as_of": as_of, "chain": chain_id}
    priced = [PricedItem(*r) for r in conn.execute(_PRICES_SQL, params).fetchall()]
    promos: dict[int, list[PromoTerms]] = defaultdict(list)
    for r in conn.execute(_PROMOS_SQL, params).fetchall():
        promos[r[9]].append(PromoTerms(*r[:9]))

    out: dict[tuple[int, int], tuple[Option, Option]] = {}
    noted: set[int] = set()
    for p in priced:
        base = base_units.get(p.item_id) if base_units else None
        reading = read_unit_price(p, base)
        if reading is None:
            continue
        unit_price, uom = reading.unit_price, reading.uom
        if reading.note is not None and notes is not None and p.item_id not in noted:
            noted.add(p.item_id)
            notes.append(
                {"item_id": p.item_id, "name": p.name, "kind": reading.note[0],
                 "detail": reading.note[1], "price": str(p.price)}
            )  # fmt: skip
        plain = Option(
            item_id=p.item_id,
            shelf_price=p.price,
            effective_price=p.price,
            effective_unit_price=unit_price.quantize(_Q4, rounding=ROUND_HALF_UP),
            uom=uom,
            price_valid_from=p.valid_from,
            is_estimated=p.is_estimated,
            pack_units=reading.pack_units,
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
            if promo.club_only and promo.club_name and per_club is not None:
                clubs = per_club.setdefault((p.store_id, p.item_id), {})
                cur = clubs.get(promo.club_name)
                if cur is None or opt.key() < cur.key():
                    clubs[promo.club_name] = opt
        out[(p.store_id, p.item_id)] = (best, best_noclub)
        if per_club is not None and (p.store_id, p.item_id) in per_club:
            clubs = per_club[(p.store_id, p.item_id)]
            for name in [n for n, o in clubs.items() if not o.key() < best_noclub.key()]:
                del clubs[name]  # keep only clubs that beat what everybody pays
    return out


def unit_price_in(
    price: Decimal,
    unit_price: Decimal | None,
    uom: str | None,
    quantity: Decimal | None,
    unit: str | None,
    base_unit: str | None,
    name: str | None = None,
    is_weighed: bool = False,
    item_code: str | None = None,
) -> tuple[Decimal, str] | None:
    """The unit price of one price event in ``base_unit``, by the precompute's rules, or None."""
    p = PricedItem(
        0, 0, price, unit_price, uom, False, datetime.now(UTC), quantity, unit,
        name, is_weighed, item_code,
    )  # fmt: skip
    return _unit_price(p, base_unit)


# --- the pack of a shelf item (docs/optimizer.md, "Packs") ------------------------------------
#
# Three readings of "how much is in this item" compete, and the first two are the chain's:
#   published  the unit price the file states (``prices.unit_price`` / ``uom``)
#   fields     Quantity / UnitQty of the item (``derive_unit_price``)
#   name       the catalog's normalization of the name (``normalize``: ``12 יח'``, ``2*30``,
#              ``6*1.5 ל'``, ``32 גלילים``), which itself weighs the fields against the name
# Rami Levy, Yohananof and Tiv Taam write ``Quantity = 1, UnitQty = יחידות`` for a tray of 12
# eggs: the fields and the published unit price are the tray's price per "1 unit", and only the
# name has the count. A stated count above 1 therefore beats a 1. When two readings state different
# amounts the safer one is used (the larger unit price: a pack is never shown cheaper per unit than
# the shelf supports) and the disagreement is recorded, not hidden.

CONSISTENT_RATIO = Decimal("1.12")
"""Two readings of one amount agree when the larger is within 12 % of the smaller (published unit
prices are rounded to the agora; a chain rounds 187.5 g to 187). A planning choice, not measured."""
CONSISTENT_ABS = Decimal("0.011")
"""... or when they differ by at most one agora rounding step (0.005 on each side)."""
_STATED_COUNT = Decimal("1.5")
"""A count below this is a 1: what the chains write when they do not know the count."""


@dataclass(frozen=True)
class UnitReading:
    unit_price: Decimal
    uom: str
    pack_units: Decimal | None = None
    note: tuple[str, str] | None = None
    """(kind, detail) when the pack was read from the name against the fields, or two readings
    disagreed: kinds ``count_from_name``, ``count_conflict``, ``measure_conflict``."""


def _agree(a: Decimal, b: Decimal) -> bool:
    lo, hi = (a, b) if a <= b else (b, a)
    return hi - lo <= CONSISTENT_ABS or hi <= lo * CONSISTENT_RATIO


def _normalized(p: PricedItem) -> NormalizedItem | None:
    """The catalog's reading of the item, or None when the name and fields give no size."""
    if not p.name:
        return None
    n = normalize(
        {
            "raw_name": p.name,
            "quantity": p.quantity,
            "unit": p.unit,
            "is_weighed": p.is_weighed,
            "item_code": p.item_code,
        }
    )
    return n if n.base_unit is not None else None


def _plain(n: Decimal) -> Decimal:
    return n.quantize(Decimal(1)) if n == n.to_integral_value() else n.normalize()


def _read_count(p: PricedItem) -> UnitReading | None:
    """A per-unit canonical: ``price / units in the item`` when some reading states a count
    above 1, else None (the caller compares per pack, as before)."""
    norm = _normalized(p)
    from_name: Decimal | None = None
    if norm is not None and norm.total_quantity is not None and not norm.is_weighed:
        if norm.unit == "unit":
            from_name = norm.total_quantity
        elif norm.pack_count > 1:  # "6 גלילים 400 גרם": the pieces, not the grams
            from_name = Decimal(norm.pack_count)
        if from_name is not None and not sane_pack(from_name, "unit"):
            from_name = None
    field = derive_unit_price(p.price, p.quantity, p.unit)
    from_fields = p.quantity if field is not None and field[1] == "unit" else None
    from_published = None
    if p.uom == "unit" and p.unit_price is not None and p.unit_price > 0:
        implied = p.price / p.unit_price  # 14.20 at 1.18 per unit: 12.03 eggs, i.e. 12
        whole = implied.quantize(Decimal(1), rounding=ROUND_HALF_UP)
        if sane_pack(whole, "unit") and abs(implied - whole) <= whole * Decimal("0.06"):
            from_published = whole
    readings = (("name", from_name), ("fields", from_fields), ("published", from_published))
    stated = {k: v for k, v in readings if v is not None and v >= _STATED_COUNT}
    if not stated:
        return None
    count = min(stated.values())  # the smaller count is the larger unit price: the safer one
    note = None
    if not all(_agree(count, v) for v in stated.values()):
        detail = ", ".join(f"{k} {_plain(v):f}" for k, v in stated.items())
        note = ("count_conflict", f"{detail}; used {_plain(count):f}")
    elif list(stated) == ["name"]:
        said = " / ".join(f"{k} {_plain(v):f}" for k, v in readings[1:] if v is not None)
        note = ("count_from_name", f"name {_plain(count):f}; {said or 'the fields say nothing'}")
    count = _plain(count)
    return UnitReading(p.price / count, "unit", count, note)


def _read_measure(p: PricedItem, base_unit: str) -> UnitReading | None:
    """A per-100 g or per-100 ml canonical: the published unit price, the fields' and the name's
    reading; when they disagree the highest unit price wins (never cheaper than the shelf)."""
    readings: dict[str, Decimal] = {}
    if p.unit_price is not None and p.uom:
        published = to_base_unit(p.unit_price, p.uom, base_unit)
        if published is not None:
            readings["published"] = published
    derived = derive_unit_price(p.price, p.quantity, p.unit)
    if derived is not None:
        converted = to_base_unit(derived[0], derived[1], base_unit)
        if converted is not None:
            readings["fields"] = converted
    norm = _normalized(p)
    if (
        norm is not None
        and not norm.is_weighed
        and norm.base_unit == base_unit
        and norm.total_quantity
        and sane_pack(norm.total_quantity, base_unit)
    ):
        readings["name"] = p.price * _HUNDRED / norm.total_quantity
    if not readings:
        return None
    values = list(readings.values())
    if _agree(min(values), max(values)):
        return UnitReading(values[0], base_unit)  # published, else the fields, else the name
    chosen = max(values)
    detail = ", ".join(f"{k} {v:.4f}" for k, v in readings.items())
    return UnitReading(
        chosen, base_unit, None, ("measure_conflict", f"{detail}; used {chosen:.4f}")
    )


def read_unit_price(p: PricedItem, base_unit: str | None) -> UnitReading | None:
    """The unit price of ``p`` in ``base_unit`` (the canonical's), the units in the item for a
    per-unit canonical, and a note when the name or a disagreement decided it; None when the item
    cannot be priced in that unit."""
    got = None
    if base_unit == "unit":
        got = _read_count(p)
    elif base_unit in ("100g", "100ml"):
        got = _read_measure(p, base_unit)
    return got if got is not None else _legacy_reading(p, base_unit)


def _legacy_reading(p: PricedItem, base_unit: str | None) -> UnitReading | None:
    """The chain's published unit price, else the one derived from the item's own fields."""
    if p.unit_price is not None and p.uom:
        unit_price, uom = p.unit_price, p.uom
    else:
        derived = derive_unit_price(p.price, p.quantity, p.unit)
        if derived is None:
            if base_unit in (None, "unit"):
                return UnitReading(p.price, "unit")  # no size known: compared per pack
            return None
        unit_price, uom = derived
    if base_unit is None:
        return UnitReading(unit_price, uom)
    converted = to_base_unit(unit_price, uom, base_unit)
    if converted is None:
        return None
    return UnitReading(converted, base_unit)


def _unit_price(p: PricedItem, base_unit: str | None) -> tuple[Decimal, str] | None:
    got = read_unit_price(p, base_unit)
    return None if got is None else (got.unit_price, got.uom)


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
    pack_notes: list[dict] | None = None
    """Items whose pack was read from the name against the fields, or whose readings disagreed."""

    def metrics(self) -> dict:
        notes = self.pack_notes or []
        kinds: dict[str, int] = defaultdict(int)
        for n in notes:
            kinds[n["kind"]] += 1
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
            "pack_reads": dict(sorted(kinds.items())),
            "pack_samples": [n for n in notes if n["kind"] != "count_from_name"][:MAX_PACK_SAMPLES]
            + [n for n in notes if n["kind"] == "count_from_name"][:MAX_PACK_SAMPLES],
        }


def _chain_rows(
    conn: psycopg.Connection, chain_id: str, as_of: datetime, notes: list[dict] | None = None
) -> tuple[list[tuple], int, int]:
    mappings = conn.execute(
        "SELECT ic.item_id, ic.canonical_id, ic.flex_level, cp.base_unit"
        " FROM item_canonical AS ic"
        " JOIN items AS i ON i.id = ic.item_id"
        " JOIN canonical_products AS cp ON cp.id = ic.canonical_id"
        " WHERE i.chain_id = %s AND NOT ic.needs_review AND NOT ic.human_rejected",
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
    club_opts: dict[tuple[str, int, int], dict[str, Option]] = {}
    for base, items in by_base.items():
        per_club: dict[tuple[int, int], dict[str, Option]] = {}
        got = item_options(
            conn, chain_id, store_ids, sorted(items), as_of, {i: base for i in items}, per_club,
            notes,
        )  # fmt: skip
        for (sid, iid), opts in got.items():
            options[(base, sid, iid)] = opts
        for (sid, iid), clubs in per_club.items():
            club_opts[(base, sid, iid)] = clubs
    by_item: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for item_id, cid, lvl, base in mappings:
        by_item[item_id].append((cid, lvl, base))

    best: dict[tuple[int, int, str], tuple[Option, Option]] = {}
    best_club: dict[tuple[int, int, str], dict[str, Option]] = defaultdict(dict)
    for (base, sid, iid), (opt, noclub) in options.items():
        clubs = club_opts.get((base, sid, iid), {})
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
                for name, copt in clubs.items():
                    have = best_club[key].get(name)
                    if have is None or copt.key() < have.key():
                        best_club[key][name] = copt
    rows = []
    for (cid, sid, level), (opt, noclub) in best.items():
        noclub_js = None
        if opt.club_required:
            noclub_js = noclub.as_json()
            alts = {  # every club whose deal beats the no-club option, the winner's included
                name: o.as_json()
                for name, o in sorted(best_club.get((cid, sid, level), {}).items())
                if o.key() < noclub.key()
            }
            if alts:
                noclub_js["clubs"] = alts
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
                json.dumps(noclub_js) if noclub_js is not None else None,
                opt.pack_units,
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
        result = PrecomputeResult(
            run_id=run_id, as_of=as_of, rows_by_flex=dict.fromkeys(LEVELS, 0), pack_notes=[]
        )
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _ep (LIKE effective_prices INCLUDING DEFAULTS)"
            " ON COMMIT DROP"
        )
        for chain_id in chain_ids:
            rows, n_stores, n_items = _chain_rows(conn, chain_id, as_of, result.pack_notes)
            result.chains += 1
            result.stores += n_stores
            result.items_priced += n_items
            conn.execute("TRUNCATE _ep")
            with conn.cursor().copy(
                "COPY _ep (canonical_id, store_id, item_id, flex_level, shelf_price,"
                " effective_unit_price, uom, promo_id, club_required, club_name,"
                " price_valid_from, effective_price, promo_min_qty, is_estimated, noclub,"
                " pack_units)"
                " FROM STDIN"
            ) as copy:
                for r in rows:
                    copy.write_row(r)
            conn.execute(
                "INSERT INTO effective_prices (canonical_id, store_id, item_id, flex_level,"
                "   shelf_price, effective_unit_price, uom, promo_id, club_required, club_name,"
                "   price_valid_from, computed_at, effective_price, promo_min_qty, is_estimated,"
                "   noclub, pack_units)"
                " SELECT canonical_id, store_id, item_id, flex_level, shelf_price,"
                "   effective_unit_price, uom, promo_id, club_required, club_name,"
                "   price_valid_from, %s, effective_price, promo_min_qty, is_estimated, noclub,"
                "   pack_units"
                " FROM _ep"
                " ON CONFLICT (canonical_id, store_id, flex_level) DO UPDATE SET"
                "   item_id = EXCLUDED.item_id, shelf_price = EXCLUDED.shelf_price,"
                "   effective_unit_price = EXCLUDED.effective_unit_price, uom = EXCLUDED.uom,"
                "   promo_id = EXCLUDED.promo_id, club_required = EXCLUDED.club_required,"
                "   club_name = EXCLUDED.club_name, price_valid_from = EXCLUDED.price_valid_from,"
                "   computed_at = EXCLUDED.computed_at, effective_price = EXCLUDED.effective_price,"
                "   promo_min_qty = EXCLUDED.promo_min_qty, is_estimated = EXCLUDED.is_estimated,"
                "   noclub = EXCLUDED.noclub, pack_units = EXCLUDED.pack_units",
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
