"""Gate changes before the fourteen real nights (#60): a stale limit per file kind (risk 1 of the
"Design risks left open" list, quarantined Stores files) and a symmetric price-drop gate (risk 4).

The invariants are listed in ``docs/ingestion.md`` ("Invariants covered by tests").
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from smartcart_ingest import quality
from smartcart_ingest.settings import Settings, Thresholds
from tests.fakes import (
    NOW,
    counts,
    encode,
    item,
    make_harness,
    parsed_file,
    price,
    statuses,
    store,
)

DAY = timedelta(days=1)

# --- stale limit per file kind: no database ------------------------------------------------------


def test_a_stores_file_has_its_own_longer_stale_limit() -> None:
    """The newest Stores file of Rami Levy, Tiv Taam, Osher Ad and Yohananof was 60 to 68 hours old
    on 2026-10-21: quarantined by the 36-hour limit of the price files."""
    stores = parsed_file("stores", encode(stores=[store("1")]), at=NOW - timedelta(hours=68))
    prices = parsed_file("price_full", encode(), at=NOW - timedelta(hours=68))
    assert quality.gate_stale_date(stores, 36, NOW) is not None  # the old behaviour
    assert quality.gate_stale_date(stores, 36, NOW, stores_max_age_hours=240) is None
    # The price files keep the tight limit whatever the Stores limit is.
    assert quality.gate_stale_date(prices, 36, NOW, stores_max_age_hours=240).gate == "stale_date"


def test_a_stores_file_is_still_stale_after_its_own_limit() -> None:
    old = parsed_file("stores", encode(stores=[store("1")]), at=NOW - timedelta(days=11))
    failure = quality.gate_stale_date(old, 36, NOW, stores_max_age_hours=240)
    assert failure is not None and "limit 240" in failure.detail


def test_stale_limits_are_settings_with_per_chain_overrides(monkeypatch) -> None:
    s = Settings(quality_overrides={"7290058140886": {"stale_stores_max_age_hours": 400}})
    default = s.thresholds_for("other")
    assert (default.stale_file_max_age_hours, default.stale_stores_max_age_hours) == (36, 240)
    assert s.thresholds_for("7290058140886").stale_stores_max_age_hours == 400
    assert s.thresholds_for("7290058140886").stale_file_max_age_hours == 36
    monkeypatch.setenv("STALE_STORES_MAX_AGE_HOURS", "96")
    assert Settings().thresholds_for("x").stale_stores_max_age_hours == 96
    with pytest.raises(ValueError):
        Settings(stale_stores_max_age_hours=0)


def test_the_price_and_promo_thresholds_were_not_loosened() -> None:
    """The issue asks to leave PriceFull, Promo and the deltas at the default limit."""
    t = Settings().thresholds_for("any")
    assert t.stale_file_max_age_hours == 36
    for kind in ("price_full", "promo_full", "price", "promo"):
        parsed = parsed_file(kind, encode(), at=NOW - timedelta(hours=68))  # type: ignore[arg-type]
        failure = quality.gate_stale_date(
            parsed, t.stale_file_max_age_hours, NOW, t.stale_stores_max_age_hours
        )
        assert failure is not None, kind


# --- price-drop gate: settings -------------------------------------------------------------------


def test_drop_gate_settings_and_overrides(monkeypatch) -> None:
    assert Settings().thresholds_for("x") == Thresholds(
        36,
        3,
        0.5,
        3,
        stale_stores_max_age_hours=240,
        price_drop_factor=8,
        price_drop_min_previous=1,
    )
    s = Settings(quality_overrides={"c": {"price_drop_factor": 20, "price_drop_min_previous": 5}})
    assert (
        s.thresholds_for("c").price_drop_factor,
        s.thresholds_for("c").price_drop_min_previous,
    ) == (
        20,
        5,
    )
    monkeypatch.setenv("PRICE_DROP_FACTOR", "0")  # off
    assert Settings().thresholds_for("x").price_drop_factor == 0


# --- through the pipeline ------------------------------------------------------------------------

db_only = pytest.mark.db


@pytest.fixture
def h(db, tmp_path):
    return make_harness(db, tmp_path)


def _full(h, prices_, at=None, salt=""):
    at = at or h.clock[0] - timedelta(hours=1)
    items_ = [item(p.item_code) for p in {p.item_code: p for p in prices_}.values()]
    return h.fetcher.add("price_full", encode(items=items_, prices=prices_, salt=salt), at=at)


def _day_two(h, prices_):
    """Load a first day with ``prices_``, then return the harness on the next day."""
    _full(h, prices_)
    h.scheduler().run_full(["fake"])
    h.set_now(NOW + DAY)
    h.fetcher.clear()


def _gates(db, remote) -> list[str]:
    fid = db.execute(
        "SELECT id FROM file_tracking WHERE path LIKE %s", (f"%/{remote.name}",)
    ).fetchone()[0]
    return [
        r[0] for r in db.execute("SELECT gate FROM quarantine_events WHERE file_id = %s", (fid,))
    ]


def _current(db, code="A"):
    return db.execute(
        "SELECT price FROM latest_prices lp JOIN items i ON i.id = lp.item_id"
        " WHERE i.item_code = %s",
        (code,),
    ).fetchone()[0]


@db_only
def test_a_price_falling_to_a_tenth_quarantines_the_file(h) -> None:
    """12.90 read as 1.29: shekels as agorot with a lost decimal point. It used to load."""
    _day_two(h, [price("A", "1", "12.90", at=NOW - timedelta(hours=2))])
    remote = _full(h, [price("A", "1", "1.29", at=NOW + DAY - timedelta(hours=2))])
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert (rep.quarantined, rep.loaded) == (1, 0)
    assert _gates(h.conn, remote) == ["price_drop"]
    assert _current(h.conn) == Decimal("12.90")  # the old price still stands
    assert "quarantine" in h.kinds_of_alerts()
    assert statuses(h.conn)[remote.name] == "quarantined"


@db_only
def test_a_quarantined_drop_file_writes_no_rows_and_is_never_loaded_later(h) -> None:
    _day_two(h, [price("A", "1", "12.90", at=NOW - timedelta(hours=2))])
    before = counts(h.conn)
    remote = _full(h, [price("A", "1", "0.129", at=NOW + DAY - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])
    assert counts(h.conn) == before
    h.set_now(NOW + DAY + timedelta(hours=1))
    h.scheduler().run_full(["fake"])  # listed again: terminal, skipped by hash
    assert counts(h.conn) == before and statuses(h.conn)[remote.name] == "quarantined"


@db_only
def test_real_promotions_and_clearance_do_not_trip_the_gate(h) -> None:
    """Measured on the seven real PromoFull files: of 1460 priced promotion items, 8.6 % are 50 %
    or more off the shelf price, 0.6 % are 80 % or more (a divisor of 5), one is 91 % (11x). A
    clearance at 75 % off is a divisor of 4, and a price at half is a divisor of 2."""
    _day_two(
        h,
        [
            price("A", "1", "20.00", at=NOW - timedelta(hours=2)),
            price("B", "1", "20.00", at=NOW - timedelta(hours=2)),
            price("C", "1", "20.00", at=NOW - timedelta(hours=2)),
        ],
    )
    _full(
        h,
        [
            price("A", "1", "10.00", at=NOW + DAY - timedelta(hours=2)),  # half
            price("B", "1", "5.00", at=NOW + DAY - timedelta(hours=2)),  # 75 % off
            price("C", "1", "3.00", at=NOW + DAY - timedelta(hours=2)),  # 85 % off, 6.7x
        ],
    )
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert (rep.loaded, rep.quarantined) == (1, 0)
    assert _current(h.conn, "C") == 3


@db_only
def test_the_boundary_is_the_factor_itself(h) -> None:
    _day_two(h, [price("A", "1", "16.00", at=NOW - timedelta(hours=2))])
    just_inside = _full(h, [price("A", "1", "2.01", at=NOW + DAY - timedelta(hours=2))])
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 1 and not _gates(h.conn, just_inside)
    h.set_now(NOW + 2 * DAY)
    h.fetcher.clear()
    past = _full(h, [price("A", "1", "0.25", at=NOW + 2 * DAY - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])  # 2.01 -> 0.25 is 8.04x
    assert _gates(h.conn, past) == ["price_drop"]


@db_only
def test_penny_items_are_not_compared(h) -> None:
    """Bags and deposits (real files hold prices of 0.01 and 0.10) swing by large factors."""
    _day_two(h, [price("A", "1", "0.90", at=NOW - timedelta(hours=2))])
    _full(h, [price("A", "1", "0.05", at=NOW + DAY - timedelta(hours=2))])
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert (rep.loaded, rep.quarantined) == (1, 0)


@db_only
def test_a_zero_price_is_the_zero_price_gates_not_the_drop_gates(h) -> None:
    _day_two(h, [price("A", "1", "12.90", at=NOW - timedelta(hours=2))])
    remote = _full(h, [price("A", "1", "0", at=NOW + DAY - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])
    assert _gates(h.conn, remote) == ["zero_price"]


@db_only
def test_a_new_item_or_store_has_nothing_to_drop_from(h) -> None:
    _day_two(h, [price("A", "1", "12.90", at=NOW - timedelta(hours=2))])
    _full(
        h,
        [
            price("B", "1", "0.50", at=NOW + DAY - timedelta(hours=2)),  # new item
            price("A", "2", "1.00", at=NOW + DAY - timedelta(hours=2)),  # new store, no base
        ],
    )
    # price_full of store 1 and 2 in one file: the fake adapter takes the file's records as they
    # are, and the store record is created by the loader.
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert (rep.loaded, rep.quarantined) == (1, 0)


@db_only
def test_the_gate_applies_to_deltas_too(h) -> None:
    _day_two(h, [price("A", "1", "12.90", at=NOW - timedelta(hours=2))])
    h.fetcher.add(
        "price_full",
        encode(
            items=[item("A")], prices=[price("A", "1", "12.90", at=NOW + DAY - timedelta(hours=3))]
        ),
        at=NOW + DAY - timedelta(hours=3),
    )
    h.scheduler().run_full(["fake"])
    delta = h.fetcher.add(
        "price",
        encode(
            items=[item("A")], prices=[price("A", "1", "1.29", at=NOW + DAY - timedelta(hours=1))]
        ),
        at=NOW + DAY - timedelta(hours=1),
    )
    h.scheduler().run_delta(["fake"])
    assert _gates(h.conn, delta) == ["price_drop"]
    assert _current(h.conn) == Decimal("12.90")


@db_only
@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"fake": {"price_drop_factor": 20}}, "loaded"),  # a tenth is allowed for this chain
        ({"fake": {"price_drop_factor": 0}}, "loaded"),  # gate off for this chain
        ({"fake": {"price_drop_factor": 5}}, "quarantined"),
        ({"other": {"price_drop_factor": 20}}, "quarantined"),  # another chain's override
        ({}, "quarantined"),
    ],
)
def test_the_factor_is_configurable_per_chain_and_can_be_switched_off(
    db, tmp_path, overrides, expected
) -> None:
    h = make_harness(db, tmp_path, quality_overrides=overrides)
    _day_two(h, [price("A", "1", "12.90", at=NOW - timedelta(hours=2))])
    remote = _full(h, [price("A", "1", "1.29", at=NOW + DAY - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])
    assert statuses(h.conn)[remote.name] == expected


@db_only
def test_a_stores_file_70_hours_old_loads_and_a_price_file_that_old_does_not(h) -> None:
    """The 2026-10-21 run: Stores files 60 to 68 hours old, PriceFull files fresh."""
    old = NOW - timedelta(hours=68)
    h.fetcher.add("stores", encode(stores=[store("1")]), at=old)
    old_prices = h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=old)]),
        at=old,
    )
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 1 and rep.quarantined == 1
    st = statuses(h.conn)
    assert st[next(n for n in st if n.startswith("Stores"))] == "loaded"
    assert st[old_prices.name] == "quarantined"
