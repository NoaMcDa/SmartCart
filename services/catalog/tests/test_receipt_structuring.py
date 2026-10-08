"""Rule-based receipt structuring (issue #61): chain, branch, total, item lines, OCR noise."""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartcart_catalog.receipt import (
    CHAINS,
    clean_line,
    detect_branch,
    detect_chain,
    expand_name,
    parse_receipt,
    query_variants,
)

D = Decimal


def rows(lines: list[str]) -> list[tuple[str, Decimal | None, str | None, Decimal | None]]:
    r = parse_receipt(lines)
    return [(i.text, i.quantity, i.unit, i.price) for i in r.items]


# --- chain ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "chain_id"),
    [
        (['שופרסל דיל בע"מ', "סניף רמת אביב"], "7290027600007"),
        (["שופרסל"], "7290027600007"),
        (["רמי לוי שיווק השקמה 2006 בע\"מ"], "7290058140886"),
        (["שיווק השקמה"], "7290058140886"),
        (["ויקטורי"], "7290696200003"),
        (["יינות ביתן"], "7290055700007"),
        (["מגה בעיר"], "7290055700007"),
        (["חצי חינם", "ראשון לציון"], "7290700100008"),
        (["טיב טעם"], "7290873255550"),
        (["אושר עד"], "7290103152017"),
        (["יוחננוף"], "7290803800003"),
        (["מחסני השוק"], "7290661400001"),
        (["קינג סטור"], "7290058108879"),
        (["שופרסל ‏", "ח.פ 123"], "7290027600007"),  # RTL mark
        (["שופרצל דיל"], "7290027600007"),  # one letter off, long enough to fuzzy-match
        (["Shufersal Deal"], "7290027600007"),
    ],
)
def test_chain_from_the_header(header: list[str], chain_id: str) -> None:
    assert detect_chain(header)[0] == chain_id


def test_chain_unknown_or_ambiguous_is_none() -> None:
    assert detect_chain(["סופר השכונה", "תל אביב"]) == (None, None)
    assert detect_chain(["שופרסל", "ויקטורי"]) == (None, None)
    assert detect_chain([]) == (None, None)


def test_chain_from_a_footer_only_when_exact() -> None:
    body = ["סופר כלשהו"] * 14 + ["תודה שקניתם בשופרסל"]
    assert detect_chain(body)[0] == "7290027600007"
    assert detect_chain(["x"] * 14 + ["תודה שקניתם בשופרצל"]) == (None, None)


def test_every_chain_id_is_a_known_gs1_id() -> None:
    assert all(cid.startswith("7290") and len(cid) == 13 for cid in CHAINS)
    assert len(CHAINS) == 10


@pytest.mark.parametrize(
    ("lines", "branch"),
    [
        (["סניף: רמת אביב"], "רמת אביב"),
        (["סניף 123 הרצליה"], "הרצליה"),
        (["סניף - נתניה 45"], "נתניה"),
        (["שופרסל"], None),
        (["סניף: 12"], None),
    ],
)
def test_branch(lines: list[str], branch: str | None) -> None:
    assert detect_branch([clean_line(x) for x in lines]) == branch


# --- totals -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lines", "total"),
    [
        (['סה"כ 27.50'], D("27.50")),
        (["לתשלום 27.50"], D("27.50")),
        (['סה"כ 30.00', "הנחה -2.50", "לתשלום 27.50"], D("27.50")),  # לתשלום wins over a subtotal
        (['סה"כ לתשלום: 112.40'], D("112.40")),
        (["27.50 לתשלום"], D("27.50")),  # price first, visual order
        (['סה"כ פריטים 5', 'סה"כ 27.50'], D("27.50")),
        (['סה"כ 1,234.50'], D("1234.50")),
        (['סה"כ הנחות 4.00'], None),
        (['סה"כ לפני מע"מ 23.30'], None),
    ],
)
def test_printed_total(lines: list[str], total: Decimal | None) -> None:
    assert parse_receipt(lines).total == total


# --- item lines -------------------------------------------------------------------------------


def test_name_and_trailing_price() -> None:
    assert rows(["לחם אחיד פרוס 7.50"]) == [("לחם אחיד פרוס", None, None, D("7.50"))]


def test_price_first_in_visual_order() -> None:
    assert rows(["7.50 לחם אחיד פרוס"]) == [("לחם אחיד פרוס", None, None, D("7.50"))]


def test_inline_count_times_unit_price() -> None:
    assert rows(["קוטג' תנובה 250 גרם 2 X 5.90 11.80"]) == [
        ("קוטג' תנובה 250 גרם", D(2), None, D("11.80"))
    ]


def test_count_detail_on_the_next_line() -> None:
    assert rows(["קוטג' תנובה", "2 X 5.90 11.80"]) == [("קוטג' תנובה", D(2), None, D("11.80"))]


def test_count_detail_after_a_priced_name_line() -> None:
    assert rows(["יוגורט דנונה 11.80", "2 x 5.90"]) == [("יוגורט דנונה", D(2), None, D("11.80"))]


def test_count_without_total_multiplies() -> None:
    assert rows(["במבה אסם", "3 * 4.50"]) == [("במבה אסם", D(3), None, D("13.50"))]


def test_reversed_count_expression() -> None:
    assert rows(["במבה אסם", "5.90 X 2 11.80"]) == [("במבה אסם", D(2), None, D("11.80"))]


def test_weighed_item_on_two_lines() -> None:
    assert rows(["עגבניות", 'ק"ג 0.532 X 9.90 5.27'])[0][1:] == (D("0.532"), "kg", D("5.27"))
    assert rows(["עגבניות", '0.532 ק"ג X 9.90 5.27']) == [("עגבניות", D("0.532"), "kg", D("5.27"))]


def test_weighed_item_with_per_kg_price_label() -> None:
    assert rows(["מלפפונים 1.250 ק\"ג 12.50", 'מחיר 9.99 ל-ק"ג'])[0][1:3] == (D("1.250"), "kg")


def test_weight_with_three_decimals_alone_is_a_weight() -> None:
    assert rows(["בננות", "1.120 ק\"ג 11.20"]) == [("בננות", D("1.120"), "kg", D("11.20"))]


def test_a_size_in_the_name_is_not_a_weight() -> None:
    assert rows(['סוכר לבן 1 ק"ג 6.90']) == [("סוכר לבן 1 קילוגרם", None, None, D("6.90"))]


def test_a_pack_count_in_the_name_is_not_a_quantity() -> None:
    assert rows(["ביצים L 12 יח' 14.90"]) == [("ביצים L 12 יחידות", None, None, D("14.90"))]


def test_unit_marker_on_a_detail_line_is_a_quantity() -> None:
    assert rows(["שוקולד פרה", "3 יח' X 6.50 19.50"]) == [("שוקולד פרה", D(3), None, D("19.50"))]


def test_name_with_percent_and_volume_is_kept_whole() -> None:
    got = rows(["חלב תנובה 3% 1 ל' 8.90"])
    assert got == [("חלב תנובה 3% 1 ליטר", None, None, D("8.90"))]


def test_a_volume_that_looks_like_a_price_is_not_one() -> None:
    assert rows(["קולה 1.50 ל' 9.90"]) == [("קולה 1.50 ליטר", None, None, D("9.90"))]


def test_barcodes_and_item_numbers_are_dropped_from_the_name() -> None:
    assert rows(["001 7290000123456 חלב טרי 3% 6.20"]) == [("חלב טרי 3%", None, None, D("6.20"))]
    assert rows(["1. פסטה ברילה 500 גרם 7.90"]) == [("פסטה ברילה 500 גרם", None, None, D("7.90"))]


# --- lines that are not items -----------------------------------------------------------------


def test_discount_lines_are_negative_and_not_items() -> None:
    r = parse_receipt(["חלב 8.90", "הנחת מועדון -1.00", "הנחה על קוטג 2.00-", "מבצע 3 ב-10 -2.50"])
    assert [i.text for i in r.items] == ["חלב"]
    assert r.discounts == [D("-1.00"), D("-2.00"), D("-2.50")]


def test_deposit_vat_payment_and_fiscal_lines_are_skipped() -> None:
    lines = [
        "פיקדון על בקבוקים 0.30",
        'מע"מ 18% 4.20',
        "אשראי ויזה 27.50",
        "מזומן 30.00",
        "עודף 2.50",
        "תאריך 08/10/2026 שעה 18:32",
        'חשבונית מס מספר 12345',
        "קופה 4 קופאית דנה",
        "ח.פ 520022732",
        "מועדון שופרסל 1234",
    ]
    assert rows(lines) == []


def test_a_name_without_a_price_is_dropped() -> None:
    assert rows(["תל אביב", "חלב 8.90", "רחוב הרצל"]) == [("חלב", None, None, D("8.90"))]


def test_a_lone_price_without_a_name_is_ignored() -> None:
    assert rows(["8.90", "חלב 8.90"]) == [("חלב", None, None, D("8.90"))]


def test_a_negative_amount_on_a_named_line_is_a_credit() -> None:
    r = parse_receipt(["חלב 8.90", "זיכוי החזרת בקבוק -0.30"])
    assert len(r.items) == 1 and r.discounts == [D("-0.30")]


# --- OCR noise --------------------------------------------------------------------------------


def test_stray_punctuation_and_bidi_marks() -> None:
    assert rows(["‏| חלב תנובה ‎_ 8.90 |"]) == [("חלב תנובה", None, None, D("8.90"))]


def test_quote_variants_in_units() -> None:
    assert rows(["תפוחי עץ 1.250 ק״ג 12.40"])[0][1:3] == (D("1.250"), "kg")
    assert rows(["עגבניות 0.532 ק”ג X 9.90 5.27"])[0][1:3] == (D("0.532"), "kg")


def test_letter_o_and_l_inside_numbers() -> None:
    assert rows(["חלב 8.9O", "לחם 7.5O"]) == [
        ("חלב", None, None, D("8.90")),
        ("לחם", None, None, D("7.50")),
    ]
    assert clean_line("12.l0") == "12.10"


def test_space_inside_the_price_and_decimal_comma() -> None:
    assert rows(["חלב 8 .90", "לחם 7,50"]) == [("חלב", None, None, D("8.90")), ("לחם", None, None, D("7.50"))]


def test_trailing_minus_marks_a_discount() -> None:
    assert parse_receipt(["הנחה 2.00-"]).discounts == [D("-2.00")]


def test_shekel_signs_are_ignored() -> None:
    assert rows(["חלב ₪8.90", 'לחם 7.50 ש"ח']) == [("חלב", None, None, D("8.90")), ("לחם", None, None, D("7.50"))]


def test_reversed_digit_order_is_fixed_only_when_the_sums_need_it() -> None:
    lines = ["חלב 90.5", "לחם 7.50", 'סה"כ 12.59']  # 90.5 is 5.09 back to front
    r = parse_receipt(lines)
    assert [i.price for i in r.items] == [D("5.09"), D("7.50")]
    assert r.reversed_fixed == 1


def test_a_one_decimal_price_that_adds_up_stays_as_read() -> None:
    r = parse_receipt(["יין 45.5", "לחם 7.50", 'סה"כ 53.00'])
    assert [i.price for i in r.items] == [D("45.50"), D("7.50")]
    assert r.reversed_fixed == 0


def test_reversed_total_is_fixed_too() -> None:
    r = parse_receipt(["במבה 2.59", 'סה"כ 95.2'])  # 95.2 is 2.59 back to front
    assert r.total == D("2.59") and r.reversed_fixed == 1


def test_no_total_means_no_reversal() -> None:
    r = parse_receipt(["חלב 90.5"])
    assert r.items[0].price == D("90.50")


# --- a whole receipt --------------------------------------------------------------------------

FULL = [
    'שופרסל דיל בע"מ',
    "סניף: רמת אביב",
    "ח.פ 520022732",
    "חשבונית מס מספר 12345",
    "תאריך 08/10/2026 שעה 18:32",
    "חלב תנובה 3% 1 ל' 8.90",
    "קוטג' 250 גרם",
    "2 X 5.90 11.80",
    "לחם אחיד פרוס 7.50",
    "עגבניות",
    '0.532 ק"ג X 9.90 5.27',
    "הנחה מבצע -2.00",
    "פיקדון 0.30",
    'סה"כ פריטים 4',
    'סה"כ 31.47',
    "לתשלום 31.47",
    'מע"מ 18% 4.80',
    "אשראי ויזה ****1234",
]


def test_a_whole_receipt() -> None:
    r = parse_receipt(FULL)
    assert (r.chain_id, r.chain_name, r.store_hint) == ("7290027600007", "שופרסל", "רמת אביב")
    assert r.total == D("31.47")
    assert r.discounts == [D("-2.00")]
    assert [(i.text, i.quantity, i.unit, i.price) for i in r.items] == [
        ("חלב תנובה 3% 1 ליטר", None, None, D("8.90")),
        ("קוטג' 250 גרם", D(2), None, D("11.80")),
        ("לחם אחיד פרוס", None, None, D("7.50")),
        ("עגבניות", D("0.532"), "kg", D("5.27")),
    ]
    assert sum(i.price for i in r.items) + sum(r.discounts) == r.total


# --- abbreviations ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "text"),
    [
        ("חלב תנובה 3% 1ל", "חלב תנובה 3% 1 ליטר"),
        ("חלב תנובה 3% 1 ל'", "חלב תנובה 3% 1 ליטר"),
        ("חל' תנובה 3% 1ל", "חלב תנובה 3% 1 ליטר"),
        ("גב' צהובה עמק 28%", "גבינה צהובה עמק 28%"),
        ("שמנ' לבישול 15% 250 מל", "שמנת לבישול 15% 250 מיליליטר"),
        ('תפו"א 1 ק"ג', "תפוחי אדמה 1 קילוגרם"),
        ("עגב' שרי", "עגבניות שרי"),
        ("ביצ' L 12", "ביצים L 12"),
        ("יוג' דנונה 3 %", "יוגורט דנונה 3%"),
        ("טחינ' הר ברכה 500 גר", "טחינה הר ברכה 500 גרם"),
        ("פיל' עוף", "פילה עוף"),
        ("קמ' לבן 1 ק\"ג", "קמח לבן 1 קילוגרם"),
        ("בגב' לבנה", "בגבינה לבנה"),  # a prefix letter is kept
    ],
)
def test_abbreviations_are_expanded(raw: str, text: str) -> None:
    assert expand_name(raw) == text


def test_a_word_that_merely_starts_like_an_abbreviation_is_untouched() -> None:
    assert expand_name("חלבה") == "חלבה"
    assert expand_name("גבינת שמנת") == "גבינת שמנת"


# --- noisy, visual-order output -----------------------------------------------------------------


def test_a_receipt_read_in_visual_order_with_junk_lines() -> None:
    lines = [
        "|||||||||||||",
        "--------------------",
        "שופרסל דיל",
        "========",
        "8.90 חלב תנובה 3% 1 ל'",
        "11.80 2 X 5.90 ‏",
        "7.50 לחם אחיד פרוס",
        "_ _ _ _",
        "27.50 לתשלום",
        "27.50 סה\"כ",
    ]
    r = parse_receipt(lines)
    assert r.chain_id == "7290027600007"
    assert r.total == D("27.50")
    assert [(i.text, i.price) for i in r.items] == [
        ("חלב תנובה 3% 1 ליטר", D("8.90")),
        ("לחם אחיד פרוס", D("7.50")),
    ]


def test_digits_glued_to_words_and_stray_marks_around_prices() -> None:
    assert rows(["חלב3% 8.90*", "* לחם 7.50"]) == [
        ("חלב3%", None, None, D("8.90")),
        ("לחם", None, None, D("7.50")),
    ]


def test_empty_and_garbage_input() -> None:
    r = parse_receipt([])
    assert r.items == [] and r.total is None and r.chain_id is None
    r = parse_receipt(["", "   ", "@@@@", "1234567890123", ".....", "ab"])
    assert r.items == []


def test_two_discounts_and_a_return_still_add_up_to_the_total() -> None:
    r = parse_receipt([
        "חלב 8.90", "לחם 7.50", "הנחת מועדון -1.00", "קופון -0.50", 'לתשלום 14.90',
    ])
    assert sum((i.price for i in r.items), D(0)) + sum(r.discounts, D(0)) == r.total


# --- query variants (what is asked of the catalog) ------------------------------------------------


@pytest.mark.parametrize(
    ("text", "variants"),
    [
        ("חלב תנובה 3% 1 ליטר", ["חלב תנובה 3% 1 ליטר", "חלב תנובה 3%", "חלב 3%"]),
        ("קוטג' 250 גרם", ["קוטג' 250 גרם", "קוטג'"]),
        ("עגבניות", ["עגבניות"]),
        ("במבה אסם 80 גרם", ["במבה אסם 80 גרם", "במבה אסם"]),  # both words are brands: nothing is left to ask
        ("במבה", ["במבה"]),  # a brand that is the whole name is not removed
    ],
)
def test_query_variants(text: str, variants: list[str]) -> None:
    assert query_variants(text) == variants


def test_query_variants_keep_the_fat_percentage() -> None:
    assert all("3%" in v for v in query_variants("חלב תנובה 3% 1 ליטר"))
