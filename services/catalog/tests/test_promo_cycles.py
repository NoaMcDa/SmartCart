"""Promo cycle prediction (issue #69): window merging, the cycle math, the gate, the advice, the
backtest, the synthetic generator, the database read and the CLI. Synthetic history only."""

from __future__ import annotations

import json
import statistics
from contextlib import contextmanager
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from smartcart_catalog import cli
from smartcart_catalog import promo_cycles as pc
from smartcart_catalog.promo_cycles import Window

TODAY = date(2026, 10, 8)


def every(period: int, n: int, first: date, length: int = 7) -> list[Window]:
    return [
        Window(first + timedelta(days=i * period), first + timedelta(days=i * period + length - 1))
        for i in range(n)
    ]


# --- math ----------------------------------------------------------------------------------------


def test_overlapping_and_adjacent_spans_merge() -> None:
    d = date(2026, 1, 1)
    spans = [
        (d, d + timedelta(days=6)),  # store A
        (d + timedelta(days=2), d + timedelta(days=9)),  # store B, overlapping
        (d + timedelta(days=11), d + timedelta(days=13)),  # renewed after a 1-day gap
        (d + timedelta(days=30), None),  # no end: its start day only
        (d + timedelta(days=40), d + timedelta(days=39)),  # end before start: its start day
    ]
    assert pc.merge_windows(spans) == [
        Window(d, d + timedelta(days=13)),
        Window(d + timedelta(days=30), d + timedelta(days=30)),
        Window(d + timedelta(days=40), d + timedelta(days=40)),
    ]


def test_confidence_rewards_cycles_and_regularity() -> None:
    assert pc.confidence([]) == 0.0
    assert pc.confidence([42]) == 0.0  # one gap says nothing about regularity
    assert pc.confidence([42, 42, 42]) == round(3 / 4.5, 3)  # 0.667
    assert pc.confidence([42] * 10) == round(10 / 11.5, 3)
    jitter = [38, 46, 41, 43]
    cv = statistics.stdev(jitter) / statistics.fmean(jitter)
    assert pc.confidence(jitter) == round(4 / 5.5 * (1 - cv), 3)
    assert pc.confidence([10, 90, 15, 80]) < 0.3
    assert pc.confidence([5, 200, 5]) == 0.0  # cv above 1 floors at 0


def test_a_regular_six_week_promo_predicts_the_next_window() -> None:
    windows = every(42, 5, date(2026, 3, 1))  # last start 2026-08-16, ends 08-22
    est = pc.estimate(windows, today=date(2026, 9, 1))
    assert est.cycles_seen == 4 and est.median_gap_days == 42.0
    assert est.confidence == round(4 / 5.5, 3)
    assert est.last_end == date(2026, 8, 22)
    # next start 2026-09-27, tolerance 3 days before the start and after the 7-day window
    assert (est.next_from, est.next_to) == (date(2026, 9, 24), date(2026, 10, 6))
    assert est.advice == "buy_now"  # more than 14 days away: do not delay


def test_advice_wait_buy_now_and_overdue() -> None:
    windows = every(42, 5, date(2026, 3, 1))
    assert pc.estimate(windows, today=date(2026, 9, 17)).advice == "wait"  # opens in 7 days
    assert (
        pc.estimate(windows, today=date(2026, 9, 27)).advice == "wait"
    )  # window open, no promo yet
    assert pc.estimate(windows, today=date(2026, 8, 18)).advice == "buy_now"  # a promo is running
    overdue = pc.estimate(windows, today=date(2026, 10, 15))
    assert overdue.advice == "unknown" and overdue.next_from is None and overdue.cycles_seen == 4


def test_the_gate_hides_predictions() -> None:
    three_cycles = every(30, 4, date(2026, 5, 1))
    assert pc.estimate(three_cycles, today=date(2026, 8, 15)).advice != "unknown"  # 0.667 >= 0.6
    two_cycles = every(30, 3, date(2026, 6, 1))
    est = pc.estimate(two_cycles, today=date(2026, 8, 15))
    assert est.advice == "unknown" and est.next_from is None and est.next_to is None
    assert est.cycles_seen == 2 and est.median_gap_days == 30.0  # the evidence is still shown
    irregular = [
        Window(date(2026, 1, 1) + timedelta(days=d), date(2026, 1, 1) + timedelta(days=d + 6))
        for d in (0, 15, 100, 120, 200, 215)
    ]
    est = pc.estimate(irregular, today=date(2026, 7, 25))
    assert est.cycles_seen == 5 and est.confidence < pc.MIN_CONFIDENCE and est.advice == "unknown"
    assert pc.estimate([], TODAY).advice == "unknown"


def test_tolerance_grows_with_the_spread_of_gaps() -> None:
    d = date(2026, 1, 1)
    starts = [0, 40, 85, 125, 170]  # gaps 40, 45, 40, 45: stdev 2.9 -> tolerance 3
    windows = [Window(d + timedelta(days=s), d + timedelta(days=s + 6)) for s in starts]
    est = pc.estimate(windows, today=d + timedelta(days=180))
    assert est.median_gap_days == 42.5
    nxt = d + timedelta(days=170 + 42)  # round(42.5) = 42 (banker's rounding)
    assert est.next_from == nxt - timedelta(days=3) and est.next_to == nxt + timedelta(days=9)


# --- synthetic history and the backtest ----------------------------------------------------------


def test_synthetic_history_is_deterministic() -> None:
    a = pc.synthetic_history(
        7, date(2025, 1, 1), date(2026, 6, 30), 42, jitter_days=4, skip_prob=0.2
    )
    b = pc.synthetic_history(
        7, date(2025, 1, 1), date(2026, 6, 30), 42, jitter_days=4, skip_prob=0.2
    )
    c = pc.synthetic_history(
        8, date(2025, 1, 1), date(2026, 6, 30), 42, jitter_days=4, skip_prob=0.2
    )
    assert a == b and a != c
    assert all(w.days == 7 for w in a[:-1]) and a == sorted(a)
    assert pc.irregular_history(
        3, date(2025, 1, 1), date(2026, 1, 1), 10, 90
    ) == pc.irregular_history(3, date(2025, 1, 1), date(2026, 1, 1), 10, 90)


def test_backtest_on_regular_and_irregular_history() -> None:
    start, end = date(2025, 1, 1), date(2026, 6, 30)
    regular = [pc.synthetic_history(s, start, end, 35, jitter_days=1) for s in range(10)]
    r = pc.backtest(regular)
    assert r.predictions > 100 and r.hit_rate is not None and r.hit_rate >= 0.95
    assert r.false_alarm_rate == 0.0 and r.coverage == 1.0
    noise = [pc.irregular_history(s, start, end, 10, 90) for s in range(10)]
    n = pc.backtest(noise)
    assert n.opportunities > 50 and (n.coverage or 0) < 0.15  # the gate abstains on noise
    assert pc.backtest([]).hit_rate is None
    assert set(r.as_dict()) >= {"hit_rate", "false_alarm_rate", "coverage", "predictions"}


def test_backtest_counts_false_alarms() -> None:
    d = date(2026, 1, 1)
    history = every(30, 5, d)
    late = [*history, Window(d + timedelta(days=200), d + timedelta(days=206))]
    r = pc.backtest([late], min_windows=5)
    assert (r.opportunities, r.predictions, r.false_alarms, r.hits) == (1, 1, 1, 0)


# --- from the database ---------------------------------------------------------------------------


def _world(db) -> dict[str, int]:
    db.execute(
        "INSERT INTO taxonomy (id, parent_id, level, name_he) VALUES ('pc', NULL, 1, 'בדיקה')"
    )
    db.execute(
        "INSERT INTO product_type_rules (product_type, critical_keys, soft_keys) VALUES ('pc_coffee', '{}', '{}')"
    )
    cid = db.execute(
        "INSERT INTO canonical_products (taxonomy_id, slug, display_name_he, product_type, base_unit)"
        " VALUES ('pc', 'pc-coffee', 'קפה נמס', 'pc_coffee', '100g') RETURNING id"
    ).fetchone()[0]
    db.execute(
        "INSERT INTO chains (id, name, portal, club_names) VALUES ('pc-a', 'רשת א', 'other', '{}'),"
        " ('pc-b', 'רשת ב', 'other', '{}')"
    )
    ids = {"cid": cid}
    for key, chain, flex, review in (
        ("a1", "pc-a", "exact", False),
        ("a2", "pc-a", "any_brand", False),
        ("b1", "pc-b", "any_brand", False),
        ("b_close", "pc-b", "close", False),
        ("b_review", "pc-b", "any_brand", True),
    ):
        iid = db.execute(
            "INSERT INTO items (chain_id, item_code, raw_name) VALUES (%s, %s, %s) RETURNING id",
            (chain, key, f"קפה {key}"),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
            " needs_review) VALUES (%s, %s, %s, 0.95, 'rule', %s)",
            (iid, cid, flex, review),
        )
        ids[key] = iid
    return ids


@pytest.mark.db
def test_promo_cycles_from_the_promos_table(db) -> None:
    ids = _world(db)
    first = TODAY - timedelta(days=42 * 5 + 10)
    # chain A: a regular six-week promo, published on two items and per store (merged)
    pc.seed_promo_history(db, "pc-a", [ids["a1"], ids["a2"]], every(42, 6, first), prefix="A")
    # chain B: three promos only (two cycles), plus history that must not count
    pc.seed_promo_history(
        db, "pc-b", [ids["b1"]], every(30, 3, TODAY - timedelta(days=80)), prefix="B"
    )
    pc.seed_promo_history(db, "pc-b", [ids["b_close"]], every(10, 8, first), prefix="CLOSE")
    pc.seed_promo_history(db, "pc-b", [ids["b_review"]], every(10, 8, first), prefix="REVIEW")
    pc.seed_promo_history(
        db, "pc-b", [ids["b1"]], every(10, 8, first), prefix="OTHER", reward_type="other"
    )
    fid = db.execute(
        "INSERT INTO file_tracking (sha256, chain_id, kind, status) VALUES (%s, 'pc-b',"
        " 'promo_full', 'quarantined') RETURNING id",
        ("f" * 64,),
    ).fetchone()[0]
    bad = pc.seed_promo_history(db, "pc-b", [ids["b1"]], every(10, 8, first), prefix="QUAR")
    db.execute("UPDATE promos SET file_id = %s WHERE id = ANY(%s)", (fid, bad))
    future = pc.seed_promo_history(
        db,
        "pc-b",
        [ids["b1"]],
        [Window(TODAY + timedelta(days=3), TODAY + timedelta(days=9))],
        prefix="FUT",
    )
    assert future

    rows = pc.promo_cycles(db, ids["cid"], TODAY)
    assert [r.chain_id for r in rows] == ["pc-a", "pc-b"]
    a, b = rows
    assert a.chain_name == "רשת א" and len(a.windows) == 6
    assert a.estimate.cycles_seen == 5 and a.estimate.median_gap_days == 42.0
    assert a.estimate.confidence == round(5 / 6.5, 3) and a.estimate.advice in ("wait", "buy_now")
    assert a.estimate.next_from is not None
    assert len(b.windows) == 3 and b.estimate.cycles_seen == 2 and b.estimate.advice == "unknown"


@pytest.mark.db
def test_club_promos_count_only_for_marked_clubs(db) -> None:
    ids = _world(db)
    first = TODAY - timedelta(days=35 * 5)
    pc.seed_promo_history(
        db,
        "pc-a",
        [ids["a1"]],
        every(35, 6, first),
        prefix="CLUB",
        club_only=True,
        club_name="מועדון הזהב",
    )
    assert pc.promo_cycles(db, ids["cid"], TODAY) == []  # only club promos, no club marked
    marked = pc.promo_cycles(
        db, ids["cid"], TODAY, include_club=lambda club, chain, own: club == "מועדון הזהב"
    )
    assert len(marked) == 1 and marked[0].estimate.cycles_seen == 5


@pytest.mark.db
def test_cli_prints_the_table_and_json(db, monkeypatch) -> None:
    ids = _world(db)
    pc.seed_promo_history(
        db, "pc-a", [ids["a1"]], every(42, 6, TODAY - timedelta(days=42 * 5 + 10))
    )

    @contextmanager
    def same_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", same_connection)
    result = CliRunner().invoke(
        cli.app, ["promo-cycles", "pc-coffee", "--as-of", TODAY.isoformat()]
    )
    assert result.exit_code == 0, result.output
    assert (
        "קפה נמס" in result.output and "רשת א (pc-a)" in result.output and "42 d" in result.output
    )
    assert "gate: at least 3 cycles" in result.output
    out = CliRunner().invoke(
        cli.app, ["promo-cycles", str(ids["cid"]), "--as-of", TODAY.isoformat(), "--json"]
    )
    data = json.loads(out.output)
    assert data["chains"][0]["cycles_seen"] == 5 and data["chains"][0]["windows"] == 6
    missing = CliRunner().invoke(cli.app, ["promo-cycles", "no-such-slug"])
    assert missing.exit_code != 0


def test_cli_synthetic_backtest() -> None:
    result = CliRunner().invoke(cli.app, ["promo-backtest", "--synthetic"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert (
        data["series"] == 80
        and data["predictions"] > 0
        and set(data["by_kind"])
        == {
            "regular, 28 to 49 days, jitter 0 to 2",
            "42 days, jitter 5, 10-day promos",
            "35 days, jitter 3, a quarter of cycles skipped",
            "irregular, gaps 10 to 90 days",
        }
    )
