"""Time budgets in the download path (#60, risk 7 of "Design risks left open").

A hung portal used to hold the run lock until the systemd unit's timeout (3 hours for the full
sync). Now one call has a timeout, a chain has a budget, and the run has a budget; a chain that
hangs is reported and alerted and the next chain still runs.
"""

from __future__ import annotations

import threading
import time
from datetime import timedelta

import pytest

from smartcart_ingest.alerts import Alerter
from smartcart_ingest.download import PortalError, PortalTimeout, RemoteFile, call_with_timeout
from smartcart_ingest.scheduler import (
    DEFAULT_CHAIN_BUDGET_SECONDS,
    DEFAULT_RUN_BUDGET_SECONDS,
    ChainBudgetExceeded,
    Deadline,
    PortalUnavailable,
    RunReport,
    Scheduler,
)
from smartcart_ingest.settings import Settings
from tests.fakes import (
    NOW,
    FakeAdapter,
    FakeFetcher,
    encode,
    item,
    make_harness,
    price,
    statuses,
)

# --- call_with_timeout: no database --------------------------------------------------------------


def test_a_call_that_finishes_returns_its_value_and_arguments_pass_through() -> None:
    assert call_with_timeout(lambda a, b=0: a + b, 5, "c", "add", 1, b=2) == 3


def test_an_error_raised_by_the_call_is_raised_in_the_callers_thread() -> None:
    def fail():
        raise PortalError("c", "connection reset")

    with pytest.raises(PortalError, match="connection reset"):
        call_with_timeout(fail, 5, "c", "fail")


def test_a_hung_call_raises_a_timeout_and_does_not_block_the_caller() -> None:
    release = threading.Event()
    started = time.monotonic()
    try:
        with pytest.raises(PortalTimeout, match=r"list_files did not finish within 0\.2 s"):
            call_with_timeout(release.wait, 0.2, "c", "list_files")
        assert time.monotonic() - started < 3
    finally:
        release.set()


def test_the_timeout_is_a_portal_error_that_names_the_chain() -> None:
    release = threading.Event()
    try:
        with pytest.raises(PortalError, match=r"^\[chain-x\]"):
            call_with_timeout(release.wait, 0.05, "chain-x", "fetch")
    finally:
        release.set()


def test_the_deadline_counts_down_on_its_own_clock() -> None:
    t = [100.0]
    d = Deadline(30, lambda: t[0])
    assert d.remaining() == 30 and not d.expired
    t[0] += 30
    assert d.remaining() == 0 and d.expired


def test_the_default_budgets_fit_under_the_unit_timeouts() -> None:
    """TimeoutStartSec: 3 h for the full and the late unit, 50 minutes for the delta unit."""
    assert DEFAULT_RUN_BUDGET_SECONDS["full"] < 3 * 3600
    assert DEFAULT_RUN_BUDGET_SECONDS["late"] < 3 * 3600
    assert DEFAULT_RUN_BUDGET_SECONDS["delta"] < 50 * 60
    for mode, chain in DEFAULT_CHAIN_BUDGET_SECONDS.items():
        assert chain < DEFAULT_RUN_BUDGET_SECONDS[mode]


def test_budget_settings_come_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("PORTAL_REQUEST_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("CHAIN_BUDGET_SECONDS", "120")
    monkeypatch.setenv("RUN_BUDGET_SECONDS", "")
    s = Settings()
    assert (s.portal_request_timeout_seconds, s.chain_budget_seconds, s.run_budget_seconds) == (
        30,
        120,
        None,
    )


# --- the scheduler -------------------------------------------------------------------------------

db_only = pytest.mark.db


class HangingFetcher(FakeFetcher):
    """Lists nothing for ``hang_list`` chains until released, and blocks in ``fetch`` of any file
    named in ``hang_fetch``."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()
        self.hang_list: set[str] = set()
        self.hang_fetch: set[str] = set()
        self.on_list = None

    def list_files(self, chain_id, kinds=None, since=None):
        if chain_id in self.hang_list:
            self.calls.append(("list", chain_id))
            self.release.wait(30)
            return []
        out = super().list_files(chain_id, kinds, since)
        if self.on_list:
            self.on_list(chain_id)
        return out

    def fetch(self, remote: RemoteFile) -> bytes:
        if remote.name in self.hang_fetch:
            self.calls.append(("fetch", remote.name))
            self.release.wait(30)
        return super().fetch(remote)


@pytest.fixture
def hung(db, tmp_path):
    h = make_harness(db, tmp_path, portal_request_timeout_seconds=0.2)
    h.fetcher = HangingFetcher()
    yield h
    h.fetcher.release.set()


def _scheduler(h, **kw) -> Scheduler:
    return Scheduler(
        h.conn,
        h.fetcher,
        h.store,
        Alerter([h.sink]),
        h.settings,
        adapter_for=lambda chain_id: FakeAdapter(),
        now=lambda: h.clock[0],
        sleep=h.sleeps.append,
        rng=lambda: 1.0,
        **kw,
    )


def _file(h, code="A", at=None):
    at = at or NOW - timedelta(hours=1)
    return h.fetcher.add(
        "price_full", encode(items=[item(code)], prices=[price(code, "1", "5.00", at=at)]), at=at
    )


@db_only
def test_a_hung_portal_is_reported_and_the_next_chain_still_runs(hung) -> None:
    hung.fetcher.hang_list = {"hung-chain"}
    remote = _file(hung)
    started = time.monotonic()
    report = _scheduler(hung).run_full(["hung-chain", "fake"])
    assert time.monotonic() - started < 10
    by_chain = {c.chain_id: c for c in report.chains}
    assert "did not finish within 0.2 s" in by_chain["hung-chain"].error
    assert by_chain["fake"].error is None and by_chain["fake"].loaded == 1
    assert statuses(hung.conn)[remote.name] == "loaded"
    assert not report.ok  # the CLI exits 1
    alerts = [a for a in hung.sink.alerts if a.kind == "portal_failure"]
    assert [a.chain_id for a in alerts] == ["hung-chain"]
    assert "did not finish" in alerts[0].message


@db_only
def test_a_timeout_is_not_retried_in_the_same_tick(hung) -> None:
    hung.fetcher.hang_list = {"hung-chain"}
    _scheduler(hung).run_full(["hung-chain"])
    assert hung.fetcher.calls.count(("list", "hung-chain")) == 1
    assert hung.sleeps == []  # no backoff either


@db_only
def test_a_file_that_hangs_in_fetch_stops_the_chain_not_the_run(hung) -> None:
    first = _file(hung, "A", NOW - timedelta(hours=2))
    hung.fetcher.hang_fetch = {first.name}
    report = _scheduler(hung).run_full(["fake"])
    assert "did not finish" in report.chains[0].error
    assert hung.conn.execute("SELECT count(*) FROM file_tracking").fetchone()[0] == 0


@db_only
def test_a_chain_budget_ends_a_slow_chain_and_says_so(db, tmp_path) -> None:
    h = make_harness(db, tmp_path, chain_budget_seconds=0.3, portal_request_timeout_seconds=60)
    h.fetcher = HangingFetcher()
    h.fetcher.hang_list = {"slow"}
    try:
        started = time.monotonic()
        report = _scheduler(h).run_full(["slow"])
        assert time.monotonic() - started < 10
    finally:
        h.fetcher.release.set()
    assert "time budget of 0.3 s exhausted" in report.chains[0].error
    assert [a.kind for a in h.sink.alerts] == ["portal_failure"]
    assert "time budget of 0.3 s exhausted" in h.sink.alerts[0].message


@db_only
def test_a_backoff_sleep_that_does_not_fit_in_the_budget_is_not_taken(db, tmp_path) -> None:
    h = make_harness(
        db, tmp_path, chain_budget_seconds=5, portal_backoff_base_seconds=500, portal_max_attempts=3
    )
    h.fetcher.list_failures = {"fake": 99}
    report = _scheduler(h).run_full(["fake"])
    assert h.sleeps == []  # a 500 s wait would end after the 5 s budget
    assert "time budget of 5 s exhausted" in report.chains[0].error
    assert "no time left to retry" in report.chains[0].error


@db_only
def test_the_run_budget_stops_the_run_and_reports_the_chains_not_started(db, tmp_path) -> None:
    h = make_harness(db, tmp_path, run_budget_seconds=50)
    clock = [1000.0]
    h.fetcher = HangingFetcher()
    h.fetcher.on_list = lambda chain_id: clock.__setitem__(0, clock[0] + 100)  # one chain: 100 s
    report = _scheduler(h, clock=lambda: clock[0]).run_full(["fake", "second", "third"])
    errors = {c.chain_id: c.error for c in report.chains}
    assert errors["fake"] is None  # it finished (the budget is checked between chains)
    assert all("run time budget of 50 s exhausted" in errors[c] for c in ("second", "third"))
    assert ("list", "second") not in h.fetcher.calls
    assert [a.chain_id for a in h.sink.alerts if a.kind == "portal_failure"] == [
        "second",
        "third",
    ]


@db_only
def test_the_budgets_leave_a_normal_run_alone(db, tmp_path) -> None:
    h = make_harness(db, tmp_path)
    remote = _file(h)
    report = _scheduler(h).run_full(["fake"])
    assert report.ok and statuses(h.conn)[remote.name] == "loaded"
    assert isinstance(report, RunReport) and not h.sink.alerts


def test_a_budget_error_is_a_portal_unavailable() -> None:
    err = ChainBudgetExceeded("c", 5, "before fetch x")
    assert isinstance(err, PortalUnavailable) and "time budget of 5 s" in str(err)


# --- the real fetcher under the timeout ----------------------------------------------------------


def test_the_upstream_scrape_runs_fine_in_the_timeout_thread(monkeypatch, tmp_path) -> None:
    """``ScraperFetcher.list_files`` calls ``asyncio.run``; it must work off the main thread."""
    from smartcart_ingest.download import ScraperFetcher
    from tests.test_download import _fake_upstream

    _fake_upstream(monkeypatch, [("PriceFull7290027600007-001-202610060600.gz", b"gz")])
    fetcher = ScraperFetcher(staging_root=tmp_path)
    (remote,) = call_with_timeout(
        fetcher.list_files, 20, "7290027600007", "list_files", "7290027600007", ["price_full"]
    )
    assert call_with_timeout(fetcher.fetch, 5, "7290027600007", "fetch", remote) == b"gz"
    fetcher.close()


def test_a_hung_upstream_scrape_times_out(monkeypatch, tmp_path) -> None:
    import asyncio

    import il_supermarket_scarper

    from smartcart_ingest.download import ScraperFetcher, load_upstream

    load_upstream()

    class HangingScraper:
        def __init__(self, file_output=None, status_database=None):
            pass

        async def scrape(self, files_types=None, when_date=None, **kw):
            await asyncio.sleep(30)
            yield  # pragma: no cover

    monkeypatch.setattr(
        il_supermarket_scarper.ScraperFactory,
        "get",
        classmethod(lambda cls, name, **kw: HangingScraper),
    )
    fetcher = ScraperFetcher(staging_root=tmp_path)
    started = time.monotonic()
    with pytest.raises(PortalTimeout):
        call_with_timeout(
            fetcher.list_files, 0.3, "7290027600007", "list_files", "7290027600007", ["price_full"]
        )
    assert time.monotonic() - started < 5
    fetcher.close()
