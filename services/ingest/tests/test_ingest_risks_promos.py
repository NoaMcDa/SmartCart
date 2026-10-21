"""Promotions that disappear (#60, risk 3 of "Design risks left open").

A PromoFull is the store's complete list of promotions in force that day. A promotion missing from
it was withdrawn, but its row kept its ``ends_at``, so the precompute went on applying it. The
loader now ends it, at the file's publication time, inside the load transaction.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from smartcart_ingest import loader, tracking
from tests.fakes import (
    NOW,
    FakeAdapter,
    encode,
    item,
    make_harness,
    parsed_file,
    price,
    promo,
    statuses,
)

pytestmark = pytest.mark.db

DAY = timedelta(days=1)
T1 = NOW - timedelta(hours=4)  # 06:00 on 2026-10-06


@pytest.fixture
def h(db, tmp_path):
    return make_harness(db, tmp_path)


def _price_full(h, store_code="1", at=T1, codes=("A", "B", "C")):
    return h.fetcher.add(
        "price_full",
        encode(
            items=[item(c) for c in codes],
            prices=[price(c, store_code, "10.00", at=at) for c in codes],
        ),
        store_code=store_code,
        at=at,
    )


def _promo_full(h, ids, store_code="1", at=T1, salt="", codes=("A",), **kw):
    promos = [promo(i, store_code, list(codes), **kw) for i in ids]
    return h.fetcher.add(
        "promo_full", encode(promos=promos, salt=salt), store_code=store_code, at=at
    )


def _ends(db, store_code="1") -> dict[str, datetime | None]:
    rows = db.execute(
        "SELECT p.promo_id, p.ends_at FROM promos p JOIN stores s ON s.id = p.store_id"
        " WHERE p.chain_id = 'fake' AND s.store_code = %s",
        (store_code,),
    ).fetchall()
    return dict(rows)


def _run(h, at=None):
    if at is not None:
        h.set_now(at)
    return h.scheduler().run_full(["fake"]).chains[0]


def _first_day(h, ids=("P1", "P2", "P3"), **kw):
    _price_full(h)
    _promo_full(h, ids, **kw)
    _run(h)


def _next_day(h, ids, **kw):
    h.fetcher.clear()
    at = NOW + DAY - timedelta(hours=4)
    _price_full(h, at=at)
    remote = _promo_full(h, ids, at=at, **kw)
    _run(h, NOW + DAY)
    return remote, at


def test_a_promotion_missing_from_the_days_promo_full_is_ended_at_its_publication_time(h) -> None:
    _first_day(h)
    assert set(_ends(h.conn).values()) == {None}
    remote, at = _next_day(h, ["P1", "P3"])
    ends = _ends(h.conn)
    assert ends["P2"] == at  # the withdrawn one, at the second file's publication time
    assert ends["P1"] is None and ends["P3"] is None  # still listed: untouched
    assert statuses(h.conn)[remote.name] == "loaded"


def test_the_loader_reports_how_many_it_ended(h, db) -> None:
    _first_day(h)
    parsed = parsed_file(
        "promo_full",
        encode(promos=[promo("P1", "1", ["A"])], salt="x"),
        "1",
        NOW + DAY,
        "raw/fake/pf2",
    )
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    res = loader.load(db, parsed, FakeAdapter())
    assert res.promos_ended == 2


def test_a_withdrawn_promotion_is_not_applied_by_the_precompute_query(h, db) -> None:
    """The precompute reads promotions in force at ``as_of``; the ended one drops out, and as of a
    time before the withdrawal it still applies (the history is kept)."""
    from smartcart_api.precompute import _PROMOS_SQL

    _first_day(h, ids=("P1", "P2"), codes=("A",))
    _, at = _next_day(h, ["P1"], codes=("A",))
    item_id = db.execute("SELECT id FROM items WHERE item_code = 'A'").fetchone()[0]
    store_id = db.execute("SELECT id FROM stores WHERE store_code = '1'").fetchone()[0]

    def applied(as_of):
        rows = db.execute(
            _PROMOS_SQL,
            {"chain": "fake", "items": [item_id], "stores": [store_id], "as_of": as_of},
        ).fetchall()
        return {r[2] for r in rows}  # the descriptions

    assert applied(at + timedelta(hours=1)) == {"Promo P1"}
    assert applied(at - timedelta(hours=1)) == {"Promo P1", "Promo P2"}


def test_a_failed_load_ends_nothing(h, db, monkeypatch) -> None:
    _first_day(h)
    h.fetcher.clear()
    at = NOW + DAY - timedelta(hours=4)
    _price_full(h, at=at)
    remote = _promo_full(h, ["P1", "P2"], at=at)

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(tracking, "mark_loaded", boom)  # after the promos were written
    rep = _run(h, NOW + DAY)
    monkeypatch.undo()
    assert rep.failed >= 1 and statuses(h.conn)[remote.name] == "failed"
    assert set(_ends(h.conn).values()) == {None}  # P2 and P3 are still open, nothing half-done


def test_a_quarantined_promo_full_ends_nothing(h) -> None:
    """A file that fails a gate (here: far fewer promotions than yesterday's) never reaches the
    loader, so it cannot end the promotions it does not list."""
    _first_day(h, ids=tuple(f"P{i}" for i in range(10)))
    remote, _ = _next_day(h, ["P0"])  # 1 of 10: below the item-count ratio
    assert statuses(h.conn)[remote.name] == "quarantined"
    assert set(_ends(h.conn).values()) == {None}


def test_a_promo_delta_never_ends_anything(h) -> None:
    _first_day(h)
    h.fetcher.add("promo", encode(promos=[promo("P9", "1", ["A"])]), at=NOW - timedelta(hours=1))
    h.scheduler().run_delta(["fake"])
    assert set(_ends(h.conn)) == {"P1", "P2", "P3", "P9"}
    assert set(_ends(h.conn).values()) == {None}


def test_a_promotion_from_a_delta_is_ended_by_the_next_full_that_lacks_it(h) -> None:
    _first_day(h, ids=("P1", "P2"))
    h.fetcher.add("promo", encode(promos=[promo("P9", "1", ["A"])]), at=NOW - timedelta(hours=1))
    h.scheduler().run_delta(["fake"])
    # The next day's PromoFull has the same bytes as the first: skipped by hash, never loaded, but it
    # is still that day's list, so the delta's promotion goes.
    _, at = _next_day(h, ["P1", "P2"])
    assert _ends(h.conn)["P9"] == at


def test_another_stores_promotions_are_not_touched(h) -> None:
    _price_full(h, "1")
    _price_full(h, "2")
    _promo_full(h, ["P1", "P2"], "1")
    _promo_full(h, ["Q1", "Q2"], "2")
    _run(h)
    h.fetcher.clear()
    at = NOW + DAY - timedelta(hours=4)
    _price_full(h, "1", at=at)
    _promo_full(h, ["P1"], "1", at=at)  # store 2 publishes nothing today
    _run(h, NOW + DAY)
    assert _ends(h.conn, "1")["P2"] == at
    assert set(_ends(h.conn, "2").values()) == {None}


def test_chain_wide_promotions_are_not_touched(h, db) -> None:
    """``store_id IS NULL`` is the chain-wide key; a store's file is not its authority."""
    _first_day(h, ids=("P1",))
    db.execute(
        "INSERT INTO promos (chain_id, store_id, promo_id, description, reward_type)"
        " VALUES ('fake', NULL, 'CW', 'chain wide', 'other')"
    )
    _next_day(h, ["P1"], salt="two")
    assert db.execute("SELECT ends_at FROM promos WHERE promo_id = 'CW'").fetchone()[0] is None


def test_a_promotion_already_over_keeps_its_own_end(h, db) -> None:
    ended = NOW - 3 * DAY
    _price_full(h)
    _promo_full(h, ["P1"], ends_at=ended)
    _run(h)
    _next_day(h, ["P2"])
    assert _ends(h.conn)["P1"] == ended


def test_an_older_full_loaded_late_does_not_end_a_newer_files_promotions(h, db) -> None:
    """Loading is not publishing order: a full published at 06:00 and loaded after a 10:00 file
    must not end what the 10:00 file introduced."""
    newer = parsed_file(
        "promo_full",
        encode(promos=[promo("N1", "1", ["A"])]),
        "1",
        T1 + timedelta(hours=4),
        "raw/fake/newer",
    )
    older = parsed_file(
        "promo_full",
        encode(promos=[promo("O1", "1", ["A"])]),
        "1",
        T1,
        "raw/fake/older",
    )
    for parsed in (
        parsed_file("price_full", encode(items=[item("A")], prices=[price("A", "1", "5")])),
    ):
        row, _ = tracking.register(db, parsed.raw)
        tracking.mark_downloaded(db, row.id, parsed.raw.path)
        loader.load(db, parsed, FakeAdapter())
    for parsed in (newer, older):
        row, _ = tracking.register(db, parsed.raw)
        tracking.mark_downloaded(db, row.id, parsed.raw.path)
        loader.load(db, parsed, FakeAdapter())
    ends = _ends(db)
    assert ends["N1"] is None  # not ended by the older file


def test_a_file_whose_records_name_another_store_ends_nothing(h, db) -> None:
    """Header store and record store disagree (a file for store 1 whose records say store 9): the
    scope of the file is unknown, so no promotion is ended."""
    _first_day(h, ids=("P1", "P2"))
    parsed = parsed_file(
        "promo_full",
        encode(promos=[promo("Z", "9", ["A"])]),
        "1",
        NOW + DAY,
        "raw/fake/odd",
    )
    row, _ = tracking.register(db, parsed.raw)
    tracking.mark_downloaded(db, row.id, parsed.raw.path)
    res = loader.load(db, parsed, FakeAdapter())
    assert res.promos_ended == 0
    assert set(_ends(db).values()) == {None}


def test_a_promotion_listed_again_is_open_again(h) -> None:
    _first_day(h, ids=("P1", "P2"))
    _next_day(h, ["P1"])
    assert _ends(h.conn)["P2"] is not None
    h.fetcher.clear()
    at = NOW + 2 * DAY - timedelta(hours=4)
    _price_full(h, at=at)
    _promo_full(h, ["P1", "P2"], at=at, salt="back")
    _run(h, NOW + 2 * DAY)
    assert _ends(h.conn)["P2"] is None


def test_the_same_file_twice_ends_nothing_new(h) -> None:
    _first_day(h)
    _next_day(h, ["P1"])
    before = _ends(h.conn)
    _run(h)  # listed again: skipped by hash
    assert _ends(h.conn) == before


def test_a_withdrawn_promotion_is_ended_by_a_full_with_different_bytes_too(h) -> None:
    """The same outcome through the loader (the republished-bytes case above goes through the
    hash skip in ``download``)."""
    _first_day(h, ids=("P1", "P2"))
    h.fetcher.add("promo", encode(promos=[promo("P9", "1", ["A"])]), at=NOW - timedelta(hours=1))
    h.scheduler().run_delta(["fake"])
    _, at = _next_day(h, ["P1", "P2"], salt="changed bytes", description="Promo again")
    assert _ends(h.conn)["P9"] == at
