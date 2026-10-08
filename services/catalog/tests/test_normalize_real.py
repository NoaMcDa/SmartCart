"""Abbreviations and cut names seen in the real chain files (first audit of real items).

Every name is a real item name from ``services/ingest/tests/fixtures/<chain>/real``; the chains
publish them as written here (some cut at a fixed width: 20 characters for Mega, Osher Ad, Rami
Levy and Yohananof, 24 for Shufersal, 40 for Tiv Taam).
"""

from __future__ import annotations

import pytest

from smartcart_catalog.normalize import (
    NAME_LIMITS,
    clean_name,
    is_full_width,
    is_truncated,
)

MEGA = "7290055700007"
OSHER_AD = "7290103152017"
SHUFERSAL = "7290027600007"
KING_STORE = "7290058108879"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('חמאת בוטנים ללת"ס340', "חמאת בוטנים ללא תוספת סוכר340"),  # Shufersal
        ('סוכריות חמאה לל"ס80 ורטר', "סוכריות חמאה ללא סוכר80 ורטר"),  # Shufersal
        ("שוק.מריר לינדט 70% 100ג", "שוקולד מריר לינדט 70% 100ג"),
        ("חט.נייטשר וואלי מעורב5יח", "חטיף נייטשר וואלי מעורב5יח"),
        ("תח. גוף נטרוג'ינה יבש400", "תחליב גוף נטרוג'ינה יבש400"),
        ("מ.כביסה דובי מפנק ירוק1ל", "מרכך כביסה דובי מפנק ירוק1ל"),
        ("נ.כלים אורגינל650מ פיירי", "נוזל כלים אורגינל650מ פיירי"),
        ('5סכיני גילוח חד"פ גילט', "5סכיני גילוח חד פעמי גילט"),
    ],
)
def test_chain_abbreviations_are_expanded(raw: str, expected: str) -> None:
    assert clean_name(raw) == expected


@pytest.mark.parametrize(
    "raw", ["שוקולד מריר 100 גרם", "חטיף תירס", "תחליב גוף", "נוזל כלים פיירי"]
)
def test_a_spelled_out_word_is_left_alone(raw: str) -> None:
    assert clean_name(raw) == raw


def test_name_limits_are_the_longest_names_measured_per_chain() -> None:
    from smartcart_catalog.review_packet import load_real_items

    items = load_real_items()
    if not items:
        pytest.skip("real fixtures not present")
    longest: dict[str, int] = {}
    for it in items:
        longest[it.chain_id] = max(longest.get(it.chain_id, 0), len(it.raw_name.strip()))
    for chain_id, limit in NAME_LIMITS.items():
        assert longest[chain_id] == limit, chain_id
    # King Store is not cut: its names run past every other chain's width
    assert KING_STORE not in NAME_LIMITS and longest[KING_STORE] > 40


@pytest.mark.parametrize(
    ("chain", "name", "cut"),
    [
        (OSHER_AD, "ענבים אדומים ענבי טל", True),  # 20 characters
        (OSHER_AD, "שוקיים עוף טרי עטרה", True),  # 19: cut right after a space, then stripped
        (OSHER_AD, "עגבניות שרי", False),
        (SHUFERSAL, "שוקולד מריר לינדט מלח 10", True),  # 24 characters
        (SHUFERSAL, "ניילון נצמד 30ס\"מ*30 מטר", True),
        (SHUFERSAL, "רוטב טבסקו 60 מ\"ל", False),
        (MEGA, "קורנפלקס קלוגס 1 ק\"ג תנובה במבצע", False),  # longer than the width: not cut by it
        (KING_STORE, "חמאת בוטנים עם שברי בוטנים 454 ג' סקיפי", False),  # this chain does not cut
        (None, "ענבים אדומים ענבי טל", False),
    ],
)
def test_is_truncated_by_the_chain_width(chain: str | None, name: str, cut: bool) -> None:
    assert is_truncated(chain, name) is cut


def test_only_a_name_at_the_full_width_ends_in_a_fragment() -> None:
    assert is_full_width(OSHER_AD, "ענבים אדומים ענבי טל")
    assert not is_full_width(OSHER_AD, "שוקיים עוף טרי עטרה")  # cut at a space: ends on a word
