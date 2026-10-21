"""Regression tests from the pre-Phase-0-exit correctness review of the ingestion core.

Each test names the failure it prevents. The invariants they cover are listed in
``docs/ingestion.md`` ("Invariants covered by tests").
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
import structlog
from psycopg.pq import TransactionStatus
from typer.testing import CliRunner

from smartcart_ingest import cli, loader, quality, tracking
from smartcart_ingest.download import RemoteFile, download
from smartcart_ingest.models import FileKind
from smartcart_ingest.rawstore import LocalRawStore
from smartcart_ingest.scheduler import RUN_LOCK_KEY, RunLocked
from tests.fakes import (
    ISRAEL,
    NOW,
    FakeAdapter,
    FakeFetcher,
    counts,
    encode,
    item,
    make_harness,
    parsed_file,
    price,
    promo,
    statuses,
)

DAY = timedelta(days=1)


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=ISRAEL)


# --- no database -------------------------------------------------------------------------------


def test_stale_gate_counts_elapsed_time_across_the_autumn_clock_change() -> None:
    """Israel leaves summer time on 2026-10-25 at 02:00. Both datetimes carry the same tzinfo
    object, so Python subtracted wall clocks: 35.5 h instead of the real 36.5 h."""
    published = _at(24, 22)  # 19:00 UTC
    now = _at(26, 9, 30)  # 07:30 UTC
    assert (now - published) == timedelta(hours=35, minutes=30)  # the wall-clock trap
    parsed = parsed_file("price_full", encode(), at=published)
    failure = quality.gate_stale_date(parsed, 36, now)
    assert failure is not None and failure.gate == "stale_date"


def test_stale_gate_counts_elapsed_time_across_the_spring_clock_change() -> None:
    """Summer time starts 2026-03-27 at 02:00: 35.5 wall hours are only 34.5 real ones."""
    published = datetime(2026, 3, 26, 20, 0, tzinfo=ISRAEL)  # 18:00 UTC
    now = datetime(2026, 3, 28, 7, 30, tzinfo=ISRAEL)  # 04:30 UTC
    parsed = parsed_file("price_full", encode(), at=published)
    assert quality.gate_stale_date(parsed, 35, now) is None


def test_stale_gate_accepts_a_utc_clock() -> None:
    parsed = parsed_file("price_full", encode(), at=NOW - timedelta(hours=35))
    assert quality.gate_stale_date(parsed, 36, NOW.astimezone(UTC)) is None


def test_a_naive_observation_time_is_israel_time_not_the_servers() -> None:
    rec = price("A", "1", "5", at=datetime(2026, 10, 6, 6, 0))  # naive
    valid_from, clamped = loader.effective_observed_at(rec, NOW)
    assert valid_from == datetime(2026, 10, 6, 3, 0, tzinfo=UTC) and not clamped


def test_an_observation_after_the_publication_time_is_clamped() -> None:
    far = price("A", "1", "5", at=datetime(2099, 1, 1, tzinfo=ISRAEL))
    assert loader.effective_observed_at(far, NOW) == (NOW, True)
    skew = price("A", "1", "5", at=NOW + timedelta(hours=3))  # a time zone mixed up
    assert loader.effective_observed_at(skew, NOW) == (NOW + timedelta(hours=3), False)


def test_precompute_waits_for_the_morning_full_sync() -> None:
    """The flock only serializes; it does not order. A precompute that wins the lock before a
    queued 08:30 full sync would price yesterday's data."""
    infra = Path(__file__).resolve().parents[3] / "infra" / "vps"
    unit = (infra / "smartcart-precompute.service").read_text(encoding="utf-8")
    assert "ExecStartPre=" in unit and "smartcart-ingest-full.service" in unit
    assert unit.index("ExecStartPre=") < unit.index("ExecStart=/usr/bin/flock")
    timers = (infra / "smartcart-ingest-full.timer").read_text(encoding="utf-8")
    assert "06:00:00 Asia/Jerusalem" in timers and "08:30:00 Asia/Jerusalem" in timers
    pre = (infra / "smartcart-precompute.timer").read_text(encoding="utf-8")
    assert "09:30:00 Asia/Jerusalem" in pre


# --- the database ------------------------------------------------------------------------------


@pytest.fixture
def h(db, tmp_path):
    return make_harness(db, tmp_path)


def _first_download(h, remote: RemoteFile, now: datetime = NOW):
    sched = h.scheduler()
    return download(h.conn, h.fetcher, h.store, remote, sched.adapter_for("fake"), now)


def _current(db, code: str = "A", store_code: str = "1"):
    return db.execute(
        "SELECT cp.price FROM items i JOIN stores s ON s.chain_id = i.chain_id"
        " CROSS JOIN LATERAL current_price(i.id, s.id) cp"
        " WHERE i.chain_id = 'fake' AND i.item_code = %s AND s.store_code = %s",
        (code, store_code),
    ).fetchone()[0]


def _price_full(h, amount: str = "5.00", at: datetime = NOW - timedelta(hours=4), **kw):
    return h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", amount, at=at)], **kw),
        at=at,
    )


# -- concurrency --------------------------------------------------------------------------------


def test_a_second_run_is_refused_while_another_holds_the_lock(h, database) -> None:
    """The flock in the systemd units does not cover a manual run. Two runs would double-process
    files, and one run's start-up recovery would fail the other's in-flight file."""
    _price_full(h)
    with psycopg.connect(database.dsn, autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock(%s)", (RUN_LOCK_KEY,))
        with pytest.raises(RunLocked):
            h.scheduler().run_full(["fake"])
        with pytest.raises(RunLocked):
            h.scheduler().run_delta(["fake"])
        assert counts(h.conn)["prices"] == 0  # nothing was touched
        other.execute("SELECT pg_advisory_unlock(%s)", (RUN_LOCK_KEY,))
        assert h.scheduler().run_full(["fake"]).chains[0].loaded == 1


def test_the_run_lock_is_released_after_a_run_and_after_a_crash(h, database) -> None:
    _price_full(h)
    sched = h.scheduler()
    sched.run_full(["fake"])
    with psycopg.connect(database.dsn, autocommit=True) as other:
        assert other.execute("SELECT pg_try_advisory_lock(%s)", (RUN_LOCK_KEY,)).fetchone()[0]
        other.execute("SELECT pg_advisory_unlock(%s)", (RUN_LOCK_KEY,))
    with pytest.raises(KeyboardInterrupt), sched.exclusive():
        raise KeyboardInterrupt
    with psycopg.connect(database.dsn, autocommit=True) as other:
        assert other.execute("SELECT pg_try_advisory_lock(%s)", (RUN_LOCK_KEY,)).fetchone()[0]
        other.execute("SELECT pg_advisory_unlock(%s)", (RUN_LOCK_KEY,))


def test_the_cli_exits_75_without_ingesting_when_the_lock_is_taken(
    h, db, database, tmp_path, monkeypatch
) -> None:
    @contextmanager
    def use_test_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", use_test_connection)
    monkeypatch.setattr(cli, "build_fetcher", lambda settings: h.fetcher)
    monkeypatch.setattr(cli, "build_rawstore", lambda settings: LocalRawStore(tmp_path / "cli"))
    monkeypatch.setattr(cli, "register_adapters", lambda: [])
    monkeypatch.setenv("DATABASE_URL", database.dsn)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    recent = datetime.now(tz=ISRAEL) - timedelta(hours=2)  # the CLI uses the real clock
    _price_full(h, at=recent)
    try:
        with psycopg.connect(database.dsn, autocommit=True) as other:
            other.execute("SELECT pg_advisory_lock(%s)", (RUN_LOCK_KEY,))
            result = CliRunner().invoke(cli.app, ["run", "--mode", "full", "--chain", "fake"])
        assert result.exit_code == cli.EXIT_LOCKED == 75
        assert counts(db)["prices"] == 0
        # The lock died with the other connection: the next run goes through.
        again = CliRunner().invoke(cli.app, ["run", "--mode", "full", "--chain", "fake"])
        assert again.exit_code == 0
        assert counts(db)["prices"] == 1
    finally:
        structlog.reset_defaults()


# -- a crash must not stop the others, nor load a file ------------------------------------------


def test_one_chains_crash_is_reported_and_the_other_chains_still_run(h) -> None:
    _price_full(h)
    sched = h.scheduler()
    real = sched.adapter_for

    def adapter_for(chain_id: str):
        if chain_id == "boom":
            raise RuntimeError("adapter factory bug")
        return real(chain_id)

    sched.adapter_for = adapter_for
    report = sched.run_full(["boom", "fake"])
    by_chain = {c.chain_id: c for c in report.chains}
    assert "adapter factory bug" in (by_chain["boom"].error or "")
    assert by_chain["fake"].loaded == 1
    assert not report.ok
    assert [a.chain_id for a in h.sink.alerts if a.kind == "load_failure"] == ["boom"]


def test_a_gate_that_crashes_fails_the_file_and_never_loads_it(h, monkeypatch) -> None:
    """quality.check raising (a database or decimal error) used to propagate out of the run and
    leave the file in 'loading'. It must fail the file, load nothing and go on."""
    _price_full(h)
    h.fetcher.add(
        "price_full",
        encode(items=[item("B")], prices=[price("B", "2", "7.00")]),
        store_code="2",
        at=NOW - timedelta(hours=4),
    )
    real = quality.check
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ArithmeticError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(quality, "check", flaky)
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.failed == 1 and rep.loaded == 1 and rep.error is None
    assert sorted(statuses(h.conn).values()) == ["failed", "loaded"]
    assert counts(h.conn)["prices"] == 1  # only the file whose gates ran
    reason = h.conn.execute("SELECT reason FROM file_tracking WHERE status = 'failed'").fetchone()[
        0
    ]
    assert "quality check crashed: ArithmeticError" in reason
    assert "load_failure" in h.kinds_of_alerts()


def test_a_failed_load_leaves_no_rows_and_a_retry_adds_each_event_once(h, monkeypatch) -> None:
    """A crash mid-load (after the price rows are written) rolls everything back, the file is
    not done, and the retry plus a byte-different republish never double-insert an event."""
    _price_full(h)
    real = loader._upsert_promos
    monkeypatch.setattr(
        loader, "_upsert_promos", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk"))
    )
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.failed == 1 and rep.loaded == 0
    after = counts(h.conn)
    assert after["prices"] == 0 and after["items"] == 0 and after["stores"] == 0
    assert list(statuses(h.conn).values()) == ["failed"]

    monkeypatch.setattr(loader, "_upsert_promos", real)
    rep = h.scheduler().run_full(["fake"]).chains[0]  # the failed file is seen again: retried
    assert rep.loaded == 1 and counts(h.conn)["prices"] == 1

    h.fetcher.clear()
    _price_full(h, salt="republished")  # same prices, different bytes, so a different hash
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 1 and counts(h.conn)["prices"] == 1  # no second event


def test_a_quarantined_file_writes_no_rows_and_is_never_loaded_again(h) -> None:
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "0.00")]),
        at=NOW - timedelta(hours=4),
    )
    h.scheduler().run_full(["fake"])
    after = counts(h.conn)
    assert after["prices"] == 0 and after["items"] == 0 and after["stores"] == 0
    assert list(statuses(h.conn).values()) == ["quarantined"]
    again = h.scheduler().run_full(["fake"]).chains[0]
    assert again.skipped == 1 and again.loaded == 0 and counts(h.conn)["prices"] == 0


# -- interrupted files --------------------------------------------------------------------------


def test_an_interrupted_file_is_retried_even_when_the_portal_no_longer_lists_it(h) -> None:
    """A full file whose load was killed at the 08:30 pass is not listed again until tomorrow
    (listings are per day), so it used to stay 'failed' and hold the day's deltas."""
    remote = _price_full(h)
    res = _first_download(h, remote)
    tracking.mark_loading(h.conn, res.file.id)  # the process dies here
    h.fetcher.clear()
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.listed == 0 and rep.loaded == 1
    assert tracking.get(h.conn, res.file.id).status == "loaded"


def test_a_file_that_kills_the_worker_twice_is_not_retried_a_third_time(h) -> None:
    remote = _price_full(h)
    res = _first_download(h, remote)
    tracking.mark_loading(h.conn, res.file.id)
    assert tracking.recover_interrupted(h.conn, "fake") == 1
    assert tracking.get(h.conn, res.file.id).reason == tracking.INTERRUPTED
    # The retry starts (marked) and the process dies again.
    tracking.mark_loading(h.conn, res.file.id, tracking.RETRYING_AFTER_INTERRUPTION)
    assert tracking.recover_interrupted(h.conn, "fake") == 1
    assert tracking.get(h.conn, res.file.id).reason == tracking.INTERRUPTED_TWICE
    h.fetcher.clear()
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 0 and tracking.get(h.conn, res.file.id).status == "failed"
    assert counts(h.conn)["prices"] == 0


def test_a_retry_after_an_interruption_is_marked_so_the_next_death_is_recognised(
    h, monkeypatch
) -> None:
    remote = _price_full(h)
    res = _first_download(h, remote)
    tracking.mark_loading(h.conn, res.file.id)
    tracking.recover_interrupted(h.conn, "fake")
    seen: list[str | None] = []
    real = tracking.mark_loading

    def spy(conn, file_id, reason=None):
        seen.append(reason)
        return real(conn, file_id, reason)

    monkeypatch.setattr(tracking, "mark_loading", spy)
    h.fetcher.clear()
    h.scheduler().run_full(["fake"])
    assert seen == [tracking.RETRYING_AFTER_INTERRUPTION]


# -- full before delta --------------------------------------------------------------------------


def test_open_files_apply_the_full_before_a_delta_published_earlier(h) -> None:
    """After a crash the open files were processed by publication time: a delta published at
    02:00 was held (its 05:00 full still 'downloaded'), the full then loaded, and the delta sat
    held until the next run."""
    delta_at, full_at = _at(6, 2), _at(6, 5)
    full = h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=full_at)]),
        at=full_at,
    )
    delta = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.50", at=_at(6, 5, 30))]),
        at=delta_at,
    )
    _first_download(h, delta)  # downloaded first, then the full: ids do not help either
    _first_download(h, full)
    h.fetcher.clear()
    rep = h.scheduler().run_delta(["fake"]).chains[0]
    assert sorted(statuses(h.conn).values()) == ["loaded", "loaded"]
    assert rep.held == 0 and _current(h.conn) == Decimal("4.50")


def test_a_byte_identical_full_on_the_next_day_does_not_hold_that_days_deltas(h) -> None:
    """A store whose prices did not change can republish the same bytes. The hash skip is right,
    but the next day's deltas wait for a loaded full file of that day and stayed held for good."""
    same_bytes = encode(items=[item("A")], prices=[price("A", "1", "5.00", at=_at(6, 3))])
    h.fetcher.add("price_full", same_bytes, at=_at(6, 6))
    h.set_now(_at(6, 10))
    assert h.scheduler().run_full(["fake"]).chains[0].loaded == 1

    h.fetcher.clear()
    h.fetcher.add("price_full", same_bytes, at=_at(7, 6))  # identical content, a day later
    h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.00", at=_at(7, 9))]),
        at=_at(7, 9),
    )
    h.set_now(_at(7, 10))
    h.scheduler().run_full(["fake"])  # the identical full is skipped by hash ...
    rep = h.scheduler().run_delta(["fake"]).chains[0]  # ... and the delta is not held
    assert rep.held == 0 and rep.loaded == 1
    assert _current(h.conn) == Decimal("4.00")
    # Re-running records the republication once.
    rows = h.conn.execute("SELECT count(*) FROM file_tracking WHERE reason LIKE '%republished'")
    assert rows.fetchone()[0] == 1
    h.scheduler().run_full(["fake"])
    rows = h.conn.execute("SELECT count(*) FROM file_tracking WHERE reason LIKE '%republished'")
    assert rows.fetchone()[0] == 1


def test_the_republished_row_carries_the_item_count_for_the_next_gate(h) -> None:
    same_bytes = encode(
        items=[item("A"), item("B")],
        prices=[price("A", "1", "5", at=_at(6, 3)), price("B", "1", "6", at=_at(6, 3))],
    )
    h.fetcher.add("price_full", same_bytes, at=_at(6, 6))
    h.set_now(_at(6, 10))
    h.scheduler().run_full(["fake"])
    h.fetcher.clear()
    h.fetcher.add("price_full", same_bytes, at=_at(7, 6))
    h.set_now(_at(7, 10))
    h.scheduler().run_full(["fake"])
    before = _at(7, 7)
    assert tracking.previous_full_count(h.conn, "fake", "1", "price_full", before) == 2
    # Day 3's file with 1 record is below half of that baseline: the gate can fire on day 3.
    gate = quality.gate_item_count_drop(
        h.conn,
        parsed_file(
            "price_full",
            encode(items=[item("A")], prices=[price("A", "1", "5")]),
            at=_at(8, 6),
        ),
        0.9,
    )
    assert gate is not None and gate.gate == "item_count_drop"


# -- listing ------------------------------------------------------------------------------------


class _CapturingFetcher(FakeFetcher):
    def __init__(self) -> None:
        super().__init__()
        self.since: list[datetime | None] = []

    def list_files(
        self,
        chain_id: str,
        kinds: Sequence[FileKind] | None = None,
        since: datetime | None = None,
    ) -> list[RemoteFile]:
        self.since.append(since)
        return super().list_files(chain_id, kinds, since)


def test_the_delta_ticks_after_midnight_also_list_yesterday(h) -> None:
    """A delta published at 23:50 is first listed at the 00:20 tick, which only asked for the
    new day: the file was never listed again, and its price changes waited for the next full."""
    h.fetcher = _CapturingFetcher()
    for now in (_at(7, 0, 20), _at(7, 1, 20), _at(7, 2, 20), _at(7, 14, 20)):
        h.set_now(now)
        h.scheduler().run_delta(["fake"])
    assert h.fetcher.since == [_at(6, 0), _at(6, 0), _at(7, 0), _at(7, 0)]
    h.fetcher.since.clear()
    h.set_now(_at(7, 0, 20))
    h.scheduler().run_full(["fake"])
    assert h.fetcher.since == [_at(7, 0)]  # the full sync never looks back


def test_a_late_evening_delta_loads_at_the_next_midnight_tick(h) -> None:
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=_at(6, 5))]),
        at=_at(6, 5),
    )
    h.set_now(_at(6, 6))
    h.scheduler().run_full(["fake"])
    late = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.20", at=_at(6, 23, 50))]),
        at=_at(6, 23, 50),
    )
    h.set_now(_at(7, 0, 20))
    rep = h.scheduler().run_delta(["fake"]).chains[0]
    assert rep.loaded == 1 and statuses(h.conn)[late.name] == "loaded"
    assert _current(h.conn) == Decimal("4.20")


def test_a_delta_from_the_small_hours_waits_for_the_new_days_full(h) -> None:
    """Files published 00:00-08:00 Israel time belong to the new day: a 00:10 delta is held
    until that day's full (05:00) loads, then applied in the same run."""
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=_at(6, 5))]),
        at=_at(6, 5),
    )
    h.set_now(_at(6, 6))
    h.scheduler().run_full(["fake"])
    h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.00", at=_at(7, 0, 10))]),
        at=_at(7, 0, 10),
    )
    h.set_now(_at(7, 1, 20))
    rep = h.scheduler().run_delta(["fake"]).chains[0]
    assert rep.held == 1 and _current(h.conn) == Decimal("5.00")
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=_at(6, 5))], salt="d2"),
        at=_at(7, 5),
    )
    h.set_now(_at(7, 6))
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 2 and _current(h.conn) == Decimal("4.00")


# -- held deltas --------------------------------------------------------------------------------


def test_held_deltas_of_days_whose_full_never_loaded_are_given_up_on(h) -> None:
    old = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.00", at=_at(3, 12))]),
        at=_at(3, 12),
    )
    recent = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.10", at=_at(5, 12))]),
        at=_at(5, 12),
    )
    h.scheduler().run_delta(["fake"])  # clock: 2026-10-06 10:00
    st = statuses(h.conn)
    assert st[old.name] == "failed" and st[recent.name] == "held"
    reason = h.conn.execute(
        "SELECT reason FROM file_tracking WHERE path LIKE %s", (f"%{old.name}",)
    ).fetchone()[0]
    assert reason.startswith("expired: waiting for price_full")
    assert [f.path.rsplit("/", 1)[-1] for f in tracking.open_files(h.conn, "fake")] == [recent.name]


# -- fetch errors versus archive errors ---------------------------------------------------------


def test_an_archive_error_is_not_retried_as_a_portal_error(h, monkeypatch) -> None:
    """download() sat inside the portal backoff: a full disk was retried five times, the second
    fetch failed ('staged file unreadable'), and the alert said the portal was down."""
    remote = _price_full(h)

    def full_disk(key: str, data: bytes) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(h.store, "put", full_disk)
    report = h.scheduler().run_full(["fake"])
    assert [name for kind, name in h.fetcher.calls if kind == "fetch"] == [remote.name]
    assert h.sleeps == []
    assert "No space left" in (report.chains[0].error or "")
    assert "portal_failure" not in h.kinds_of_alerts()
    assert "load_failure" in h.kinds_of_alerts()


def test_a_flaky_fetch_is_still_retried(h) -> None:
    _price_full(h)
    h.fetcher.fetch_failures["fake"] = 2
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 1 and h.sleeps == [1.0, 2.0] and not h.sink.alerts


# -- gates --------------------------------------------------------------------------------------


@pytest.mark.parametrize(("kind", "loads"), [("price_full", False), ("stores", False)])
def test_an_empty_full_file_is_quarantined_not_loaded(h, kind: str, loads: bool) -> None:
    """A portal glitch that serves an empty PriceFull or Stores file used to load 'successfully',
    count as the night's load, and set the item-count baseline to zero."""
    h.fetcher.add(kind, encode(), at=NOW - timedelta(hours=4))
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.quarantined == 1 and rep.loaded == 0
    gates = [r[0] for r in h.conn.execute("SELECT gate FROM quarantine_events").fetchall()]
    assert gates == ["empty_file"]


def test_an_empty_promo_full_is_legitimate(h) -> None:
    h.fetcher.add("promo_full", encode(), at=NOW - timedelta(hours=4))
    rep = h.scheduler().run_full(["fake"]).chains[0]
    assert rep.loaded == 1 and rep.quarantined == 0


def test_the_gates_fire_on_the_second_day(h) -> None:
    """Day 1 has no history, so only day 2 can show that the price-jump and item-count gates
    really read what day 1 loaded."""
    items = [item(c) for c in "ABCD"]
    day1 = [price(c, "1", "10.00", at=_at(6, 3)) for c in "ABCD"]
    h.fetcher.add("price_full", encode(items=items, prices=day1), at=_at(6, 6))
    h.set_now(_at(6, 10))
    assert h.scheduler().run_full(["fake"]).chains[0].loaded == 1

    h.fetcher.clear()
    jump = [price("A", "1", "31.00", at=_at(7, 3))] + [
        price(c, "1", "10.00", at=_at(7, 3)) for c in "BCD"
    ]
    h.fetcher.add("price_full", encode(items=items, prices=jump), at=_at(7, 6))
    h.set_now(_at(7, 10))
    h.scheduler().run_full(["fake"])
    assert _current(h.conn, "A") == Decimal("10.00")
    gates = [r[0] for r in h.conn.execute("SELECT gate FROM quarantine_events").fetchall()]
    assert gates == ["price_jump"]

    h.fetcher.clear()
    short = [price("A", "1", "10.00", at=_at(8, 3))]
    h.fetcher.add("price_full", encode(items=items[:1], prices=short), at=_at(8, 6))
    h.set_now(_at(8, 10))
    h.scheduler().run_full(["fake"])
    gates = [r[0] for r in h.conn.execute("SELECT gate FROM quarantine_events").fetchall()]
    assert gates == ["price_jump", "item_count_drop"]  # the baseline is day 1, not the jump file


# -- price event times --------------------------------------------------------------------------


def test_a_price_dated_in_the_future_cannot_freeze_the_item(h) -> None:
    """valid_from only moves forward and an older observation is skipped. One record dated 2099
    (a typo, a clock) used to make every real update of that item and store a 'stale' one."""
    h.fetcher.add(
        "price_full",
        encode(
            items=[item("A")],
            prices=[price("A", "1", "5.00", at=datetime(2099, 1, 1, tzinfo=ISRAEL))],
        ),
        at=_at(6, 6),
    )
    h.set_now(_at(6, 7))
    h.scheduler().run_full(["fake"])
    valid_from = h.conn.execute("SELECT valid_from FROM prices").fetchone()[0]
    assert valid_from == _at(6, 6)  # dated at the publication time

    h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "6.00", at=_at(6, 9))]),
        at=_at(6, 9),
    )
    h.set_now(_at(6, 10))
    h.scheduler().run_delta(["fake"])
    assert _current(h.conn) == Decimal("6.00")


def test_a_naive_observation_time_is_stored_as_israel_time(h) -> None:
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=datetime(2026, 10, 6, 6, 0))]),
        at=_at(6, 7),
    )
    h.set_now(_at(6, 8))
    h.scheduler().run_full(["fake"])
    valid_from = h.conn.execute("SELECT valid_from FROM prices").fetchone()[0]
    assert valid_from == datetime(2026, 10, 6, 3, 0, tzinfo=UTC)  # 06:00 Israel time (UTC+3)


def test_events_straddling_a_month_boundary_land_in_their_utc_month(h) -> None:
    """Partitions are UTC months: 01:30 Israel time on 1 November is 23:30 UTC on 31 October."""
    at = datetime(2026, 11, 1, 1, 30, tzinfo=ISRAEL)
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=at)]),
        at=at + timedelta(minutes=5),
    )
    h.set_now(at + timedelta(hours=2))
    assert h.scheduler().run_full(["fake"]).chains[0].loaded == 1
    tables = h.conn.execute("SELECT tableoid::regclass::text FROM prices").fetchall()
    assert tables == [("prices_2026_10",)]


def test_a_new_months_partition_is_created_before_the_first_event_of_that_month(h) -> None:
    at = datetime(2027, 3, 1, 8, 0, tzinfo=ISRAEL)
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=at)]),
        at=at,
    )
    h.set_now(at + timedelta(hours=1))
    assert h.scheduler().run_full(["fake"]).chains[0].loaded == 1
    assert h.conn.execute("SELECT tableoid::regclass::text FROM prices").fetchall() == [
        ("prices_2027_03",)
    ]


def test_partitions_are_created_outside_the_load_transaction(database, tmp_path, monkeypatch):
    """Creating a partition locks the parent table. Inside the load transaction that lock would
    be held, and the API's price reads blocked, until the whole file is committed."""
    seen: list[TransactionStatus] = []
    real = loader._ensure_partitions

    def spy(conn, parsed):
        seen.append(conn.info.transaction_status)
        return real(conn, parsed)

    monkeypatch.setattr(loader, "_ensure_partitions", spy)
    at = NOW - timedelta(hours=4)
    parsed = parsed_file(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=at)]),
        "1",
        at,
        "raw/fake/outside-txn",
    )
    conn = psycopg.connect(database.dsn, autocommit=True)
    try:
        conn.execute("SET TIME ZONE 'UTC'")
        row, _ = tracking.register(conn, parsed.raw)
        tracking.mark_downloaded(conn, row.id, parsed.raw.path)
        loader.load(conn, parsed, FakeAdapter())
        assert seen == [TransactionStatus.IDLE]
    finally:
        conn.execute(
            "DELETE FROM prices WHERE item_id IN (SELECT id FROM items WHERE chain_id = 'fake')"
        )
        conn.execute("DELETE FROM items WHERE chain_id = 'fake'")
        conn.execute("DELETE FROM stores WHERE chain_id = 'fake'")
        conn.execute("DELETE FROM file_tracking WHERE chain_id = 'fake'")
        conn.execute("DELETE FROM chains WHERE id = 'fake'")
        conn.close()


def test_promo_times_without_a_zone_are_israel_time(h) -> None:
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00")]),
        at=NOW - timedelta(hours=4),
    )
    h.fetcher.add(
        "promo_full",
        encode(
            promos=[promo("P1", "1", ["A"], starts_at=datetime(2026, 10, 1, 0, 0))],
        ),
        at=NOW - timedelta(hours=4),
    )
    h.scheduler().run_full(["fake"])
    starts = h.conn.execute("SELECT starts_at FROM promos").fetchone()[0]
    assert starts == datetime(2026, 9, 30, 21, 0, tzinfo=UTC)
