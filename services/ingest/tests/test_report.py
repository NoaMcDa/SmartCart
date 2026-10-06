"""Exit report computation and rendering (issue #60). Needs Postgres but not PostGIS."""

from __future__ import annotations

import hashlib
import itertools
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from smartcart_ingest import report
from smartcart_ingest.report import D13_CHAINS, ChainSpec

pytestmark = pytest.mark.db

START = date(2026, 10, 20)
END = date(2026, 11, 2)  # 14 days
FAIL_DAY = date(2026, 10, 27)  # the eighth day

SHUFERSAL = "7290027600007"
RAMI_LEVY = "7290058140886"
VICTORY_A, VICTORY_B = "7290696200003", "7290058103393"

_counter = itertools.count()


def _sha() -> str:
    return hashlib.sha256(f"file-{next(_counter)}".encode()).hexdigest()


def _file(db, chain_id: str, day: date, kind: str, status: str, reason: str | None = None) -> None:
    published = datetime(day.year, day.month, day.day, 3, 0, tzinfo=UTC)  # 05:00 or 06:00 Israel
    db.execute(
        "INSERT INTO file_tracking (sha256, chain_id, kind, status, reason, published_at)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (_sha(), chain_id, kind, status, reason, published),
    )


def _all_chains(db) -> None:
    for spec in D13_CHAINS:
        for cid in spec.chain_ids:
            db.execute(
                "INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')"
                " ON CONFLICT DO NOTHING",
                (cid, spec.name),
            )


@pytest.fixture
def two_weeks(db):
    """14 nightly days for all ten chains; Rami Levy's load fails on FAIL_DAY.

    Victory publishes under two chain ids and only the first one loads, which must still count.
    A delta (kind `price`) that loaded must not count on its own.
    """
    _all_chains(db)
    for n in range(14):
        day = START + timedelta(days=n)
        for spec in D13_CHAINS:
            if spec.name == "Rami Levy" and day == FAIL_DAY:
                _file(db, RAMI_LEVY, day, "price_full", "quarantined", "price_jump")
                _file(db, RAMI_LEVY, day, "price", "loaded")  # a delta does not make a day
                continue
            _file(db, spec.chain_ids[0], day, "price_full", "loaded")
        _file(db, VICTORY_B, day, "price_full", "failed", "timeout")  # second id, ignored
    return db


def test_success_rate_streak_and_failed_files(two_weeks) -> None:
    rep = report.build_exit_report(two_weeks, START, END)

    assert rep.window_days == 14
    assert rep.success_rate == pytest.approx(139 / 140)
    assert rep.meets_success_rate

    assert len(rep.days) == 14
    failing = [d for d in rep.days if d.day == FAIL_DAY][0]
    assert (failing.succeeded, failing.total) == (9, 10)
    assert failing.rate == pytest.approx(0.9)
    assert not failing.above_threshold
    assert sum(d.above_threshold for d in rep.days) == 13

    # Seven good days, the failure, then six good days.
    assert rep.longest_streak == 7
    assert (rep.streak_start, rep.streak_end) == (date(2026, 10, 20), date(2026, 10, 26))

    rami = next(c for c in rep.chains if c.chain.name == "Rami Levy")
    assert rami.successes == 13 and rami.days[FAIL_DAY] is False
    assert rami.rate == pytest.approx(13 / 14)
    shufersal = next(c for c in rep.chains if c.chain.name == "Shufersal")
    assert shufersal.rate == 1.0
    victory = next(c for c in rep.chains if c.chain.name == "Victory")
    assert victory.rate == 1.0  # either chain id may carry the load

    reasons = {(f.chain_id, f.day, f.status, f.reason) for f in rep.failed_files}
    assert (RAMI_LEVY, FAIL_DAY, "quarantined", "price_jump") in reasons
    assert (VICTORY_B, START, "failed", "timeout") in reasons  # listed even though masked
    assert not any(f.kind == "price" for f in rep.failed_files)


def test_window_shorter_than_two_weeks_does_not_meet_the_criterion(two_weeks) -> None:
    rep = report.build_exit_report(two_weeks, START, START + timedelta(days=6))
    assert rep.success_rate == 1.0
    assert rep.longest_streak == 7
    assert not rep.meets_success_rate


def test_days_without_any_file_count_as_failures(two_weeks) -> None:
    rep = report.build_exit_report(two_weeks, START, END + timedelta(days=2))
    assert rep.window_days == 16
    assert rep.success_rate == pytest.approx(139 / 160)
    assert not rep.meets_success_rate
    assert rep.days[-1].succeeded == 0 and rep.longest_streak == 7


def test_rate_below_threshold_over_eight_chains_when_two_are_dropped(two_weeks) -> None:
    eight = tuple(c for c in D13_CHAINS if c.name not in {"King Store", "Machsanei Hashuk"})
    rep = report.build_exit_report(two_weeks, START, END, chains=eight)
    assert rep.success_rate == pytest.approx(111 / 112)
    assert rep.days[0].total == 8


def test_longest_streak_helper() -> None:
    def day(n: int, ok: bool) -> report.DaySummary:
        return report.DaySummary(START + timedelta(days=n), 1, 1, 1.0 if ok else 0.0, ok)

    flags = [True, True, False, True, True, True, False]
    assert report.longest_streak([day(n, f) for n, f in enumerate(flags)]) == (
        3,
        START + timedelta(days=3),
        START + timedelta(days=5),
    )
    assert report.longest_streak([]) == (0, None, None)
    assert report.longest_streak([day(0, False)]) == (0, None, None)


def test_physical_stores_without_coordinates_are_listed(db) -> None:
    _all_chains(db)
    db.execute(
        "INSERT INTO stores (chain_id, store_code, name, address, city, channel) VALUES"
        " (%s, '001', 'Shufersal Deal Ramat Aviv', 'Einstein 40', 'Tel Aviv', 'physical'),"
        " (%s, '002', 'Rami Levy Talpiot', NULL, 'Jerusalem', 'physical'),"
        " (%s, '999', 'Shufersal Online', NULL, NULL, 'online')",
        (SHUFERSAL, RAMI_LEVY, SHUFERSAL),
    )
    rep = report.build_exit_report(db, START, END)

    assert rep.physical_stores == 2  # the online store is not a physical store
    assert rep.stores_with_coordinates == 0
    assert rep.stores_missing_coordinates == 2
    listed = {(s.chain_id, s.store_code): s for s in rep.store_exceptions}
    assert set(listed) == {(SHUFERSAL, "001"), (RAMI_LEVY, "002")}
    assert listed[(SHUFERSAL, "001")].address == "Einstein 40"
    assert listed[(RAMI_LEVY, "002")].reason  # every exception states a reason


@pytest.mark.postgis
def test_stores_with_coordinates_are_not_exceptions(db) -> None:
    _all_chains(db)
    db.execute(
        "INSERT INTO stores (chain_id, store_code, name, geog) VALUES"
        " (%s, '001', 'Located', ST_SetSRID(ST_MakePoint(34.79, 32.07), 4326)::geography)",
        (SHUFERSAL,),
    )
    db.execute(
        "INSERT INTO stores (chain_id, store_code, name) VALUES (%s, '002', 'Not located')",
        (SHUFERSAL,),
    )
    rep = report.build_exit_report(db, START, END)
    assert rep.physical_stores == 2 and rep.stores_with_coordinates == 1
    assert [s.store_code for s in rep.store_exceptions] == ["002"]
    assert "geog is NULL" in rep.store_exceptions[0].reason


def _promo(db, chain_id: str, promo_id: str, reward_type: str, store_id=None, **kw) -> int:
    return db.execute(
        "INSERT INTO promos (chain_id, store_id, promo_id, description, reward_type,"
        " reward_value, min_qty, club_only, club_name, starts_at, ends_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            chain_id,
            store_id,
            promo_id,
            kw.get("description", f"promo {promo_id}"),
            reward_type,
            kw.get("reward_value"),
            kw.get("min_qty"),
            kw.get("club_name") is not None,
            kw.get("club_name"),
            datetime(2026, 10, 1, tzinfo=UTC),
            datetime(2026, 10, 31, tzinfo=UTC),
        ),
    ).fetchone()[0]


def test_promo_sample_is_capped_per_main_chain_and_spread_over_reward_types(db) -> None:
    _all_chains(db)
    types = ["price", "percent", "buy_x_get_y", "bundle", "other"]
    for n in range(30):  # 30 promos, six of each type
        _promo(db, SHUFERSAL, f"S{n}", types[n % 5], reward_value=Decimal("9.90"))
    for n in range(3):
        _promo(db, RAMI_LEVY, f"R{n}", "percent", reward_value=Decimal(10 + n))
    _promo(db, "7290058108879", "K1", "price")  # King Store is not a main chain

    store_id = db.execute(
        "INSERT INTO stores (chain_id, store_code, name) VALUES (%s, '001', 'S1') RETURNING id",
        (SHUFERSAL,),
    ).fetchone()[0]
    item_id = db.execute(
        "INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, 'i1', 'חלב') RETURNING id",
        (SHUFERSAL,),
    ).fetchone()[0]
    detailed = _promo(
        db, SHUFERSAL, "S-detail", "buy_x_get_y", store_id=store_id,
        description="2 ב-20 למועדון", min_qty=Decimal(2), club_name="Shufersal Club",
    )  # fmt: skip
    db.execute("INSERT INTO promo_items (promo_id, item_id) VALUES (%s, %s)", (detailed, item_id))

    rep = report.build_exit_report(db, START, END)

    assert set(rep.promo_samples) == {c.name for c in D13_CHAINS if c.main}
    shufersal = rep.promo_samples["Shufersal"]
    assert len(shufersal) == report.PROMO_SAMPLE_SIZE == 10
    assert {p.reward_type for p in shufersal} == set(types)  # spread, not the first ten rows
    assert len(rep.promo_samples["Rami Levy"]) == 3
    assert rep.promo_samples["Tiv Taam"] == []

    stats = {s.chain: s for s in rep.promo_stats}
    assert stats["Shufersal"].total == 31
    assert stats["Shufersal"].by_reward_type["buy_x_get_y"] == 7

    # The structured fields of a sampled promo are carried next to its raw description.
    full = report.build_exit_report(db, START, END, promo_sample_size=100)
    detail = next(p for p in full.promo_samples["Shufersal"] if p.promo_id == "S-detail")
    assert detail.description == "2 ב-20 למועדון"
    assert detail.store_code == "001"
    assert detail.reward_type == "buy_x_get_y"
    assert detail.min_qty == 2 and detail.club_only and detail.club_name == "Shufersal Club"
    assert detail.item_count == 1
    assert next(p for p in full.promo_samples["Shufersal"] if p.promo_id == "S0").store_code is None

    # A rerun on the same data picks the same promos.
    again = report.build_exit_report(db, START, END)
    assert [p.promo_id for p in again.promo_samples["Shufersal"]] == [p.promo_id for p in shufersal]


def test_render_markdown_has_every_section_and_the_numbers(two_weeks) -> None:
    _promo(two_weeks, SHUFERSAL, "S1", "percent", description="20 אחוז הנחה", reward_value=20)
    two_weeks.execute(
        "INSERT INTO stores (chain_id, store_code, name, city) VALUES (%s, '001', 'No coords', 'Haifa')",
        (SHUFERSAL,),
    )
    rep = report.build_exit_report(two_weeks, START, END)
    md = report.render_markdown(rep)

    assert md.startswith("# Phase 0 exit evidence, 2026-10-20 to 2026-11-02")
    for heading in (
        "## 1. Nightly loads",
        "## 2. Store coordinates",
        "## 3. Promo parsing, main chains",
        "## 4. Basket price across stores in a radius",
    ):
        assert heading in md
    assert "99.3%" in md and "**met**" in md
    assert "Longest streak" in md and "**7**" in md
    assert "10-27" in md and "FAIL" in md
    assert "price_jump" in md  # the failed file is explained
    assert "No coords" in md and "without: **1**" in md
    assert "20 אחוז הנחה" in md and "[ ]" in md
    assert "Not run in this report" in md


def test_render_markdown_includes_basket_rows_when_present(db) -> None:
    rep = report.build_exit_report(db, START, END)
    rep.basket_params = {"barcodes": ["1", "2"], "lon": 34.79, "lat": 32.07, "radius_m": 3000}
    rep.basket_rows = [
        {
            "store_id": 7, "chain_id": SHUFERSAL, "store_name": "S", "distance_m": 120,
            "basket_total": Decimal("13.50"), "found_count": 1, "missing_barcodes": ["2"],
            "is_complete": False,
        }
    ]  # fmt: skip
    md = report.render_markdown(rep)
    assert "| 7 | 7290027600007 | S | 120 | 13.50 | 1 | 2 | no |" in md
    assert "online stores excluded" in md


def test_end_before_start_is_rejected(db) -> None:
    with pytest.raises(ValueError):
        report.build_exit_report(db, END, START)


def test_module_runs_without_the_cli() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "smartcart_ingest.report", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--start" in out.stdout and "--out" in out.stdout


def test_main_requires_a_database(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert report.main(["--start", "2026-10-20", "--end", "2026-11-02"]) == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_chain_list_matches_decision_d13() -> None:
    assert len(D13_CHAINS) == 10
    assert [c.name for c in D13_CHAINS if c.main] == [
        "Shufersal", "Rami Levy", "Victory", "Yeinot Bitan and Carrefour", "Hazi Hinam", "Tiv Taam",
    ]  # fmt: skip
    assert isinstance(D13_CHAINS[0], ChainSpec)


def test_without_a_geog_column_every_physical_store_is_an_exception(db) -> None:
    """A database without PostGIS has no stores.geog; DDL is transactional, so drop it here."""
    db.execute("ALTER TABLE stores DROP COLUMN IF EXISTS geog")
    _all_chains(db)
    db.execute(
        "INSERT INTO stores (chain_id, store_code, name) VALUES (%s, '001', 'A'), (%s, '002', 'B')",
        (SHUFERSAL, RAMI_LEVY),
    )
    rep = report.build_exit_report(db, START, END)
    assert rep.physical_stores == 2 and rep.stores_with_coordinates == 0
    assert len(rep.store_exceptions) == 2
    assert "no stores.geog column" in rep.store_exceptions[0].reason
