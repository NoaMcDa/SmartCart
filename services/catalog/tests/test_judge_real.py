"""Judge name guards, each from a real chain item the first audit of real items got wrong.

``docs/matching.md``, "Real items, first audit": the rule pipeline served (or queued) products
whose own words said they were something else. The names below are item names as the chains
published them (``services/ingest/tests/fixtures/<chain>/real``), cut at the chain's width where
the chain cuts them. Each rule has a case that must be refused and a case that must stay allowed,
so the guard is a rule and not a list of items.
"""

from __future__ import annotations

import pytest

from smartcart_catalog.judge import name_guard
from smartcart_catalog.seed import load_catalog


@pytest.fixture(scope="module")
def by_slug():
    return {c.slug: c for c in load_catalog().canonicals}


def refused(by_slug, name: str, slug: str) -> bool:
    veto, _ = name_guard(name, by_slug[slug])
    return bool(veto)


def soft(by_slug, name: str, slug: str) -> list[str]:
    return name_guard(name, by_slug[slug])[1]


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        # a nectar (juice drink) is not the fruit or vegetable on the label (Osher Ad, cut at 20)
        ("נקטר ספרינג עגבניות", "tomato"),
        ("נקטר ספרינג אפרסק 1", "peach"),
        # a snack, a sauce, a jelly and a cereal flavored with the product are not the product
        ("חטיף נייטשר וואלי דבש5יח", "honey"),
        ("בולס איי רוטב ברביקיו עם דבש 4", "honey"),
        ("קורנפלקס דבש תלמה 44", "honey"),
        ("חטיף שיבולת שועל עם סירופ מייפל 210 ג' ניטשר ואלי", "rolled-oats"),
        ("ג'לי תנובה אפרסק", "peach"),
        ("קראנצי שיבולת שועל ושוקולד מריר 210 גר", "rolled-oats"),  # Tiv Taam: a bar
        ("סוכריות חמאה 50 גרם ורטר", "butter"),  # butter candy
        ("בצק עלים חמאה מעדנות", "butter"),  # puff pastry
        ("אשבול דגן חמאה 150 ג", "butter"),  # a cereal
        # flour and dough of a thing are not the thing
        ("קמח פיצה מנופה הנחתו", "frozen-pizza"),
    ],
)
def test_a_derived_product_is_not_the_base_product(by_slug, name, slug) -> None:
    assert refused(by_slug, name, slug)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("עגבניות חתוכות פולפה", "tomato"),  # crushed canned tomato (Rami Levy)
        ("שעועית לבנה ברוטב מב", "white-beans"),  # beans in sauce (Mega)
        ("פפריקה מתוקה בשמן 45", "sweet-paprika"),  # paprika paste in oil (Rami Levy)
        ("שוקיים/כרעיים מעושן", "chicken-drumstick-fresh"),  # smoked (Tiv Taam)
        ("יוקלה-פילה סלמון בעישון קר", "salmon-fillet-fresh"),  # cold-smoked
        ("מנגו מיובש דל סוכר ב", "mango"),  # dried
    ],
)
def test_a_prepared_or_preserved_item_is_not_the_fresh_or_dry_base(by_slug, name, slug) -> None:
    assert refused(by_slug, name, slug)


def test_a_preparation_word_in_the_canonical_name_is_not_a_veto(by_slug) -> None:
    # "טונה בשמן" and "סלמון מעושן פרוס" are canonicals made of the very word
    assert not refused(by_slug, "נתחי טונה בשמן 672 ג", "tuna-in-oil")
    assert not refused(by_slug, "פלטת סלמון מעושן 150", "smoked-salmon-sliced")


def test_a_derived_word_in_the_canonical_name_is_not_a_veto(by_slug) -> None:
    # the canonical is the juice, so a "מיץ" in the item is the product itself
    assert not refused(by_slug, "תירוש מיץ ענבים אדום", "grape-juice")
    assert not refused(by_slug, "מימון פלפל שחור טחון", "black-pepper")


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("סבון נוזלי לתינוק", "hand-soap"),  # Tiv Taam: baby soap served as adult hand soap
        ("שמפו אל דמע לתינוקות", "shampoo"),
        ("גונסון בייבי שמפו גו", "shampoo"),
        ("טלק לתינוק תירס 200", "sweet-corn-canned"),  # talc with corn starch
    ],
)
def test_a_baby_product_is_not_the_adult_one(by_slug, name, slug) -> None:
    assert refused(by_slug, name, slug)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("טבעול נאגטס צמחוני ב", "chicken-nuggets"),
        ("המבורגר ביונד מיט זוג 226 גרם", "beef-burger-frozen"),
    ],
)
def test_a_plant_based_item_is_not_the_animal_product(by_slug, name, slug) -> None:
    assert refused(by_slug, name, slug)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("משקה מוגז בטעם קולה 150 מ\"ל צ'אט", "cola"),  # a drink flavored like cola
        ("חטיף בטעם תירס ובוטנים 100 ג' אחלה", "sweet-corn-canned"),
        ("קראנצי בטעם מייפל וסוכר חום 210 גר", "sugar-brown"),
    ],
)
def test_a_word_after_the_flavor_marker_is_a_flavor_not_the_product(by_slug, name, slug) -> None:
    assert refused(by_slug, name, slug)


def test_the_product_before_the_flavor_marker_is_kept(by_slug) -> None:
    assert not refused(by_slug, 'גלידה בטעם וניל 500 מ"ל', "ice-cream-vanilla")


def test_diet_variant_is_a_close_substitute_never_any_brand(by_slug) -> None:
    # Skippy "no sugar" peanut butter and Verter "no sugar" candy are not the regular product
    assert soft(by_slug, "חמאת בוטנים ללא סוכר 340 ג' סקיפי", "peanut-butter")
    assert soft(by_slug, "חמאת בוטנים ללא תוספת סוכר 340", "peanut-butter")  # ללת"ס expanded
    # the canonical that is itself the diet variant carries the word
    assert soft(by_slug, "קולה דיאט 1.5 ליטר", "cola-zero") == []
    assert soft(by_slug, "קולה זירו 2 ליטר בוד", "cola-zero") == []
    assert soft(by_slug, "קולה זירו 2 ליטר בוד", "cola")


def test_a_fat_claim_next_to_a_fat_percentage_is_not_a_diet_variant(by_slug) -> None:
    # "light" cottage 3% and "דל שומן 1%" milk are decided by the fat percentage (critical)
    assert soft(by_slug, "קוטג' לייט 3% 250 גרם תנובה", "cottage-3") == []
    assert soft(by_slug, "חלב דל שומן 1% 1 ליטר טרה", "milk-fresh-1") == []
    assert soft(by_slug, "מיונז הלמנס לייט 394 גרם", "mayonnaise")
    assert soft(by_slug, "מיונז הלמנס לייט 394 גרם", "mayonnaise-light") == []
