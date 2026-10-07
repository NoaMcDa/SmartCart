"""The transactional loader (issue #37)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from smartcart_ingest import loader, tracking
from smartcart_ingest.loader import LoadError, load, normalize_unit_price
from smartcart_ingest.models import ParsedFile
from tests.fakes import (
    ISRAEL,
    NOW,
    FakeAdapter,
    counts,
    encode,
    item,
    parsed_file,
    price,
    promo,
    store,
)

D = Decimal

# --- unit prices (no database) -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("unit_price", "uom_in", "weighed", "expected"),
    [
        ("1.20", "100 גרם", False, (D("1.20"), "100g", False)),
        ("0.012", "גרם", False, (D("1.2"), "100g", False)),
        ("12", 'ק"ג', False, (D("1.2"), "100g", False)),
        ("12", 'לק"ג', False, (D("1.2"), "100g", False)),
        ("6.90", "ליטר", False, (D("0.69"), "100ml", False)),
        ("0.69", '100 מ"ל', False, (D("0.69"), "100ml", False)),
        ("3", "יחידה", False, (D("3"), "unit", False)),
        ("3", "יח'", False, (D("3"), "unit", False)),
        ("1.5", "ל-100 גרם", False, (D("1.5"), "100g", False)),
        ("9.90", 'ק"ג', True, (D("9.90"), "kg", True)),
        (None, None, True, (D("9.90"), "kg", True)),  # weighed: the shelf price is per kg
        ("2", "100ml", False, (D("2"), "100ml", False)),
        ("2", "דונם", False, (None, None, False)),  # unknown unit: no unit price
        (None, "ליטר", False, (None, None, False)),
    ],
)
def test_normalize_unit_price(unit_price, uom_in, weighed, expected) -> None:
    got = normalize_unit_price(D("9.90"), D(unit_price) if unit_price else None, uom_in, weighed)
    assert got[1:] == expected[1:]
    assert got[0] == expected[0]


# --- database ----------------------------------------------------------------------------------

pytestmark = pytest.mark.db
T0 = NOW - timedelta(hours=4)


def _track(db, parsed: ParsedFile) -> tracking.TrackedFile:
    row, _ = tracking.register(db, parsed.raw)
    return tracking.mark_downloaded(db, row.id, parsed.raw.path)


def _price_full(rows, items=None, store_code="1", at=T0, salt="", path=None) -> ParsedFile:
    items = items if items is not None else [item(p.item_code) for p in rows]
    data = encode(items=items, prices=rows, salt=salt)
    return parsed_file("price_full", data, store_code, at, path or f"raw/fake/pf-{salt}")


def _events(db, item_code: str, store_code: str = "1") -> list[tuple]:
    return db.execute(
        "SELECT p.price, p.unit_price, p.uom, p.is_estimated, p.valid_from FROM prices p"
        " JOIN items i ON i.id = p.item_id JOIN stores s ON s.id = p.store_id"
        " WHERE i.chain_id = 'fake' AND i.item_code = %s AND s.store_code = %s"
        " ORDER BY p.valid_from",
        (item_code, store_code),
    ).fetchall()


def test_stores_file_upserts_stores_and_applies_the_online_rule(db) -> None:
    data = encode(
        stores=[
            store("1", "Fake Tel Aviv", city="Tel Aviv", address="Dizengoff 1"),
            store("90", "Fake Online"),
        ]
    )
    parsed = parsed_file("stores", data)
    f = _track(db, parsed)
    res = load(db, parsed, FakeAdapter())
    assert res.stores == 2
    rows = dict(
        db.execute("SELECT store_code, channel FROM stores WHERE chain_id = 'fake'").fetchall()
    )
    assert rows == {"1": "physical", "90": "online"}
    chain = db.execute("SELECT name, portal FROM chains WHERE id = 'fake'").fetchone()
    assert chain == ("Fake Chain", "other")
    assert tracking.get(db, f.id).status == "loaded"
    assert tracking.get(db, f.id).reason == "items=2"


def test_price_full_writes_items_events_and_marks_loaded(db) -> None:
    parsed = _price_full(
        [
            price("A", "1", "5.90", unit_price=D("0.59"), unit_of_measure='100 מ"ל'),
            price("B", "1", "12.00"),
        ],
        items=[item("A", "חלב 3%"), item("B", "עגבניות", is_weighed=True)],
    )
    f = _track(db, parsed)
    res = load(db, parsed, FakeAdapter())
    assert (res.items, res.prices_written, res.record_count) == (2, 2, 2)
    assert _events(db, "A") == [(D("5.90"), D("0.59"), "100ml", False, T0)]
    assert _events(db, "B") == [(D("12.00"), D("12.00"), "kg", True, T0)]
    file_ids = db.execute(
        "SELECT DISTINCT file_id FROM prices p JOIN items i ON i.id = p.item_id"
        " WHERE i.chain_id = 'fake'"
    ).fetchall()
    assert file_ids == [(f.id,)]
    # Store placeholder created for a store the Stores file has not delivered yet.
    assert db.execute("SELECT name FROM stores WHERE chain_id = 'fake'").fetchall() == [("1",)]
    loaded = tracking.get(db, f.id)
    assert loaded.status == "loaded" and loaded.schema_version == "v1"


def test_partition_is_created_for_a_month_without_one(db) -> None:
    far = datetime(2027, 9, 15, 12, tzinfo=ISRAEL)
    parsed = _price_full([price("A", "1", "4.00", at=far)], at=far)
    _track(db, parsed)
    load(db, parsed, FakeAdapter())
    assert db.execute("SELECT to_regclass('prices_2027_09') IS NOT NULL").fetchone()[0]
    assert _events(db, "A")[0][0] == D("4.00")


def test_only_changes_are_stored(db) -> None:
    t1, t2, t3 = T0, T0 + timedelta(hours=1), T0 + timedelta(hours=2)
    first = _price_full([price("A", "1", "5.00", at=t1), price("B", "1", "7.00", at=t1)], salt="1")
    _track(db, first)
    load(db, first, FakeAdapter())

    second = _price_full([price("A", "1", "5.00", at=t2), price("B", "1", "7.50", at=t2)], salt="2")
    _track(db, second)
    res = load(db, second, FakeAdapter())
    assert (res.prices_written, res.prices_unchanged) == (1, 1)

    # B returns to its earlier price: that is a change and gets an event.
    third = _price_full([price("A", "1", "5.00", at=t3), price("B", "1", "7.00", at=t3)], salt="3")
    _track(db, third)
    load(db, third, FakeAdapter())
    assert [e[0] for e in _events(db, "A")] == [D("5.00")]
    assert [e[0] for e in _events(db, "B")] == [D("7.00"), D("7.50"), D("7.00")]

    # An older observation than the latest event is not written.
    old = _price_full([price("B", "1", "1.00", at=t1 - timedelta(days=1))], salt="4")
    _track(db, old)
    res = load(db, old, FakeAdapter())
    assert (res.prices_written, res.prices_stale) == (0, 1)


def test_same_content_twice_gives_identical_row_counts(db) -> None:
    """A republished file with identical records but a different hash (the 08:30 pass, a
    re-zipped file) must not change the data tables."""
    rows = [price("A", "1", "5.00"), price("B", "1", "3.00")]
    promos = [promo("P1", "1", ["A", "B"], reward_type="price", reward_value=D("7"))]
    stores = [store("1", "Fake 1")]

    def files(salt: str) -> list[ParsedFile]:
        return [
            parsed_file("stores", encode(stores=stores, salt=salt), path=f"raw/s{salt}"),
            parsed_file(
                "price_full",
                encode(items=[item("A"), item("B")], prices=rows, salt=salt),
                path=f"raw/p{salt}",
            ),
            parsed_file("promo_full", encode(promos=promos, salt=salt), path=f"raw/r{salt}"),
        ]

    for parsed in files("first"):
        _track(db, parsed)
        load(db, parsed, FakeAdapter())
    after_first = counts(db)
    assert after_first == {
        "chains": 1, "stores": 1, "items": 2, "prices": 2, "promos": 1, "promo_items": 2,
    }  # fmt: skip
    for parsed in files("second"):
        _track(db, parsed)
        load(db, parsed, FakeAdapter())
    assert counts(db) == after_first


def test_loading_an_already_loaded_file_is_a_no_op(db) -> None:
    parsed = _price_full([price("A", "1", "5.00")])
    _track(db, parsed)
    load(db, parsed, FakeAdapter())
    before = counts(db)
    res = load(db, parsed, FakeAdapter())
    assert res.skipped and counts(db) == before


def test_promos_link_known_items_and_replace_the_item_list(db) -> None:
    pf = _price_full([price("A", "1", "5"), price("B", "1", "6")])
    _track(db, pf)
    load(db, pf, FakeAdapter())

    first = parsed_file(
        "promo_full",
        encode(
            promos=[
                promo("P1", "1", ["A", "B", "NOPE"], club_only=True, club_name="Club",
                      raw={"PromotionID": "P1", "when": NOW}),
            ]
        ),
        path="raw/promo1",
    )  # fmt: skip
    _track(db, first)
    res = load(db, first, FakeAdapter())
    assert (res.promos, res.promo_items, res.promo_items_unknown) == (1, 2, 1)
    row = db.execute(
        "SELECT club_only, club_name, raw->>'PromotionID' FROM promos WHERE chain_id = 'fake'"
    ).fetchone()
    assert row == (True, "Club", "P1")

    second = parsed_file("promo", encode(promos=[promo("P1", "1", ["B"])]), path="raw/promo2")
    _track(db, second)
    load(db, second, FakeAdapter())
    linked = db.execute(
        "SELECT i.item_code FROM promo_items pi JOIN items i ON i.id = pi.item_id"
    ).fetchall()
    assert linked == [("B",)]
    assert counts(db)["promos"] == 1


def test_crash_after_items_upsert_rolls_back_everything(db, monkeypatch) -> None:
    parsed = _price_full([price("A", "1", "5.00")], items=[item("A")])
    f = _track(db, parsed)

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(loader, "_insert_prices", boom)
    with pytest.raises(LoadError, match="disk full"):
        load(db, parsed, FakeAdapter())
    assert counts(db) == dict.fromkeys(counts(db), 0)
    after = tracking.get(db, f.id)
    assert after.status == "failed"
    assert after.reason == "load failed: RuntimeError: disk full"

    # The failure is recoverable: the next attempt loads the file.
    monkeypatch.undo()
    load(db, parsed, FakeAdapter())
    assert tracking.get(db, f.id).status == "loaded"
    assert counts(db)["prices"] == 1


def test_price_for_an_unknown_item_fails_the_file(db) -> None:
    parsed = _price_full([price("GHOST", "1", "5.00")], items=[])
    f = _track(db, parsed)
    with pytest.raises(LoadError, match="unknown items"):
        load(db, parsed, FakeAdapter())
    assert tracking.get(db, f.id).status == "failed"
    assert counts(db)["chains"] == 0


def test_quarantined_file_is_never_loaded(db) -> None:
    parsed = _price_full([price("A", "1", "5.00")])
    f = _track(db, parsed)
    tracking.mark_loading(db, f.id)
    tracking.record_quarantine(db, f.id, [("zero_price", "x")])
    with pytest.raises(LoadError, match="quarantined"):
        load(db, parsed, FakeAdapter())
    assert counts(db)["items"] == 0


def test_untracked_file_is_refused(db) -> None:
    with pytest.raises(LoadError, match="not in file_tracking"):
        load(db, _price_full([price("A", "1", "5")]), FakeAdapter())
