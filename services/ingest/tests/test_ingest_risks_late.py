"""Late full files (#60, risk 3 of "Design risks left open").

Only the 06:00 and 08:30 passes listed full files, so a chain that publishes its PriceFull after
08:30 was never loaded that day and its deltas were held and expired. ``run --mode late`` (timer
at 11:30 and 15:30) lists the full files of the chains that are still missing some, and a marker
file makes the precompute run again an hour later when one loaded.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import structlog
from typer.testing import CliRunner

from smartcart_ingest import cli
from smartcart_ingest.rawstore import LocalRawStore
from smartcart_ingest.scheduler import LATE_KINDS
from tests.fakes import NOW, encode, item, make_harness, price, promo, statuses

INFRA = Path(__file__).resolve().parents[3] / "infra" / "vps"
DAY = timedelta(days=1)
T0900 = NOW - timedelta(hours=1)  # the fixed "now" is 10:00 on 2026-10-06


def _unit(name: str) -> str:
    return (INFRA / name).read_text(encoding="utf-8")


# --- the units: no database ----------------------------------------------------------------------


def test_the_late_ingestion_timer_runs_at_1130_and_1530_israel_time() -> None:
    timer = _unit("smartcart-ingest-late.timer")
    assert re.findall(r"^OnCalendar=(.+)$", timer, re.M) == [
        "*-*-* 11:30:00 Asia/Jerusalem",
        "*-*-* 15:30:00 Asia/Jerusalem",
    ]
    assert "Unit=smartcart-ingest-late.service" in timer


def test_the_late_ingestion_service_takes_the_shared_lock_and_runs_the_late_mode() -> None:
    unit = _unit("smartcart-ingest-late.service")
    assert "/run/smartcart/ingest.lock" in unit  # the lock of the full and delta units
    assert re.search(r"ExecStart=/usr/bin/flock --timeout \d+ /run/smartcart/ingest.lock", unit)
    assert "run --mode late" in unit and "TimeoutStartSec=3h" in unit
    assert "ReadWritePaths=/var/lib/smartcart" in unit  # the marker is written there


def test_the_late_precompute_follows_each_late_pass_and_needs_the_marker() -> None:
    timer = _unit("smartcart-precompute-late.timer")
    assert re.findall(r"^OnCalendar=(.+)$", timer, re.M) == [
        "*-*-* 12:30:00 Asia/Jerusalem",
        "*-*-* 16:30:00 Asia/Jerusalem",
    ]
    unit = _unit("smartcart-precompute-late.service")
    ingest = _unit("smartcart-ingest-late.service")
    marker = re.search(r'LATE_LOAD_MARKER=(\S+?)"', unit).group(1)
    assert re.search(r'LATE_LOAD_MARKER=(\S+?)"', ingest).group(1) == marker  # one path, both units
    assert marker.startswith("/var/lib/smartcart/")
    # waits for the ingestion units, then runs under the shared lock, only when the marker exists
    assert unit.index("ExecStartPre=") < unit.index("ExecStart=/usr/bin/flock")
    assert "smartcart-ingest-late.service" in unit and "smartcart-ingest-full.service" in unit
    assert "/run/smartcart/ingest.lock" in unit and "smartcart-api precompute" in unit
    assert 'rm -f "$$marker"' in unit and "! -e" in unit
    assert "&& rm -f" in unit  # removed only after a precompute that succeeded


def test_setup_installs_and_enables_the_new_units() -> None:
    setup = _unit("setup.sh")
    for name in (
        "smartcart-ingest-late.service",
        "smartcart-ingest-late.timer",
        "smartcart-precompute-late.service",
        "smartcart-precompute-late.timer",
    ):
        assert name in setup
    assert "systemctl enable smartcart-ingest-full.timer smartcart-ingest-late.timer" in setup
    assert "smartcart-precompute-late.timer" in setup.split("systemctl enable smartcart-api")[1]


def test_the_existing_timers_are_unchanged() -> None:
    assert "08:30:00 Asia/Jerusalem" in _unit("smartcart-ingest-full.timer")
    assert "*:20:00 Asia/Jerusalem" in _unit("smartcart-ingest-delta.timer")
    assert "09:30:00 Asia/Jerusalem" in _unit("smartcart-precompute.timer")


# --- which chains need a late pass ---------------------------------------------------------------

db_only = pytest.mark.db


@pytest.fixture
def h(db, tmp_path):
    return make_harness(db, tmp_path)


def _full(h, store_code="1", at=None, code="A", price_="5.00", promos=False):
    at = at or h.clock[0] - timedelta(hours=1)
    h.fetcher.add(
        "price_full",
        encode(items=[item(code)], prices=[price(code, store_code, price_, at=at)]),
        store_code=store_code,
        at=at,
    )
    if promos:
        h.fetcher.add(
            "promo_full",
            encode(promos=[promo(f"P{store_code}", store_code, [code])]),
            store_code=store_code,
            at=at,
        )


def _yesterday(h, stores=("1",)):
    """A full sync on the previous day: PriceFull and PromoFull for each of ``stores``."""
    h.set_now(NOW - DAY)
    for s in stores:
        _full(h, s, promos=True)
    h.scheduler().run_full(["fake"])
    h.fetcher.clear()
    h.set_now(NOW)


@db_only
def test_a_chain_with_no_price_full_today_is_pending(h) -> None:
    assert h.scheduler().pending_full_chains(["fake"]) == ["fake"]  # a first day: nothing loaded


@db_only
def test_a_chain_that_loaded_what_it_loaded_yesterday_is_complete(h) -> None:
    _yesterday(h, stores=("1", "2"))
    for s in ("1", "2"):
        _full(h, s, promos=True)
    h.scheduler().run_full(["fake"])
    assert h.scheduler().pending_full_chains(["fake"]) == []


@db_only
def test_a_chain_missing_a_store_it_had_yesterday_is_pending(h) -> None:
    _yesterday(h, stores=("1", "2"))
    _full(h, "1", promos=True)  # store 2 has not published yet
    h.scheduler().run_full(["fake"])
    assert h.scheduler().pending_full_chains(["fake"]) == ["fake"]


@db_only
def test_a_missing_promo_full_makes_the_chain_pending_but_a_chain_without_promos_is_not(h) -> None:
    _yesterday(h, stores=("1",))
    _full(h, "1", promos=False)  # PriceFull only; yesterday had a PromoFull
    h.scheduler().run_full(["fake"])
    assert h.scheduler().pending_full_chains(["fake"]) == ["fake"]


@db_only
def test_a_chain_that_never_publishes_promos_is_complete_with_its_price_full(h) -> None:
    h.set_now(NOW - DAY)
    _full(h, "1", promos=False)
    h.scheduler().run_full(["fake"])
    h.fetcher.clear()
    h.set_now(NOW)
    _full(h, "1", promos=False)
    h.scheduler().run_full(["fake"])
    assert h.scheduler().pending_full_chains(["fake"]) == []


@db_only
def test_the_completeness_ratio_tolerates_a_store_or_two_of_a_hundred(db, tmp_path) -> None:
    h = make_harness(db, tmp_path, late_full_complete_ratio=0.5)
    _yesterday(h, stores=("1", "2"))
    _full(h, "1", promos=True)  # one of two: 50 %, at the ratio
    h.scheduler().run_full(["fake"])
    assert h.scheduler().pending_full_chains(["fake"]) == []


# --- the late pass -------------------------------------------------------------------------------


@db_only
def test_a_full_published_at_1100_is_loaded_by_the_1130_pass_with_its_held_delta(h) -> None:
    """The case of the issue: nothing at 06:00 and 08:30, the PriceFull appears at 11:00, its delta
    at 11:10 (held at the 11:20 tick), and the day is complete after the 11:30 pass."""
    h.set_now(NOW.replace(hour=8, minute=30))
    assert h.scheduler().run_full(["fake"]).chains[0].loaded == 0

    at_full = NOW.replace(hour=11, minute=0)
    at_delta = NOW.replace(hour=11, minute=10)
    h.fetcher.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=at_full)]),
        at=at_full,
    )
    delta = h.fetcher.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.50", at=at_delta)]),
        at=at_delta,
    )
    h.set_now(NOW.replace(hour=11, minute=20))
    h.scheduler().run_delta(["fake"])  # the hourly tick lists only deltas: it is held
    assert statuses(h.conn)[delta.name] == "held"

    h.set_now(NOW.replace(hour=11, minute=30))
    sched = h.scheduler()
    assert sched.pending_full_chains(["fake"]) == ["fake"]
    report = sched.run_late(["fake"])
    chain = report.chains[0]
    assert report.mode == "late" and chain.loaded_full == 1
    assert statuses(h.conn)[delta.name] == "loaded"  # applied behind its full in the same run
    price_now = h.conn.execute(
        "SELECT price FROM latest_prices lp JOIN items i ON i.id = lp.item_id"
        " WHERE i.item_code = 'A'"
    ).fetchone()[0]
    assert float(price_now) == 4.5
    assert sched.pending_full_chains(["fake"]) == []  # nothing left for the 15:30 pass


@db_only
def test_the_late_pass_lists_only_price_full_and_promo_full(h) -> None:
    seen: list[tuple] = []
    original = h.fetcher.list_files

    def spy(chain_id, kinds=None, since=None):
        seen.append(tuple(kinds or ()))
        return original(chain_id, kinds, since)

    h.fetcher.list_files = spy
    h.scheduler().run_late(["fake"])
    assert seen == [LATE_KINDS] == [("price_full", "promo_full")]


@db_only
def test_a_late_pass_over_files_already_loaded_loads_nothing_twice(h) -> None:
    _full(h, promos=True)
    h.scheduler().run_full(["fake"])
    report = h.scheduler().run_late(["fake"])
    chain = report.chains[0]
    assert (chain.loaded, chain.loaded_full, chain.skipped) == (0, 0, 2)


# --- the marker, through the CLI -----------------------------------------------------------------


@pytest.fixture
def wired(db, tmp_path, monkeypatch, database):
    from tests.fakes import FakeFetcher

    fetcher = FakeFetcher()

    @contextmanager
    def use_test_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", use_test_connection)
    monkeypatch.setattr(cli, "build_fetcher", lambda settings: fetcher)
    monkeypatch.setattr(cli, "build_rawstore", lambda settings: LocalRawStore(tmp_path / "raw"))
    monkeypatch.setattr(cli, "register_adapters", lambda: [])
    monkeypatch.setenv("DATABASE_URL", database.dsn)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("LATE_LOAD_MARKER", str(tmp_path / "state" / "late-full-loaded"))
    yield fetcher
    structlog.reset_defaults()


def _now() -> datetime:
    return datetime.now(tz=ZoneInfo("Asia/Jerusalem"))


@db_only
def test_a_late_load_leaves_the_marker_and_a_quiet_pass_does_not(wired, tmp_path) -> None:
    marker = tmp_path / "state" / "late-full-loaded"
    quiet = CliRunner().invoke(cli.app, ["run", "--mode", "late", "--chain", "fake"])
    assert quiet.exit_code == 0 and not marker.exists()

    at = _now() - timedelta(minutes=5)
    wired.add(
        "price_full", encode(items=[item("A")], prices=[price("A", "1", "5.00", at=at)]), at=at
    )
    loaded = CliRunner().invoke(cli.app, ["run", "--mode", "late", "--chain", "fake"])
    assert loaded.exit_code == 0 and '"loaded_full": 1' in loaded.output
    assert marker.read_text().startswith("1 full files")

    marker.unlink()  # the late precompute removed it
    again = CliRunner().invoke(cli.app, ["run", "--mode", "late", "--chain", "fake"])
    assert again.exit_code == 0 and not marker.exists()  # nothing new: not marked again


@db_only
def test_the_full_and_delta_modes_never_leave_the_marker(wired, tmp_path) -> None:
    at = _now() - timedelta(minutes=5)
    wired.add(
        "price_full", encode(items=[item("A")], prices=[price("A", "1", "5.00", at=at)]), at=at
    )
    result = CliRunner().invoke(cli.app, ["run", "--mode", "full", "--chain", "fake"])
    assert result.exit_code == 0 and not (tmp_path / "state").exists()


@db_only
def test_without_a_configured_marker_the_late_pass_still_works(wired, monkeypatch) -> None:
    monkeypatch.delenv("LATE_LOAD_MARKER")
    at = _now() - timedelta(minutes=5)
    wired.add(
        "price_full", encode(items=[item("A")], prices=[price("A", "1", "5.00", at=at)]), at=at
    )
    assert CliRunner().invoke(cli.app, ["run", "--mode", "late", "--chain", "fake"]).exit_code == 0
