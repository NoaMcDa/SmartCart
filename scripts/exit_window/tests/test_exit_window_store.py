"""Tests for the idempotent append of exit window records (issue #60). No network, no database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import exit_window_testkit as kit  # noqa: E402
import window_record as wr  # noqa: E402
import window_store as ws  # noqa: E402


def test_first_append_adds_one_file_named_by_date(tmp_path: Path) -> None:
    status, path = ws.append_record(tmp_path, kit.make_record("2026-10-22"))
    assert status == ws.ADDED
    assert path == tmp_path / "records" / "2026-10-22.json"
    assert json.loads(path.read_text(encoding="utf-8"))["date"] == "2026-10-22"
    assert [p.name for p in (tmp_path / "records").iterdir()] == ["2026-10-22.json"]


def test_a_second_append_for_the_same_date_changes_nothing(tmp_path: Path) -> None:
    ws.append_record(tmp_path, kit.make_record("2026-10-22", country="US"))
    path = tmp_path / "records" / "2026-10-22.json"
    before = path.read_bytes()
    different = kit.make_record("2026-10-22", {"victory": "unreachable"}, country="DE")
    status, again = ws.append_record(tmp_path, different)
    assert (status, again) == (ws.EXISTS, path)
    assert path.read_bytes() == before  # the first record of the day stands
    assert len(list((tmp_path / "records").iterdir())) == 1  # and no temporary file is left


def test_replace_is_the_one_explicit_overwrite(tmp_path: Path) -> None:
    ws.append_record(tmp_path, kit.make_record("2026-10-22", country="US"))
    status, path = ws.append_record(
        tmp_path, kit.make_record("2026-10-22", country="DE"), replace=True
    )
    assert status == ws.REPLACED
    assert json.loads(path.read_text(encoding="utf-8"))["run"]["runner_ip_country"] == "DE"
    # replace on a day without a record is an ordinary add
    status, _ = ws.append_record(tmp_path, kit.make_record("2026-10-23"), replace=True)
    assert status == ws.ADDED


def test_an_invalid_record_writes_nothing(tmp_path: Path) -> None:
    rec = kit.make_record("2026-10-22")
    rec["chains"]["mega"]["full_loaded"] = False
    with pytest.raises(wr.RecordError):
        ws.append_record(tmp_path, rec)
    assert not (tmp_path / "records").exists()


@pytest.mark.parametrize("day", ["../x", "2026-10-22/../../x", "", "2026-1-2", "x"])
def test_a_date_cannot_escape_the_records_folder(tmp_path: Path, day: str) -> None:
    with pytest.raises(wr.RecordError):
        ws.record_path(tmp_path, day)


def test_the_interrupted_write_leaves_no_half_record(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    def boom(*_a, **_k):  # noqa: ANN002, ANN003
        raise OSError("disk full")

    monkeypatch.setattr(ws.os, "replace", boom)
    with pytest.raises(OSError):
        ws.append_record(tmp_path, kit.make_record("2026-10-22"))
    assert list((tmp_path / "records").iterdir()) == []
    monkeypatch.undo()
    # so the retry of the same day is an add, not "exists"
    assert ws.append_record(tmp_path, kit.make_record("2026-10-22"))[0] == ws.ADDED


def test_hebrew_and_other_text_is_stored_as_it_is(tmp_path: Path) -> None:
    rec = kit.make_record("2026-10-22")
    rec["alerts"] = [{"chain_id": "7290027600007", "kind": "quarantine", "message": "שופרסל ₪"}]
    _, path = ws.append_record(tmp_path, rec)
    assert "שופרסל ₪" in path.read_text(encoding="utf-8")


def test_load_records_sorts_by_date_and_reports_problems(tmp_path: Path) -> None:
    for day in ("2026-10-24", "2026-10-22", "2026-10-23"):
        ws.append_record(tmp_path, kit.make_record(day))
    folder = tmp_path / "records"
    (folder / "2026-10-25.json").write_text("{not json", encoding="utf-8")
    bad = kit.make_record("2026-10-26")
    bad["kind"] = "nope"
    (folder / "2026-10-26.json").write_text(json.dumps(bad), encoding="utf-8")
    (folder / "2026-10-27.json").write_text(
        json.dumps(kit.make_record("2026-10-28")), encoding="utf-8"
    )  # file name and date disagree
    records, problems = ws.load_records(tmp_path)
    assert [r["date"] for r in records] == ["2026-10-22", "2026-10-23", "2026-10-24"]
    assert len(problems) == 3
    assert any(p.startswith("2026-10-25.json") for p in problems)
    assert any("kind" in p for p in problems)
    assert any("does not match date" in p for p in problems)


def test_load_records_of_an_empty_or_missing_folder(tmp_path: Path) -> None:
    assert ws.load_records(tmp_path) == ([], [])
    (tmp_path / "records").mkdir()
    assert ws.load_records(tmp_path) == ([], [])


def test_cli_append_check_and_exit_codes(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    data = tmp_path / "data"
    record = tmp_path / "record.json"
    record.write_text(json.dumps(kit.make_record("2026-10-22")), encoding="utf-8")
    assert ws.main(["append", "--data", str(data), "--record", str(record)]) == 0
    assert capsys.readouterr().out.startswith("added ")
    assert ws.main(["append", "--data", str(data), "--record", str(record)]) == 0
    assert capsys.readouterr().out.startswith("exists ")  # the workflow reads this first word
    assert ws.main(["append", "--data", str(data), "--record", str(record), "--replace"]) == 0
    assert capsys.readouterr().out.startswith("replaced ")
    assert ws.main(["check", "--data", str(data)]) == 0
    assert "1 valid record(s), 0 problem(s)" in capsys.readouterr().out

    record.write_text("[]", encoding="utf-8")
    assert ws.main(["append", "--data", str(data), "--record", str(record)]) == 2
    assert ws.main(["append", "--data", str(data), "--record", str(tmp_path / "missing")]) == 2
    (data / "records" / "2026-10-23.json").write_text("{", encoding="utf-8")
    assert ws.main(["check", "--data", str(data)]) == 1
