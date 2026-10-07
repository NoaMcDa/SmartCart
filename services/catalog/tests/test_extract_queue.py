"""The extraction queue with the rule extractor, and the CLI commands around it (issue #25)."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

import psycopg
import pytest
from typer.testing import CliRunner

from smartcart_catalog import cli
from smartcart_catalog.extract.base import attrs_json, trusted_verified_keys
from smartcart_catalog.extract.queue import count_pending, run_extraction, write_result
from smartcart_catalog.extract.rule import RuleExtractor
from smartcart_catalog.models import Attributes

NAMES = [
    "חלב תנובה 3% בקרטון 1 ליטר",
    'מצות כשר לפסח בד"ץ 1 ק"ג',
    "משקה סויה טבעוני 1 ליטר",
    "עגבניות",
    "מוצר לא מוכר",
]


def _seed(db: psycopg.Connection) -> list[int]:
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('7290027600007', 'שופרסל', 'other')")
    db.execute("INSERT INTO chains (id, name, portal) VALUES ('7290058140886', 'רמי לוי', 'other')")
    ids = []
    for n, name in enumerate(NAMES):
        chain = "7290058140886" if n == len(NAMES) - 1 else "7290027600007"
        ids.append(db.execute(
            "INSERT INTO items (chain_id, item_code, raw_name, quantity, unit, is_weighed)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (chain, f"72900{n:05d}", name, 1 if n == 3 else None, "קילוגרם" if n == 3 else None,
             n == 3),
        ).fetchone()[0])
    return ids


@pytest.fixture(scope="module")
def rx() -> RuleExtractor:
    return RuleExtractor()


def test_only_humans_verify() -> None:
    assert trusted_verified_keys(["kosher", "fat_pct"], "rule") == []
    assert trusted_verified_keys(["kosher", "fat_pct"], "claude") == []
    assert trusted_verified_keys(["kosher", "fat_pct"], "human") == ["fat_pct", "kosher"]


def test_attrs_json_keeps_set_values_as_numbers() -> None:
    a = Attributes(product_type="milk", fat_pct=Decimal("1.5"), pack_size=Decimal(1000),
                   diet_flags=("vegan",), confidence=0.5, verified_keys=("fat_pct",))
    assert attrs_json(a) == (
        '{"diet_flags": ["vegan"], "fat_pct": 1.5, "pack_size": 1000, "product_type": "milk"}'
    )


@pytest.mark.db
@pytest.mark.pgvector
def test_each_item_is_processed_once(db, rx) -> None:
    ids = _seed(db)
    assert count_pending(db) == len(NAMES)
    run = run_extraction(db, rx, batch_size=2)
    assert (run.items, run.ok, run.retry, run.failed) == (len(NAMES), len(NAMES), 0, 0)
    assert count_pending(db) == 0
    again = run_extraction(db, rx, batch_size=2)
    assert again.items == 0

    rows = {r[0]: r[1:] for r in db.execute(
        "SELECT item_id, status, attrs, verified_keys, extractor, model, confidence"
        " FROM item_attributes").fetchall()}
    milk = rows[ids[0]]
    assert milk[0] == "ok" and milk[3:5] == ("rule", None)
    assert milk[1]["product_type"] == "milk" and milk[1]["fat_pct"] == 3
    matzah = rows[ids[1]]
    assert matzah[1]["kosher"] == "כשר לפסח" and matzah[2] == []
    assert rows[ids[2]][1]["diet_flags"] == ["vegan"] and rows[ids[2]][2] == []
    assert "pack_size" not in rows[ids[3]][1]  # weighed
    assert all(r[2] == [] for r in rows.values())
    assert all(Decimal(0) < r[5] <= Decimal("0.8") for r in rows.values())

    runs = db.execute("SELECT kind, metrics FROM match_runs WHERE kind = 'extract'").fetchall()
    assert len(runs) == 1 and runs[0][1]["items"] == len(NAMES)  # the empty re-run is not logged


@pytest.mark.db
@pytest.mark.pgvector
def test_chain_filter_and_limit(db, rx) -> None:
    _seed(db)
    assert run_extraction(db, rx, chain="7290058140886").items == 1
    assert run_extraction(db, rx, limit=2, batch_size=10).items == 2
    assert count_pending(db) == len(NAMES) - 3


@pytest.mark.db
@pytest.mark.pgvector
def test_ok_rows_are_not_overwritten(db, rx) -> None:
    ids = _seed(db)
    run_extraction(db, rx)
    write_result(db, ids[0], Attributes(product_type="cola"), extractor="rule", model=None,
                 attempts=0, max_attempts=3)
    assert db.execute("SELECT attrs->>'product_type' FROM item_attributes WHERE item_id = %s",
                      (ids[0],)).fetchone()[0] == "milk"


def test_human_source_is_refused(rx) -> None:
    class Human:
        name = "human"
        model = None

        def extract(self, items):
            return []

    with pytest.raises(ValueError, match="review UI"):
        run_extraction(None, Human())  # type: ignore[arg-type]


# --- CLI ---------------------------------------------------------------------------------------------


@pytest.fixture
def cli_db(db, monkeypatch):
    @contextmanager
    def same_connection(settings):
        yield db

    monkeypatch.setattr(cli, "open_connection", same_connection)
    monkeypatch.setattr(db, "commit", lambda: None)  # keep the test's rollback
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    return db


def test_cli_seed_check() -> None:
    result = CliRunner().invoke(cli.app, ["seed", "--check"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("files ok:")
    assert "taxonomy nodes" in result.output and "canonicals" in result.output


@pytest.mark.db
@pytest.mark.pgvector
def test_cli_seed_normalize_extract(cli_db) -> None:
    runner = CliRunner()
    seeded = runner.invoke(cli.app, ["seed"])
    assert seeded.exit_code == 0, seeded.output
    assert "canonicals:" in seeded.output and "inserted" in seeded.output
    _seed(cli_db)

    norm = runner.invoke(cli.app, ["normalize"])
    assert norm.exit_code == 0, norm.output
    assert f"{len(NAMES)} items" in norm.output and "unparseable: " in norm.output

    ext = runner.invoke(cli.app, ["extract", "--extractor", "rule"])
    assert ext.exit_code == 0, ext.output
    assert f"{len(NAMES)} items: {len(NAMES)} ok, 0 retry, 0 failed (rule)" in ext.output
    assert "0 items pending" in runner.invoke(cli.app, ["extract"]).output


def test_cli_claude_needs_a_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = CliRunner().invoke(cli.app, ["extract", "--extractor", "claude"])
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in result.output
