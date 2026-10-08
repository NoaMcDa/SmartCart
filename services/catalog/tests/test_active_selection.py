"""Uncertainty-first review selection and labels per hour (issue #52)."""

from __future__ import annotations

import pytest
from test_match_seed import add_item, seed_catalog

from smartcart_catalog import review_app
from smartcart_catalog.active import DISTANCE_BAND, labels_per_hour, select_for_review
from smartcart_catalog.embed import HASH_MODEL_NAME, HashEmbedder, to_pgvector
from smartcart_catalog.judge import ACCEPT_THRESHOLD
from smartcart_catalog.match import apply_decisions
from smartcart_catalog.models import MatchDecision

LEARNED = "test-learned-model-v1"


def _map(db, item_id, canonical_id, conf, *, review=True, level="any_brand"):
    apply_decisions(db, [MatchDecision(item_id=item_id, canonical_id=canonical_id, flex_level=level,
                                       confidence=conf, source="rule", needs_review=review)])  # fmt: skip


def _report(db, item_id, canonical_id, n=1):
    for _ in range(n):
        db.execute(
            "INSERT INTO substitution_feedback (canonical_id, substitute_item_id, verdict)"
            " VALUES (%s, %s, 'not_good')", (canonical_id, item_id))  # fmt: skip


def _vectors(db, item_id, canonical_id, item_vec, canon_vec, model=LEARNED):
    db.execute(
        "INSERT INTO item_embeddings (item_id, embedding, model) VALUES (%s, %s::vector, %s)"
        " ON CONFLICT (item_id) DO UPDATE SET embedding = EXCLUDED.embedding, model = EXCLUDED.model",
        (item_id, to_pgvector(item_vec), model))  # fmt: skip
    db.execute("UPDATE canonical_products SET embedding = %s::vector, embedding_model = %s"
               " WHERE id = %s", (to_pgvector(canon_vec), model, canonical_id))  # fmt: skip


def _unit(i: int) -> list[float]:
    v = [0.0] * 1024
    v[i] = 1.0
    return v


@pytest.fixture
def queue(db):
    """A seeded queue. canonical ranks: milk-3 1, milk-1 2, soy 3, almond 4, salmon-fresh 5,
    salmon-frozen 6, olive-oil 7. Returns name -> (item_id, canonical_id)."""
    ids = seed_catalog(db)
    spec = {
        # name: (item name, canonical slug, confidence)
        "reported_twice": ("חלב 3% 1 ליטר", "t-milk-3", 0.62),
        "reported_once": ("חלב טרי 1% 1 ליטר", "t-milk-1", 0.62),
        "near_a": ("סלמון טרי פילה", "t-salmon-fresh", 0.895),     # band 0, rank 5
        "near_b": ("משקה סויה 1 ליטר", "t-soy", 0.905),            # band 0, rank 3
        "near_c": ("שמן זית כתית 750", "t-olive-oil", 0.895),      # band 0, rank 7, embedders disagree
        "near_d": ("משקה שקדים 1 ליטר", "t-almond", 0.895),        # band 0, rank 4, embedders agree
        "mid": ("סלמון קפוא פילה", "t-salmon-frozen", 0.87),       # band 1
        "far": ("חלב 3% קרטון", "t-milk-3", 0.75),                 # band 7
        "farthest": ("חלב 1% קרטון", "t-milk-1", 0.66),            # band 12
    }
    out = {}
    for name, (text, slug, conf) in spec.items():
        item = add_item(db, text)
        _map(db, item, ids[slug], conf)
        out[name] = (item, ids[slug])
    _report(db, *out["reported_twice"], n=2)
    _report(db, *out["reported_once"], n=1)
    # near_c: a learned model that sees no match where the names are alike (cosine 0 against
    # ~0.5 or more for the character n-grams).
    item, canon = out["near_c"]
    _vectors(db, item, canon, _unit(0), _unit(1))
    # near_d: the "learned" vectors are the hash vectors of the names: both embedders agree.
    item, canon = out["near_d"]
    names = db.execute("SELECT i.raw_name, cp.display_name_he FROM items i, canonical_products cp"
                       " WHERE i.id = %s AND cp.id = %s", (item, canon)).fetchone()  # fmt: skip
    iv, cv = HashEmbedder().embed(list(names))
    _vectors(db, item, canon, iv, cv)
    # Pairs that must never be queued.
    done = add_item(db, "לחם")
    _map(db, done, ids["t-soy"], 0.95, review=False)
    return out


def ids_of(rows):
    return [(r["item_id"], r["canonical_id"]) for r in rows]


@pytest.mark.db
def test_order_on_a_seeded_queue(db, queue) -> None:
    rows = select_for_review(db, 100)
    want = [queue[k] for k in (
        "reported_twice",  # (a) two user reports
        "reported_once",   # (a) one report
        "near_c",          # (b) band 0, (c) the embedders disagree
        "near_b",          # (b) band 0, no disagreement, (d) best seller of the three (rank 3)
        "near_d",          # rank 4
        "near_a",          # rank 5
        "mid",             # (b) band 1
        "far",             # (b) band 7
        "farthest",        # (b) band 12
    )]  # fmt: skip
    assert ids_of(rows) == want
    assert [r["reports"] for r in rows[:2]] == [2, 1]
    assert rows[0]["feedback_marker"] and not rows[2]["feedback_marker"]
    dis = {r["item_id"]: r["disagreement"] for r in rows}
    assert dis[queue["near_c"][0]] is not None and dis[queue["near_c"][0]] > 0.3
    assert dis[queue["near_d"][0]] == 0.0
    assert dis[queue["near_a"][0]] is None  # no learned vectors: one embedder only
    assert [r["distance"] for r in rows[2:]] == sorted(r["distance"] for r in rows[2:])


@pytest.mark.db
def test_each_key_decides_when_the_earlier_ones_tie(db, queue) -> None:
    rows = {r["item_id"]: r for r in select_for_review(db, 100)}
    c, d, a, b = (queue[k][0] for k in ("near_c", "near_d", "near_a", "near_b"))
    # same reports (0) and same band (0) for all four ...
    assert {rows[i]["reports"] for i in (a, b, c, d)} == {0}
    assert {int(rows[i]["distance"] // DISTANCE_BAND) for i in (a, b, c, d)} == {0}
    # ... (c) puts the disagreeing pair first, (d) the best seller among the rest: soy 3, almond 4, salmon 5
    order = [r["item_id"] for r in select_for_review(db, 100) if r["item_id"] in (a, b, c, d)]
    assert order == [c, b, d, a]


@pytest.mark.db
def test_a_user_report_beats_closeness(db, queue) -> None:
    rows = select_for_review(db, 100)
    # 0.62 is 0.28 from the threshold, farther than anything unreported, yet it is first
    assert rows[0]["confidence"] == pytest.approx(0.62)
    assert rows[0]["distance"] > rows[2]["distance"]


@pytest.mark.db
def test_limit_takes_the_head_of_the_same_order(db, queue) -> None:
    full = ids_of(select_for_review(db, 100))
    for n in (1, 2, 3, 4, 5, 8):
        assert ids_of(select_for_review(db, n)) == full[:n]
    assert select_for_review(db, 0) == []


@pytest.mark.db
def test_the_threshold_is_a_parameter(db, queue) -> None:
    rows = select_for_review(db, 100, threshold=0.66)
    unreported = [r for r in rows if r["reports"] == 0]
    assert unreported[0]["confidence"] == pytest.approx(0.66)  # now the closest
    assert ACCEPT_THRESHOLD == 0.90


@pytest.mark.db
def test_accepted_rejected_and_unflagged_pairs_are_not_queued(db, queue) -> None:
    item, canon = queue["near_a"]
    review_app.accept(db, item, canon, "noa")
    item_b, canon_b = queue["near_b"]
    review_app.reject(db, item_b, canon_b, "noa")
    got = ids_of(select_for_review(db, 100))
    assert queue["near_a"] not in got and queue["near_b"] not in got
    assert len(got) == 7


@pytest.mark.db
def test_hash_vectors_alone_do_not_count_as_a_second_embedder(db, queue) -> None:
    item, canon = queue["near_a"]
    _vectors(db, item, canon, _unit(0), _unit(1), model=HASH_MODEL_NAME)
    row = next(r for r in select_for_review(db, 100) if r["item_id"] == item)
    assert row["disagreement"] is None
    # and vectors of two different models are never compared
    db.execute("UPDATE canonical_products SET embedding_model = 'other-model' WHERE id = %s", (canon,))
    row = next(r for r in select_for_review(db, 100) if r["item_id"] == item)
    assert row["disagreement"] is None


@pytest.mark.db
def test_the_review_queue_is_this_selection(db, queue) -> None:
    assert ids_of(review_app.review_queue(db, 100)) == ids_of(select_for_review(db, 100))
    first = review_app.review_queue(db, 1)[0]
    assert {"item_name", "canonical_slug", "feedback_marker", "reason", "attrs"} <= set(first)


# --- labels per hour ---------------------------------------------------------------------------


def _human(db, item, canon, who, offset_seconds):
    """A human decision ``offset_seconds`` after a fixed base (a day ago)."""
    db.execute(
        "UPDATE item_canonical SET source = 'human', reviewed_by = %s, needs_review = false,"
        " reviewed_at = now() - interval '1 day' + make_interval(secs => %s)"
        " WHERE item_id = %s AND canonical_id = %s", (who, offset_seconds, item, canon))  # fmt: skip


@pytest.mark.db
def test_labels_per_hour_from_decision_timestamps(db, queue) -> None:
    pairs = list(queue.values())
    # noa: four labels a minute apart, a break of two hours, then two labels 30 s apart.
    for (item, canon), at in zip(pairs[:6], (0, 60, 120, 180, 7380, 7410), strict=True):
        _human(db, item, canon, "noa", at)
    # dana: one label.
    _human(db, *pairs[6], "dana", 500)
    # A label from 30 days ago is outside the 7-day window.
    _human(db, *pairs[7], "noa", -30 * 86400)
    m = labels_per_hour(db, days=7)
    by = {r["reviewer"]: r for r in m["by_reviewer"]}
    # noa: in-session gaps 60, 60, 60, 30 (sum 210, median 60) + one typical gap per session (2)
    noa_seconds = 210 + 2 * 60
    assert by["noa"]["labels"] == 6
    assert by["noa"]["active_hours"] == pytest.approx(noa_seconds / 3600, abs=1e-3)
    assert by["noa"]["labels_per_hour"] == pytest.approx(6 / (noa_seconds / 3600), abs=0.1)
    assert by["dana"]["labels"] == 1 and by["dana"]["labels_per_hour"] == pytest.approx(60.0)
    assert m["labels"] == 7
    assert m["labels_per_hour"] == pytest.approx(7 / ((noa_seconds + 60) / 3600), abs=0.1)
    assert sum(n for _, n in m["by_day"]) == 7
    # a wider window includes the old label
    assert labels_per_hour(db, days=60)["labels"] == 8


@pytest.mark.db
def test_labels_per_hour_with_no_labels(db) -> None:
    m = labels_per_hour(db, days=7)
    assert m["labels"] == 0 and m["labels_per_hour"] is None and m["by_reviewer"] == []


def test_review_command_explains_the_missing_extra(monkeypatch) -> None:
    import importlib.util

    from typer.testing import CliRunner

    from smartcart_catalog.cli import app

    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a, **k: None if name == "streamlit" else real(name, *a, **k))
    result = CliRunner().invoke(app, ["review"])
    assert result.exit_code == 2
    assert "optional 'review' extra" in result.output and "uv sync --extra review" in result.output
