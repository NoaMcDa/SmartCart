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
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

MAX_QUANTITY = Decimal(99)

_SEPARATORS = re.compile(r"[\n\r,;،؛]+|(?:^|\s)[•·▪\-–*]\s+")
_VAV_SPLIT = re.compile(r"\s+ו(?=[א-ת])")
_NUM = r"\d+(?:[.,]\d+)?"
_WORD_NUMBERS = {
    "שני": 2, "שתי": 2, "שניים": 2, "שתיים": 2, "שלוש": 3, "שלושה": 3, "ארבע": 4, "ארבעה": 4,
    "חמש": 5, "חמישה": 5, "שש": 6, "שישה": 6, "שבע": 7, "שבעה": 7, "שמונה": 8, "תשע": 9,
    "תשעה": 9, "עשר": 10, "עשרה": 10,
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
    parts = [p.strip(" \t.-–•·▪*") for p in _SEPARATORS.split(text)]
    return [p for p in parts if p]


def split_vav(fragment: str) -> list[str]:
    """``"חלב ולחם"`` -> ``["חלב", "לחם"]``; no change without a `` ו`` boundary."""
    parts = _VAV_SPLIT.split(fragment)
    return [p.strip() for p in parts if p.strip()]


def _dec(s: str) -> Decimal | None:
    try:
        d = Decimal(s.replace(",", "."))
    except InvalidOperation:
        return None
    return d if 0 < d <= 10_000 else None


def parse_fragment(raw: str) -> Fragment:
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
