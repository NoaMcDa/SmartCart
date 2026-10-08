"""Rule-based Hebrew recipe parser: recipe text or a recipe page to ingredient amounts (issue #71).

The parser reads a recipe and returns, per ingredient line, the product text to search for and
the amount in grams, milliliters, pieces or packs. It does not touch the database: the API
(``POST /parse-recipe``) resolves each ingredient through the ``/parse-list`` matcher and turns
the amount into a basket quantity with :func:`basket_quantity`.

Sources, in order of trust:

* a recipe page's JSON-LD ``Recipe`` (schema.org ``recipeIngredient``, ``recipeYield``, ``name``),
  :func:`recipe_from_html`;
* else the page's visible text, read only below an ingredients header ("מצרכים", "רכיבים") and
  above the method header ("אופן ההכנה"): without the header nothing is read (a page has too
  much other text to guess from);
* pasted text, :func:`parse_recipe_text`: the same sections when the headers are there, else
  every short line, the first line without an amount being the title.

Ingredient lines (:func:`parse_ingredient`):

* amounts: integers, decimals (``1.5``, ``1,5``), fractions (``1/2``, ``1 1/2``, ``½``, ``1½``),
  Hebrew words (``חצי``, ``רבע``, ``שליש``, ``שתי``, ``כוס וחצי``, ``2 וחצי``), ranges
  (``2-3``, ``2 עד 3``: the upper bound, so the list buys enough), approximations (``כ-200``);
* units: grams and kilograms; milliliters and liters; a cup is 240 ml, a spoon 15 ml, a teaspoon
  5 ml (the Israeli kitchen convention, an estimate); packs (``חבילה``, ``גביע``, ``קופסה``,
  ``פחית``...) count purchasable packs; pieces (``יחידות``, ``צרור``, ``שן``, ``ראש``) count
  pieces;
* a weight in parentheses (``1 בצל גדול (כ-200 גרם)``) replaces a piece count;
* the product text drops preparation words (``קצוץ``, ``מומסת``, ``גדולים``), what follows a
  comma, parenthetical remarks and the second of two alternatives (``חמאה או מרגרינה``), and
  common recipe words are mapped to the catalog's names (``ביצה`` to ``ביצים L``, ``בצל`` to
  ``בצל יבש``; :data:`ALIASES`).

Precision over recall (D5): a line goes to ``unresolved`` instead of the list when it is not a
supermarket product (tap water, ice), when it has no amount and says "to taste" or "as needed"
(``מלח לפי הטעם``, ``קורט``, ``שמן לטיגון``), or when it is optional (``לא חובה``). The API adds
lines whose product the matcher cannot find. Nothing is dropped silently.

Unit conversion to the canonical's base unit (:func:`basket_quantity`): volume to mass and back
through :data:`GRAMS_PER_CUP`, a per-ingredient density table for staples, pieces to kilograms
through :data:`PIECE_GRAMS` for produce. Every number in both tables is a kitchen estimate, not a
measurement. When a conversion is unknown the row keeps one pack (or one kilogram) and asks the
user to confirm; it never invents an amount silently.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from typing import Any, Literal

Dim = Literal["g", "ml", "piece", "pack"]

CUP_ML = Decimal(240)
TBSP_ML = Decimal(15)
TSP_ML = Decimal(5)
MAX_PACKS = Decimal(99)

# Hebrew number words that may open an amount.
_WORD_NUM: dict[str, Decimal] = {
    "חצי": Decimal("0.5"), "רבע": Decimal("0.25"), "שליש": Decimal(1) / 3,
    "אחד": Decimal(1), "אחת": Decimal(1), "שני": Decimal(2), "שתי": Decimal(2),
    "שניים": Decimal(2), "שתיים": Decimal(2), "שלוש": Decimal(3), "שלושה": Decimal(3),
    "ארבע": Decimal(4), "ארבעה": Decimal(4), "חמש": Decimal(5), "חמישה": Decimal(5),
    "שש": Decimal(6), "שישה": Decimal(6), "שבע": Decimal(7), "שבעה": Decimal(7),
    "שמונה": Decimal(8), "תשע": Decimal(9), "תשעה": Decimal(9), "עשר": Decimal(10),
    "עשרה": Decimal(10), "תריסר": Decimal(12),
}
_VULGAR = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3", "⅛": "1/8", "⅕": "1/5"}

# unit word -> (dimension, factor to that dimension's base: g, ml, piece or pack)
_UNIT_TABLE: dict[str, tuple[Dim, Decimal]] = {}


def _units(dim: Dim, factor: Decimal | int, *words: str) -> None:
    for w in words:
        _UNIT_TABLE[w] = (dim, Decimal(factor))


_units("g", 1, "גרם", "גרמים", "גר'", "גר", "ג'", "ג", "g", "gr")
_units("g", 1000, 'ק"ג', "ק״ג", "קג", "קילו", "קילוגרם", "kg")
_units("ml", 1, 'מ"ל', "מ״ל", "מל", "מיליליטר", "ml")
_units("ml", 1000, "ליטר", "ליטרים", "ל'", "l")
_units("ml", CUP_ML, "כוס", "כוסות")
_units("ml", TBSP_ML, "כף", "כפות")
_units("ml", TSP_ML, "כפית", "כפיות")
_units(
    "pack", 1, "חבילה", "חבילות", "חבילת", "אריזה", "אריזות", "אריזת", "שקית", "שקיות", "קופסה",
    "קופסא", "קופסת", "קופסאות", "פחית", "פחיות", "גביע", "גביעים", "בקבוק", "בקבוקים",
    "צנצנת", "צנצנות", "קרטון", "קרטונים", "מגש", "מגשים", "חפיסה", "חפיסת", "חפיסות",
    "שקיק", "שקיקים", "מיכל", "מיכלים",
)
_units(
    "piece", 1, "יחידה", "יחידות", "יח'", "יח", "צרור", "צרורות", "צרור", "אגודה", "אגודת",
    "ראש", "ראשי", "שן", "שיני", "שיניים", "פרוסה", "פרוסות", "ענף", "ענפי", "ענפים", "עלה",
    "עלי", "עלים",
)
# Pieces that are a known fraction of the product: one garlic clove is about 5 g of garlic.
# Every piece unit except "יחידה" is loose: three slices of cheese are not three packs.
_PACK_LIKE_PIECES = frozenset({"יחידה", "יחידות", "יח'", "יח"})
_PIECE_UNIT_GRAMS = {"שן": Decimal(5), "שיני": Decimal(5), "שיניים": Decimal(5)}
_SIZE_WORDS = ("גדושה", "גדושות", "שטוחה", "שטוחות", "מלאה", "מלאות", "גדולה", "גדולות",
               "קטנה", "קטנות")

# Grams in one 240 ml cup, for converting cups and spoons to grams and back (estimates from
# common kitchen conversion tables; not measured). Keys match the start of the product text
# or the canonical's name, longest first.
GRAMS_PER_CUP: dict[str, Decimal] = {k: Decimal(v) for k, v in {
    "קמח": 140, "קמח לבן": 140, "קמח מלא": 130, "קמח תופח": 140, "קמח כוסמין": 130,
    "סוכר": 200, "סוכר לבן": 200, "סוכר חום": 200, "אבקת סוכר": 120, "סוכר וניל": 190,
    "אורז": 200, "קוסקוס": 180, "פתיתים": 180, "בורגול": 180, "קינואה": 180, "עדשים": 200,
    "גרגרי חומוס": 200, "חומוס יבש": 200, "שעועית": 190, "שיבולת שועל": 90, "פירורי לחם": 120,
    "קורנפלקס": 30, "גרנולה": 110, "מלח": 290, "אבקת אפייה": 230, "סודה לשתייה": 230,
    "שמרים": 145, "שמרים יבשים": 145, "פפריקה": 110, "כמון": 100, "כורכום": 145,
    "פלפל שחור": 110, "קפה נמס": 96, "קפה": 80, "גבינה מגורדת": 100, "גבינה צהובה": 100,
    "גבינה לבנה": 240, "שמנת חמוצה": 240, "יוגורט": 245, "קוטג'": 225, "לבנה": 240,
    "חמאה": 227, "מרגרינה": 227, "טחינה": 240, "דבש": 340, "סילאן": 330, "ריבה": 320,
    "ריבת": 320, "חמאת בוטנים": 258, "ממרח שוקולד": 300, "מיונז": 220, "קטשופ": 240,
    "רסק עגבניות": 260, "חרדל": 250, "זיתים": 135, "תירס": 165, "אפונה": 145,
    "שמן": 218, "שמן זית": 216, "שמן קנולה": 218,
}.items()}
# Grams of one piece of produce bought by the kilogram (estimates of a medium piece).
PIECE_GRAMS: dict[str, Decimal] = {k: Decimal(v) for k, v in {
    "בצל": 150, "בצלים": 150, "בצל יבש": 150, "בצל סגול": 150, "עגבניה": 130, "עגבנייה": 130,
    "עגבניות": 130, "עגבניות שרי": 15, "מלפפון": 100, "מלפפונים": 100, "תפוח אדמה": 200,
    "תפוחי אדמה": 200, "גזר": 100, "גזרים": 100, "פלפל": 150, "פלפלים": 150, "פלפל אדום": 150,
    "לימון": 100, "לימונים": 100, "אבוקדו": 200, "תפוח עץ": 180, "תפוחי עץ": 180, "תפוח": 180,
    "תפוחים": 180, "בננה": 120, "בננות": 120, "חציל": 300, "חצילים": 300, "קישוא": 200,
    "קישואים": 200, "בטטה": 300, "בטטות": 300, "שום": 50, "תפוז": 200, "תפוזים": 200,
    "קלמנטינה": 80, "קלמנטינות": 80, "אגס": 180, "אגסים": 180, "מנגו": 300, "כרוב": 1000,
    "כרובית": 800, "ברוקולי": 400,
}.items()}
# Recipe words to the catalog's names (whole product text, after cleanup).
ALIASES: dict[str, str] = {
    "קמח": "קמח לבן", "קמח רגיל": "קמח לבן", "קמח חיטה": "קמח לבן", "סוכר": "סוכר לבן",
    "סוכר רגיל": "סוכר לבן", "ביצה": "ביצים L", "ביצים": "ביצים L", "חלמון": "ביצים L",
    "חלמונים": "ביצים L", "חלבון": "ביצים L", "חלבונים": "ביצים L", "בצל": "בצל יבש",
    "בצלים": "בצל יבש", "בצל לבן": "בצל יבש", "עגבניה": "עגבניות", "עגבנייה": "עגבניות",
    "מלפפון": "מלפפונים", "תפוח אדמה": "תפוחי אדמה", "גזרים": "גזר", "לימון": "לימונים",
    "חציל": "חצילים", "קישוא": "קישואים", "בטטות": "בטטה",
    "תפוז": "תפוזים", "בננה": "בננות", "תפוח עץ": "תפוחי עץ ירוקים", "אגס": "אגסים",
    "פלפל אדום": "פלפל אדום", "פלפלים אדומים": "פלפל אדום", "גבינה צהובה מגורדת": "גבינה מגורדת",
    "מוצרלה מגורדת": "גבינה מגורדת", "שמנת לקצפת": "שמנת מתוקה", "רסק": "רסק עגבניות",
    "שמרים": "שמרים יבשים", "שמן צמחי": "שמן קנולה", "פטרוזיליה קצוצה": "פטרוזיליה",
    "שיני שום": "שום", "ראש שום": "שום", "שן שום": "שום", "טחינה": "טחינה גולמית",
    "טחינה גולמית": "טחינה גולמית", "יוגורט": "יוגורט טבעי", "יוגורט טבעי": "יוגורט טבעי",
    "פפריקה": "פפריקה מתוקה", "כרעיים עוף": "כרעיים עוף טריים", "חזה עוף": "חזה עוף טרי",
}
# Not supermarket products in a recipe: tap water and ice.
NOT_PRODUCTS = frozenset({
    "מים", "מים רותחים", "מים חמים", "מים קרים", "מים פושרים", "מים קרים מאוד", "מים מהברז",
    "מי ברז", "קרח", "קוביות קרח", "מים חמימים",
})
# "To taste" and "as needed": unresolved when the line gives no amount.
_TO_TASTE = re.compile(
    r"לפי\s+ה?טעם|לפי\s+הצורך|כפי\s+הצורך|לפי\s+הרצון|^קורט\b|\bקורט\b|^מעט\b|\bמעט\b|\bקצת\b"
    r"|\bלטיגון\b|\bלקישוט\b|\bלהגשה\b|\bלשימון\b|\bלציפוי\b|\bלפיזור\b|\bלהברשה\b"
    r"|\bלמריחה\b|^מלח\s+ו?פלפל\b"
)
# Optional ingredients: always left to the user.
_OPTIONAL = re.compile(r"לא\s+חובה|אופציונלי|\bרשות\b|\bאפשר\s+גם\b")
# Preparation and size words dropped from the product text.
_PREP_WORDS = frozenset({
    "קצוץ", "קצוצה", "קצוצים", "קצוצות", "חתוך", "חתוכה", "חתוכים", "חתוכות", "קלוף", "קלופה",
    "קלופים", "קלופות", "מקולף", "מקולפת", "מקולפים", "מקולפות", "מומס", "מומסת", "מומסים",
    "רך", "רכה", "רכים", "מרוכך", "מרוככת", "גדול", "גדולה", "גדולים", "גדולות", "בינוני",
    "בינונית", "בינוניים", "בינוניות", "קטן", "קטנה", "קטנים", "קטנות", "דק", "דקה", "גס",
    "גסה", "שטוף", "שטופה", "שטופים", "מסונן", "מסוננים", "מסוננת", "מושרים", "מושרה",
    "מגורען", "בערך", "כתוש", "כתושה", "כתושים", "מעוך", "מעוכה", "סחוט", "סחוטה", "טרייה",
    "טריים", "טריות", "לקוביות", "לרצועות", "לטבעות", "לפרוסות", "לחצאים", "לרבעים", "היטב",
    "מוקצף", "קר", "קרה", "קרים", "בטמפרטורת", "החדר", "של", "כתושות", "בשל", "בשלה",
    "בשלים", "בשלות", "גרוס", "גרוסה", "מנופה", "מנופים", "מסוננות", "קלויים", "קלויה",
    "קלוי", "מוכן", "מוכנה", "מגורדים", "מעוכים",
})
_INGREDIENT_HEADER = re.compile(r"^(?:ה)?(?:מצרכים|רכיבים|מרכיבים|חומרים)(?:\s.*)?:?$")
_METHOD_HEADER = re.compile(
    r"^(?:אופן\s+ה?הכנה|הוראות\s+ה?הכנה|דרך\s+ה?הכנה|שלבי\s+ה?הכנה|ה?הכנה|מהלך\s+ה?הכנה)\b"
)
_SERVINGS = re.compile(
    r"(?:(?:מספר\s+)?מנות|סועדים|כמות)\s*[:\-]?\s*(\d{1,3})(?!\d)"
    r"|(?:ל[-־]?\s*)?(\d{1,3})\s*(?:מנות|סועדים|אנשים|איש)\b"
)
_BULLET = re.compile(r"^\s*(?:[-–—•·▪*◦●○]+|\d{1,2}[.)](?=\s))\s*")
_NUMBER = r"\d+(?:[.,]\d+)?(?:\s+\d+\s*/\s*\d+)?|\d+\s*/\s*\d+"
_AMOUNT = re.compile(
    rf"^(?:כ[-־]?\s*|בערך\s+|~\s*)?({_NUMBER})(?:\s*(?:-|–|עד|או)\s*({_NUMBER}))?(?=\s|$|[א-ת])"
)
_PAREN = re.compile(r"\(([^)]*)\)")
_PAREN_WEIGHT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(ק\"ג|ק״ג|קג|קילו|גרם|גר'|גר|ג')")
_TRAILING = re.compile(r"^(.+?)\s*[-–:]\s*(\S.*)$")


@dataclass(frozen=True)
class Ingredient:
    """One ingredient line. ``amount`` is in ``dim``: grams, milliliters, pieces or packs."""

    line: str
    name: str
    amount: Decimal | None = None
    dim: Dim | None = None
    piece_grams: Decimal | None = None  # grams of one piece when the unit says so (a clove)
    loose: bool = False  # pieces that are not packs (slices, leaves, cloves, bunches)


@dataclass
class Recipe:
    title: str | None = None
    servings: int | None = None
    ingredients: list[Ingredient] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Unresolved:
    line: str
    reason: Literal["not_a_product", "to_taste", "optional", "no_product"]


# --- numbers -------------------------------------------------------------------------------------


def _number(s: str) -> Decimal | None:
    s = s.strip().replace(",", ".")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)?\s*(?:(\d+)\s*/\s*(\d+))?", s)
    if not m or not (m.group(1) or m.group(2)):
        return None
    whole = Decimal(m.group(1)) if m.group(1) else Decimal(0)
    if m.group(2):
        den = Decimal(m.group(3))
        if den == 0:
            return None
        whole += Decimal(m.group(2)) / den
    return whole if whole > 0 else None


def _vulgar(s: str) -> str:
    """``1½`` -> ``1 1/2``, ``½`` -> ``1/2``."""
    for ch, frac in _VULGAR.items():
        s = re.sub(rf"(\d)\s*{ch}", rf"\1 {frac}", s)
        s = s.replace(ch, frac)
    return s.replace("⁄", "/")


def _take_half(rest: str, amount: Decimal) -> tuple[str, Decimal]:
    """``וחצי`` / ``ורבע`` after an amount or a unit."""
    m = re.match(r"^\s*ו(חצי|רבע)\b\s*", rest)
    if not m:
        return rest, amount
    return rest[m.end():], amount + (Decimal("0.5") if m.group(1) == "חצי" else Decimal("0.25"))


def _take_unit(rest: str) -> tuple[str, tuple[Dim, Decimal] | None, str | None]:
    words = rest.split()
    if not words:
        return rest, None, None
    w = words[0].rstrip(".,:")
    unit = _UNIT_TABLE.get(w)
    if unit is None:
        return rest, None, None
    rest = " ".join(words[1:])
    while rest.split()[:1] and rest.split()[0] in _SIZE_WORDS:
        rest = " ".join(rest.split()[1:])
    return rest, unit, w


# --- one ingredient line -------------------------------------------------------------------------


def clean_name(name: str) -> str:
    """The product text: no remarks, no preparation words, the first alternative, aliased."""
    s = _PAREN.sub(" ", name)
    s = re.split(r"[,;]|\s\+\s", s, maxsplit=1)[0]
    s = re.split(r"\s+או\s+|\s*/\s*", s, maxsplit=1)[0]
    s = re.sub(r"^(?:של|מ)\s+", "", s.strip())
    words = [w.strip(".:!-–") for w in s.split()]
    words = [w for w in words if w and w not in _PREP_WORDS]
    s = " ".join(words)
    s = re.sub(r"\s+(?:ל|ב)?(?:עוד|נוסף|נוספת|נוספים)$", "", s)
    return ALIASES.get(s, s)


def _lookup(table: dict[str, Decimal], *names: str) -> Decimal | None:
    for name in names:
        if not name:
            continue
        for key in sorted(table, key=len, reverse=True):
            if name == key or name.startswith(key + " "):
                return table[key]
    return None


def parse_ingredient(line: str) -> Ingredient | Unresolved | None:
    """One ingredient line; None for an empty line or a sub-header (``לבצק:``)."""
    raw = _BULLET.sub("", " ".join(html.unescape(line).split())).strip()
    s = raw
    if not s or s.endswith(":"):
        return None
    s = _vulgar(s)
    if _OPTIONAL.search(s):
        return Unresolved(raw, "optional")
    paren = " ".join(_PAREN.findall(s))
    body = _PAREN.sub(" ", s).strip()

    amount: Decimal | None = None
    unit: tuple[Dim, Decimal] | None = None
    unit_word: str | None = None
    rest = body
    m = _AMOUNT.match(rest)
    if m:
        low, high = _number(m.group(1)), _number(m.group(2)) if m.group(2) else None
        amount = max(x for x in (low, high) if x is not None) if (low or high) else None
        rest = rest[m.end():]
        rest, amount = _take_half(rest, amount) if amount is not None else (rest, amount)
        rest, unit, unit_word = _take_unit(rest)
        if unit is not None and amount is not None:
            rest, amount = _take_half(rest, amount)  # "1 כוס וחצי"
    else:
        first, _, after = rest.partition(" ")
        if first in _WORD_NUM:
            amount = _WORD_NUM[first]
            rest, amount = _take_half(after, amount)
            rest, unit, unit_word = _take_unit(rest)
            if unit is not None:
                rest, amount = _take_half(rest, amount)
        else:
            rest2, unit, unit_word = _take_unit(rest)
            if unit is not None:  # "כוס קמח", "כוס וחצי קמח", "כף אחת שמן"
                amount = Decimal(1)
                rest2, amount = _take_half(rest2, amount)
                w0, _, w_rest = rest2.partition(" ")
                if w0 in ("אחד", "אחת"):
                    rest2 = w_rest
                rest = rest2
    if amount is None:
        # "קמח - 2 כוסות", "גבינה לבנה: 250 גרם"
        t = _TRAILING.match(body)
        if t:
            parsed = parse_ingredient(f"{t.group(2)} {t.group(1)}")
            if isinstance(parsed, Ingredient) and parsed.amount is not None:
                return replace(parsed, line=raw)
    name = clean_name(rest)
    if not name:
        return Unresolved(raw, "no_product")
    if name in NOT_PRODUCTS or clean_name(body) in NOT_PRODUCTS:
        return Unresolved(raw, "not_a_product")
    if _TO_TASTE.search(s):
        if amount is None:
            return Unresolved(raw, "to_taste")
        name = clean_name(_TO_TASTE.sub(" ", rest))
        if not name:
            return Unresolved(raw, "to_taste")

    dim: Dim | None = None
    piece_grams: Decimal | None = None
    loose = False
    if amount is None and _PAREN_WEIGHT.search(paren):
        amount = Decimal(1)  # "בצל גדול (כ-200 גרם)": one piece of that weight
    if amount is not None:
        if unit is None:
            dim = "piece"
        else:
            dim, factor = unit
            amount = amount * factor
            if unit_word in _PIECE_UNIT_GRAMS:
                piece_grams = _PIECE_UNIT_GRAMS[unit_word]
            loose = dim == "piece" and unit_word not in _PACK_LIKE_PIECES
        if dim == "piece":
            w = _PAREN_WEIGHT.search(paren)
            if w:  # "1 בצל גדול (כ-200 גרם)": the weight is more useful than the count
                grams = Decimal(w.group(1).replace(",", "."))
                if w.group(2) in ('ק"ג', "ק״ג", "קג", "קילו"):
                    grams *= 1000
                amount, dim, piece_grams, loose = grams * amount, "g", None, False
    return Ingredient(raw, name, amount, dim, piece_grams, loose)


# --- whole recipes -------------------------------------------------------------------------------


def parse_servings(value: Any) -> int | None:
    """``recipeYield`` or a servings line: ``4``, ``"4 מנות"``, ``["6", "6 servings"]``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        n = int(value)
        return n if 0 < n <= 100 else None
    if isinstance(value, list):
        for v in value:
            n = parse_servings(v)
            if n:
                return n
        return None
    if not isinstance(value, str):
        return None
    m = _SERVINGS.search(value)
    if m:
        n = int(m.group(1) or m.group(2))
        return n if 0 < n <= 100 else None
    m = re.search(r"\d{1,3}", value)
    if m and re.fullmatch(r"\s*\d{1,3}\s*(?:servings?|portions?|people|מנות|סועדים)?\s*", value, re.I):
        n = int(m.group(0))
        return n if 0 < n <= 100 else None
    return None


def _lines(text: str) -> list[str]:
    return [" ".join(x.split()) for x in text.replace("\r", "\n").split("\n")]


def _is_header(line: str, pattern: re.Pattern[str]) -> bool:
    return len(line.split()) <= 4 and bool(pattern.match(line.strip(" :-–")))


def parse_recipe_text(text: str, *, require_header: bool = False) -> Recipe:
    """A pasted Hebrew recipe. ``require_header`` (pages): read nothing without "מצרכים"."""
    lines = _lines(text)
    recipe = Recipe(servings=None)
    for ln in lines:
        recipe.servings = recipe.servings or (parse_servings(ln) if _SERVINGS.search(ln) else None)
    start = next((i for i, ln in enumerate(lines) if _is_header(ln, _INGREDIENT_HEADER)), None)
    if start is None and require_header:
        return recipe
    begin = 0 if start is None else start + 1
    end = next(
        (i for i, ln in enumerate(lines) if i >= begin and _is_header(ln, _METHOD_HEADER)),
        len(lines),
    )
    if start is not None:
        recipe.title = next(
            (ln for ln in lines[:start] if ln and not _SERVINGS.search(ln) and len(ln.split()) <= 10),
            None,
        )
    candidates = [ln for ln in lines[begin:end] if ln]
    if start is None and candidates:
        first = parse_ingredient(candidates[0])
        if not (isinstance(first, Ingredient) and first.amount is not None):
            recipe.title = candidates[0] if len(candidates[0].split()) <= 10 else None
            candidates = candidates[1:]
    limit = 12 if start is not None else 6
    for ln in candidates:
        if _SERVINGS.search(ln) and parse_servings(ln):
            continue
        if _INGREDIENT_HEADER.match(ln.strip(" :-–")) and len(ln.split()) <= 4:
            continue
        parsed = parse_ingredient(ln)
        if parsed is None:
            continue
        if isinstance(parsed, Ingredient) and parsed.amount is None and len(ln.split()) > limit // 2:
            continue  # prose, not an ingredient
        if len(ln.split()) > limit:
            continue
        if isinstance(parsed, Unresolved):
            recipe.unresolved.append(parsed.line)
        else:
            recipe.ingredients.append(parsed)
    return recipe


class _TextAndScripts(HTMLParser):
    """Visible text with line breaks at block elements, JSON-LD blocks, and the title."""

    _BLOCK = frozenset({"p", "li", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "ul",
                        "ol", "section", "article", "header", "footer", "td", "dt", "dd"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.jsonld: list[str] = []
        self.title: str | None = None
        self.og_title: str | None = None
        self._skip = 0
        self._in_jsonld = False
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower().startswith("application/ld+json"):
            self._in_jsonld, self._buf = True, []
        elif tag in ("script", "style", "noscript", "template", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_title, self._buf = True, []
        elif tag == "meta" and (a.get("property") or "").lower() == "og:title":
            self.og_title = (a.get("content") or "").strip() or None
        if tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._buf))
            self._in_jsonld = False
        elif tag in ("script", "style", "noscript", "template", "svg"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title" and self._in_title:
            self.title = " ".join("".join(self._buf).split()) or None
            self._in_title = False
        if tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_jsonld or self._in_title:
            self._buf.append(data)
        elif not self._skip:
            self.parts.append(data)


def _walk_jsonld(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for x in node:
            yield from _walk_jsonld(x)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if "Recipe" in types:
            yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk_jsonld(node[key])


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split()) or None
    return None


def recipe_from_jsonld(blocks: Iterable[str]) -> Recipe | None:
    for block in blocks:
        try:
            data = json.loads(block.strip())
        except (ValueError, TypeError):
            continue
        for node in _walk_jsonld(data):
            ingredients = node.get("recipeIngredient") or node.get("ingredients") or []
            if isinstance(ingredients, str):
                ingredients = [ingredients]
            recipe = Recipe(title=_text(node.get("name")), servings=parse_servings(node.get("recipeYield")))
            for raw in ingredients:
                line = _text(raw)
                if not line:
                    continue
                parsed = parse_ingredient(line)
                if isinstance(parsed, Unresolved):
                    recipe.unresolved.append(parsed.line)
                elif parsed is not None:
                    recipe.ingredients.append(parsed)
            if recipe.ingredients or recipe.unresolved:
                return recipe
    return None


def recipe_from_html(page: str) -> Recipe:
    """JSON-LD ``Recipe`` first, else the visible text under an ingredients header."""
    parser = _TextAndScripts()
    parser.feed(page)
    parser.close()
    found = recipe_from_jsonld(parser.jsonld)
    if found is not None:
        return found
    recipe = parse_recipe_text("".join(parser.parts), require_header=True)
    recipe.title = parser.og_title or parser.title or recipe.title
    return recipe


def scale(recipe: Recipe, servings: int | None) -> tuple[Recipe, int | None]:
    """Scale amounts to ``servings`` when the recipe's own yield is known.

    Returns the recipe and the servings its amounts are for: the requested number when scaled,
    the recipe's own yield when nothing was requested, None when either is unknown.
    """
    if servings is None or recipe.servings is None:
        return recipe, recipe.servings if servings is None else None
    factor = Decimal(servings) / Decimal(recipe.servings)
    scaled = [
        replace(i, amount=i.amount * factor) if i.amount is not None else i
        for i in recipe.ingredients
    ]
    return replace(recipe, ingredients=scaled), servings


# --- amounts to basket quantities ----------------------------------------------------------------


@dataclass(frozen=True)
class BasketQuantity:
    """A basket row's quantity: packs, or kilograms when ``unit == "kg"``."""

    quantity: Decimal
    unit: Literal["kg"] | None
    converted: bool  # False: the amount could not be converted and the row needs confirmation


def _ceil(x: Decimal, step: Decimal = Decimal(1)) -> Decimal:
    return (x / step).to_integral_value(rounding=ROUND_CEILING) * step


def _packs(amount: Decimal, pack: Decimal | None) -> tuple[Decimal, bool]:
    if pack is None or pack <= 0:
        return Decimal(1), False
    return min(max(_ceil(amount / pack), Decimal(1)), MAX_PACKS), True


def _density(name: str, canonical_name: str | None) -> Decimal | None:
    per_cup = _lookup(GRAMS_PER_CUP, name, canonical_name or "")
    return per_cup / CUP_ML if per_cup is not None else None


def basket_quantity(
    ing: Ingredient,
    base_unit: str,
    pack_size: Decimal | None = None,
    pack_unit: str | None = None,
    canonical_name: str | None = None,
) -> BasketQuantity:
    """The quantity the basket needs for ``ing`` under a canonical with ``base_unit``.

    * ``kg`` (sold by weight): kilograms, rounded up to 50 g; pieces through
      :data:`PIECE_GRAMS`; a volume through :data:`GRAMS_PER_CUP`.
    * ``100g`` / ``100ml`` / ``unit``: whole packs of the canonical's typical ``pack_size``
      (``soft_attrs.pack_size`` in g, ml or units), rounded up; a pack count is kept as it is.
    * No amount: one pack (or one kilogram), as ``/parse-list`` does for a bare product name.
    * An amount that cannot be converted keeps one pack (or one kilogram) with
      ``converted = False``: the caller asks the user to confirm.
    """
    amount, dim = ing.amount, ing.dim
    kg = base_unit == "kg"
    if amount is None or dim is None:
        return BasketQuantity(Decimal(1), "kg" if kg else None, True)
    if dim == "pack":
        return BasketQuantity(min(_ceil(amount), MAX_PACKS), "kg" if kg else None, not kg)
    # Everything else goes through grams, milliliters or pieces.
    grams: Decimal | None = None
    ml: Decimal | None = None
    pieces: Decimal | None = None
    density = _density(ing.name, canonical_name)
    if dim == "g":
        grams = amount
        ml = amount / density if density else None
    elif dim == "ml":
        ml = amount
        grams = amount * density if density else None
    else:
        pieces = amount
        each = ing.piece_grams or _lookup(PIECE_GRAMS, ing.name, canonical_name or "")
        grams = amount * each if each else None
    if kg:
        if grams is None:
            return BasketQuantity(Decimal(1), "kg", False)
        kilos = _ceil(grams / 1000, Decimal("0.05"))
        return BasketQuantity(max(kilos, Decimal("0.05")).quantize(Decimal("0.01"), ROUND_HALF_UP), "kg", True)
    unit = (pack_unit or {"100g": "g", "100ml": "ml", "unit": "unit"}.get(base_unit, "")).lower()
    if base_unit == "unit" or unit == "unit":
        if pieces is None:
            return BasketQuantity(Decimal(1), None, False)
        if base_unit == "unit" and unit != "unit":
            return BasketQuantity(min(_ceil(pieces), MAX_PACKS), None, True)
        q, ok = _packs(pieces, pack_size)
        return BasketQuantity(q if ok else min(_ceil(pieces), MAX_PACKS), None, True)
    if pieces is not None and not ing.loose:
        # "2 חמאה", "1 שמנת מתוקה": a bare count of a packaged product counts packs.
        return BasketQuantity(min(_ceil(pieces), MAX_PACKS), None, True)
    if ml is None and grams is not None and unit == "ml" and dim == "g":
        ml = grams  # a liquid given by weight: water-like density 1 (estimate)
    have = grams if unit == "g" else ml if unit == "ml" else None
    if have is None:
        return BasketQuantity(Decimal(1), None, False)
    q, ok = _packs(have, pack_size)
    return BasketQuantity(q, None, ok)


def merge(ingredients: Iterable[Ingredient]) -> list[Ingredient]:
    """Same product text and dimension twice (eggs in the dough and for brushing): one line."""
    out: list[Ingredient] = []
    index: dict[tuple[str, str | None, Decimal | None, bool], int] = {}
    for ing in ingredients:
        key = (ing.name, ing.dim, ing.piece_grams, ing.loose)
        at = index.get(key)
        if at is not None and out[at].amount is not None and ing.amount is not None:
            prev = out[at]
            out[at] = replace(prev, line=f"{prev.line} + {ing.line}", amount=prev.amount + ing.amount)
            continue
        index.setdefault(key, len(out))
        out.append(ing)
    return out
