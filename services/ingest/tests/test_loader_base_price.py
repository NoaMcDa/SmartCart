"""Chain base prices in the loader (issue #80).

A ``PriceRecord`` with ``store_code=None`` is the chain base price: it is written with
``store_id NULL``, ``current_price()`` returns it for stores without an exception, and a store
record becomes a store event only when it differs from the price in force at that store.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from smartcart_ingest import tracking
from smartcart_ingest.loader import load
from smartcart_ingest.models import ParsedFile, PriceRecord
from tests.fakes import NOW, FakeAdapter, encode, item, parsed_file, price, store

pytestmark = pytest.mark.db
T0 = NOW - timedelta(hours=6)
T1 = NOW - timedelta(hours=3)


def _load(db, prices, salt: str, stores=("1", "2", "3")) -> object:
    codes = sorted({p.item_code for p in prices})
    data = encode(
        stores=[store(c) for c in stores],
        items=[item(c) for c in codes],
        prices=prices,
        salt=salt,
    )
    parsed: ParsedFile = parsed_file("price_full", data, None, T0, f"raw/fake/base-{salt}")
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    return load(db, parsed, FakeAdapter())


def _store_id(db, code: str) -> int:
    return db.execute(
        "SELECT id FROM stores WHERE chain_id = 'fake' AND store_code = %s", (code,)
    ).fetchone()[0]


def _item_id(db, code: str) -> int:
    return db.execute(
        "SELECT id FROM items WHERE chain_id = 'fake' AND item_code = %s", (code,)
    ).fetchone()[0]


def _rows(db, code: str) -> list[tuple]:
    return db.execute(
        "SELECT s.store_code, p.price FROM prices p LEFT JOIN stores s ON s.id = p.store_id"
        " WHERE p.item_id = %s ORDER BY s.store_code NULLS FIRST, p.valid_from",
        (_item_id(db, code),),
    ).fetchall()


def _current(db, code: str, store_code: str) -> tuple[Decimal, bool]:
    return db.execute(
        "SELECT price, is_store_price FROM current_price(%s, %s)",
        (_item_id(db, code), _store_id(db, store_code)),
    ).fetchone()


def test_price_record_accepts_a_chain_level_record() -> None:
    p = PriceRecord(chain_id="c", store_code=None, item_code="1", price=Decimal(1), observed_at=NOW)
    assert p.store_code is None


def test_base_price_is_written_with_null_store_and_inherited(db) -> None:
    result = _load(db, [price("100", None, "9.90", T0)], "a")
    assert result.base_prices_written == 1
    assert _rows(db, "100") == [(None, Decimal("9.90"))]
    for code in ("1", "2", "3"):
        assert _current(db, "100", code) == (Decimal("9.90"), False)


def test_store_event_only_when_it_differs_from_the_base(db) -> None:
    result = _load(
        db,
        [
            price("100", None, "9.90", T0),
            price("100", "1", "9.90", T0),  # same as the base: not stored
            price("100", "2", "8.50", T0),  # an exception
        ],
        "b",
    )
    assert result.prices_same_as_base == 1
    assert _rows(db, "100") == [(None, Decimal("9.90")), ("2", Decimal("8.50"))]
    assert _current(db, "100", "1") == (Decimal("9.90"), False)
    assert _current(db, "100", "2") == (Decimal("8.50"), True)
    assert _current(db, "100", "3") == (Decimal("9.90"), False)


def test_return_to_base_supersedes_the_exception(db) -> None:
    _load(db, [price("100", None, "9.90", T0), price("100", "2", "8.50", T0)], "c1")
    # Later the store goes back to the base price: a store event must be written, otherwise
    # the old exception would stay in force.
    result = _load(db, [price("100", None, "9.90", T1), price("100", "2", "9.90", T1)], "c2")
    assert result.prices_written == 1  # the base is unchanged, the store returns to it
    assert _current(db, "100", "2") == (Decimal("9.90"), True)


def test_base_change_is_followed_by_stores_without_exception(db) -> None:
    _load(db, [price("100", None, "9.90", T0)], "d1")
    _load(db, [price("100", None, "10.90", T1)], "d2")
    assert _current(db, "100", "1") == (Decimal("10.90"), False)
    assert [r[1] for r in _rows(db, "100")] == [Decimal("9.90"), Decimal("10.90")]


def test_store_keeping_the_old_price_after_a_base_change_gets_an_exception(db) -> None:
    _load(db, [price("100", None, "9.90", T0)], "e1")
    _load(db, [price("100", None, "10.90", T1), price("100", "1", "9.90", T1)], "e2")
    assert _current(db, "100", "1") == (Decimal("9.90"), True)
    assert _current(db, "100", "2") == (Decimal("10.90"), False)


def test_per_store_files_still_work_without_a_base(db) -> None:
    result = _load(db, [price("100", "1", "7.00", T0)], "f")
    assert result.prices_written == 1 and result.base_prices_written == 0
    assert _rows(db, "100") == [("1", Decimal("7.00"))]
