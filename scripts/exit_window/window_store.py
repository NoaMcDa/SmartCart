"""The data directory of the exit window: one record file per day, appended idempotently.

The data lives on the git branch ``exit-window/data`` (``records/<YYYY-MM-DD>.json`` plus a
README). This module only touches files; the workflow does the git work (check the branch out
into a directory, call ``append``, commit, push), so it can be tested without git.

* ``append_record`` never overwrites: a second record for a date that already has one is left
  alone and reported as ``exists`` (a re-run of the same day, a manual dispatch after the
  scheduled run). ``replace=True`` is the one explicit exception, for a deliberate re-run; the
  branch history still keeps the old file because the change is an ordinary new commit.
* Files are written atomically (a temporary file in the same directory, then a rename), so an
  interrupted write never leaves half a record that a later run would call ``exists``.
* ``load_records`` validates every file and returns the problems next to the records instead of
  raising, so one corrupt file cannot hide the rest of the window from the report.

    python scripts/exit_window/window_store.py append --data DIR --record record.json [--replace]
    python scripts/exit_window/window_store.py check  --data DIR
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import window_record as rec  # noqa: E402

RECORDS_DIR = "records"
ADDED = "added"
EXISTS = "exists"
REPLACED = "replaced"


def record_path(data_dir: Path, day: str) -> Path:
    """``<data>/records/<day>.json``; ``day`` must be a plain calendar date (no path parts)."""
    if not rec.DATE_RE.match(day):
        raise rec.RecordError(f"not a date: {day!r}")
    return data_dir / RECORDS_DIR / f"{day}.json"


def _dump(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def append_record(data_dir: Path, record: dict, replace: bool = False) -> tuple[str, Path]:
    """Write the record of ``record['date']`` unless that day already has one.

    Returns ``(status, path)`` with status ``added``, ``exists`` (nothing written) or
    ``replaced``. The record is validated first; an invalid one raises ``RecordError`` and
    writes nothing."""
    rec.validate_record(record)
    path = record_path(data_dir, record["date"])
    existed = path.exists()
    if existed and not replace:
        return EXISTS, path
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(_dump(record))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return (REPLACED if existed else ADDED), path


def load_records(data_dir: Path) -> tuple[list[dict], list[str]]:
    """Every valid record under ``<data>/records``, oldest date first, and one message per file
    that could not be used (unreadable JSON, schema violation, file name not matching its date)."""
    folder = data_dir / RECORDS_DIR
    records: list[dict] = []
    problems: list[str] = []
    if not folder.is_dir():
        return records, problems
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rec.validate_record(data)
            if path.stem != data["date"]:
                raise rec.RecordError(f"file name {path.name} does not match date {data['date']}")
        except (OSError, ValueError) as exc:  # JSONDecodeError and RecordError are ValueErrors
            problems.append(f"{path.name}: {exc}")
            continue
        records.append(data)
    records.sort(key=lambda r: r["date"])
    return records, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append", help="add one day's record (idempotent per date)")
    a.add_argument("--data", type=Path, required=True, help="checkout of the data branch")
    a.add_argument("--record", type=Path, required=True)
    a.add_argument("--replace", action="store_true", help="overwrite that day's file")
    c = sub.add_parser("check", help="validate every record in the data directory")
    c.add_argument("--data", type=Path, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "check":
        records, problems = load_records(args.data)
        print(f"{len(records)} valid record(s), {len(problems)} problem(s)")
        for p in problems:
            print(f"  {p}")
        return 1 if problems else 0

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        status, path = append_record(args.data, record, replace=args.replace)
    except (OSError, ValueError) as exc:
        print(f"cannot append: {exc}", file=sys.stderr)
        return 2
    print(f"{status} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
