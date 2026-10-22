"""Unit prices from price and pack size, the published value as a cross-check (docs/adapters.md,
"Unit prices in real files"). No database.

Every row in ``REAL_ROWS`` is copied verbatim from a committed real PriceFull (2026-10-21,
``fixtures/<chain>/real/``; the chain's first store): item name (cut at 20 characters by the
portal), ``ItemPrice``, ``Quantity``, ``UnitQty``, ``UnitOfMeasure`` and ``UnitOfMeasurePrice``.
They include the case that motivated the change: Rami Levy publishes 0.08 for 200 g of almonds
costing 15.10, labelled "per 100 g", which is the price of one gram.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from smartcart_ingest.unitprice import (
    PUBLISHED_SCALE,
    check_published,
    pack_amount,
    parse_label,
    resolve_unit_price,
)
from tests.test_adapters import FIXTURES, chain_adapters, parse_fixture

D = Decimal
RAMI, KING, MEGA = "7290058140886", "7290058108879", "7290055700007"
OSHER, SHUFERSAL, TIV, YOHANANOF = (
    "7290103152017",
    "7290027600007",
    "7290873255550",
    "7290803800003",
)
UNKNOWN = "לא ידוע"

# chain, name, ItemPrice, Quantity, UnitQty, UnitOfMeasure, UnitOfMeasurePrice, weighed,
#   -> value, uom, source, check under the chain's measured reading, check as labelled
REAL_ROWS = [
    # --- Rami Levy: weight and volume labelled "100 ..." are published per gram / per ml ---
    (RAMI, "שקד * קלוי 200 גר בש", "15.10", "200.00", UNKNOWN, "100 גרם", "0.08", False,
     "7.55", "100g", "computed", "agree", "off_x100_low"),
    (RAMI, "חיטה 1 קג רמי לוי", "10.00", "1000.00", UNKNOWN, "100 גרם", "0.01", False,
     "1.00", "100g", "computed", "agree", "off_x100_low"),
    (RAMI, "חלבה וניל 500 גרם", "15.90", "500.00", UNKNOWN, "100 גרם", "0.03", False,
     "3.18", "100g", "computed", "agree", "off_x100_low"),
    (RAMI, "טמפו סודה 500 מ\"ל", "2.90", "500.00", UNKNOWN, "100 מיליליטר", "0.01", False,
     "0.58", "100ml", "computed", "agree", "off_x100_low"),
    (RAMI, "סרקל מתיר קשרים 340", "27.90", "340.00", UNKNOWN, "100 מיליליטר", "0.08", False,
     "8.2059", "100ml", "computed", "agree", "off_x100_low"),
    # ... while its liter, kilogram and unit labels are as labelled
    (RAMI, "קולה 2 ליטר בודד", "8.60", "2.00", UNKNOWN, "ליטר", "4.30", False,
     "0.43", "100ml", "computed", "agree", "agree"),
    (RAMI, "שיני שום קלוף 1 ק\"ג", "24.90", "1.00", "קילוגרם", "קילוגרם", "24.90", False,
     "2.49", "100g", "computed", "agree", "agree"),
    (RAMI, "תרומה עטופים באהבה", "10.20", "1.00", "יחידות", "יחידות", "10.20", False,
     "10.20", "unit", "computed", "agree", "agree"),
    # a weighed item stays per kg and estimated
    (RAMI, "תפו\"א", "6.90", "1.00", "קילוגרם", "קילוגרם", "6.90", True,
     "6.90", "kg", "weighed", "agree", "agree"),
    # the label says "2 units" and the price is per unit: a disagreement, kept and reported
    (RAMI, "בושם לכביסה 240 מל", "38.90", "20.00", UNKNOWN, "2   יחידות", "1.94", False,
     "1.945", "unit", "computed", "other", "other"),
    # --- Osher Ad: volume published per ml, weight per 100 g ---
    (OSHER, "שמפו נקה 7 לשיער רגי", "9.90", "750.00", UNKNOWN, "100 מ\"ל", "0.01", False,
     "1.32", "100ml", "computed", "agree", "off_x100_low"),
    (OSHER, "חוואיג תימני מיה 50", "5.80", "50.00", "גרם", "100 גרם", "11.60", False,
     "11.60", "100g", "computed", "agree", "agree"),
    (OSHER, "אבקת ביומט 8 קג", "44.90", "8.00", UNKNOWN, "ק\"ג", "5.61", False,
     "0.5613", "100g", "computed", "agree", "agree"),
    (OSHER, "מרכך בדין לבן 4 ליטר", "22.90", "4.00", UNKNOWN, "ליטר", "5.72", False,
     "0.5725", "100ml", "computed", "agree", "agree"),
    # a weighed item labelled "per unit": the shelf price is the price of a kilogram
    (OSHER, "פילה מרלוזה ארגנטינא", "34.90", "1.00", "יחידות", "יחידה", "34.90", True,
     "34.90", "kg", "weighed", None, None),
    # no pack size (Quantity 0) and a published 0.00: nothing usable, the shelf price stays
    (OSHER, "פטמות לבקבוק רחב ארי", "11.90", None, "יחידות", "יחידה", "0.00", False,
     None, None, "none", None, None),
    # --- Mega: "מיליליטר" carries the price per 100 ml ---
    (MEGA, "יין P.C קברנה סוביני", "57.30", "750.00", "מיליליטר", "מיליליטר", "7.64", False,
     "7.64", "100ml", "computed", "agree", "off_x100_high"),
    (MEGA, "גבינת שמנת טבעי 25%", "14.90", "230.00", "גרם", "100 גרם", "6.48", False,
     "6.4783", "100g", "computed", "agree", "agree"),
    (MEGA, "ספרינג לימונענע 1.5", "8.70", "1.50", UNKNOWN, "ליטר", "5.80", False,
     "0.58", "100ml", "computed", "agree", "agree"),
    # grams labelled as liters ("ליטר 1", UnitQty ליטר, Quantity 200): 200 liters is not a pack
    (MEGA, "תפוצ'יפס קראנצ' בטעם", "12.90", "200.00", "ליטר", "ליטר 1", "0.06", False,
     None, None, "none", None, None),
    # --- King Store ---
    (KING, "פסטרמה מקסיקנית", "99.00", "1000", "גרם", "1 קילוגרם", "99", True,
     "99.00", "kg", "weighed", "agree", "agree"),
    (KING, "נתחי ברבקיו 1.43ק\"ג N8US פריסקיז", "42.90", "1430", "גרם", "1 קילוגרם", "30", False,
     "3.00", "100g", "computed", "agree", "agree"),
    (KING, "פסק זמן 40 ג' PLAY עלית", "6.50", "40", "גרם", "100 גרם", "16.25", False,
     "16.25", "100g", "computed", "agree", "agree"),
    (KING, "שתיה קרה ב 9.9", "9.90", "1500", "מיליליטר", "1 ליטר", "6.6", False,
     "0.66", "100ml", "computed", "agree", "agree"),
    # --- Shufersal, Tiv Taam, Yohananof: as labelled ---
    (SHUFERSAL, "שעועית שחורה 439 גרם", "12.90", "439.00", "גרם", "100 גרם", "2.94", False,
     "2.9385", "100g", "computed", "agree", "agree"),
    (SHUFERSAL, "מים מינרלים מוגז פרייה1ל", "11.90", "1.00", "ליטר", "1ליטר", "11.90", False,
     "1.19", "100ml", "computed", "agree", "agree"),
    (SHUFERSAL, "ניילון נצמד 30ס\"מ*30 מטר", "10.00", "30.00", "מטרים", "מטרים", "0.33", False,
     None, None, "none", None, None),
    (TIV, "קינג קול שעועית לימה 439 גרם", "11.90", "439.00", "גרם", "100 גרם", "2.71", False,
     "2.7107", "100g", "computed", "agree", "agree"),
    (TIV, "בוזנינה לבנה להב", "145.00", "1.00", "קילוגרם", "1קילוגרם", "145.00", True,
     "145.00", "kg", "weighed", "agree", "agree"),
    (YOHANANOF, "רוטב טבסקו 60 מ\"ל", "10.90", "60.00", "מיליליטר", "100 מיליליטר", "18.17", False,
     "18.1667", "100ml", "computed", "agree", "agree"),
    (YOHANANOF, "*מבצע* אורז בסמטי או", "29.90", "5.00", "קילוגרם", "1קילוגרם", "5.98", False,
     "0.598", "100g", "computed", "agree", "agree"),
]  # fmt: skip


@pytest.mark.parametrize(
    ("chain", "name", "price", "qty", "unitqty", "label", "published", "weighed", "value", "uom",
     "source", "check", "as_labelled"),
    REAL_ROWS,
    ids=[f"{r[0][-4:]}-{r[1][:14]}" for r in REAL_ROWS],
)  # fmt: skip
def test_a_real_row_resolves_to_price_over_pack_size(
    chain, name, price, qty, unitqty, label, published, weighed, value, uom, source, check,
    as_labelled,
) -> None:  # fmt: skip
    quantity = D(qty) if qty is not None and D(qty) > 0 else None  # the adapter reads 0 as absent
    got = resolve_unit_price(D(price), D(published), label, weighed, quantity, unitqty, chain)
    assert (got.uom, got.source) == (uom, source), name
    assert got.is_estimated is weighed
    if value is None:
        assert got.value is None
    else:
        assert got.value == D(value), name
    assert (got.check, got.check_as_labelled) == (check, as_labelled), name


def _real_prices(slug: str) -> list:
    folder = FIXTURES / slug / "real"
    adapter = chain_adapters()[slug]()
    return parse_fixture(adapter, next(folder.glob("PriceFull*")))


def test_every_row_above_is_verbatim_in_a_committed_real_file() -> None:
    slugs = {RAMI: "ramilevy", KING: "king_store", MEGA: "mega", OSHER: "osherad"}
    slugs |= {SHUFERSAL: "shufersal", TIV: "tivtaam", YOHANANOF: "yohananof"}
    parsed = {chain: _real_prices(slug) for chain, slug in slugs.items()}
    for chain, name, price, qty, unitqty, label, published, weighed, *_ in REAL_ROWS:
        file = parsed[chain]
        names = {i.item_code: i for i in file.items}
        quantity = D(qty) if qty is not None and D(qty) > 0 else None
        hits = [
            r
            for r in file.prices
            if names[r.item_code].raw_name == name
            and r.price == D(price)
            and r.quantity == quantity
            and r.quantity_unit == (unitqty if unitqty != UNKNOWN else UNKNOWN)
            and r.unit_of_measure == label
            and r.unit_price == D(published)
            and names[r.item_code].is_weighed is weighed
        ]
        assert hits, f"{chain} {name!r} is not a row of the real file"


def test_the_100x_case_published_per_gram_is_read_from_the_pack_not_the_label() -> None:
    # 15.10 for 200 g: 7.55 per 100 g. Read as labelled, 0.08 would be 100 times too small.
    got = resolve_unit_price(D("15.10"), D("0.08"), "100 גרם", False, D("200"), UNKNOWN, RAMI)
    assert got.value == D("7.55") and got.uom == "100g"
    assert got.check == "agree" and got.check_as_labelled == "off_x100_low"


def test_without_a_pack_size_the_chains_measured_scale_reads_the_published_value() -> None:
    # Rami Levy, no Quantity: 0.08 per gram is 8.00 per 100 g (the pack's 7.55, to the rounding of
    # a two-decimal per-gram price). Another chain's "100 גרם" is read as labelled.
    rami = resolve_unit_price(D("15.10"), D("0.08"), "100 גרם", False, None, None, RAMI)
    assert (rami.value, rami.uom, rami.source) == (D("8.00"), "100g", "published_scaled")
    shufersal = resolve_unit_price(D("12.90"), D("2.94"), "100 גרם", False, None, None, SHUFERSAL)
    assert (shufersal.value, shufersal.source) == (D("2.94"), "published")
    # an unlisted chain (or none) is read as labelled
    assert resolve_unit_price(D("15.10"), D("7.55"), "100 גרם", False).value == D("7.55")
    # Mega's "מיליליטר" is per 100 ml
    mega = resolve_unit_price(D("57.30"), D("7.64"), "מיליליטר", False, None, None, MEGA)
    assert (mega.value, mega.uom) == (D("7.64"), "100ml")


def test_a_published_value_that_implies_an_impossible_pack_is_not_used() -> None:
    # 0.00 (Rami Levy rounds a cheap per-gram price to zero) and a per-liter 0.06 on 12.90.
    assert (
        resolve_unit_price(D("3.00"), D("0.00"), "100 גרם", False, None, None, RAMI).value is None
    )
    assert resolve_unit_price(D("12.90"), D("0.06"), "ליטר 1", False).value is None
    # 0.01 per gram on 10.00 is a 1 kg pack: kept
    assert resolve_unit_price(D("10.00"), D("0.01"), "100 גרם", False, None, None, RAMI).value == 1


def test_a_disagreement_is_reported_and_the_computed_price_still_wins() -> None:
    got = resolve_unit_price(D("12.00"), D("3.00"), "100 גרם", False, D("200"), "גרם", KING)
    assert got.value == D("6.00") and got.source == "computed"
    assert got.check == "other"


def test_weighed_items_are_the_shelf_price_per_kg() -> None:
    assert resolve_unit_price(D("9.90"), None, None, True).value == D("9.90")
    # published per 100 g, labelled so: only compared (99 per kg is 9.90 per 100 g)
    got = resolve_unit_price(D("99.00"), D("9.90"), "100 גרם", True)
    assert (got.value, got.uom, got.is_estimated, got.check) == (D("99.00"), "kg", True, "agree")
    # a published per-kg price 10 times the shelf price is flagged, the shelf price is kept
    got = resolve_unit_price(D("9.90"), D("99.00"), 'ק"ג', True)
    assert got.value == D("9.90") and got.check == "off_x10_high"


# --- labels and pack sizes ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "dim", "size", "named"),
    [
        ("100 גרם", "mass", 100, 1),
        ("גרם", "mass", 1, 1),
        ('ק"ג', "mass", 1000, 1000),
        ('לק"ג', "mass", 1000, 1000),
        ("1 קילוגרם", "mass", 1000, 1000),
        ("1קילוגרם", "mass", 1000, 1000),
        ("ל-100 גרם", "mass", 100, 1),
        ('100 מ"ל', "volume", 100, 1),
        ("100 מיליליטר", "volume", 100, 1),
        ("מיליליטר", "volume", 1, 1),
        ("ליטר", "volume", 1000, 1000),
        ("ליטר 1", "volume", 1000, 1000),
        ("1ליטר", "volume", 1000, 1000),
        ("100ml", "volume", 100, 1),
        ("2   יחידות", "unit", 2, 1),
        ("יח'", "unit", 1, 1),
        ("יחידה", "unit", 1, 1),
    ],
)
def test_labels_in_every_spelling_the_real_files_use(raw, dim, size, named) -> None:
    label = parse_label(raw)
    assert label is not None
    assert (label.dim, label.size, label.named) == (dim, D(size), D(named))


@pytest.mark.parametrize("raw", [None, "", UNKNOWN, "מטרים", "דונם", "100"])
def test_unknown_labels_are_none(raw) -> None:
    assert parse_label(raw) is None


def test_pack_amount_takes_the_unit_of_unitqty_else_the_labels_own_unit() -> None:
    label = parse_label("100 גרם")
    assert pack_amount(D("200"), "גרם", label) == ("mass", D("200"))
    assert pack_amount(D("0.5"), "קילוגרם", label) == ("mass", D("500"))
    assert pack_amount(D("200"), UNKNOWN, label) == ("mass", D("200"))  # grams for "100 גרם"
    assert pack_amount(D("8"), UNKNOWN, parse_label('ק"ג')) == ("mass", D("8000"))
    assert pack_amount(D("1.5"), UNKNOWN, parse_label("ליטר")) == ("volume", D("1500"))
    assert pack_amount(D("12"), "יחידות", parse_label("יחידות")) == ("unit", D("12"))
    # a unit that contradicts the label's dimension, a zero or missing size, an impossible one
    assert pack_amount(D("200"), "מיליליטר", label) is None
    assert pack_amount(None, "גרם", label) is None
    assert pack_amount(D("0"), "גרם", label) is None
    assert pack_amount(D("452"), "ליטר", parse_label("ליטר 1")) is None  # 452 liters of cereal
    assert pack_amount(D("60000"), "גרם", label) is None
    assert pack_amount(D("200"), UNKNOWN, None) is None  # nothing says what it is 200 of


@pytest.mark.parametrize(
    ("published", "expected", "result"),
    [
        ("7.55", "7.55", "agree"),
        ("7.54", "7.55", "agree"),  # a rounded two-decimal price
        ("0.08", "7.55", "off_x100_low"),
        ("755", "7.55", "off_x100_high"),
        ("0.755", "7.55", "off_x10_low"),
        ("75.5", "7.55", "off_x10_high"),
        ("0.00755", "7.55", "off_x1000_low"),
        ("7550", "7.55", "off_x1000_high"),
        ("3.00", "7.55", "other"),
        ("1.00", "0", "other"),
    ],
)
def test_check_published_classes(published, expected, result) -> None:
    assert check_published(D(published), D(expected)) == result


def test_every_chain_scale_is_a_power_of_ten_and_documented() -> None:
    for chain, rules in PUBLISHED_SCALE.items():
        assert chain in {RAMI, OSHER, MEGA}
        for (dim, size), factor in rules.items():
            assert dim in {"mass", "volume"} and size in {1, 100}
            assert factor in {D(100), D("0.01")}
