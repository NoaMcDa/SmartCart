from __future__ import annotations

import uuid

import pytest
from test_match_seed import add_item, seed_catalog

from smartcart_catalog.feedback import (
    feedback_gold_candidates,
    record_feedback,
    rejection_rates,
)
from smartcart_catalog.match import apply_decisions
from smartcart_catalog.models import MatchDecision


def _mapped(db, ids):
    original = add_item(db, "חלב טרי 3% תנובה 1 ליטר")
    substitute = add_item(db, "חלב 3% שופרסל 1 ליטר")
    apply_decisions(db, [MatchDecision(item_id=substitute, canonical_id=ids["t-milk-3"],
                                       flex_level="any_brand", confidence=0.95, source="rule",
                                       needs_review=False)])  # fmt: skip
    return original, substitute


def _mapping(db, item_id, canonical_id):
    return db.execute(
        "SELECT canonical_id, flex_level, confidence::float, source, needs_review"
        " FROM item_canonical WHERE item_id = %s AND canonical_id = %s",
        (item_id, canonical_id),
    ).fetchone()


@pytest.mark.db
def test_not_good_flags_mapping_for_review_without_changing_it(db) -> None:
    ids = seed_catalog(db)
    original, substitute = _mapped(db, ids)
    before = _mapping(db, substitute, ids["t-milk-3"])
    user = uuid.uuid4()
    res = record_feedback(db, user, ids["t-milk-3"], original, substitute, "not_good")
    assert res.flagged and res.flex_level == "any_brand" and res.confidence == 0.95
    after = _mapping(db, substitute, ids["t-milk-3"])
    assert after[4] is True and after[:4] == before[:4]  # only the review flag changed
    row = db.execute(
        "SELECT user_id, canonical_id, original_item_id, substitute_item_id, verdict"
        " FROM substitution_feedback WHERE id = %s",
        (res.feedback_id,),
    ).fetchone()
    assert row == (user, ids["t-milk-3"], original, substitute, "not_good")


@pytest.mark.db
def test_other_verdicts_and_anonymous_users_do_not_flag(db) -> None:
    ids = seed_catalog(db)
    original, substitute = _mapped(db, ids)
    for verdict in ("kept_original", "accepted"):
        res = record_feedback(db, None, ids["t-milk-3"], original, substitute, verdict)
        assert not res.flagged
    assert _mapping(db, substitute, ids["t-milk-3"])[4] is False
    # Feedback about a pair with no mapping is still recorded.
    res = record_feedback(db, None, ids["t-milk-1"], original, substitute, "not_good")
    assert not res.flagged and res.flex_level is None
    with pytest.raises(ValueError):
        record_feedback(db, None, ids["t-milk-3"], original, substitute, "meh")  # type: ignore[arg-type]


@pytest.mark.db
def test_rejection_rates_and_gold_candidates(db) -> None:
    ids = seed_catalog(db)
    original, substitute = _mapped(db, ids)
    record_feedback(db, None, ids["t-milk-3"], original, substitute, "not_good")
    record_feedback(db, None, ids["t-milk-3"], original, substitute, "accepted")
    record_feedback(db, None, ids["t-milk-3"], original, substitute, "not_good")
    rates = {(r["category"], r["flex_level"]): r for r in rejection_rates(db)}
    milk = rates[("dairy.milk", "any_brand")]
    assert milk["reports"] == 3 and milk["not_good"] == 2
    assert milk["rejection_rate"] == pytest.approx(2 / 3)
    cands = feedback_gold_candidates(db)
    assert cands[0]["item_id"] == substitute and cands[0]["reports"] == 2
    assert cands[0]["suggested_label"] == "no_match"
    db.execute(
        "INSERT INTO gold_pairs (item_id, canonical_id, label) VALUES (%s, %s, 'any_brand')",
        (substitute, ids["t-milk-3"]),
    )
    assert feedback_gold_candidates(db) == []  # a human already labeled the pair


@pytest.mark.db
def test_feedback_context_columns_are_written_when_given(db) -> None:
    ids = seed_catalog(db)
    original, substitute = _mapped(db, ids)
    res = record_feedback(db, None, ids["t-milk-3"], original, substitute, "not_good",
                          list_item_id=42, flex_level="any_brand", match_confidence=0.95)  # fmt: skip
    row = db.execute(
        "SELECT list_item_id, flex_level, match_confidence::float FROM substitution_feedback"
        " WHERE id = %s", (res.feedback_id,),
    ).fetchone()
    assert row == (42, "any_brand", 0.95)
    bare = record_feedback(db, None, ids["t-milk-3"], original, substitute, "accepted")
    assert db.execute(
        "SELECT list_item_id, flex_level, match_confidence FROM substitution_feedback"
        " WHERE id = %s", (bare.feedback_id,),
    ).fetchone() == (None, None, None)
    with pytest.raises(ValueError):
        record_feedback(db, None, ids["t-milk-3"], original, substitute, "accepted",
                        flex_level="loose")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        record_feedback(db, None, ids["t-milk-3"], original, substitute, "accepted",
                        match_confidence=1.5)


@pytest.mark.db
def test_feedback_on_a_rejected_pair_does_not_flag_it(db) -> None:
    ids = seed_catalog(db)
    original, substitute = _mapped(db, ids)
    db.execute("UPDATE item_canonical SET human_rejected = true, source = 'human'"
               " WHERE item_id = %s", (substitute,))  # fmt: skip
    res = record_feedback(db, None, ids["t-milk-3"], original, substitute, "not_good")
    assert not res.flagged and res.flex_level is None
    rates = {(r["category"], r["flex_level"]) for r in rejection_rates(db)}
    assert ("dairy.milk", "rejected") in rates


@pytest.mark.db
def test_dismissed_swap_is_stored_with_its_source_but_does_not_flag(db) -> None:
    """A smart-cart dismissal is a weak signal: counted, never pulls the mapping from the price run."""
    ids = seed_catalog(db)
    original, substitute = _mapped(db, ids)
    res = record_feedback(db, None, ids["t-milk-3"], original, substitute, "not_good", source="swap")
    assert not res.flagged and res.flex_level == "any_brand"
    assert _mapping(db, substitute, ids["t-milk-3"])[4] is False
    assert db.execute(
        "SELECT source FROM substitution_feedback WHERE id = %s", (res.feedback_id,)
    ).fetchone() == ("swap",)
    # The card's verdict on the same pair still flags it.
    assert record_feedback(db, None, ids["t-milk-3"], original, substitute, "not_good").flagged
