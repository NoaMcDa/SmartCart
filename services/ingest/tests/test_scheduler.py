"""Full and delta jobs: ordering, holding, idempotency, backoff (issues #37 and #49)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from smartcart_ingest import loader, tracking
from smartcart_ingest.download import PortalError
from smartcart_ingest.scheduler import (
    D13_CHAINS,
    MAIN_CHAIN_IDS,
    Backoff,
    ChainSchedule,
    PortalUnavailable,
    chain_schedules,
    is_delta_due,
    spread_order,
)
from smartcart_ingest.settings import Settings
from tests.fakes import ISRAEL, NOW, counts, encode, item, make_harness, price, promo, statuses

# --- schedule (no database) --------------------------------------------------------------------


def test_main_chains_are_d13_chains_one_to_six() -> None:
    assert MAIN_CHAIN_IDS == (
        "7290027600007",  # Shufersal
        "7290058140886",  # Rami Levy
        "7290696200003",  # Victory
        "7290055700007",  # Yeinot Bitan and Carrefour
        "7290700100008",  # Hazi Hinam
        "7290873255550",  # Tiv Taam
    )
    assert len(D13_CHAINS) == 10
    hourly = {c.chain_id: c.delta_interval_minutes for c in D13_CHAINS}
    assert all(hourly[c] == 60 for c in MAIN_CHAIN_IDS)
    assert sum(v is None for v in hourly.values()) == 4


def test_delta_intervals_are_configurable_per_chain() -> None:
    s = Settings(
        delta_interval_minutes={"7290058140886": 120, "7290027600007": 0, "7290103152017": 60}
    )
    sched = chain_schedules(s)
    assert sched["7290058140886"].delta_interval_minutes == 120
    assert not sched["7290027600007"].has_deltas  # 0 turns deltas off
    assert sched["7290103152017"].has_deltas  # Osher Ad promoted to hourly


def test_is_delta_due() -> None:
    hourly = ChainSchedule("a", "A", "web", 60)
    two_hourly = ChainSchedule("b", "B", "web", 120)
    full_only = ChainSchedule("c", "C", "web", None)
    even = datetime(2026, 10, 6, 10, 20, tzinfo=ISRAEL)  # 07:20 UTC: hour count is odd or even
    odd = even + timedelta(hours=1)
    assert is_delta_due(hourly, even) and is_delta_due(hourly, odd)
    assert is_delta_due(two_hourly, even) != is_delta_due(two_hourly, odd)
    assert not is_delta_due(full_only, even)


def test_spread_order_separates_chains_on_the_same_portal() -> None:
    main = [c for c in D13_CHAINS if c.has_deltas]
    ordered = spread_order(main)
    assert {c.chain_id for c in ordered} == set(MAIN_CHAIN_IDS)
    portals = [c.portal for c in ordered]
    assert all(a != b or a != "cerberus" for a, b in zip(portals, portals[1:], strict=False))


# --- backoff (no database) ---------------------------------------------------------------------


def test_backoff_is_exponential_with_a_cap_and_gives_up() -> None:
    sleeps: list[float] = []
    calls = []

    def always_fails():
        calls.append(1)
        raise PortalError("c", "503")

    b = Backoff(max_attempts=6, base=2, cap=10, sleep=sleeps.append, rng=lambda: 1.0)
    with pytest.raises(PortalUnavailable) as exc:
        b.call("c", always_fails)
    assert len(calls) == 6 and exc.value.attempts == 6
    assert sleeps == [2, 4, 8, 10, 10]


def test_backoff_uses_full_jitter_and_returns_on_success() -> None:
    sleeps: list[float] = []
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise PortalError("c", "reset")
        return "ok"

    b = Backoff(max_attempts=5, base=2, cap=60, sleep=sleeps.append, rng=lambda: 0.25)
    assert b.call("c", flaky) == "ok"
    assert sleeps == [0.5, 1.0]


def test_backoff_does_not_retry_other_errors() -> None:
    b = Backoff(sleep=lambda s: None)
    with pytest.raises(ValueError):
        b.call("c", lambda: (_ for _ in ()).throw(ValueError("bug")))


# --- jobs (database) ---------------------------------------------------------------------------

pytestmark = pytest.mark.db


@pytest.fixture
def h(db, tmp_path):
    return make_harness(db, tmp_path)


def _current(db, code="A", store_code="1"):
    return db.execute(
        "SELECT cp.price FROM items i JOIN stores s ON s.chain_id = i.chain_id"
        " CROSS JOIN LATERAL current_price(i.id, s.id) cp"
        " WHERE i.chain_id = 'fake' AND i.item_code = %s AND s.store_code = %s",
        (code, store_code),
    ).fetchone()[0]


def _full_and_delta(h):
    full = h.fetcher.add(
        "price_full",
        encode(items=[item("A"), item("B")], prices=[price("A", "1", "5.00", at=NOW - timedelta(hours=4)),
                                                     price("B", "1", "8.00", at=NOW - timedelta(hours=4))]),
        at=NOW - timedelta(hours=4),
    )  # fmt: skip
    delta = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.50", at=NOW - timedelta(hours=1))]),
        at=NOW - timedelta(hours=1),
    )
    return full, delta


def test_delta_listed_before_its_full_is_applied_after_it(h, monkeypatch) -> None:
    # The portal lists the delta first; the full sync still loads the full file first.
    delta = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.50", at=NOW - timedelta(hours=1))]),
        at=NOW - timedelta(hours=1),
    )
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=NOW - timedelta(hours=4))]),
        at=NOW - timedelta(hours=4),
    )
    rep = h.scheduler().run_delta(["fake"]).chains[0]
    # A delta run lists only deltas: the delta waits.
    assert rep.held == 1 and statuses(h.conn)[delta.name] == "held"
    assert counts(h.conn)["prices"] == 0

    loaded_kinds = []
    real_load = loader.load

    def spy(conn, parsed, adapter):
        # Record the order and that the full is loaded whenever a delta is loaded.
        if parsed.raw.kind == "price":
            assert tracking.is_full_loaded(conn, "fake", "1", NOW.date(), "price_full")
        loaded_kinds.append(parsed.raw.kind)
        return real_load(conn, parsed, adapter)

    monkeypatch.setattr(loader, "load", spy)
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 2 and rep.held == 0
    assert loaded_kinds == ["price_full", "price"]
    assert statuses(h.conn)[delta.name] == "loaded"
    assert _current(h.conn) == 4.50


def test_full_and_delta_in_one_listing_load_full_first(h) -> None:
    h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.50", at=NOW - timedelta(hours=1))]),
        at=NOW - timedelta(hours=1),
    )
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=NOW - timedelta(hours=4))]),
        at=NOW - timedelta(hours=4),
    )
    sched = h.scheduler()
    # A combined listing (both kinds), as a portal returning everything would give.
    rep = sched._run_chain("fake", ("price_full", "price"))
    assert rep.loaded == 2 and rep.held == 0
    assert _current(h.conn) == 4.50


def test_delta_waits_while_the_full_file_of_the_day_is_missing(h) -> None:
    # Yesterday's full is loaded; today's is not out yet.
    h.set_now(NOW - timedelta(days=1))
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=NOW - timedelta(days=1, hours=2))]),
        at=NOW - timedelta(days=1, hours=2),
    )  # fmt: skip
    h.scheduler().run_full(["fake"])
    h.set_now(NOW)
    h.fetcher.clear()
    delta = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.00", at=NOW - timedelta(hours=1))]),
        at=NOW - timedelta(hours=1),
    )
    h.scheduler().run_delta(["fake"])
    f = h.conn.execute(
        "SELECT status, reason FROM file_tracking WHERE path LIKE %s", (f"%{delta.name}",)
    ).fetchone()
    assert f[0] == "held" and "price_full" in f[1] and "2026-10-06" in f[1]
    assert _current(h.conn) == 5.00
    # Held across further ticks, never dropped.
    h.scheduler().run_delta(["fake"])
    assert statuses(h.conn)[delta.name] == "held"


def test_promo_delta_waits_for_promo_full_not_price_full(h) -> None:
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00")]),
        at=NOW - timedelta(hours=4),
    )
    h.scheduler().run_full(["fake"])
    pdelta = h.fetcher.add(
        "promo", encode(promos=[promo("P", "1", ["A"])]), at=NOW - timedelta(hours=1)
    )
    h.scheduler().run_delta(["fake"])
    assert statuses(h.conn)[pdelta.name] == "held"
    h.fetcher.add(
        "promo_full", encode(promos=[promo("P0", "1", ["A"])]), at=NOW - timedelta(hours=3)
    )
    h.scheduler().run_full(["fake"])
    assert statuses(h.conn)[pdelta.name] == "loaded"


def test_delta_of_a_store_whose_full_was_quarantined_stays_held(h) -> None:
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "0")]),
        at=NOW - timedelta(hours=4),
    )
    delta = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.00", at=NOW - timedelta(hours=1))]),
        at=NOW - timedelta(hours=1),
    )
    h.scheduler().run_full(["fake"])
    h.scheduler().run_delta(["fake"])
    assert statuses(h.conn)[delta.name] == "held"
    assert counts(h.conn)["prices"] == 0


def test_running_the_same_job_twice_gives_identical_state(h) -> None:
    _full_and_delta(h)
    h.fetcher.add("stores", encode(stores=[]), at=NOW - timedelta(hours=5))
    first = h.scheduler().run_full(["fake"]).chains[0]
    first_delta = h.scheduler().run_delta(["fake"]).chains[0]
    assert first.loaded == 2 and first_delta.loaded == 1
    state = (counts(h.conn), statuses(h.conn))

    again = h.scheduler().run_full(["fake"]).chains[0]
    again_delta = h.scheduler().run_delta(["fake"]).chains[0]
    assert (again.skipped, again.loaded, again.downloaded) == (again.listed, 0, 0)
    assert (again_delta.skipped, again_delta.loaded) == (again_delta.listed, 0)
    assert (counts(h.conn), statuses(h.conn)) == state
    assert (
        h.conn.execute("SELECT count(*) FROM file_tracking WHERE chain_id = 'fake'").fetchone()[0]
        == 3
    )


def test_every_file_seen_has_an_accurate_status(h) -> None:
    h.fetcher.add("price_full", encode(items=[item("A")], prices=[price("A", "1", "5")]),
                  at=NOW - timedelta(hours=4))  # fmt: skip
    h.fetcher.add("price_full", encode(items=[item("B")], prices=[price("B", "2", "0")]),
                  store_code="2", at=NOW - timedelta(hours=4))  # fmt: skip
    h.fetcher.add("promo_full", b"!parse-error", at=NOW - timedelta(hours=4))
    h.fetcher.add("price", encode(items=[item("C")], prices=[price("C", "3", "1")]),
                  store_code="3", at=NOW - timedelta(hours=1))  # fmt: skip
    sched = h.scheduler()
    sched.run_full(["fake"])
    sched.run_delta(["fake"])
    assert sorted(statuses(h.conn).values()) == ["failed", "held", "loaded", "quarantined"]


def test_interrupted_load_is_recovered_on_the_next_run(h) -> None:
    remote = h.fetcher.add(
        "price_full", encode(items=[item("A")], prices=[price("A", "1", "5")]),
        at=NOW - timedelta(hours=4),
    )  # fmt: skip
    sched = h.scheduler()
    sched.run_full(["fake"])
    fid = h.conn.execute(
        "SELECT id FROM file_tracking WHERE path LIKE %s", (f"%{remote.name}",)
    ).fetchone()[0]
    # Simulate a process killed mid-load on a new file.
    other = h.fetcher.add(
        "price_full", encode(items=[item("B")], prices=[price("B", "2", "5")]), store_code="2",
        at=NOW - timedelta(hours=4),
    )  # fmt: skip
    from smartcart_ingest.download import download

    res = download(h.conn, h.fetcher, h.store, other, sched.adapter_for("fake"), NOW)
    tracking.mark_loading(h.conn, res.file.id)
    sched.run_full(["fake"])
    assert tracking.get(h.conn, res.file.id).status == "loaded"
    assert tracking.get(h.conn, fid).status == "loaded"


def test_portal_failure_backs_off_then_alerts_after_the_cap(h) -> None:
    h.fetcher.list_failures["fake"] = 99
    report = h.scheduler().run_full(["fake"])
    rep = report.chains[0]
    assert rep.error and "failed 3 times" in rep.error
    assert not report.ok
    assert h.sleeps == [1.0, 2.0]  # base 1 s, doubling, rng pinned at 1.0
    alerts = [a for a in h.sink.alerts if a.kind == "portal_failure"]
    assert len(alerts) == 1 and alerts[0].chain_id == "fake"


def test_transient_portal_failure_recovers_without_alert(h) -> None:
    h.fetcher.add("price_full", encode(items=[item("A")], prices=[price("A", "1", "5")]),
                  at=NOW - timedelta(hours=4))  # fmt: skip
    h.fetcher.list_failures["fake"] = 1
    h.fetcher.fetch_failures["fake"] = 1
    report = h.scheduler().run_full(["fake"])
    assert report.ok and report.chains[0].loaded == 1
    assert h.sleeps == [1.0, 1.0]
    assert not h.sink.alerts


def test_chain_without_adapter_is_reported(h) -> None:
    report = h.scheduler().run_full(["7290027600007"])
    assert report.chains[0].error.startswith("no adapter")
    assert not report.ok


def test_default_delta_run_polls_the_due_main_chains(h) -> None:
    sched = h.scheduler()
    assert set(sched.due_delta_chains()) == set(MAIN_CHAIN_IDS)
    report = sched.run_delta()
    assert {c.chain_id for c in report.chains} == set(MAIN_CHAIN_IDS)
