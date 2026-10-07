"""The smartcart-ingest CLI, through typer's CliRunner against the test database."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import structlog
from typer.testing import CliRunner

from smartcart_ingest import cli
from smartcart_ingest.rawstore import LocalRawStore
from tests.fakes import FakeFetcher, encode, item, price

pytestmark = pytest.mark.db
runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    structlog.reset_defaults()


@pytest.fixture
def wired(db, tmp_path, monkeypatch, database):
    """The CLI wired to the test connection (rolled back after the test), a fake fetcher and a
    local raw store."""
    fetcher = FakeFetcher()

    @contextmanager
    def use_test_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", use_test_connection)
    monkeypatch.setattr(cli, "build_fetcher", lambda settings: fetcher)
    monkeypatch.setattr(cli, "build_rawstore", lambda settings: LocalRawStore(tmp_path))
    monkeypatch.setattr(cli, "register_adapters", lambda: [])
    monkeypatch.setenv("DATABASE_URL", database.dsn)
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    return fetcher


def _now() -> datetime:
    return datetime.now(tz=ZoneInfo("Asia/Jerusalem"))


def _lines(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def _full_and_delta_times() -> tuple[datetime, datetime]:
    """A PriceFull time and a later Price (delta) time on the same Israel calendar day.

    A delta loads only after that day's full file, so the two must not straddle midnight: between
    00:30 and 02:00 Israel time "now - 2 h" would fall on the previous day and the delta would be
    held, which made this test fail in CI at that hour.
    """
    delta_at = _now() - timedelta(minutes=30)
    full_at = delta_at - timedelta(minutes=90)
    if full_at.date() != delta_at.date():
        full_at = min(delta_at.replace(hour=0, minute=1, second=0), delta_at - timedelta(seconds=1))
    return full_at, delta_at


def test_run_full_then_delta_then_status(wired, db) -> None:
    full_at, delta_at = _full_and_delta_times()
    wired.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "5.00", at=full_at)]),
        at=full_at,
    )
    wired.add(
        "price",
        encode(items=[item("A")], prices=[price("A", "1", "4.00", at=delta_at)]),
        at=delta_at,
    )
    result = runner.invoke(cli.app, ["run", "--mode", "full", "--chain", "fake"])
    assert result.exit_code == 0, result.output
    (full,) = _lines(result.stdout)
    assert full["mode"] == "full" and full["chain_id"] == "fake" and full["loaded"] == 1

    result = runner.invoke(cli.app, ["run", "--mode", "delta", "--chain", "fake"])
    assert result.exit_code == 0, result.output
    (delta,) = _lines(result.stdout)
    assert delta["mode"] == "delta" and delta["loaded"] == 1

    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0, result.output
    rows = [line.split() for line in result.stdout.splitlines()]
    assert ["fake", "loaded", "2"] in rows


def test_run_exits_nonzero_when_a_chain_fails(wired, monkeypatch) -> None:
    monkeypatch.setenv("PORTAL_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("PORTAL_MAX_ATTEMPTS", "2")
    wired.list_failures["fake"] = 99
    result = runner.invoke(cli.app, ["run", "--mode", "full", "--chain", "fake"])
    assert result.exit_code == 1
    (rep,) = _lines(result.stdout)
    assert "portal failed" in rep["error"]


def test_status_shows_quarantine_counts(wired) -> None:
    wired.add(
        "price_full",
        encode(items=[item("A")], prices=[price("A", "1", "0")]),
        at=_now() - timedelta(hours=1),
    )
    assert runner.invoke(cli.app, ["run", "--mode", "full", "--chain", "fake"]).exit_code == 0
    out = runner.invoke(cli.app, ["status"]).stdout
    assert "quarantined" in out
    assert any(line.split()[:2] == ["fake", "1"] for line in out.splitlines()[-1:])


def test_status_with_no_files(wired, db) -> None:
    db.execute("DELETE FROM quarantine_events")
    db.execute("DELETE FROM file_tracking")
    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0 and "no files tracked" in result.stdout


def test_default_run_skips_chains_without_an_adapter(wired) -> None:
    result = runner.invoke(cli.app, ["run", "--mode", "full"])
    # Only D13 chains with a registered adapter run; the fake fetcher has no files for them.
    assert result.exit_code == 0, result.output
    assert all(rep["listed"] == 0 and rep["chain_id"] != "fake" for rep in _lines(result.stdout))


def test_mode_is_required_and_checked(wired) -> None:
    assert runner.invoke(cli.app, ["run"]).exit_code != 0
    assert runner.invoke(cli.app, ["run", "--mode", "weekly"]).exit_code != 0


def test_migrate_is_a_no_op_on_a_migrated_database(wired, tmp_path, monkeypatch) -> None:
    # Only the plain-SQL schema file, which the session fixture applied everywhere (the
    # extension files are skipped locally when the server has no PostGIS or pgvector).
    from smartcart_ingest import db as dbmod

    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    schema = next(m for m in dbmod.list_migrations() if m.filename.endswith("_schema_v1.sql"))
    (mig_dir / schema.filename).write_text(schema.read(), encoding="utf-8")
    monkeypatch.setenv("SMARTCART_MIGRATIONS_DIR", str(mig_dir))
    result = runner.invoke(cli.app, ["migrate"])
    assert result.exit_code == 0, result.output
    assert "no pending migrations" in result.stdout
