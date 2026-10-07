"""Rule-based attribute extraction from normalized names (issue #25, the no-key default).

Deterministic and free: keyword tables from ``data/product_type_rules.yaml`` pick the product
type, regexes read the fat percentage, keyword lists give state, flavor, kosher text and diet
flags, a brand list and per-chain private-label lists give the brand. It is the baseline the
model extractor is compared against, and the fallback when no API key is configured.

Every value it produces is unverified (only a human verifies), and its confidence is capped at
``MAX_CONFIDENCE`` so rule output never looks as sure as a reviewed value.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache

from smartcart_catalog.extract.base import Result
from smartcart_catalog.models import Attributes, ExtractionError, NormalizedItem
from smartcart_catalog.seed import Catalog, load_catalog

MAX_CONFIDENCE = 0.8
_HE = "א-ת"
_LETTER = rf"[{_HE}A-Za-z]"
_PREFIX = "בהולמש"

# --- vocabularies (initial lists; estimate, to be tuned on loaded data) -----------------------------

# Chain ids from decision D13. Only the chains' own names are listed: the house-brand names
# behind each chain still have to be collected from the loaded catalog.
PRIVATE_LABELS: dict[str, tuple[str, ...]] = {
    "7290027600007": ("שופרסל",),
    "7290058140886": ("רמי לוי", "שיווק השקמה"),
    "7290696200003": ("ויקטורי",),
    "7290058103393": ("ויקטורי",),
    "7290055700007": ("קרפור", "יינות ביתן", "carrefour"),
    "7290700100008": ("חצי חינם",),
    "7290873255550": ("טיב טעם",),
    "7290103152017": ("אושר עד",),
    "7290803800003": ("יוחננוף",),
    "7290661400001": ("מחסני השוק",),
    "7290633800006": ("מחסני השוק",),
    "7290058108879": ("קינג סטור",),
}

KNOWN_BRANDS: tuple[str, ...] = (
    "תנובה", "טרה", "שטראוס", "יטבתה", "גד", "דנונה", "יופלה", "מולר", "עמק", "נעם", "תרה",
    "אסם", "עלית", "תלמה", "סוגת", "וילי פוד", "פרי ניר", "יכין", "זוגלובק", "טירת צבי",
    "מאמא עוף", "עוף טוב", "מעדני מיקי", "נטו", "צבר", "אחלה", "שמיר", "מיה", "פרי הגליל",
    "תפוגן", "פריגת", "ספרינג", "קוקה קולה", "פפסי", "נביעות", "מי עדן", "עין גדי", "יעקבס",
    "נסקפה", "לנדוור", "ויסוצקי", "קליק", "במבה", "קרמבו", "מזולה", "יד מרדכי", "בית השיטה",
    "סנו", "פיירי", "פיניש", "טאץ'", "בדין", "לילי", "סופטלן", "מאיר", "ברמן", "אנג'ל",
    "דוידוביץ'", "סטארקיסט", "פילדלפיה", "קנור", "הלמנס", "היינץ", "ברילה", "פסטה זרה",
    "קלוגס", "תבליני פרג", "מגדל",
)

_FAT_EXCLUDE = ("קקאו", "שוקולד", "מיץ", "פרי", "אלכוהול", "יין", "בירה", "הנחה", "מבצע",
                "אחוז כוהל", "סיבים", "חלבון")
_FAT = re.compile(r"(\d+(?:\.\d+)?)\s*%")

_STATE_WORDS: tuple[tuple[str, str], ...] = (
    ("מוקפא", "frozen"), ("מוקפאת", "frozen"), ("מוקפאים", "frozen"), ("קפוא", "frozen"),
    ("קפואה", "frozen"), ("קפואים", "frozen"), ("קפואות", "frozen"),
    ("בשימורים", "canned"), ("שימורי", "canned"), ("שימורים", "canned"), ("פחית", "canned"),
    ("טרי", "fresh"), ("טריה", "fresh"), ("טרייה", "fresh"), ("טריים", "fresh"),
    ("טריות", "fresh"), ("מצונן", "chilled"), ("מקורר", "chilled"),
)

_FLAVOR_WORDS: tuple[tuple[str, str], ...] = (
    ("טבעי", "plain"), ("ללא תוספות", "plain"), ("תות", "strawberry"), ("אפרסק", "peach"),
    ("בננה", "banana"), ("שוקולד", "chocolate"), ("וניל", "vanilla"), ("קפה", "coffee"),
    ("לימון", "lemon"), ("תפוז", "orange"), ("תפוח", "apple"), ("ענבים", "grape"),
    ("פטל", "raspberry"), ("נענע", "mint"), ("דבש", "honey"), ("גריל", "grill"),
    ("בצל", "onion"), ("מלח", "salted"), ("ברביקיו", "barbecue"), ("חריף", "spicy"),
    ("גבינה", "cheese"), ("תפוחי אדמה", "potato"), ("עוף", "chicken"), ("בקר", "beef"),
    ("פטריות", "mushroom"), ("זיתים", "olive"), ("שום", "garlic"), ("צנובר", "pine_nut"),
    ("צנוברים", "pine_nut"),
)
_FLAVOR_BY_TYPE: dict[str, tuple[tuple[str, str], ...]] = {
    "chocolate_bar": (("מריר", "dark"), ("לבן", "white"), ("חלב", "milk")),
}
_EXTRA_INGREDIENT = re.compile(rf"(?<!{_LETTER})(?:עם|בתוספת|ממולא)(?!{_LETTER})")

# Plant drinks (issue #92): the base is critical (soy vs almond is never "any brand").
PLANT_DRINK_TYPES: frozenset[str] = frozenset(
    {"soy_drink", "almond_drink", "oat_drink", "rice_drink", "coconut_drink", "plant_drink"}
)
_BASE_WORDS: tuple[tuple[str, str], ...] = (
    ("שיבולת שועל", "oat"), ("שיבולת", "oat"), ("אוטלי", "oat"), ("oat", "oat"),
    ("סויה", "soy"), ("soy", "soy"), ("שקדים", "almond"), ("שקד", "almond"),
    ("almond", "almond"), ("אורז", "rice"), ("rice", "rice"), ("קוקוס", "coconut"),
    ("coconut", "coconut"),
)
_BASE_BY_TYPE: dict[str, str] = {
    "soy_drink": "soy", "almond_drink": "almond", "oat_drink": "oat", "rice_drink": "rice",
    "coconut_drink": "coconut",
}
_VARIETY_WORDS: tuple[tuple[str, str], ...] = (
    ("בריסטה", "barista"), ("ברסיטה", "barista"), ("barista", "barista"),
    ("חלבון", "protein"), ("protein", "protein"),
)

_KOSHER_WORDS: tuple[tuple[str, str], ...] = (
    ("כשר לפסח", "כשר לפסח"), ('בד"ץ', 'בד"ץ'), ("בדץ", 'בד"ץ'), ("מהדרין", "מהדרין"),
)
_DIET_WORDS: tuple[tuple[str, str], ...] = (
    ("ללא גלוטן", "gluten_free"), ("ללא לקטוז", "lactose_free"), ("דל לקטוז", "lactose_free"),
    ("ללא תוספת סוכר", "no_added_sugar"), ("ללא סוכר", "sugar_free"), ("טבעוני", "vegan"),
    ("צמחוני", "vegetarian"), ("אורגני", "organic"), ("דל נתרן", "low_sodium"),
)


@lru_cache(maxsize=8192)
def _word_re(word: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!{_LETTER})[{_PREFIX}]?{re.escape(word)}(?!{_LETTER})", re.IGNORECASE)


def _find(word: str, text: str) -> re.Match[str] | None:
    """``word`` as a whole word, optionally after one Hebrew prefix letter (ב, ה, ו, ...)."""
    return _word_re(word).search(text)


def _has(word: str, text: str) -> bool:
    return _find(word, text) is not None


class RuleExtractor:
    """``Extractor`` over keyword tables. Chain and manufacturer come from the item."""

    name = "rule"
    model: str | None = None

    def __init__(self, catalog: Catalog | None = None) -> None:
        self.catalog = catalog or load_catalog()
        # product_type -> taxonomy ids of its canonicals, and (type, state) -> id
        self._type_nodes: dict[str, set[str]] = {}
        self._type_state_node: dict[tuple[str, str], str] = {}
        for c in self.catalog.canonicals:
            self._type_nodes.setdefault(c.product_type, set()).add(c.taxonomy_id)
            state = c.critical_attrs.get("state")
            if state:
                self._type_state_node[(c.product_type, state)] = c.taxonomy_id

    # --- single attributes --------------------------------------------------------------------

    def product_type(self, name: str) -> str | None:
        best: tuple[int, str] | None = None
        for pt, extra in self.catalog.extras.items():
            if any(ex in name for ex in extra.exclude):
                continue
            for kw in extra.keywords:
                if _has(kw, name) and (best is None or len(kw) > best[0]):
                    best = (len(kw), pt)
        return best[1] if best else None

    def category_path(self, product_type: str | None, state: str | None) -> str | None:
        if product_type is None:
            return None
        if state and (product_type, state) in self._type_state_node:
            return self._type_state_node[(product_type, state)]
        nodes = sorted(self._type_nodes.get(product_type, ()))
        if not nodes:
            return None
        if len(nodes) == 1:
            return nodes[0]
        common = nodes[0].split(".")
        for other in nodes[1:]:
            parts = other.split(".")
            n = 0
            while n < min(len(common), len(parts)) and common[n] == parts[n]:
                n += 1
            common = common[:n]
        return ".".join(common) or None

    @staticmethod
    def fat_pct(name: str) -> Decimal | None:
        if any(word in name for word in _FAT_EXCLUDE):
            return None
        for m in _FAT.finditer(name):
            value = Decimal(m.group(1))
            if 0 <= value <= 100:
                return value
        return None

    @staticmethod
    def state(name: str) -> str | None:
        found = [(m.start(), st) for word, st in _STATE_WORDS if (m := _find(word, name))]
        return min(found)[1] if found else None

    @staticmethod
    def flavor(name: str, product_type: str | None) -> str | None:
        for table in (_FLAVOR_BY_TYPE.get(product_type or "", ()), _FLAVOR_WORDS):
            found = [(m.start(), fl) for word, fl in table if (m := _find(word, name))]
            if found:
                return min(found)[1]
        if _EXTRA_INGREDIENT.search(name):
            return "other"
        return None

    @staticmethod
    def base(name: str, product_type: str | None) -> str | None:
        """Plant-drink base, only for plant drink types: the first base word in the name, else
        the one the product type implies."""
        if product_type not in PLANT_DRINK_TYPES:
            return None
        found = [(m.start(), b) for word, b in _BASE_WORDS if (m := _find(word, name))]
        if found:
            return min(found)[1]
        return _BASE_BY_TYPE.get(product_type or "")

    @staticmethod
    def variety(name: str) -> str | None:
        found = [(m.start(), v) for word, v in _VARIETY_WORDS if (m := _find(word, name))]
        return min(found)[1] if found else None

    @staticmethod
    def kosher(name: str) -> str | None:
        for word, value in _KOSHER_WORDS:
            if word in name:
                return value
        return None

    @staticmethod
    def diet_flags(name: str) -> tuple[str, ...]:
        flags: list[str] = []
        for word, flag in _DIET_WORDS:
            if word in name and flag not in flags and not (
                flag == "sugar_free" and "no_added_sugar" in flags
            ):
                flags.append(flag)
        return tuple(flags)

    @staticmethod
    def brand(
        name: str, chain_id: str | None = None, manufacturer: str | None = None
    ) -> tuple[str | None, bool | None]:
        """``(brand, is_private_label)``. Private label needs the chain id."""
        texts = [name] + ([manufacturer] if manufacturer else [])
        if chain_id in PRIVATE_LABELS:
            for label in PRIVATE_LABELS[chain_id]:
                if any(_has(label, t) for t in texts):
                    return label, True
        for text in texts:
            hits = [(m.start(), b) for b in KNOWN_BRANDS if (m := _find(b, text))]
            if hits:
                return min(hits)[1], False
        return None, None

    # --- whole item ------------------------------------------------------------------------------

    def extract_one(self, item: NormalizedItem) -> Result:
        name = item.clean_name
        if not name.strip():
            return ExtractionError(item_id=item.item_id, reason="empty name", retryable=False)
        pt = self.product_type(name)
        extra = self.catalog.extras.get(pt) if pt else None
        implied = extra.implied if extra else {}
        rule = self.catalog.rules.get(pt) if pt else None
        keys = set(rule.critical_keys) | set(rule.soft_keys) if rule else set()

        state = self.state(name) or implied.get("state")
        flavor = self.flavor(name, pt) if (not rule or "flavor" in keys) else None
        if flavor is None and "flavor" in implied:
            flavor = implied["flavor"]
        brand, private = self.brand(name, item.chain_id, item.manufacturer)
        pack_size = None if item.is_weighed else item.total_quantity
        unit = None if item.is_weighed else item.unit

        confidence = 0.2 + (0.4 if pt else 0) + (0.1 if brand else 0) + (0.1 if pack_size else 0)
        return Attributes(
            category_path=self.category_path(pt, state),
            product_type=pt,
            brand=brand,
            is_private_label=private,
            fat_pct=self.fat_pct(name),
            state=state,
            flavor=flavor,
            kosher=self.kosher(name),
            diet_flags=self.diet_flags(name),
            pack_size=pack_size,
            unit=unit,
            base=self.base(name, pt) or implied.get("base"),
            variety=self.variety(name) or implied.get("variety"),
            verified_keys=(),
            confidence=round(min(confidence, MAX_CONFIDENCE), 2),
        )

    def extract(self, items: list[NormalizedItem]) -> list[Result]:
        return [self.extract_one(i) for i in items]
