"""Rule extractor on real chain item names (first audit of real items, ``docs/matching.md``).

Each case is an item as a chain published it (``services/ingest/tests/fixtures/<chain>/real``):
what the extractor must not conclude from a name the chain cut, and from words that are an
ingredient, a flavor or a type of another product.
"""

from __future__ import annotations

import pytest

from smartcart_catalog.extract.rule import RuleExtractor
from smartcart_catalog.models import Attributes
from smartcart_catalog.normalize import normalize

MEGA = "7290055700007"
OSHER_AD = "7290103152017"
SHUFERSAL = "7290027600007"
KING_STORE = "7290058108879"
RAMI_LEVY = "7290058140886"


@pytest.fixture(scope="module")
def rx() -> RuleExtractor:
    return RuleExtractor()


def extract(rx: RuleExtractor, name: str, chain: str, **fields) -> Attributes:
    row = {"raw_name": name, "item_code": "7290000000000", "chain_id": chain, **fields}
    out = rx.extract([normalize(row, item_id=1)])[0]
    assert isinstance(out, Attributes)
    return out


def test_a_cut_name_does_not_get_the_state_its_product_type_implies(rx) -> None:
    # Osher Ad cuts at 20 characters: "ענבי טל" may be followed by "קפואים" for all we know
    cut = extract(rx, "ענבים אדומים ענבי טל", OSHER_AD)
    whole = extract(rx, "ענבים אדומים", KING_STORE)
    assert cut.product_type == whole.product_type == "grapes"
    assert whole.state == "fresh"
    assert cut.state is None


def test_the_last_word_of_a_full_width_name_is_not_matched_as_a_word(rx) -> None:
    # Mega, 20 characters: "שוקולד" is the start of a longer word, not the product type
    cut = extract(rx, "קליפות הדרים בשוקולד", MEGA)
    whole = extract(rx, "קליפות הדרים בשוקולד", KING_STORE)
    assert whole.product_type == "chocolate_bar"
    assert cut.product_type is None


@pytest.mark.parametrize(
    ("name", "chain"),
    [
        ("האופה - גרגירי חומוס", MEGA),  # the full name continues; "חומוס" is a fragment here
        ("נקטר ספרינג תות בננה", OSHER_AD),
    ],
)
def test_the_fragment_at_the_cut_never_decides_the_type(rx, name, chain) -> None:
    assert extract(rx, name, chain).product_type is None


def test_a_number_at_the_cut_is_kept(rx) -> None:
    # "שוקולד מריר לינדט מלח 10" ends in the start of "100 גרם"; the digits are not a word
    got = extract(rx, "שוקולד מריר לינדט מלח 10", SHUFERSAL)
    assert got.product_type == "chocolate_bar"


def test_dark_chocolate_with_salt_is_not_the_plain_dark_bar(rx) -> None:
    salted = extract(rx, "שוקולד מריר לינדט מלח 10", SHUFERSAL)
    plain = extract(rx, "שוקולד מריר לינדט 100 גרם", KING_STORE)
    assert plain.flavor == "dark"
    assert salted.flavor != "dark" and salted.flavor.startswith("dark+")


def test_a_filling_makes_a_bar_a_different_bar(rx) -> None:
    assert extract(rx, "שוקולד מריר עם אגוזים 100 גרם", KING_STORE).flavor == "dark+other"


def test_a_percent_sign_on_vinegar_or_beer_is_not_a_fat_percentage(rx) -> None:
    # Shufersal: "חומץ 9% 1 ליטר" is acidity; Mega: "בירה קרומבאכר חיטה 5" is alcohol
    assert extract(rx, "חומץ 9% 1 ליטר", SHUFERSAL).fat_pct is None
    assert extract(rx, 'חומץ היינץ 5% 946 מ"ל', "7290873255550").fat_pct is None
    assert str(extract(rx, "חמאה 60% אלוויר 200 גרם", SHUFERSAL).fat_pct) == "60"


@pytest.mark.parametrize(
    ("name", "chain", "wrong_type"),
    [
        ("תה ירוק יסמין 25 שקיקים", SHUFERSAL, "rice_jasmine"),  # Shufersal: tea, not jasmine rice
        ("סבון מוצק עץ התה של", "7290873255550", "tea_black"),  # soap with tea tree oil
        ('בירה פאולנר חיטה 500 מ"ל', SHUFERSAL, "lager_beer"),  # wheat beer is not a lager
        ("קליק טבלת שוקו קראנץ", RAMI_LEVY, "chocolate_milk"),  # a chocolate bar, not milk
        ("לחמניה שמרים", "7290873255550", "dry_yeast"),  # a yeast roll
        ("גרעיני אבטיח גמבו ק", "7290803800003", "watermelon"),  # seeds
        ("תירס גרעינים מבורך 4", OSHER_AD, "sunflower_seeds"),  # corn kernels
        ("שברי בייגלה במילוי חמאת בוטנים 283 ג' סניידרס", KING_STORE, "peanut_butter"),
    ],
)
def test_product_type_exclusions_from_real_items(rx, name, chain, wrong_type) -> None:
    assert extract(rx, name, chain).product_type != wrong_type


@pytest.mark.parametrize(
    ("name", "chain"),
    [("גרגירי חומוס 800 גרם", RAMI_LEVY), ("גרגרי חומוס 400 גרם", KING_STORE)],
)
def test_chickpeas_in_either_spelling_are_not_the_hummus_salad(rx, name, chain) -> None:
    assert extract(rx, name, chain).product_type == "chickpeas"


def test_sugar_free_claims_become_diet_flags(rx) -> None:
    got = extract(rx, 'חמאת בוטנים ללת"ס340', SHUFERSAL)
    assert got.product_type == "peanut_butter"
    assert "no_added_sugar" in got.diet_flags
    assert "sugar_free" in extract(rx, 'סוכריות חמאה לל"ס80 ורטר', SHUFERSAL).diet_flags


def test_kosher_badatz_spelled_with_a_final_tsadi(rx) -> None:
    assert extract(rx, 'קמח תופח בד"צ 1 ק"ג', KING_STORE).kosher == 'בד"ץ'
