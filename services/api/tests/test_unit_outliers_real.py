"""The implausible unit prices of the real day, from the real rows (docs/real-day-dry-run.md,
"Unit-price outliers"; rows in ``real_unit_rows.py``).

Run 39804455160 left five outliers in ``effective_prices``: toilet paper (24 rolls) at 813.60 against
20.93, paper towels and garbage bags at 9.90 against 1 to 2, mineral water at 6.8 times, sunflower
oil at 10.90 per 100 ml and soda water at 0.03. Every case is derived here the way the system does
it: the chain's adapter parses the row, the loader's ``resolve_unit_price`` makes the stored unit
price, and the precompute's ``read_unit_price`` reads the item for its canonical (with the
canonical's typical pack from ``data/canonicals.yaml``).

The rule, for every case: a unit price is the true price of one unit, or it is unknown. A pack whose
count no reading states is not priced per unit; two readings of a size that cannot be told apart are
no reading; a chain's size that is a decimal slip of the name's is not believed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
import yaml
from api_world import World, add_price
from real_unit_rows import ROWS
from test_api_packs import add_counted_canonical, ep_row

from smartcart_api.offers import units_per_pack
from smartcart_api.precompute import (
    PricedItem,
    precompute_effective_prices,
    read_unit,
    read_unit_price,
    unit_price_in,
)
from smartcart_ingest.adapters import REGISTRY
from smartcart_ingest.unitprice import resolve_unit_price

D = Decimal
NOW = datetime(2026, 10, 22, tzinfo=UTC)
CHAIN_IDS = {
    "shufersal": "7290027600007",
    "king_store": "7290058108879",
    "tivtaam": "7290873255550",
    "ramilevy": "7290058140886",
    "yohananof": "7290803800003",
    "osherad": "7290103152017",
    "mega": "7290055700007",
}
CANONICALS = {
    c["slug"]: c
    for c in yaml.safe_load(
        (Path(__file__).resolve().parents[3] / "data" / "canonicals.yaml").read_text("utf-8")
    )["canonicals"]
}
CASE_CANONICAL = {
    "toilet": "toilet-paper",
    "towels": "paper-towels",
    "bags": "garbage-bags",
    "water": "mineral-water",
    "oil": "sunflower-oil",
    "soda": "soda-water",
}


def _xml(chain_id, file, code, name, unitqty, qty, uom, weighed, price, uomprice) -> bytes:
    """A PriceFull of one row, in the shape every chain's file has (header, Items, Item)."""
    store = file.split("-")[2]
    fields = {
        "PriceUpdateTime": "2026-10-22T03:00:00", "ItemCode": code, "ItemType": "1",
        "ItemName": name, "UnitQty": unitqty, "Quantity": qty, "UnitOfMeasure": uom,
        "bIsWeighted": weighed, "ItemPrice": price, "UnitOfMeasurePrice": uomprice,
    }  # fmt: skip
    item = "".join(f"<{k}>{escape(v)}</{k}>" for k, v in fields.items())
    return (
        f'<?xml version="1.0" encoding="utf-8"?><Root><ChainID>{chain_id}</ChainID>'
        f"<SubChainID>001</SubChainID><StoreID>{store}</StoreID><BikoretNo>1</BikoretNo>"
        f'<Items Count="1"><Item>{item}</Item></Items></Root>'
    ).encode()


class Real:
    """One real row, ingested: what the adapter, the loader and the precompute make of it."""

    def __init__(self, row: tuple) -> None:
        (self.case, self.chain, self.file, self.code, self.name, self.unitqty, self.qty,
         self.uom, self.weighed, self.price, self.uomprice) = row  # fmt: skip
        self.chain_id = CHAIN_IDS[self.chain]
        adapter = REGISTRY[self.chain_id]()
        data = _xml(
            self.chain_id, self.file, self.code, self.name, self.unitqty, self.qty, self.uom,
            self.weighed, self.price, self.uomprice,
        )  # fmt: skip
        parsed = adapter.parse(adapter.raw_file_for(self.file, data, path=self.file), data)
        self.item, self.record = parsed.items[0], parsed.prices[0]
        assert self.item.raw_name == self.name and self.record.price == D(self.price)
        self.stored = resolve_unit_price(
            self.record.price, self.record.unit_price, self.record.unit_of_measure,
            self.item.is_weighed, self.record.quantity, self.record.quantity_unit, self.chain_id,
        )  # fmt: skip

    @property
    def typical(self) -> Decimal | None:
        c = CANONICALS[CASE_CANONICAL[self.case]]
        return units_per_pack(c["base_unit"], c.get("soft_attrs"))

    def priced(self) -> PricedItem:
        """The item as the precompute reads it: ``prices.unit_price`` as the loader stored it,
        ``items.quantity`` and ``items.unit`` (UnitQty) as the loader stored them."""
        return PricedItem(
            1, 1, self.record.price, self.stored.value, self.stored.uom, self.stored.is_estimated,
            NOW, self.item.quantity, self.item.unit, self.item.raw_name, self.item.is_weighed,
            self.item.item_code,
        )  # fmt: skip

    def unit_price(self) -> Decimal | None:
        base = CANONICALS[CASE_CANONICAL[self.case]]["base_unit"]
        got = read_unit_price(self.priced(), base, self.typical)
        return None if got is None else got.unit_price


def real(case: str, chain: str, code: str, price: str) -> Real:
    for row in ROWS:
        if row[:2] == (case, chain) and row[3] == code and row[9] == price:
            return Real(row)
    raise KeyError((case, chain, code, price))


def of_case(case: str) -> list[Real]:
    return [Real(r) for r in ROWS if r[0] == case]


def approx(value: Decimal | None, expected: str, tol: str = "0.0005") -> bool:
    return value is not None and abs(value - D(expected)) <= D(tol)


# --- 1. toilet paper: 813.60 against 20.93 --------------------------------------------------------

# (chain, ItemCode, ItemPrice) -> price per roll, None = no unit price (count unknown)
TOILET = [
    # Shufersal publishes the paper's length: 528 "meters" of 32 rolls, 0.06 per meter. The count
    # is in the name: "32 גליל" (singular), "32גל" (cut), "48גלילים", "32ג XPO" (one letter).
    ("shufersal", "7290000262031", "33.90", "1.0594"),  # was 33.90: 24 rolls cost 813.60
    ("shufersal", "7296073128175", "25.90", "0.8094"),
    ("shufersal", "7290000187938", "43.90", "1.3719"),
    ("shufersal", "7296073128182", "32.90", "0.6854"),
    ("shufersal", "7290103707002", "36.90", "1.1531"),
    ("shufersal", "7290103704063", "34.90", None),  # "כדור פורח 48": a bare 48, cut: unknown
    ("king_store", "7290111348167", "27.90", "0.8719"),  # Quantity 32 יחידות: always right
    ("tivtaam", "7290000262031", "32.90", "1.0281"),
    ("tivtaam", "7290012823602", "35.90", "1.1219"),
    ("tivtaam", "63435703793", "45.90", "5.1000"),  # 9 rolls of a premium brand: real
    ("ramilevy", "7290103704162", "37.90", "1.1844"),
    ("ramilevy", "7290019712176", "24.90", None),  # "רויאל 32", 17 "meters": unknown
    ("yohananof", "96619194254", "19.90", None),  # no count anywhere: was 19.90 a roll
    ("yohananof", "7290111346088", "26.90", "0.8967"),  # "מולט 30 ג"
    ("osherad", "7290002008903", "16.90", None),  # Quantity 0.00: was 16.90 a roll
    ("osherad", "7290002008903", "7.90", None),
    ("osherad", "7290000187921", "41.50", None),  # 552 "meters", no count in the name
]


@pytest.mark.parametrize(("chain", "code", "price", "expected"), TOILET)
def test_toilet_paper_is_the_price_of_one_roll_or_unknown(chain, code, price, expected) -> None:
    r = real("toilet", chain, code, price)
    got = r.unit_price()
    if expected is None:
        assert got is None
    else:
        assert approx(got, expected), (r.name, got)
        assert got < D(r.price) / 2  # never the shelf price of a pack of rolls


def test_toilet_paper_of_a_pack_of_24_to_48_rolls_agrees_across_chains() -> None:
    """The 38.9 times between Shufersal (33.90) and King Store (0.87) is gone: every chain's pack
    of 30 to 48 rolls costs 0.6 to 1.4 a roll, so 24 rolls cost between 15 and 33."""
    per_chain: dict[str, list[Decimal]] = defaultdict(list)
    for r in of_case("toilet"):
        got = r.unit_price()
        if got is not None and got < 3:
            per_chain[r.chain].append(got)
    assert set(per_chain) == {"shufersal", "king_store", "tivtaam", "ramilevy", "yohananof"}
    every = [v for values in per_chain.values() for v in values]
    assert max(every) / min(every) < D("2.5")
    assert max(every) * 24 < D("35")


@pytest.mark.parametrize("chain", ["shufersal", "osherad", "yohananof", "ramilevy"])
def test_toilet_paper_without_a_count_was_priced_per_pack_before(chain) -> None:
    """The root cause, shown: with no typical pack to say it is a multi-pack, the reading falls back
    to the shelf price as the price of one unit (the 813.60). ``typical`` is what stops it."""
    unknown = [r for r in of_case("toilet") if r.chain == chain and r.unit_price() is None]
    assert unknown
    for r in unknown:
        old = read_unit_price(r.priced(), "unit")  # no canonical context: the old behavior
        assert old is not None and old.unit_price == D(r.price) and old.pack_units is None
        got = read_unit(r.priced(), "unit", r.typical)
        assert got.note[0] == "count_unknown"


def test_the_published_metres_are_not_read_as_units() -> None:
    """Shufersal: 528 מטרים. The loader has no unit price for it (a length is not a unit price per
    unit) and the precompute never takes the 528 for a count: the 32 is the name's ("32 גליל",
    which the normalizer did not read as a count before: singular גליל)."""
    r = real("toilet", "shufersal", "7290000262031", "33.90")
    assert r.stored.value is None and r.stored.source == "none"
    assert r.item.unit == "מטרים" and r.item.quantity == D("528.00")
    got = read_unit(r.priced(), "unit", r.typical)
    assert got.pack_units == 32 and got.note[0] == "count_from_name"
    assert got.unit_price == D("33.90") / 32


# --- 2. paper towels and garbage bags at 9.90 -----------------------------------------------------

TOWELS = [
    ("king_store", "7290019099703", "12.90", "2.1500"),  # שישיית: 6 rolls
    ("yohananof", "7290005427107", "9.90", "1.6500"),  # "שישיה סוש": 6, was 9.90 a roll
    ("yohananof", "7290103705640", "9.90", None),  # "דו שכבתי": no count, was 9.90 a roll
    ("osherad", "7290000188355", "10.90", "1.8167"),  # "ניקול 6 י" (cut): 6 units
    ("osherad", "7290108352900", "19.90", None),  # 126.96 "meters", no count: was 19.90
    ("ramilevy", "7290019712206", "17.90", "2.9833"),  # "רויאל 6 י" (cut), 20.7 meters: 6 rolls
]


@pytest.mark.parametrize(("chain", "code", "price", "expected"), TOWELS)
def test_paper_towels_are_the_price_of_one_roll_or_unknown(chain, code, price, expected) -> None:
    r = real("towels", chain, code, price)
    got = r.unit_price()
    if expected is None:
        assert got is None or got < D(r.price) / 2
    else:
        assert approx(got, expected), (r.name, got)


BAGS = [
    ("king_store", "7290000189536", "19.90", "0.4975"),  # "40 יח'", Quantity 40
    ("ramilevy", "7290108271430", "14.90", "0.7450"),  # Quantity 20
    ("ramilevy", "7290001713464", "14.90", "0.1490"),  # "100 יח", Quantity 1.25 ליטר
    ("tivtaam", "4007519035369", "9.90", "0.8250"),  # "12 שקיות", Quantity 1: was 9.90 a bag
    ("osherad", "7290011969042", "9.90", None),  # Quantity 0.00, cut name: was 9.90 a bag
    ("ramilevy", "7290005033230", "19.00", None),  # "75*90 50" cut: no unit word, 19.00 a bag
    ("yohananof", "7290000289472", "17.90", "0.3580"),  # "סושי 50 י" (cut): 50 bags, Quantity 1
]


@pytest.mark.parametrize(("chain", "code", "price", "expected"), BAGS)
def test_garbage_bags_are_the_price_of_one_bag_or_unknown(chain, code, price, expected) -> None:
    r = real("bags", chain, code, price)
    got = r.unit_price()
    if expected is None:
        assert got is None or got < D(r.price) / 2
    else:
        assert approx(got, expected), (r.name, got)


def test_counted_bags_and_towels_agree_across_chains() -> None:
    bags = [v for r in of_case("bags") if (v := r.unit_price()) is not None]
    assert bags and max(bags) < D("2")  # 9.90, 19.00 and 17.90 a bag are gone
    towels = [v for r in of_case("towels") if (v := r.unit_price()) is not None]
    assert towels and max(towels) < D("3")


# --- 3. mineral water at 6.8 times ----------------------------------------------------------------


def test_osher_ads_mineral_water_is_a_correct_unit_price_of_a_different_product() -> None:
    """14.90 for 1.32 liters (4 x 330 ml of sparkling water): 1.1288 per 100 ml, which is what the
    chain itself publishes (11.29 a liter) and what the loader stored. It is not a unit-price
    error, so no unit-price rule can change it; the 6.8 times of the basket index is a 4-pack of
    small bottles of sparkling water standing in for the 9-liter pack of still water the line asks
    for (open: docs/real-day-dry-run.md)."""
    r = real("water", "osherad", "3179730012564", "14.90")
    assert r.item.quantity == D("1.32") and r.record.unit_price == D("11.29")
    assert approx(r.stored.value, "1.1288") and r.stored.uom == "100ml"
    assert approx(r.unit_price(), "1.1288")


WATER = [
    ("ramilevy", "726529154153", "14.90", "0.1656"),  # 9 liters
    ("king_store", "7290019056553", "14.90", "0.1242"),  # "שישית ... 2ל'": 12 liters
    ("king_store", "7290019056973", "15.90", "0.1767"),
    ("ramilevy", "3800103433586", "14.90", "0.2483"),  # 6 liters, a cut name
]


@pytest.mark.parametrize(("chain", "code", "price", "expected"), WATER)
def test_bulk_mineral_water_is_unchanged_and_agrees(chain, code, price, expected) -> None:
    r = real("water", chain, code, price)
    assert approx(r.unit_price(), expected), r.name
    assert D("0.1") < r.unit_price() < D("0.3")


# --- 4. sunflower oil at 10.90 per 100 ml ---------------------------------------------------------


def test_tiv_taams_1_liter_oil_that_says_100_ml_is_read_from_the_name() -> None:
    """The file says Quantity 100 מיליליטר for "שמן חמניות 1 ליטר" at 10.90, and the loader (which
    sees no name) computes 10.90 per 100 ml, as the chain's published 10.90 agrees. The name says
    1 liter, ten times the chain's size: a decimal slip, so the name is used: 1.09."""
    r = real("oil", "tivtaam", "7290003578672", "10.90")
    assert r.item.quantity == D("100.00") and r.record.unit_price == D("10.90")
    assert r.stored.value == D("10.9000") and r.stored.uom == "100ml"
    got = read_unit(r.priced(), "100ml", None)
    assert got.unit_price == D("1.09") and got.note[0] == "measure_name_over_chain"


def test_the_same_oil_costs_the_same_at_every_chain() -> None:
    """Willi-Food's 1 liter (barcode 7290003578672) at Tiv Taam, Rami Levy and Osher Ad: 9.90 to
    10.90 a liter. Tiv Taam was 10.90 per 100 ml, ten times a liter's price."""
    prices = [
        real("oil", "tivtaam", "7290003578672", "10.90"),
        real("oil", "ramilevy", "7290003578672", "9.90"),
        real("oil", "osherad", "7290003578672", "9.90"),
    ]
    got = [r.unit_price() for r in prices]
    assert all(v is not None for v in got)
    assert max(got) / min(got) < D("1.2")


@pytest.mark.parametrize(
    ("chain", "code", "price"),
    [
        ("tivtaam", "7290015888196", "10.90"),
        ("ramilevy", "7290015888196", "9.90"),
        ("king_store", "7290002374268", "12.90"),
        ("yohananof", "7290117035290", "8.90"),
    ],
)
def test_one_liter_of_sunflower_oil_is_about_one_per_100_ml(chain, code, price) -> None:
    got = real("oil", chain, code, price).unit_price()
    assert got is not None and D("0.85") < got < D("1.35")


# --- 5. soda water at 0.03 per 100 ml -------------------------------------------------------------


def test_the_soda_bottle_whose_file_says_nine_liters_has_no_unit_price() -> None:
    """Rami Levy: "סודה מי עדן 1.5 לי" at 2.70 with Quantity 9.00 (liters; the six-pack's total).
    The loader computes 2.70 / 9 liters = 0.03 per 100 ml and the chain's published 0.30 a liter
    agrees. The name says 1.5 liters (0.18 per 100 ml, what every other chain charges for it); a
    name that left out a six-pack looks the same, and the data cannot say which is right, so the
    item has no unit price instead of the cheapest soda in the country."""
    r = real("soda", "ramilevy", "19153450", "2.70")
    assert r.item.quantity == D("9.00") and r.record.unit_price == D("0.30")
    assert approx(r.stored.value, "0.0300")
    got = read_unit(r.priced(), "100ml", None)
    assert got.note[0] == "measure_unknown"
    assert r.unit_price() is None


@pytest.mark.parametrize(
    ("chain", "code", "price", "expected"),
    [
        ("ramilevy", "7290000135342", "2.90", "0.5800"),  # 500 ml, published rounded to 0.01
        ("osherad", "7290000136240", "2.90", "0.1933"),  # 1.5 liters
        ("tivtaam", "7290019153467", "3.20", "0.6400"),
        ("ramilevy", "7290019153504", "16.90", "0.1878"),  # six 1.5 liter bottles
    ],
)
def test_other_soda_is_unchanged(chain, code, price, expected) -> None:
    assert approx(real("soda", chain, code, price).unit_price(), expected)


def test_a_cut_name_that_leaves_out_the_six_pack_is_unknown_too() -> None:
    """Rami Levy's name is cut at 20 characters: "מי עדן סודה 500מל שי" (שישייה). The file says
    3000 ml (6 x 500) and 13.90 is 0.4633 per 100 ml, the right price; the name alone says 500 ml.
    It looks exactly like the 9 liters of the single bottle above, so it is unknown as well: the
    price of one precision rule, a recall cost (docs/real-day-dry-run.md)."""
    r = real("soda", "ramilevy", "7290019153511", "13.90")
    assert approx(r.stored.value, "0.4633")
    assert read_unit(r.priced(), "100ml", None).note[0] == "measure_unknown"


def test_no_soda_row_is_below_a_tenth_of_the_median() -> None:
    values = sorted(v for r in of_case("soda") if (v := r.unit_price()) is not None)
    median = values[len(values) // 2]
    assert values[0] > median / 10 and values[-1] < median * 10


# --- the rules at their edges -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typical", "priced"),
    [(None, True), (D(1), True), (D(4), True), (D("5.9"), True), (D(6), False), (D(32), False)],
)
def test_only_a_canonical_sold_in_packs_refuses_an_item_with_no_count(typical, priced) -> None:
    """A loose lettuce, a baguette or a sponge (typical 1 to 4) stays priced per item; a canonical of
    6 or more (paper towels, bags, rolls, eggs) does not price a shelf item of unknown count."""
    p = PricedItem(1, 1, D("5.90"), D("5.90"), "unit", False, NOW, D("1"), "יחידות", "חסה", False)
    got = read_unit_price(p, "unit", typical)
    assert (got is not None) == priced
    if priced:
        assert got.unit_price == D("5.90") and got.pack_units is None


def test_a_count_in_any_reading_is_a_count() -> None:
    """The fields (King Store), the name (Shufersal) or the published unit price (Rami Levy) each
    state the count; the typical pack of the canonical changes nothing for them."""
    fields = PricedItem(
        1, 1, D("19.90"), D("0.4975"), "unit", False, NOW, D("40"), "יחידות", "שקיות"
    )
    name = PricedItem(
        1, 1, D("19.90"), None, None, False, NOW, D("1"), "יחידות", "שקיות אשפה 40 יח'"
    )
    published = PricedItem(
        1, 1, D("19.90"), D("0.4975"), "unit", False, NOW, D("1"), "יחידות", "שקיות"
    )
    for p in (fields, name, published):
        got = read_unit_price(p, "unit", D(30))
        assert got is not None and got.pack_units == 40 and got.unit_price == D("0.4975")


def test_readings_within_three_times_keep_the_dearer_one() -> None:
    """Gel for the laundry: 33.90 for 1 liter by the name, 1.5 liters by the chain (2.26 per 100 ml).
    Not a decimal slip and not far apart: the dearer reading, as before."""
    p = PricedItem(
        1,
        1,
        D("33.90"),
        D("2.26"),
        "100ml",
        False,
        NOW,
        D("1.5"),
        "ליטר",
        "ג'ל כביסה מרוכז 1 ל' BLUE",
    )
    got = read_unit(p, "100ml", None)
    assert got.unit_price == D("3.39") and got.note[0] == "measure_conflict"


def test_a_name_that_misses_the_pack_and_a_chain_that_misses_it_are_not_told_apart() -> None:
    """12 x 500 ml for 14.90 under "500 מ"ל" (chain right: 0.2483) and 9 liters for a 1.5 liter
    bottle at 2.70 (name right: 0.18) have the same shape; both are unknown, never the cheaper."""
    water = PricedItem(
        1,
        1,
        D("14.90"),
        D("0.2483"),
        "100ml",
        False,
        NOW,
        D("6000"),
        "מיליליטר",
        'מים מינרליים 500 מ"ל',
    )
    bottle = PricedItem(
        1, 1, D("2.70"), D("0.03"), "100ml", False, NOW, D("9"), "ליטר", "סודה מי עדן 1.5 ליטר"
    )
    for p in (water, bottle):
        got = read_unit(p, "100ml", None)
        assert got.note[0] == "measure_unknown"


# --- the history reads the same way ---------------------------------------------------------------


def test_the_history_helper_is_unchanged_for_a_counted_item() -> None:
    r = real("toilet", "king_store", "7290111348167", "27.90")
    got = unit_price_in(
        r.record.price, r.stored.value, r.stored.uom, r.item.quantity, r.item.unit, "unit",
        name=r.name,
    )  # fmt: skip
    assert got is not None and approx(got[0], "0.8719")


# --- through the precompute and the database ------------------------------------------------------


def _add(db, w: World, key: str, canon: str, chain: str, r: Real, level: str = "any_brand") -> None:
    """The row as the loader stores it: ``items.quantity`` (0.00 is NULL), ``items.unit`` (UnitQty)
    and the price with the loader's unit price."""
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (chain, key, f"72999{len(w.items):08d}", r.name, r.item.quantity, r.item.unit),
    ).fetchone()[0]
    w.items[key] = iid
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, %s, 0.95, 'rule')",
        (iid, w.canon[canon], level),
    )
    stored = r.stored
    add_price(
        db,
        iid,
        None,
        r.price,
        None if stored.value is None else str(stored.value),
        stored.uom,
        w.valid_from,
    )


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_precompute_prices_toilet_paper_per_roll_at_both_chains(db, world: World) -> None:
    add_counted_canonical(db, world, "tp", 32)
    for n, r in enumerate(x for x in of_case("toilet") if x.chain == "shufersal"):
        _add(db, world, f"s{n}", "tp", "t-c1", r)
    for n, r in enumerate(x for x in of_case("toilet") if x.chain == "king_store"):
        _add(db, world, f"k{n}", "tp", "t-c2", r)
    res = precompute_effective_prices(db, chains=world.chains)
    home, other = ep_row(db, world, "tp", "home"), ep_row(db, world, "tp", "b")
    assert home["uom"] == "unit" and other["uom"] == "unit"
    # Shufersal's cheapest: 48 rolls at 32.90; King Store's: 32 rolls at 27.90
    assert approx(home["effective_unit_price"], "0.6854") and home["pack_units"] == 48
    assert approx(other["effective_unit_price"], "0.8719")
    assert home["effective_unit_price"] * 24 < D("20") and other["effective_unit_price"] * 24 < D(
        "21"
    )
    metrics = db.execute("SELECT metrics FROM match_runs WHERE id = %s", (res.run_id,)).fetchone()[
        0
    ]
    assert metrics["pack_reads"]["count_unknown"] == 1  # Shufersal's "כדור פורח 48"


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_an_item_with_no_count_has_no_effective_price(db, world: World) -> None:
    """Osher Ad's only toilet paper with a price is a pack of unknown size: no row, not 16.90."""
    add_counted_canonical(db, world, "tp", 32)
    _add(db, world, "o", "tp", "t-c1", real("toilet", "osherad", "7290002008903", "16.90"))
    res = precompute_effective_prices(db, chains=world.chains)
    n = db.execute(
        "SELECT count(*) FROM effective_prices WHERE canonical_id = %s", (world.canon["tp"],)
    ).fetchone()[0]
    assert n == 0
    metrics = db.execute("SELECT metrics FROM match_runs WHERE id = %s", (res.run_id,)).fetchone()[
        0
    ]
    assert metrics["pack_reads"] == {"count_unknown": 1}
    sample = metrics["pack_samples"][0]
    assert sample["name"] == "נייר טואלט חתוך הנמל" and sample["price"] == "16.90"


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_precompute_prices_the_oil_and_leaves_the_soda_unpriced(db, world: World) -> None:
    add_counted_canonical(db, world, "oil", 1000, "100ml")
    add_counted_canonical(db, world, "soda", 1500, "100ml")
    _add(db, world, "o1", "oil", "t-c1", real("oil", "tivtaam", "7290003578672", "10.90"))
    _add(db, world, "o2", "oil", "t-c2", real("oil", "ramilevy", "7290003578672", "9.90"))
    _add(db, world, "s1", "soda", "t-c1", real("soda", "ramilevy", "19153450", "2.70"))
    _add(db, world, "s2", "soda", "t-c2", real("soda", "osherad", "7290000136240", "2.90"))
    res = precompute_effective_prices(db, chains=world.chains)
    a, b = ep_row(db, world, "oil", "home"), ep_row(db, world, "oil", "b")
    assert approx(a["effective_unit_price"], "1.09") and approx(b["effective_unit_price"], "0.99")
    assert approx(ep_row(db, world, "soda", "b")["effective_unit_price"], "0.1933")
    n = db.execute(
        "SELECT count(*) FROM effective_prices WHERE canonical_id = %s AND store_id = %s",
        (world.canon["soda"], world.stores["home"]),
    ).fetchone()[0]
    assert n == 0  # was 0.03 per 100 ml
    kinds = db.execute("SELECT metrics FROM match_runs WHERE id = %s", (res.run_id,)).fetchone()[0][
        "pack_reads"
    ]
    assert kinds["measure_name_over_chain"] == 1 and kinds["measure_unknown"] == 1
