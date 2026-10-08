"""The Arabic evaluation harness: metric arithmetic, the query set and the CLI command (issue #73)."""

from __future__ import annotations

import typer
from typer.testing import CliRunner

from smartcart_catalog.cli_arabic import app as standalone_app
from smartcart_catalog.cli_arabic import register
from smartcart_catalog.evaluate_ar import (
    ArLine,
    Outcome,
    compute,
    format_report,
    load_lines,
    passes,
)
from smartcart_catalog.normalize import ar_clean_query, normalize_ar
from smartcart_catalog.seed import load_catalog


def _o(expect: str, got: str | None, conf: float = 0.95, flex: str = "any_brand",
       holdout: bool = False, candidates: bool = False) -> Outcome:  # fmt: skip
    served = got is not None and conf >= 0.75
    return Outcome(
        line=ArLine("q", expect, flex, holdout),
        slug=got,
        confidence=conf,
        rows=1,
        served=served,
        shown=got is not None and conf >= 0.35,
        correct=served and expect != "none" and got == expect,
        in_candidates=candidates,
    )


def test_precision_and_recall_per_level() -> None:
    report = compute([
        _o("a", "a"), _o("b", "b"), _o("c", "x"),        # any_brand: 2 of 3 served right
        _o("none", None, 0.0),                           # not served, expected none: neither
        _o("d", "d", flex="exact"),
        _o("e", "e", conf=0.6, flex="close", candidates=True),  # below the floor: not served
    ])  # fmt: skip
    assert report.precision["any_brand"] == 2 / 3
    assert report.recall["any_brand"] == 2 / 3  # 2 of the 3 lines that expect a slug
    assert report.precision["exact"] == 1.0 and report.recall["exact"] == 1.0
    assert "close" not in report.precision  # nothing served at that level: n/a
    assert report.recall["close"] == 0.0
    assert report.precision["all"] == 3 / 4
    assert report.extra["recall_with_candidates"] == 4 / 5  # a, b, d, e (suggested); c, wrong


def test_a_none_line_that_is_served_is_wrong() -> None:
    report = compute([_o("a", "a"), _o("none", "a")])
    assert report.precision["any_brand"] == 0.5
    assert report.extra["none_lines_served"] == 1
    assert "WRONG" in format_report(report)


def test_gate_treats_a_missing_level_as_a_failure() -> None:
    report = compute([_o("e", "e", conf=0.6)])
    assert not passes(report, 0.98)
    assert passes(compute([_o("a", "a")]), 0.98)
    assert not passes(compute([_o("a", "a"), _o("none", "a")]), 0.98)


def test_holdout_is_reported_separately() -> None:
    report = compute([_o("a", "a"), _o("b", "b", holdout=True), _o("none", "b", holdout=True)])
    assert report.extra["holdout_lines"] == 2
    assert report.extra["holdout_precision"] == 0.5
    assert report.extra["holdout_recall"] == 1.0
    assert "held-out" in format_report(report)


def test_report_says_it_is_synthetic() -> None:
    assert "synthetic" in format_report(compute([_o("a", "a")]))
    assert compute([_o("a", "a")]).to_json()["synthetic"] is True


# --- the query set --------------------------------------------------------------------------------


def test_query_set_is_well_formed() -> None:
    lines = load_lines()
    slugs = {c.slug for c in load_catalog().canonicals}
    assert len(lines) >= 300
    assert {ln.flex for ln in lines} == {"exact", "any_brand", "close"}
    assert all(ln.expect == "none" or ln.expect in slugs for ln in lines)
    assert len({ln.q for ln in lines}) == len(lines)  # no line twice
    none = sum(1 for ln in lines if ln.expect == "none")
    assert 0.15 < none / len(lines) < 0.5  # attribute traps, too general, not in the catalog
    assert any(ln.holdout for ln in lines) and not all(ln.holdout for ln in lines)


def test_every_canonical_is_asked_for_at_least_once() -> None:
    asked = {ln.expect for ln in load_lines()}
    missing = {c.slug for c in load_catalog().canonicals} - asked
    assert not missing, sorted(missing)


def test_attribute_sensitive_pairs_are_in_the_set() -> None:
    qs = {ln.q: ln.expect for ln in load_lines()}
    assert qs["حليب 3%"] == "milk-fresh-3" and qs["حليب 1%"] == "milk-fresh-1"
    assert qs["حليب لوز"] == "almond-drink" and qs["حليب صويا"] == "soy-drink"
    assert qs["صدر دجاج مجمد"] == "chicken-breast-frozen"
    assert qs["حليب 2%"] == "none"


def test_names_survive_the_query_cleaning() -> None:
    # a canonical's own name, typed as a query, keeps its words (nothing is dropped as filler)
    for c in load_catalog().canonicals:
        for name in c.names_ar:
            assert ar_clean_query(normalize_ar(name)) == normalize_ar(name), (c.slug, name)


# --- the command ----------------------------------------------------------------------------------


def test_command_registers_on_the_catalog_cli() -> None:
    app = typer.Typer()
    register(app)
    assert [c.name for c in app.registered_commands] == ["evaluate-ar"]


def test_standalone_cli_lists_the_command() -> None:
    result = CliRunner().invoke(standalone_app, ["--help"])
    assert result.exit_code == 0 and "evaluate-ar" in result.output
