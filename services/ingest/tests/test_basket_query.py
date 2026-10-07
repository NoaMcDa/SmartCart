"""The basket-in-a-radius query, supabase/queries/basket_radius.sql (issue #60, exit criterion 4).

Synthetic data only: two chains, four stores around Tel Aviv and one in Jerusalem. Skipped locally
when the server has no PostGIS; CI runs it against supabase/postgres.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from smartcart_ingest import report

pytestmark = [pytest.mark.db, pytest.mark.postgis]

CENTER = (34.7918, 32.0744)  # Tel Aviv, Azrieli
EAST_940M = (34.8018, 32.0744)
JERUSALEM = (35.2033, 31.7890)  # about 50 km away
RADIUS_M = 3000

MILK, BREAD, SALT = "7290000000011", "7290000000012", "7290000000013"
MISSING_EVERYWHERE = "7290000000099"


@dataclass(frozen=True)
class World:
    a_near: int  # chain A, at the center
    b_near: int  # chain B, 940 m east
    a_far: int  # chain A, in Jerusalem
    a_online: int  # chain A online store, located at the center
    chain_a_items: dict[str, int]
    chain_b_items: dict[str, int]


def _now() -> datetime:
    return datetime.now(UTC)


def _price(db, item_id, store_id, price, valid_from) -> None:
    # The loader's rule: make sure the month's partition exists before inserting.
    db.execute("SELECT ensure_price_partition(%s)", (valid_from.date(),))
    db.execute(
        "INSERT INTO prices (item_id, store_id, price, unit_price, uom, valid_from)"
        " VALUES (%s, %s, %s, %s, 'unit', %s)",
        (item_id, store_id, Decimal(price), Decimal(price), valid_from),
    )


def _store(db, chain, code, point, channel="physical") -> int:
    return db.execute(
        "INSERT INTO stores (chain_id, store_code, name, city, channel, geog)"
        " VALUES (%s, %s, %s, 'Test', %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography)"
        " RETURNING id",
        (chain, code, f"{chain} {code}", channel, *point),
    ).fetchone()[0]


def _item(db, chain, code, barcode) -> int:
    return db.execute(
        "INSERT INTO items (chain_id, item_code, barcode, raw_name) VALUES (%s, %s, %s, %s)"
        " RETURNING id",
        (chain, code, barcode, f"item {code}"),
    ).fetchone()[0]


@pytest.fixture
def world(db) -> World:
    """Prices as of now:

    chain A: milk base 10.00, replaced 10 days ago by 9.00 (an even newer 1.00 is in the future,
             so it must be ignored); bread base 5.00 with a store exception of 4.50 at a_near;
             salt is not sold.
    chain B: milk base 7.50; bread exists as an item but has no price at all; salt is not sold.
    """
    for chain in ("chain-a", "chain-b"):
        db.execute("INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (chain, chain))
    a_near = _store(db, "chain-a", "001", CENTER)
    b_near = _store(db, "chain-b", "001", EAST_940M)
    a_far = _store(db, "chain-a", "002", JERUSALEM)
    a_online = _store(db, "chain-a", "web", CENTER, channel="online")

    a = {"milk": _item(db, "chain-a", "m", MILK), "bread": _item(db, "chain-a", "b", BREAD)}
    b = {"milk": _item(db, "chain-b", "m", MILK), "bread": _item(db, "chain-b", "b", BREAD)}

    now = _now()
    _price(db, a["milk"], None, "10.00", now - timedelta(days=40))
    _price(db, a["milk"], None, "9.00", now - timedelta(days=10))
    _price(db, a["milk"], None, "1.00", now + timedelta(days=1))  # not in force yet
    _price(db, a["bread"], None, "5.00", now - timedelta(days=40))
    _price(db, a["bread"], a_near, "4.50", now - timedelta(days=5))  # store exception
    _price(db, b["milk"], None, "7.50", now - timedelta(days=3))
    return World(a_near, b_near, a_far, a_online, a, b)


def _run(db, world: World, barcodes, include_online=False, radius_m=RADIUS_M):
    """Rows of the query, restricted to this test's stores so other data cannot interfere."""
    ours = {world.a_near, world.b_near, world.a_far, world.a_online}
    rows = report.run_basket_query(db, barcodes, *CENTER, radius_m, include_online)
    return {r["store_id"]: r for r in rows if r["store_id"] in ours}, rows


def test_per_store_totals_found_counts_and_missing_barcodes(db, world) -> None:
    by_store, _ = _run(db, world, [MILK, BREAD, SALT])

    near = by_store[world.a_near]
    assert near["basket_total"] == Decimal("13.50")  # milk 9.00 (latest in force) + bread 4.50
    assert near["found_count"] == 2
    assert near["missing_barcodes"] == [SALT]
    assert near["is_complete"] is False
    assert near["chain_id"] == "chain-a" and near["channel"] == "physical"
    assert near["distance_m"] <= 1

    east = by_store[world.b_near]
    assert east["basket_total"] == Decimal("7.50")  # only milk is priced at chain B
    assert east["found_count"] == 1
    assert east["missing_barcodes"] == [BREAD, SALT]  # bread has an item but no price
    assert 900 < east["distance_m"] < 1000


def test_online_store_is_excluded_unless_requested(db, world) -> None:
    by_store, _ = _run(db, world, [MILK, BREAD, SALT])
    assert world.a_online not in by_store

    with_online, _ = _run(db, world, [MILK, BREAD, SALT], include_online=True)
    online = with_online[world.a_online]
    assert online["channel"] == "online"
    assert online["basket_total"] == Decimal("14.00")  # base prices only: 9.00 + 5.00
    assert online["missing_barcodes"] == [SALT]
    assert set(with_online) == {world.a_near, world.b_near, world.a_online}


def test_store_outside_the_radius_is_excluded(db, world) -> None:
    by_store, _ = _run(db, world, [MILK])
    assert world.a_far not in by_store
    assert set(by_store) == {world.a_near, world.b_near}

    # A radius that reaches Jerusalem brings the far store in, priced from the chain base prices.
    wide, _ = _run(db, world, [MILK, BREAD], radius_m=80_000)
    assert wide[world.a_far]["basket_total"] == Decimal("14.00")
    # And a tiny radius leaves out the store 940 m away.
    tiny, _ = _run(db, world, [MILK], radius_m=500)
    assert set(tiny) == {world.a_near}


def test_a_store_missing_everything_still_appears_with_a_zero_total(db, world) -> None:
    by_store, _ = _run(db, world, [MISSING_EVERYWHERE, SALT])
    for store_id in (world.a_near, world.b_near):
        row = by_store[store_id]
        assert row["found_count"] == 0
        assert row["basket_total"] == 0
        assert row["missing_barcodes"] == sorted([MISSING_EVERYWHERE, SALT])
        assert row["is_complete"] is False


def test_complete_baskets_sort_before_partial_ones_even_when_partial_is_cheaper(db, world) -> None:
    # Chain B sells milk only, so for [MILK] both stores are complete and B (7.50) is cheaper.
    by_store, rows = _run(db, world, [MILK])
    assert by_store[world.b_near]["is_complete"] and by_store[world.a_near]["is_complete"]
    order = [r["store_id"] for r in rows if r["store_id"] in by_store]
    assert order == [world.b_near, world.a_near]

    # For [MILK, BREAD] chain B is cheaper in total (7.50 against 13.50) but incomplete.
    by_store, rows = _run(db, world, [MILK, BREAD])
    order = [r["store_id"] for r in rows if r["store_id"] in by_store]
    assert order == [world.a_near, world.b_near]
    assert by_store[world.a_near]["is_complete"] and not by_store[world.b_near]["is_complete"]


def test_duplicate_and_null_barcodes_are_collapsed(db, world) -> None:
    by_store, _ = _run(db, world, [MILK, MILK, None, MILK])
    assert by_store[world.a_near]["basket_total"] == Decimal("9.00")
    assert by_store[world.a_near]["found_count"] == 1
    assert by_store[world.a_near]["missing_barcodes"] == []
    assert by_store[world.a_near]["is_complete"] is True


def test_a_newer_store_event_supersedes_the_exception_and_the_base_price(db, world) -> None:
    # A newer store-specific event for bread: it wins over the older exception, and the chain
    # base price is not consulted again.
    _price(db, world.chain_a_items["bread"], world.a_near, "5.20", _now() - timedelta(hours=1))
    by_store, _ = _run(db, world, [BREAD])
    assert by_store[world.a_near]["basket_total"] == Decimal("5.20")
    # A different store of the chain is unaffected by the exception.
    with_online, _ = _run(db, world, [BREAD], include_online=True)
    assert with_online[world.a_online]["basket_total"] == Decimal("5.00")


def test_same_barcode_twice_in_a_chain_uses_the_cheapest_item(db, world) -> None:
    twin = _item(db, "chain-a", "m-twin", MILK)
    _price(db, twin, None, "8.25", _now() - timedelta(days=1))
    by_store, _ = _run(db, world, [MILK])
    assert by_store[world.a_near]["basket_total"] == Decimal("8.25")
    assert by_store[world.a_near]["found_count"] == 1  # one barcode, counted once


def test_empty_basket_returns_no_rows(db, world) -> None:
    _, rows = _run(db, world, [])
    assert rows == []
