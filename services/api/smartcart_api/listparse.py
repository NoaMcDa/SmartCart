"""Split a pasted Hebrew shopping list into fragments with quantities (issue #51).

Splitting: newlines, commas, semicolons and bullets always separate items. `` ו`` ("and", a vav
attached to the next word after a space) separates only when the whole fragment does not resolve
confidently on its own, so "חלב ולחם" becomes two rows while a product whose name contains a
word starting with ו stays whole; the caller decides (see routes/parse_list.py).

Quantities, at the start or the end of a fragment:

* leading count: ``2 רסק עגבניות``, ``2x חלב``, ``x2 חלב``, ``שני חלב`` (Hebrew number words 2-10);
* leading weight: ``1.5 ק"ג עגבניות``, ``500 גרם גבינה`` (converted to kg, ``unit = "kg"``);
* trailing count only with an explicit marker: ``חלב x3``, ``חלב ×3``, ``חלב *3``, ``חלב 3x``,
  ``חלב 3 יח'``. A bare trailing number stays in the text, because it is usually part of the
  product (``ביצים L 12``, ``חלב 3%``, ``רסק 100 גרם``).

Arabic lines (issue #73) take a separate path: a line with more Arabic than Hebrew letters is
split and parsed by the ``*_ar`` functions below (``,`` between digits is a decimal mark, ``و``
is the conjunction, and quantities such as ``نص كيلو``, ``كيلو ونص``, ``علبتين``, ``2 كيلو`` are
understood). Text with no Arabic letters never reaches them, so Hebrew results do not change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from smartcart_catalog.normalize import (
    AR_FRACTION_WORDS,
    AR_LETTERS,
    AR_NUMBER_WORDS,
    FOLD_TRANSLATE,
    fold_ar,
    has_arabic,
    script_of,
)
from smartcart_catalog.normalize import ar_unit as _ar_unit

MAX_QUANTITY = Decimal(99)

_SEPARATORS = re.compile(r"[\n\r,;،؛]+|(?:^|\s)[•·▪\-–*]\s+")
_VAV_SPLIT = re.compile(r"\s+ו(?=[א-ת])")
_NUM = r"\d+(?:[.,]\d+)?"
_WORD_NUMBERS = {
    "שני": 2,
    "שתי": 2,
    "שניים": 2,
    "שתיים": 2,
    "שלוש": 3,
    "שלושה": 3,
    "ארבע": 4,
    "ארבעה": 4,
    "חמש": 5,
    "חמישה": 5,
    "שש": 6,
    "שישה": 6,
    "שבע": 7,
    "שבעה": 7,
    "שמונה": 8,
    "תשע": 9,
    "תשעה": 9,
    "עשר": 10,
    "עשרה": 10,
}
_KG = r"(?:ק\"ג|ק״ג|קג|קילו(?:גרם)?|kg)"
_GRAM = r"(?:גרם|גר'?|g)"
_UNITS = r"(?:יח'?|יחידות|יחידה)"
_LEAD_WEIGHT = re.compile(rf"^({_NUM})\s*({_KG}|{_GRAM})\s+(.+)$", re.IGNORECASE)
_LEAD_COUNT = re.compile(rf"^(?:[x×*]\s*)?({_NUM})\s*(?:[x×*]|{_UNITS})?\s+(.+)$", re.IGNORECASE)
_TRAIL_COUNT = re.compile(
    rf"^(.+?)\s+(?:[x×*]\s*({_NUM})|({_NUM})\s*[x×*]|({_NUM})\s*{_UNITS})$", re.IGNORECASE
)


@dataclass(frozen=True)
class Fragment:
    input_text: str  # the fragment as the user typed it
    text: str  # the product text, quantity removed
    quantity: Decimal = Decimal(1)
    unit: str | None = None  # "kg" when a weight was given


def split_items(text: str) -> list[str]:
    if has_arabic(text):
        return split_items_ar(text)
    parts = [p.strip(" \t.-–•·▪*") for p in _SEPARATORS.split(text)]
    return [p for p in parts if p]


def split_vav(fragment: str) -> list[str]:
    """``"חלב ולחם"`` -> ``["חלב", "לחם"]``; no change without a `` ו`` boundary."""
    if script_of(fragment) == "ar":
        return split_waw_ar(fragment)
    parts = _VAV_SPLIT.split(fragment)
    return [p.strip() for p in parts if p.strip()]


def _dec(s: str) -> Decimal | None:
    try:
        d = Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None
    return d if 0 < d <= 10_000 else None


def parse_fragment(raw: str) -> Fragment:
    if script_of(raw) == "ar":
        return parse_fragment_ar(raw)
    s = " ".join(raw.split())
    m = _LEAD_WEIGHT.match(s)
    if m:
        amount = _dec(m.group(1))
        if amount is not None:
            if re.fullmatch(_GRAM, m.group(2), re.IGNORECASE):
                amount = amount / 1000
            return Fragment(raw, m.group(3).strip(), _cap(amount), "kg")
    words = s.split(" ", 1)
    if len(words) == 2 and words[0] in _WORD_NUMBERS:
        return Fragment(raw, words[1].strip(), Decimal(_WORD_NUMBERS[words[0]]))
    m = _LEAD_COUNT.match(s)
    if m and not re.match(r"^\s*%", m.group(2)):
        amount = _dec(m.group(1))
        if amount is not None:
            return Fragment(raw, m.group(2).strip(), _cap(amount))
    m = _TRAIL_COUNT.match(s)
    if m:
        amount = _dec(next(g for g in m.groups()[1:] if g))
        if amount is not None:
            return Fragment(raw, m.group(1).strip(), _cap(amount))
    return Fragment(raw, s)


def _cap(q: Decimal) -> Decimal:
    return min(q, MAX_QUANTITY)


# --- Arabic lists (issue #73) -------------------------------------------------------------------

_AR_SEPARATORS = re.compile(r"[;؛،]+|(?<!\d),|,(?!\d)|(?:^|\s)[•·▪\-–*]\s+")
_BIDI = "‎‏؜"
_AR_FRACTION_PATTERN = "|".join(("نص", "نصف", "ربع", "ثلث", "تلت"))
# A waw that is the conjunction "and": standalone ("حليب و خبز") or attached to the next word
# ("حليب وخبز"), but not the "and a half" of a quantity ("كيلو ونص").
_WAW_SPLIT = re.compile(
    rf"\s+و(?!\s*(?:{_AR_FRACTION_PATTERN})(?![{AR_LETTERS}]))\s*(?=[{AR_LETTERS}])"
)
_DIGITS_ONLY = {
    k: v for k, v in FOLD_TRANSLATE.items() if v is not None and (v.isdigit() or v in ".,")
}
_AR_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_AR_ATTACHED = re.compile(r"(\d+(?:[.,]\d+)?)([^\d\s.,]+)")
_AR_LEAD_MARK = re.compile(rf"^(?:[x×*]\s*({_NUM})|({_NUM})\s*[x×*])\s+(.+)$", re.IGNORECASE)
_AR_TRAIL_MARK = re.compile(rf"^(.+?)\s+(?:[x×*]\s*({_NUM})|({_NUM})\s*[x×*])$", re.IGNORECASE)
_AR_HALVES = {"ونص": "نص", "ونصف": "نصف", "وربع": "ربع", "وثلث": "ثلث", "وتلت": "تلت"}


def split_items_ar(text: str) -> list[str]:
    """Items of a pasted list that has Arabic in it. Newlines, ``،``, ``;`` and bullets always
    separate; a comma separates unless it sits between digits (``1,5 كيلو``). A line that is not
    mostly Arabic is split by the Hebrew rules."""
    parts: list[str] = []
    for line in re.split(r"[\r\n]+", text):
        pieces = _AR_SEPARATORS.split(line) if script_of(line) == "ar" else _SEPARATORS.split(line)
        parts.extend(p.strip(" \t.-–•·▪*" + _BIDI) for p in pieces)
    return [p for p in parts if p]


def split_waw_ar(fragment: str) -> list[str]:
    """``"حليب وخبز"`` -> ``["حليب", "خبز"]``; ``"كيلو ونص بندورة"`` stays whole. Like the Hebrew
    vav, a waw that starts a real word (ورق, وافل) is also split here; the caller keeps the
    fragment whole when its parts resolve worse than it does."""
    return [p.strip() for p in _WAW_SPLIT.split(fragment) if p.strip()]


def _latin(token: str) -> str:
    return token.translate(_DIGITS_ONLY)


def _number(token: str) -> Decimal | None:
    t = _latin(token)
    return _dec(t) if _AR_NUM.fullmatch(t) else None


def _leading_quantity_ar(
    tokens: list[str], *, trailing: bool = False
) -> tuple[Decimal, str | None, int] | None:
    """A quantity phrase at the start of ``tokens``: ``(quantity, unit, tokens used)``.

    Phrases: ``2`` / ``2.5`` / ``٢`` / ``ثلاث`` + optional unit, ``نص كيلو``, ``ربع كيلو``,
    ``كيلو`` (= 1), ``كيلوين`` (= 2), ``علبتين``, each optionally followed by ``ونص``/``وربع``.
    Mass becomes kilograms (``unit = "kg"``); a count noun is a count; a volume word is a pack
    count when it is a whole number of litres (``2 لتر`` = 2 packs of a litre) and 1 otherwise
    (``500 مل`` is a size, not a count). With ``trailing`` the phrase must be explicit: a bare
    number, a fraction, grams, millilitres and a lone count noun are product text there."""
    if not tokens:
        return None
    first = tokens[0]
    amount: Decimal | None = None
    unit = None
    used = 0
    attached = _AR_ATTACHED.fullmatch(_latin(first))
    if attached and _ar_unit(attached.group(2)) is not None:
        amount, unit, used = _dec(attached.group(1)), _ar_unit(attached.group(2)), 1
    elif (n := _number(first)) is not None:
        amount, used = n, 1
    elif (folded := fold_ar(first)) in AR_NUMBER_WORDS:
        amount, used = Decimal(AR_NUMBER_WORDS[folded]), 1
    elif folded in AR_FRACTION_WORDS:
        amount, used = AR_FRACTION_WORDS[folded], 1
    if amount is not None and used == 1 and unit is None and len(tokens) > 1:
        unit = _ar_unit(tokens[1])
        used += 1 if unit is not None else 0
    elif amount is None:
        unit = _ar_unit(first)
        if unit is None or unit.plural:
            return None  # a bare plural ("اكياس زبالة", "علب") is part of the product
        used = 1
    if unit is None:
        # a bare number or number word is a count; a bare fraction is not a quantity
        if amount is None or fold_ar(first) in AR_FRACTION_WORDS or trailing:
            return None
        if len(tokens) > 1 and tokens[1].startswith("%"):
            return None
        return min(amount, MAX_QUANTITY), None, used
    if unit.multiplier == 2 and amount is None:
        amount = Decimal(2)
    elif amount is None:
        amount = Decimal(1)
    # "and a half": "ونص", "و نص"
    if used < len(tokens):
        nxt = fold_ar(tokens[used])
        if nxt in _AR_HALVES:
            amount += AR_FRACTION_WORDS[_AR_HALVES[nxt]]
            used += 1
        elif (
            nxt == "و" and used + 1 < len(tokens) and fold_ar(tokens[used + 1]) in AR_FRACTION_WORDS
        ):
            amount += AR_FRACTION_WORDS[fold_ar(tokens[used + 1])]
            used += 2
    if unit.kind == "mass":
        if trailing and unit.factor < 1:
            return None  # "جبنة 250 غرام": a size of the product, as in the Hebrew rules
        return _cap(amount * unit.factor), "kg", used
    if unit.kind == "volume":
        if trailing:
            return None
        whole = amount * unit.factor
        packs = whole if unit.factor == 1 and whole == whole.to_integral_value() else Decimal(1)
        return _cap(packs), None, used
    if trailing and used == 1 and unit.multiplier == 1:
        return None  # a lone count noun ("تونة علبة") is part of the product when it trails
    return _cap(amount), None, used


_AR_COUNT_WORD = re.compile(rf"^(?:عدد\s*({_NUM})\s+(.+)|(.+?)\s+عدد\s*({_NUM}))$")


def parse_fragment_ar(raw: str) -> Fragment:
    """Quantity and product of one Arabic list line. See the module docstring."""
    s = " ".join(raw.split()).strip(_BIDI + " ")
    sd = _latin(s)
    m = _AR_COUNT_WORD.match(sd)  # "عدد 2" = a count of 2
    if m:
        amount = _dec(m.group(1) or m.group(4))
        if amount is not None:
            text = s[m.start(2) : m.end(2)] if m.group(2) else s[m.start(3) : m.end(3)]
            return Fragment(raw, text.strip(), _cap(amount))
    m = _AR_LEAD_MARK.match(sd)
    if m:
        amount = _dec(m.group(1) or m.group(2))
        if amount is not None:
            return Fragment(raw, s[m.start(3) : m.end(3)].strip(), _cap(amount))
    m = _AR_TRAIL_MARK.match(sd)
    if m:
        amount = _dec(m.group(2) or m.group(3))
        if amount is not None:
            return Fragment(raw, s[m.start(1) : m.end(1)].strip(), _cap(amount))
    tokens = s.split(" ")
    lead = _leading_quantity_ar(tokens)
    if lead is not None and lead[2] < len(tokens):
        qty, unit, used = lead
        return Fragment(raw, " ".join(tokens[used:]).strip(), qty, unit)
    for k in range(min(4, len(tokens) - 1), 0, -1):
        tail = _leading_quantity_ar(tokens[-k:], trailing=True)
        if tail is not None and tail[2] == k:
            qty, unit, _ = tail
            return Fragment(raw, " ".join(tokens[:-k]).strip(), qty, unit)
    return Fragment(raw, s)
