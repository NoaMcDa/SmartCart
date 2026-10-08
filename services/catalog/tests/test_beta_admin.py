"""beta-invite, beta-feedback and the by-segment part of beta-report (issue #40)."""

from __future__ import annotations

import json
import re
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta

import pytest
from test_export_seo import _NoCommit
from typer.testing import CliRunner

from smartcart_catalog import beta_admin, cli, cli_seo
from smartcart_catalog.beta_admin import (
    CODE_ALPHABET,
    SEGMENTS,
    create_invites,
    join_link,
    new_code,
    render_segment_section,
    segment_metrics,
    web_origin,
)
from smartcart_catalog.cli_seo import BETA_THRESHOLDS, beta_metrics, render_beta_report

pytestmark = pytest.mark.db

CODE_RE = re.compile(r"^[A-Z0-9]{5}-[A-Z0-9]{5}$")


@pytest.fixture
def connect(db, monkeypatch):
    @contextmanager
    def fake_connect():
        yield _NoCommit(db)

    monkeypatch.setattr(cli_seo, "_connect", fake_connect)


def member(db, code: str, segment: str) -> uuid.UUID:
    uid = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (uid,))
    db.execute(
        "INSERT INTO beta_invites (code, segment, max_uses) VALUES (%s, %s, 5)"
        " ON CONFLICT DO NOTHING",
        (code, segment),
    )
    db.execute("INSERT INTO beta_members (user_id, code, segment) VALUES (%s, %s, %s)",
               (uid, code, segment))
    return uid


def put(db, user, name: str, props: dict, at: datetime | None = None) -> None:
    db.execute(
        "INSERT INTO events (user_id, session_id, name, props, created_at)"
        " VALUES (%s, 'sess-abcdef12', %s, %s::jsonb, %s)",
        (user, name, json.dumps(props), at or datetime.now(UTC)),
    )


# --- invitations -----------------------------------------------------------------------------


def test_codes_are_unambiguous_and_well_formed() -> None:
    codes = {new_code() for _ in range(200)}
    assert len(codes) == 200 and all(CODE_RE.match(c) for c in codes)
    assert not set("01IO") & set(CODE_ALPHABET)


def test_web_origin_prefers_the_option_then_the_environment(monkeypatch) -> None:
    monkeypatch.delenv("API_PUBLIC_WEB_URL", raising=False)
    monkeypatch.delenv("API_CORS_ORIGINS", raising=False)
    assert web_origin() == "http://localhost:3000"
    monkeypatch.setenv("API_CORS_ORIGINS", "https://a.example/, https://b.example")
    assert web_origin() == "https://a.example"
    monkeypatch.setenv("API_PUBLIC_WEB_URL", "https://smartcart.example/")
    assert web_origin() == "https://smartcart.example"
    assert web_origin("https://x.example/") == "https://x.example"
    assert join_link("https://x.example/", "ABCDE-FGHJK") == "https://x.example/beta/join/ABCDE-FGHJK"


def test_beta_invite_prints_codes_and_links_and_stores_them(db, connect, monkeypatch) -> None:
    monkeypatch.setenv("API_PUBLIC_WEB_URL", "https://smartcart.example")
    r = CliRunner().invoke(
        cli.app, ["beta-invite", "--segment", "kosher", "--count", "20", "--max-uses", "1"]
    )
    assert r.exit_code == 0, r.output
    lines = [ln for ln in r.stdout.splitlines() if "\t" in ln]
    assert len(lines) == 20
    for line in lines:
        code, link = line.split("\t")
        assert CODE_RE.match(code) and link == f"https://smartcart.example/beta/join/{code}"
    rows = db.execute(
        "SELECT segment, max_uses, uses, expires_at FROM beta_invites ORDER BY code"
    ).fetchall()
    assert len(rows) == 20 and {r[:3] for r in rows} == {("kosher", 1, 0)}
    days = (rows[0][3] - datetime.now(UTC)).days
    assert 58 <= days <= 60  # the default expiry


def test_beta_invite_options(db, connect) -> None:
    r = CliRunner().invoke(
        cli.app,
        ["beta-invite", "--segment", "periphery", "--count", "2", "--max-uses", "4",
         "--expires-days", "0", "--web-url", "https://w.example"],
    )  # fmt: skip
    assert r.exit_code == 0, r.output
    assert db.execute("SELECT max_uses, expires_at FROM beta_invites").fetchall() == [
        (4, None), (4, None)]
    assert "https://w.example/beta/join/" in r.stdout
    bad = CliRunner().invoke(cli.app, ["beta-invite", "--segment", "everyone"])
    assert bad.exit_code != 0


def test_create_invites_redraws_a_collision(db, monkeypatch) -> None:
    db.execute("INSERT INTO beta_invites (code, segment) VALUES ('AAAAA-AAAAA', 'general')")
    draws = iter(["AAAAA-AAAAA", "AAAAA-AAAAA", "BBBBB-BBBBB"])
    monkeypatch.setattr(beta_admin, "new_code", lambda: next(draws))
    assert create_invites(db, "general", 1, 1, None) == ["BBBBB-BBBBB"]


# --- feedback --------------------------------------------------------------------------------


def test_beta_feedback_lists_text_with_segment_and_average(db, connect) -> None:
    old = datetime(2026, 9, 1, tzinfo=UTC)
    for seg, rating, body, at in [
        ("kosher", 5, "מצוין\nממש", None),
        ("kosher", 3, "", None),
        ("periphery", 1, "התחליף לא נכון", None),
        ("general", 4, "ישן", old),
    ]:
        db.execute(
            "INSERT INTO beta_feedback (segment, rating, body, created_at)"
            " VALUES (%s, %s, %s, coalesce(%s, now()))", (seg, rating, body, at))
    r = CliRunner().invoke(cli.app, ["beta-feedback", "--since", "2026-10-01"])
    assert r.exit_code == 0, r.output
    assert "kosher: 4.0 (n=2)" in r.stdout and "periphery: 1.0 (n=1)" in r.stdout
    assert "ישן" not in r.stdout and "general" not in r.stdout.split("\n\n")[0]
    assert "    מצוין\n    ממש" in r.stdout
    only = CliRunner().invoke(cli.app, ["beta-feedback", "--segment", "periphery"])
    assert "התחליף לא נכון" in only.stdout and "מצוין" not in only.stdout
    empty = CliRunner().invoke(cli.app, ["beta-feedback", "--since", "2030-01-01"])
    assert "No feedback in this window." in empty.stdout


# --- the report by segment --------------------------------------------------------------------


def seed_two_segments(db) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    k = member(db, "KOSH-11111", "kosher")
    p = member(db, "PERI-11111", "periphery")
    outsider = uuid.uuid4()
    db.execute("INSERT INTO auth.users (id) VALUES (%s)", (outsider,))
    put(db, k, "substitutions_shown", {"flex_level": "any_brand", "count": 120})
    for _ in range(12):
        put(db, k, "substitution_verdict", {"flex_level": "any_brand", "verdict": "not_good"})
    put(db, p, "substitutions_shown", {"flex_level": "any_brand", "count": 30})
    put(db, p, "substitution_verdict", {"flex_level": "any_brand", "verdict": "not_good"})
    put(db, outsider, "substitutions_shown", {"flex_level": "any_brand", "count": 500})
    for ms in (2000, 4000, 6000):
        put(db, k, "results_shown", {"duration_ms": ms})
    put(db, p, "results_shown", {"duration_ms": 9000})
    put(db, k, "app_opened", {})
    put(db, p, "app_opened", {})
    return k, p, outsider


def test_segment_metrics_split_by_segment_with_sample_sizes(db) -> None:
    seed_two_segments(db)
    m = segment_metrics(db)
    assert list(m) == list(SEGMENTS)  # every segment is present, even an empty one
    assert m["kosher"]["rejection"]["any_brand"] == {"shown": 120, "users": 1, "rejected": 12}
    assert m["periphery"]["rejection"]["any_brand"] == {"shown": 30, "users": 1, "rejected": 1}
    assert m["large_family"]["rejection"]["close"] == {"shown": 0, "users": 0, "rejected": 0}
    assert m["kosher"]["paste_to_results"] == {
        "results": 3, "users": 1, "median_ms": 4000.0, "p90_ms": 5600.0}  # fmt: skip
    assert (m["kosher"]["joined"], m["kosher"]["active"], m["kosher"]["places"]) == (1, 1, 5)
    # The outsider (not a member) is in the overall numbers and in no segment.
    assert beta_metrics(db)["rejection"]["any_brand"]["shown"] == 650
    assert sum(s["rejection"]["any_brand"]["shown"] for s in m.values()) == 150


def test_window_applies_to_the_segment_numbers(db) -> None:
    k = member(db, "KOSH-11111", "kosher")
    put(db, k, "substitutions_shown", {"flex_level": "close", "count": 400},
        at=datetime(2026, 9, 1, tzinfo=UTC))
    put(db, k, "substitutions_shown", {"flex_level": "close", "count": 7})
    assert segment_metrics(db, date(2026, 10, 1))["kosher"]["rejection"]["close"]["shown"] == 7
    assert segment_metrics(db)["kosher"]["rejection"]["close"]["shown"] == 407


def test_section_shows_n_rates_and_flags_small_samples(db) -> None:
    seed_two_segments(db)
    text = render_segment_section(segment_metrics(db))
    assert "| kosher | any_brand | 120 | 12 | 10.0% | 1 | ok |" in text
    assert "| periphery | any_brand | 30 | 1 | 3.3% | 1 | small (<100) |" in text
    assert "| large_family | close | 0 | 0 | - | 0 | none |" in text
    assert "| kosher | 3 | 1 | 4.0 s | 5.6 s | small (<30) |" in text
    assert "| kosher (kosher-conscious) | 1 | 5 | 1 | 1 |" in text
    assert "Joined in total: 2" in text
    # No verdict wording per segment: the thresholds stay the owner's, on the overall rates.
    assert "pass" not in text and "fail" not in text and "NOT MET" not in text


def test_the_cli_report_keeps_the_overall_part_and_adds_the_segments(db, connect, tmp_path) -> None:
    seed_two_segments(db)
    base = render_beta_report(beta_metrics(db), None, datetime.now(UTC).date())
    names = [c.name for c in cli.app.registered_commands]
    assert names.count("beta-report") == 1  # replaced, not duplicated
    out = tmp_path / "beta.md"
    r = CliRunner().invoke(cli.app, ["beta-report", "--out", str(out)])
    assert r.exit_code == 0, r.output
    text = out.read_text(encoding="utf-8")
    assert text.startswith(base.rstrip("\n"))
    assert "## By segment" in text and "### Substitution rejection rate by segment" in text
    # any_brand overall: 13 of 650 shown = 2%, a pass at the unchanged 5% threshold
    assert "| rejection rate, any_brand | 2.0% (13 of 650) | <= 5% | pass | yes |" in text
    printed = CliRunner().invoke(cli.app, ["beta-report"])
    assert "## By segment" in printed.stdout
    assert CliRunner().invoke(cli.app, ["beta-report", "--fail-on-miss"]).exit_code == 1
    # exact and close have too few shown, so the gate is inconclusive and --fail-on-miss fails


def test_the_proposed_thresholds_are_untouched() -> None:
    assert BETA_THRESHOLDS["rejection_rate"] == {"exact": 0.02, "any_brand": 0.05, "close": 0.15}
    assert BETA_THRESHOLDS["min_shown"] == 100 and BETA_THRESHOLDS["min_results"] == 30


def test_active_counts_only_members_who_opened_in_the_window(db) -> None:
    k = member(db, "KOSH-11111", "kosher")
    put(db, k, "app_opened", {}, at=datetime.now(UTC) - timedelta(days=40))
    assert segment_metrics(db)["kosher"]["active"] == 1
    assert segment_metrics(db, date.today() - timedelta(days=7))["kosher"]["active"] == 0
