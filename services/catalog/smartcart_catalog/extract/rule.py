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
from smartcart_catalog.kosher import read_marks, render
from smartcart_catalog.models import Attributes, ExtractionError, NormalizedItem
from smartcart_catalog.normalize import is_full_width, is_truncated
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
    "תנובה",
    "טרה",
    "שטראוס",
    "יטבתה",
    "גד",
    "דנונה",
    "יופלה",
    "מולר",
    "עמק",
    "נעם",
    "תרה",
    "אסם",
    "עלית",
    "תלמה",
    "סוגת",
    "וילי פוד",
    "פרי ניר",
    "יכין",
    "זוגלובק",
    "טירת צבי",
    "מאמא עוף",
    "עוף טוב",
    "מעדני מיקי",
    "נטו",
    "צבר",
    "אחלה",
    "שמיר",
    "מיה",
    "פרי הגליל",
    "תפוגן",
    "פריגת",
    "ספרינג",
    "קוקה קולה",
    "פפסי",
    "נביעות",
    "מי עדן",
    "עין גדי",
    "יעקבס",
    "נסקפה",
    "לנדוור",
    "ויסוצקי",
    "קליק",
    "במבה",
    "קרמבו",
    "מזולה",
    "יד מרדכי",
    "בית השיטה",
    "סנו",
    "פיירי",
    "פיניש",
    "טאץ'",
    "בדין",
    "לילי",
    "סופטלן",
    "מאיר",
    "ברמן",
    "אנג'ל",
    "דוידוביץ'",
    "סטארקיסט",
    "פילדלפיה",
    "קנור",
    "הלמנס",
    "היינץ",
    "ברילה",
    "פסטה זרה",
    "קלוגס",
    "תבליני פרג",
    "מגדל",
)

_FAT_EXCLUDE = (
    "קקאו",
    "שוקולד",
    "מיץ",
    "פרי",
    "אלכוהול",
    "יין",
    "בירה",
    "הנחה",
    "מבצע",
    "אחוז כוהל",
    "סיבים",
    "חלבון",
)
_FAT = re.compile(r"(\d+(?:\.\d+)?)\s*%")

_STATE_WORDS: tuple[tuple[str, str], ...] = (
    ("מוקפא", "frozen"),
    ("מוקפאת", "frozen"),
    ("מוקפאים", "frozen"),
    ("קפוא", "frozen"),
    ("קפואה", "frozen"),
    ("קפואים", "frozen"),
    ("קפואות", "frozen"),
    ("בשימורים", "canned"),
    ("שימורי", "canned"),
    ("שימורים", "canned"),
    ("פחית", "canned"),
    ("טרי", "fresh"),
    ("טריה", "fresh"),
    ("טרייה", "fresh"),
    ("טריים", "fresh"),
    ("טריות", "fresh"),
    ("מצונן", "chilled"),
    ("מקורר", "chilled"),
)

_FLAVOR_WORDS: tuple[tuple[str, str], ...] = (
    ("טבעי", "plain"),
    ("ללא תוספות", "plain"),
    ("תות", "strawberry"),
    ("אפרסק", "peach"),
    ("בננה", "banana"),
    ("שוקולד", "chocolate"),
    ("וניל", "vanilla"),
    ("קפה", "coffee"),
    ("לימון", "lemon"),
    ("תפוז", "orange"),
    ("תפוח", "apple"),
    ("ענבים", "grape"),
    ("פטל", "raspberry"),
    ("נענע", "mint"),
    ("דבש", "honey"),
    ("גריל", "grill"),
    ("בצל", "onion"),
    ("מלח", "salted"),
    ("ברביקיו", "barbecue"),
    ("חריף", "spicy"),
    ("גבינה", "cheese"),
    ("תפוחי אדמה", "potato"),
    ("עוף", "chicken"),
    ("בקר", "beef"),
    ("פטריות", "mushroom"),
    ("זיתים", "olive"),
    ("שום", "garlic"),
    ("צנובר", "pine_nut"),
    ("צנוברים", "pine_nut"),
)
_FLAVOR_BY_TYPE: dict[str, tuple[tuple[str, str], ...]] = {
    "chocolate_bar": (("מריר", "dark"), ("לבן", "white"), ("חלב", "milk")),
}
# Flavor words that are the product itself or too common to make a bar a different bar.
_NOT_A_SECOND_FLAVOR = frozenset({"chocolate", "plain", "milk", "dark", "white"})
_EXTRA_INGREDIENT = re.compile(rf"(?<!{_LETTER})(?:עם|בתוספת|ממולא)(?!{_LETTER})")

# Plant drinks (issues #92, #102): the base is a critical key of the plant drink types, so soy
# vs almond is never "any brand" even when the product type was guessed wrong.
PLANT_DRINK_TYPES: frozenset[str] = frozenset(
    {"soy_drink", "almond_drink", "oat_drink", "rice_drink", "coconut_drink", "plant_drink",
     "plant_yogurt"}
)  # fmt: skip
_BASE_WORDS: tuple[tuple[str, str], ...] = (
    ("שיבולת שועל", "oat"),
    ("שיבולת", "oat"),
    ("אוטלי", "oat"),
    ("oat", "oat"),
    ("סויה", "soy"),
    ("סוייה", "soy"),
    ("soy", "soy"),
    ("שקדים", "almond"),
    ("שקד", "almond"),
    ("almond", "almond"),
    ("אורז", "rice"),
    ("rice", "rice"),
    ("קוקוס", "coconut"),
    ("coconut", "coconut"),
)
# A name with no product type still gets a base when it says it is a drink, a "milk" or a
# yogurt made from one ("משקה אורז", "חלב קוקוס"): the base then vetoes the plant drink
# canonicals it is not. A base word right after "בטעם" is a flavor ("בטעם קוקוס"), not a base.
_BASE_CUES: tuple[str, ...] = ("משקה", "חלב", "יוגורט", "מעדן", "תחליף חלב")
_FLAVOR_MARKER = re.compile(rf"(?<!{_LETTER})בטעם\s+$")
_BASE_BY_TYPE: dict[str, str] = {
    "soy_drink": "soy",
    "almond_drink": "almond",
    "oat_drink": "oat",
    "rice_drink": "rice",
    "coconut_drink": "coconut",
}
_VARIETY_WORDS: tuple[tuple[str, str], ...] = (
    ("בריסטה", "barista"),
    ("ברסיטה", "barista"),
    ("barista", "barista"),
    ("חלבון", "protein"),
    ("protein", "protein"),
)

_DIET_WORDS: tuple[tuple[str, str], ...] = (
    ("ללא גלוטן", "gluten_free"),
    ("ללא לקטוז", "lactose_free"),
    ("דל לקטוז", "lactose_free"),
    ("ללא תוספת סוכר", "no_added_sugar"),
    ("ללא סוכר", "sugar_free"),
    ("טבעוני", "vegan"),
    ("צמחוני", "vegetarian"),
    ("אורגני", "organic"),
    ("דל נתרן", "low_sodium"),
)


# --- eggs (docs/matching.md, "Eggs") ---------------------------------------------------------------
# The three size canonicals and the free-range one are told apart by product type, and the size
# word is not always next to "ביצים" ("ביצים 2*30 יח' בינונ", "תבנית ביצים 30 יח' L"), so the type
# of an egg name is decided from the whole name. Only a name that states exactly one size gets a
# size type; every other egg gets the generic ``eggs``, which no canonical has, so the judge vetoes
# it for every egg canonical: an egg of unknown size is never served as L.
EGG_TYPES = frozenset({"eggs_l", "eggs_m", "eggs_xl", "eggs_free_range_l"})
EGG_GENERIC = "eggs"
_EGG_WORD = re.compile(rf"(?<!{_LETTER})[{_PREFIX}]?(?:ביצים|ביצי|ביצה)(?!{_LETTER})")
# not an egg to eat: noodles, a chocolate egg, mayonnaise, a cake, egg-free products...
_EGG_NOT_FOOD = (
    "אטריות", "קינדר", "שוקולד", "עוגה", "עוגת", "עוגי", "מיונז", "סלט", "ממרח", "פסטה", "לחם",
    "חלה", "בייגל", "ללא ביצ", "אבקת", "חלבון", "חלמון", "קמח", "פתיתים", "כריך", "סנדוויץ'",
    "רוטב", "מרק", "חביתה", "שניצל", "פשטידה", "בצק", "תחליף", "הפתעה", "צעצוע", "קישוט", "קרם",
    "גלידה", "שמפו", "סבון", "פיצה", "מקרוני", "לביבות", "מאפה", "איטריות", "נודלס", "פורס",
    "חותך", "כדור תה", "נירוסטה", "ביצי דג", "ביצי דגים", "דגים", "איקרה", "קוויאר", "ליקר",
    "משחק", "גומי", "פריזר", "נטוראה", "מעדן", "מגירת", "פתיתי", "טליאטלה",
)  # fmt: skip
# an egg, but not what the size canonicals mean: quail, duck, hard-boiled, organic, omega-3, small...
_EGG_OTHER_KIND = (
    "שליו", "ברווז", "אווז", "קשות", "קשה", "מבושל", "אורגני", "אומגה", "מועשר", "נוזלי",
    "מפוסטר", "קטנות", "קטנים", "קטנה",
)  # fmt: skip
# Spellings seen on real names: M, בינוני, בינונ (cut), בנוני (typo), מידיום; L, גדול, גודל L, לארג'
_EGG_XL = re.compile(
    rf"(?<![A-Za-z])XL(?![A-Za-z])|(?<!{_LETTER})ענק\w*|(?<!{_LETTER})גדול\w*\s+(?:מאוד|במיוחד)"
    rf"|(?<!{_LETTER})אקס\s*לארג"
)
_EGG_L = re.compile(rf"(?<![A-Za-z])L(?![A-Za-z])|(?<!{_LETTER})גדול\w*|(?<!{_LETTER})לארג")
_EGG_M = re.compile(rf"(?<![A-Za-z])M(?![A-Za-z])|(?<!{_LETTER})(?:בינו|בנוני|מ[י]?דיום)\w*")
_EGG_CUT_SIZE = re.compile(r"(?:בינו|גדול|ענק)\w*$")


def egg_product_type(name: str, *, cut_tail: str = "") -> str | None:
    """The egg product type of a name: ``eggs_l`` / ``eggs_m`` / ``eggs_xl`` / ``eggs_free_range_l``
    when the name states exactly one size (free range only with size L), ``eggs`` for any other egg,
    ``None`` when the name is not an egg to eat. ``cut_tail`` is the last word of a name the chain
    cut; it is read only when it starts like a size word ("בינונ")."""
    if not _EGG_WORD.search(name) or any(w in name for w in _EGG_NOT_FOOD):
        return None
    text = f"{name} {cut_tail}" if cut_tail and _EGG_CUT_SIZE.match(cut_tail) else name
    if any(w in text for w in _EGG_OTHER_KIND):
        return EGG_GENERIC
    sizes: set[str] = set()
    if _EGG_XL.search(text):
        sizes.add("XL")
        text = _EGG_XL.sub(" ", text)  # the plain "גדולות" of "גדולות מאוד" is not a second size
    if _EGG_L.search(text):
        sizes.add("L")
    if _EGG_M.search(text):
        sizes.add("M")
    if len(sizes) != 1:
        return EGG_GENERIC
    size = next(iter(sizes))
    if "חופש" in text:
        return "eggs_free_range_l" if size == "L" else EGG_GENERIC
    return {"L": "eggs_l", "M": "eggs_m", "XL": "eggs_xl"}[size]


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
        if product_type == EGG_GENERIC:
            return "dairy.eggs.chicken"
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
        by_type = _FLAVOR_BY_TYPE.get(product_type or "", ())
        for table in (by_type, _FLAVOR_WORDS):
            found = [(m.start(), fl) for word, fl in table if (m := _find(word, name))]
            if found:
                value = min(found)[1]
                if table is by_type:
                    # "dark chocolate with sea salt" is not the plain dark bar: a second flavor
                    # (or an "עם ..." filling) makes a compound value that no plain canonical has.
                    extra = sorted(
                        {
                            fl
                            for word, fl in _FLAVOR_WORDS
                            if fl not in _NOT_A_SECOND_FLAVOR and _find(word, name)
                        }
                    )
                    if extra:
                        value += "+" + "+".join(extra)
                    elif _EXTRA_INGREDIENT.search(name):
                        value += "+other"
                return value
        if _EXTRA_INGREDIENT.search(name):
            return "other"
        return None

    @staticmethod
    def base(name: str, product_type: str | None) -> str | None:
        """Plant base (soy, almond, oat, rice, coconut): the first base word in the name that
        is not a flavor ("בטעם קוקוס"), else the one the product type implies. Only for plant
        drink types, or for an untyped name that says it is a drink, a "milk" or a yogurt."""
        if product_type is None:
            if not any(_has(cue, name) for cue in _BASE_CUES):
                return None
        elif product_type not in PLANT_DRINK_TYPES:
            return None
        found = []
        for word, b in _BASE_WORDS:
            for m in _word_re(word).finditer(name):
                if not _FLAVOR_MARKER.search(name[: m.start()]):
                    found.append((m.start(), b))
                    break
        if found:
            return min(found)[1]
        return _BASE_BY_TYPE.get(product_type or "")

    @staticmethod
    def variety(name: str) -> str | None:
        found = [(m.start(), v) for word, v in _VARIETY_WORDS if (m := _find(word, name))]
        return min(found)[1] if found else None

    @staticmethod
    def kosher(name: str) -> str | None:
        """What the name states about kashrut, explicit words only (``smartcart_catalog.kosher``):
        the stated marks as text ('בד"ץ, כשר לפסח'), or None. Never inferred from a brand."""
        return render(read_marks(name))

    @staticmethod
    def diet_flags(name: str) -> tuple[str, ...]:
        flags: list[str] = []
        for word, flag in _DIET_WORDS:
            if (
                word in name
                and flag not in flags
                and not (flag == "sugar_free" and "no_added_sugar" in flags)
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

    @staticmethod
    def words_of(item: NormalizedItem) -> str:
        """The part of the name whose words can be trusted. A chain that cuts item names at a
        fixed width (``normalize.NAME_LIMITS``) leaves the last word of a full-width name as a
        fragment ("חלב" from "חלבון"), so that word is not matched; a number there is kept."""
        name = item.clean_name
        if not is_full_width(item.chain_id, item.raw_name):
            return name
        head, _, tail = name.rstrip().rpartition(" ")
        return head if head and not any(ch.isdigit() for ch in tail) else name

    def extract_one(self, item: NormalizedItem) -> Result:
        full_name = item.clean_name
        if not full_name.strip():
            return ExtractionError(item_id=item.item_id, reason="empty name", retryable=False)
        truncated = is_truncated(item.chain_id, item.raw_name)
        name = self.words_of(item)
        pt = self.product_type(name)
        # eggs are sold by the piece: a name with a weight or volume ("ביצים עלומות 200 גרם",
        # "פתיתי ביצים 400 גר") is a jar or a pasta, never a tray
        if (pt is None or pt in EGG_TYPES) and item.unit in (None, "unit"):
            words = full_name.split()
            egg = egg_product_type(name, cut_tail=words[-1] if words and name != full_name else "")
            if egg is not None:
                pt = egg
        extra = self.catalog.extras.get(pt) if pt else None
        # What a product type implies ("milk without עמיד is fresh") is not known for a name the
        # chain cut: the missing words may say otherwise. The value stays unknown, so the judge
        # sends the item to review instead of serving it.
        implied = {} if truncated else (extra.implied if extra else {})
        rule = self.catalog.rules.get(pt) if pt else None
        keys = set(rule.critical_keys) | set(rule.soft_keys) if rule else set()

        state = self.state(name) or implied.get("state")
        flavor = self.flavor(name, pt) if (not rule or "flavor" in keys) else None
        if flavor is None and "flavor" in implied:
            flavor = implied["flavor"]
        # a percent sign on a vinegar (9%) or a beer (5%) is acidity or alcohol, not fat
        fat_pct = self.fat_pct(full_name) if (not rule or "fat_pct" in keys) else None
        brand, private = self.brand(full_name, item.chain_id, item.manufacturer)
        pack_size = None if item.is_weighed else item.total_quantity
        unit = None if item.is_weighed else item.unit

        confidence = 0.2 + (0.4 if pt else 0) + (0.1 if brand else 0) + (0.1 if pack_size else 0)
        return Attributes(
            category_path=self.category_path(pt, state),
            product_type=pt,
            brand=brand,
            is_private_label=private,
            fat_pct=fat_pct,
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
