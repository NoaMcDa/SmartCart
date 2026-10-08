"""The machine audit on real chain items (``smartcart-catalog audit-real``).

The audit is a MACHINE audit: a reader judged each accepted mapping once. These tests keep the
tooling honest (every accepted mapping has a verdict, the verdict file says what it is, the
statistics are the ones documented) and keep the errors the audit found from coming back.
"""

from __future__ import annotations

import csv

import pytest
from typer.testing import CliRunner

from smartcart_catalog import audit_real
from smartcart_catalog.audit_real import (
    AUDIT_DIR,
    COLUMNS,
    HEADER,
    VERDICTS_NAME,
    LevelStats,
    Verdict,
    load_verdicts,
    relabel_csv,
    run_audit,
    write_csv,
)
from smartcart_catalog.cli import app
from smartcart_catalog.review_packet import load_real_items


@pytest.fixture(scope="module")
def items():
    found = load_real_items()
    if not found:
        pytest.skip("real fixtures not present")
    return found


@pytest.fixture(scope="module")
def report(items):
    return run_audit(items=items)


def test_every_real_item_gets_a_row_and_the_counts_add_up(items, report) -> None:
    assert report.items == len(items) == len(report.rows)
    assert report.mapped == report.served + report.to_review
    assert report.served == sum(s.served for s in report.by_level.values())
    assert 0 < report.served < report.mapped < report.items


def test_every_accepted_mapping_has_a_machine_verdict(report) -> None:
    unlabeled = [r.match.item.raw_name for r in report.rows if r.served and r.verdict is None]
    assert unlabeled == [], "read these accepted mappings and add them to machine_verdicts.csv"
    assert report.overall.unlabeled == 0


def test_no_accepted_mapping_is_judged_wrong_after_the_rules(report) -> None:
    wrong = [(r.match.item.raw_name, r.match.canonical_slug) for r in report.rows
             if r.verdict and r.verdict.verdict == "wrong"]  # fmt: skip
    assert wrong == []


@pytest.mark.parametrize(
    "raw_name",
    [
        "נקטר ספרינג עגבניות",  # a tomato nectar served as tomatoes
        "עגבניות חתוכות פולפה",  # canned crushed tomatoes served as fresh
        "שעועית לבנה ברוטב מב",  # beans in sauce served as dry beans
        "פפריקה מתוקה בשמן 45",  # paprika paste served as the spice
        "שוקולד מריר לינדט מלח 10",  # salted dark chocolate served as the plain bar
        "סבון נוזלי לתינוק",  # baby soap served as adult hand soap
    ],
)
def test_the_first_audits_wrong_mappings_are_no_longer_served(report, raw_name) -> None:
    served = [r.match.canonical_slug for r in report.rows
              if r.match.item.raw_name == raw_name and r.served]  # fmt: skip
    assert served == []


def test_precision_counts_unsure_separately() -> None:
    s = LevelStats(correct=8, wrong=2, unsure=5, unlabeled=1)
    assert s.labeled == 10
    assert s.served == 16
    assert s.precision == pytest.approx(0.8)
    assert LevelStats(unsure=3).precision is None


def test_the_csv_says_it_is_a_machine_audit_and_has_the_documented_columns(report, tmp_path) -> None:
    out = tmp_path / "real.csv"
    write_csv(report, out)
    text = out.read_text(encoding="utf-8-sig")
    head = [ln for ln in text.splitlines() if ln.startswith("#")]
    assert head == list(HEADER)
    assert any("MACHINE AUDIT" in ln and "not a gold set" in ln for ln in head)
    rows = list(csv.DictReader(ln for ln in text.splitlines() if not ln.startswith("#")))
    assert tuple(rows[0].keys()) == COLUMNS
    assert len(rows) == report.items
    served = [r for r in rows if r["served"]]
    assert len(served) == report.served
    assert all(r["machine_verdict"] in {"correct", "wrong", "unsure"} for r in served)
    assert all(r["needs_review"] == "" for r in served)
    assert all(r["machine_verdict"] == "" for r in rows if not r["served"])


def test_a_truncated_name_is_marked(report) -> None:
    cut = [r for r in report.rows if r.truncated]
    assert cut and all(r.match.item.chain_name != "קינג סטור" for r in cut)
    assert [r for r in report.rows if r.match.item.chain_name == "קינג סטור" and r.truncated] == []


def test_relabel_rewrites_the_verdicts_of_an_earlier_audit(report, tmp_path) -> None:
    out = tmp_path / "earlier.csv"
    write_csv(report, out)
    served = next(r for r in report.rows if r.served)
    flipped = {served.key: Verdict("wrong", "test")}
    after = relabel_csv(out, flipped)
    assert after.overall.wrong == 1
    assert after.overall.unlabeled == report.served - 1
    text = out.read_text(encoding="utf-8-sig")
    assert text.count(",wrong,test") == 1


def test_verdict_file_is_valid_and_labeled_as_a_machine_audit() -> None:
    path = AUDIT_DIR / VERDICTS_NAME
    head = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("#")]
    assert any("MACHINE AUDIT" in ln and "not a gold set" in ln for ln in head)
    verdicts = load_verdicts(path)
    assert verdicts
    assert {v.verdict for v in verdicts.values()} <= {"correct", "wrong", "unsure"}
    assert all(v.reason for v in verdicts.values())


def test_bad_verdict_is_rejected(tmp_path) -> None:
    bad = tmp_path / "v.csv"
    bad.write_text("item_key,canonical_slug,verdict,reason\nx:1,tomato,maybe,why\n", encoding="utf-8")
    with pytest.raises(ValueError, match="verdict must be one of"):
        load_verdicts(bad)


def test_cli_audit_real_writes_the_file_and_prints_precision(tmp_path) -> None:
    out = tmp_path / "audit.csv"
    result = CliRunner().invoke(app, ["audit-real", "--out", str(out), "--require-verdicts"])
    assert result.exit_code == 0, result.output
    assert "NOT a gold set" in result.output
    assert "any_brand" in result.output and "precision" in result.output
    assert out.exists()


def test_cli_rejects_a_bad_date(tmp_path) -> None:
    result = CliRunner().invoke(app, ["audit-real", "--date", "yesterday", "--out", str(tmp_path / "x.csv")])
    assert result.exit_code != 0


def test_module_registers_itself_once() -> None:
    names = [c.name for c in app.registered_commands]
    assert names.count("audit-real") == 1
    assert audit_real.register is not None
