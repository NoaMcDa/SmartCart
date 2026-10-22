# exit-window/data

Data branch of the Phase 0 exit window rehearsal on GitHub runners (issue #60). Not code, and
not the VPS window. One file per Israel date, `records/<YYYY-MM-DD>.json`, appended by the
`Exit window` workflow (`.github/workflows/exit-window.yml`) and never rewritten; the schema
is `scripts/exit_window/window_record.py` on `main`, and
`python scripts/exit_window/report.py --data .` turns the records into the report
(`docs/exit-window.md`).
