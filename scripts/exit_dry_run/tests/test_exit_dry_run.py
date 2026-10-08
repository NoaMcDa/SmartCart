"""Tests for the Phase 0 exit dry run (issue #60).

    uv run pytest scripts/exit_dry_run/tests -q

The end-to-end test needs a Postgres server with PostGIS that allows CREATE DATABASE: the ingest
suite's throwaway cluster (or ``DATABASE_URL``) provides it, and the test is skipped when none is
available.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

import dry_run  # noqa: E402
import replay  # noqa: E402

ISRAEL = ZoneInfo("Asia/Jerusalem")


def test_first_pass_that_sees_a_file() -> None:
    at = lambda h, m: datetime(2026, 10, 8, h, m, tzinfo=ISRAEL)  # noqa: E731
    assert dry_run.first_pass_that_sees(at(0, 10)) == "06:00"
    assert dry_run.first_pass_that_sees(at(6, 0)) == "06:00"
    assert dry_run.first_pass_that_sees(at(8, 0)) == "08:30"
    assert dry_run.first_pass_that_sees(at(8, 31)) == "next day 06:00"


def test_markdown_helpers() -> None:
    table = dry_run.md_table(["a", "b"], [["x|y", None], [1, "line\nbreak"]])
    assert table[0] == "| a | b |"
    assert table[2] == "| x\\|y |  |"
    assert table[3] == "| 1 | line break |"
    assert dry_run.demote("# T\ntext\n## S") == "## T\ntext\n### S"
    assert dry_run.pct(7, 10) == "70%" and dry_run.pct(0, 0) == "n/a"


def test_the_real_set_is_stores_and_price_files_of_seven_chains() -> None:
    files = replay.fixture_set("real")
    assert {f.kind for f in files} == {"stores", "price_full"}
    assert len({f.chain_id for f in files}) == 7
    assert all(f.path.parent.name == "real" for f in files)
    assert [f.published_at for f in files] == sorted(f.published_at for f in files)


def test_the_synthetic_set_has_promos_and_all_ten_chains() -> None:
    files = replay.fixture_set("synthetic")
    assert len({f.chain_id for f in files}) == 10
    assert {"stores", "price_full", "promo_full"} <= {f.kind for f in files}
    assert not any(f.path.parent.name == "real" for f in files)
    with pytest.raises(ValueError):
        replay.fixture_set("other")


def test_run_sh_is_executable_and_parses() -> None:
    script = HERE / "run.sh"
    assert script.stat().st_mode & 0o111
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_end_to_end_writes_the_dry_run_and_cleans_up(pg_dsn: str, tmp_path: Path) -> None:
    out = tmp_path / "dry-run.md"
    result = dry_run.run(pg_dsn, out)
    text = out.read_text(encoding="utf-8")
    assert result["real_files"] == result["real_loaded"] == 14

    # the banner and the verdict
    assert text.startswith("# Phase 0 exit dry run")
    assert "**This is not the exit validation.**" in text
    assert "**NO-GO**" in text
    # every section the brief asks for
    for heading in (
        "## 1. What was run", "## 2. The real files", "## 3. The exit report generator",
        "## 4. The synthetic set", "## 5. Which criteria can pass", "## 6. Findings",
        "## 7. What the owner runs on the VPS later", "## 8. Reproduce",
    ):  # fmt: skip
        assert heading in text
    # numbers the databases must have produced
    assert "Ten chains: success rate **70.0%** (7 of 10 chain-days)" in text
    assert "Chains with no loaded full file on the day: Victory, Hazi Hinam, Machsanei Hashuk." in text
    assert "827 physical and 13 online stores, **0 with coordinates**" in text
    assert "**0 stores returned**" in text  # the real basket: no coordinates
    # the synthetic set has what the real one lacks
    assert "Promos parsed for the main chains: 23" in text
    assert "Stores: 27 physical, 24 with coordinates." in text
    # the generator's own output is embedded, not retyped
    assert text.count("<details><summary>Generator output") == 2
    assert "Criterion: above 95.0% over at least 14 days: **not met**" in text
    # the commands for the VPS
    for needle in ("smartcart_ingest.report", "infra/vps/setup.sh", "--only-chains",
                   "systemctl list-timers", "smartcart-ingest status"):  # fmt: skip
        assert needle in text

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        left = [r[0] for r in conn.execute(
            "SELECT datname FROM pg_database WHERE datname LIKE 'exit_dry_run_%'").fetchall()]  # fmt: skip
    assert left == []  # both throwaway databases were dropped


def test_missing_server_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert dry_run.main([]) == 2
