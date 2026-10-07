"""Rule extractor (issue #25 baseline): product type, fat, state, flavor, brand, private label."""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartcart_catalog.extract.rule import MAX_CONFIDENCE, RuleExtractor
from smartcart_catalog.models import Attributes, ExtractionError, NormalizedItem
from smartcart_catalog.normalize import normalize

SHUFERSAL = "7290027600007"
RAMI_LEVY = "7290058140886"


@pytest.fixture(scope="module")
def rx() -> RuleExtractor:
    return RuleExtractor()


def _extract(rx: RuleExtractor, name: str, chain: str | None = SHUFERSAL) -> Attributes:
    item = normalize({"raw_name": name, "item_code": "7290000000000", "chain_id": chain}, item_id=1)
    out = rx.extract([item])[0]
    assert isinstance(out, Attributes)
    return out


@pytest.mark.parametrize(
    ("name", "product_type", "fat", "state", "flavor"),
    [
        ("חלב תנובה 3% בקרטון 1 ליטר", "milk", "3", "fresh", None),
        ("חלב טרה 1% בשקית 1 ל'", "milk", "1", "fresh", None),
        ("חלב עמיד טרה 1% 1 ליטר", "milk_long_life", "1", None, None),
        ("חלב ללא לקטוז 2% 1 ליטר", "milk_lactose_free", "2", None, None),
        ("משקה סויה אלפרו 1 ליטר", "soy_drink", None, None, None),
        ("משקה שקדים ללא סוכר 1 ליטר", "almond_drink", None, None, None),
        ("משקה שיבולת שועל 1 ליטר", "oat_drink", None, None, None),
        ('פילה סלמון קפוא 1 ק"ג', "salmon_fillet", None, "frozen", None),
        ("פילה סלמון טרי", "salmon_fillet", None, "fresh", None),
        ("קוטג' 5% 250 גרם", "cottage_cheese", "5", None, None),
        ("יוגורט תות 150 גרם", "yogurt_fruit", None, None, "strawberry"),
        ("יוגורט טבעי 3% 200 גרם", "yogurt", "3", None, "plain"),
        ("שוקולד פרה מריר 100 גרם", "chocolate_bar", None, None, "dark"),
        ("שוקולד חלב 100 גרם", "chocolate_bar", None, None, "milk"),
        ("ביסלי גריל 70 גרם", "wheat_snack", None, None, "grill"),
        ("חומוס אחלה 400 גרם", "hummus_salad", None, None, "plain"),
        ("חומוס עם צנוברים 400 גרם", "hummus_salad", None, None, "pine_nut"),
        ("אפונה קפואה 800 גרם", "peas", None, "frozen", None),
        ("אפונה בשימורים 400 גרם", "peas", None, "canned", None),
        ("עגבניות", "tomato", None, "fresh", None),
        ("חלבה 500 גרם", "halva", None, None, None),
        ("קולה זירו 1.5 ליטר", "cola_zero", None, None, None),
        ("קוקה קולה 1.5 ליטר", "cola", None, None, None),
        ("בורקס גבינה קפוא", "burekas", None, "frozen", "cheese"),
        ("שוקולד מריר 70% קקאו", "chocolate_bar", None, None, "dark"),
        ("מיץ תפוזים טבעי 1 ליטר", "orange_juice_chilled", None, None, None),
        ("מיץ ענבים 100% 1 ליטר", "grape_juice", None, None, None),
    ],
)
def test_rule_table(rx, name, product_type, fat, state, flavor) -> None:
    a = _extract(rx, name)
    assert a.product_type == product_type
    assert a.fat_pct == (Decimal(fat) if fat else None)
    assert a.state == state
    assert a.flavor == flavor


def test_category_path_follows_state(rx) -> None:
    assert _extract(rx, "אפונה קפואה").category_path == "frozen.vegetables.single"
    assert _extract(rx, "אפונה בשימורים").category_path == "canned.vegetables.legumes"
    assert _extract(rx, "חלב 3% 1 ליטר").category_path == "dairy.milk.fresh"


def test_private_label_needs_the_chain(rx) -> None:
    a = _extract(rx, "שופרסל חלב 3% 1 ליטר", chain=SHUFERSAL)
    assert (a.brand, a.is_private_label) == ("שופרסל", True)
    # the same text at another chain is not that chain's private label
    b = _extract(rx, "שופרסל חלב 3% 1 ליטר", chain=RAMI_LEVY)
    assert b.is_private_label is not True
    c = _extract(rx, "חלב תנובה 3% 1 ליטר")
    assert (c.brand, c.is_private_label) == ("תנובה", False)
    assert _extract(rx, "חלב 3% 1 ליטר").is_private_label is None


def test_kosher_and_diet_are_read_but_never_verified(rx) -> None:
    a = _extract(rx, 'מצות כשר לפסח בד"ץ 1 ק"ג')
    assert a.kosher == "כשר לפסח"
    b = _extract(rx, "משקה שקדים ללא סוכר טבעוני 1 ליטר")
    assert set(b.diet_flags) == {"sugar_free", "vegan"}
    assert a.verified_keys == () and b.verified_keys == ()


def test_pack_size_comes_from_normalization(rx) -> None:
    a = _extract(rx, "מים מינרליים 6*1.5 ל'")
    assert (a.pack_size, a.unit) == (Decimal(9000), "ml")
    assert _extract(rx, "עגבניות במשקל").pack_size is None


def test_confidence_is_capped(rx) -> None:
    a = _extract(rx, "חלב תנובה 3% בקרטון 1 ליטר")
    assert 0 < a.confidence <= MAX_CONFIDENCE
    assert _extract(rx, "מוצר לא מוכר").confidence < a.confidence


def test_empty_name_is_a_non_retryable_error(rx) -> None:
    out = rx.extract([NormalizedItem(item_id=9, clean_name="  ")])[0]
    assert isinstance(out, ExtractionError) and not out.retryable


def test_output_order_and_count_match_input(rx) -> None:
    items = [normalize({"raw_name": n}, item_id=i) for i, n in enumerate(["חלב 1 ליטר", "", "במבה"])]
    out = rx.extract(items)
    assert [type(o).__name__ for o in out] == ["Attributes", "ExtractionError", "Attributes"]


@pytest.mark.parametrize(
    ("name", "base", "variety"),
    [
        ("משקה סויה אלפרו 1 ליטר", "soy", None),
        ("משקה שקדים ללא סוכר 1 ליטר", "almond", None),
        ("משקה שיבולת שועל בריסטה 1 ליטר", "oat", "barista"),
        ("חלב תנובה 3% בקרטון 1 ליטר", None, None),
        ("רוטב סויה 250 מ\"ל", None, None),  # soy sauce is not a plant drink
    ],
)
def test_plant_drink_base_and_variety(rx, name, base, variety) -> None:
    """Issue #92: ``base`` for plant drinks, ``variety`` for named varieties."""
    a = _extract(rx, name)
    assert (a.base, a.variety) == (base, variety)


@pytest.mark.parametrize(
    ("name", "product_type", "base"),
    [
        # the five bases, from the name, with the usual Hebrew spellings
        ("משקה סויה אלפרו 1 ליטר", "soy_drink", "soy"),
        ("חלב סוייה 1 ליטר", "soy_drink", "soy"),
        ("משקה שקדים ללא סוכר 1 ליטר", "almond_drink", "almond"),
        ("חלב שקדים וניל 1 ליטר", "almond_drink", "almond"),
        ("משקה שיבולת שועל 1 ליטר", "oat_drink", "oat"),
        ("חלב שיבולת שועל בריסטה 1 ליטר", "oat_drink", "oat"),  # not rolled oats
        ("אוטלי בריסטה 1 ליטר", "oat_drink", "oat"),
        # a plant drink is never lactose-free cow's milk, even on a keyword tie
        ("משקה סויה ללא לקטוז 1 ליטר", "soy_drink", "soy"),
        ("משקה שקדים ללא לקטוז 1 ליטר", "almond_drink", "almond"),
        # no product type of their own: the base still comes from the name
        ("משקה אורז 1 ליטר", None, "rice"),
        ("משקה קוקוס 1 ליטר", None, "coconut"),
        ('חלב קוקוס 400 מ"ל', None, "coconut"),
        # a soy or coconut yogurt is not a dairy yogurt
        ("יוגורט סויה טבעי 400 גרם", None, "soy"),
        ("יוגורט קוקוס 150 גרם", None, "coconut"),
        # the first base wins; a base word after "בטעם" is a flavor
        ("משקה סויה בטעם שקדים 1 ליטר", "soy_drink", "soy"),
        ("משקה בטעם קוקוס אורז 1 ליטר", None, "rice"),
        # not plant products: no base
        ("יוגורט בטעם קוקוס 150 גרם", "yogurt_fruit", None),
        ("שמן סויה 1 ליטר", "soybean_oil", None),
        ('אורז בסמטי 1 ק"ג', "rice_basmati", None),
        ("שיבולת שועל 500 גרם", "rolled_oats", None),
        ("עוגיות שקדים 200 גרם", None, None),
        ("חלב טרי 3% 1 ליטר", "milk", None),
    ],
)
def test_base_from_hebrew_names(rx, name, product_type, base) -> None:
    """Issue #102: ``base`` is critical for the plant drinks, so it must be read reliably."""
    a = _extract(rx, name)
    assert (a.product_type, a.base) == (product_type, base)


def test_private_label_reads_chain_and_manufacturer_from_the_item(rx) -> None:
    item = normalize({"raw_name": "חלב 3% 1 ליטר", "item_code": "1", "chain_id": SHUFERSAL,
                      "manufacturer": "שופרסל בע\"מ"}, item_id=3)
    out = rx.extract([item])[0]
    assert isinstance(out, Attributes)
    assert (out.brand, out.is_private_label) == ("שופרסל", True)
