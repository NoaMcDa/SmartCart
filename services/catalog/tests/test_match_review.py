"""Review UI commands and queries (``review_app``), tested without Streamlit."""

from __future__ import annotations

import pytest
from test_match_seed import LEXICON, add_item, embed_all, seed_catalog

from smartcart_catalog import review_app
from smartcart_catalog.match import Lexicon, apply_decisions
from smartcart_catalog.models import MatchDecision


def _map(db, item_id, canonical_id, *, review=True, conf=0.75, level="any_brand"):
    apply_decisions(db, [MatchDecision(item_id=item_id, canonical_id=canonical_id,
                                       flex_level=level, confidence=conf, source="rule",
                                       needs_review=review)])  # fmt: skip


def _row(db, item_id, canonical_id):
    return db.execute(
        "SELECT flex_level, source, needs_review, reviewed_by, reviewed_at IS NOT NULL,"
        " confidence::float FROM item_canonical WHERE item_id = %s AND canonical_id = %s",
        (item_id, canonical_id),
    ).fetchone()


def _gold(db, item_id, canonical_id):
    row = db.execute(
        "SELECT label FROM gold_pairs WHERE item_id = %s AND canonical_id = %s",
        (item_id, canonical_id),
    ).fetchone()
    return row[0] if row else None


@pytest.mark.db
def test_queue_lists_review_items_with_feedback_first(db) -> None:
    ids = seed_catalog(db)
    a = add_item(db, "חלב 3% 1 ליטר")
    b = add_item(db, "פילה סלמון 400 גרם")
    c = add_item(db, "חלב טרי 1% 1 ליטר")
    _map(db, a, ids["t-milk-3"], conf=0.85)
    _map(db, b, ids["t-salmon-fresh"], conf=0.70)
    _map(db, c, ids["t-milk-1"], review=False, conf=0.95)
    db.execute(
        "INSERT INTO substitution_feedback (canonical_id, substitute_item_id, verdict)"
        " VALUES (%s, %s, 'not_good')",
        (ids["t-salmon-fresh"], b),
    )
    queue = review_app.review_queue(db)
    assert [r["item_id"] for r in queue] == [b, a]  # reported first; accepted c not listed
    assert queue[0]["feedback_marker"] and not queue[1]["feedback_marker"]
    assert queue[1]["item_name"] == "חלב 3% 1 ליטר" and queue[1]["canonical_slug"] == "t-milk-3"


@pytest.mark.db
def test_accept_records_human_decision_and_gold_pair(db) -> None:
    ids = seed_catalog(db)
    it = add_item(db, "חלב 3% 1 ליטר")
    _map(db, it, ids["t-milk-3"])
    review_app.accept(db, it, ids["t-milk-3"], "noa@example.com")
    assert _row(db, it, ids["t-milk-3"]) == ("any_brand", "human", False, "noa@example.com", True,
                                             1.0)  # fmt: skip
    assert _gold(db, it, ids["t-milk-3"]) == "any_brand"
    assert review_app.review_queue(db) == []
    # A later judge run cannot touch it.
    _map(db, it, ids["t-milk-1"], review=False, conf=0.99)
    assert _row(db, it, ids["t-milk-1"]) is None
    with pytest.raises(ValueError):
        review_app.accept(db, it, ids["t-milk-3"], "  ")


@pytest.mark.db
def test_reject_and_remap(db) -> None:
    ids = seed_catalog(db)
    it = add_item(db, "חלב 1% 1 ליטר")
    _map(db, it, ids["t-milk-3"])
    review_app.reject(db, it, ids["t-milk-3"], "noa")
    assert _row(db, it, ids["t-milk-3"]) is None
    assert _gold(db, it, ids["t-milk-3"]) == "no_match"
    _map(db, it, ids["t-milk-3"], review=False, conf=0.99)  # the judge cannot bring it back
    assert _row(db, it, ids["t-milk-3"]) is None

    other = add_item(db, "משקה סויה 2 ליטר")
    _map(db, other, ids["t-almond"])
    review_app.remap(db, other, ids["t-almond"], ids["t-soy"], "close", "noa")
    assert _row(db, other, ids["t-almond"]) is None
    assert _row(db, other, ids["t-soy"])[:3] == ("close", "human", False)
    assert _gold(db, other, ids["t-almond"]) == "no_match"
    assert _gold(db, other, ids["t-soy"]) == "close"


@pytest.mark.db
def test_bestseller_status_and_search(db) -> None:
    ids = seed_catalog(db)
    it = add_item(db, "חלב 3% 1 ליטר")
    _map(db, it, ids["t-milk-3"])
    status = {s["slug"]: s for s in review_app.bestseller_status(db, top=3)}
    assert set(status) == {"t-milk-3", "t-milk-1", "t-soy"}
    assert status["t-milk-3"]["pending"] == 1 and not status["t-milk-3"]["fully_reviewed"]
    review_app.accept(db, it, ids["t-milk-3"], "noa")
    status = {s["slug"]: s for s in review_app.bestseller_status(db, top=3)}
    assert status["t-milk-3"]["fully_reviewed"]
    found = review_app.search_canonicals(db, "סויה")
    assert [f["slug"] for f in found] == ["t-soy"]


@pytest.mark.db
@pytest.mark.pgvector
def test_explain_shows_attributes_candidates_and_reasons(db) -> None:
    seed_catalog(db)
    it = add_item(db, "חלב טרי 1% 1 ליטר")
    embed_all(db)
    info = review_app.explain(db, it, lexicon=Lexicon.from_mapping(LEXICON))
    assert info["attributes"]["fat_pct"] == "1"
    assert info["block"] == "dairy / 100ml"
    by_slug = {c["slug"]: c for c in info["candidates"]}
    assert by_slug["t-milk-3"]["eligible"] is False
    assert "fat_pct 1 vs 3" in by_slug["t-milk-3"]["reason"]
    assert by_slug["t-milk-1"]["eligible"] is True
    assert info["decision"]["canonical_id"] is not None
