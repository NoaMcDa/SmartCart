"""Rule normalization of chain items, matching step A (issue #20).

``normalize(item)`` takes an ``items`` row (an ``ItemRecord``, a psycopg dict row, or anything
with ``raw_name``, ``quantity``, ``unit``, ``is_weighed`` and ``item_code``) and returns a
``NormalizedItem``:

* ``clean_name``: quotes unified, abbreviations expanded from the ``ABBREVIATIONS`` table
  (ש.ז. -> שמן זית, מהד' -> מהדורה, ק"ג -> קילוגרם, ...), whitespace collapsed.
* ``quantity`` / ``unit``: the size of one piece, in ``g``, ``ml`` or ``unit``.
* ``pack_count``: pieces in the pack (``6*1.5 ל'`` -> 6, ``מארז 8`` -> 8).
* ``total_quantity``: ``quantity * pack_count``; unit prices are computed on it.
* ``base_unit``: ``100g``, ``100ml``, ``unit``, or ``kg`` for weighed goods (CLAUDE.md conventions).
* ``is_weighed``: sold by weight; the shelf price is per kg and the unit price is "estimated".

Where the size comes from: the chain's quantity fields first; the name when the fields are empty
or uninformative (``1 יחידה``) or disagree with the name. ``normalize_with_issues`` also returns
what was ambiguous or unparseable, so the caller can report it instead of trusting a guess. When
nothing can be parsed the item has no quantity and no base unit; it is never given a made-up size.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from smartcart_catalog.models import BaseUnit, NormalizedItem

Unit = Literal["g", "ml", "unit"]

_HE = "א-ת"
_NOT_WORD = rf"(?![{_HE}A-Za-z])"
_NOT_WORD_BEFORE = rf"(?<![{_HE}A-Za-z])"

# --- abbreviations ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Abbreviation:
    pattern: str
    """Regex over the quote-normalized name (geresh is ', gershayim is ")."""
    expansion: str
    note: str = ""


# Table-driven and extendable: add a row, add a test in test_normalize.py. Order matters: longer
# and more specific forms first. Patterns run on a name whose quote variants (׳ ״ ` ’ ” “) were
# unified to ' and ". A leading ב/ו/ה/ל/מ prefix letter is kept (בש.ז. -> בשמן זית).
_P = rf"{_NOT_WORD_BEFORE}([בוהלמ]?)"
ABBREVIATIONS: tuple[Abbreviation, ...] = (
    Abbreviation(_P + r'ש(?:\.|")ז\.?' + _NOT_WORD, r"\1שמן זית",
                 "ש.ז. = שמן זית (olive oil); general knowledge, reviewer to confirm"),
    Abbreviation(_P + r"מהד'", r"\1מהדורה", "מהד' מוגבלת = limited edition"),
    Abbreviation(_P + r'תפו"א' + _NOT_WORD, r"\1תפוחי אדמה"),
    Abbreviation(_P + r'ק"ג' + _NOT_WORD, r"\1קילוגרם"),
    Abbreviation(_P + r"קג'" + _NOT_WORD, r"\1קילוגרם"),
    Abbreviation(_P + r"קג" + rf"(?![{_HE}A-Za-z'])", r"\1קילוגרם"),
    Abbreviation(_P + r'מ"ל' + _NOT_WORD, r"\1מיליליטר"),
    Abbreviation(_P + r"גר'" + _NOT_WORD, r"\1גרם"),
    Abbreviation(_P + r"ליט'" + _NOT_WORD, r"\1ליטר"),
    Abbreviation(_P + r"יחי?'" + _NOT_WORD, r"\1יחידות"),
    # bare one-letter units: only right after a number, so ג'/ל' elsewhere is left alone
    Abbreviation(r"(?<=\d)(\s*)ג'" + _NOT_WORD, r"\1גרם"),
    Abbreviation(r"(?<=\d)(\s*)ל'" + _NOT_WORD, r"\1ליטר"),
)
_ABBR = tuple((re.compile(a.pattern), a.expansion) for a in ABBREVIATIONS)

_QUOTES = str.maketrans({"׳": "'", "`": "'", "’": "'", "‘": "'", "״": '"', "”": '"', "“": '"'})
_SPACE = re.compile(r"\s+")


def clean_name(raw: str) -> str:
    """Unify quotes, expand abbreviations, collapse whitespace."""
    s = raw.translate(_QUOTES)
    s = s.replace("‏", "").replace("‎", "")  # RTL/LTR marks from some chain files
    for pattern, expansion in _ABBR:
        s = pattern.sub(expansion, s)
    return _SPACE.sub(" ", s).strip()


# --- units ---------------------------------------------------------------------------------------

# spelling -> (unit, factor to g / ml / unit)
_UNIT_WORDS: dict[str, tuple[Unit, Decimal]] = {}
for _words, _unit, _factor in (
    (("קילוגרם", "קילוגרמים", "קילו", "kg"), "g", Decimal(1000)),
    (("גרם", "גרמים", "גר", "ג", "g", "gr", "gram"), "g", Decimal(1)),
    (("ליטר", "ליטרים", "ל", "l", "lt", "ltr", "liter"), "ml", Decimal(1000)),
    (("מיליליטר", "מיליליטרים", "מל", "ml"), "ml", Decimal(1)),
    (("יחידות", "יחידה", "יח", "unit", "units"), "unit", Decimal(1)),
):
    for _w in _words:
        _UNIT_WORDS[_w] = (_unit, _factor)

# count nouns that also mean "N pieces" after a number (32 גלילים, 72 מגבונים)
_COUNT_NOUNS = ("יחידות", "יחידה", "יח", "גלילים", "שקיות", "ביצים", "טבליות", "קפסולות",
                "מגבונים", "שקיקים", "פריטים", "כוסות", "צלחות", "ממחטות", "פיתות", "לחמניות")

_MEASURE_ALT = "|".join(
    sorted((re.escape(w) for w, (u, _) in _UNIT_WORDS.items() if u != "unit"), key=len,
           reverse=True)
)
_COUNT_ALT = "|".join(sorted((re.escape(w) for w in _COUNT_NOUNS), key=len, reverse=True))
_NUM = r"(\d+(?:[.,]\d+)?)"
_X = r"\s*[*xX×]\s*"

# 6*1.5 ליטר / 4X250 מיליליטר (count first) and 1.5 ליטר*6 (size first)
_MULTI_COUNT_FIRST = re.compile(rf"{_NOT_WORD_BEFORE}{_NUM}{_X}{_NUM}\s*({_MEASURE_ALT}){_NOT_WORD}")
_MULTI_SIZE_FIRST = re.compile(rf"{_NUM}\s*({_MEASURE_ALT}){_X}(\d+){_NOT_WORD}")
_MEASURE = re.compile(rf"{_NOT_WORD_BEFORE}{_NUM}\s*-?\s*({_MEASURE_ALT}){_NOT_WORD}")
_COUNT = re.compile(rf"{_NOT_WORD_BEFORE}(\d+)\s*({_COUNT_ALT}){_NOT_WORD}")
# "מארז 8" is a count; "מארז 500 גרם" is a size, so a number followed by a unit is not a count
_PACK_WORD = re.compile(
    r"(?:מארז|מארזי|אריזת|חבילת|מגש)\s*(?:של\s*)?(\d+)"
    + rf"(?![\d.,]|\s*(?:{_MEASURE_ALT}){_NOT_WORD}|{_X})"
    + _NOT_WORD
)
_PACK_NAMED = {"זוג": 2, "שלישייה": 3, "שלישיית": 3, "רביעייה": 4, "רביעיית": 4,
               "שישייה": 6, "שישיית": 6}
_PACK_NAMED_RE = re.compile(
    _NOT_WORD_BEFORE + "(?:מארז\\s*)?(" + "|".join(_PACK_NAMED) + ")" + _NOT_WORD
)
_WEIGHED_WORDS = re.compile(r"במשקל|לפי משקל|לקילוגרם|לקילו" + _NOT_WORD + r"|ל-1 קילוגרם")
_PLU = re.compile(r"^\d{3,5}$")


def _dec(text: str) -> Decimal | None:
    text = text.strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+", text):
        text = text.replace(",", "")
    text = text.replace(",", ".")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value > 0 else None


def _unit_word(word: str) -> tuple[Unit, Decimal] | None:
    w = word.translate(_QUOTES).replace('"', "").replace("'", "").strip().lower()
    w = _SPACE.sub("", w)
    if w in _UNIT_WORDS:
        return _UNIT_WORDS[w]
    if w.startswith("ל") and w[1:] in _UNIT_WORDS:  # "לק"ג" = per kg
        return _UNIT_WORDS[w[1:]]
    return None


@dataclass(frozen=True)
class Size:
    quantity: Decimal  # one piece, in g, ml or units
    unit: Unit
    pack_count: int = 1

    @property
    def total(self) -> Decimal:
        return self.quantity * self.pack_count


def _measure(number: str, unit_word: str) -> tuple[Decimal, Unit] | None:
    value, hit = _dec(number), _unit_word(unit_word)
    if value is None or hit is None:
        return None
    unit, factor = hit
    return value * factor, unit


def parse_fields(quantity: Any, unit: str | None) -> tuple[Decimal, Unit] | None:
    """The chain's Quantity/UnitQty fields as ``(quantity, unit)`` in g, ml or units.

    ``unit`` is the raw UnitQty text: גרם, גרמים, ק"ג, קילוגרמים, ליטר, מ"ל, יחידה, ...
    Returns None when either field is missing, zero, or the unit is unknown (לא ידוע, מטר)."""
    if quantity is None or not unit:
        return None
    try:
        value = Decimal(str(quantity))
    except InvalidOperation:
        return None
    if value <= 0:
        return None
    text = clean_name(str(unit))
    # "100 גרם" as a UnitQty: take the unit word, ignore the reference amount
    text = re.sub(r"^\d+(?:[.,]\d+)?\s*", "", text)
    hit = _unit_word(text)
    if hit is None:
        return None
    u, factor = hit
    return value * factor, u


@dataclass(frozen=True)
class NameSize:
    size: Size | None
    pack_word: int | None  # מארז N without a per-piece size next to it
    weighed_word: bool
    ambiguous: str | None = None


def parse_name(name: str) -> NameSize:
    """Size information found in a cleaned name."""
    weighed_word = bool(_WEIGHED_WORDS.search(name))
    pack_word = None
    m = _PACK_WORD.search(name)
    if m:
        pack_word = int(m.group(1))
    else:
        named = _PACK_NAMED_RE.search(name)
        if named:
            pack_word = _PACK_NAMED[named.group(1)]

    m = _MULTI_COUNT_FIRST.search(name)
    if m:
        a, b = _dec(m.group(1)), _dec(m.group(2))
        measure = _measure(m.group(2), m.group(3))
        if a is not None and b is not None and measure is not None:
            if a == a.to_integral_value() and (b != b.to_integral_value() or a <= b):
                return NameSize(Size(measure[0], measure[1], int(a)), None, weighed_word)
            # "250*4 גרם": the integer next to the unit is the count
            other = _measure(m.group(1), m.group(3))
            if b == b.to_integral_value() and other is not None:
                return NameSize(Size(other[0], other[1], int(b)), None, weighed_word)
    m = _MULTI_SIZE_FIRST.search(name)
    if m:
        measure = _measure(m.group(1), m.group(2))
        if measure is not None:
            return NameSize(Size(measure[0], measure[1], int(m.group(3))), None, weighed_word)

    measures = [x for x in (_measure(g1, g2) for g1, g2 in _MEASURE.findall(name)) if x]
    counts = [int(n) for n, _ in _COUNT.findall(name) if int(n) > 0]
    ambiguous = None
    if len(set(measures)) > 1:
        ambiguous = f"several sizes in the name: {', '.join(f'{q:g} {u}' for q, u in measures)}"
    if measures:
        qty, unit = measures[0]
        pieces = pack_word or (counts[0] if counts else None)
        if pieces and pieces > 1:
            return NameSize(Size(qty, unit, pieces), pack_word, weighed_word, ambiguous)
        return NameSize(Size(qty, unit), pack_word, weighed_word, ambiguous)
    if counts:
        return NameSize(Size(Decimal(counts[0]), "unit"), pack_word, weighed_word)
    return NameSize(None, pack_word, weighed_word)


# --- normalize -----------------------------------------------------------------------------------

_BASE: dict[Unit, BaseUnit] = {"g": "100g", "ml": "100ml", "unit": "unit"}
WEIGHED_REFERENCE = Decimal(1000)
"""Weighed items are normalized as 1 kg: chains publish their shelf price per kg."""


@dataclass(frozen=True)
class NormalizationResult:
    item: NormalizedItem
    issues: tuple[str, ...] = ()
    source: Literal["fields", "name", "weighed", "none"] = "none"

    @property
    def parsed(self) -> bool:
        return self.item.base_unit is not None


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _plain(value: Decimal) -> Decimal:
    """1000 rather than 1E+3; 1.5 rather than 1.500."""
    if value == value.to_integral_value():
        return value.quantize(Decimal(1))
    return value.normalize()


def _to_item(item_id: int, name: str, size: Size, *, weighed: bool = False) -> NormalizedItem:
    q = _plain(size.quantity)
    total = _plain(size.total)
    return NormalizedItem(
        item_id=item_id,
        clean_name=name,
        quantity=q,
        unit=size.unit,
        pack_count=size.pack_count,
        total_quantity=total,
        base_unit="kg" if weighed else _BASE[size.unit],
        is_weighed=weighed,
    )


def _field_is_kg(unit: Any) -> bool:
    if not unit:
        return False
    text = re.sub(r"^\d+(?:[.,]\d+)?\s*", "", clean_name(str(unit)))
    return _unit_word(text) == ("g", Decimal(1000))


def normalize_with_issues(item: Any, *, item_id: int | None = None) -> NormalizationResult:
    """Normalize one item and say what was ambiguous. See the module docstring."""
    if item_id is None:
        item_id = _get(item, "id") or _get(item, "item_id") or 0
    name = clean_name(str(_get(item, "raw_name") or ""))
    issues: list[str] = []
    raw_qty, raw_unit = _get(item, "quantity"), _get(item, "unit")
    fields = parse_fields(raw_qty, raw_unit)
    found = parse_name(name)
    size = found.size
    if found.ambiguous:
        issues.append(found.ambiguous)

    def done(s: Size, source: Literal["fields", "name"]) -> NormalizationResult:
        return NormalizationResult(_to_item(item_id, name, s), tuple(issues), source)

    # --- weighed goods: the shelf price is per kg ---------------------------------------------
    has_measure = size is not None and size.unit != "unit"
    weighed = bool(_get(item, "is_weighed")) or found.weighed_word
    if not weighed and not has_measure:
        code = str(_get(item, "item_code") or "")
        if _field_is_kg(raw_unit) and (fields is None or fields[0] == WEIGHED_REFERENCE):
            weighed = True
            issues.append("treated as weighed: unit is kg and the name has no size")
        elif _PLU.match(code):
            weighed = True
            issues.append(f"treated as weighed: PLU-style item code {code}")
    if weighed:
        return NormalizationResult(
            _to_item(item_id, name, Size(WEIGHED_REFERENCE, "g"), weighed=True),
            tuple(issues),
            "weighed",
        )

    # --- the name has a measure (g/ml): it wins, the fields only cross-check it ------------------
    if size is not None and has_measure:
        if fields is not None:
            f_qty, f_unit = fields
            if f_unit == "unit":
                if f_qty > 1 and size.pack_count == 1 and f_qty == f_qty.to_integral_value():
                    size = Size(size.quantity, size.unit, int(f_qty))
                    issues.append(f"{int(f_qty)} pieces from the fields, size from the name")
            elif f_unit != size.unit:
                issues.append(f"fields say {f_unit}, name says {size.unit}; used the name")
            elif f_qty not in (size.quantity, size.total):
                issues.append(
                    f"fields say {f_qty:g} {f_unit}, name says {size.total:g} {size.unit};"
                    " used the name"
                )
        return done(size, "name")

    # --- the fields have a measure: they are the pack total ---------------------------------------
    pieces = found.pack_word or (int(size.quantity) if size is not None else 1)
    if fields is not None and fields[1] != "unit":
        f_qty, f_unit = fields
        if pieces > 1:
            issues.append(f"{pieces} pieces from the name; the fields are the pack total")
            return done(Size(f_qty / pieces, f_unit, pieces), "fields")
        return done(Size(f_qty, f_unit), "fields")

    # --- counted goods: 12 ביצים, 32 גלילים, 1 יחידה --------------------------------------------
    if size is not None:
        packs = found.pack_word if found.pack_word and found.pack_word > 1 else 1
        return done(Size(size.quantity, "unit", packs), "name")
    if fields is not None:
        return done(Size(fields[0], "unit", found.pack_word or 1), "fields")
    if found.pack_word:
        issues.append("only a pack count was found; unit price is per piece")
        return done(Size(Decimal(1), "unit", found.pack_word), "name")
    issues.append("unparseable: no quantity in the fields or the name")
    return NormalizationResult(
        NormalizedItem(item_id=item_id, clean_name=name), tuple(issues), "none"
    )


def normalize(item: Any, *, item_id: int | None = None) -> NormalizedItem:
    """Normalize one ``items`` row. Use ``normalize_with_issues`` to see what was ambiguous."""
    return normalize_with_issues(item, item_id=item_id).item


# --- unit price ----------------------------------------------------------------------------------

_PER = {"100g": Decimal(100), "100ml": Decimal(100), "unit": Decimal(1), "kg": Decimal(1000)}
_PLACES = Decimal("0.0001")


def unit_price(price: Decimal, normalized: NormalizedItem) -> tuple[Decimal, BaseUnit]:
    """Price per 100 g, per 100 ml, per unit, or per kg (weighed goods), on the pack total.

    A weighed item's price is already per kg, so it comes back unchanged and is an estimate
    (``normalized.is_weighed``): the shopper pays for the weight on the scale. Raises
    ``ValueError`` for an item whose size could not be parsed, rather than guessing."""
    base = normalized.base_unit
    total = normalized.total_quantity
    if base is None or total is None or total <= 0:
        raise ValueError(f"item {normalized.item_id} has no parsed size; no unit price")
    if normalized.is_weighed:
        return Decimal(price).quantize(_PLACES), "kg"
    value = Decimal(price) * _PER[base] / total
    return value.quantize(_PLACES), base
