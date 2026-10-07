"""Build the SYNTHETIC gold set for matching evaluation (issue #38).

    uv run python data/gold/build_gold.py          # writes gold_catalog.yaml and gold_pairs.csv

Everything here is a placeholder generated from templates, not real chain data. The item names
imitate the way Israeli chains write names in their transparency files (brand, fat percent,
fresh/frozen, pack size, abbreviations like ל' and ק"ג, word order changes), and the labels are
computed from the template's ground truth with the D4 semantics:

* exact      the item's barcode is a reference barcode of the canonical
* any_brand  same product type and every critical attribute equal; soft attributes equal
* close      same product type and critical attributes; a soft attribute (pack size, flavor) differs
* no_match   different product type or any critical attribute differs (3% vs 1%, fresh vs frozen,
             soy vs almond, cola vs cola zero, tuna in oil vs in water, ...)

Every item is paired with its own canonical, its hard negatives and one random canonical of the
same department, so the set is rich in hard negatives. "Orphan" items (goat milk, smoked salmon,
rice drink, ...) have no canonical at all and are paired only as no_match.

Base boundary (issue #102): the plant drinks are separate product types, so the type alone
already vetoes soy against almond. ``BASE_SPECS`` add two plant yogurts that share one product
type and differ only by their ``base`` (soy, coconut), so a soy yogurt paired with the coconut
yogurt is a no_match that only the ``base`` critical key can catch. They are generated after
everything else with their own random stream, so adding them left every earlier pair unchanged.

Replace with real items labeled by a human as soon as real chain items are loaded: the numbers
measured on this set say the pipeline works end to end, not that it reaches 98% precision on
real data. Deterministic: the same seed always produces the same files.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any

import yaml

SEED = 20261007
HERE = Path(__file__).resolve().parent

# --- taxonomy -----------------------------------------------------------------------------------

TAXONOMY: list[tuple[str, str | None, int, str, str]] = [
    ("dairy", None, 1, "חלב, ביצים ומוצרי חלב", "Dairy and eggs"),
    ("dairy.milk", "dairy", 2, "חלב", "Milk"),
    ("dairy.cottage", "dairy", 2, "קוטג'", "Cottage cheese"),
    ("dairy.white_cheese", "dairy", 2, "גבינה לבנה", "White cheese"),
    ("dairy.yellow_cheese", "dairy", 2, "גבינה צהובה", "Yellow cheese"),
    ("dairy.yogurt", "dairy", 2, "יוגורט", "Yogurt"),
    ("dairy.butter_cream", "dairy", 2, "חמאה ושמנת", "Butter and cream"),
    ("dairy.eggs", "dairy", 2, "ביצים", "Eggs"),
    ("dairy.plant_drinks", "dairy", 2, "משקאות צמחיים", "Plant-based drinks"),
    ("meat_fish", None, 1, "בשר, עוף ודגים", "Meat, poultry and fish"),
    ("meat_fish.fish", "meat_fish", 2, "דגים", "Fish"),
    ("meat_fish.poultry", "meat_fish", 2, "עוף", "Poultry"),
    ("meat_fish.beef", "meat_fish", 2, "בקר", "Beef"),
    ("produce", None, 1, "פירות וירקות", "Fruit and vegetables"),
    ("produce.vegetables", "produce", 2, "ירקות", "Vegetables"),
    ("produce.fruit", "produce", 2, "פירות", "Fruit"),
    ("bakery", None, 1, "לחם ומאפים", "Bread and bakery"),
    ("bakery.bread", "bakery", 2, "לחם", "Bread"),
    ("pantry", None, 1, "מזווה", "Pantry"),
    ("pantry.grains", "pantry", 2, "אורז ודגנים", "Rice and grains"),
    ("pantry.pasta", "pantry", 2, "פסטה", "Pasta"),
    ("pantry.baking", "pantry", 2, "אפייה", "Baking"),
    ("pantry.oil", "pantry", 2, "שמן", "Oil"),
    ("pantry.canned", "pantry", 2, "שימורים", "Canned food"),
    ("pantry.spreads", "pantry", 2, "ממרחים", "Spreads"),
    ("pantry.coffee", "pantry", 2, "קפה", "Coffee"),
    ("pantry.snacks", "pantry", 2, "חטיפים", "Snacks"),
    ("beverages", None, 1, "משקאות", "Beverages"),
    ("beverages.soft", "beverages", 2, "משקאות קלים", "Soft drinks"),
    ("beverages.water", "beverages", 2, "מים", "Water"),
    ("beverages.juice", "beverages", 2, "מיצים", "Juice"),
    ("household", None, 1, "ניקיון וחד פעמי", "Household"),
    ("household.paper", "household", 2, "מוצרי נייר", "Paper goods"),
    ("household.cleaning", "household", 2, "ניקיון", "Cleaning"),
]

# product_type -> (critical keys, soft keys)
RULES: dict[str, tuple[list[str], list[str]]] = {
    "milk": (["fat_pct", "state"], ["pack_size", "brand"]),
    "chocolate_milk": (["fat_pct"], ["pack_size", "brand"]),
    "goat_milk": (["fat_pct"], ["pack_size", "brand"]),
    "cottage": (["fat_pct"], ["pack_size", "brand"]),
    "white_cheese": (["fat_pct"], ["pack_size", "brand"]),
    "yellow_cheese": (["fat_pct"], ["pack_size", "brand"]),
    "yogurt": (["fat_pct"], ["pack_size", "flavor", "brand"]),
    "butter": ([], ["pack_size", "brand"]),
    "sweet_cream": (["fat_pct"], ["pack_size", "brand"]),
    "sour_cream": (["fat_pct"], ["pack_size", "brand"]),
    "eggs": ([], ["pack_size", "brand"]),
    "soy_drink": (["base"], ["pack_size", "flavor", "brand"]),
    "almond_drink": (["base"], ["pack_size", "flavor", "brand"]),
    "oat_drink": (["base"], ["pack_size", "flavor", "brand"]),
    "rice_drink": (["base"], ["pack_size", "flavor", "brand"]),
    "plant_yogurt": (["base"], ["pack_size", "flavor", "brand"]),
    "salmon": (["state"], ["pack_size", "brand"]),
    "smoked_salmon": ([], ["pack_size", "brand"]),
    "tilapia": (["state"], ["pack_size", "brand"]),
    "chicken_breast": (["state"], ["pack_size", "brand"]),
    "ground_beef": (["state", "fat_pct"], ["pack_size", "brand"]),
    "tomato": ([], []),
    "cherry_tomato": ([], ["pack_size"]),
    "cucumber": ([], []),
    "potato": ([], []),
    "onion": ([], []),
    "banana": ([], []),
    "bread": (["flavor"], ["pack_size", "brand"]),
    "rice": (["flavor"], ["pack_size", "brand"]),
    "pasta": ([], ["flavor", "pack_size", "brand"]),
    "sugar": (["flavor"], ["pack_size", "brand"]),
    "flour": (["flavor"], ["pack_size", "brand"]),
    "olive_oil": ([], ["pack_size", "brand"]),
    "canola_oil": ([], ["pack_size", "brand"]),
    "tuna": (["flavor"], ["pack_size", "brand"]),
    "canned_corn": ([], ["pack_size", "brand"]),
    "hummus_spread": ([], ["pack_size", "brand"]),
    "tahini": ([], ["pack_size", "brand"]),
    "instant_coffee": ([], ["pack_size", "brand"]),
    "turkish_coffee": ([], ["pack_size", "brand"]),
    "peanut_snack": ([], ["pack_size", "brand"]),
    "cola": ([], ["pack_size", "brand"]),
    "cola_zero": ([], ["pack_size", "brand"]),
    "mineral_water": ([], ["pack_size", "brand"]),
    "orange_juice": ([], ["pack_size", "brand"]),
    "toilet_paper": ([], ["pack_size", "brand"]),
    "dish_soap": ([], ["pack_size", "brand"]),
}

# Fallback-extractor keywords (issue #25 extraction replaces this on real items). Longest wins.
LEXICON_PT: dict[str, list[str]] = {
    "milk": ["חלב", "חלב טרי", "ח. טרי", "חלב בקרטון", "חלב בשקית"],
    "chocolate_milk": ["שוקו", "חלב שוקו"],
    "goat_milk": ["חלב עזים"],
    "cottage": ["קוטג'", "קוטג", "גבינת קוטג'"],
    "white_cheese": ["גבינה לבנה", "גבינה לבנה רכה"],
    "yellow_cheese": ["גבינה צהובה", "גבינה צהובה פרוסה", "עמק"],
    "yogurt": ["יוגורט"],
    "butter": ["חמאה"],
    "sweet_cream": ["שמנת מתוקה", "שמנת להקצפה"],
    "sour_cream": ["שמנת חמוצה"],
    "eggs": ["ביצים", "ביצי חופש"],
    "soy_drink": ["משקה סויה", "סויה"],
    "almond_drink": ["משקה שקדים", "שקדים"],
    "oat_drink": ["משקה שיבולת שועל", "שיבולת שועל", "משקה שיבולת"],
    "rice_drink": ["משקה אורז"],
    "plant_yogurt": ["יוגורט סויה", "יוגורט קוקוס", "יוגורט שקדים"],
    "salmon": ["סלמון", "פילה סלמון", "נתחי סלמון"],
    "smoked_salmon": ["סלמון מעושן"],
    "tilapia": ["אמנון", "פילה אמנון"],
    "chicken_breast": ["חזה עוף", "פילה עוף", "שניצל עוף"],
    "ground_beef": ["בשר טחון", "בקר טחון"],
    "tomato": ["עגבניה", "עגבנייה", "עגבניות"],
    "cherry_tomato": ["עגבניות שרי", "עגבניה שרי", "שרי"],
    "cucumber": ["מלפפון", "מלפפונים"],
    "potato": ["תפוח אדמה", "תפוחי אדמה", 'תפו"א'],
    "onion": ["בצל", "בצל יבש", "בצלים"],
    "banana": ["בננה", "בננות"],
    "bread": ["לחם", "לחם פרוס", "לחם אחיד"],
    "rice": ["אורז"],
    "pasta": ["פסטה", "ספגטי", "פנה", "פוזילי"],
    "sugar": ["סוכר"],
    "flour": ["קמח"],
    "olive_oil": ["שמן זית"],
    "canola_oil": ["שמן קנולה"],
    "tuna": ["טונה", "נתחי טונה"],
    "canned_corn": ["תירס", "תירס מתוק", "גרעיני תירס"],
    "hummus_spread": ["חומוס", "ממרח חומוס", "סלט חומוס"],
    "tahini": ["טחינה", "טחינה גולמית"],
    "instant_coffee": ["קפה נמס", "נמס"],
    "turkish_coffee": ["קפה טורקי", "קפה שחור", "טורקי"],
    "peanut_snack": ["במבה", "חטיף בוטנים"],
    "cola": ["קולה", "קוקה קולה", "פפסי"],
    "cola_zero": ["קולה זירו", "קוקה קולה זירו", "פפסי מקס", "קולה דיאט"],
    "mineral_water": ["מים מינרליים", "מים"],
    "orange_juice": ["מיץ תפוזים", "תפוזים"],
    "toilet_paper": ["נייר טואלט"],
    "dish_soap": ["סבון כלים", "נוזל כלים"],
}
# Attributes a product type implies (Attributes.base, issue #92), applied by the fallback
# extractor when the name does not state them.
LEXICON_IMPLIED: dict[str, dict[str, str]] = {
    "soy_drink": {"base": "soy"},
    "almond_drink": {"base": "almond"},
    "oat_drink": {"base": "oat"},
    "rice_drink": {"base": "rice"},
}
# Base keywords, read from the name for these product types (the first one that does not follow
# "בטעם" wins; "יוגורט סויה בטעם קוקוס" is a soy yogurt with a coconut flavor).
LEXICON_BASES: dict[str, list[str]] = {
    "soy": ["סויה"],
    "almond": ["שקדים"],
    "oat": ["שיבולת שועל", "שיבולת"],
    "rice": ["אורז"],
    "coconut": ["קוקוס"],
}
LEXICON_BASE_TYPES = ["soy_drink", "almond_drink", "oat_drink", "rice_drink", "plant_yogurt"]
LEXICON_FLAVORS: dict[str, list[str]] = {
    "white": ["לבן", "לחם לבן", "קמח לבן", "סוכר לבן"],
    "whole_wheat": ["מלא", "חיטה מלאה", "מחיטה מלאה", "קמח מלא"],
    "brown": ["חום", "סוכר חום", "דמררה"],
    "basmati": ["בסמטי"],
    "persian": ["פרסי"],
    "oil": ["בשמן", "בשמן צמחי", "בשמן זית"],
    "water": ["במים"],
    "natural": ["טבעי"],
    "strawberry": ["תות"],
    "vanilla": ["וניל"],
    "coconut": ["בטעם קוקוס"],
    "spaghetti": ["ספגטי"],
    "penne": ["פנה"],
    "fusilli": ["פוזילי"],
}

# --- canonicals and item templates --------------------------------------------------------------
# sizes: (text, amount, unit); the first is the canonical's own pack size.
# variants: (text, overrides of soft/critical truth); the first is the canonical's own.

DAIRY_BRANDS = ["תנובה", "טרה", "שטראוס", "יטבתה", "שופרסל", "רמי לוי", "ויקטורי", "יוחננוף"]
CHEESE_BRANDS = ["תנובה", "שטראוס", "גד", "השחר", "שופרסל", "רמי לוי", "מחלבות גד"]
PLANT_BRANDS = ["אלפרו", "תנובה", "וילי פוד", "שופרסל", "אוטלי", "יטבתה"]
FISH_BRANDS = ["דגי הגליל", "שופרסל", "נורווגיה", "פרש מרקט", "מעדני הים", ""]
POULTRY_BRANDS = ["עוף טוב", "זוגלובק", "מאמא עוף", "שופרסל", "יוחננוף", ""]
PANTRY_BRANDS = ["אסם", "סוגת", "וילי פוד", "שופרסל", "רמי לוי", "מיה", "יכין", "פריניר"]
DRINK_BRANDS = ["קוקה קולה", "פפסי", "שופרסל", "רמי לוי", "נביעות", "עין גדי", "פרימור", "ספרינג"]

L = "ל'"
ML = 'מ"ל'
KG = 'ק"ג'

SPECS: list[dict[str, Any]] = [
    # dairy.milk
    dict(
        slug="milk-3pct-1l",
        tax="dairy.milk",
        name="חלב טרי 3% שומן, 1 ליטר",
        pt="milk",
        bu="100ml",
        crit={"fat_pct": 3, "state": "fresh"},
        soft={"pack_size": 1, "unit": "l"},
        templates=[
            "חלב טרי 3% {b} {s}",
            "חלב {b} 3% {s}",
            "חלב טרי בקרטון 3% {s} {b}",
            "ח. טרי 3% {s} {b}",
            "חלב בשקית 3% {b} {s}",
            "{b} חלב 3% שומן {s}",
        ],
        brands=DAIRY_BRANDS,
        sizes=[("1 ליטר", 1, "l"), (f"1 {L}", 1, "l"), (f"2 {L}", 2, "l"), ("1.5 ליטר", 1.5, "l")],
        neg=["milk-1pct-1l"],
        n=30,
    ),
    dict(
        slug="milk-1pct-1l",
        tax="dairy.milk",
        name="חלב טרי 1% שומן, 1 ליטר",
        pt="milk",
        bu="100ml",
        crit={"fat_pct": 1, "state": "fresh"},
        soft={"pack_size": 1, "unit": "l"},
        templates=[
            "חלב טרי 1% {b} {s}",
            "חלב {b} 1% {s}",
            "חלב דל שומן 1% {s} {b}",
            "ח. טרי 1% {s} {b}",
            "{b} חלב 1% שומן {s}",
        ],
        brands=DAIRY_BRANDS,
        sizes=[("1 ליטר", 1, "l"), (f"1 {L}", 1, "l"), (f"2 {L}", 2, "l")],
        neg=["milk-3pct-1l"],
        n=26,
    ),
    # dairy.cottage: 250 g vs 500 g is a soft difference (close), 5% vs 3% a critical one.
    dict(
        slug="cottage-5pct-250g",
        tax="dairy.cottage",
        name="קוטג' 5%, 250 גרם",
        pt="cottage",
        bu="100g",
        crit={"fat_pct": 5},
        soft={"pack_size": 250, "unit": "g"},
        templates=[
            "קוטג' 5% {b} {s}",
            "גבינת קוטג' 5% {s} {b}",
            "קוטג {b} 5% {s}",
            "{b} קוטג' 5% שומן {s}",
        ],
        brands=CHEESE_BRANDS,
        sizes=[("250 גרם", 250, "g"), ("250 ג'", 250, "g")],
        neg=["cottage-3pct-250g", "cottage-5pct-500g"],
        n=22,
    ),
    dict(
        slug="cottage-5pct-500g",
        tax="dairy.cottage",
        name="קוטג' 5%, 500 גרם",
        pt="cottage",
        bu="100g",
        crit={"fat_pct": 5},
        soft={"pack_size": 500, "unit": "g"},
        templates=["קוטג' 5% {b} {s}", "גבינת קוטג' 5% {s} {b}", "קוטג {b} 5% {s}"],
        brands=CHEESE_BRANDS,
        sizes=[("500 גרם", 500, "g"), ("500 ג'", 500, "g")],
        neg=["cottage-5pct-250g", "cottage-3pct-250g"],
        n=14,
    ),
    dict(
        slug="cottage-3pct-250g",
        tax="dairy.cottage",
        name="קוטג' 3%, 250 גרם",
        pt="cottage",
        bu="100g",
        crit={"fat_pct": 3},
        soft={"pack_size": 250, "unit": "g"},
        templates=["קוטג' 3% {b} {s}", "קוטג' לייט 3% {s} {b}", "קוטג {b} 3% {s}"],
        brands=CHEESE_BRANDS,
        sizes=[("250 גרם", 250, "g"), ("500 גרם", 500, "g")],
        neg=["cottage-5pct-250g"],
        n=16,
    ),
    # dairy.white_cheese
    dict(
        slug="white-cheese-5pct-250g",
        tax="dairy.white_cheese",
        name="גבינה לבנה 5%, 250 גרם",
        pt="white_cheese",
        bu="100g",
        crit={"fat_pct": 5},
        soft={"pack_size": 250, "unit": "g"},
        templates=["גבינה לבנה 5% {b} {s}", "גבינה לבנה רכה 5% {s} {b}", "{b} גבינה לבנה 5% {s}"],
        brands=CHEESE_BRANDS,
        sizes=[("250 גרם", 250, "g"), ("500 גרם", 500, "g")],
        neg=["white-cheese-9pct-250g"],
        n=18,
    ),
    dict(
        slug="white-cheese-9pct-250g",
        tax="dairy.white_cheese",
        name="גבינה לבנה 9%, 250 גרם",
        pt="white_cheese",
        bu="100g",
        crit={"fat_pct": 9},
        soft={"pack_size": 250, "unit": "g"},
        templates=["גבינה לבנה 9% {b} {s}", "גבינה לבנה 9% שומן {s} {b}", "{b} גבינה לבנה 9% {s}"],
        brands=CHEESE_BRANDS,
        sizes=[("250 גרם", 250, "g"), ("500 גרם", 500, "g")],
        neg=["white-cheese-5pct-250g"],
        n=16,
    ),
    # dairy.yellow_cheese
    dict(
        slug="yellow-cheese-28pct-200g",
        tax="dairy.yellow_cheese",
        name="גבינה צהובה פרוסה 28%, 200 גרם",
        pt="yellow_cheese",
        bu="100g",
        crit={"fat_pct": 28},
        soft={"pack_size": 200, "unit": "g"},
        templates=[
            "גבינה צהובה פרוסה 28% {b} {s}",
            "גבינה צהובה 28% {s} {b}",
            "עמק פרוסות 28% {s}",
            "{b} גבינה צהובה 28% {s}",
        ],
        brands=CHEESE_BRANDS,
        sizes=[("200 גרם", 200, "g"), ("400 גרם", 400, "g")],
        neg=["yellow-cheese-9pct-200g"],
        n=18,
    ),
    dict(
        slug="yellow-cheese-9pct-200g",
        tax="dairy.yellow_cheese",
        name="גבינה צהובה פרוסה 9%, 200 גרם",
        pt="yellow_cheese",
        bu="100g",
        crit={"fat_pct": 9},
        soft={"pack_size": 200, "unit": "g"},
        templates=[
            "גבינה צהובה פרוסה 9% {b} {s}",
            "גבינה צהובה לייט 9% {s} {b}",
            "{b} גבינה צהובה 9% {s}",
        ],
        brands=CHEESE_BRANDS,
        sizes=[("200 גרם", 200, "g"), ("400 גרם", 400, "g")],
        neg=["yellow-cheese-28pct-200g"],
        n=14,
    ),
    # dairy.yogurt: flavor is soft (strawberry vs natural is close), fat is critical.
    dict(
        slug="yogurt-3pct-200g",
        tax="dairy.yogurt",
        name="יוגורט טבעי 3%, 200 גרם",
        pt="yogurt",
        bu="100g",
        crit={"fat_pct": 3},
        soft={"pack_size": 200, "unit": "g", "flavor": "natural"},
        templates=["יוגורט {v} 3% {b} {s}", "יוגורט 3% {v} {s} {b}", "{b} יוגורט {v} 3% {s}"],
        brands=DAIRY_BRANDS,
        sizes=[("200 גרם", 200, "g"), ("500 גרם", 500, "g")],
        variants=[("טבעי", {}), ("תות", {"flavor": "strawberry"}), ("וניל", {"flavor": "vanilla"})],
        neg=["yogurt-1.5pct-200g"],
        n=22,
    ),
    dict(
        slug="yogurt-1.5pct-200g",
        tax="dairy.yogurt",
        name="יוגורט טבעי 1.5%, 200 גרם",
        pt="yogurt",
        bu="100g",
        crit={"fat_pct": 1.5},
        soft={"pack_size": 200, "unit": "g", "flavor": "natural"},
        templates=["יוגורט {v} 1.5% {b} {s}", "יוגורט 1.5% {v} {s} {b}", "{b} יוגורט {v} 1.5% {s}"],
        brands=DAIRY_BRANDS,
        sizes=[("200 גרם", 200, "g"), ("500 גרם", 500, "g")],
        variants=[("טבעי", {}), ("תות", {"flavor": "strawberry"})],
        neg=["yogurt-3pct-200g"],
        n=16,
    ),
    # dairy.butter_cream
    dict(
        slug="butter-200g",
        tax="dairy.butter_cream",
        name="חמאה, 200 גרם",
        pt="butter",
        bu="100g",
        crit={},
        soft={"pack_size": 200, "unit": "g"},
        templates=["חמאה {b} {s}", "חמאה 82% {b} {s}", "{b} חמאה רכה {s}"],
        brands=DAIRY_BRANDS,
        sizes=[("200 גרם", 200, "g"), ("100 גרם", 100, "g")],
        neg=["sweet-cream-38pct-250ml"],
        n=14,
    ),
    dict(
        slug="sweet-cream-38pct-250ml",
        tax="dairy.butter_cream",
        name='שמנת מתוקה 38%, 250 מ"ל',
        pt="sweet_cream",
        bu="100ml",
        crit={"fat_pct": 38},
        soft={"pack_size": 250, "unit": "ml"},
        templates=["שמנת מתוקה 38% {b} {s}", "שמנת להקצפה 38% {s} {b}", "{b} שמנת מתוקה 38% {s}"],
        brands=DAIRY_BRANDS,
        sizes=[(f"250 {ML}", 250, "ml"), (f"500 {ML}", 500, "ml")],
        neg=["sour-cream-15pct-200g"],
        n=14,
    ),
    dict(
        slug="sour-cream-15pct-200g",
        tax="dairy.butter_cream",
        name="שמנת חמוצה 15%, 200 גרם",
        pt="sour_cream",
        bu="100g",
        crit={"fat_pct": 15},
        soft={"pack_size": 200, "unit": "g"},
        templates=["שמנת חמוצה 15% {b} {s}", "{b} שמנת חמוצה 15% {s}"],
        brands=DAIRY_BRANDS,
        sizes=[("200 גרם", 200, "g"), ("400 גרם", 400, "g")],
        neg=["sweet-cream-38pct-250ml"],
        n=12,
    ),
    # dairy.eggs
    dict(
        slug="eggs-l-12",
        tax="dairy.eggs",
        name="ביצים L, 12 יחידות",
        pt="eggs",
        bu="unit",
        crit={},
        soft={"pack_size": 12, "unit": "unit"},
        templates=["ביצים L {b} {s}", "ביצים גודל L {s} {b}", "{b} ביצי חופש L {s}"],
        brands=["תנובה", "ביצי הגליל", "שופרסל", "רמי לוי", "משק"],
        sizes=[("12 יח'", 12, "unit"), ("30 יח'", 30, "unit")],
        neg=[],
        n=14,
    ),
    # dairy.plant_drinks: soy vs almond vs oat are different product types, and the base
    # (Attributes.base) is critical as well.
    dict(
        slug="soy-drink-1l",
        tax="dairy.plant_drinks",
        name="משקה סויה, 1 ליטר",
        pt="soy_drink",
        bu="100ml",
        crit={"base": "soy"},
        soft={"pack_size": 1, "unit": "l", "flavor": "natural"},
        templates=["משקה סויה {v} {b} {s}", "{b} משקה סויה {v} {s}", "סויה {b} {v} {s}"],
        brands=PLANT_BRANDS,
        sizes=[("1 ליטר", 1, "l"), (f"1 {L}", 1, "l"), (f"2 {L}", 2, "l")],
        variants=[("", {}), ("וניל", {"flavor": "vanilla"})],
        neg=["almond-drink-1l", "oat-drink-1l"],
        n=20,
    ),
    dict(
        slug="almond-drink-1l",
        tax="dairy.plant_drinks",
        name="משקה שקדים, 1 ליטר",
        pt="almond_drink",
        bu="100ml",
        crit={"base": "almond"},
        soft={"pack_size": 1, "unit": "l", "flavor": "natural"},
        templates=["משקה שקדים {v} {b} {s}", "{b} משקה שקדים {v} {s}", "שקדים {b} משקה {s}"],
        brands=PLANT_BRANDS,
        sizes=[("1 ליטר", 1, "l"), (f"1 {L}", 1, "l")],
        variants=[("", {}), ("וניל", {"flavor": "vanilla"})],
        neg=["soy-drink-1l", "oat-drink-1l"],
        n=18,
    ),
    dict(
        slug="oat-drink-1l",
        tax="dairy.plant_drinks",
        name="משקה שיבולת שועל, 1 ליטר",
        pt="oat_drink",
        bu="100ml",
        crit={"base": "oat"},
        soft={"pack_size": 1, "unit": "l", "flavor": "natural"},
        templates=[
            "משקה שיבולת שועל {b} {s}",
            "{b} משקה שיבולת שועל {s}",
            "שיבולת שועל משקה {b} {s}",
        ],
        brands=PLANT_BRANDS,
        sizes=[("1 ליטר", 1, "l"), (f"1 {L}", 1, "l")],
        neg=["soy-drink-1l", "almond-drink-1l"],
        n=14,
    ),
    # meat_fish.fish: fresh vs frozen is critical.
    dict(
        slug="salmon-fillet-fresh",
        tax="meat_fish.fish",
        name="פילה סלמון טרי",
        pt="salmon",
        bu="100g",
        crit={"state": "fresh"},
        soft={},
        templates=[
            "פילה סלמון טרי {b} {s}",
            "סלמון טרי {b} {s}",
            "פילה סלמון נורבגי טרי {s}",
            "נתחי סלמון טריים {b} {s}",
            "פילה סלמון {b} {s}",
        ],
        brands=FISH_BRANDS,
        sizes=[("400 גרם", 400, "g"), ('1 ק"ג', 1, "kg"), ("", None, None)],
        neg=["salmon-fillet-frozen"],
        n=20,
    ),
    dict(
        slug="salmon-fillet-frozen",
        tax="meat_fish.fish",
        name="פילה סלמון קפוא",
        pt="salmon",
        bu="100g",
        crit={"state": "frozen"},
        soft={},
        templates=[
            "פילה סלמון קפוא {b} {s}",
            "סלמון קפוא {b} {s}",
            "נתחי סלמון קפואים {b} {s}",
            "פילה סלמון מוקפא {s} {b}",
        ],
        brands=FISH_BRANDS,
        sizes=[("800 גרם", 800, "g"), (f"1 {KG}", 1, "kg"), ("400 גרם", 400, "g")],
        neg=["salmon-fillet-fresh"],
        n=20,
    ),
    dict(
        slug="tilapia-fillet-frozen",
        tax="meat_fish.fish",
        name="פילה אמנון קפוא",
        pt="tilapia",
        bu="100g",
        crit={"state": "frozen"},
        soft={},
        templates=["פילה אמנון קפוא {b} {s}", "אמנון קפוא {b} {s}", "פילה אמנון מוקפא {s}"],
        brands=FISH_BRANDS,
        sizes=[(f"1 {KG}", 1, "kg"), ("800 גרם", 800, "g")],
        neg=["salmon-fillet-frozen"],
        n=12,
    ),
    # meat_fish.poultry and beef
    dict(
        slug="chicken-breast-fresh",
        tax="meat_fish.poultry",
        name="חזה עוף טרי",
        pt="chicken_breast",
        bu="100g",
        crit={"state": "fresh"},
        soft={},
        templates=[
            "חזה עוף טרי {b} {s}",
            "פילה עוף טרי {b} {s}",
            "חזה עוף טרי בטרש {s}",
            "שניצל עוף טרי {b} {s}",
        ],
        brands=POULTRY_BRANDS,
        sizes=[(f"1 {KG}", 1, "kg"), ("500 גרם", 500, "g")],
        neg=["chicken-breast-frozen"],
        n=18,
    ),
    dict(
        slug="chicken-breast-frozen",
        tax="meat_fish.poultry",
        name="חזה עוף קפוא",
        pt="chicken_breast",
        bu="100g",
        crit={"state": "frozen"},
        soft={},
        templates=["חזה עוף קפוא {b} {s}", "פילה עוף קפוא {b} {s}", "חזה עוף מוקפא {s} {b}"],
        brands=POULTRY_BRANDS,
        sizes=[(f"1 {KG}", 1, "kg"), (f"2 {KG}", 2, "kg")],
        neg=["chicken-breast-fresh"],
        n=16,
    ),
    dict(
        slug="ground-beef-fresh-15pct",
        tax="meat_fish.beef",
        name="בשר בקר טחון טרי 15%",
        pt="ground_beef",
        bu="100g",
        crit={"state": "fresh", "fat_pct": 15},
        soft={},
        templates=[
            "בשר טחון טרי 15% {b} {s}",
            "בקר טחון טרי 15% שומן {s}",
            "בשר בקר טחון טרי 15% {b} {s}",
        ],
        brands=["טיב טעם", "שופרסל", "אדום אדום", "יוחננוף", ""],
        sizes=[("500 גרם", 500, "g"), (f"1 {KG}", 1, "kg")],
        neg=["ground-beef-frozen-15pct"],
        n=12,
    ),
    dict(
        slug="ground-beef-frozen-15pct",
        tax="meat_fish.beef",
        name="בשר בקר טחון קפוא 15%",
        pt="ground_beef",
        bu="100g",
        crit={"state": "frozen", "fat_pct": 15},
        soft={},
        templates=[
            "בשר טחון קפוא 15% {b} {s}",
            "בקר טחון קפוא 15% {s}",
            "בשר בקר טחון מוקפא 15% {b} {s}",
        ],
        brands=["סוגת", "שופרסל", "אדום אדום", "יוחננוף", ""],
        sizes=[("500 גרם", 500, "g"), (f"1 {KG}", 1, "kg")],
        neg=["ground-beef-fresh-15pct"],
        n=12,
    ),
    # produce: weighed, per kg
    dict(
        slug="tomato",
        tax="produce.vegetables",
        name="עגבניה",
        pt="tomato",
        bu="kg",
        crit={},
        soft={},
        templates=[
            "עגבניה {b}",
            "עגבניות במשקל",
            "עגבנייה טריה",
            'עגבניה לק"ג {b}',
            "עגבניות {b}",
            "עגבניה אשכולות",
        ],
        brands=["", "מובחר", "ארוז", "אורגני"],
        sizes=[("", None, None)],
        weighed=True,
        neg=["cherry-tomato"],
        n=12,
    ),
    dict(
        slug="cherry-tomato",
        tax="produce.vegetables",
        name="עגבניות שרי",
        pt="cherry_tomato",
        bu="kg",
        crit={},
        soft={},
        templates=["עגבניות שרי {b}", "עגבניה שרי במשקל", "שרי אדום {b}", "עגבניות שרי תמר {b}"],
        brands=["", "מובחר", "ארוז"],
        sizes=[("", None, None)],
        weighed=True,
        neg=["tomato"],
        n=10,
    ),
    dict(
        slug="cucumber",
        tax="produce.vegetables",
        name="מלפפון",
        pt="cucumber",
        bu="kg",
        crit={},
        soft={},
        templates=["מלפפון {b}", "מלפפונים במשקל", "מלפפון טרי", 'מלפפון לק"ג {b}'],
        brands=["", "מובחר", "אורגני"],
        sizes=[("", None, None)],
        weighed=True,
        neg=["tomato"],
        n=9,
    ),
    dict(
        slug="potato",
        tax="produce.vegetables",
        name="תפוח אדמה",
        pt="potato",
        bu="kg",
        crit={},
        soft={},
        templates=["תפוח אדמה {b}", "תפוחי אדמה במשקל", 'תפו"א לבן {b}', "תפוח אדמה אדום"],
        brands=["", "מובחר", "ארוז"],
        sizes=[("", None, None)],
        weighed=True,
        neg=["onion"],
        n=9,
    ),
    dict(
        slug="onion",
        tax="produce.vegetables",
        name="בצל יבש",
        pt="onion",
        bu="kg",
        crit={},
        soft={},
        templates=["בצל יבש {b}", "בצל במשקל", "בצל לבן {b}", "בצלים יבשים"],
        brands=["", "מובחר", "ארוז"],
        sizes=[("", None, None)],
        weighed=True,
        neg=["potato"],
        n=8,
    ),
    dict(
        slug="banana",
        tax="produce.fruit",
        name="בננה",
        pt="banana",
        bu="kg",
        crit={},
        soft={},
        templates=["בננה {b}", "בננות במשקל", "בננה מובחרת", 'בננה לק"ג {b}'],
        brands=["", "אורגני", "ארוז"],
        sizes=[("", None, None)],
        weighed=True,
        neg=[],
        n=8,
    ),
    # bakery: white vs whole wheat is critical (flavor = variety)
    dict(
        slug="bread-white-sliced-750g",
        tax="bakery.bread",
        name="לחם לבן פרוס, 750 גרם",
        pt="bread",
        bu="100g",
        crit={"flavor": "white"},
        soft={"pack_size": 750, "unit": "g"},
        templates=["לחם לבן פרוס {b} {s}", "לחם אחיד לבן {s} {b}", "{b} לחם לבן {s}"],
        brands=["אנג'ל", "ברמן", "דוידוביץ", "שופרסל", "אחדות"],
        sizes=[("750 גרם", 750, "g"), ("500 גרם", 500, "g")],
        neg=["bread-whole-wheat-750g"],
        n=16,
    ),
    dict(
        slug="bread-whole-wheat-750g",
        tax="bakery.bread",
        name="לחם מחיטה מלאה, 750 גרם",
        pt="bread",
        bu="100g",
        crit={"flavor": "whole_wheat"},
        soft={"pack_size": 750, "unit": "g"},
        templates=["לחם מחיטה מלאה {b} {s}", "לחם חיטה מלאה פרוס {s} {b}", "{b} לחם מלא {s}"],
        brands=["אנג'ל", "ברמן", "דוידוביץ", "שופרסל", "אחדות"],
        sizes=[("750 גרם", 750, "g"), ("500 גרם", 500, "g")],
        neg=["bread-white-sliced-750g"],
        n=14,
    ),
    # pantry
    dict(
        slug="rice-basmati-1kg",
        tax="pantry.grains",
        name='אורז בסמטי, 1 ק"ג',
        pt="rice",
        bu="100g",
        crit={"flavor": "basmati"},
        soft={"pack_size": 1, "unit": "kg"},
        templates=["אורז בסמטי {b} {s}", "{b} אורז בסמטי הודי {s}", "אורז בסמטי ארוך {s} {b}"],
        brands=PANTRY_BRANDS,
        sizes=[(f"1 {KG}", 1, "kg"), (f"2 {KG}", 2, "kg"), ("500 גרם", 500, "g")],
        neg=["rice-persian-1kg"],
        n=16,
    ),
    dict(
        slug="rice-persian-1kg",
        tax="pantry.grains",
        name='אורז פרסי, 1 ק"ג',
        pt="rice",
        bu="100g",
        crit={"flavor": "persian"},
        soft={"pack_size": 1, "unit": "kg"},
        templates=["אורז פרסי {b} {s}", "{b} אורז פרסי {s}", "אורז פרסי ארוך {s} {b}"],
        brands=PANTRY_BRANDS,
        sizes=[(f"1 {KG}", 1, "kg"), (f"2 {KG}", 2, "kg")],
        neg=["rice-basmati-1kg"],
        n=14,
    ),
    dict(
        slug="pasta-spaghetti-500g",
        tax="pantry.pasta",
        name="ספגטי, 500 גרם",
        pt="pasta",
        bu="100g",
        crit={},
        soft={"pack_size": 500, "unit": "g", "flavor": "spaghetti"},
        templates=["פסטה {v} {b} {s}", "{v} {b} {s}", "{b} פסטה {v} {s}"],
        brands=["אסם", "ברילה", "שופרסל", "דה צ'קו", "רמי לוי"],
        sizes=[("500 גרם", 500, "g"), (f"1 {KG}", 1, "kg")],
        variants=[("ספגטי", {}), ("פנה", {"flavor": "penne"}), ("פוזילי", {"flavor": "fusilli"})],
        neg=[],
        n=18,
    ),
    dict(
        slug="sugar-white-1kg",
        tax="pantry.baking",
        name='סוכר לבן, 1 ק"ג',
        pt="sugar",
        bu="100g",
        crit={"flavor": "white"},
        soft={"pack_size": 1, "unit": "kg"},
        templates=["סוכר לבן {b} {s}", "סוכר {b} לבן {s}", "{b} סוכר לבן מזוקק {s}"],
        brands=["סוגת", "שופרסל", "רמי לוי", "וילי פוד"],
        sizes=[(f"1 {KG}", 1, "kg"), (f"2 {KG}", 2, "kg")],
        neg=["sugar-brown-1kg"],
        n=12,
    ),
    dict(
        slug="sugar-brown-1kg",
        tax="pantry.baking",
        name='סוכר חום, 1 ק"ג',
        pt="sugar",
        bu="100g",
        crit={"flavor": "brown"},
        soft={"pack_size": 1, "unit": "kg"},
        templates=["סוכר חום {b} {s}", "סוכר דמררה {b} {s}", "{b} סוכר חום {s}"],
        brands=["סוגת", "שופרסל", "וילי פוד"],
        sizes=[(f"1 {KG}", 1, "kg"), ("500 גרם", 500, "g")],
        neg=["sugar-white-1kg"],
        n=10,
    ),
    dict(
        slug="flour-white-1kg",
        tax="pantry.baking",
        name='קמח לבן, 1 ק"ג',
        pt="flour",
        bu="100g",
        crit={"flavor": "white"},
        soft={"pack_size": 1, "unit": "kg"},
        templates=["קמח לבן {b} {s}", "קמח חיטה לבן {s} {b}", "{b} קמח לבן מנופה {s}"],
        brands=["סוגת", "שטיבל", "שופרסל", "רמי לוי"],
        sizes=[(f"1 {KG}", 1, "kg"), (f"2 {KG}", 2, "kg")],
        neg=["flour-whole-1kg"],
        n=12,
    ),
    dict(
        slug="flour-whole-1kg",
        tax="pantry.baking",
        name='קמח מלא, 1 ק"ג',
        pt="flour",
        bu="100g",
        crit={"flavor": "whole_wheat"},
        soft={"pack_size": 1, "unit": "kg"},
        templates=["קמח מלא {b} {s}", "קמח חיטה מלאה {s} {b}", "{b} קמח מלא {s}"],
        brands=["סוגת", "שטיבל", "שופרסל"],
        sizes=[(f"1 {KG}", 1, "kg")],
        neg=["flour-white-1kg"],
        n=10,
    ),
    dict(
        slug="olive-oil-750ml",
        tax="pantry.oil",
        name='שמן זית כתית מעולה, 750 מ"ל',
        pt="olive_oil",
        bu="100ml",
        crit={},
        soft={"pack_size": 750, "unit": "ml"},
        templates=["שמן זית כתית מעולה {b} {s}", "שמן זית {b} {s}", "{b} שמן זית כתית {s}"],
        brands=["יד מרדכי", "זיתא", "שופרסל", "עץ הזית", "רמי לוי"],
        sizes=[(f"750 {ML}", 750, "ml"), (f"1 {L}", 1, "l"), (f"500 {ML}", 500, "ml")],
        neg=["canola-oil-1l"],
        n=16,
    ),
    dict(
        slug="canola-oil-1l",
        tax="pantry.oil",
        name="שמן קנולה, 1 ליטר",
        pt="canola_oil",
        bu="100ml",
        crit={},
        soft={"pack_size": 1, "unit": "l"},
        templates=["שמן קנולה {b} {s}", "{b} שמן קנולה {s}", "שמן קנולה טהור {s} {b}"],
        brands=["עץ הזית", "מיה", "שופרסל", "רמי לוי"],
        sizes=[(f"1 {L}", 1, "l"), (f"2 {L}", 2, "l")],
        neg=["olive-oil-750ml"],
        n=12,
    ),
    dict(
        slug="tuna-in-oil-160g",
        tax="pantry.canned",
        name="טונה בשמן, 160 גרם",
        pt="tuna",
        bu="100g",
        crit={"flavor": "oil"},
        soft={"pack_size": 160, "unit": "g"},
        templates=["טונה בשמן {b} {s}", "נתחי טונה בשמן צמחי {s} {b}", "{b} טונה בשמן {s}"],
        brands=["סטארקיסט", "פלוגת", "ויליגר", "שופרסל", "רמי לוי"],
        sizes=[("160 גרם", 160, "g"), ("4*160 גרם", 640, "g")],
        neg=["tuna-in-water-160g"],
        n=16,
    ),
    dict(
        slug="tuna-in-water-160g",
        tax="pantry.canned",
        name="טונה במים, 160 גרם",
        pt="tuna",
        bu="100g",
        crit={"flavor": "water"},
        soft={"pack_size": 160, "unit": "g"},
        templates=["טונה במים {b} {s}", "נתחי טונה במים {s} {b}", "{b} טונה במים ומלח {s}"],
        brands=["סטארקיסט", "פלוגת", "ויליגר", "שופרסל"],
        sizes=[("160 גרם", 160, "g"), ("4*160 גרם", 640, "g")],
        neg=["tuna-in-oil-160g"],
        n=14,
    ),
    dict(
        slug="canned-corn-340g",
        tax="pantry.canned",
        name="תירס מתוק בשימורים, 340 גרם",
        pt="canned_corn",
        bu="100g",
        crit={},
        soft={"pack_size": 340, "unit": "g"},
        templates=["תירס מתוק {b} {s}", "גרעיני תירס {b} {s}", "{b} תירס בשימורים {s}"],
        brands=["יכין", "פרי ניר", "שופרסל", "רמי לוי", "גרין ג'ייאנט"],
        sizes=[("340 גרם", 340, "g"), ("3*340 גרם", 1020, "g")],
        neg=[],
        n=12,
    ),
    dict(
        slug="hummus-spread-400g",
        tax="pantry.spreads",
        name="ממרח חומוס, 400 גרם",
        pt="hummus_spread",
        bu="100g",
        crit={},
        soft={"pack_size": 400, "unit": "g"},
        templates=["חומוס {b} {s}", "ממרח חומוס {b} {s}", "סלט חומוס {b} {s}"],
        brands=["צבר", "אחלה", "שופרסל", "מיקי"],
        sizes=[("400 גרם", 400, "g"), ("750 גרם", 750, "g")],
        neg=["tahini-500g"],
        n=12,
    ),
    dict(
        slug="tahini-500g",
        tax="pantry.spreads",
        name="טחינה גולמית, 500 גרם",
        pt="tahini",
        bu="100g",
        crit={},
        soft={"pack_size": 500, "unit": "g"},
        templates=["טחינה גולמית {b} {s}", "{b} טחינה {s}", "טחינה גולמית משומשום מלא {s} {b}"],
        brands=["הנסיך", "אל ארז", "שופרסל", "הר ברכה"],
        sizes=[("500 גרם", 500, "g"), (f"1 {KG}", 1, "kg")],
        neg=["hummus-spread-400g"],
        n=12,
    ),
    dict(
        slug="instant-coffee-200g",
        tax="pantry.coffee",
        name="קפה נמס, 200 גרם",
        pt="instant_coffee",
        bu="100g",
        crit={},
        soft={"pack_size": 200, "unit": "g"},
        templates=["קפה נמס {b} {s}", "{b} קפה נמס מגורען {s}", "נמס {b} {s}"],
        brands=["עלית", "נסקפה", "שופרסל", "ג'ייקובס"],
        sizes=[("200 גרם", 200, "g"), ("100 גרם", 100, "g")],
        neg=["turkish-coffee-200g"],
        n=12,
    ),
    dict(
        slug="turkish-coffee-200g",
        tax="pantry.coffee",
        name="קפה טורקי, 200 גרם",
        pt="turkish_coffee",
        bu="100g",
        crit={},
        soft={"pack_size": 200, "unit": "g"},
        templates=["קפה טורקי {b} {s}", "קפה שחור טורקי {b} {s}", "{b} קפה טורקי עם הל {s}"],
        brands=["עלית", "לנדוור", "שופרסל", "אליטה"],
        sizes=[("200 גרם", 200, "g"), ("100 גרם", 100, "g")],
        neg=["instant-coffee-200g"],
        n=12,
    ),
    dict(
        slug="peanut-snack-80g",
        tax="pantry.snacks",
        name="חטיף בוטנים (במבה), 80 גרם",
        pt="peanut_snack",
        bu="100g",
        crit={},
        soft={"pack_size": 80, "unit": "g"},
        templates=["במבה {b} {s}", "חטיף בוטנים {b} {s}", "{b} במבה {s}"],
        brands=["אסם", "שופרסל", "רמי לוי"],
        sizes=[("80 גרם", 80, "g"), ("25 גרם", 25, "g")],
        neg=[],
        n=10,
    ),
    # beverages: cola vs cola zero are different product types
    dict(
        slug="cola-1.5l",
        tax="beverages.soft",
        name="משקה קולה, 1.5 ליטר",
        pt="cola",
        bu="100ml",
        crit={},
        soft={"pack_size": 1.5, "unit": "l"},
        templates=["קוקה קולה {s}", "קולה {b} {s}", "פפסי {s}", "משקה קולה {b} {s}"],
        brands=["", "שופרסל", "רמי לוי", "קריסטל"],
        sizes=[("1.5 ליטר", 1.5, "l"), (f"6*1.5 {L}", 9, "l")],
        neg=["cola-zero-1.5l"],
        n=12,
    ),
    dict(
        slug="cola-zero-1.5l",
        tax="beverages.soft",
        name="משקה קולה זירו, 1.5 ליטר",
        pt="cola_zero",
        bu="100ml",
        crit={},
        soft={"pack_size": 1.5, "unit": "l"},
        templates=["קוקה קולה זירו {s}", "קולה זירו {b} {s}", "פפסי מקס {s}", "קולה דיאט {b} {s}"],
        brands=["", "שופרסל", "רמי לוי"],
        sizes=[("1.5 ליטר", 1.5, "l"), (f"6*1.5 {L}", 9, "l")],
        neg=["cola-1.5l"],
        n=12,
    ),
    dict(
        slug="mineral-water-1.5l",
        tax="beverages.water",
        name="מים מינרליים, 1.5 ליטר",
        pt="mineral_water",
        bu="100ml",
        crit={},
        soft={"pack_size": 1.5, "unit": "l"},
        templates=["מים מינרליים {b} {s}", "{b} מים {s}", "מים מינרליים טבעיים {s} {b}"],
        brands=["נביעות", "עין גדי", "מי עדן", "שופרסל", "נסטלה"],
        sizes=[("1.5 ליטר", 1.5, "l"), (f"6*1.5 {L}", 9, "l"), (f"500 {ML}", 500, "ml")],
        neg=[],
        n=14,
    ),
    dict(
        slug="orange-juice-1l",
        tax="beverages.juice",
        name="מיץ תפוזים, 1 ליטר",
        pt="orange_juice",
        bu="100ml",
        crit={},
        soft={"pack_size": 1, "unit": "l"},
        templates=["מיץ תפוזים {b} {s}", "מיץ תפוזים טבעי 100% {b} {s}", "{b} תפוזים מיץ {s}"],
        brands=["פרימור", "ספרינג", "יטבתה", "שופרסל", "תפוזינה"],
        sizes=[("1 ליטר", 1, "l"), (f"2 {L}", 2, "l")],
        neg=[],
        n=14,
    ),
    # household
    dict(
        slug="toilet-paper-32",
        tax="household.paper",
        name="נייר טואלט, 32 גלילים",
        pt="toilet_paper",
        bu="unit",
        crit={},
        soft={"pack_size": 32, "unit": "unit"},
        templates=["נייר טואלט {b} {s}", "{b} נייר טואלט 3 שכבות {s}", "נייר טואלט לבן {s} {b}"],
        brands=["לילי", "סנו", "שופרסל", "טאצ'"],
        sizes=[("32 יח'", 32, "unit"), ("48 יח'", 48, "unit")],
        neg=[],
        n=12,
    ),
    dict(
        slug="dish-soap-750ml",
        tax="household.cleaning",
        name='סבון כלים, 750 מ"ל',
        pt="dish_soap",
        bu="100ml",
        crit={},
        soft={"pack_size": 750, "unit": "ml"},
        templates=["סבון כלים {b} {s}", "נוזל כלים {b} {s}", "{b} סבון כלים לימון {s}"],
        brands=["פיירי", "סנו", "שופרסל", "פריל"],
        sizes=[(f"750 {ML}", 750, "ml"), (f"1 {L}", 1, "l")],
        neg=[],
        n=12,
    ),
]

# Items whose product has no canonical: every pair is no_match. The near canonicals are the
# ones an embedding would most likely confuse them with.
ORPHANS: list[dict[str, Any]] = [
    dict(
        pt="goat_milk",
        texts=["חלב עזים 3% {b} 1 ליטר", "חלב עזים טרי {b} 1 ל'"],
        brands=["", "צוק", "משק"],
        near=["milk-3pct-1l", "milk-1pct-1l"],
        cat="dairy",
        n=6,
    ),
    dict(
        pt="chocolate_milk",
        texts=["שוקו {b} 1 ליטר", "חלב שוקו 1% {b} 1 ל'"],
        brands=["תנובה", "יטבתה", "טרה"],
        near=["milk-1pct-1l", "milk-3pct-1l"],
        cat="dairy",
        n=6,
    ),
    dict(
        pt="rice_drink",
        texts=["משקה אורז {b} 1 ליטר", "משקה אורז טבעי {b} 1 ל'"],
        brands=["אלפרו", "וילי פוד", "שופרסל"],
        near=["soy-drink-1l", "almond-drink-1l", "oat-drink-1l"],
        cat="dairy",
        n=6,
    ),
    dict(
        pt="smoked_salmon",
        texts=["סלמון מעושן {b} 100 גרם", "פרוסות סלמון מעושן {b} 200 גרם"],
        brands=["", "שופרסל", "פרש מרקט"],
        near=["salmon-fillet-fresh", "salmon-fillet-frozen"],
        cat="meat_fish",
        n=6,
    ),
]

# Base boundary (issue #102): one product type, two canonicals that differ only by base.
BASE_SPECS: list[dict[str, Any]] = [
    dict(
        slug="soy-yogurt-400g",
        tax="dairy.yogurt",
        name="יוגורט סויה טבעי, 400 גרם",
        pt="plant_yogurt",
        bu="100g",
        crit={"base": "soy"},
        soft={"pack_size": 400, "unit": "g", "flavor": "natural"},
        templates=[
            "יוגורט סויה {v} {b} {s}",
            "{b} יוגורט סויה {v} {s}",
            "יוגורט סויה טבעי {b} {s}",
        ],
        brands=["אלפרו", "שטראוס", "וילי פוד", "שופרסל"],
        sizes=[("400 גרם", 400, "g"), ("150 גרם", 150, "g")],
        variants=[
            ("", {}),
            ("וניל", {"flavor": "vanilla"}),
            ("בטעם קוקוס", {"flavor": "coconut"}),
        ],  # fmt: skip
        neg=["coconut-yogurt-400g", "yogurt-3pct-200g"],
        n=14,
    ),
    dict(
        slug="coconut-yogurt-400g",
        tax="dairy.yogurt",
        name="יוגורט קוקוס טבעי, 400 גרם",
        pt="plant_yogurt",
        bu="100g",
        crit={"base": "coconut"},
        soft={"pack_size": 400, "unit": "g", "flavor": "natural"},
        templates=[
            "יוגורט קוקוס {v} {b} {s}",
            "{b} יוגורט קוקוס {v} {s}",
            "יוגורט קוקוס טבעי {b} {s}",
        ],
        brands=["אלפרו", "שטראוס", "וילי פוד", "שופרסל"],
        sizes=[("400 גרם", 400, "g"), ("150 גרם", 150, "g")],
        variants=[("", {}), ("וניל", {"flavor": "vanilla"})],
        neg=["soy-yogurt-400g", "yogurt-3pct-200g"],
        n=12,
    ),
]


# --- generation ---------------------------------------------------------------------------------


def _clean(text: str) -> str:
    return " ".join(text.split())


def _qty_base(amount: Any, unit: str | None) -> tuple[str, float] | None:
    if amount is None or unit is None:
        return None
    factor = {"g": ("g", 1), "kg": ("g", 1000), "ml": ("ml", 1), "l": ("ml", 1000),
              "unit": ("unit", 1)}[unit]  # fmt: skip
    return factor[0], round(float(amount) * factor[1], 3)


def label(truth: dict[str, Any], canon: dict[str, Any], barcode: str) -> tuple[str, str]:
    """Gold label of (item truth, canonical) and a short note."""
    if barcode in canon["soft"].get("barcodes", []):
        return "exact", "same barcode"
    if truth["product_type"] != canon["pt"]:
        return "no_match", f"hard negative: product type {truth['product_type']} vs {canon['pt']}"
    for key, value in canon["crit"].items():
        if truth.get(key) != value:
            return "no_match", f"hard negative: {key} {truth.get(key)} vs {value}"
    soft_keys = RULES[canon["pt"]][1]
    diffs = []
    if "pack_size" in soft_keys and "pack_size" in canon["soft"]:
        a = truth.get("pack")
        b = _qty_base(canon["soft"]["pack_size"], canon["soft"].get("unit"))
        if a is not None and b is not None and a != b:
            diffs.append(f"pack size {a[1]:g} vs {b[1]:g} {b[0]}")
    for key in soft_keys:
        if key in {"pack_size", "brand"} or key not in canon["soft"]:
            continue
        if truth.get(key) is not None and truth.get(key) != canon["soft"][key]:
            diffs.append(f"{key} {truth.get(key)} vs {canon['soft'][key]}")
    if diffs:
        return "close", "soft differs: " + "; ".join(diffs)
    return "any_brand", "critical attributes equal"


def build(seed: int = SEED) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rng = random.Random(seed)
    all_specs = [*SPECS, *BASE_SPECS]
    by_slug = {s["slug"]: s for s in all_specs}
    for i, spec in enumerate(all_specs):
        spec["soft"] = dict(spec["soft"])
        spec["soft"]["barcodes"] = [f"7290000{i:05d}0"]
    rows: list[dict[str, Any]] = []
    used_barcodes: set[str] = set()
    seen_text: set[str] = set()
    item_no = 0

    def new_barcode(rng: random.Random) -> str:
        while True:
            code = "729" + "".join(rng.choice("0123456789") for _ in range(10))
            if code not in used_barcodes:
                used_barcodes.add(code)
                return code

    def emit(specs: list[dict[str, Any]], pool: list[dict[str, Any]], rng: random.Random) -> None:
        """Items of ``specs``, each paired with its canonical, its hard negatives and one
        random canonical of the same department drawn from ``pool``."""
        nonlocal item_no
        for spec in specs:
            dept = spec["tax"].split(".")[0]
            variants = spec.get("variants") or [("", {})]
            made = 0
            attempts = 0
            exact_left = 2 if spec["sizes"][0][1] is not None else 0
            while made < spec["n"] and attempts < spec["n"] * 40:
                attempts += 1
                tpl = rng.choice(spec["templates"])
                brand = rng.choice(spec["brands"])
                si = 0 if rng.random() < 0.65 else rng.randrange(len(spec["sizes"]))
                vi = 0 if rng.random() < 0.75 else rng.randrange(len(variants))
                if "{v}" not in tpl:
                    vi = 0  # the template cannot show the variant, so the truth is the default
                size_text, amount, unit = spec["sizes"][si]
                var_text, overrides = variants[vi]
                text = _clean(tpl.format(b=brand, s=size_text, v=var_text))
                if text in seen_text:
                    continue
                seen_text.add(text)
                truth: dict[str, Any] = {"product_type": spec["pt"], **spec["crit"]}
                for key, value in spec["soft"].items():
                    if key not in {"pack_size", "unit", "barcodes"}:
                        truth[key] = value
                truth.update(overrides)
                truth["pack"] = _qty_base(amount, unit)
                if exact_left and si == 0 and vi == 0:
                    barcode = spec["soft"]["barcodes"][0]
                    exact_left -= 1
                else:
                    barcode = new_barcode(rng)
                item_no += 1
                key = f"gold-{item_no:05d}"
                others = [s for s in pool if s["tax"].split(".")[0] == dept
                          and s["slug"] != spec["slug"] and s["slug"] not in spec["neg"]]  # fmt: skip
                compare = [spec["slug"], *spec["neg"]]
                if others:
                    compare.append(rng.choice(others)["slug"])
                for slug in compare:
                    lab, note = label(truth, by_slug[slug], barcode)
                    rows.append(dict(item_key=key, item_text=text, barcode=barcode,
                                     is_weighed=bool(spec.get("weighed")), canonical_slug=slug,
                                     label=lab, category=dept, note=note))  # fmt: skip
                made += 1

    emit(SPECS, SPECS, rng)

    for orphan in ORPHANS:
        made = 0
        attempts = 0
        while made < orphan["n"] and attempts < 200:
            attempts += 1
            text = _clean(rng.choice(orphan["texts"]).format(b=rng.choice(orphan["brands"])))
            if text in seen_text:
                continue
            seen_text.add(text)
            item_no += 1
            key = f"gold-{item_no:05d}"
            barcode = new_barcode(rng)
            for slug in orphan["near"]:
                rows.append(dict(item_key=key, item_text=text, barcode=barcode, is_weighed=False,
                                 canonical_slug=slug, label="no_match", category=orphan["cat"],
                                 note=f"orphan: {orphan['pt']} has no canonical"))  # fmt: skip
            made += 1

    # Own random stream (issue #102), so the pairs above are the same with or without them.
    emit(BASE_SPECS, all_specs, random.Random(seed + 102))

    catalog = {
        "synthetic": True,
        "note": "Synthetic placeholder catalog for the gold set; see data/gold/build_gold.py.",
        "taxonomy": [
            {"id": t[0], "parent_id": t[1], "level": t[2], "name_he": t[3], "name_en": t[4]}
            for t in TAXONOMY
        ],
        "product_type_rules": [
            {"product_type": pt, "critical_keys": ck, "soft_keys": sk}
            for pt, (ck, sk) in RULES.items()
        ],
        "canonicals": [
            {
                "slug": s["slug"],
                "taxonomy_id": s["tax"],
                "display_name_he": s["name"],
                "product_type": s["pt"],
                "base_unit": s["bu"],
                "critical_attrs": s["crit"],
                "soft_attrs": {k: v for k, v in s["soft"].items() if k != "barcodes"},
                "reference_barcodes": s["soft"]["barcodes"],
            }
            for s in all_specs
        ],  # fmt: skip
        "lexicon": {
            "product_types": {
                pt: {
                    "keywords": kws,
                    "taxonomy_id": next(
                        (s["tax"] for s in all_specs if s["pt"] == pt), _orphan_tax(pt)
                    ),
                    **({"implied": LEXICON_IMPLIED[pt]} if pt in LEXICON_IMPLIED else {}),
                }
                for pt, kws in LEXICON_PT.items()
            },  # fmt: skip
            "flavors": LEXICON_FLAVORS,
            "bases": LEXICON_BASES,
            "base_types": LEXICON_BASE_TYPES,
        },
    }
    return catalog, rows


def _orphan_tax(pt: str) -> str | None:
    return {"goat_milk": "dairy.milk", "chocolate_milk": "dairy.milk",
            "rice_drink": "dairy.plant_drinks", "smoked_salmon": "meat_fish.fish"}.get(pt)  # fmt: skip


FIELDS = ["item_key", "item_text", "barcode", "is_weighed", "canonical_slug", "label", "category",
          "note"]  # fmt: skip


def main() -> None:
    catalog, rows = build()
    (HERE / "gold_catalog.yaml").write_text(
        "# GENERATED by data/gold/build_gold.py. SYNTHETIC placeholder, not real chain data.\n"
        + yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    with (HERE / "gold_pairs.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    labels: dict[str, int] = {}
    for r in rows:
        labels[r["label"]] = labels.get(r["label"], 0) + 1
    items = len({r["item_key"] for r in rows})
    canonicals = len(catalog["canonicals"])
    print(f"{len(rows)} pairs, {items} items, {canonicals} canonicals; labels {labels}")


if __name__ == "__main__":
    main()
