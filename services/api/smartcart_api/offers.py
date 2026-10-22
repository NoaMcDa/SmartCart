"""The price of a line for a quantity, and the small set of offers kept per (canonical, store, level).

The nightly precompute used to keep one offer per (canonical, store, flexibility level): the one with
the best effective unit price. A unit price does not know the quantity asked: at ``close`` a tray of
30 eggs at 1.00 an egg beats a 12-pack at 1.18, so the line for 12 eggs was the whole tray (29.90)
although the 12-pack (14.20) is the cheapest way to buy 12. The same holds for promos: a "2 for 14"
that only pays at two packs lost to a deeper promo that needs four.

``effective_prices`` still holds that offer (rank 0, ``kind`` ``unit``; ``/search``, the history and the
alerts read nothing else). ``effective_offers`` holds up to ``MAX_EXTRA_OFFERS`` more rows per key,
chosen here (``choose_extras``) so that ``basket.price_baskets`` can take, for the quantity asked,
the cheapest line among them (docs/optimizer.md, "Offers for the quantity asked").

This module is pure (no database): the pricing rules that ``basket`` and the precompute share, and the
selection of the extra offers.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Any, NamedTuple, Protocol

_C2 = Decimal("0.01")
ZERO = Decimal(0)
_ONE = Decimal(1)


def money(d: Decimal) -> Decimal:
    return d.quantize(_C2, rounding=ROUND_HALF_UP)


class Pricing(Protocol):
    """What a line total needs of an offer (``precompute.Option`` and ``basket._Choice`` both are)."""

    shelf_price: Decimal
    effective_price: Decimal
    effective_unit_price: Decimal
    promo_id: int | None
    promo_min_qty: Decimal | None
    pack_units: Decimal | None


class Priced(Pricing, Protocol):
    """An offer as the selection sees it."""

    item_id: int
    club_required: bool
    club_name: str | None
    amount: Decimal | None


# --- the line for a quantity ------------------------------------------------------------------


def units_per_pack(base_unit: str, soft_attrs: dict | None) -> Decimal | None:
    """The typical count of a canonical counted in units (``soft_attrs.pack_size`` in units); 1
    when it states none. None for a weight or a volume, which count shelf items."""
    if base_unit != "unit":
        return None
    soft = soft_attrs or {}
    size = soft.get("pack_size")
    if size is None or soft.get("unit") not in (None, "unit"):
        return Decimal(1)
    try:
        value = Decimal(str(size))
    except ArithmeticError:
        return Decimal(1)
    return value if value > 0 else Decimal(1)


def shelf_packs(c: Pricing, quantity: Decimal, per: Decimal | None) -> Decimal:
    """Shelf items to buy for ``quantity`` packs of the requested canonical.

    ``per`` is the canonical's typical count (12 for ``eggs-l``), None when the canonical is not
    counted in units. When both it and the item's own count (``c.pack_units``) are known the line
    buys whole shelf items covering ``quantity x per`` units; otherwise the quantity already counts
    shelf items."""
    if c.pack_units is None or per is None:
        return quantity
    return (quantity * per / c.pack_units).to_integral_value(rounding=ROUND_CEILING)


def line_total(c: Pricing, quantity: Decimal, by_weight: bool) -> tuple[Decimal, bool]:
    """(line total, promo applied) for ``quantity`` shelf items (kg when weighed) of offer ``c``."""
    if by_weight:
        return money(quantity * c.effective_unit_price), c.promo_id is not None
    need = c.promo_min_qty or _ONE
    if c.promo_id is None:
        return money(quantity * c.shelf_price), False
    if need <= 1:
        return money(quantity * c.effective_price), True
    bundles = (quantity / need).to_integral_value(rounding=ROUND_FLOOR)
    rest = quantity - bundles * need
    total = bundles * money(c.effective_price * need) + rest * c.shelf_price
    return money(total), bundles > 0


# --- the extra offers ---------------------------------------------------------------------------

MAX_EXTRA_OFFERS = 4
"""Rows kept in ``effective_offers`` per (canonical, store, level), next to the ``effective_prices``
row (rank 0): five offers in all. The offers worth keeping are the ones that are cheapest for some
quantity or some audience, and a store rarely has more: a chain has one to three items per
canonical (brands, sizes), each with at most a couple of promos (a plain price, a per-unit or
percent deal, an "N for X" bundle, a club deal), and the best unit price already is one of them. The
greedy choice adds an offer only if it lowers the price somewhere, so most keys have no extra row
(measured on the scaled synthetic world, docs/optimizer.md)."""

MAX_PROBE_SHELF = 6
"""Lines of up to this many shelf items are priced exactly: for every quantity that buys at most six
shelf items of an offer (or at most six requested packs) the cheapest line among the stored offers
is the cheapest of all the offers open to the user. For larger quantities the stored offers are
still all valid and the best unit price, always kept, wins in the long run."""

SUB_PENALTY = Decimal("0.0001")
"""Added to a substitute's cost while choosing: an exact or any-brand item that costs the same as a
close substitute is kept in preference (below one agora, so it never outweighs a real difference)."""

_UNAVAILABLE = Decimal(10) ** 9


def probe_quantities(offers: Iterable[Priced], per: Decimal | None) -> list[Decimal]:
    """The quantities (in requested packs) at which the cheapest offer can change.

    An offer that holds ``n`` units costs the same for every quantity in ``((k-1) n / per,
    k n / per]`` (``k`` whole shelf items), and a promo bundle changes the price only at whole
    shelf items. Between two such points every offer's price is constant, so the cheapest offer is
    the same: it is enough to price the integers up to ``MAX_PROBE_SHELF`` and the point where
    each offer's ``k``-th shelf item ends, ``k`` up to ``MAX_PROBE_SHELF`` (30 eggs from a tray of
    30 are 2.5 packs of 12)."""
    qs = {Decimal(i) for i in range(1, MAX_PROBE_SHELF + 1)}
    if per is not None:
        for step in {o.pack_units / per for o in offers if o.pack_units}:
            for k in range(1, MAX_PROBE_SHELF + 1):
                # rounded down, so that quantity x per / n stays at k and does not tip over to k + 1
                qs.add((k * step).quantize(Decimal("0.000001"), rounding=ROUND_DOWN))
    qs.discard(Decimal(0))
    return sorted(qs)


def kind_of(o: Priced) -> str:
    """Why an offer is kept: ``club`` (needs a club), ``bundle`` (a promo over several packs) or
    ``pack`` (a plain item or a per-pack deal that is the cheapest way to buy a few)."""
    if o.club_required:
        return "club"
    if o.promo_id is not None and o.promo_min_qty is not None and o.promo_min_qty > 1:
        return "bundle"
    return "pack"


SAME_SIZE = Decimal("1.05")
"""Two per-100 g or per-100 ml items are the same size when the larger is within 5 % of the smaller
(unit prices are rounded to four decimals and the chains round weights)."""


def comparable(o: Priced, ref: Priced) -> bool:
    """Whether the line for a quantity can be compared between ``o`` and ``ref``: counted items
    (both state their units) are compared in whole packs of units, an item that states none only
    with others that state none, and a weight or a volume only with an item of the same size. A
    unit price already decides between sizes; a cheaper small bottle is not a cheaper line."""
    if (o.pack_units is None) != (ref.pack_units is None):
        return False
    if o.pack_units is not None:
        return True
    if o.amount is None or ref.amount is None:
        return o.amount is None and ref.amount is None
    lo, hi = sorted((o.amount, ref.amount))
    return hi <= lo * SAME_SIZE


def identity(o: Priced) -> tuple[int, int | None, str | None]:
    return o.item_id, o.promo_id, o.club_name if o.club_required else None


def _order(o: Priced) -> tuple:
    return (o.effective_unit_price, o.effective_price, o.item_id, o.promo_id or 0)


class _Offer(NamedTuple):
    """The fields of an offer that decide a line total (``Priced`` for ``line_total``)."""

    shelf_price: Decimal
    effective_price: Decimal
    effective_unit_price: Decimal
    promo_id: int | None
    promo_min_qty: Decimal | None
    pack_units: Decimal | None


@lru_cache(maxsize=8192)
def _cost_row(
    shelf: Decimal,
    eff: Decimal,
    promo_id: int | None,
    need: Decimal | None,
    pack_units: Decimal | None,
    per: Decimal | None,
    qs: tuple[Decimal, ...],
    sub: bool,
) -> tuple[Decimal, ...]:
    """What each quantity of ``qs`` costs with the offer (a substitute ``SUB_PENALTY`` more). The
    same offer is priced for every level and every store of a chain with the same prices."""
    o = _Offer(shelf, eff, eff, promo_id, need, pack_units)
    by_packs: dict[Decimal, Decimal] = {}  # many quantities buy the same number of shelf items
    row = []
    for q in qs:
        n = shelf_packs(o, q, per)
        c = by_packs.get(n)
        if c is None:
            c = by_packs[n] = line_total(o, n, False)[0] + (SUB_PENALTY if sub else ZERO)
        row.append(c)
    return tuple(row)


def choose_extras(
    offers: Sequence[tuple[Any, bool]],
    stored: Sequence[Priced],
    per: Decimal | None,
    cap: int = MAX_EXTRA_OFFERS,
) -> list[Any]:
    """The offers to keep besides ``stored`` (the rank 0 row and the options its ``noclub`` JSON
    carries), best first.

    ``offers`` is every way to buy the canonical at the store, as (offer, is a close substitute).
    The audiences are everybody (no club deal), each club rule on its own (everybody plus that
    club's deals) and, with several rules, a member of all. For each audience and each probe
    quantity the cheapest line (a substitute costs ``SUB_PENALTY`` more) is the target; the
    greedy loop adds the offer that lowers the total excess over the targets the most, until the
    excess is 0, nothing helps, or ``cap`` offers are kept. Ties go to the lower unit price.

    Only offers ``comparable`` with the rank 0 offer take part: a line for a quantity compares
    shelf items of the same size."""
    stored = list(stored)
    ref = stored[0]  # the rank 0 offer: the size the line is for
    usable = [
        (o, sub) for o, sub in offers if (not o.club_required or o.club_name) and comparable(o, ref)
    ]
    if len(usable) < 2:
        return []
    stored_ids = {identity(o) for o in stored}
    names = sorted({o.club_name for o, _ in usable if o.club_required})
    audiences: list[frozenset[str]] = [frozenset(), *(frozenset([n]) for n in names)]
    if len(names) > 1:
        audiences.append(frozenset(names))
    qs = probe_quantities([o for o, _ in usable], per)
    qs_key = tuple(qs)
    cost = [
        _cost_row(
            o.shelf_price, o.effective_price, o.promo_id, o.promo_min_qty, o.pack_units, per,
            qs_key, sub,
        )
        for o, sub in usable
    ]  # fmt: skip
    open_to = [
        [i for i, (o, _) in enumerate(usable) if not o.club_required or o.club_name in aud]
        for aud in audiences
    ]
    target = [[min(cost[i][j] for i in idx) for j in range(len(qs))] for idx in open_to]
    have = {i for i, (o, _) in enumerate(usable) if identity(o) in stored_ids}

    def excess(kept: set[int]) -> Decimal:
        total = ZERO
        for a, idx in enumerate(open_to):
            mine = [i for i in idx if i in kept]
            for j in range(len(qs)):
                got = min((cost[i][j] for i in mine), default=_UNAVAILABLE)
                total += got - target[a][j]
        return total

    order = sorted(range(len(usable)), key=lambda i: _order(usable[i][0]))
    now = excess(have)
    out: list[Any] = []
    while now > 0 and len(out) < cap:
        best_i, best_x = None, now
        for i in order:
            if i in have:
                continue
            x = excess(have | {i})
            if x < best_x:
                best_i, best_x = i, x
        if best_i is None:
            break
        have.add(best_i)
        out.append(usable[best_i][0])
        now = best_x
    return out
