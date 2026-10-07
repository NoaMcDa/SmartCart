"""beta-report: the closed beta's metrics against the proposed thresholds (issue #40)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
import typer
from test_export_seo import _NoCommit
from typer.testing import CliRunner

from smartcart_catalog import cli_seo
from smartcart_catalog.cli_seo import (
    BETA_THRESHOLDS,
    beta_metrics,
    beta_verdicts,
    render_beta_report,
)

pytestmark = pytest.mark.db


def put(db, name: str, props: dict, session: str = "sess-abcdef12", at: datetime | None = None):
    db.execute(
        "INSERT INTO events (session_id, name, props, created_at) VALUES (%s, %s, %s::jsonb, %s)",
        (session, name, json.dumps(props), at or datetime.now(UTC)),
    )


def seed(db, shown: dict[str, int], rejected: dict[str, int]) -> None:
    for lvl, n in shown.items():
        put(db, "substitutions_shown", {"flex_level": lvl, "count": n})
    for lvl, n in rejected.items():
        for _ in range(n):
            put(db, "substitution_verdict", {"flex_level": lvl, "verdict": "not_good"})


def status(rows, label: str) -> str:
    return next(r[3] for r in rows if r[0] == label)


def test_rejection_rate_gate_passes_fails_and_is_inconclusive_by_level(db) -> None:
    seed(db, {"any_brand": 200, "close": 100, "exact": 50}, {"any_brand": 8, "close": 20})
    rows = beta_verdicts(beta_metrics(db))
    assert status(rows, "rejection rate, any_brand") == "pass"  # 4.0% <= 5%
    assert status(rows, "rejection rate, close") == "fail"  # 20% > 15%
    assert status(rows, "rejection rate, exact") == "inconclusive"  # 50 shown < 100
    text = render_beta_report(beta_metrics(db), None, date(2026, 10, 20))
    assert "| rejection rate, any_brand | 4.0% (8 of 200) | <= 5% | pass | yes |" in text
    assert "NOT MET" in text


def test_everything_within_thresholds_is_met(db) -> None:
    seed(db, {"any_brand": 300, "close": 150, "exact": 120}, {"any_brand": 6, "close": 10})
    text = render_beta_report(beta_metrics(db), None, date(2026, 10, 20))
    assert "MET: every rejection rate" in text and "NOT MET" not in text


def test_too_few_substitutions_shown_is_inconclusive_not_a_pass(db) -> None:
    seed(db, {"any_brand": 20}, {})
    assert "INCONCLUSIVE" in render_beta_report(beta_metrics(db), None, date(2026, 10, 20))


def test_window_starts_at_since(db) -> None:
    old = datetime(2026, 9, 1, tzinfo=UTC)
    put(db, "substitutions_shown", {"flex_level": "close", "count": 500}, at=old)
    put(db, "substitution_verdict", {"flex_level": "close", "verdict": "not_good"}, at=old)
    put(db, "substitutions_shown", {"flex_level": "close", "count": 10})
    m = beta_metrics(db, since=date(2026, 10, 1))
    assert m["rejection"]["close"] == {"shown": 10, "rejected": 0}
    assert beta_metrics(db)["rejection"]["close"] == {"shown": 510, "rejected": 1}


def test_paste_to_results_and_return_visits(db) -> None:
    for i in range(40):
        put(db, "results_shown", {"duration_ms": 1000 + i * 100})  # median 2.95 s, p90 4.51 s
    rows = beta_verdicts(beta_metrics(db))
    assert status(rows, "paste to results, median") == "pass"
    assert status(rows, "paste to results, p90") == "pass"
    for _ in range(40):
        put(db, "results_shown", {"duration_ms": 30_000})
    assert status(beta_verdicts(beta_metrics(db)), "paste to results, median") == "fail"

    # last complete week: 2 of 3 active users had first opened earlier
    last_monday = date.today() - timedelta(days=date.today().weekday() + 7)
    before = datetime.combine(last_monday - timedelta(days=3), datetime.min.time(), UTC)
    during = datetime.combine(last_monday + timedelta(days=1), datetime.min.time(), UTC)
    for s in ("anon-a-123456", "anon-b-123456"):
        put(db, "app_opened", {}, session=s, at=before)
        put(db, "app_opened", {}, session=s, at=during)
    put(db, "app_opened", {}, session="anon-c-123456", at=during)
    m = beta_metrics(db)
    assert m["returning"]["active_users"] == 3 and m["returning"]["returning_users"] == 2
    assert status(beta_verdicts(m), "return visits") == "pass"  # 67% >= 40%


def test_no_events_means_inconclusive_everywhere(db) -> None:
    rows = beta_verdicts(beta_metrics(db))
    assert {r[3] for r in rows} == {"inconclusive"}


def test_cli_prints_writes_and_can_fail_the_gate(db, monkeypatch, tmp_path) -> None:
    seed(db, {"any_brand": 200, "close": 100, "exact": 100}, {"close": 40})

    @contextmanager
    def fake_connect():
        yield _NoCommit(db)

    monkeypatch.setattr(cli_seo, "_connect", fake_connect)
    app = typer.Typer()
    cli_seo.register(app)
    out = tmp_path / "beta.md"
    r = CliRunner().invoke(app, ["beta-report", "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert "NOT MET" in out.read_text(encoding="utf-8")
    assert CliRunner().invoke(app, ["beta-report", "--fail-on-miss"]).exit_code == 1


def test_thresholds_are_the_documented_proposals() -> None:
    assert BETA_THRESHOLDS["rejection_rate"] == {"exact": 0.02, "any_brand": 0.05, "close": 0.15}
    assert BETA_THRESHOLDS["min_shown"] == 100
