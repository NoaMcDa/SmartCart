"""The whole workflow logic on the committed real fixtures, offline (issue #60).

``run_day.py --from-fixtures`` loads the seven chains' real files through the real Scheduler into a
fresh database, writes the record, and the store and the report read it back. Needs a Postgres
server with PostGIS, pgvector and pg_trgm that allows CREATE DATABASE (``DATABASE_URL`` or the
ingest suite's throwaway cluster); skipped otherwise.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import exit_window_testkit as kit  # noqa: E402
import test_exit_window_report as report_tests  # noqa: E402
import window_record as wr  # noqa: E402
import window_store as ws  # noqa: E402

SCRIPT = HERE.parents[0] / "run_day.py"
REPO = HERE.parents[2]
NEEDED = {"postgis", "vector", "pg_trgm"}


def _database_url(base: str, name: str) -> str:
    return psycopg.conninfo.make_conninfo(base, dbname=name)


@pytest.fixture
def fresh_db(pg_dsn: str):  # noqa: ANN201
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        have = {r[0] for r in conn.execute("SELECT name FROM pg_available_extensions").fetchall()}
        if not NEEDED <= have:
            pytest.skip(f"the server lacks {sorted(NEEDED - have)} (runs in CI)")
        name = f"exit_window_{uuid.uuid4().hex[:10]}"
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield _database_url(pg_dsn, name)
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


def run_day(url: str, work: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": url, "SMARTCART_GEO_DIR": str(work / "no-geo")}
    for key in ("SMARTCART_GEO_LOCALITIES", "SMARTCART_GEO_STORES"):
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--work", str(work), "--out", str(out), "--from-fixtures",
         "--ip-country", "ZZ", *extra],
        capture_output=True, text=True, cwd=REPO, env=env, timeout=600,
    )  # fmt: skip


def test_fixtures_load_with_a_fixed_clock_and_the_record_round_trips(
    fresh_db: str, tmp_path: Path
) -> None:
    out = tmp_path / "record.json"
    # One hour after the last real file was published (Yohananof's PromoFull, 2026-10-22 00:40).
    res = run_day(fresh_db, tmp_path / "work", out, "--now", "2026-10-22T01:40+03:00",
                  "--date", "2026-10-22")  # fmt: skip
    assert res.returncode == 0, res.stderr[-2000:]
    rec = json.loads(out.read_text(encoding="utf-8"))
    wr.validate_record(rec)
    assert rec["date"] == "2026-10-22"
    assert rec["run"]["source"] == "fixtures" and rec["run"]["clock"] == "fixed"
    assert rec["run"]["runner_ip_country"] == "ZZ"

    chains = rec["chains"]
    assert set(chains) == set(kit.SLUGS)
    real = {"shufersal", "ramilevy", "mega", "tivtaam", "osherad", "yohananof", "king_store"}
    for slug, chain in chains.items():
        if slug in real:
            assert chain["loaded"] == 3 and chain["full_loaded"], (slug, chain["failure"])
            assert chain["files"]["price_full"]["items"] == 200  # trimmed fixtures
            assert chain["files"]["promo_full"]["promos"] == 100
            assert chain["files"]["price_full"]["published_at"].endswith(("+03:00", "+02:00"))
        else:  # no real file in the repository for these three
            assert chain["downloaded"] == 0 and not chain["full_loaded"]
            assert "no file" in chain["failure"]
    assert sum(c["full_loaded"] for c in chains.values()) == 7
    assert sum(sum(c["promos_by_reward"].values()) for c in chains.values()) > 0

    # the store accepts it once and keeps it, and the report reads it back
    data = tmp_path / "data"
    assert ws.append_record(data, rec)[0] == ws.ADDED
    assert ws.append_record(data, rec)[0] == ws.EXISTS
    records, problems = ws.load_records(data)
    assert problems == [] and len(records) == 1
    text = report_tests.report.render(records, problems)
    assert "70.0%" in text and "Victory, Hazi Hinam, Machsanei Hashuk" in text


def test_the_real_clock_quarantines_what_is_older_than_the_stale_limit(
    fresh_db: str, tmp_path: Path
) -> None:
    """No clock replay: the fixtures are days old, so the stale-date gate must act on them,
    whatever day this test runs on."""
    out = tmp_path / "record.json"
    res = run_day(fresh_db, tmp_path / "work", out)
    assert res.returncode == 0, res.stderr[-2000:]
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["run"]["clock"] == "real"
    checked = 0
    for chain in rec["chains"].values():
        for kind in wr.FULL_KINDS:
            f = chain["files"][kind]
            if not f["downloaded"]:
                continue
            checked += 1
            if f["age_hours"] > 36.5:  # the limit is 36 h; stay clear of the boundary
                assert f["quarantined"] and f["gates"] == ["stale_date"], (kind, f)
            elif f["age_hours"] < 35.5:
                assert "stale_date" not in f["gates"], (kind, f)
    assert checked == 14
    # a quarantined full file is not a successful load, so a stale day is a failed day
    for chain in rec["chains"].values():
        if all(chain["files"][k]["quarantined"] for k in wr.FULL_KINDS):
            assert not chain["full_loaded"] and "stale_date" in chain["failure"]


def test_a_chain_limit_and_an_unknown_chain(fresh_db: str, tmp_path: Path) -> None:
    out = tmp_path / "record.json"
    res = run_day(fresh_db, tmp_path / "work", out, "--chain", "osherad",
                  "--now", "2026-10-22T01:40+03:00")  # fmt: skip
    assert res.returncode == 0, res.stderr[-2000:]
    assert list(json.loads(out.read_text(encoding="utf-8"))["chains"]) == ["osherad"]
    bad = run_day(fresh_db, tmp_path / "work2", tmp_path / "x.json", "--chain", "nope")
    assert bad.returncode == 2 and "unknown chain" in bad.stderr


def test_no_database_url_is_a_clear_error(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--work", str(tmp_path), "--out", str(tmp_path / "r.json")],
        capture_output=True, text=True, env=env, cwd=REPO,
    )  # fmt: skip
    assert res.returncode == 2 and "DATABASE_URL is not set" in res.stderr
