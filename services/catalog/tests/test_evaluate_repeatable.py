"""The gold-set evaluations give the same numbers on a used database as on a fresh one.

Before the harness isolated its inputs, ``evaluate`` after ``evaluate-ar`` on one database
(precision 0.9754 instead of 1.0000) failed the gate: ``evaluate-ar`` seeds the catalog, which
rewrites 11 of the gold set's 58 canonicals and adds 234 more that compete as candidates. The
"fresh" baselines (module fixtures) are taken in a transaction that is rolled back; the used
databases are built by the tests, inside the rolled-back transaction of the ``db`` fixture.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from psycopg import Connection

from smartcart_catalog.embed import HashEmbedder, embed_canonicals
from smartcart_catalog.evaluate import Report, load_gold, run_evaluation
from smartcart_catalog.evaluate_ar import ArReport, load_lines
from smartcart_catalog.evaluate_ar import run_evaluation as run_evaluation_ar
from smartcart_catalog.judge import RuleJudge
from smartcart_catalog.seed import load_catalog, seed_all

pytestmark = [pytest.mark.db, pytest.mark.pgvector]


def numbers(report: Report) -> dict[str, Any]:
    """Everything a run reports except the identity of the run itself."""
    m = report.metrics.model_dump(mode="json", exclude={"run_id", "computed_at"})
    return {**m, **report.extra}


def evaluate(db: Connection, **kwargs: Any) -> Report:
    return run_evaluation(db, RuleJudge(), HashEmbedder(), k=10, **kwargs)


@pytest.fixture(scope="module")
def fresh(database: Any) -> dict[str, Any]:
    """The Hebrew numbers of a run from the database as the migrations leave it, in a
    transaction that is rolled back (the numbers are a function of the code and the gold files)."""
    with psycopg.connect(database.dsn) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        try:
            return numbers(evaluate(conn))
        finally:
            conn.rollback()


@pytest.fixture(scope="module")
def fresh_ar(database: Any) -> dict[str, Any]:
    with psycopg.connect(database.dsn) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        try:
            return ar_numbers(arabic(conn))
        finally:
            conn.rollback()


def pollute_like_evaluate_ar(db: Connection) -> None:
    """What ``smartcart-catalog evaluate-ar`` leaves behind: the seeded catalog and its vectors."""
    seed_all(db, load_catalog())
    embed_canonicals(db, HashEmbedder())


def test_hebrew_evaluation_twice_in_a_row_is_identical(db: Connection, fresh) -> None:
    runs_before = _evaluate_runs(db)
    first = evaluate(db)
    second = evaluate(db, load=False)  # --no-load, as the JSON step of the workflow runs it
    assert numbers(first) == numbers(second) == fresh
    assert first.metrics.precision == {"exact": 1.0, "any_brand": 1.0, "close": 1.0}
    assert _evaluate_runs(db) == runs_before + 2  # every run is still recorded, with its own id
    assert first.metrics.run_id != second.metrics.run_id


def test_hebrew_evaluation_after_evaluate_ar_equals_a_fresh_run(db: Connection, fresh) -> None:
    pollute_like_evaluate_ar(db)
    load_gold(db)
    before = _catalog_state(db)
    assert numbers(evaluate(db, load=False)) == fresh
    assert _catalog_state(db) == before  # the evaluation did not change the catalog it ran on


def test_hebrew_evaluation_on_a_seeded_catalog_equals_a_fresh_run(db: Connection, fresh) -> None:
    pollute_like_evaluate_ar(db)  # seed first: the gold set loads into a used catalog
    assert numbers(evaluate(db)) == fresh


def _evaluate_runs(db: Connection) -> int:
    return db.execute("SELECT count(*) FROM match_runs WHERE kind = 'evaluate'").fetchone()[0]


def _catalog_state(db: Connection) -> list[tuple]:
    rows = db.execute(
        "SELECT slug, display_name_he, taxonomy_id, base_unit, critical_attrs::text,"
        " soft_attrs::text, reference_barcodes, embedding_model, embedding::text"
        " FROM canonical_products ORDER BY slug"
    ).fetchall()
    rules = db.execute("SELECT * FROM product_type_rules ORDER BY product_type").fetchall()
    items = db.execute(
        "SELECT item_code, manufacturer, quantity, unit FROM items ORDER BY id"
    ).fetchall()
    return [*rows, *rules, *items]


def test_stored_extractions_mappings_and_rejections_do_not_enter_the_evaluation(
    db: Connection, fresh
) -> None:
    """Rows other jobs attach to gold items (extraction, auto and human mappings, a human
    rejection of the right answer, normalized quantities) are not inputs of the evaluation."""
    load_gold(db)
    item_ids = [r[0] for r in db.execute(
        "SELECT DISTINCT item_id FROM gold_pairs ORDER BY item_id").fetchall()]  # fmt: skip
    db.execute(
        "INSERT INTO item_attributes (item_id, attrs, extractor, confidence, status)"
        ' SELECT id, \'{"category_path": "pantry", "state": "frozen"}\'::jsonb, \'test\', 0.99,'
        " 'ok' FROM items WHERE id = ANY(%s)",
        (item_ids,),
    )
    # a human rejected the best pair of every item, and an auto mapping points elsewhere
    rejected = db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
        " human_rejected)"
        " SELECT DISTINCT ON (item_id) item_id, canonical_id, 'any_brand', 0.5, 'human', true"
        " FROM gold_pairs WHERE label <> 'no_match' ORDER BY item_id, id"
    ).rowcount
    db.execute(
        "UPDATE items SET manufacturer = 'x', quantity = 7, unit = 'kg' WHERE id = ANY(%s)",
        (item_ids,),
    )
    assert numbers(evaluate(db, load=False)) == fresh
    # the rows other jobs wrote are still there afterwards
    assert db.execute("SELECT count(*) FROM item_attributes").fetchone()[0] == len(item_ids)
    assert db.execute("SELECT count(*) FROM item_canonical").fetchone()[0] == rejected


# --- the Arabic evaluation ------------------------------------------------------------------------


def arabic(db: Connection, **kwargs: Any) -> ArReport:
    lines = load_lines()[::12]  # a spread over the whole file, held-out lines included
    return run_evaluation_ar(db, lines, **kwargs)


def ar_numbers(report: ArReport) -> dict[str, Any]:
    return {**report.to_json(), "outcomes": [(o.line.q, o.slug, o.served, o.correct)
                                             for o in report.outcomes]}  # fmt: skip


def test_arabic_evaluation_twice_in_a_row_is_identical(db: Connection, fresh_ar) -> None:
    first = ar_numbers(arabic(db))
    assert first == fresh_ar
    assert ar_numbers(arabic(db)) == first
    assert ar_numbers(arabic(db, seed=False)) == first  # --no-seed, on what the first run wrote
    assert first["precision"]["any_brand"] >= 0.98


def test_arabic_evaluation_after_the_hebrew_one_equals_a_fresh_run(
    db: Connection, fresh, fresh_ar
) -> None:
    assert numbers(evaluate(db)) == fresh  # the gold set's canonicals and items stay behind
    assert ar_numbers(arabic(db)) == fresh_ar
    # and the Hebrew numbers did not move because the Arabic run seeded over the gold slugs
    assert numbers(evaluate(db, load=False)) == fresh
