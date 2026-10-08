"""Rule-based structuring of OCR text from a Hebrew supermarket receipt (issue #61).

Input is the receipt's text lines as an OCR engine or a vision model read them (pure strings, no
image, no network, no LLM). Output is a ``Receipt``: the chain (a GS1 company id, or None when
unsure), the branch text, the printed total and the item lines with quantity and price.

What is an item
---------------
* ``name  price`` (the price at either end, because RTL lines come out in either visual order);
* ``name`` on one line and the details on the next: ``2 X 5.90 11.80`` or ``0.532 ק"ג X 9.90 5.27``;
* ``name  2 X 5.90  11.80`` all on one line.

Quantities are counts (``2 X 5.90``) or weights in kg (``0.532 ק"ג``). A weight is only believed
with three decimals or next to a per-kg price, so a product size such as ``סוכר 1 ק"ג`` stays a
name. A count with the ``יח'`` marker is read only on a line without a name for the same reason
(``ביצים 12 יח'`` is a pack).

What is not an item: discount lines (``הנחה``, ``מבצע`` with a minus, ``קופון``; collected as
negative amounts), deposits (``פיקדון``), VAT, payment, change, totals, dates, branch, club and
fiscal lines. A name with no price and no detail line is dropped: precision over recall, and a
header line must not become a product.

OCR noise handled: bidi marks and stray punctuation, quote variants, ``O``/``l`` inside numbers, a
space inside a price (``8 .90``), a trailing minus (``2.00-``), thousands separators, and prices
printed in reversed digit order (``90.5`` for ``5.09``): a one-decimal price with a two digit
integer part is only reversed when that makes the item prices, discounts and the printed total add
up (``fix_reversed``); otherwise it stays as read.

Everything numeric is ``Decimal``. Accuracy numbers for this module are measured on synthetic
receipts only (docs/ocr.md).
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from smartcart_catalog.extract.rule import KNOWN_BRANDS
from smartcart_catalog.normalize import clean_name

D = Decimal

# --- chains (GS1 company ids as the transparency files carry them) --------------------------------

# id -> display name, aliases. Ids match services/ingest adapters and apps/web/.../chains.ts.
# "מגה" is the Mega brand of the same group as יינות ביתן (adapters/mega.py loads it under the
# Bitan id). Aliases shorter than six characters must match exactly; longer ones may be one letter off.
CHAINS: dict[str, tuple[str, tuple[str, ...]]] = {
    "7290027600007": ("שופרסל", ("שופרסל", "shufersal")),
    "7290058140886": ("רמי לוי", ("רמי לוי", "שיווק השקמה", "rami levy")),
    "7290696200003": ("ויקטורי", ("ויקטורי", "victory")),
    "7290055700007": ("יינות ביתן", ("יינות ביתן", "ביתן", "מגה", "mega")),
    "7290700100008": ("חצי חינם", ("חצי חינם", "hazi hinam")),
    "7290873255550": ("טיב טעם", ("טיב טעם", "tiv taam")),
    "7290103152017": ("אושר עד", ("אושר עד", "osher ad")),
    "7290803800003": ("יוחננוף", ("יוחננוף", "yochananof")),
    "7290661400001": ("מחסני השוק", ("מחסני השוק", "machsanei hashuk")),
    "7290058108879": ("קינג סטור", ("קינג סטור", "king store")),
}
HEADER_LINES = 12
FUZZY_RATIO = 0.83

# --- text cleanup ---------------------------------------------------------------------------------

_BIDI = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
     0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF], None
)
_JUNK = re.compile(r"[|_~¦\[\]{}<>=\\^]+")
_QUOTES = str.maketrans({"׳": "'", "`": "'", "’": "'", "‘": "'", "´": "'",
                         "״": '"', "”": '"', "“": '"', "\u00a0": " ", "₪": " "})
_HE = "א-ת"
_O_IN_NUMBER = re.compile(r"(?<=\d)[Oo](?=\d|[.,]\d)|(?<=[.,])[Oo](?=\d)|(?<=\d[.,]\d)[Oo](?![A-Za-z\d])")
_L_IN_NUMBER = re.compile(r"(?<=[\d.,])[Il|](?=\d)|(?<=\d)[Il](?=[.,]\d)")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}[.,]\d{2}(?!\d))")
_SHEKEL = re.compile(r'ש"ח|שח|nis|ils', re.IGNORECASE)


def clean_line(raw: str) -> str:
    s = raw.translate(_BIDI).translate(_QUOTES).replace("''", '"')
    s = _JUNK.sub(" ", s)
    s = _O_IN_NUMBER.sub("0", s)
    s = _L_IN_NUMBER.sub("1", s)
    s = _THOUSANDS.sub("", s)
    s = _SHEKEL.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip(" \t.,:;*#")


# --- numbers --------------------------------------------------------------------------------------

_SIZE_AFTER = r"(?!\s*(?:%|ל'|ליטר|מ\"ל|מל|גרם|גר'|ג'))"
_PRICE = re.compile(r"(?<![\d.,])(-?)\s?(\d{1,5})\s?[.,]\s?(\d{2})(?!\d)" + _SIZE_AFTER + r"(-?)")
_AMBIGUOUS = re.compile(r"(?<![\d.,])(-?)(\d{2})[.,](\d)(?![\d%])(-?)")
_WEIGHT3 = re.compile(r"(?<![\d.,])(\d{1,3})[.,](\d{3})(?!\d)")
_X = r"[xX×*@✕]"
_KG = r"(?:ק\"ג|קג|ק'ג|קילו(?:גרם)?|kg|KG|Kg)"
_COUNT_X_PRICE = re.compile(rf"(?<![\d.,])(\d{{1,3}})\s*{_X}\s*(\d{{1,4}}[.,]\d{{2}})(?!\d)")
_PRICE_X_COUNT = re.compile(rf"(?<![\d.,])(\d{{1,4}}[.,]\d{{2}})\s*{_X}\s*(\d{{1,3}})(?![\d.,]\d)(?!\d)")
_WEIGHT_X_PRICE = re.compile(
    rf"(?<![\d.,])(\d{{1,3}}(?:[.,]\d{{1,3}})?)\s*{_KG}?\s*{_X}\s*(\d{{1,4}}[.,]\d{{2}})(?!\d)"
)
_PER_KG_PRICE = re.compile(rf"(\d{{1,4}}[.,]\d{{2}})\s*(?:ל\s*-?\s*|/|\\)\s*{_KG}")
_WEIGHT_UNIT = re.compile(rf"(?<![\d.,])(\d{{1,3}}(?:[.,]\d{{1,3}})?)\s*{_KG}(?![{_HE}A-Za-z])")
_COUNT_UNITS = re.compile(r"(?<![\d.,])(\d{1,3})\s*(?:יח'?|יחידות|יחידה)(?![א-ת])")
_BARCODE = re.compile(r"(?<![\d.,])\d{6,14}(?![\d.,])")
_ITEM_NO = re.compile(r"^(?:\d{1,3}\s*[.)\-]\s+|0\d{1,3}\s+)")


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", ".").replace(" ", ""))
    except InvalidOperation:
        return None


def _reverse_price(whole: str, frac: str) -> Decimal | None:
    """``"90.5"`` read back to front is ``"5.09"``: two decimals, so a plausible price."""
    rev = f"{whole}.{frac}"[::-1]
    return _dec(rev) if re.fullmatch(r"\d\.\d{2}", rev) or re.fullmatch(r"\d{2}\.\d{2}", rev) else None


# --- result types ---------------------------------------------------------------------------------


@dataclass
class ReceiptItem:
    text: str  # the name after abbreviation expansion (what is matched against the catalog)
    raw: str  # the name as read, without prices and quantities
    quantity: Decimal | None = None  # a count, or kilograms when ``unit == "kg"``
    unit: str | None = None  # "kg" for weighed goods, else None
    price: Decimal | None = None  # the line total, ILS
    unit_price: Decimal | None = None
    price_alt: Decimal | None = field(default=None, repr=False)  # price with reversed digits


@dataclass
class Receipt:
    chain_id: str | None = None
    chain_name: str | None = None
    store_hint: str | None = None
    total: Decimal | None = None
    items: list[ReceiptItem] = field(default_factory=list)
    discounts: list[Decimal] = field(default_factory=list)  # negative amounts
    total_alt: Decimal | None = field(default=None, repr=False)
    reversed_fixed: int = 0  # prices whose digit order was corrected to make the sums add up


# --- name expansion -------------------------------------------------------------------------------

_P = rf"(?<![{_HE}A-Za-z])([בוהלמש]?)"
_END = rf"(?![{_HE}A-Za-z])"
RECEIPT_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    (_P + r"חל'" + _END, r"\1חלב"),
    (_P + r"גב'" + _END, r"\1גבינה"),
    (_P + r"גבינ'" + _END, r"\1גבינה"),
    (_P + r"שמנ'" + _END, r"\1שמנת"),
    (_P + r"יוג'" + _END, r"\1יוגורט"),
    (_P + r"ביצ'" + _END, r"\1ביצים"),
    (_P + r"עגב'" + _END, r"\1עגבניות"),
    (_P + r"עגבני'" + _END, r"\1עגבניות"),
    (_P + r"מלפ'" + _END, r"\1מלפפונים"),
    (_P + r"שוק'" + _END, r"\1שוקולד"),
    (_P + r"שוקו'" + _END, r"\1שוקולד"),
    (_P + r"שניצ'" + _END, r"\1שניצל"),
    (_P + r"פיל'" + _END, r"\1פילה"),
    (_P + r"משק'" + _END, r"\1משקה"),
    (_P + r"שימ'" + _END, r"\1שימורי"),
    (_P + r"תפוח\"א" + _END, r"\1תפוחי אדמה"),
    (_P + r"תפו\"א" + _END, r"\1תפוחי אדמה"),
    (_P + r"פלפ'" + _END, r"\1פלפל"),
    (_P + r"מיץ'" + _END, r"\1מיץ"),
    (_P + r"אבקת'" + _END, r"\1אבקת"),
    (_P + r"ק\.נמס" + _END, r"\1קפה נמס"),
    (_P + r"ס\.ש\." + _END, r"\1סוכר"),
    (_P + r"טחינ'" + _END, r"\1טחינה"),
    (_P + r"חומו'" + _END, r"\1חומוס"),
    (_P + r"קמ'" + _END, r"\1קמח"),
    (_P + r"סול'" + _END, r"\1סולת"),
    (_P + r"אורז'" + _END, r"\1אורז"),
    (_P + r"עוף'" + _END, r"\1עוף"),
    (_P + r"טבעי'" + _END, r"\1טבעי"),
    (_P + r"מוצר'" + _END, r"\1מוצרלה"),
    (_P + r"מוצ'" + _END, r"\1מוצרלה"),
    (_P + r"פתי'" + _END, r"\1פתיבר"),
    # a unit glued to its number: 1ל, 750מל, 500גר, 3 %
    (r"(?<=\d)\s*ל(?![א-ת\"'])", " ליטר"),
    (r"(?<=\d)\s*מל(?![א-ת])", " מיליליטר"),
    (r"(?<=\d)\s*גר(?![א-ת])", " גרם"),
    (r"(?<=\d)\s+%", "%"),
)
_ABBR = tuple((re.compile(p), r) for p, r in RECEIPT_ABBREVIATIONS)


def expand_name(raw: str) -> str:
    """The receipt's shortened name as a catalog query: abbreviations and units expanded."""
    s = clean_name(raw.translate(_QUOTES))
    for pattern, repl in _ABBR:
        s = pattern.sub(repl, s)
    s = re.sub(r"\s+", " ", s).strip(" .,:;-*'\"")
    return clean_name(s)


_SIZE = re.compile(
    r"(?<![\d.,])\d+(?:[.,]\d+)?\s*(?:קילוגרם|גרם|ליטר|מיליליטר|יחידות|יחידה|מ\"ל|ק\"ג)(?![א-ת])"
    r"|(?<![\d.,])\d+\s*[xX×]\s*\d+(?:[.,]\d+)?"
)
_BRAND_WORDS = tuple(sorted({b for b in KNOWN_BRANDS}, key=len, reverse=True))


def query_variants(text: str) -> list[str]:
    """The expanded name, then the name without pack sizes, then without sizes and brands.

    A receipt prints brand and size ("חלב תנובה 3% 1 ליטר") and the catalog asks for neither at
    the "any brand" level. The caller resolves every variant and keeps the best; the fat
    percentage is never removed because it is a critical attribute. A variant that would be
    empty is not offered.
    """
    out = [text]
    no_size = re.sub(r"\s+", " ", _SIZE.sub(" ", text)).strip()
    if no_size and no_size != text:
        out.append(no_size)
    words = no_size or text
    for brand in _BRAND_WORDS:
        pattern = rf"(?<![{_HE}A-Za-z])[בוהלמש]?{re.escape(brand)}(?![{_HE}A-Za-z])"
        words = re.sub(pattern, " ", words)
    words = re.sub(r"\s+", " ", words).strip()
    if words and words not in out and _is_name(words):
        out.append(words)
    return out


# --- chain, branch --------------------------------------------------------------------------------

_NON_WORD = re.compile(r"[^\w\s]|_", re.UNICODE)


def _tokens(s: str) -> list[str]:
    return _NON_WORD.sub(" ", s.lower()).split()


def _alias_in(tokens: list[str], alias: str, *, fuzzy: bool) -> bool:
    a = _tokens(alias)
    n = len(a)
    if n == 0 or len(tokens) < n:
        return False
    target = " ".join(a)
    for i in range(len(tokens) - n + 1):
        window = " ".join(tokens[i : i + n])
        if window == target:
            return True
        # a one-letter Hebrew prefix glued to the name: "בשופרסל" (in Shufersal)
        first = tokens[i]
        if len(a[0]) >= 4 and len(first) == len(a[0]) + 1 and first[0] in "בהלמוש":
            if " ".join([first[1:], *tokens[i + 1 : i + n]]) == target:
                return True
        if fuzzy and len(target) >= 6 and SequenceMatcher(None, window, target).ratio() >= FUZZY_RATIO:
            return True
    return False


def detect_chain(lines: list[str]) -> tuple[str | None, str | None]:
    """(GS1 chain id, Hebrew name) from the header words; (None, None) when absent or ambiguous.

    The first ``HEADER_LINES`` lines may match one letter off. If the header names no chain, any
    line may name one exactly (a footer such as "תודה שקניתם בשופרסל"). Two different chains
    matching at the same stage is no answer.
    """
    stages = (
        (_tokens(" ".join(lines[:HEADER_LINES])), True),
        (_tokens(" ".join(lines)), False),
    )
    for tokens, fuzzy in stages:
        found = [
            cid for cid, (_, aliases) in CHAINS.items()
            if any(_alias_in(tokens, alias, fuzzy=fuzzy) for alias in aliases)
        ]
        if len(found) == 1:
            return found[0], CHAINS[found[0]][0]
        if len(found) > 1:
            return None, None
    return None, None


_BRANCH = re.compile(r"סניף\s*[:\-]?\s*(.+)")


def detect_branch(lines: list[str]) -> str | None:
    for line in lines[:HEADER_LINES + 6]:
        m = _BRANCH.search(line)
        if m:
            text = re.sub(r"[\d\s:\-.,]+$", "", m.group(1)).strip()
            text = re.sub(r"^[\d\s:\-.,]+", "", text).strip()
            if 2 <= len(text) <= 60 and re.search(rf"[{_HE}A-Za-z]{{2}}", text):
                return text
    return None


# --- line classes ---------------------------------------------------------------------------------

_TOTAL_STRONG = re.compile(r"לתשלום|סה\"כ\s*לתשלום|סכום\s*לתשלום|total\s*due", re.IGNORECASE)
_TOTAL_WEAK = re.compile(r"סה\"כ|סהכ|סך\s*הכל|סה כ|total", re.IGNORECASE)
_NOT_TOTAL = re.compile(
    r"פריטים|מוצרים|כמות|הנחה|הנחות|חיסכון|חסכת|מע\"מ|מעמ|לפני|פיקדון|נקודות|עודף|שורות|מבצע",
)
_DISCOUNT = re.compile(r"הנחה|הנחת|הטבה|חיסכון|קופון|זיכוי|ניכוי|הנח'")
_SKIP = re.compile(
    r"מע\"מ|מעמ|אשראי|מזומן|ויזה|visa|מאסטרקארד|mastercard|ישראכרט|דיינרס|אמריקן|כרטיס|עודף|חשבונית|"
    r"קבלה|טלפון|טל[.:']|פקס|ח\.פ|ח\"פ|עוסק|תאריך|שעה|קופה|קופאי|סניף|מועדון|חבר\b|נקודות|תודה|"
    r"אישור|הקצאה|תשלום|תשלומים|פיקדון|בע\"מ|רחוב|רח'|כתובת|שאלות|אתר|www|\.co\.il|@|החזרה|החלפה|"
    r"אחריות|ת\.ד|מספר\s*עסקה|עסקה|מס'\s*ספק",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b|\b\d{1,2}:\d{2}\b")
_VALID_NAME = re.compile(rf"[{_HE}]{{2}}|[A-Za-z]{{3}}")


def _price_tokens(line: str) -> list[tuple[int, int, Decimal, bool, Decimal | None]]:
    """(start, end, value, negative, reversed-digits alternative) for each price in ``line``."""
    out = []
    for m in _PRICE.finditer(line):
        value = _dec(f"{m.group(2)}.{m.group(3)}")
        if value is None:
            continue
        out.append((m.start(), m.end(), value, bool(m.group(1) or m.group(4)), None))
    stripped = line.strip()
    for m in _AMBIGUOUS.finditer(line):
        at_edge = m.start() <= len(line) - len(line.lstrip()) or m.end() >= len(line.rstrip())
        # only a token at the end of the line, not part of a name ("קפה 12.5 גרם")
        if not at_edge or not stripped:
            continue
        if any(s <= m.start() < e for s, e, *_ in out):
            continue
        read = _dec(f"{m.group(2)}.{m.group(3)}0")
        alt = _reverse_price(m.group(2), m.group(3))
        if read is not None and alt is not None:
            out.append((m.start(), m.end(), read, bool(m.group(1) or m.group(4)), alt))
    out.sort()
    return out


def _blank(line: str, spans: list[tuple[int, int]]) -> str:
    chars = list(line)
    for s, e in spans:
        for i in range(s, e):
            chars[i] = " "
    return "".join(chars)


def _tidy_name(s: str) -> str:
    s = _BARCODE.sub(" ", s)
    s = _ITEM_NO.sub("", s.strip())
    s = re.sub(rf"(?<![{_HE}A-Za-z\d])[xX×*@✕-](?![{_HE}A-Za-z\d])", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,:;-*#()")


@dataclass
class _Parsed:
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    price: Decimal | None = None
    price_alt: Decimal | None = None
    has_qty_expr: bool = False


def _parse_detail(line: str) -> _Parsed:
    """Split a line into name, quantity expression and prices. The name may be empty."""
    spans: list[tuple[int, int]] = []
    p = _Parsed("")
    named = bool(_VALID_NAME.search(
        _COUNT_UNITS.sub(" ", _PRICE.sub(" ", _WEIGHT_UNIT.sub(" ", line)))
    ))

    def grab(m: re.Match[str]) -> None:
        spans.append((m.start(), m.end()))

    pk = _PER_KG_PRICE.search(line)
    if pk:
        p.unit_price = _dec(pk.group(1))
        grab(pk)
    w = _WEIGHT_X_PRICE.search(line)
    if w and (_WEIGHT3.fullmatch(w.group(1)) or _kg_near(line, w)):
        qty = _dec(w.group(1))
        if qty is not None and 0 < qty < 100:
            p.quantity, p.unit, p.unit_price, p.has_qty_expr = qty, "kg", _dec(w.group(2)), True
            grab(w)
    if p.quantity is None:
        wu = _WEIGHT_UNIT.search(line)
        w3 = _WEIGHT3.search(line)
        per_kg = p.unit_price is not None
        if wu and (_WEIGHT3.fullmatch(wu.group(1)) or per_kg):
            qty = _dec(wu.group(1))
            if qty is not None and 0 < qty < 100:
                p.quantity, p.unit, p.has_qty_expr = qty, "kg", True
                grab(wu)
        elif w3 and (per_kg or not named):
            qty = _dec(f"{w3.group(1)}.{w3.group(2)}")
            if qty is not None and qty > 0:
                p.quantity, p.unit, p.has_qty_expr = qty, "kg", True
                grab(w3)
    if p.quantity is None:
        c = _COUNT_X_PRICE.search(line)
        r = _PRICE_X_COUNT.search(line)
        if c:
            p.quantity, p.unit_price, p.has_qty_expr = _dec(c.group(1)), _dec(c.group(2)), True
            grab(c)
        elif r:
            p.quantity, p.unit_price, p.has_qty_expr = _dec(r.group(2)), _dec(r.group(1)), True
            grab(r)
        elif not named:
            cu = _COUNT_UNITS.search(line)
            if cu:
                p.quantity, p.has_qty_expr = _dec(cu.group(1)), True
                grab(cu)
    if p.quantity is not None and p.unit is None and not (0 < p.quantity <= 99):
        p.quantity, p.has_qty_expr = None, False
    rest = _blank(line, spans)
    tokens = [t for t in _price_tokens(rest) if t[2] != p.unit_price or p.unit_price is None]
    if tokens:
        # the line total is the last price on the line (or the first, printed in visual order);
        # with a unit price already known, any price equal to it is the unit price echoed
        last = tokens[-1]
        p.price, p.price_alt = last[2], last[4]
        spans.extend((t[0], t[1]) for t in tokens)
    p.name = _tidy_name(_blank(line, spans))
    if p.quantity is not None and p.unit_price is not None and p.price is None:
        p.price = (p.quantity * p.unit_price).quantize(D("0.01"))
    return p


def _kg_near(line: str, m: re.Match[str]) -> bool:
    return bool(re.match(rf"\s*{_KG}", line[m.start(1) + len(m.group(1)) :]))


# --- the parser -----------------------------------------------------------------------------------


def _is_name(name: str) -> bool:
    return bool(_VALID_NAME.search(name))


def parse_receipt(lines: list[str]) -> Receipt:
    """Structure the OCR lines of one receipt."""
    cleaned = [c for c in (clean_line(x) for x in lines) if c]
    receipt = Receipt()
    receipt.chain_id, receipt.chain_name = detect_chain(cleaned)
    receipt.store_hint = detect_branch(cleaned)

    strong: tuple[Decimal, Decimal | None] | None = None
    weak: tuple[Decimal, Decimal | None] | None = None
    pending: _Parsed | None = None
    last: ReceiptItem | None = None
    discounts: list[tuple[Decimal, Decimal | None]] = []

    def finish(p: _Parsed) -> ReceiptItem | None:
        if not _is_name(p.name) or p.price is None:
            return None
        item = ReceiptItem(
            text=expand_name(p.name), raw=p.name, quantity=p.quantity, unit=p.unit,
            price=p.price, unit_price=p.unit_price, price_alt=p.price_alt,
        )
        return item if _is_name(item.text) else None

    for line in cleaned:
        tokens = _price_tokens(line)
        # totals
        if (_TOTAL_STRONG.search(line) or _TOTAL_WEAK.search(line)) and not _NOT_TOTAL.search(line):
            if tokens:
                value, alt = tokens[-1][2], tokens[-1][4]
                if _TOTAL_STRONG.search(line):
                    strong = (value, alt)
                else:
                    weak = (value, alt)
            pending = None
            continue
        # discounts and credits: negative amounts, never items
        if _DISCOUNT.search(line) or (
            tokens and any(t[3] for t in tokens) and not _is_name(_blank(line, [(t[0], t[1]) for t in tokens]))
        ) or (re.match(r"\s*מבצע", line) and tokens):
            if tokens and not re.search(r"סה\"כ|סהכ", line):
                discounts.append((-abs(tokens[-1][2]), tokens[-1][4]))
            pending = None
            continue
        if _SKIP.search(line) or _DATE.search(line):
            pending = None
            continue
        if tokens and any(t[3] for t in tokens):  # a negative amount on a named line: a credit
            discounts.append((-abs(tokens[-1][2]), tokens[-1][4]))
            pending = None
            continue

        p = _parse_detail(line)
        if _is_name(p.name):
            if p.price is not None:
                item = finish(p)
                if item:
                    receipt.items.append(item)
                    last, pending = item, None
                else:
                    pending = None
            else:
                pending = p
            continue
        # a detail line: quantity and/or price without a name
        if pending is not None:
            pending.quantity, pending.unit = p.quantity or pending.quantity, p.unit or pending.unit
            pending.unit_price = p.unit_price or pending.unit_price
            pending.price, pending.price_alt = p.price or pending.price, p.price_alt or pending.price_alt
            if pending.price is None and pending.quantity and pending.unit_price:
                pending.price = (pending.quantity * pending.unit_price).quantize(D("0.01"))
            item = finish(pending)
            if item:
                receipt.items.append(item)
                last = item
            pending = None
        elif last is not None and p.has_qty_expr and last.quantity is None:
            last.quantity, last.unit, last.unit_price = p.quantity, p.unit, p.unit_price
            if p.price is not None and last.price is None:
                last.price = p.price

    chosen = strong or weak
    if chosen:
        receipt.total, receipt.total_alt = chosen
    receipt.discounts = [d for d, _ in discounts]
    fix_reversed(receipt, discounts)
    return receipt


def fix_reversed(receipt: Receipt, discounts: list[tuple[Decimal, Decimal | None]]) -> None:
    """Flip prices printed in reversed digit order when that makes the receipt add up.

    Only prices that have an alternative (a one-decimal price with a two digit integer part) are
    candidates, at most eight of them, and only when the receipt has a printed total that the
    prices as read do not reproduce. The smallest set of flips that reproduces it wins; if none
    does, everything stays as read.
    """
    if receipt.total is None or not receipt.items:
        return
    tolerance = D("0.06")

    def balanced(total: Decimal, prices: list[Decimal], disc: list[Decimal]) -> bool:
        return abs(sum(prices, D(0)) + sum(disc, D(0)) - total) <= tolerance

    prices = [i.price for i in receipt.items if i.price is not None]
    disc = [d for d, _ in discounts]
    if balanced(receipt.total, prices, disc):
        return
    slots: list[tuple[str, int]] = []
    for idx, item in enumerate(receipt.items):
        if item.price is not None and item.price_alt is not None:
            slots.append(("item", idx))
    for idx, (_, alt) in enumerate(discounts):
        if alt is not None:
            slots.append(("disc", idx))
    if receipt.total_alt is not None:
        slots.append(("total", 0))
    if not slots or len(slots) > 8:
        return
    for size in range(1, len(slots) + 1):
        for combo in itertools.combinations(slots, size):
            p = [i.price for i in receipt.items if i.price is not None]
            item_pos = [k for k, i in enumerate(receipt.items) if i.price is not None]
            d2 = list(disc)
            total = receipt.total
            for kind, idx in combo:
                if kind == "item":
                    p[item_pos.index(idx)] = receipt.items[idx].price_alt  # type: ignore[assignment]
                elif kind == "disc":
                    d2[idx] = -(discounts[idx][1] or D(0))
                else:
                    total = receipt.total_alt  # type: ignore[assignment]
            if total is not None and balanced(total, p, d2):
                for kind, idx in combo:
                    if kind == "item":
                        receipt.items[idx].price = receipt.items[idx].price_alt
                    elif kind == "disc":
                        receipt.discounts[idx] = d2[idx]
                    else:
                        receipt.total = receipt.total_alt
                receipt.reversed_fixed = len(combo)
                return
