"""The pack count in an item's name reaches its unit price and the line total (finding 9 of
docs/real-day-dry-run.md, docs/optimizer.md "Packs").

Real data: the egg names, Quantity and UnitQty are verbatim from the real day
(``services/catalog/tests/test_extract_eggs_real.py``), the Rami Levy 12-pack's 14.20 is the
price in docs/real-day-dry-run.md, and the Shufersal beer and King Store water are real rows of
the committed fixtures (``services/ingest/tests/fixtures/*/real``: name, Quantity, UnitQty and
price). Where the real day gives a name but no price (pitas, toilet paper, the other egg trays)
the price here is illustrative, and ``קולה 6*1.5 ל'`` is a name in the shape the issue lists.
Rami Levy, Yohananof and Tiv Taam write ``Quantity = 1, UnitQty = יחידות`` for a tray of 12 eggs,
and the published unit price of such an item is its price per "1 unit".
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from api_world import World, add_price, add_promo
from psycopg.types.json import Jsonb

from smartcart_api import schemas
from smartcart_api.basket import money, shelf_packs, units_per_pack
from smartcart_api.precompute import (
    PricedItem,
    derive_unit_price,
    precompute_effective_prices,
    read_unit_price,
    unit_price_in,
)

D = Decimal
NOW = datetime(2026, 10, 22, tzinfo=UTC)

# --- the reading of one item, no database ---------------------------------------------------------


def _item(
    price: str,
    name: str,
    qty: str | None,
    unit: str | None,
    published: str | None = None,
    uom: str | None = None,
) -> PricedItem:
    return PricedItem(
        1, 1, D(price), D(published) if published else None, uom, False, NOW,
        D(qty) if qty else None, unit, name, False, None,
    )  # fmt: skip


# (name, Quantity, UnitQty, price, published unit price, its uom, units in the item)
COUNTED = [
    # eggs: Rami Levy writes 1 unit and publishes the tray's price as the price of one
    ("ביצים 12 יח גדול L", "1.00", "יחידות", "14.20", "14.20", "unit", 12),
    ("ביצים 18יח בנוני M", "1.00", "יחידות", "21.50", "21.50", "unit", 18),
    ("ביצים 30יח ענק XL", "1.00", "יחידות", "33.90", None, None, 30),
    ("ביצים גדולות לארג 12", "12.00", "יחידות", "14.20", None, None, 12),
    # Yohananof, Tiv Taam: the count only in the name
    ("ביצים 12 יח  גדול", "1.00", "יחידות", "14.50", None, None, 12),
    ("ביצים אריזון 12 גדול", "1.00", "יחידות", "13.90", None, None, 12),
    # King Store states the count in the fields too, and publishes a per-egg price
    ("ביצים לארג' 12 יח'", "12", "יחידות", "14.16", "1.18", "unit", 12),
    ("ביצים מידיום עטוף 30יח'", "30", "יחידות", "29.90", "1.00", "unit", 30),
    # Osher Ad: two trays of 30, the fields say the total
    ("ביצים 2*30 יח' בינונ", "60.00", "יחידות", "28.90", None, None, 60),
    ("מארז ביצים בינוני 2*", "60.00", "יחידות", "28.90", None, None, 60),
    # pitas and toilet paper
    ("פיתות 10 יח'", "1", "יחידות", "9.90", "9.90", "unit", 10),
    ("נייר טואלט לילי 32 גלילים", "1", "יחידה", "20.90", "20.90", "unit", 32),
]


@pytest.mark.parametrize(
    ("name", "qty", "unit", "price", "pub", "uom", "units"), COUNTED, ids=[c[0] for c in COUNTED]
)
def test_a_counted_item_is_priced_per_unit_on_the_count_in_the_pack(
    name, qty, unit, price, pub, uom, units
) -> None:
    got = read_unit_price(_item(price, name, qty, unit, pub, uom), "unit")
    assert got is not None and got.uom == "unit" and got.pack_units == units
    assert got.unit_price == D(price) / units
    # The same event through the history helper (it has no promo, only the price and the item).
    got2 = unit_price_in(D(price), D(pub) if pub else None, uom, D(qty), unit, "unit", name=name)
    assert got2 == (got.unit_price, "unit")


def test_the_fields_and_the_published_price_alone_are_what_the_chain_says() -> None:
    """No name: the old reading (the published unit price) is kept."""
    item = PricedItem(1, 1, D("14.20"), D("14.20"), "unit", False, NOW, D("1"), "יחידות")
    got = read_unit_price(item, "unit")
    assert got is not None and got.unit_price == D("14.20") and got.pack_units is None


def test_a_name_that_states_no_count_stays_per_pack() -> None:
    got = read_unit_price(_item("5.90", "חסה", "1", "יחידות", "5.90", "unit"), "unit")
    assert got is not None and got.unit_price == D("5.90") and got.pack_units is None
    assert got.note is None


def test_the_name_over_a_field_of_one_is_recorded() -> None:
    got = read_unit_price(_item("14.20", "ביצים 12 יח גדול L", "1.00", "יחידות"), "unit")
    assert got is not None and got.note is not None and got.note[0] == "count_from_name"


def test_disagreeing_counts_use_the_smaller_count_and_say_so() -> None:
    """Fields say 6, the name says 12: the safer reading is the dearer unit price (6 eggs)."""
    got = read_unit_price(_item("14.00", "ביצים 12 יח גדול", "6", "יחידות"), "unit")
    assert got is not None and got.pack_units == 6 and got.unit_price == D("14.00") / 6
    assert got.note is not None and got.note[0] == "count_conflict"
    assert "name 12" in got.note[1] and "fields 6" in got.note[1]
    # The published price says 30 eggs, the name 12: again the smaller count wins.
    got = read_unit_price(_item("30.00", "ביצים 12 יח גדול", None, None, "1.00", "unit"), "unit")
    assert got is not None and got.pack_units == 12 and got.note[0] == "count_conflict"


def test_a_published_price_that_matches_the_name_is_not_a_conflict() -> None:
    got = read_unit_price(_item("14.16", "ביצים 12 יח'", "12", "יחידות", "1.18", "unit"), "unit")
    assert got is not None and got.note is None


# per 100 ml / 100 g: the multi-pack total, the per-gram published price
def test_a_multipack_drink_is_priced_on_its_total_volume() -> None:
    """6 bottles of 1.5 L at 27.00: 9000 ml, 0.30 per 100 ml, even when the fields say 1 unit."""
    name = "קולה 6*1.5 ל'"
    got = read_unit_price(_item("27.00", name, "1", "יחידות"), "100ml")
    assert got is not None and got.uom == "100ml" and got.unit_price == D("0.3")
    assert got.pack_units is None and got.note is None
    # Before: Quantity 1 'יחידות' gave a unit price per unit, which has no 100 ml conversion.
    assert read_unit_price(_item("27.00", "קולה", "1", "יחידות"), "100ml") is None


# real rows of the committed fixtures: (name, Quantity, UnitQty, price, published per 100 ml, ml)
REAL_MULTIPACKS = [
    # Shufersal: 6 x 330 ml, the file says 1.98 ליטר and 23.94 per liter
    ('בירה קרומבאכר 6*330 מ"ל', "1.98", "ליטר", "47.40", "2.394", 1980),
    # King Store: 24 x 330 ml as 7920 מיליליטר, 3.77 per liter
    ("מארז מים קסטל 330 מ\"ל *24 יח'", "7920", "מיליליטר", "29.90", "0.377", 7920),
]


@pytest.mark.parametrize(
    ("name", "qty", "unit", "price", "published", "ml"),
    REAL_MULTIPACKS,
    ids=[c[0] for c in REAL_MULTIPACKS],
)
def test_real_multipacks_are_priced_on_the_total_volume(
    name, qty, unit, price, published, ml
) -> None:
    on_total = D(price) * 100 / ml
    for pub in (published, None):  # with the published unit price and without it
        got = read_unit_price(_item(price, name, qty, unit, pub, "100ml" if pub else None), "100ml")
        assert got is not None and got.uom == "100ml" and got.pack_units is None
        assert got.note is None and abs(got.unit_price - on_total) < D("0.001"), pub
    # The fields say "1 unit" (the Rami Levy way): the total comes from the name.
    got = read_unit_price(_item(price, name, "1", "יחידות"), "100ml")
    assert got is not None and got.unit_price == on_total and got.note is None


def test_a_per_100g_item_with_consistent_readings_is_unchanged() -> None:
    item = _item("5.90", "קוטג' 5% 250 גרם", "250", "גרם", "2.36", "100g")
    got = read_unit_price(item, "100g")
    assert got is not None and (got.unit_price, got.uom, got.pack_units, got.note) == (
        D("2.36"), "100g", None, None,
    )  # fmt: skip


def test_a_published_price_a_hundred_times_too_small_loses_to_the_pack() -> None:
    """Rami Levy's per-gram price read as per 100 g (finding 8): the fields and the name agree on
    7.55, so the published price is outvoted (it used to be "the dearer reading", the same value)."""
    item = _item("15.10", "שקד קלוי 200 גר", "200", "גרם", "0.08", "100g")
    got = read_unit_price(item, "100g")
    assert got is not None and got.unit_price == D("7.55")
    assert got.note is not None and got.note[0] == "measure_outvoted"


def test_weighed_goods_are_not_touched() -> None:
    item = PricedItem(1, 1, D("12.90"), D("12.90"), "kg", True, NOW, D("1"), 'ק"ג', "עגבניות", True)
    got = read_unit_price(item, "kg")
    assert got is not None and (got.unit_price, got.uom) == (D("12.90"), "kg")


# --- shelf_packs: the rule, no database ---------------------------------------------------------


def _choice(pack_units: str | None):
    from smartcart_api.basket import _Choice

    return _Choice(1, D(10), D(10), D(1), "unit", None, None, False, None, NOW, False,
                   None if pack_units is None else D(pack_units))  # fmt: skip


@pytest.mark.parametrize(
    ("pack_units", "quantity", "per_pack", "packs"),
    [
        ("12", "1", "12", "1"),  # a tray of 12 for 12 eggs
        ("12", "3", "12", "3"),
        ("30", "1", "12", "1"),  # 12 eggs from a tray of 30: one tray
        ("30", "2", "12", "1"),  # 24 eggs: still one
        ("30", "3", "12", "2"),  # 36 eggs: two trays
        ("6", "1", "12", "2"),  # 12 eggs from packs of 6: two
        ("6", "0.5", "12", "1"),  # 6 eggs: one pack of 6
        ("60", "5", "12", "1"),
        ("60", "6", "12", "2"),
        ("24", "1", "32", "2"),  # 32 rolls wanted, packs of 24
        (None, "2.5", "12", "2.5"),  # no count stated: the quantity counts shelf items
        ("12", "2.5", None, "2.5"),  # a weight or a volume
    ],
)
def test_whole_packs_for_the_quantity(pack_units, quantity, per_pack, packs) -> None:
    got = shelf_packs(_choice(pack_units), D(quantity), None if per_pack is None else D(per_pack))
    assert got == D(packs)


def test_units_per_pack_of_a_canonical() -> None:
    assert units_per_pack("unit", {"pack_size": 12, "unit": "unit"}) == 12
    assert units_per_pack("unit", {"pack_size": 1, "unit": "unit"}) == 1
    assert units_per_pack("unit", {}) == 1
    assert units_per_pack("unit", {"pack_size": 200, "unit": "g"}) == 1
    assert units_per_pack("100g", {"pack_size": 12, "unit": "unit"}) is None
    assert units_per_pack("kg", {}) is None


# --- the precompute and /compare ----------------------------------------------------------------


def add_counted_canonical(db, w: World, key: str, pack_size: int, base: str = "unit") -> int:
    unit = "unit" if base == "unit" else ("g" if base == "100g" else "ml")
    cid = db.execute(
        "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type,"
        " base_unit, critical_attrs, soft_attrs, is_mvp, rank)"
        " VALUES ('t.dairy.eggs', %s, %s, 't_wafer', %s, '{}', %s, true, 40) RETURNING id",
        (f"t-pk-{key}", key, base, Jsonb({"pack_size": pack_size, "unit": unit})),
    ).fetchone()[0]
    w.canon[key] = cid
    return cid


def add_pack_item(
    db,
    w: World,
    key: str,
    cid_key: str,
    chain: str,
    name: str,
    qty: str,
    unit: str,
    price: str,
    published: str | None = None,
    uom: str | None = None,
    level: str = "any_brand",
) -> int:
    iid = db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name, quantity, unit)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (chain, key, f"72999{len(w.items):08d}", name, D(qty), unit),
    ).fetchone()[0]
    w.items[key] = iid
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source)"
        " VALUES (%s, %s, %s, 0.95, 'rule')",
        (iid, w.canon[cid_key], level),
    )
    add_price(db, iid, None, price, published, uom, w.valid_from)
    return iid


def ep_row(db, w: World, canon: str, store: str, flex: str = "any_brand") -> dict:
    cur = db.execute(
        "SELECT item_id, shelf_price, effective_unit_price, uom, pack_units"
        " FROM effective_prices WHERE canonical_id = %s AND store_id = %s AND flex_level = %s",
        (w.canon[canon], w.stores[store], flex),
    )
    r = cur.fetchone()
    return dict(zip([c.name for c in cur.description], r, strict=True))


def line(client, w: World, canon: str, quantity, store: str = "home", **kw) -> dict:
    body = {
        "items": [{"canonical_id": w.canon[canon], "quantity": quantity, **kw}],
        "location": w.location,
    }
    r = client.post("/compare", json=body)
    assert r.status_code == 200, r.text
    stores = {s["store_id"]: s for s in r.json()["stores"]}
    items = stores[w.stores[store]]["items"]
    assert len(items) == 1
    return items[0]


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_precompute_prices_the_rami_levy_tray_per_egg_not_per_tray(db, world: World) -> None:
    add_counted_canonical(db, world, "eggs12", 12)
    add_pack_item(
        db, world, "rl12", "eggs12", "t-c1", "ביצים 12 יח גדול L", "1.00", "יחידות",
        "14.20", "14.20", "unit",
    )  # fmt: skip
    res = precompute_effective_prices(db, chains=world.chains)
    row = ep_row(db, world, "eggs12", "home")
    assert row["shelf_price"] == D("14.20") and row["pack_units"] == 12
    assert row["uom"] == "unit" and row["effective_unit_price"] == D("1.1833")  # not 14.20
    # The run records that the count came from the name (and not from the chain's fields).
    metrics = db.execute("SELECT metrics FROM match_runs WHERE id = %s", (res.run_id,)).fetchone()[
        0
    ]
    assert metrics["pack_reads"]["count_from_name"] >= 1
    assert any(
        s["name"] == "ביצים 12 יח גדול L" and s["kind"] == "count_from_name"
        for s in metrics["pack_samples"]
    )


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
@pytest.mark.parametrize(
    ("name", "qty", "unit", "price", "units"),
    [
        ("ביצים 12 יח גדול L", "1.00", "יחידות", "14.20", 12),
        ("ביצים 30יח ענק XL", "1.00", "יחידות", "33.90", 30),
        ("ביצים 2*30 יח' בינונ", "60.00", "יחידות", "28.90", 60),
        ("ביצים 18 יח' בינוני", "18.00", "יחידות", "21.50", 18),
    ],
)
def test_eggs_unit_price_per_egg_for_each_tray_size(
    db, world: World, name, qty, unit, price, units
) -> None:
    add_counted_canonical(db, world, "eggs", 12)
    add_pack_item(db, world, "x", "eggs", "t-c1", name, qty, unit, price, level="close")
    precompute_effective_prices(db, chains=world.chains)
    row = ep_row(db, world, "eggs", "home", "close")
    assert row["pack_units"] == units
    assert row["effective_unit_price"] == (D(price) / units).quantize(D("0.0001"))


# (name, Quantity, UnitQty, price, quantity asked, shelf items, line total, units in the item)
LINE_CASES = [
    ("ביצים 12 יח גדול L", "1.00", "יחידות", "14.20", 1, 1, "14.20", 12),
    ("ביצים 12 יח גדול L", "1.00", "יחידות", "14.20", 3, 3, "42.60", 12),
    ("ביצים 30 יח' גדול מן", "30.00", "יחידות", "29.90", 1, 1, "29.90", 30),  # 12 eggs, one tray
    ("ביצים 30 יח' גדול מן", "30.00", "יחידות", "29.90", 2, 1, "29.90", 30),  # 24 eggs, one tray
    ("ביצים 30 יח' גדול מן", "30.00", "יחידות", "29.90", 3, 2, "59.80", 30),  # 36 eggs, two trays
    ("ביצים 18 יח' בינוני", "18.00", "יחידות", "21.50", 1, 1, "21.50", 18),
    ("ביצים 18 יח' בינוני", "18.00", "יחידות", "21.50", 4, 3, "64.50", 18),  # 48 eggs: 3 x 18 = 54
    ("ביצים 2*30 יח' בינונ", "60.00", "יחידות", "28.90", 5, 1, "28.90", 60),  # 60 eggs, one pack
    ("ביצים 2*30 יח' בינונ", "60.00", "יחידות", "28.90", 6, 2, "57.80", 60),  # 72 eggs
    ("ביצים 6 יח'", "6.00", "יחידות", "8.40", 1, 2, "16.80", 6),  # 12 eggs from packs of 6
    ("ביצים 6 יח'", "6.00", "יחידות", "8.40", 0.5, 1, "8.40", 6),  # 6 eggs
    ("ביצים 12 יח גדול L", "1.00", "יחידות", "14.20", 0.5, 1, "14.20", 12),  # 6 eggs: one pack
]


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
@pytest.mark.parametrize(
    ("name", "qty", "unit", "price", "asked", "packs", "total", "units"),
    LINE_CASES,
    ids=[f"{c[0]}-x{c[4]}" for c in LINE_CASES],
)
def test_compare_line_total_buys_whole_packs(
    client, db, world: World, name, qty, unit, price, asked, packs, total, units
) -> None:
    add_counted_canonical(db, world, "eggs", 12)
    add_pack_item(db, world, "x", "eggs", "t-c1", name, qty, unit, price, level="close")
    precompute_effective_prices(db, chains=world.chains)
    got = line(client, world, "eggs", asked, flex_level="close")
    assert D(got["packs"]) == packs and D(got["quantity"]) == D(str(asked))
    assert D(got["line_total"]) == D(total)
    assert D(got["line_total"]) == money(D(price) * packs)
    assert D(got["pack_units"]) == units


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_the_basket_no_longer_prices_eggs_at_170(client, db, world: World) -> None:
    """Rami Levy's 12-pack at 14.20: the line was 12 x 14.20 = 170.40 for 12 eggs before."""
    add_counted_canonical(db, world, "eggs", 12)
    add_pack_item(
        db, world, "rl", "eggs", "t-c1", "ביצים 12 יח גדול L", "1.00", "יחידות", "14.20", "14.20",
        "unit",
    )  # fmt: skip
    precompute_effective_prices(db, chains=world.chains)
    got = line(client, world, "eggs", 1)
    assert D(got["line_total"]) == D("14.20")
    assert D(got["effective_unit_price"]) == D("1.1833") and got["uom"] == "unit"


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_a_tray_wins_the_unit_price_but_not_the_line_for_twelve_eggs(
    client, db, world: World
) -> None:
    """At close, 30 eggs for 29.90 (1.00 an egg) beat 12 for 14.20 (1.18) by unit price, which is
    what /search and the effective_prices row rank by. The line for 12 eggs is the 12-pack, 14.20,
    the cheapest way to buy 12; 30 eggs are the tray (docs/optimizer.md, "Offers for the quantity
    asked"). It used to be the whole tray, 29.90, for 12 eggs."""
    add_counted_canonical(db, world, "eggs", 12)
    add_pack_item(db, world, "p12", "eggs", "t-c1", "ביצים 12 יח גדול L", "1.00", "יחידות", "14.20")
    add_pack_item(
        db, world, "p30", "eggs", "t-c1", "ביצים 30 יח' גדול מן", "30.00", "יחידות", "29.90",
        level="close",
    )  # fmt: skip
    precompute_effective_prices(db, chains=world.chains)
    assert ep_row(db, world, "eggs", "home", "close")["item_id"] == world.items["p30"]  # rank 0
    any_brand = line(client, world, "eggs", 1)
    assert any_brand["item_id"] == world.items["p12"] and D(any_brand["line_total"]) == D("14.20")
    close = line(client, world, "eggs", 1, flex_level="close")  # 12 eggs
    assert close["item_id"] == world.items["p12"] and D(close["packs"]) == 1
    assert D(close["line_total"]) == D("14.20") and not close["is_substitute"]
    tray = line(client, world, "eggs", 2.5, flex_level="close")  # 30 eggs
    assert tray["item_id"] == world.items["p30"] and D(tray["packs"]) == 1
    assert D(tray["line_total"]) == D("29.90") and tray["is_substitute"]
    two = line(client, world, "eggs", 2, flex_level="close")  # 24 eggs: 2 packs, not a tray
    assert two["item_id"] == world.items["p12"] and D(two["line_total"]) == D("28.40")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_a_promo_counts_shelf_packs(client, db, world: World) -> None:
    """'2 for 25' on a pack of 6 eggs: 12 eggs are two packs, which reach the promo."""
    add_counted_canonical(db, world, "eggs", 12)
    iid = add_pack_item(
        db, world, "p6", "eggs", "t-c1", "ביצים 6 יח'", "6.00", "יחידות", "8.40", level="close"
    )
    add_promo(db, "t-c1", None, "PK", [iid], "bundle", "14.00", min_qty="2", description="2 ב-14")
    precompute_effective_prices(db, chains=world.chains)
    got = line(client, world, "eggs", 1, flex_level="close")
    assert D(got["packs"]) == 2 and D(got["line_total"]) == D("14.00") and got["promo_applied"]
    three = line(client, world, "eggs", 1.5, flex_level="close")  # 18 eggs: three packs
    assert D(three["packs"]) == 3
    assert D(three["line_total"]) == D("22.40")  # one bundle 14.00 + one at 8.40
    assert D(three["promo_add_qty"]) == 1  # one more pack completes the second bundle


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_optimize_reads_the_packs(client, db, world: World) -> None:
    """The MILP counts the shelf packs of each line, so its total equals /compare's."""
    add_counted_canonical(db, world, "eggs", 12)
    iid = add_pack_item(
        db, world, "p6", "eggs", "t-c1", "ביצים 6 יח'", "6.00", "יחידות", "8.40", level="close"
    )
    add_promo(db, "t-c1", None, "PK", [iid], "bundle", "14.00", min_qty="2", description="2 ב-14")
    precompute_effective_prices(db, chains=world.chains)
    body = {
        "items": [{"canonical_id": world.canon["eggs"], "quantity": 1, "flex_level": "close"}],
        "location": world.location,
    }
    cmp_total = {
        s["store_id"]: D(s["total"]) for s in client.post("/compare", json=body).json()["stores"]
    }
    r = client.post("/optimize", json=body)
    assert r.status_code == 200, r.text
    store = r.json()["single"]["stores"][0]["store"]
    assert D(store["total"]) == cmp_total[store["store_id"]] == D("14.00")
    only = store["items"][0]
    assert D(only["packs"]) == 2 and D(only["line_total"]) == D("14.00")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_a_per_100g_item_is_not_affected(client, db, world: World) -> None:
    """Quantity still counts shelf items for a canonical in grams or millilitres."""
    add_counted_canonical(db, world, "yog", 150, base="100g")
    add_pack_item(
        db, world, "y4", "yog", "t-c1", "מארז 8 יוגורט פרי 150 גרם", "1200", "גרם", "16.00",
        "1.33", "100g",
    )  # fmt: skip
    add_counted_canonical(db, world, "cola", 1500, base="100ml")
    add_pack_item(
        db, world, "cola6", "cola", "t-c1", "קולה 6*1.5 ל'", "1", "יחידות", "27.00",
    )  # fmt: skip
    precompute_effective_prices(db, chains=world.chains)
    y = ep_row(db, world, "yog", "home")
    assert y["pack_units"] is None and y["uom"] == "100g"
    assert y["effective_unit_price"] == D("1.3300")  # the published 1.33 (16.00 per 1200 g)
    for qty in (1, 2, 2.5):
        got = line(client, world, "yog", qty)
        assert D(got["packs"]) == D(str(qty)) and got["pack_units"] is None
        assert D(got["line_total"]) == money(D("16.00") * D(str(qty)))
    c = ep_row(db, world, "cola", "home")
    assert c["pack_units"] is None and c["uom"] == "100ml"
    assert c["effective_unit_price"] == D("0.3000")  # 27.00 per 9000 ml, not per "1 unit"
    got = line(client, world, "cola", 2)
    assert D(got["line_total"]) == D("54.00") and D(got["packs"]) == 2


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_exact_barcode_quantities_count_that_item(client, db, world: World) -> None:
    """An exact item is the product asked for: its quantity counts that item, not eggs."""
    add_counted_canonical(db, world, "eggs", 12)
    iid = add_pack_item(
        db, world, "p30", "eggs", "t-c1", "ביצים 30 יח' גדול מן", "30.00", "יחידות", "29.90",
        level="exact",
    )  # fmt: skip
    precompute_effective_prices(db, chains=world.chains)
    got = line(client, world, "eggs", 2, flex_level="exact", exact_item_id=iid)
    assert D(got["packs"]) == 2 and D(got["line_total"]) == D("59.80")


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_rows_from_before_the_migration_keep_counting_shelf_items(client, db, world: World) -> None:
    """A precomputed row with no pack_units (an older run) prices as it always did."""
    add_counted_canonical(db, world, "eggs", 12)
    add_pack_item(
        db, world, "p30", "eggs", "t-c1", "ביצים 30 יח' גדול מן", "30.00", "יחידות", "29.90"
    )
    precompute_effective_prices(db, chains=world.chains)
    db.execute("UPDATE effective_prices SET pack_units = NULL")
    got = line(client, world, "eggs", 2)
    assert D(got["packs"]) == 2 and D(got["line_total"]) == D("59.80")
    assert got["pack_units"] is None


def test_priced_item_model_accepts_a_line_without_packs() -> None:
    li = schemas.PricedItem(
        canonical_id=1, item_id=1, display_name_he="x", quantity=D(1), shelf_price=D(1),
        effective_unit_price=D(1), uom="unit", line_total=D(1), is_substitute=False,
        price_valid_from=NOW,
    )  # fmt: skip
    assert li.packs is None and li.pack_units is None


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_price_history_is_per_egg_too(client, db, world: World) -> None:
    """The history chart of a tray reads the same count as the basket, not 14.40 per unit."""
    add_counted_canonical(db, world, "eggs", 12)
    add_pack_item(
        db, world, "rl", "eggs", "t-c1", "ביצים 12 יח גדול L", "1.00", "יחידות", "14.40", "14.40",
        "unit",
    )  # fmt: skip
    precompute_effective_prices(db, chains=world.chains)
    r = client.get(f"/history/{world.canon['eggs']}", params={"days": 3})
    assert r.status_code == 200, r.text
    prices = {D(p["unit_price"]) for p in r.json()["points"] if p["unit_price"] is not None}
    assert prices == {D("1.2000")}


# --- the sanity cap of the fallback (Mega's gram packs labelled as liters) -------------------------


@pytest.mark.parametrize(
    ("qty", "unit"),
    [
        ("200", "ליטר"),  # Mega 'ליטר 1' rows carry 80 to 686 "liters" of chips and spices
        ("80", "ליטר"),
        ("686", "ליטר"),
        ("50.1", "ליטר"),
        ("50001", "מיליליטר"),
        ("50.5", 'ק"ג'),
        ("50001", "גרם"),
        ("10001", "יחידות"),
    ],
)
def test_the_fallback_refuses_an_insane_pack(qty, unit) -> None:
    assert derive_unit_price(D("12.90"), D(qty), unit) is None


@pytest.mark.parametrize(
    ("qty", "unit", "per100"),
    [
        ("50", "ליטר", D("12.90") * 100 / 50000),  # the limit itself is a real pack
        ("7920", "מיליליטר", D("12.90") * 100 / 7920),  # the largest real volume (King Store)
        ("8", 'ק"ג', D("12.90") * 100 / 8000),  # the largest real weight
    ],
)
def test_the_fallback_keeps_the_largest_real_packs(qty, unit, per100) -> None:
    got = derive_unit_price(D("12.90"), D(qty), unit)
    assert got is not None and got[0] == per100
    assert derive_unit_price(D("12.90"), D("10000"), "יחידות") == (D("12.90") / 10000, "unit")


def test_a_gram_pack_labelled_as_liters_gets_no_unit_price() -> None:
    """The loader leaves the unit price NULL for these rows; the precompute must not compute
    one from the same fields: '200 liters' of chips is no price per 100 ml."""
    chips = _item("7.90", "צ'יפס פיקנטי 200", "200", "ליטר")
    assert read_unit_price(chips, "100ml") is None  # a liter canonical: no price, not 0.0040
    assert read_unit_price(chips, "100g") is None  # nor 200 liters read as 200 kg of anything
    assert read_unit_price(chips, "unit") is not None  # per pack, as an item of unknown size


def test_the_name_still_prices_a_mislabelled_pack_when_it_states_a_sane_size() -> None:
    """The fields are refused, the name '200 גרם' is not: per 100 g, and still no per-100 ml."""
    chips = _item("7.90", "צ'יפס פיקנטי 200 גרם", "200", "ליטר")
    got = read_unit_price(chips, "100g")
    assert got is not None and got.unit_price == D("3.95") and got.uom == "100g"
    assert read_unit_price(chips, "100ml") is None  # a dimension the canonical does not have


@pytest.mark.db
@pytest.mark.postgis
@pytest.mark.pgvector
def test_precompute_gives_a_mislabelled_item_no_row(db, world: World) -> None:
    add_counted_canonical(db, world, "soda", 1000, base="100ml")
    add_pack_item(db, world, "chips", "soda", "t-c1", "צ'יפס פיקנטי 200", "200", "ליטר", "7.90")
    precompute_effective_prices(db, chains=world.chains)
    assert (
        db.execute(
            "SELECT count(*) FROM effective_prices WHERE canonical_id = %s",
            (world.canon["soda"],),
        ).fetchone()[0]
        == 0
    )
