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
    Abbreviation(
        _P + r'ש(?:\.|")ז\.?' + _NOT_WORD,
        r"\1שמן זית",
        "ש.ז. = שמן זית (olive oil); general knowledge, reviewer to confirm",
    ),
    Abbreviation(_P + r"מהד'", r"\1מהדורה", "מהד' מוגבלת = limited edition"),
    Abbreviation(_P + r'תפו"א' + _NOT_WORD, r"\1תפוחי אדמה"),
    Abbreviation(_P + r'ק"ג' + _NOT_WORD, r"\1קילוגרם"),
    Abbreviation(_P + r"קג'" + _NOT_WORD, r"\1קילוגרם"),
    Abbreviation(_P + r"קג" + rf"(?![{_HE}A-Za-z'])", r"\1קילוגרם"),
    Abbreviation(_P + r'מ"ל' + _NOT_WORD, r"\1מיליליטר"),
    Abbreviation(_P + r"גר'" + _NOT_WORD, r"\1גרם"),
    Abbreviation(_P + r"ליט'" + _NOT_WORD, r"\1ליטר"),
    # sugar claims: ללת"ס / לל"ס are printed on "no added sugar" and "sugar free" goods (a diet
    # variant, never the regular product); real names: חמאת בוטנים ללת"ס, סוכריות חמאה לל"ס
    Abbreviation(_P + r'ללת"ס' + _NOT_WORD, r"\1ללא תוספת סוכר", "ללא תוספת סוכר"),
    Abbreviation(_P + r'לל"ס' + _NOT_WORD, r"\1ללא סוכר", "ללא סוכר"),
    Abbreviation(_P + r'חד"פ' + _NOT_WORD, r"\1חד פעמי", "disposable"),
    # dotted chain shorthand for the first word of a name: שוק.מריר, חט.דגנים, תח.גוף, נ.כלים
    Abbreviation(_P + r"שוק\.\s*", r"\1שוקולד ", "שוק. = שוקולד"),
    Abbreviation(_P + r"חט\.\s*", r"\1חטיף ", "חט. = חטיף"),
    Abbreviation(_P + r"תח\.\s*", r"\1תחליב ", "תח. = תחליב (body lotion)"),
    Abbreviation(_P + r"מ\.כביסה" + _NOT_WORD, r"\1מרכך כביסה", "מ.כביסה"),
    Abbreviation(_P + r"נ\.כלים" + _NOT_WORD, r"\1נוזל כלים", "נ.כלים"),
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


# --- truncated names -------------------------------------------------------------------------------

# Several chains publish ItemName cut at a fixed width (measured on the committed real fixtures
# of 2026-10-08: the longest name is 20 characters for Carrefour/Mega, Osher Ad, Rami Levy and
# Yohananof, 24 for Shufersal and 40 for Tiv Taam; King Store's longest is 55 with no pile-up at
# one length, so it is not cut). A cut name may end inside a word ("חלבון" -> "חלב"), and may
# have lost a flavor, a fat percentage or a size: it must not be trusted as complete.
NAME_LIMITS: dict[str, int] = {
    "7290055700007": 20,  # Carrefour (Mega)
    "7290103152017": 20,  # Osher Ad
    "7290058140886": 20,  # Rami Levy
    "7290803800003": 20,  # Yohananof
    "7290027600007": 24,  # Shufersal
    "7290873255550": 40,  # Tiv Taam
}


def is_truncated(chain_id: str | None, raw_name: str | None) -> bool:
    """True when ``raw_name`` is at, or one character under, its chain's cut width.

    One under, because a cut right after a space is stripped, so a name cut at 20 can be 19
    long. A name longer than the width was not cut by that chain. A false positive only sends
    an item to review; a false negative can serve a wrong match, so the boundary errs on the
    side of "cut"."""
    limit = NAME_LIMITS.get(chain_id or "")
    if limit is None or not raw_name:
        return False
    return limit - 1 <= len(raw_name.strip()) <= limit


def is_full_width(chain_id: str | None, raw_name: str | None) -> bool:
    """True when ``raw_name`` is exactly as wide as its chain cuts names: the last word may be
    a fragment (a name cut at a space is one character shorter and ends on a whole word)."""
    limit = NAME_LIMITS.get(chain_id or "")
    return limit is not None and bool(raw_name) and len(raw_name.strip()) == limit


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
_COUNT_NOUNS = (
    "יחידות",
    "יחידה",
    "יח",
    "גלילים",
    "שקיות",
    "ביצים",
    "טבליות",
    "קפסולות",
    "מגבונים",
    "שקיקים",
    "פריטים",
    "כוסות",
    "צלחות",
    "ממחטות",
    "פיתות",
    "לחמניות",
)

_MEASURE_ALT = "|".join(
    sorted(
        (re.escape(w) for w, (u, _) in _UNIT_WORDS.items() if u != "unit"), key=len, reverse=True
    )
)
_COUNT_ALT = "|".join(sorted((re.escape(w) for w in _COUNT_NOUNS), key=len, reverse=True))
_NUM = r"(\d+(?:[.,]\d+)?)"
_X = r"\s*[*xX×]\s*"

# 6*1.5 ליטר / 4X250 מיליליטר (count first) and 1.5 ליטר*6 (size first)
_MULTI_COUNT_FIRST = re.compile(
    rf"{_NOT_WORD_BEFORE}{_NUM}{_X}{_NUM}\s*({_MEASURE_ALT}){_NOT_WORD}"
)
_MULTI_SIZE_FIRST = re.compile(rf"{_NUM}\s*({_MEASURE_ALT}){_X}(\d+){_NOT_WORD}")
_MEASURE = re.compile(rf"{_NOT_WORD_BEFORE}{_NUM}\s*-?\s*({_MEASURE_ALT}){_NOT_WORD}")
_COUNT = re.compile(rf"{_NOT_WORD_BEFORE}(\d+)\s*({_COUNT_ALT}){_NOT_WORD}")
# "מארז 8" is a count; "מארז 500 גרם" is a size, so a number followed by a unit is not a count
_PACK_WORD = re.compile(
    r"(?:מארז|מארזי|אריזת|חבילת|מגש)\s*(?:של\s*)?(\d+)"
    + rf"(?![\d.,]|\s*(?:{_MEASURE_ALT}){_NOT_WORD}|{_X})"
    + _NOT_WORD
)
_PACK_NAMED = {
    "זוג": 2,
    "שלישייה": 3,
    "שלישיית": 3,
    "רביעייה": 4,
    "רביעיית": 4,
    "שישייה": 6,
    "שישיית": 6,
}
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


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_with_issues(item: Any, *, item_id: int | None = None) -> NormalizationResult:
    """Normalize one item and say what was ambiguous. See the module docstring.

    The returned item also carries the row's ``chain_id``, ``chain_name``, ``manufacturer``,
    ``barcode`` and ``raw_name`` when the row has them, and ``issues`` (issue #92)."""
    result = _normalize(item, item_id=item_id)
    source = {
        "chain_id": _text(_get(item, "chain_id")),
        "chain_name": _text(_get(item, "chain_name")),
        "manufacturer": _text(_get(item, "manufacturer")),
        "barcode": _text(_get(item, "barcode")),
        "raw_name": _text(_get(item, "raw_name")),
        "issues": result.issues,
    }
    return NormalizationResult(result.item.model_copy(update=source), result.issues, result.source)


def _normalize(item: Any, *, item_id: int | None = None) -> NormalizationResult:
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


# --- Arabic (issue #73) ------------------------------------------------------------------------
#
# Pure helpers for Arabic shopping-list lines and canonical names. ``fold_ar`` is the character
# level folding that ``search_norm_ar()`` in the database repeats (supabase migration
# 20261011100600); ``normalize_ar`` adds the rewrites that only a query needs ("3 بالمية" -> "3%").
# The article ال and the conjunction و are not removed here: ``ar_variants`` offers the forms
# without them and matching tries both, the way the Hebrew prefix letters are handled.

import unicodedata  # noqa: E402
from typing import NamedTuple  # noqa: E402

AR_LETTERS = "ء-غف-يٮ-ۓۺ-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿"
_AR_RE = re.compile(f"[{AR_LETTERS}]")
_HE_RE = re.compile("[א-ת]")


def has_arabic(text: str) -> bool:
    return _AR_RE.search(text) is not None


def script_of(text: str) -> Literal["ar", "he", "other"]:
    """The script of a list line: ``ar`` when it has more Arabic than Hebrew letters, ``he`` when
    Hebrew wins or ties, ``other`` when it has neither (digits, Latin only). Only ``ar`` takes the
    Arabic path; everything else keeps the Hebrew behavior."""
    n_ar = len(_AR_RE.findall(text))
    n_he = len(_HE_RE.findall(text))
    if n_ar > n_he:
        return "ar"
    return "he" if n_he else "other"


_FOLD_FROM = (
    "أإآٱ" "ى" "ة" "ؤ" "ئ" "ک" "ی" "ڤ" "پ"
    "٠١٢٣٤٥٦٧٨٩" "۰۱۲۳۴۵۶۷۸۹"
    "٪٫،؛؟"
    "ءـ٬" "\"'`’‘“”"
)  # fmt: skip
_FOLD_TO = "اااايهويكيفب01234567890123456789%.,;?"
FOLD_TRANSLATE: dict[int, str | None] = {
    **{ord(a): b for a, b in zip(_FOLD_FROM, _FOLD_TO, strict=False)},
    **{ord(c): None for c in _FOLD_FROM[len(_FOLD_TO) :]},
}
_MARKS = re.compile("[ً-ٰٟۖ-ۭ‎‏؜‪-‮⁦-⁩]")
_PUNCT = re.compile(r"[\s,;:!?()\[\]{}/\\*+=|<>~#&^$@«»…–—•·-]+")


def fold_ar(text: str) -> str:
    """Spelling-variant folding, identical to ``search_norm_ar()`` in Postgres: NFKC and lower
    case; alef forms to ا, ى to ي, ة to ه, ؤ to و, ئ to ي, hamza and tatweel removed, tashkeel
    removed, Arabic-Indic and Persian digits to Latin, Arabic punctuation to ASCII, quote marks
    removed, punctuation to single spaces."""
    s = unicodedata.normalize("NFKC", text).lower().translate(FOLD_TRANSLATE)
    s = _MARKS.sub("", s)
    return _PUNCT.sub(" ", s).strip()


_NUM_RE = r"\d+(?:\.\d+)?"
_PCT_WORD = r"(?:بالميه|بالمايه|في\s+الميه|في\s+المايه)"
# Whole-number words, as fold_ar spells them, that precede "بالمية" ("ثلاثة بالمية" = 3%).
_PCT_NUMBERS: dict[str, str] = {
    "واحد ونص": "1.5", "واحد ونصف": "1.5", "واحد": "1", "اثنين": "2", "اتنين": "2",
    "ثنتين": "2", "ثلاثه": "3", "ثلاث": "3", "تلاته": "3", "تلات": "3", "اربعه": "4",
    "اربع": "4", "خمسه": "5", "خمس": "5", "سته": "6", "ست": "6", "سبعه": "7", "سبع": "7",
    "ثمانيه": "8", "ثماني": "8", "تمانيه": "8", "تماني": "8", "تسعه": "9", "تسع": "9",
    "عشره": "10", "عشر": "10", "خمستعشر": "15", "خمسه عشر": "15", "عشرين": "20",
    "اربعه وعشرين": "24", "ثمانيه وعشرين": "28", "تمانيه وعشرين": "28", "ثلاثين": "30",
    "تلاتين": "30", "اثنين وثلاثين": "32", "اتنين وتلاتين": "32", "ثمانيه وثلاثين": "38",
    "تمانيه وتلاتين": "38",
}  # fmt: skip
_PCT_NUMBER_RE = re.compile(
    r"(?<![\w.])("
    + "|".join(sorted(map(re.escape, _PCT_NUMBERS), key=len, reverse=True))
    + r")\s*(?="
    + _PCT_WORD
    + ")"
)


def normalize_ar(text: str) -> str:
    """``fold_ar`` plus the rewrites of a shopper's query: "%3" and "3 %" become "3%", and
    "3 بالمية", "ثلاثة بالمئة" become "3%". The article and the conjunction stay (``ar_variants``)."""
    s = fold_ar(text)
    s = _PCT_NUMBER_RE.sub(lambda m: _PCT_NUMBERS[m.group(1)] + " ", s)
    s = re.sub(rf"({_NUM_RE})\s*{_PCT_WORD}", r"\1%", s)
    s = re.sub(rf"(?<![\d.])%\s*({_NUM_RE})(?![\d%])", r"\1%", s)
    s = re.sub(rf"({_NUM_RE})\s+%", r"\1%", s)
    return " ".join(s.split())


_AR_PROCLITIC_ARTICLES = ("بال", "لل", "كال")


def ar_variants(token: str) -> list[str]:
    """A normalized token and its forms without a removable prefix: ال ("the"), و ("and"), وال,
    and the preposition + article forms بال ("with the") and لل ("for the"), which lists use
    ("بالفراولة", "للطبخ"). A prefix is only removed when at least three letters remain, so ورق
    and الف stay whole. ``"الحليب" -> ["الحليب", "حليب"]``; ``"وحليب" -> ["وحليب", "حليب"]``."""
    out = [token]
    rest = token
    if token.startswith("و") and len(token) >= 4:
        rest = token[1:]
        out.append(rest)
    for pre in _AR_PROCLITIC_ARTICLES:
        if rest.startswith(pre) and len(rest) - len(pre) >= 3:
            out.append(rest[len(pre) :])
            break
    else:
        if rest.startswith("ال") and len(rest) >= 5:
            out.append(rest[2:])
    return list(dict.fromkeys(out))


def ar_strip_prefixes(text: str) -> str:
    """Normalized text with the article ال removed from every word (and the و before it)."""
    return " ".join(
        ar_variants(t)[-1] if t.startswith(("ال", "وال", "بال", "لل", "كال")) else t
        for t in text.split()
    )


# Brands a shopper adds to a line ("حليب تنوفا 3%"). Canonicals are brand-free, so matching drops
# them (only when another word remains); names that contain a brand (نوتيلا, ميلكي) are not here.
AR_BRANDS: frozenset[str] = frozenset(
    fold_ar(b)
    for b in (
        "تنوفا", "شتراوس", "اوسم", "عوسم", "عيليت", "عليت", "تيفع", "تارا", "زوغلوبك",
        "زوغلوبيك", "سوغات", "يوطبتا", "ويسوتسكي", "ليبتون", "كنور", "هاينز", "باريلا",
        "tnuva", "strauss", "osem", "elite", "tara", "zoglowek", "sugat", "wissotzky",
        "lipton", "knorr", "heinz", "barilla",
    )
)  # fmt: skip


# Politeness and soft descriptors that the canonical does not state ("close" flexibility: size,
# family pack, novelty). Dropped from the query when another word remains.
AR_FILLER: frozenset[str] = frozenset(
    fold_ar(w)
    for w in (
        "كبير", "كبيرة", "صغير", "صغيرة", "وسط", "عائلي", "عائلية", "اقتصادي", "اقتصادية",
        "جديد", "جديدة", "عرض", "توفير", "لو", "سمحت", "من", "فضلك", "ارجوك", "بدي", "بدنا",
        "اريد", "نريد", "محتاج", "محتاجة", "عدد", "منتج", "نوع",
    )
)  # fmt: skip
_SIZE_WORDS = frozenset({"رول", "رولات", "لفه", "لفات"})
_BARE_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def ar_clean_query(text: str) -> str:
    """``text`` (as ``normalize_ar`` made it) without what is not part of the product: brands,
    soft descriptors, politeness, bare numbers (pack counts and sizes such as "12", "32 رول",
    "500 غرام"); a percentage stays. Unchanged when nothing else would be left."""
    kept: list[str] = []
    after_number = False
    for tok in text.split():
        if _BARE_NUMBER.fullmatch(tok):
            after_number = True
            continue
        size = after_number and (ar_unit(tok) is not None or tok in _SIZE_WORDS)
        after_number = False
        if size or any(v in AR_FILLER or v in AR_BRANDS for v in ar_variants(tok)):
            continue
        kept.append(tok)
    return " ".join(kept) if kept else text


# --- units and quantity words ----------------------------------------------------------------


class ArUnit(NamedTuple):
    kind: Literal["mass", "volume", "count"]
    factor: Decimal
    """Mass in kg per unit, volume in litres per unit, count in pieces per unit."""
    multiplier: int = 1
    """2 for a dual form (علبتين = two boxes, كيلوين = two kilos)."""
    plural: bool = False
    """A plural form (اكياس, علب): only a unit after a number; alone it is product text
    (اكياس زبالة)."""


_DUAL_BASES = (
    "كيلو", "غرام", "جرام", "لتر", "ليتر", "علبه", "حبه", "قطعه", "كيس", "باكيت", "زجاجه",
    "عبوه", "كرتونه", "ربطه", "حزمه", "وحده", "صندوق", "مغلف", "طبق", "قنينه",
)  # fmt: skip


def _dual_forms(word: str) -> list[str]:
    if word.endswith("ه"):
        return [word[:-1] + "تين", word[:-1] + "تان"]
    return [word + "ين", word + "ان"]


_PLURAL_UNITS = frozenset({
    "علب", "حبات", "قطع", "اكياس", "باكيتات", "زجاجات", "عبوات", "كراتين", "ربطات", "حزم",
    "وحدات", "صناديق", "كيلوات", "غرامات", "جرامات", "لترات", "ليترات", "مليلترات",
    "كيلوغرامات",
})  # fmt: skip
AR_UNITS: dict[str, ArUnit] = {}
for _kind, _factor, _words in (
    ("mass", Decimal(1), ("كيلو", "كيلوغرام", "كيلوجرام", "كيلوغرامات", "كغم", "كجم", "كغ",
                          "كج", "كلغ", "كلغم", "كلجم", "كيلوات", "كلو")),
    ("mass", Decimal("0.001"), ("غرام", "جرام", "غم", "جم", "غرامات", "جرامات", "غر")),
    ("volume", Decimal(1), ("لتر", "ليتر", "لترات", "ليترات")),
    ("volume", Decimal("0.001"), ("مل", "ملل", "ملي", "مليلتر", "مللتر", "ميليلتر", "مليلترات")),
    ("count", Decimal(1), ("علبه", "علب", "حبه", "حبات", "قطعه", "قطع", "كيس", "اكياس",
                           "باكيت", "باكيتات", "باكت", "زجاجه", "زجاجات", "قنينه", "عبوه",
                           "عبوات", "كرتونه", "كراتين", "كرتون", "ربطه", "ربطات", "حزمه",
                           "حزم", "وحده", "وحدات", "صندوق", "صناديق", "مغلف", "طبق")),
):  # fmt: skip
    for _w in _words:
        AR_UNITS[_w] = ArUnit(_kind, _factor, 1, _w in _PLURAL_UNITS)
        if _w in _DUAL_BASES:
            for _d in _dual_forms(_w):
                AR_UNITS[_d] = ArUnit(_kind, _factor, 2)
del _kind, _factor, _words, _w


def ar_unit(word: str) -> ArUnit | None:
    """The unit a word names (any spelling variant, with or without ال), or None.

    ``ar_unit("كغم") -> ArUnit("mass", 1)``, ``ar_unit("علبتين") -> ArUnit("count", 1, 2)``,
    ``ar_unit("الكيلو")`` is the kilo too."""
    w = fold_ar(word).replace(" ", "")
    for v in ar_variants(w):
        if v in AR_UNITS:
            return AR_UNITS[v]
    return None


AR_NUMBER_WORDS: dict[str, int] = {
    "واحد": 1, "واحده": 1, "اثنين": 2, "اتنين": 2, "اثنان": 2, "اثنتين": 2, "ثنتين": 2,
    "ثلاث": 3, "ثلاثه": 3, "تلات": 3, "تلاته": 3, "اربع": 4, "اربعه": 4, "خمس": 5,
    "خمسه": 5, "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثمان": 8, "ثماني": 8, "ثمانيه": 8,
    "تمان": 8, "تمانيه": 8, "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10,
}  # fmt: skip
AR_FRACTION_WORDS: dict[str, Decimal] = {
    "نص": Decimal("0.5"), "نصف": Decimal("0.5"), "ربع": Decimal("0.25"),
    "ثلث": Decimal("0.333"), "تلت": Decimal("0.333"),
}  # fmt: skip


# --- query attributes (the hard checks) ---------------------------------------------------------

_AR_STATE_WORDS: dict[str, tuple[str, ...]] = {
    "fresh": ("طازج", "طازجه", "طازجين", "طازه", "طري", "طريه", "فريش"),
    "frozen": ("مجمد", "مجمده", "مجمدين", "مجمدات", "مثلج", "مثلجه", "متجمد", "فروزن"),
    "canned": ("معلب", "معلبه", "معلبات", "كونسروه", "بالعلبه"),
    "dry": ("ناشف", "ناشفه", "جاف", "جافه", "يابس", "يابسه", "مجفف", "مجففه"),
    "chilled": ("مبرد", "مبرده"),
}
_AR_BASE_WORDS: dict[str, tuple[str, ...]] = {
    "soy": ("صويا", "سويا", "صوجا"),
    "almond": ("لوز",),
    "oat": ("شوفان",),
    "coconut": ("كوكوس",),
}
_AR_FLAVOR_WORDS: dict[str, tuple[str, ...]] = {
    "strawberry": ("فراوله", "فريز"),
    "peach": ("خوخ", "دراق"),
    "chocolate": ("شوكولاته", "شوكولا", "شوكولاطه", "شيكولاته", "شوكو"),
    "vanilla": ("فانيلا", "فانيليا"),
    "cheese": ("جبنه",),
    "potato": ("بطاطا", "بطاطس"),
    "grill": ("شواء", "غريل", "مشوي", "مشويه"),
    "onion": ("بصل",),
    "salted": ("مملح", "مملحه", "بالملح", "مالح", "مالحه"),
    "milk": ("حليب",),
    "dark": ("داكنه", "داكن", "مره", "مر"),
    "lemon": ("ليمون",),
    "plain": ("طبيعي", "طبيعيه", "ساده", "بلين"),
    "chicken": ("دجاج",),
}  # fmt: skip
STATE_CONFLICTS: dict[str, frozenset[str]] = {
    "frozen": frozenset({"fresh", "canned", "dry", "chilled"}),
    "canned": frozenset({"fresh", "frozen", "chilled", "dry"}),
    "fresh": frozenset({"frozen", "canned", "dry"}),
    "dry": frozenset({"frozen", "canned"}),
    "chilled": frozenset({"frozen", "canned"}),
}
"""query state -> catalog states it contradicts. A query that says "dry" does not contradict a
fresh canonical (the catalog's dry onion is state fresh); one that says "fresh" does contradict
frozen, canned and dry."""


def _word_table(table: dict[str, tuple[str, ...]]) -> dict[str, str]:
    return {fold_ar(w): key for key, words in table.items() for w in words}


_STATE_LOOKUP = _word_table(_AR_STATE_WORDS)
_BASE_LOOKUP = _word_table(_AR_BASE_WORDS)
_FLAVOR_LOOKUP = _word_table(_AR_FLAVOR_WORDS)
_FAT_RE = re.compile(rf"(?<![\w.])({_NUM_RE})%")
_FAT_ZERO = re.compile(r"(?:^| )(?:خالي|بدون|من غير|ما فيه) (?:ال)?دسم(?: |$)")


class ArAttributes(NamedTuple):
    """What a query or a name states about the critical attributes. Empty = not stated."""

    fat_pct: frozenset[Decimal]
    state: frozenset[str]
    base: frozenset[str]
    flavor: frozenset[str]


def _attribute_forms(token: str) -> set[str]:
    """A token, its forms without و/ال, and without the proclitic ب/ل/ك (بالحليب -> حليب)."""
    forms = set(ar_variants(token))
    for form in list(forms):
        for pre in ("بال", "لل", "كال", "فال"):
            if form.startswith(pre) and len(form) - len(pre) >= 3:
                forms.add(form[len(pre) :])
        if form[:1] in ("ب", "ل", "ك") and len(form) >= 5:
            forms.add(form[1:])
    return forms


def ar_attributes(text: str) -> ArAttributes:
    """The fat percentages, states (fresh, frozen, canned, dry, chilled), plant bases and flavors
    that an Arabic query or canonical name states, from the lexicons above. Shared by the seed
    validation (a canonical's name must state its critical attributes) and the API's hard checks
    (a query may not resolve to a canonical whose critical attribute it contradicts)."""
    s = normalize_ar(text)
    fats = {Decimal(m) for m in _FAT_RE.findall(s)}
    if _FAT_ZERO.search(s):
        fats.add(Decimal(0))
    states: set[str] = set()
    bases: set[str] = set()
    flavors: set[str] = set()
    for tok in s.split():
        for v in _attribute_forms(tok):
            if v in _STATE_LOOKUP:
                states.add(_STATE_LOOKUP[v])
            if v in _BASE_LOOKUP:
                bases.add(_BASE_LOOKUP[v])
            if v in _FLAVOR_LOOKUP:
                flavors.add(_FLAVOR_LOOKUP[v])
    return ArAttributes(frozenset(fats), frozenset(states), frozenset(bases), frozenset(flavors))


def ar_conflicts(
    query: ArAttributes,
    critical: Mapping[str, Any],
    sibling_flavors: frozenset[str] = frozenset(),
) -> list[str]:
    """Critical attributes of a canonical that the query contradicts (empty = compatible).

    fat_pct and base must equal a stated value; state follows ``STATE_CONFLICTS``. A flavor
    contradicts only when the query states a flavor of a *sibling* (``sibling_flavors``: the
    flavors of the other canonicals of the same product type) and not the canonical's own, so a
    generic noun in the query ("جبنة" in "جبنة كريمة") never vetoes anything. Only keys the
    canonical has are checked."""
    out: list[str] = []
    fat = critical.get("fat_pct")
    if fat is not None and query.fat_pct and Decimal(str(fat)) not in query.fat_pct:
        out.append(f"fat_pct {fat}")
    base = critical.get("base")
    if base is not None and query.base and str(base) not in query.base:
        out.append(f"base {base}")
    flavor = critical.get("flavor")
    if (
        flavor is not None
        and str(flavor) not in query.flavor
        and query.flavor & (sibling_flavors - {str(flavor)})
    ):
        out.append(f"flavor {flavor}")
    state = critical.get("state")
    if state is not None and any(str(state) in STATE_CONFLICTS[q] for q in query.state):
        out.append(f"state {state}")
    return out
