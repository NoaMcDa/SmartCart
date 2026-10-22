"""Unit prices: computed from price and pack size, the published value only as a cross-check.

Chains publish ``UnitOfMeasurePrice`` next to ``ItemPrice``, ``Quantity``, ``UnitQty`` (the unit
of ``Quantity``) and ``UnitOfMeasure`` (the label of the published unit price). Measured on the
committed real files of seven chains (docs/adapters.md, "Unit prices in real files"), the
published value is *not* always what its label says: Rami Levy labels it ``100 גרם`` and
``100 מיליליטר`` and publishes the price of one gram and one millilitre, which read as per 100 g
and per 100 ml is 100 times too small. A per-chain hand fix would not catch the next chain that
does the same, so the internal unit price is derived like this (``resolve_unit_price``):

1. **Weighed items** are per kg and estimated. The shelf price of a weighed item is the price of
   a kilogram (every weighed row of the real files publishes a unit price equal to it), so it is
   the value; the published one is only compared.
2. **Computed**: ``price / pack size`` per 100 g, per 100 ml or per unit, when the pack size is
   present and sane (``quantity`` in the unit of ``UnitQty``, or, when ``UnitQty`` is unknown, in
   the natural unit of the label: grams for ``100 גרם``, kilograms for ``ק"ג``, liters for
   ``ליטר``; positive, and at most ``MAX_BASE_AMOUNT`` of the base unit, so 452 "liters" of
   cereal are refused).
3. **Published**, only when no sane pack size exists: the label's reading, multiplied by the
   chain's measured scale (``PUBLISHED_SCALE``) and refused when the pack size it implies is
   not sane.

The published value is cross-checked against the computed one (``check_published``): the
classes ``agree``, ``off_x100_low`` (published 100 times smaller than its label implies),
``off_x100_high``, ``off_x10_*``, ``off_x1000_*`` and ``other``. A disagreement is a data-quality
signal, counted per class by the loader; it never drops a price or quarantines a file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_ZERO = Decimal(0)
_HUNDRED = Decimal(100)
_Q4 = Decimal("0.0001")

MAX_BASE_AMOUNT: dict[str, Decimal] = {
    "mass": Decimal(50_000),  # grams: 50 kg
    "volume": Decimal(50_000),  # milliliters: 50 L
    "unit": Decimal(10_000),
}
"""The largest pack size taken as real, in grams, milliliters and units. Measured: the largest
real pack in the files is 8 kg and 7.92 L; the insane ones are 100 to 452 "liters" of spices and
cereal (Mega) and a quantity in kilograms where a count was meant."""

_UOM = {"mass": "100g", "volume": "100ml", "unit": "unit"}
_PER = {"mass": _HUNDRED, "volume": _HUNDRED, "unit": Decimal(1)}

# normalized spelling -> (dimension, base amount of one named unit: grams, milliliters or units)
_NAMES: dict[str, tuple[str, Decimal]] = {}
for _names, _dim, _size in (
    (("g", "gr", "gram", "grams", "גרם", "גר", "ג"), "mass", Decimal(1)),
    (("kg", "קג", "קילו", "קילוגרם"), "mass", Decimal(1000)),
    (("ml", "מל", "מיליליטר"), "volume", Decimal(1)),
    (("l", "lt", "ltr", "liter", "litre", "ליטר", "ל"), "volume", Decimal(1000)),
    (("unit", "units", "יחידה", "יחידות", "יח"), "unit", Decimal(1)),
):
    for _n in _names:
        _NAMES[_n] = (_dim, _size)

_QUOTES = re.compile(r"[\"'`׳״“”’]")
_SPACE = re.compile(r"\s+")
_LABEL = re.compile(r"^(?P<a>\d+(?:\.\d+)?)?(?P<name>[^\d.]+?)(?P<b>\d+(?:\.\d+)?)?$")


@dataclass(frozen=True)
class Label:
    """A parsed unit label, e.g. ``100 גרם`` or ``ליטר 1`` or ``ק"ג``."""

    dim: str
    """``mass`` (grams), ``volume`` (milliliters) or ``unit``."""
    size: Decimal
    """Base amount (g, ml, unit) the label's price is *stated* for: 100 for ``100 גרם``, 1000
    for ``ק"ג`` and ``ליטר 1``."""
    named: Decimal
    """Base amount of the named unit alone: 1 for ``100 גרם``, 1000 for ``ק"ג``."""


def parse_label(raw: str | None) -> Label | None:
    """The label of a unit price or the unit of a quantity, or None when it is not a known
    mass, volume or count unit (``לא ידוע``, ``מטרים``, ``דונם``)."""
    if not raw:
        return None
    s = _SPACE.sub("", _QUOTES.sub("", raw.strip().lower()))
    candidates = [s]
    if s.startswith("ל-"):
        candidates.append(s[2:])
    elif s.startswith("ל"):
        candidates.append(s[1:])
    for cand in candidates:
        cand = cand.lstrip("-")
        m = _LABEL.match(cand)
        if m is None or (m["a"] and m["b"]):
            continue
        hit = _NAMES.get(m["name"])
        if hit is None:
            continue
        amount = Decimal(m["a"] or m["b"] or 1)
        if amount <= 0:
            continue
        dim, named = hit
        return Label(dim, amount * named, named)
    return None


# --- the chains' measured behaviour ---------------------------------------------------------------

PUBLISHED_SCALE: dict[str, dict[tuple[str, Decimal], Decimal]] = {
    # Rami Levy labels the unit price of weight and volume "100 גרם" / "100 מיליליטר" and
    # publishes the price of one gram / one milliliter, so the label's amount is 100 times too
    # big. Measured on the committed real PriceFull files of 2026-10-21 and 2026-10-08: every
    # such row with a sane pack size agrees with price / quantity only under this reading (its
    # "ליטר", "קילוגרם" and "יחידות" labels agree as labelled).
    "7290058140886": {
        ("mass", Decimal(100)): Decimal(100),
        ("volume", Decimal(100)): Decimal(100),
    },
    # Osher Ad: the same, for volume only ("100 מ"ל" is per milliliter; "100 גרם" is per 100 g).
    "7290103152017": {("volume", Decimal(100)): Decimal(100)},
    # Mega: the opposite for one label. "מיליליטר" (per milliliter) carries the price per
    # 100 ml, 100 times too big as labelled.
    "7290055700007": {("volume", Decimal(1)): Decimal("0.01")},
}
"""chain id -> (label dimension, label size) -> factor that the label's reading of the published
value must be multiplied by. Measured per chain on 2026-10-21 and 2026-10-08 (docs/adapters.md,
"Unit prices in real files"); ``test_unit_price_real.py`` re-derives every entry from the files.
A chain or label not listed is read as labelled."""


def published_scale(chain_id: str | None, label: Label) -> Decimal:
    return PUBLISHED_SCALE.get(chain_id or "", {}).get((label.dim, label.size), Decimal(1))


# --- computing ------------------------------------------------------------------------------------


def pack_amount(
    quantity: Decimal | None, quantity_unit: str | None, label: Label | None
) -> tuple[str, Decimal] | None:
    """``(dimension, base amount)`` of the pack in grams, milliliters or units, or None when the
    pack size is missing, in a unit that contradicts the label, or not sane."""
    if quantity is None or quantity <= 0:
        return None
    unit = parse_label(quantity_unit)
    if unit is not None:
        if label is not None and unit.dim != label.dim:
            return None
        dim, base = unit.dim, quantity * unit.named
    elif label is not None:
        # UnitQty unknown: the quantity is in the label's own named unit (measured: grams for
        # "100 גרם", kilograms for "ק"ג", liters for "ליטר", milliliters for "100 מ"ל").
        dim, base = label.dim, quantity * label.named
    else:
        return None
    if base > MAX_BASE_AMOUNT[dim] or (dim != "unit" and base < 1):
        return None
    return dim, base


def computed_unit_price(price: Decimal, dim: str, base: Decimal) -> Decimal:
    """``price`` of a pack of ``base`` grams, milliliters or units, per 100 g, 100 ml or unit."""
    return (price / base * _PER[dim]).quantize(_Q4, rounding=ROUND_HALF_UP)


def _plausible(price: Decimal, per: Decimal, dim: str) -> bool:
    """A unit price (per 100 g, 100 ml or unit) that implies a sane pack size for ``price``."""
    if per <= 0:
        return False
    implied = price / per * _PER[dim]
    if dim == "unit":
        return implied > 0
    return Decimal(1) <= implied <= MAX_BASE_AMOUNT[dim]


# --- cross-check ------------------------------------------------------------------------------------

_POWERS = (
    (0, "agree"),
    (2, "off_x100_high"),
    (-2, "off_x100_low"),
    (1, "off_x10_high"),
    (-1, "off_x10_low"),
    (3, "off_x1000_high"),
    (-3, "off_x1000_low"),
)


def check_published(published: Decimal, expected: Decimal) -> str:
    """How ``published`` relates to ``expected``, both in the published unit: ``agree`` within
    the rounding of a two-decimal price (half a cent, plus 2 %), or ``off_x100_low`` when it is
    100 times smaller, and so on; ``other`` when it is no power of ten away."""
    if expected <= 0:
        return "other"
    for power, name in _POWERS:
        target = expected * (Decimal(10) ** power)
        if abs(published - target) <= Decimal("0.0051") + target * Decimal("0.02"):
            return name
    return "other"


# --- the entry point --------------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitPrice:
    value: Decimal | None
    uom: str | None
    is_estimated: bool
    source: str
    """``weighed``, ``computed``, ``published``, ``published_scaled`` or ``none``."""
    check: str | None = None
    """``check_published`` of the published value against the computed one under the chain's
    measured reading; None when either is missing."""
    check_as_labelled: str | None = None
    """The same, reading the published value as its label says (no chain scale)."""


def resolve_unit_price(
    price: Decimal,
    published: Decimal | None,
    label_raw: str | None,
    is_weighed: bool,
    quantity: Decimal | None = None,
    quantity_unit: str | None = None,
    chain_id: str | None = None,
) -> UnitPrice:
    """The internal ``(unit price, uom, is_estimated)`` of one price record; see the module
    doc. Never raises and never drops the price: no usable unit price is ``value=None``."""
    label = parse_label(label_raw)
    if is_weighed and (label is None or label.dim != "volume"):
        return _weighed(price, published, label)
    pack = pack_amount(quantity, quantity_unit, label)
    if pack is not None:
        value = computed_unit_price(price, pack[0], pack[1])
        as_labelled = ruled = None
        if published is not None and label is not None:
            expected = price / pack[1] * label.size  # in the published unit, as labelled
            as_labelled = check_published(published, expected)
            scale = published_scale(chain_id, label)
            ruled = as_labelled if scale == 1 else check_published(published, expected / scale)
        return UnitPrice(value, _UOM[pack[0]], is_weighed, "computed", ruled, as_labelled)
    if published is None or label is None or (label.dim == "unit" and label.size != 1):
        # (a count label other than "1": Rami Levy's "2   יחידות" is published per unit)
        return UnitPrice(None, None, is_weighed, "none")
    scale = published_scale(chain_id, label)
    value = (published * scale / label.size * _PER[label.dim]).quantize(_Q4, rounding=ROUND_HALF_UP)
    if not _plausible(price, value, label.dim):
        return UnitPrice(None, None, is_weighed, "none")
    return UnitPrice(
        value, _UOM[label.dim], is_weighed, "published" if scale == 1 else "published_scaled"
    )


def _weighed(price: Decimal, published: Decimal | None, label: Label | None) -> UnitPrice:
    """A weighed item is per kg: the shelf price, which chains publish per kg. Compared with the
    published unit price when that is per kg (or per 100 g)."""
    check = None
    if published is not None and label is not None and label.dim == "mass":
        per_kg = published * Decimal(1000) / label.size
        check = check_published(per_kg, price)
    return UnitPrice(price, "kg", True, "weighed", check, check)
