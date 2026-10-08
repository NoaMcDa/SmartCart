"""Arabic list splitting and quantities, and proof that Hebrew parsing did not change (issue #73)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartcart_api.listparse import parse_fragment, split_items, split_vav

D = Decimal


# --- splitting ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "items"),
    [
        ("حليب\nخبز\nبيض", ["حليب", "خبز", "بيض"]),
        ("حليب، خبز، بيض", ["حليب", "خبز", "بيض"]),  # Arabic comma
        ("حليب, خبز", ["حليب", "خبز"]),
        ("حليب؛ خبز", ["حليب", "خبز"]),  # Arabic semicolon
        ("حليب; خبز", ["حليب", "خبز"]),
        ("- حليب\n• خبز\n\n", ["حليب", "خبز"]),
        ("1,5 كيلو بندورة، حليب", ["1,5 كيلو بندورة", "حليب"]),  # a comma between digits is a decimal mark
        ("١٫٥ كيلو بندورة\nحليب", ["١٫٥ كيلو بندورة", "حليب"]),
        ("حليب 3%, كوتيج 5%", ["حليب 3%", "كوتيج 5%"]),
        ("‏حليب‎\n‏خبز", ["حليب", "خبز"]),  # bidirectional marks are dropped
        ("حليب\nחלב, לחם", ["حليب", "חלב", "לחם"]),  # a Hebrew line keeps the Hebrew rules
        ("חלב\nحليب, خبز", ["חלב", "حليب", "خبز"]),
    ],
)
def test_split_items_arabic(text: str, items: list[str]) -> None:
    assert split_items(text) == items


@pytest.mark.parametrize(
    ("fragment", "parts"),
    [
        ("حليب وخبز", ["حليب", "خبز"]),  # attached waw
        ("حليب و خبز", ["حليب", "خبز"]),  # standalone waw
        ("بندورة وخيار وبصل", ["بندورة", "خيار", "بصل"]),
        ("كيلو ونص بندورة", ["كيلو ونص بندورة"]),  # "and a half" is a quantity
        ("كيلو و نص بندورة", ["كيلو و نص بندورة"]),
        ("2 كيلو وربع بصل", ["2 كيلو وربع بصل"]),
        ("حليب 3%", ["حليب 3%"]),
        ("2 حليب و3 خبز", ["2 حليب و3 خبز"]),  # waw before a digit is not split, like the Hebrew vav
        ("ورق تواليت", ["ورق تواليت"]),  # a word that starts with waw at the front stays
        ("حليب والخبز", ["حليب", "الخبز"]),  # the article is stripped later, in matching
        ("بندورة", ["بندورة"]),
    ],
)
def test_split_waw(fragment: str, parts: list[str]) -> None:
    assert split_vav(fragment) == parts


def test_split_waw_inside_a_real_word_is_left_to_the_caller() -> None:
    # "ورق" after a space looks like a waw + "رق"; the route keeps the whole fragment when its
    # parts resolve worse than it does (like "חטיף וופל" in Hebrew)
    assert split_vav("منديل ورق") == ["منديل", "رق"]


# --- quantities ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "product", "qty", "unit"),
    [
        ("2 كيلو بندورة", "بندورة", "2", "kg"),
        ("2كيلو بندورة", "بندورة", "2", "kg"),
        ("٢ كيلو بندورة", "بندورة", "2", "kg"),
        ("2.5 كغم تفاح احمر", "تفاح احمر", "2.5", "kg"),
        ("1,5 كيلو بندورة", "بندورة", "1.5", "kg"),
        ("١٫٥ كيلو بندورة", "بندورة", "1.5", "kg"),
        ("نص كيلو جبنة بيضاء", "جبنة بيضاء", "0.5", "kg"),
        ("نصف كيلو جبنة", "جبنة", "0.5", "kg"),
        ("ربع كيلو لحمة", "لحمة", "0.25", "kg"),
        ("كيلو بندورة", "بندورة", "1", "kg"),
        ("كيلو ونص بندورة", "بندورة", "1.5", "kg"),
        ("كيلو و نص بندورة", "بندورة", "1.5", "kg"),
        ("كيلو وربع جبنة", "جبنة", "1.25", "kg"),
        ("كيلوين بصل", "بصل", "2", "kg"),
        ("كيلوين ونص بصل", "بصل", "2.5", "kg"),
        ("اثنين كيلو برتقال", "برتقال", "2", "kg"),
        ("500 غرام جبنة بيضاء 5%", "جبنة بيضاء 5%", "0.5", "kg"),
        ("250 غم جبنة", "جبنة", "0.25", "kg"),
        ("علبتين حليب", "حليب", "2", None),
        ("علبة حليب", "حليب", "1", None),
        ("حبتين افوكادو", "افوكادو", "2", None),
        ("٣ علب حليب", "حليب", "3", None),
        ("3 حبات خيار", "خيار", "3", None),
        ("ثلاث بندورات", "بندورات", "3", None),
        ("كيس رز", "رز", "1", None),
        ("2 لتر حليب", "حليب", "2", None),  # whole litres: packs of a litre
        ("نص لتر حليب", "حليب", "1", None),  # a size, not a count
        ("500 مل كريمة", "كريمة", "1", None),
        ("بندورة 2 كيلو", "بندورة", "2", "kg"),  # trailing weight
        ("بندورة كيلو ونص", "بندورة", "1.5", "kg"),
        ("بندورة كيلو", "بندورة", "1", "kg"),
        ("حليب 3 علب", "حليب", "3", None),
        ("حليب علبتين", "حليب", "2", None),
        ("حليب x3", "حليب", "3", None),
        ("حليب ×3", "حليب", "3", None),
        ("x2 حليب", "حليب", "2", None),
        ("3x حليب", "حليب", "3", None),
        ("بيض L عدد 2", "بيض L", "2", None),
        ("عدد 3 حليب", "حليب", "3", None),
        ("2 حليب", "حليب", "2", None),
        # what stays in the text
        ("حليب 3%", "حليب 3%", "1", None),  # a fat percentage is not a quantity
        ("حليب %3", "حليب %3", "1", None),
        ("3% حليب", "3% حليب", "1", None),
        ("بيض L 12", "بيض L 12", "1", None),  # a bare trailing number is part of the product
        ("جبنة بيضاء 250 غرام", "جبنة بيضاء 250 غرام", "1", None),  # a size
        ("تونة علبة", "تونة علبة", "1", None),
        ("اكياس زبالة", "اكياس زبالة", "1", None),  # a bare plural unit noun is the product
        ("نص بندورة", "نص بندورة", "1", None),
        ("حليب", "حليب", "1", None),
        ("ورق تواليت", "ورق تواليت", "1", None),
    ],
)
def test_arabic_quantities(text: str, product: str, qty: str, unit: str | None) -> None:
    f = parse_fragment(text)
    assert (f.text, f.quantity, f.unit) == (product, D(qty), unit)
    assert f.input_text == text


def test_quantity_is_capped() -> None:
    assert parse_fragment("500 علبة حليب").quantity == D(99)


# --- Hebrew is unchanged ---------------------------------------------------------------------------------
# A snapshot of the Hebrew behavior of the original parser (taken before the Arabic path was added).
# Hebrew text never reaches the Arabic functions, so these must stay byte-identical.

HE_SPLIT_ITEMS = [
    ("חלב, 2 רסק עגבניות\nסלמון;לחם", ["חלב", "2 רסק עגבניות", "סלמון", "לחם"]),
    ("- חלב\n• לחם\n\n", ["חלב", "לחם"]),
    ("חלב ולחם", ["חלב ולחם"]),
    ("1,5 קילו עגבניות, חלב", ["1", "5 קילו עגבניות", "חלב"]),  # the old behavior, kept as is
    ("חלב ، לחם ؛ ביצים", ["חלב", "לחם", "ביצים"]),  # Arabic punctuation inside Hebrew
    ("חלב 3%\nקוטג' 5%\nביצים L 12", ["חלב 3%", "קוטג' 5%", "ביצים L 12"]),
    ("חלב * 3", ["חלב", "3"]),
    ("milk 3%", ["milk 3%"]),
    ("חלב, milk", ["חלב", "milk"]),
    ("", []),
    ("  ", []),
    ("לחם; חלב\nביצים, גבינה\n- שמנת", ["לחם", "חלב", "ביצים", "גבינה", "שמנת"]),
]
HE_VAV = [
    ("חלב ולחם", ["חלב", "לחם"]),
    ("רסק עגבניות", ["רסק עגבניות"]),
    ("2 חלב ו3 לחם", ["2 חלב ו3 לחם"]),
    ("סלמון ולחם", ["סלמון", "לחם"]),
    ("חטיף וופל", ["חטיף", "ופל"]),
    ("חלב ולחם וביצים", ["חלב", "לחם", "ביצים"]),
]
HE_FRAGMENTS = [
    ("2 רסק עגבניות", "רסק עגבניות", "2", None),
    ("חלב x3", "חלב", "3", None),
    ("חלב ×3", "חלב", "3", None),
    ("חלב 3x", "חלב", "3", None),
    ("3x חלב", "חלב", "3", None),
    ("x2 חלב", "חלב", "2", None),
    ("חלב 4 יח'", "חלב", "4", None),
    ('1.5 ק"ג עגבניות', "עגבניות", "1.5", "kg"),
    ("5 קילו עגבניות", "עגבניות", "5", "kg"),
    ("500 גרם גבינה צהובה", "גבינה צהובה", "0.5", "kg"),
    ("250 גר' גבינה", "גבינה", "0.25", "kg"),
    ("שני חלב", "חלב", "2", None),
    ("שלוש בננות", "בננות", "3", None),
    ("חלב 3%", "חלב 3%", "1", None),
    ("ביצים L 12", "ביצים L 12", "1", None),
    ("רסק עגבניות 100 גרם", "רסק עגבניות 100 גרם", "1", None),
    ("חלב 2 יחידות", "חלב", "2", None),
    ("2 ליטר חלב", "ליטר חלב", "2", None),  # Hebrew keeps the unit word
    ("500 מל שמנת", "מל שמנת", "99", None),  # a quirk of the Hebrew rules, kept
    ("חצי קילו עגבניות", "חצי קילו עגבניות", "1", None),
    ('עגבניות 2 ק"ג', 'עגבניות 2 ק"ג', "1", None),
    ("2 חלב ו3 לחם", "חלב ו3 לחם", "2", None),
    ("milk 3%", "milk 3%", "1", None),
    ("Coca Cola זירו", "Coca Cola זירו", "1", None),
    ("x", "x", "1", None),
    ("3", "3", "1", None),
    ("", "", "1", None),
]


@pytest.mark.parametrize(("text", "items"), HE_SPLIT_ITEMS)
def test_hebrew_split_items_unchanged(text: str, items: list[str]) -> None:
    assert split_items(text) == items


@pytest.mark.parametrize(("fragment", "parts"), HE_VAV)
def test_hebrew_vav_unchanged(fragment: str, parts: list[str]) -> None:
    assert split_vav(fragment) == parts


@pytest.mark.parametrize(("text", "product", "qty", "unit"), HE_FRAGMENTS)
def test_hebrew_fragments_unchanged(text: str, product: str, qty: str, unit: str | None) -> None:
    f = parse_fragment(text)
    assert (f.input_text, f.text, f.quantity, f.unit) == (text, product, D(qty), unit)
