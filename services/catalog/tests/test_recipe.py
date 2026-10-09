"""The rule-based Hebrew recipe parser (issue #71): amounts, units, conversions, pages."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from smartcart_catalog import recipe as rp
from smartcart_catalog.recipe import Ingredient, Unresolved, basket_quantity, parse_ingredient

D = Decimal


@pytest.mark.parametrize(
    ("line", "name", "amount", "dim"),
    [
        ("2 כוסות קמח", "קמח לבן", D(480), "ml"),
        ("½ כפית מלח", "מלח", D("2.5"), "ml"),
        ("3 ביצים", "ביצים L", D(3), "piece"),
        ("200 גרם גבינה", "גבינה", D(200), "g"),
        ('1.5 ק"ג תפוחי אדמה', "תפוחי אדמה", D(1500), "g"),
        ("1,5 ליטר חלב", "חלב", D(1500), "ml"),
        ('250 מ"ל שמנת מתוקה', "שמנת מתוקה", D(250), "ml"),
        ("1 1/2 כוסות סוכר", "סוכר לבן", D(360), "ml"),
        ("1½ כוסות סוכר", "סוכר לבן", D(360), "ml"),
        ("3/4 כוס שמן", "שמן", D(180), "ml"),
        ("כוס וחצי קמח", "קמח לבן", D(360), "ml"),
        ("1 כוס וחצי קמח", "קמח לבן", D(360), "ml"),
        ("2 וחצי כוסות קמח", "קמח לבן", D(600), "ml"),
        ("חצי כוס סוכר", "סוכר לבן", D(120), "ml"),
        ("רבע כוס שמן זית", "שמן זית", D(60), "ml"),
        ("שתי כפות דבש", "דבש", D(30), "ml"),
        ("כף שמן", "שמן", D(15), "ml"),
        ("2-3 כפות סוכר", "סוכר לבן", D(45), "ml"),
        ("2 עד 3 עגבניות", "עגבניות", D(3), "piece"),
        ("כ-200 גרם פטריות", "פטריות", D(200), "g"),
        ("2 שיני שום כתושות", "שום", D(2), "piece"),
        ("1 ראש שום", "שום", D(1), "piece"),
        ("1 צרור פטרוזיליה קצוצה", "פטרוזיליה", D(1), "piece"),
        ("1 גביע שמנת חמוצה", "שמנת חמוצה", D(1), "pack"),
        ("1 חבילת שמרים יבשים", "שמרים יבשים", D(1), "pack"),
        ("2 קופסאות רסק עגבניות", "רסק עגבניות", D(2), "pack"),
        ("1 בצל גדול (כ-200 גרם), קצוץ", "בצל יבש", D(200), "g"),
        ("בצל גדול (כ-200 גרם)", "בצל יבש", D(200), "g"),
        ("100 גרם חמאה רכה או מרגרינה", "חמאה", D(100), "g"),
        ("2 ביצים + 1 חלמון למריחה", "ביצים L", D(2), "piece"),
        ("קמח - 2 כוסות", "קמח לבן", D(480), "ml"),
        ("גבינה לבנה 5%: 250 גרם", "גבינה לבנה 5%", D(250), "g"),
        ("- 4 עגבניות בשלות", "עגבניות", D(4), "piece"),
        ("• 1 כפית כמון", "כמון", D(5), "ml"),
        ("פטרוזיליה", "פטרוזיליה", None, None),
        ("2 כוסות שמן לטיגון", "שמן", D(480), "ml"),
        ("1 כפית מלח (או לפי הטעם)", "מלח", D(5), "ml"),
    ],
)
def test_ingredient_lines(line, name, amount, dim) -> None:
    got = parse_ingredient(line)
    assert isinstance(got, Ingredient), got
    assert got.name == name
    assert (got.amount if got.amount is None else got.amount.quantize(D("0.01"))) == (
        amount if amount is None else amount.quantize(D("0.01"))
    )
    assert got.dim == dim


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("מלח לפי הטעם", "to_taste"),
        ("מלח ופלפל שחור", "to_taste"),
        ("קורט מלח", "to_taste"),
        ("מעט שמן", "to_taste"),
        ("שמן לטיגון", "to_taste"),
        ("שומשום לקישוט", "to_taste"),
        ("2 כוסות מים", "not_a_product"),
        ("מים רותחים", "not_a_product"),
        ("קוביות קרח", "not_a_product"),
        ("פלפל צ'ילי (לא חובה)", "optional"),
        ("50 גרם אגוזים, אופציונלי", "optional"),
    ],
)
def test_lines_left_to_the_user(line, reason) -> None:
    got = parse_ingredient(line)
    assert isinstance(got, Unresolved) and got.reason == reason and got.line == line


def test_empty_lines_and_sub_headers_are_skipped() -> None:
    assert parse_ingredient("   ") is None
    assert parse_ingredient("לבצק:") is None


def test_mineral_water_is_a_product() -> None:
    got = parse_ingredient("1 בקבוק מים מינרליים")
    assert isinstance(got, Ingredient) and got.name == "מים מינרליים"


# --- whole recipes -------------------------------------------------------------------------------


TEXT = """מרק עדשים
6 מנות
מצרכים:
2 כוסות עדשים כתומות
1 בצל
לתיבול:
1 כפית כמון
מלח לפי הטעם
אופן ההכנה:
מטגנים את הבצל 5 דקות ומוסיפים 2 כוסות מים.
"""


def test_text_with_headers() -> None:
    r = rp.parse_recipe_text(TEXT)
    assert r.title == "מרק עדשים" and r.servings == 6
    assert [i.name for i in r.ingredients] == ["עדשים כתומות", "בצל יבש", "כמון"]
    assert r.unresolved == ["מלח לפי הטעם"]  # the method's "2 כוסות מים" is not read


def test_text_without_headers_takes_the_first_line_as_title() -> None:
    r = rp.parse_recipe_text(
        "סלט ירקות\n3 עגבניות\n2 מלפפונים\nשמן זית\nמערבבים הכל היטב ומגישים מיד עם לחם טרי"
    )
    assert r.title == "סלט ירקות" and r.servings is None
    assert [i.name for i in r.ingredients] == ["עגבניות", "מלפפונים", "שמן זית"]


@pytest.mark.parametrize(
    ("value", "servings"),
    [
        (4, 4),
        ("4", 4),
        ("6 מנות", 6),
        (["8", "8 servings"], 8),
        ("ל-4 סועדים", 4),
        ("מספר מנות: 10", 10),
        ("12 servings", 12),
        ("כ-30 עוגיות", None),
        (None, None),
        (0, None),
        (True, None),
        ("500", None),
    ],
)
def test_servings(value, servings) -> None:
    assert rp.parse_servings(value) == servings


def _page(jsonld: object, body: str = "") -> str:
    return (
        f'<html><head><title>כותרת הדף</title><script type="application/ld+json">'
        f"{json.dumps(jsonld, ensure_ascii=False)}</script></head><body>{body}</body></html>"
    )


def test_jsonld_recipe_variants() -> None:
    node = {
        "@type": ["Recipe", "NewsArticle"],
        "name": "פנקייק &amp; סירופ",
        "recipeYield": ["4", "4 מנות"],
        "recipeIngredient": ["1 כוס קמח", "<b>2</b> ביצים", "קורט מלח"],
    }
    r = rp.recipe_from_html(
        _page({"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, node]})
    )
    assert r.title == "פנקייק & סירופ" and r.servings == 4
    assert [(i.name, i.amount) for i in r.ingredients] == [("קמח לבן", D(240)), ("ביצים L", D(2))]
    assert r.unresolved == ["קורט מלח"]
    assert (
        rp.recipe_from_html(
            _page([{"@type": "Recipe", "name": "x", "recipeIngredient": "1 כוס סוכר"}])
        )
        .ingredients[0]
        .name
        == "סוכר לבן"
    )


def test_broken_jsonld_falls_back_to_the_text_under_the_header() -> None:
    page = (
        '<html><head><meta property="og:title" content="עוגה"><script type="application/ld+json">{oops'
        "</script></head><body><p>מבוא עם 3 כוסות של השראה</p><h3>המצרכים</h3><ul><li>1 כוס קמח</li>"
        "<li>2 ביצים</li></ul><h3>אופן ההכנה</h3><p>1 כוס סוכר נוספת לקישוט</p></body></html>"
    )
    r = rp.recipe_from_html(page)
    assert r.title == "עוגה"
    assert [i.name for i in r.ingredients] == ["קמח לבן", "ביצים L"]


def test_a_page_without_an_ingredients_header_yields_nothing() -> None:
    r = rp.recipe_from_html("<html><body><p>2 כוסות קמח</p><p>3 ביצים</p></body></html>")
    assert r.ingredients == [] and r.unresolved == []


def test_scale_and_merge() -> None:
    r = rp.parse_recipe_text("מצרכים (4 מנות):\n2 ביצים\n1 כוס קמח\n1 ביצה\nמלח לפי הטעם")
    r.ingredients = rp.merge(r.ingredients)
    assert [(i.name, i.amount) for i in r.ingredients] == [("ביצים L", D(3)), ("קמח לבן", D(240))]
    assert r.ingredients[0].line == "2 ביצים + 1 ביצה"
    scaled, servings = rp.scale(r, 6)
    assert servings == 6 and [i.amount for i in scaled.ingredients] == [D("4.5"), D(360)]
    same, servings = rp.scale(r, None)
    assert servings == 4 and same is r
    r.servings = None
    unscaled, servings = rp.scale(r, 6)
    assert servings is None and unscaled.ingredients[0].amount == D(3)


# --- basket quantities ---------------------------------------------------------------------------


def ing(line: str) -> Ingredient:
    got = parse_ingredient(line)
    assert isinstance(got, Ingredient)
    return got


@pytest.mark.parametrize(
    ("line", "base", "pack", "unit", "quantity", "kg", "converted"),
    [
        # by weight: kilograms, rounded up to 50 g
        ('1 ק"ג חזה עוף', "kg", None, None, D("1.00"), True, True),
        ("320 גרם סלמון", "kg", None, None, D("0.35"), True, True),
        ("3 עגבניות", "kg", None, None, D("0.40"), True, True),  # 3 x 130 g
        ("2 שיני שום", "kg", None, None, D("0.05"), True, True),
        ("1 כוס עגבניות שרי", "kg", None, None, D(1), True, False),  # no density: confirm
        ("2 חזה עוף", "kg", None, None, D(1), True, False),  # no piece weight: confirm
        ("עגבניות", "kg", None, None, D(1), True, True),  # no amount: like /parse-list
        # packaged by mass: cups through the density table, whole packs
        ("2 כוסות קמח", "100g", D(1000), "g", D(1), False, True),  # 280 g
        ("8 כוסות קמח", "100g", D(1000), "g", D(2), False, True),  # 1120 g
        ("1 כפית מלח", "100g", D(1000), "g", D(1), False, True),
        ("1 כוס אגוזי מלך", "100g", D(200), "g", D(1), False, False),  # unknown density
        ("600 גרם ספגטי", "100g", D(500), "g", D(2), False, True),
        ("600 גרם ספגטי", "100g", None, None, D(1), False, False),  # no pack size
        ("3 פרוסות גבינה צהובה", "100g", D(200), "g", D(1), False, False),  # slices are not packs
        ("2 חמאה", "100g", D(200), "g", D(2), False, True),  # a bare count is packs
        ("2 גביעים שמנת חמוצה", "100g", D(200), "g", D(2), False, True),
        # liquids
        ("3 כוסות חלב", "100ml", D(1000), "ml", D(1), False, True),  # 720 ml
        ("5 כוסות חלב", "100ml", D(1000), "ml", D(2), False, True),  # 1200 ml
        ("300 גרם שמנת מתוקה", "100ml", D(250), "ml", D(2), False, True),  # density 1 for liquids
        ("1 כוס שמן", "100ml", D(1000), "ml", D(1), False, True),
        # counted goods
        ("14 ביצים", "unit", D(12), "unit", D(2), False, True),
        ("3 ביצים", "unit", D(12), "unit", D(1), False, True),
        ("2 צרורות פטרוזיליה", "unit", D(1), "unit", D(2), False, True),
        ("100 גרם ביצים", "unit", D(12), "unit", D(1), False, False),
    ],
)
def test_basket_quantity(line, base, pack, unit, quantity, kg, converted) -> None:
    q = basket_quantity(ing(line), base, pack, unit)
    assert (q.quantity, q.unit == "kg", q.converted) == (quantity, kg, converted)


def test_density_falls_back_to_the_canonical_name() -> None:
    q = basket_quantity(ing("1 כוס אורז לבן"), "100g", D(1000), "g", canonical_name="אורז פרסי")
    assert q.converted and q.quantity == 1


def test_quantities_are_capped() -> None:
    assert basket_quantity(ing("500 קופסאות רסק"), "100g", D(100), "g").quantity == rp.MAX_PACKS
