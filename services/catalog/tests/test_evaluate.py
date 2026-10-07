from __future__ import annotations

from contextlib import contextmanager

import pytest
from typer.testing import CliRunner

from smartcart_catalog import cli_matching
from smartcart_catalog.embed import HashEmbedder
from smartcart_catalog.evaluate import (
    Prediction,
    compute_metrics,
    format_report,
    load_gold,
    passes,
    run_evaluation,
)
from smartcart_catalog.judge import RuleJudge
from smartcart_catalog.models import EvaluationMetrics

# Hand-computed example (see the comments for each number).
GOLD = {
    (1, 10): "any_brand",
    (1, 11): "no_match",
    (2, 10): "no_match",
    (2, 11): "close",
    (3, 12): "exact",
    (4, 10): "no_match",  # item 4 is an orphan: no positive canonical
    (5, 13): "any_brand",
}
PREDICTIONS = [
    Prediction(1, 10, "any_brand"),  # correct
    Prediction(2, 10, "any_brand"),  # wrong: (2, 10) is no_match
    Prediction(3, 12, "exact"),  # correct
    Prediction(4, None, None),  # unmapped
    Prediction(5, 13, "any_brand", needs_review=True),  # review queue: not served
]
RETRIEVED = {1: [10, 11], 2: [10], 3: [12], 4: [10], 5: [14, 15]}


def test_metric_arithmetic_on_a_hand_computed_set() -> None:
    report = compute_metrics(GOLD, PREDICTIONS, RETRIEVED)
    m = report.metrics
    # exact: served exact predictions {3}, all correct; gold exact items {3}.
    assert m.precision["exact"] == 1.0 and m.recall["exact"] == 1.0
    # any_brand: served at exact|any_brand {1, 2, 3}, correct {1, 3}; gold items {1, 3, 5}.
    assert m.precision["any_brand"] == pytest.approx(2 / 3)
    assert m.recall["any_brand"] == pytest.approx(2 / 3)
    # close: served {1, 2, 3}, correct {1, 3}; gold items {1, 2, 3, 5}.
    assert m.precision["close"] == pytest.approx(2 / 3)
    assert m.recall["close"] == pytest.approx(2 / 4)
    # recall@k: items with a positive {1, 2, 3, 5}; positive retrieved for {1, 3}.
    assert m.recall_at_k == pytest.approx(0.5)
    assert m.support["any_brand"] == 3 and m.support["predicted_any_brand"] == 3
    assert (m.support["served"], m.support["review"], m.support["unmapped"]) == (3, 1, 1)
    assert m.support["items"] == 5 and m.support["pairs"] == 7
    # If the review queue were auto-accepted: {1, 2, 3, 5} at any_brand, correct {1, 3, 5}.
    assert report.extra["any_brand_precision_if_review_auto_accepted"] == pytest.approx(3 / 4)
    assert not passes(m, 0.98) and passes(m, 0.6)


def test_levels_without_predictions_have_no_precision_and_fail_the_gate() -> None:
    report = compute_metrics(GOLD, [Prediction(1, None, None)], {})
    assert report.metrics.precision == {}
    assert report.metrics.recall["any_brand"] == 0.0
    assert report.metrics.recall_at_k is None
    assert not passes(report.metrics, 0.98)
    assert "n/a" in format_report(report)
    assert not passes(EvaluationMetrics(), 0.0)


@pytest.mark.db
@pytest.mark.pgvector
def test_harness_on_the_gold_set_saves_the_run(db) -> None:
    first = load_gold(db)
    again = load_gold(db)
    assert first == again and 2000 <= first["pairs"] <= 3000
    n_pairs = db.execute(
        "SELECT count(*) FROM gold_pairs gp JOIN items i ON i.id = gp.item_id"
        " WHERE i.chain_id = 'gold'"
    ).fetchone()[0]
    assert n_pairs == first["pairs"]

    report = run_evaluation(db, RuleJudge(), HashEmbedder(), k=10, load=False)
    m = report.metrics
    assert set(m.precision) == {"exact", "any_brand", "close"}
    assert m.precision["any_brand"] >= 0.98  # synthetic set; see docs/matching.md
    assert m.recall_at_k is not None and m.recall_at_k > 0.9
    assert report.extra["synthetic_gold_set"] is True
    saved = db.execute(
        "SELECT kind, finished_at IS NOT NULL, metrics FROM match_runs WHERE id = %s",
        (m.run_id,),
    ).fetchone()
    assert saved[0] == "evaluate" and saved[1]
    assert saved[2]["precision"]["any_brand"] == m.precision["any_brand"]
    assert saved[2]["recall"] == m.recall and saved[2]["embedder"] == HashEmbedder().model_name
    text = format_report(report)
    assert "synthetic" in text and "recall@10" in text


class _NoCommit:
    """Proxy for the test connection: the CLI's commit must not end the test transaction."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def commit(self) -> None:
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.mark.db
@pytest.mark.pgvector
def test_cli_evaluate_fail_below_exit_codes(db, monkeypatch) -> None:
    @contextmanager
    def fake_connect():
        yield _NoCommit(db)

    monkeypatch.setattr(cli_matching, "_connect", fake_connect)
    runner = CliRunner()
    ok = runner.invoke(cli_matching.app, ["evaluate", "--fail-below", "0.98", "--embedder", "hash"])
    assert ok.exit_code == 0, ok.output
    assert "any_brand" in ok.output and "recall@10" in ok.output
    fail = runner.invoke(cli_matching.app, ["evaluate", "--no-load", "--fail-below", "1.01"])
    assert fail.exit_code == 1
    as_json = runner.invoke(cli_matching.app, ["evaluate", "--no-load", "--json"])
    assert as_json.exit_code == 0 and '"precision"' in as_json.output


def test_register_adds_the_four_commands() -> None:
    import typer

    app = typer.Typer()
    cli_matching.register(app)
    names = {c.name for c in app.registered_commands}
    assert names == {"embed", "judge", "evaluate", "review"}
