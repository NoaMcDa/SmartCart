from __future__ import annotations

import json
from decimal import Decimal

import pytest
from test_match_seed import LEXICON, MILK3_BARCODE, add_item, embed_all, seed_catalog

from smartcart_catalog.judge import RuleJudge
from smartcart_catalog.match import (
    Lexicon,
    apply_decisions,
    fallback_attributes,
    load_items,
    parse_quantity,
    run_matching,
)
from smartcart_catalog.models import MatchDecision


@pytest.mark.parametrize(
    ("name", "qty", "unit", "count"),
    [
        ("חלב טרי 3% 1 ליטר", Decimal("1"), "l", 1),
        ("קוטג' 5% 250 גרם", Decimal("250"), "g", 1),
        ("מים מינרליים 6*1.5 ל'", Decimal("1.5"), "l", 6),
        ('שמן זית 750 מ"ל', Decimal("750"), "ml", 1),
        ('חזה עוף 1 ק"ג', Decimal("1"), "kg", 1),
        ("עגבניות במשקל", None, None, 1),
    ],
)
def test_parse_quantity(name, qty, unit, count) -> None:
    assert parse_quantity(name) == (qty, unit, count)


def test_fallback_attributes_with_lexicon() -> None:
    lex = Lexicon.from_mapping(LEXICON)
    a = fallback_attributes("חלב טרי 3% תנובה 1 ליטר", lex)
    assert (a.product_type, a.fat_pct, a.state, a.pack_size, a.unit) == (
        "milk",
        Decimal("3"),
        "fresh",
        Decimal("1"),
        "l",
    )
    assert a.category_path == "dairy.milk"
    frozen = fallback_attributes("פילה סלמון קפוא 800 גרם", lex)
    assert frozen.product_type == "salmon" and frozen.state == "frozen"
    soy = fallback_attributes("משקה סויה אלפרו 1 ליטר", lex)
    assert soy.product_type == "soy_drink"  # longest keyword wins over nothing else
    assert fallback_attributes("קולה זירו 1.5 ליטר").diet_flags == ("sugar_free",)
    unknown = fallback_attributes("משהו אחר")
    assert unknown.product_type is None and unknown.category_path is None


@pytest.mark.db
def test_load_items_prefers_item_attributes(db) -> None:
    seed_catalog(db)
    with_attrs = add_item(db, "חלב 1 ליטר")
    db.execute(
        "INSERT INTO item_attributes (item_id, attrs, extractor) VALUES (%s, %s, 'claude')",
        (with_attrs, json.dumps({"product_type": "milk", "fat_pct": 3, "state": "fresh",
                                 "category_path": "dairy.milk", "unknown_key": 1})),
    )  # fmt: skip
    without = add_item(db, "פילה סלמון קפוא 800 גרם")
    ctx = load_items(db, [with_attrs, without], Lexicon.from_mapping(LEXICON))
    assert ctx[with_attrs].attrs_source == "item_attributes"
    assert ctx[with_attrs].attrs.fat_pct == Decimal(3)
    assert ctx[with_attrs].item.base_unit == "100ml"
    assert ctx[without].attrs_source == "fallback" and ctx[without].attrs.state == "frozen"
    assert ctx[without].item.base_unit == "100g"


def _mapping(db, item_id):
    return db.execute(
        "SELECT canonical_id, flex_level, confidence::float, source, needs_review"
        " FROM item_canonical WHERE item_id = %s ORDER BY canonical_id",
        (item_id,),
    ).fetchall()


def _decision(item_id, canonical_id, level="any_brand", conf=0.95, review=False):
    return MatchDecision(item_id=item_id, canonical_id=canonical_id, flex_level=level,
                         confidence=conf, source="rule", needs_review=review)  # fmt: skip


@pytest.mark.db
def test_apply_decisions_is_idempotent_and_replaces_machine_rows(db) -> None:
    ids = seed_catalog(db)
    it = add_item(db, "חלב טרי 3% 1 ליטר")
    d = _decision(it, ids["t-milk-3"])
    apply_decisions(db, [d])
    first = _mapping(db, it)
    apply_decisions(db, [d])
    assert _mapping(db, it) == first == [(ids["t-milk-3"], "any_brand", 0.95, "rule", False)]

    # The judge changes its mind: the stale machine row goes away.
    apply_decisions(db, [_decision(it, ids["t-milk-1"], conf=0.7, review=True)])
    assert _mapping(db, it) == [(ids["t-milk-1"], "any_brand", 0.7, "rule", True)]
    # Rejected now: no mapping at all.
    counts = apply_decisions(db, [MatchDecision(item_id=it, canonical_id=None, flex_level=None,
                                                confidence=0.2, source="rule",
                                                needs_review=False)])  # fmt: skip
    assert _mapping(db, it) == [] and counts["unmapped"] == 1


@pytest.mark.db
def test_apply_decisions_never_overwrites_human_rows(db) -> None:
    ids = seed_catalog(db)
    it = add_item(db, "חלב טרי 3% 1 ליטר")
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
        " needs_review, reviewed_by, reviewed_at) VALUES (%s, %s, 'close', 1, 'human', false,"
        " 'noa', now())",
        (it, ids["t-milk-3"]),
    )
    before = _mapping(db, it)
    counts = apply_decisions(db, [
        _decision(it, ids["t-milk-3"], level="any_brand", conf=0.99),
        _decision(it, ids["t-milk-1"], conf=0.99),
        MatchDecision(item_id=it, canonical_id=None, flex_level=None, confidence=0.1,
                      source="rule", needs_review=False),
    ])  # fmt: skip
    assert _mapping(db, it) == before == [(ids["t-milk-3"], "close", 1.0, "human", False)]
    assert counts["skipped_human"] == 3


def _reject(db, item_id, canonical_id) -> None:
    db.execute(
        "INSERT INTO item_canonical (item_id, canonical_id, flex_level, confidence, source,"
        " needs_review, human_rejected, reviewed_by, reviewed_at)"
        " VALUES (%s, %s, 'close', 0, 'human', true, true, 'noa', now())",
        (item_id, canonical_id),
    )


@pytest.mark.db
def test_apply_decisions_respects_human_rejections_and_open_feedback(db) -> None:
    ids = seed_catalog(db)
    rejected = add_item(db, "חלב 1% 1 ליטר")
    _reject(db, rejected, ids["t-milk-3"])
    counts = apply_decisions(db, [_decision(rejected, ids["t-milk-3"])])
    assert counts["skipped_rejected_by_human"] == 1
    assert _mapping(db, rejected) == [(ids["t-milk-3"], "close", 0.0, "human", True)]
    # A rejection is not a human mapping: the judge may still map the item elsewhere.
    apply_decisions(db, [_decision(rejected, ids["t-milk-1"])])
    assert [m[0] for m in _mapping(db, rejected)] == [ids["t-milk-3"], ids["t-milk-1"]]
    # gold_pairs is for evaluation only: a no_match gold pair no longer blocks the judge.
    gold_only = add_item(db, "חלב טרי 3% 1 ליטר")
    db.execute(
        "INSERT INTO gold_pairs (item_id, canonical_id, label) VALUES (%s, %s, 'no_match')",
        (gold_only, ids["t-milk-3"]),
    )
    apply_decisions(db, [_decision(gold_only, ids["t-milk-3"])])
    assert _mapping(db, gold_only) == [(ids["t-milk-3"], "any_brand", 0.95, "rule", False)]

    reported = add_item(db, "חלב טרי 3% 1 ליטר")
    db.execute(
        "INSERT INTO substitution_feedback (canonical_id, substitute_item_id, verdict)"
        " VALUES (%s, %s, 'not_good')",
        (ids["t-milk-3"], reported),
    )
    apply_decisions(db, [_decision(reported, ids["t-milk-3"], conf=0.99)])
    assert _mapping(db, reported)[0][4] is True  # stays in the review queue


@pytest.mark.db
@pytest.mark.pgvector
def test_run_matching_end_to_end_and_rerun_is_idempotent(db) -> None:
    ids = seed_catalog(db)
    lex = Lexicon.from_mapping(LEXICON)
    milk = add_item(db, "חלב טרי 3% תנובה 1 ליטר")
    milk1 = add_item(db, "חלב טרי 1% טרה 1 ליטר")
    exact = add_item(db, "ח. טרי 3% 1 ל' שופרסל", barcode=MILK3_BARCODE)
    frozen = add_item(db, "פילה סלמון קפוא 800 גרם")
    soy = add_item(db, "משקה סויה אלפרו 1 ליטר")
    embed_all(db)
    results = {r.decision.item_id: r for r in run_matching(db, RuleJudge(), k=5, lexicon=lex)}

    assert results[exact].decision.flex_level == "exact"
    assert results[exact].decision.canonical_id == ids["t-milk-3"]
    assert results[milk].decision.canonical_id == ids["t-milk-3"]
    assert results[milk1].decision.canonical_id == ids["t-milk-1"]
    assert results[frozen].decision.canonical_id == ids["t-salmon-frozen"]
    assert results[soy].decision.canonical_id == ids["t-soy"]
    # The abbreviated name has no product type keyword: no taxonomy block, base unit only.
    assert results[exact].block.prefix is None and results[exact].block.base_unit == "100ml"
    for r in (results[i] for i in (milk, milk1, frozen, soy)):
        assert r.block.prefix is not None
        assert all(c.canonical.taxonomy_id.startswith(r.block.prefix) for c in r.candidates)

    snapshot = db.execute(
        "SELECT item_id, canonical_id, flex_level, confidence, source, needs_review"
        " FROM item_canonical ORDER BY 1, 2"
    ).fetchall()
    assert all(row[5] is not None and row[3] is not None for row in snapshot)
    run_matching(db, RuleJudge(), k=5, lexicon=lex)
    again = db.execute(
        "SELECT item_id, canonical_id, flex_level, confidence, source, needs_review"
        " FROM item_canonical ORDER BY 1, 2"
    ).fetchall()
    assert again == snapshot
    run = db.execute(
        "SELECT metrics FROM match_runs WHERE kind = 'judge' ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    assert run["items"] >= 5 and run["judge"] == "rule-v1"


@pytest.mark.db
def test_apply_decisions_stores_the_reason(db) -> None:
    ids = seed_catalog(db)
    it = add_item(db, "חלב טרי 3% 1 ליטר")
    d = _decision(it, ids["t-milk-3"]).model_copy(update={"reason": "accept: t-milk-3 | why"})
    apply_decisions(db, [d])
    assert db.execute("SELECT reason FROM item_canonical WHERE item_id = %s",
                      (it,)).fetchone()[0] == "accept: t-milk-3 | why"  # fmt: skip
    apply_decisions(db, [d.model_copy(update={"reason": "accept: again"})])
    assert db.execute("SELECT reason FROM item_canonical WHERE item_id = %s",
                      (it,)).fetchone()[0] == "accept: again"  # fmt: skip


@pytest.mark.db
@pytest.mark.pgvector
def test_the_judge_never_proposes_a_human_rejected_canonical(db) -> None:
    ids = seed_catalog(db)
    lex = Lexicon.from_mapping(LEXICON)
    it = add_item(db, "חלב טרי 3% תנובה 1 ליטר")
    embed_all(db)
    first = run_matching(db, RuleJudge(), [it], k=5, lexicon=lex)[0]
    assert first.decision.canonical_id == ids["t-milk-3"]
    db.execute("UPDATE item_canonical SET human_rejected = true, source = 'human',"
               " needs_review = true WHERE item_id = %s", (it,))  # fmt: skip
    ctx = load_items(db, [it], lex)[it]
    assert ctx.rejected == frozenset({ids["t-milk-3"]})
    again = run_matching(db, RuleJudge(), [it], k=5, lexicon=lex)[0]
    assert ids["t-milk-3"] not in [c.canonical_id for c in again.candidates]
    assert again.decision.canonical_id != ids["t-milk-3"]
    rows = db.execute("SELECT canonical_id, human_rejected FROM item_canonical"
                      " WHERE item_id = %s", (it,)).fetchall()  # fmt: skip
    assert (ids["t-milk-3"], True) in rows


@pytest.mark.db
def test_load_items_carries_barcode_chain_and_manufacturer(db) -> None:
    seed_catalog(db)
    it = add_item(db, "חלב טרי 3% 1 ליטר", barcode=MILK3_BARCODE)
    ctx = load_items(db, [it])[it]
    assert ctx.item.barcode == MILK3_BARCODE and ctx.item.chain_id == "test-match"
    assert ctx.item.raw_name == "חלב טרי 3% 1 ליטר"


def test_fallback_applies_the_lexicon_implied_base() -> None:
    lex = Lexicon.from_mapping({"product_types": {"soy_drink": {
        "keywords": ["משקה סויה"], "taxonomy_id": "dairy.plant_drinks",
        "implied": {"base": "soy"}}}})  # fmt: skip
    assert fallback_attributes("משקה סויה אלפרו 1 ליטר", lex).base == "soy"
    assert fallback_attributes("חלב 3% 1 ליטר", lex).base is None
