"""The loader stores the computed unit price and counts the published ones that disagree
(docs/ingestion.md, "Unit prices"). Real Rami Levy PriceFull of 2026-10-21 and the fake chain."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from smartcart_ingest import tracking
from smartcart_ingest.loader import load
from tests.fakes import NOW, FakeAdapter, encode, item, parsed_file, price
from tests.test_adapters import FIXTURES, chain_adapters, parse_fixture

D = Decimal
RAMI = "7290058140886"
T0 = NOW - timedelta(hours=4)

pytestmark = pytest.mark.db


def _load_real_rami(db):
    adapter = chain_adapters()["ramilevy"]()
    path = next((FIXTURES / "ramilevy" / "real").glob("PriceFull*"))
    parsed = parse_fixture(adapter, path)
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    return load(db, parsed, adapter), parsed


def _stored(db, code: str) -> list[tuple]:
    return db.execute(
        "SELECT p.price, p.unit_price, p.uom, p.is_estimated FROM prices p"
        " JOIN items i ON i.id = p.item_id WHERE i.chain_id = %s AND i.item_code = %s",
        (RAMI, code),
    ).fetchall()


def test_rami_levy_weight_and_volume_are_stored_per_100g_and_per_100ml(db) -> None:
    result, parsed = _load_real_rami(db)
    assert result.prices_written == len(parsed.prices) == 200
    # 15.10 for 200 g of almonds published as 0.08 "per 100 g": stored as 7.55, not 0.08
    assert _stored(db, "7290018566183") == [(D("15.10"), D("7.55"), "100g", False)]
    # 10.00 for 1 kg of wheat published as 0.01
    assert _stored(db, "7290119671748") == [(D("10.00"), D("1.00"), "100g", False)]
    # 2.90 for 500 ml of soda published as 0.01 "per 100 ml"; 8.60 for 2 l of cola as 4.30 per l
    assert _stored(db, "7290000135342") == [(D("2.90"), D("0.58"), "100ml", False)]
    assert _stored(db, "7290110119508") == [(D("8.60"), D("0.43"), "100ml", False)]
    # a weighed item stays per kg and estimated
    assert _stored(db, "7290000000541") == [(D("6.90"), D("6.90"), "kg", True)]


def test_disagreements_are_counted_and_never_stop_the_load(db) -> None:
    result, parsed = _load_real_rami(db)
    assert result.unit_price_sources == {"computed": 197, "weighed": 3}
    # 195 rows agree under the chain's measured reading; the two "2   יחידות" rows do not
    assert result.unit_price_disagreements == {"other": 2}
    row = tracking.get_by_sha(db, parsed.raw.sha256)
    assert row is not None and row.status == "loaded"
    assert db.execute(
        "SELECT count(*) FROM prices p JOIN items i ON i.id = p.item_id WHERE i.chain_id = %s",
        (RAMI,),
    ).fetchone() == (200,)


def test_a_hundred_times_disagreement_still_loads_the_price(db) -> None:
    """The fake chain has no measured rule, so its per-gram value under "100 גרם" is a 100x
    disagreement: counted, and the stored unit price is the computed one."""
    rows = [
        price(
            "A", "1", "15.10", unit_price=D("0.08"), unit_of_measure="100 גרם",
            quantity=D("200"), quantity_unit="גרם",
        ),
        price("B", "1", "9.90", unit_price=D("4.95"), unit_of_measure="100 גרם",
              quantity=D("200"), quantity_unit="גרם"),
    ]  # fmt: skip
    data = encode(items=[item("A"), item("B")], prices=rows)
    parsed = parsed_file("price_full", data, "1", T0, "raw/fake/pf-unit")
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    result = load(db, parsed, FakeAdapter())
    assert result.unit_price_disagreements == {"off_x100_low": 1}
    assert result.unit_price_sources == {"computed": 2}
    got = dict(
        db.execute(
            "SELECT i.item_code, p.unit_price FROM prices p JOIN items i ON i.id = p.item_id"
            " WHERE i.chain_id = 'fake'"
        ).fetchall()
    )
    assert got == {"A": D("7.55"), "B": D("4.95")}


def test_a_wrong_value_stored_by_an_earlier_load_is_corrected_in_place(db) -> None:
    """Event key (item, store, valid_from): the same observation time with a different unit price
    is rewritten, so the 100x values stored before this change are fixed by the next load."""
    first = encode(items=[item("A")], prices=[price("A", "1", "15.10", unit_price=D("0.08"),
                    unit_of_measure="100 גרם")])  # fmt: skip
    old = parsed_file("price_full", first, "1", T0, "raw/fake/pf-old")
    row, _ = tracking.register(db, old.raw)
    tracking.mark_downloaded(db, row.id, old.raw.path)
    load(db, old, FakeAdapter())
    # no pack size: the label is read as published, which is what the old loader stored
    assert db.execute("SELECT unit_price FROM prices").fetchall() == [(D("0.08"),)]
    second = encode(
        items=[item("A")],
        prices=[
            price("A", "1", "15.10", unit_price=D("0.08"), unit_of_measure="100 גרם",
                  quantity=D("200"), quantity_unit="גרם")
        ],
        salt="2",
    )  # fmt: skip
    new = parsed_file("price_full", second, "1", T0, "raw/fake/pf-new")
    row, _ = tracking.register(db, new.raw)
    tracking.mark_downloaded(db, row.id, new.raw.path)
    result = load(db, new, FakeAdapter())
    assert result.prices_written == 1
    assert db.execute("SELECT price, unit_price, uom FROM prices").fetchall() == [
        (D("15.10"), D("7.55"), "100g")
    ]
