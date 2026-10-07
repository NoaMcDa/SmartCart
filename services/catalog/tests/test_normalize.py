"""Rule normalization (issue #20): abbreviations, sizes, multipacks, weighed goods, unit price.

The names are written the way chain transparency files spell them (abbreviations, geresh and
gershayim, multipack notation). They are realistic, not copied from loaded files: the regression
fixtures under services/ingest/tests/fixtures are synthetic too. Replace or extend with names
from real PriceFull files once the VPS loads them.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from smartcart_catalog.models import NormalizedItem
from smartcart_catalog.normalize import (
    ABBREVIATIONS,
    clean_name,
    normalize,
    normalize_with_issues,
    parse_fields,
    unit_price,
)
from smartcart_ingest.models import ItemRecord

# raw_name, quantity, unit, is_weighed, item_code
#   -> quantity (one piece), unit, pack_count, total, base_unit, is_weighed
CASES = [
    ("חלב תנובה 3% בקרטון 1 ליטר", 1, "ליטר", False, "7290004131074", (1000, "ml", 1, 1000, "100ml", False)),
    ("חלב טרה 1% בשקית 1 ל'", 1, "ליטרים", False, "7290010117", (1000, "ml", 1, 1000, "100ml", False)),
    ("מים מינרליים נביעות 6*1.5 ל'", None, None, False, "7290011498", (1500, "ml", 6, 9000, "100ml", False)),
    ("מי עדן 1.5 ליטר*6", 9, "ליטר", False, "7290000066", (1500, "ml", 6, 9000, "100ml", False)),
    ('קוקה קולה 4X250 מ"ל', None, None, False, "7290001594", (250, "ml", 4, 1000, "100ml", False)),
    ("קולה זירו 4 x 330 מל", None, None, False, "7290001595", (330, "ml", 4, 1320, "100ml", False)),
    ("יוגורט דנונה 1.5% 4*200 גר'", 800, "גרם", False, "7290110", (200, "g", 4, 800, "100g", False)),
    ("טונה בש.ז. סטארקיסט 4*160ג'", None, None, False, "7290111", (160, "g", 4, 640, "100g", False)),
    ("שוקולד פרה מהד' מוגבלת 100 גרם", 100, "גרמים", False, "7290112", (100, "g", 1, 100, "100g", False)),
    ('סוכר לבן 1 ק"ג', 1, "קילוגרם", False, "7290113", (1000, "g", 1, 1000, "100g", False)),
    ("קמח לבן 1 קג", 1, 'ק"ג', False, "7290114", (1000, "g", 1, 1000, "100g", False)),
    ("עגבניות במשקל", 1, "קילוגרמים", True, "7290115", (1000, "g", 1, 1000, "kg", True)),
    ("עגבניות שרי", 1, 'ק"ג', False, "2000123", (1000, "g", 1, 1000, "kg", True)),
    ("בננה", None, None, False, "4011", (1000, "g", 1, 1000, "kg", True)),
    ("מלפפונים", 0, "קילוגרם", True, "7290116", (1000, "g", 1, 1000, "kg", True)),
    ("ביצים L 12 יח'", 12, "יחידה", False, "7290117", (12, "unit", 1, 12, "unit", False)),
    ("נייר טואלט לילי 32 גלילים", 1, "יחידה", False, "7290118", (32, "unit", 1, 32, "unit", False)),
    ("מארז 8 יוגורט פרי 150 גרם", 1200, "גרם", False, "7290119", (150, "g", 8, 1200, "100g", False)),
    ("קוטג' 5% 250 גרם", 1, "יחידה", False, "7290120", (250, "g", 1, 250, "100g", False)),
    ("שמן קנולה 1 ל'", 1000, 'מ"ל', False, "7290121", (1000, "ml", 1, 1000, "100ml", False)),
    ("במבה אסם 80 גרם", 80, "גרם", False, "7290122", (80, "g", 1, 80, "100g", False)),
    ("מארז שישייה קולה 1.5 ליטר", None, None, False, "7290123", (1500, "ml", 6, 9000, "100ml", False)),
    ("מים נביעות 1.5 ליטר", 6, "יחידות", False, "7290124", (1500, "ml", 6, 9000, "100ml", False)),
    ("שוקו 250*4 מל", None, None, False, "7290125", (250, "ml", 4, 1000, "100ml", False)),
    ("יוגורט 4 יחידות", 600, "גרם", False, "7290126", (150, "g", 4, 600, "100g", False)),
    ("חומוס אחלה 400 גרם", 400, "גרם", False, "7290127", (400, "g", 1, 400, "100g", False)),
    ("פסטרמה הודו 200 ג'", 200, "גרם", False, "7290128", (200, "g", 1, 200, "100g", False)),
    ('תפו"א לבנים', 1, 'ק"ג', False, "7290129", (1000, "g", 1, 1000, "kg", True)),
    ("מגבונים לחים 72 מגבונים", None, None, False, "7290130", (72, "unit", 1, 72, "unit", False)),
    ("טבליות למדיח פיניש 40 טבליות", 40, "יחידות", False, "7290131", (40, "unit", 1, 40, "unit", False)),
    ("תה ויסוצקי 100 שקיקים", 100, "יחידה", False, "7290132", (100, "unit", 1, 100, "unit", False)),
    ("ג'ל כביסה 3 ליטר", 3, "ליטר", False, "7290133", (3000, "ml", 1, 3000, "100ml", False)),
    ('שמנת מתוקה 32% 250 מ"ל', 250, "מיליליטרים", False, "7290134", (250, "ml", 1, 250, "100ml", False)),
    ("גבינה צהובה עמק 28% פרוסה 200 גר", 200, "גרם", False, "7290135", (200, "g", 1, 200, "100g", False)),
    ("פיתות 10 יח'", None, None, False, "7290136", (10, "unit", 1, 10, "unit", False)),
    ('אבקת כביסה 2.5 ק"ג', 2.5, "קילוגרמים", False, "7290137", (2500, "g", 1, 2500, "100g", False)),
    ("מיץ תפוזים פריגת 1,5 ליטר", None, None, False, "7290138", (1500, "ml", 1, 1500, "100ml", False)),
    ("ממרח שוקולד 750 גרם", D("0.75"), "קילוגרם", False, "7290139", (750, "g", 1, 750, "100g", False)),
    ("קפה נמס עלית 200 גרם", 1, "יחידה", False, "7290140", (200, "g", 1, 200, "100g", False)),
    ("חזה עוף טרי", 1, "קילוגרם", True, "7290141", (1000, "g", 1, 1000, "kg", True)),
    ('בירה גולדסטאר 6*330 מ"ל', None, None, False, "7290142", (330, "ml", 6, 1980, "100ml", False)),
    ("מים 1.5 ל' * 6", None, None, False, "7290143", (1500, "ml", 6, 9000, "100ml", False)),
    ("שקיות אשפה 30 שקיות", None, None, False, "7290144", (30, "unit", 1, 30, "unit", False)),
    ("גבינה לבנה 5% 500 גרם", 250, "גרם", False, "7290145", (500, "g", 1, 500, "100g", False)),
    ('זוג סבון ידיים 500 מ"ל', None, None, False, "7290146", (500, "ml", 2, 1000, "100ml", False)),
    ('אורז פרסי סוגת 1 ק"ג', 1, 'ק"ג', False, "7290147", (1000, "g", 1, 1000, "100g", False)),
    ("רסק עגבניות 100 גרם*4", None, None, False, "7290148", (100, "g", 4, 400, "100g", False)),
    ("עגבניות שרי מארז 500 גרם", 500, "גרם", False, "7290149", (500, "g", 1, 500, "100g", False)),
    ("לחם ג'בטה 300 גרם", 300, "גרם", False, "7290150", (300, "g", 1, 300, "100g", False)),
    ("סרדינים בש.ז 4*125 גרם", 500, "גרם", False, "7290151", (125, "g", 4, 500, "100g", False)),
]


@pytest.mark.parametrize(("raw", "qty", "unit", "weighed", "code", "expected"), CASES,
                         ids=[c[0] for c in CASES])
def test_normalize_table(raw, qty, unit, weighed, code, expected) -> None:
    item = ItemRecord(chain_id="c", item_code=code, raw_name=raw,
                      quantity=None if qty is None else D(str(qty)), unit=unit, is_weighed=weighed)
    n = normalize(item, item_id=7)
    e_qty, e_unit, e_pack, e_total, e_base, e_weighed = expected
    assert (n.quantity, n.unit, n.pack_count, n.total_quantity, n.base_unit, n.is_weighed) == (
        D(e_qty), e_unit, e_pack, D(e_total), e_base, e_weighed
    )
    assert n.item_id == 7


def test_table_has_at_least_forty_names() -> None:
    assert len(CASES) >= 40


# --- abbreviations -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("טונה בש.ז. 160 גרם", "טונה בשמן זית 160 גרם"),
        ("טונה בש.ז 160 גרם", "טונה בשמן זית 160 גרם"),
        ('סרדינים בש"ז', "סרדינים בשמן זית"),
        ("פסטו ש.ז.", "פסטו שמן זית"),
        ("שוקולד מהד' מוגבלת", "שוקולד מהדורה מוגבלת"),
        ("שוקולד מהד׳ חורף", "שוקולד מהדורה חורף"),
        ('סוכר 1 ק"ג', "סוכר 1 קילוגרם"),
        ("סוכר 1 ק״ג", "סוכר 1 קילוגרם"),
        ("קמח 1קג", "קמח 1קילוגרם"),
        ("עגבניות לק\"ג", "עגבניות לקילוגרם"),
        ('שמנת 250 מ"ל', "שמנת 250 מיליליטר"),
        ("חטיף 80 ג'", "חטיף 80 גרם"),
        ("חטיף 80ג'", "חטיף 80גרם"),
        ("חטיף 80 גר'", "חטיף 80 גרם"),
        ("מים 1.5 ל'", "מים 1.5 ליטר"),
        ("ביצים 12 יח'", "ביצים 12 יחידות"),
        ('תפו"א אדום', "תפוחי אדמה אדום"),
        ("  חלב   3%  ", "חלב 3%"),
    ],
)
def test_abbreviation_expansion(raw: str, expected: str) -> None:
    assert clean_name(raw) == expected


@pytest.mark.parametrize("raw", ["שזיפים מיובשים", "ג'בטה", "לחם ל'אפה", "גבינת עיזים", "קג'ון"])
def test_abbreviations_leave_words_alone(raw: str) -> None:
    assert clean_name(raw) == raw


def test_abbreviation_table_is_documented() -> None:
    assert len(ABBREVIATIONS) >= 8
    assert all(a.expansion for a in ABBREVIATIONS)


# --- fields ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("qty", "unit", "expected"),
    [
        (500, "גרם", (D(500), "g")),
        (500, "גרמים", (D(500), "g")),
        (1, 'ק"ג', (D(1000), "g")),
        (D("1.5"), "ליטר", (D(1500), "ml")),
        (330, 'מ"ל', (D(330), "ml")),
        (1, "יחידה", (D(1), "unit")),
        (1, "100 גרם", (D(1), "g")),
        (0, "גרם", None),
        (None, "גרם", None),
        (1, "לא ידוע", None),
        (2, "מטר", None),
        (1, None, None),
    ],
)
def test_parse_fields(qty, unit, expected) -> None:
    assert parse_fields(qty, unit) == expected


# --- issues are reported, never guessed ---------------------------------------------------------


def test_unparseable_is_reported_not_guessed() -> None:
    r = normalize_with_issues({"raw_name": "לחם אחיד פרוס", "item_code": "7290000000002"})
    assert not r.parsed
    assert r.item.base_unit is None and r.item.total_quantity is None
    assert any("unparseable" in i for i in r.issues)


def test_conflicting_fields_use_the_name_and_say_so() -> None:
    r = normalize_with_issues(
        {"raw_name": "גבינה לבנה 5% 500 גרם", "quantity": 250, "unit": "גרם", "item_code": "1"}
    )
    assert r.item.total_quantity == D(500)
    assert r.source == "name"
    assert any("fields say 250 g" in i for i in r.issues)


def test_dimension_mismatch_reported() -> None:
    r = normalize_with_issues(
        {"raw_name": "חלב 1 ליטר", "quantity": 1, "unit": "קילוגרם", "item_code": "1"}
    )
    assert (r.item.total_quantity, r.item.unit) == (D(1000), "ml")
    assert any("fields say g" in i for i in r.issues)


def test_weighed_by_plu_is_flagged() -> None:
    r = normalize_with_issues({"raw_name": "אבוקדו", "item_code": "4046"})
    assert r.item.is_weighed and r.item.base_unit == "kg"
    assert any("PLU" in i for i in r.issues)


def test_plu_code_does_not_override_a_size_in_the_name() -> None:
    n = normalize({"raw_name": "עגבניות שרי 250 גרם", "item_code": "4087"})
    assert not n.is_weighed and n.base_unit == "100g"


def test_dict_row_and_id_key() -> None:
    n = normalize({"id": 42, "raw_name": "במבה 80 גרם"})
    assert n.item_id == 42 and n.clean_name == "במבה 80 גרם"


def test_source_fields_and_issues_travel_on_the_item() -> None:
    """Issue #92: chain, manufacturer, barcode, raw name and issues are on the item itself."""
    row = ItemRecord(chain_id="7290027600007", item_code="7290004131074",
                     barcode="7290004131074", raw_name="גבינה לבנה 5% 500 גרם",
                     manufacturer="תנובה", quantity=D(250), unit="גרם")  # fmt: skip
    r = normalize_with_issues(row, item_id=7)
    n = r.item
    assert (n.chain_id, n.manufacturer, n.barcode) == ("7290027600007", "תנובה", "7290004131074")
    assert n.raw_name == "גבינה לבנה 5% 500 גרם"
    assert n.issues == r.issues and any("fields say 250 g" in i for i in n.issues)
    bare = normalize({"raw_name": "במבה 80 גרם", "manufacturer": "  "})
    assert (bare.chain_id, bare.manufacturer, bare.barcode, bare.issues) == (None, None, None, ())


# --- unit price -----------------------------------------------------------------------------------


def _n(**kw) -> NormalizedItem:
    return normalize(kw | {"item_code": kw.get("item_code", "1")}, item_id=1)


def test_unit_price_per_100ml_on_the_multipack_total() -> None:
    n = _n(raw_name="מים מינרליים 6*1.5 ל'")
    assert n.total_quantity == D(9000)
    assert unit_price(D("12.90"), n) == (D("0.1433"), "100ml")


def test_unit_price_per_100ml() -> None:
    assert unit_price(D("6.90"), _n(raw_name="חלב 3% 1 ליטר")) == (D("0.6900"), "100ml")


def test_unit_price_per_100g() -> None:
    assert unit_price(D("5.50"), _n(raw_name="קוטג' 5% 250 גרם")) == (D("2.2000"), "100g")


def test_unit_price_per_unit() -> None:
    assert unit_price(D("13.80"), _n(raw_name="ביצים L 12 יח'")) == (D("1.1500"), "unit")


def test_unit_price_weighed_is_per_kg_and_estimated() -> None:
    n = _n(raw_name="עגבניות", quantity=1, unit="קילוגרם", is_weighed=True)
    assert n.is_weighed  # the caller labels this price "estimated"
    assert unit_price(D("7.90"), n) == (D("7.9000"), "kg")


def test_unit_price_refuses_unparsed_items() -> None:
    with pytest.raises(ValueError, match="no parsed size"):
        unit_price(D("8.90"), _n(raw_name="לחם אחיד פרוס", item_code="7290000000002"))
