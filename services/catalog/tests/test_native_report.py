"""Native-app decision metrics (issue #56): the views of migration 20261011100300_retention.sql and
`smartcart-catalog native-report`, on seeded events with hand-computed answers."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from test_match_seed import seed_catalog
from typer.testing import CliRunner

from smartcart_catalog import cli_growth
from smartcart_catalog.cli import app
from smartcart_catalog.cli_growth import (
    NATIVE_CRITERIA,
    native_metrics,
    native_outcome,
    native_verdicts,
    render_native_report,
)

ON_DAY = (
    "((now() AT TIME ZONE 'Asia/Jerusalem')::date - %(ago)s + time '12:00')"
    " AT TIME ZONE 'Asia/Jerusalem'"
)


def ev(
    db, name: str, session: str, ago: int, props: dict | None = None, *, user=None, n: int = 1
) -> None:
    """``n`` events at noon, Israel time, ``ago`` days before today."""
    from psycopg.types.json import Jsonb

    for _ in range(n):
        db.execute(
            "INSERT INTO events (user_id, session_id, name, props, created_at)"
            f" VALUES (%(user)s, %(session)s, %(name)s, %(props)s, {ON_DAY})",
            {
                "user": user,
                "session": session,
                "name": name,
                "props": Jsonb(props or {}),
                "ago": ago,
            },
        )


@pytest.fixture
def seeded(db):
    """Cohort X (first opened 40 days ago, 7 actors) and a young cohort (opened yesterday, 4).

    X: a1 returns on day 1, 7 and 30; a2 on day 1; a3 on day 7; a4 never; a5 on day 30; a6 never;
    u1 is one signed-in user on two browsers who returns on day 1.
    Yesterday (D): b1 to b4 open the app and do the things the views count.
    """
    ses = lambda name: f"sess-{name}-0001"  # noqa: E731
    for name, back in (("a1", (1, 7, 30)), ("a2", (1,)), ("a3", (7,)), ("a4", ()), ("a5", (30,)),
                       ("a6", ())):  # fmt: skip
        ev(db, "app_opened", ses(name), 40)
        for d in back:
            ev(db, "app_opened", ses(name), 40 - d)
    user = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (user,))
    ev(db, "app_opened", ses("u1a"), 40, user=user)
    ev(db, "app_opened", ses("u1b"), 39, user=user)  # another browser, same user: the same actor
    for b in ("b1", "b2", "b3", "b4"):
        ev(db, "app_opened", ses(b), 1, {"surface": "pwa"})
    ev(db, "pwa_installed", ses("b1"), 1, {"platform": "ios"}, n=2)
    ev(db, "pwa_installed", ses("b2"), 1, {"platform": "android"})
    ev(db, "pwa_installed", ses("b3"), 1)  # no platform
    ev(db, "push_opt_in", ses("b1"), 1, {"platform": "ios"})
    ev(db, "push_opt_in", ses("b2"), 1, {"platform": "android"})
    ev(db, "push_opened", ses("b1"), 1, {"platform": "ios"}, n=3)
    ev(db, "store_mode_used", ses("b1"), 1, {"plan": "single", "platform": "ios"}, n=2)
    ev(db, "store_mode_used", ses("b2"), 1, {"plan": "split", "platform": "android"})
    ev(db, "store_mode_used", ses("b4"), 1, {"plan": "single", "platform": "ios"})
    ev(db, "scan_started", ses("b1"), 1, {"engine": "zxing"}, n=5)
    ev(db, "scan_completed", ses("b1"), 1, {"outcome": "found"}, n=3)
    ev(db, "scan_completed", ses("b1"), 1, {"outcome": "not_found"})
    ev(db, "scan_completed", ses("b1"), 1, {"outcome": "cancelled"})
    # ten pushes delivered yesterday, and two log-only deliveries that are not pushes
    canon = seed_catalog(db)["t-milk-3"]
    alert = db.execute("INSERT INTO price_alerts (user_id, canonical_id, threshold_unit_price)"
                       " VALUES (%s, %s, 1) RETURNING id", (user, canon)).fetchone()[0]  # fmt: skip
    for channel, n in (("push", 10), ("log", 2)):
        for _ in range(n):
            db.execute(
                "INSERT INTO alert_deliveries (alert_id, unit_price, channel, delivered_at)"
                f" VALUES (%(a)s, 1, %(c)s, {ON_DAY})", {"a": alert, "c": channel, "ago": 1})  # fmt: skip
    return db


def week_of(db, ago: int) -> str:
    return db.execute("SELECT date_trunc('week', (now() AT TIME ZONE 'Asia/Jerusalem')::date - %s)::date",
                      (ago,)).fetchone()[0]  # fmt: skip


@pytest.mark.db
def test_cohort_retention_view(seeded) -> None:
    rows = {r[0]: r for r in seeded.execute(
        "SELECT cohort_week, cohort_size, d1_eligible, d1_retained, d1_rate, d7_eligible,"
        " d7_retained, d7_rate, d30_eligible, d30_retained, d30_rate FROM native_cohort_retention"
    ).fetchall()}  # fmt: skip
    x = rows[week_of(seeded, 40)]
    assert x[1:4] == (7, 7, 3)  # size 7; D1 retained: a1, a2 and the user on two browsers
    assert float(x[4]) == pytest.approx(3 / 7, abs=1e-4)
    assert x[5:7] == (7, 2) and float(x[7]) == pytest.approx(2 / 7, abs=1e-4)  # a1, a3
    assert x[8:10] == (7, 2) and float(x[10]) == pytest.approx(2 / 7, abs=1e-4)  # a1, a5
    young = rows[week_of(seeded, 1)]
    # first opened yesterday: day 1 is today and not over, so nobody is eligible yet; no rate, not 0
    assert young[1:4] == (4, 0, 0) and young[4] is None
    assert young[5] == 0 and young[7] is None and young[8] == 0 and young[10] is None


@pytest.mark.db
def test_installs_by_platform_view(seeded) -> None:
    w = week_of(seeded, 1)
    rows = {r[0]: r[1:] for r in seeded.execute(
        "SELECT platform, installs, installers, active_users, installers_per_active_user"
        " FROM native_installs_by_platform WHERE week = %s", (w,)).fetchall()}  # fmt: skip
    assert set(rows) == {"ios", "android", "unknown"}
    assert rows["ios"][:3] == (2, 1, 4) and rows["android"][:3] == (1, 1, 4)
    assert float(rows["ios"][3]) == 0.25  # one installer of four active actors


@pytest.mark.db
def test_push_view_counts_pushes_not_log_deliveries(seeded) -> None:
    w = week_of(seeded, 1)
    row = seeded.execute(
        "SELECT active_users, opt_in_users, opt_in_events, opt_in_rate, pushes_sent, push_opened,"
        " push_open_rate FROM native_push_engagement WHERE week = %s", (w,)).fetchone()  # fmt: skip
    assert row[:3] == (4, 2, 2) and float(row[3]) == 0.5
    assert row[4:6] == (10, 3) and float(row[6]) == 0.3


@pytest.mark.db
def test_store_mode_view(seeded) -> None:
    w = week_of(seeded, 1)
    row = seeded.execute(
        "SELECT active_users, store_mode_users, store_mode_events, single_events, split_events,"
        " store_mode_user_share, events_per_store_mode_user FROM native_store_mode_usage"
        " WHERE week = %s", (w,)).fetchone()  # fmt: skip
    assert row[:5] == (4, 3, 4, 3, 1)
    assert float(row[5]) == 0.75 and float(row[6]) == 1.33
    # a week with active users and no store-mode use is listed with zero, not left out
    other = seeded.execute("SELECT store_mode_users, store_mode_user_share FROM native_store_mode_usage"
                           " WHERE week = %s", (week_of(seeded, 40),)).fetchone()  # fmt: skip
    assert other[0] == 0 and float(other[1]) == 0.0


@pytest.mark.db
def test_platform_funnel_view(seeded) -> None:
    rows = {r[0]: r[1:] for r in seeded.execute(
        "SELECT platform, actors_seen, installers, push_opt_in_users, push_opened_users,"
        " store_mode_users, installed_share, not_installed_share FROM native_platform_funnel"
    ).fetchall()}  # fmt: skip
    # ios: b1 (installed, push, store mode) and b4 (store mode only, never installed)
    assert rows["ios"][:5] == (2, 1, 1, 1, 2)
    assert float(rows["ios"][5]) == 0.5 and float(rows["ios"][6]) == 0.5
    assert rows["android"][:5] == (1, 1, 1, 0, 1) and float(rows["android"][6]) == 0.0
    assert rows["unknown"][:2] == (1, 1)


@pytest.mark.db
def test_views_are_not_readable_by_the_data_api_roles(db) -> None:
    for role in ("anon", "authenticated"):
        if db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone() is None:
            continue
        for view in ("native_cohort_retention", "native_push_engagement", "native_platform_funnel"):
            assert not db.execute(
                "SELECT has_table_privilege(%s, %s, 'SELECT')", (role, view)
            ).fetchone()[0]


@pytest.mark.db
def test_metrics_pool_the_window_with_sample_sizes(seeded) -> None:
    m = native_metrics(seeded, weeks=12)
    r = m["retention"]
    assert r["users"] == 11
    assert (r["d1"]["retained"], r["d1"]["eligible"]) == (3, 7)
    assert (r["d7"]["retained"], r["d7"]["eligible"]) == (2, 7)
    assert (r["d30"]["retained"], r["d30"]["eligible"]) == (2, 7)
    assert m["push"]["sent"] == 10 and m["push"]["opened"] == 3 and m["push"]["open_rate"] == 0.3
    expected_user_weeks = seeded.execute(
        "SELECT count(*) FROM (SELECT DISTINCT week, actor FROM native_events"
        " WHERE name = 'app_opened') x").fetchone()[0]  # fmt: skip
    assert m["store_mode"]["user_weeks"] == expected_user_weeks
    assert m["store_mode"]["store_mode_user_weeks"] == 3
    assert m["scans"] == {"started": 5, "completed": 4, "found": 3, "success_rate": 0.75}
    assert (
        m["ios"]["actors"] == 2
        and m["ios"]["share"] == 0.5
        and m["ios"]["not_installed_share"] == 0.5
    )
    assert {p["platform"]: (p["installs"], p["installers"]) for p in m["installs"]} == {
        "android": (1, 1),
        "ios": (2, 1),
        "unknown": (1, 1),
    }


@pytest.mark.db
def test_verdicts_need_their_minimum_sample(seeded) -> None:
    m = native_metrics(seeded, weeks=12)
    rows = native_verdicts(m)  # the real minimums (100 users and so on): nothing is conclusive
    assert {r["status"] for r in rows} == {"inconclusive"}
    assert native_outcome(rows)[0] == "inconclusive"
    small = {**NATIVE_CRITERIA, "d30_min_eligible": 5, "ios_min_actors": 3,
             "ios_not_installed_min_actors": 2, "push_min_sent": 10, "store_mode_min_user_weeks": 3,
             "scan_min_completed": 4, "store_mode_share": 0.9}  # fmt: skip
    rows = {r["criterion"][:2]: r for r in native_verdicts(m, small)}
    assert rows["C1"]["status"] == "met" and rows["C1"]["observed"] == "28.6%"  # 2/7 >= 15%
    assert rows["C2"]["status"] == "met"  # 2 of 4 platform-tagged actors are iOS >= 30%
    assert rows["C3"]["status"] == "met"  # 50% never installed >= 50%
    assert rows["C4"]["status"] == "met"  # 30% >= 15%
    assert rows["C5"]["status"] == "not_met"  # at most 3 of 4 or more active user-weeks, under 90%
    assert rows["C6"]["status"] == "not_met"  # 75% < 80%
    outcome, why = native_outcome(list(rows.values()))
    assert outcome == "evaluate_capacitor" and "Capacitor" in why


def row(status_by_id: dict[str, str]) -> list[dict]:
    return [{"criterion": f"{k} x", "status": v} for k, v in status_by_id.items()]


def test_outcome_rules() -> None:
    base = dict.fromkeys(("C1", "C2", "C3", "C4", "C5", "C6"), "met")
    assert native_outcome(row(base))[0] == "evaluate_capacitor"
    assert native_outcome(row({**base, "C1": "not_met"}))[0] == "stay_pwa"
    assert native_outcome(row({**base, "C1": "inconclusive"}))[0] == "inconclusive"
    assert native_outcome(row({**base, "C3": "not_met"}))[0] == "stay_pwa_fix_gaps"
    assert native_outcome(row({**base, "C4": "inconclusive"}))[0] == "inconclusive"
    assert (
        native_outcome(row({**base, "C3": "not_met", "C4": "inconclusive"}))[0]
        == "stay_pwa_fix_gaps"
    )
    # React Native is never the outcome of these numbers alone
    for c1 in ("met", "not_met", "inconclusive"):
        for c6 in ("met", "not_met", "inconclusive"):
            assert native_outcome(row({**base, "C1": c1, "C6": c6}))[0] != "react_native"


@pytest.mark.db
def test_report_text_and_command(seeded, monkeypatch) -> None:
    text = render_native_report(native_metrics(seeded, weeks=12), datetime(2026, 10, 9, tzinfo=UTC))
    assert "# Native-app decision report, 2026-10-09" in text
    assert "| **pooled** | 11 |" in text
    assert "3/7" in text and "2/7" in text
    assert "| ios | 2 | 1 | 1 | 2 | 50.0% |" in text
    assert "D15 criteria against the numbers" in text and "inconclusive" in text
    assert "10" in text and "30.0%" in text  # pushes opened over sent
    assert "estimates, not research facts" in text

    @contextmanager
    def _connect():
        yield seeded

    monkeypatch.setattr(cli_growth, "_connect", _connect)
    result = CliRunner().invoke(app, ["native-report", "--weeks", "12"])
    assert result.exit_code == 0, result.output
    assert "Outcome by the D15 rules: inconclusive." in result.output


@pytest.mark.db
def test_empty_database_reports_no_data_not_zero_rates(db, monkeypatch) -> None:
    m = native_metrics(db, weeks=12)
    assert m["retention"]["d30"]["rate"] is None and m["push"]["open_rate"] is None
    assert m["store_mode"]["share"] is None and m["scans"]["success_rate"] is None
    text = render_native_report(m, datetime(2026, 10, 9, tzinfo=UTC))
    assert "n/a" in text and "(none yet)" in text
