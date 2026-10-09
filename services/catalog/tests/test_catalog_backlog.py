"""The catalog expansion backlog (issue #52): supabase/queries/catalog_backlog.sql and the CLI."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from test_match_seed import seed_catalog
from typer.testing import CliRunner

from smartcart_catalog import cli_growth
from smartcart_catalog.active import backlog_sql_path, catalog_backlog
from smartcart_catalog.cli import app


@pytest.fixture
def db(db_utf8):
    """pg_trgm only understands Hebrew on a UTF-8 database (see conftest.utf8_dsn)."""
    return db_utf8


def miss(db, query: str, n: int = 1, days_ago: float = 1, source: str = "search") -> None:
    for _ in range(n):
        db.execute(
            "INSERT INTO search_misses (query_norm, source, seen_at)"
            " VALUES (%s, %s, now() - make_interval(secs => %s))", (query, source, days_ago * 86400))  # fmt: skip


def by_kind(rows, kind):
    return [r for r in rows if r["kind"] == kind]


def test_the_query_file_exists_and_is_named_in_the_docs() -> None:
    assert backlog_sql_path().is_file()
    text = backlog_sql_path().read_text(encoding="utf-8")
    assert "%(days)s" in text and "%(top)s" in text


@pytest.mark.db
def test_missed_queries_are_ranked_deduplicated_and_clustered(db) -> None:
    miss(db, "עגבניות שרי", 5)
    miss(db, "עגבניות שירי", 2, source="parse_list")  # a spelling variant
    miss(db, "עגבניות  שרי", 1)  # same words, extra space: the same normalized form
    miss(db, "קינואה", 4, source="parse_recipe")
    miss(db, "Quinoa", 2)  # case differs from the next row only
    miss(db, "quinoa", 1)
    miss(db, "טחינה גולמית", 3)
    miss(db, "ישן מאוד", 10, days_ago=45)  # outside the 30 day window
    miss(db, "xyzzy plugh", 1)
    rows = by_kind(catalog_backlog(db, days=30, top=10), "missed_query")
    got = [(r["label"], r["demand"], r["secondary"]) for r in rows]
    assert got[0] == ("עגבניות שרי", 8, 2)  # 5 + 2 + 1 across two spellings after normalization
    assert ("קינואה", 4, 1) in got
    assert ("quinoa", 3, 1) in got  # Quinoa and quinoa are one demand
    assert ("טחינה גולמית", 3, 1) in got
    assert all(r["label"] != "ישן מאוד" for r in rows)  # outside the window
    assert [r["demand"] for r in rows] == sorted((r["demand"] for r in rows), reverse=True)
    assert [r["position"] for r in rows] == list(range(1, len(rows) + 1))
    variants = rows[0]["examples"]
    assert variants[0] == "עגבניות שרי" and "עגבניות שירי" in variants
    assert rows[0]["last_seen"] is not None


@pytest.mark.db
def test_similarity_and_window_parameters(db) -> None:
    miss(db, "עגבניות שרי", 3)
    miss(db, "עגבניות שירי", 1)
    strict = by_kind(catalog_backlog(db, min_similarity=0.99), "missed_query")
    assert sorted((r["label"], r["demand"]) for r in strict) == [
        ("עגבניות שירי", 1),
        ("עגבניות שרי", 3),
    ]
    loose = by_kind(catalog_backlog(db, min_similarity=0.4), "missed_query")
    assert [(r["label"], r["demand"]) for r in loose] == [("עגבניות שרי", 4)]
    assert by_kind(catalog_backlog(db, min_misses=4, min_similarity=0.99), "missed_query") == []
    assert by_kind(catalog_backlog(db, days=0), "missed_query") == []
    assert len(by_kind(catalog_backlog(db, top=1, min_similarity=0.99), "missed_query")) == 1


@pytest.fixture
def shelves(db):
    """Two chains. c1: three physical stores and an online one, a base price on most items.
    c2: two stores with per-store prices only."""
    seed_catalog(db)
    for cid in ("bk-c1", "bk-c2"):
        db.execute("INSERT INTO chains (id, name, portal) VALUES (%s, %s, 'other')", (cid, cid))
    stores: dict[str, list[int]] = {"bk-c1": [], "bk-c2": []}
    for chain, n, channel in (
        ("bk-c1", 3, "physical"),
        ("bk-c1", 1, "online"),
        ("bk-c2", 2, "physical"),
    ):
        for i in range(n):
            stores[chain].append(db.execute(
                "INSERT INTO stores (chain_id, store_code, name, channel) VALUES (%s, %s, 's', %s)"
                " RETURNING id", (chain, f"{channel}{i}{len(stores[chain])}", channel)).fetchone()[0])  # fmt: skip
    db.execute("SELECT ensure_price_partition(now()::date)")

    def item(chain, code, name, barcode, *, base=False, at=(), updated_days=0):
        iid = db.execute(
            "INSERT INTO items (chain_id, item_code, barcode, raw_name, updated_at)"
            " VALUES (%s, %s, %s, %s, now() - make_interval(days => %s)) RETURNING id",
            (chain, code, barcode, name, updated_days)).fetchone()[0]  # fmt: skip
        if base:
            db.execute(
                "INSERT INTO prices (item_id, store_id, price, valid_from) VALUES (%s, NULL, 5, now())",
                (iid,),
            )
        for sid in at:
            db.execute(
                "INSERT INTO prices (item_id, store_id, price, valid_from) VALUES (%s, %s, 5, now())",
                (iid, sid),
            )
        return iid

    return stores, item


@pytest.mark.db
def test_uncovered_products_ranked_by_stores_that_carry_them(db, shelves) -> None:
    stores, item = shelves
    c1, c2 = stores["bk-c1"], stores["bk-c2"]
    canon = dict(db.execute("SELECT slug, id FROM canonical_products").fetchall())

    # barcode 111: a base price in c1 (3 physical stores; the online one does not count) and
    # per-store prices at both c2 stores: 5 stores in 2 chains.
    item("bk-c1", "a1", "קינואה אורגנית 500 גרם", "111", base=True)
    item("bk-c2", "a2", "קינואה 500ג", "111", at=c2)
    # no barcode, one store only
    item("bk-c1", "b1", "טחינה גולמית מלאה", None, at=c1[:1])
    # two items of one chain share a barcode: the chain counts once
    item("bk-c2", "d1", "שעועית אדומה", "222", at=c2[:1])
    item("bk-c2", "d2", "שעועית אדומה 1 קג", "222", at=c2)
    # excluded: mapped (served), pending review, no prices, stale
    mapped = item("bk-c1", "m1", "חלב 3% תנובה", "333", base=True)
    pending = item("bk-c1", "m2", "חלב 1% תנובה", "444", base=True)
    item("bk-c1", "n1", "ללא מחיר", "555")
    item("bk-c1", "s1", "פריט ישן", "666", base=True, updated_days=100)
    # included: only a human rejection, so no canonical covers it
    rejected = item("bk-c1", "r1", "סלמון מעושן", "777", base=True)
    for iid, review, rej in (
        (mapped, False, False),
        (pending, True, False),
        (rejected, True, True),
    ):
        db.execute(
            "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
            " needs_review, human_rejected) VALUES (%s, %s, 'any_brand', 0.9, 'rule', %s, %s)",
            (iid, canon["t-milk-3"], review, rej))  # fmt: skip

    rows = by_kind(catalog_backlog(db, top=10), "unmapped_item")
    got = [(r["label"], r["demand"], r["secondary"]) for r in rows]
    assert got == [
        (
            "קינואה אורגנית 500 גרם",
            5,
            2,
        ),  # named as the chain with more stores names it; 3 + 2 stores
        ("סלמון מעושן", 3, 1),
        ("שעועית אדומה 1 קג", 2, 1),  # max per chain (2), not the sum of its two items (3)
        ("טחינה גולמית מלאה", 1, 1),
    ]
    assert rows[0]["examples"] == ["קינואה אורגנית 500 גרם", "קינואה 500ג"]
    assert by_kind(catalog_backlog(db, top=2), "unmapped_item")[-1]["position"] == 2
    # item_days: the stale item comes in with a wide window
    wide = [
        r["label"] for r in by_kind(catalog_backlog(db, top=10, item_days=365), "unmapped_item")
    ]
    assert "פריט ישן" in wide and "ללא מחיר" not in wide


@pytest.mark.db
def test_both_lists_come_from_one_query_and_an_empty_database_is_fine(db) -> None:
    assert catalog_backlog(db) == []
    miss(db, "קינואה", 2)
    rows = catalog_backlog(db)
    assert {r["kind"] for r in rows} == {"missed_query"}


# --- the command -------------------------------------------------------------------------------


@pytest.fixture
def cli_db(db, monkeypatch):
    @contextmanager
    def _connect():
        yield db

    monkeypatch.setattr(cli_growth, "_connect", _connect)
    return db


@pytest.mark.db
def test_backlog_command_prints_the_top_rows(cli_db) -> None:
    miss(cli_db, "קינואה", 4)
    miss(cli_db, "טחינה גולמית", 2)
    result = CliRunner().invoke(app, ["backlog", "--top", "1"])
    assert result.exit_code == 0, result.output
    assert "Searched for and not found (last 30 days): 1 shown" in result.output
    assert "1. קינואה  [4 misses, 1 spellings]" in result.output
    assert "טחינה" not in result.output
    assert "In the price files, no canonical covers it: 0 shown" in result.output


def test_backlog_is_registered_on_the_catalog_cli() -> None:
    names = {c.name or c.callback.__name__ for c in app.registered_commands}
    assert {"backlog", "native-report"} <= names
