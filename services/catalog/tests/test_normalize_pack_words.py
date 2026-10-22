"""Pack counts the real day's names state in words the normalizer did not read (docs/real-day-dry-run.md,
finding 9 and "Unit-price outliers").

Names, Quantity and UnitQty are verbatim from the transparency files of 2026-10-22 (the Shufersal and
Rami Levy rows are in ``services/api/tests/test_unit_outliers_real.py`` with their prices):

* Shufersal prints a roll count as ``32גל`` (cut by its 24-character name width) and as ``32 גליל``
  (singular): the count was not read, so a pack of 32 rolls was priced as one roll.
* Rami Levy prints a six-pack as ``שישית`` (no second yod), Shufersal an eight-pack as ``שמיניית``.
"""

from __future__ import annotations

import pytest

from smartcart_catalog.normalize import clean_name, normalize

# (name, Quantity, UnitQty, base unit, total quantity, pack count)
REAL = [
    ('נייר טואלט פרימ."יש"32גל', 1, "יחידה", "unit", 32, 1),
    ("נייר טואלט מולט 32 גליל", 1, "יחידה", "unit", 32, 1),
    ("נייר טואלט 32 גלילים שמורת טבע", 32, "יחידות", "unit", 32, 1),
    ("שישית מים מינרליים 2ל'", 12, "ליטר", "100ml", 12000, 6),
    ("שמיניית מעדן חלב בטעם שוקולד עם קצפת 133 ג' מילקי", 1, "יחידות", "100g", 1064, 8),
    # one-letter ג on toilet paper is a roll count, cut by the chain's name width (Yohananof, Shufersal)
    ("נייר טואלט מולט 30 ג", 495, "מטרים", "unit", 30, 1),
    ("נייר טואלט פסטל 32ג XPO", 573, "מטרים", "unit", 32, 1),
    ("נייר טואלט 3שכבות32גTNX", 573, "מטרים", "unit", 32, 1),
    ("נייר טואלט לילי פסטל32גל", 552, "מטרים", "unit", 32, 1),
    ('נייר טואלט "יש" 48גלילים', 883, "מטרים", "unit", 48, 1),
    ("מגבות נייר שישיה סוש", 63.48, "מטרים", "unit", 6, 6),
    # a unit cut to two letters (Rami Levy): 1.5 liters, not "1.5"
    ("סודה מי עדן 1.5 לי", 9, "לא ידוע", "100ml", 1500, 1),
]


@pytest.mark.parametrize(
    ("name", "qty", "unit", "base", "total", "packs"), REAL, ids=[r[0] for r in REAL]
)
def test_real_names_with_a_count_the_normalizer_missed(name, qty, unit, base, total, packs) -> None:
    n = normalize({"raw_name": name, "quantity": qty, "unit": unit})
    assert n.base_unit == base
    assert n.total_quantity == total
    assert n.pack_count == packs


def test_a_roll_count_cut_to_two_letters_is_expanded() -> None:
    assert clean_name('נייר טואלט פרימ."יש"32גל') == 'נייר טואלט פרימ."יש"32 גלילים'
    assert clean_name("נייר טואלט 32גל'") == "נייר טואלט 32 גלילים"


@pytest.mark.parametrize(
    "name",
    [
        "ג'ל כביסה מרוכז 1 ל' BLUE BLOSSOM",  # gel: a geresh between the letters
        "גל בר 20 גרם",  # a brand called Gal, no number right before it
        "מגבוני נייר טואלט לח 70 ג",  # wet wipes are not rolls
        "נייר טואלט לח 3*40י XPO",
        'סוכר לבן 1 ק"ג',  # no toilet paper in the name: ג stays a gram
        "פסטה 500 ג",
    ],
)
def test_the_roll_abbreviations_do_not_fire_on_other_words(name) -> None:
    assert "גלילים" not in clean_name(name)


def test_a_single_roll_is_one_unit() -> None:
    n = normalize({"raw_name": "נייר טואלט 1 גליל", "quantity": 1, "unit": "יחידה"})
    assert n.base_unit == "unit" and n.total_quantity == 1
