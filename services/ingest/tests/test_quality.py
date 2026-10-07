"""Quality gates and quarantine (issue #42), exercised through the FakeAdapter pipeline."""

from __future__ import annotations

from datetime import timedelta

import pytest

from smartcart_ingest import quality, tracking
from smartcart_ingest.settings import Settings, Thresholds
from tests.fakes import NOW, counts, encode, item, make_harness, parsed_file, price, statuses

DAY = timedelta(days=1)

# --- no database -------------------------------------------------------------------------------


def test_default_thresholds_and_per_chain_overrides() -> None:
    s = Settings(quality_overrides={"7290027600007": {"price_jump_factor": 4}})
    assert s.thresholds_for("other") == Thresholds(36, 3, 0.5)
    assert s.thresholds_for("7290027600007") == Thresholds(36, 4, 0.5)
    with pytest.raises(ValueError, match="unknown threshold"):
        Settings(quality_overrides={"x": {"price_jumps": 4}})


def test_thresholds_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("STALE_FILE_MAX_AGE_HOURS", "12")
    monkeypatch.setenv("PRICE_JUMP_FACTOR", "2.5")
    monkeypatch.setenv("ITEM_COUNT_DROP_RATIO", "0.7")
    monkeypatch.setenv("QUALITY_OVERRIDES", '{"fake": {"item_count_drop_ratio": 0.9}}')
    s = Settings()
    assert s.thresholds_for("x") == Thresholds(12, 2.5, 0.7)
    assert s.thresholds_for("fake").item_count_drop_ratio == 0.9


def test_zero_price_gate_needs_no_database() -> None:
    parsed = parsed_file(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "0"), price("A", "2", "-1")]),
    )
    failure = quality.gate_zero_price(parsed)
    assert failure is not None and failure.gate == "zero_price" and "2 prices" in failure.detail


def test_stale_gate_needs_no_database() -> None:
    fresh = parsed_file("price_full", encode(), at=NOW - timedelta(hours=35))
    stale = parsed_file("price_full", encode(), at=NOW - timedelta(hours=37))
    assert quality.gate_stale_date(fresh, 36, NOW) is None
    assert quality.gate_stale_date(stale, 36, NOW).gate == "stale_date"


# --- through the pipeline ----------------------------------------------------------------------

pytestmark = pytest.mark.db


@pytest.fixture
def h(db, tmp_path):
    return make_harness(db, tmp_path)


def _full(h, prices_, items_=None, at=None, salt=""):
    at = at or h.clock[0] - timedelta(hours=1)
    items_ = items_ if items_ is not None else [item(p.item_code) for p in prices_]
    return h.fetcher.add("price_full", encode(items=items_, prices=prices_, salt=salt), at=at)


def _events(db, file_id):
    return db.execute(
        "SELECT gate, detail FROM quarantine_events WHERE file_id = %s ORDER BY gate", (file_id,)
    ).fetchall()


def _file_id(db, remote):
    return db.execute(
        "SELECT id FROM file_tracking WHERE path LIKE %s", (f"%/{remote.name}",)
    ).fetchone()[0]


def _assert_quarantined(h, remote, gate):
    fid = _file_id(h.conn, remote)
    f = tracking.get(h.conn, fid)
    assert f.status == "quarantined"
    assert gate in f.reason
    assert gate in [g for g, _ in _events(h.conn, fid)]
    assert (
        h.conn.execute("SELECT count(*) FROM prices WHERE file_id = %s", (fid,)).fetchone()[0] == 0
    )
    alert = [a for a in h.sink.alerts if a.kind == "quarantine" and a.details["file_id"] == fid]
    assert len(alert) == 1
    assert alert[0].chain_id == "fake" and gate in alert[0].message
    assert remote.name in alert[0].message and "store 1" in alert[0].message
    return fid


def test_zero_price_file_is_quarantined_and_no_row_reaches_the_database(h) -> None:
    remote = _full(h, [price("A", "1", "5.00"), price("B", "1", "0")])
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.quarantined == 1 and rep.loaded == 0
    _assert_quarantined(h, remote, "zero_price")
    assert counts(h.conn) == dict.fromkeys(counts(h.conn), 0)


def test_price_more_than_three_times_the_previous_is_quarantined(h) -> None:
    _full(h, [price("A", "1", "10.00", at=NOW - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])
    h.set_now(NOW + DAY)
    h.fetcher.clear()
    remote = _full(h, [price("A", "1", "30.01", at=NOW + DAY - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])
    _assert_quarantined(h, remote, "price_jump")
    # The current price is still the old one.
    assert (
        h.conn.execute(
            "SELECT price FROM latest_prices lp JOIN items i ON i.id = lp.item_id"
            " WHERE i.item_code = 'A'"
        ).fetchone()[0]
        == 10
    )


def test_price_at_three_times_the_previous_passes(h) -> None:
    _full(h, [price("A", "1", "10.00", at=NOW - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])
    h.set_now(NOW + DAY)
    h.fetcher.clear()
    _full(h, [price("A", "1", "30.00", at=NOW + DAY - timedelta(hours=2))])
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 1 and rep.quarantined == 0


def test_price_jump_threshold_is_configurable_per_chain(db, tmp_path) -> None:
    h = make_harness(db, tmp_path, quality_overrides={"fake": {"price_jump_factor": 5}})
    _full(h, [price("A", "1", "10.00", at=NOW - timedelta(hours=2))])
    h.scheduler().run_full(["fake"])
    h.set_now(NOW + DAY)
    h.fetcher.clear()
    _full(h, [price("A", "1", "40.00", at=NOW + DAY - timedelta(hours=2))])
    assert h.scheduler().run_full(["fake"]).chains[0].loaded == 1


def _n_items(n, amount="5.00"):
    return [price(f"I{i}", "1", amount) for i in range(n)]


def test_sharp_item_count_drop_is_quarantined(h) -> None:
    _full(h, _n_items(10))
    h.scheduler().run_full(["fake"])
    h.set_now(NOW + DAY)
    h.fetcher.clear()
    remote = _full(
        h, [price(f"I{i}", "1", "5.00", at=NOW + DAY - timedelta(hours=2)) for i in range(4)]
    )
    h.scheduler().run_full(["fake"])
    fid = _assert_quarantined(h, remote, "item_count_drop")
    assert "4 records versus 10" in _events(h.conn, fid)[0][1]


def test_item_count_at_the_ratio_passes(h) -> None:
    _full(h, _n_items(10))
    h.scheduler().run_full(["fake"])
    h.set_now(NOW + DAY)
    h.fetcher.clear()
    _full(h, [price(f"I{i}", "1", "5.00", at=NOW + DAY - timedelta(hours=2)) for i in range(5)])
    assert h.scheduler().run_full(["fake"]).chains[0].loaded == 1


def test_item_count_compares_the_same_store_only(h) -> None:
    _full(h, _n_items(10))
    h.scheduler().run_full(["fake"])
    h.fetcher.clear()
    other = h.fetcher.add(
        "price_full", encode(items=[item("X")], prices=[price("X", "2", "1")]), store_code="2",
        at=NOW - timedelta(minutes=30),
    )  # fmt: skip
    h.scheduler().run_full(["fake"])
    assert tracking.get(h.conn, _file_id(h.conn, other)).status == "loaded"


def test_stale_file_is_quarantined(h) -> None:
    old = NOW - timedelta(hours=40)
    remote = _full(h, [price("A", "1", "5.00", at=old)], at=old)
    h.scheduler().run_full(["fake"])
    _assert_quarantined(h, remote, "stale_date")


def test_every_failing_gate_is_recorded(h) -> None:
    old = NOW - timedelta(hours=40)
    remote = _full(h, [price("A", "1", "0", at=old)], at=old)
    h.scheduler().run_full(["fake"])
    fid = _file_id(h.conn, remote)
    assert [g for g, _ in _events(h.conn, fid)] == ["stale_date", "zero_price"]


def test_delta_files_pass_through_the_gates(h) -> None:
    _full(h, [price("A", "1", "5.00", at=NOW - timedelta(hours=3))])
    h.scheduler().run_full(["fake"])
    delta = h.fetcher.add(
        "price", encode(items=[item("A")], prices=[price("A", "1", "0", at=NOW - timedelta(minutes=10))]),
        at=NOW - timedelta(minutes=10),
    )  # fmt: skip
    rep = h.scheduler().run_delta(["fake"]).chains[0]
    assert rep.quarantined == 1
    _assert_quarantined(h, delta, "zero_price")
    assert statuses(h.conn)[delta.name] == "quarantined"


def test_quarantine_counts_per_chain(h) -> None:
    _full(h, [price("A", "1", "0")], salt="1")
    h.fetcher.add("promo_full", encode(), at=NOW - timedelta(hours=50))  # stale: quarantined too
    h.scheduler().run_full(["fake"])
    rows = {c: (n, recent) for c, n, recent in tracking.quarantine_counts(h.conn)}
    assert rows["fake"] == (2, 2)
