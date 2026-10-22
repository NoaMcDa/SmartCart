"""Tests for the exit window report generator (issue #60). Offline, on fixture records."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import exit_window_testkit as kit  # noqa: E402
import window_store as ws  # noqa: E402

# report.py shares its name with smartcart_ingest.report: load it by path under its own name.
_spec = importlib.util.spec_from_file_location("exit_window_report", HERE.parents[0] / "report.py")
assert _spec and _spec.loader
report = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = report
_spec.loader.exec_module(report)

NOON = datetime(2026, 11, 5, 12, 0)


def fortnight(modes_by_day: dict[str, dict[str, str]] | None = None, n: int = 14,
              start: str = "2026-10-23", skip_days: tuple[str, ...] = ()) -> list[dict]:  # fmt: skip
    modes_by_day = modes_by_day or {}
    return [
        kit.make_record(d, modes_by_day.get(d)) for d in kit.days(start, n) if d not in skip_days
    ]


def test_fourteen_perfect_days_meet_the_criterion() -> None:
    win = report.build_window(fortnight())
    assert win.window_days == 14 and win.missing_days == []
    assert win.success_rate == 1.0
    assert (win.longest_streak, win.streak_start, win.streak_end) == (
        14, date(2026, 10, 23), date(2026, 11, 5),
    )  # fmt: skip
    assert win.best_window_rate == 1.0 and win.meets_criterion
    text = report.render(fortnight(), [], generated_at=NOON)
    assert "| 1. More than 95.0% nightly loads over 14 consecutive days | **met** |" in text


def test_thirteen_days_are_not_enough_even_if_perfect() -> None:
    win = report.build_window(fortnight(n=13))
    assert win.success_rate == 1.0 and win.best_window_rate is None and not win.meets_criterion
    text = report.render(fortnight(n=13), [], generated_at=NOON)
    assert "**not met: 13 of 14 days so far**" in text


def test_one_failed_chain_day_matches_the_documented_139_of_140() -> None:
    # services/ingest/tests/test_report.py: a fortnight with one failure day gives 139 of 140.
    recs = fortnight({"2026-10-27": {"victory": "unreachable"}})
    win = report.build_window(recs)
    assert sum(c.successes for c in win.chains) == 139
    assert win.success_rate == pytest.approx(139 / 140)
    assert win.meets_criterion  # 99.3% is above 95% over the 14 days
    assert win.longest_streak == 9  # 10-28 to 11-05: the failure day breaks the day streak
    assert (win.streak_start, win.streak_end) == (date(2026, 10, 28), date(2026, 11, 5))


def test_chains_a_runner_cannot_reach_count_as_failures_with_the_reason() -> None:
    down = {"victory": "unreachable", "hazihinam": "unreachable", "machsanei_hashuk": "unreachable"}
    recs = fortnight({d: down for d in kit.days("2026-10-23", 14)})
    win = report.build_window(recs)
    assert win.success_rate == pytest.approx(0.7)
    assert win.longest_streak == 0 and not win.meets_criterion
    text = report.render(recs, [], generated_at=NOON)
    assert "**not met**" in text
    assert "70.0%" in text
    # information only: the rate over the chains reached from a runner is stated separately
    assert "Information only, not the criterion: over the 7 chain(s)" in text
    assert "7 of 7" not in text and "98 of 98 chain-days loaded (100.0%)" in text
    assert "The others: Victory, Hazi Hinam, Machsanei Hashuk." in text
    # and the reason is the real one, not a generic failure
    assert "portal unreachable from the runner (http 0)" in text
    assert "TimeoutError: connection timed out" in text


def test_a_day_without_a_record_is_a_failure_of_every_chain() -> None:
    recs = fortnight(skip_days=("2026-10-29",))
    win = report.build_window(recs)
    assert win.window_days == 14 and win.missing_days == [date(2026, 10, 29)]
    assert sum(c.successes for c in win.chains) == 130
    assert win.success_rate == pytest.approx(130 / 140)
    assert not win.meets_criterion  # 92.9%
    text = report.render(recs, [], generated_at=NOON)
    assert "`--` = no record for the day" in text
    assert "no record for this day" in text
    assert "(1 day(s) without one)" in text


def test_a_chain_missing_from_a_record_is_a_failure_not_a_smaller_denominator() -> None:
    recs = [kit.make_record(d, skip=("king_store",)) for d in kit.days("2026-10-23", 14)]
    win = report.build_window(recs)
    assert win.success_rate == pytest.approx(0.9)
    assert not win.meets_criterion
    king = next(c for c in win.chains if c.chain.name == "King Store")
    assert king.successes == 0
    assert any("not in that day's record" in r for r in win.failure_reasons.values())


def test_the_best_fourteen_day_window_is_found_inside_a_longer_history() -> None:
    bad = {"victory": "unreachable", "hazihinam": "unreachable"}
    first_week = {d: bad for d in kit.days("2026-10-20", 3)}
    recs = fortnight(first_week, n=17, start="2026-10-20")
    win = report.build_window(recs)
    assert win.window_days == 17 and win.success_rate < 1.0
    assert win.best_window_rate == 1.0 and win.best_window_start == date(2026, 10, 23)
    assert win.meets_criterion


def test_end_cuts_the_window_and_later_records_are_ignored() -> None:
    recs = fortnight()
    win = report.build_window(recs, end=date(2026, 11, 1))
    assert win.end == date(2026, 11, 1) and win.window_days == 10
    assert max(win.records) == date(2026, 11, 1)
    with pytest.raises(ValueError):
        report.build_window(recs, end=date(2026, 10, 1))
    with pytest.raises(ValueError):
        report.build_window([])


def test_the_report_is_labelled_a_rehearsal_and_keeps_the_no_go() -> None:
    text = report.render(fortnight(n=2), [], generated_at=NOON)
    assert text.startswith("# Phase 0 exit window, runner rehearsal: 2026-10-23 to 2026-10-24")
    assert "**Runner rehearsal, not the VPS window.**" in text
    assert "may be pasted into that report as evidence" in text
    assert "**NO-GO**" in text
    assert "Runner IP country per record: US (2)." in text
    for heading in ("## Criteria of issue #60", "## 1. Nightly loads", "## 2. The latest record,",
                    "## 3. Promo parsing and store coordinates"):  # fmt: skip
        assert heading in text
    # criteria 2 to 4 are not claimed from a rehearsal
    assert text.count("not evaluable here") == 2 and "not evaluated here" in text
    assert "Every full file of every chain in the window loaded." in text


def test_publication_hours_ages_and_causes_are_tallied() -> None:
    modes = {d: {"shufersal": "stale", "tivtaam": "failed"} for d in kit.days("2026-10-23", 3)}
    recs = fortnight(modes, n=3)
    text = report.render(recs, [], generated_at=NOON)
    assert "| Shufersal | 3 | 3 | 3 | 0 | 3 | 0 | 05:10 to 05:10 (median 05:10) | 40.0 h |" in text
    # the digits are masked so the same cause groups across days
    assert "| Shufersal | 3 | price_full quarantined: stale_date |" in text
    assert "| Tiv Taam | 3 | promo_full failed: parse error: boom |" in text
    assert "| Osher Ad | 3 | 3 | 3 | 3 | 0 | 0 | 05:10 to 05:10 (median 05:10) | 3.5 h |" in text


def test_promo_and_store_counts_come_from_the_latest_record() -> None:
    text = report.render(fortnight(n=2), [], generated_at=NOON)
    assert "| Shufersal (main) | 40 | 25.0% | other 10, price 30 | 40 of 50 |" in text
    assert "| Osher Ad | 40 | 25.0% |" in text


def test_unusable_records_are_listed_and_an_empty_data_set_is_stated() -> None:
    text = report.render(fortnight(n=1), ["2026-10-25.json: kind: bad"], generated_at=NOON)
    assert "## Records that could not be used" in text and "2026-10-25.json: kind: bad" in text
    empty = report.render([], ["x.json: broken"])
    assert "No records yet." in empty and "x.json: broken" in empty


def test_cell_text_from_records_cannot_break_a_table_row() -> None:
    recs = fortnight(n=1)
    recs[0]["chains"]["mega"]["files"]["price_full"].update(
        status="failed", failed=True, loaded=False, reason="a | b\nc"
    )
    recs[0]["chains"]["mega"]["files"]["promo_full"].update(
        status="failed", failed=True, loaded=False, reason="x"
    )
    recs[0]["chains"]["mega"].update(full_loaded=False, failure="a | b\nc", failed=2, loaded=1)
    text = report.render(recs, [], generated_at=NOON)
    assert "a \\| b c" in text
    assert "a | b\nc" not in text


def test_the_cli_reads_the_data_directory_and_writes_the_file(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    data = tmp_path / "data"
    for rec in fortnight(n=3):
        ws.append_record(data, rec)
    out = tmp_path / "out" / "report.md"
    assert report.main(["--data", str(data), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Phase 0 exit window, runner rehearsal")
    assert report.main(["--data", str(data), "--end", "2026-10-24"]) == 0
    assert "2026-10-23 to 2026-10-24" in capsys.readouterr().out
    # an empty branch is not an error: the first run of the workflow prints this
    assert report.main(["--data", str(tmp_path / "nothing")]) == 0
    assert "No records yet." in capsys.readouterr().out
