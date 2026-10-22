"""The Phase 0 exit report for the runner exit window (issue #60), from the accumulated records.

Reads the daily records of ``exit-window/data`` (``records/<date>.json``, written by
``run_day.py``, schema in ``window_record.py``) and writes a Markdown report. It reuses the exit
report code of ``smartcart_ingest.report`` (the D13 chain list, ``ChainLoads``, ``DaySummary``,
``FailedFile``, ``longest_streak``, the 95 percent and 14 day constants and the table helpers) but
takes **records as input instead of a database**: the nightly database was a throwaway, so what it
held is in the record.

**This is a runner rehearsal, not the VPS window**, and the report says so at the top. It cannot
be pasted into ``docs/phase-0-exit-report.md`` as evidence. What it does show, measured: which
chains a GitHub runner reaches, which files pass the adapters and the gates with the real clock,
when the chains publish, and how long a night takes.

How criterion 1 is evaluated here, and where it differs from ``smartcart_ingest.report`` (all of it
stated again in the generated text):

* A (chain, day) succeeds when the rehearsal of that Israel date loaded a ``price_full`` or
  ``promo_full`` file of the chain through the real Scheduler path. The VPS report attributes a file
  to the Israel date of its ``published_at``; here the date is the date of the run (a file
  published late the evening before and loaded this morning counts for this morning).
* Every D13 chain counts. A chain a runner cannot reach, or one the record does not contain, is a
  failure with the reason, never dropped from the denominator. A day between the first and the
  last record that has no record counts as a failure of every chain ("no record").
* The criterion is met when some 14 consecutive days all have a record and the success rate over
  them is above 95 percent. With ten chains that means every chain on every one of the days.
* A second figure, "chains reached from a runner", is information only: the rate over the chains
  that produced a full file at least once. It is not the criterion.

    python scripts/exit_window/report.py --data DIR [--out report.md] [--end 2026-11-05]
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import window_record as wr  # noqa: E402
import window_store as ws  # noqa: E402

from smartcart_ingest.report import (  # noqa: E402
    D13_CHAINS,
    REQUIRED_WINDOW_DAYS,
    SUCCESS_THRESHOLD,
    ChainLoads,
    ChainSpec,
    DaySummary,
    FailedFile,
    _pct,
    _table,
    longest_streak,
)

NO_RECORD = "no record for this day (the nightly run did not finish or its record was not saved)"
NOT_IN_RECORD = "the chain is not in that day's record (the run was limited to other chains)"
MAX_FAILURE_ROWS = 40


# --- computation -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    start: date
    end: date
    chains: list[ChainLoads]
    days: list[DaySummary]
    success_rate: float
    longest_streak: int
    streak_start: date | None
    streak_end: date | None
    best_window_rate: float | None  # best rate over 14 consecutive days (None: fewer days)
    best_window_start: date | None
    meets_criterion: bool
    failed: list[FailedFile]
    failure_reasons: dict[tuple[str, date], str]  # (chain name, day) -> reason, for the matrix
    records: dict[date, dict]
    missing_days: list[date]

    @property
    def window_days(self) -> int:
        return (self.end - self.start).days + 1


def _normalise(text: str) -> str:
    """A tally key: numbers (hours, sizes, dates) removed so equal causes group together."""
    return re.sub(r"\d+(?:[.,:-]\d+)*", "N", text)[:90]


def _chain_in_record(spec: ChainSpec, record: dict) -> dict | None:
    for chain in record["chains"].values():
        if chain["name"] == spec.name:
            return chain
    return None


def build_window(
    records: list[dict],
    chains: tuple[ChainSpec, ...] = D13_CHAINS,
    end: date | None = None,
    threshold: float = SUCCESS_THRESHOLD,
) -> Window:
    """The criterion-1 evidence over ``first record date .. end`` (default the last record)."""
    if not records:
        raise ValueError("no records")
    by_day = {date.fromisoformat(r["date"]): r for r in records}
    start = min(by_day)
    last = end or max(by_day)
    if last < start:
        raise ValueError("end is before the first record")
    by_day = {d: r for d, r in by_day.items() if d <= last}
    window = [start + timedelta(days=n) for n in range((last - start).days + 1)]
    loads: list[ChainLoads] = []
    failed: list[FailedFile] = []
    reasons: dict[tuple[str, date], str] = {}
    for spec in chains:
        days: dict[date, bool] = {}
        for d in window:
            record = by_day.get(d)
            if record is None:
                days[d] = False
                reasons[(spec.name, d)] = NO_RECORD
                failed.append(FailedFile(spec.name, d, "price_full", "no_record", NO_RECORD))
                continue
            chain = _chain_in_record(spec, record)
            if chain is None:
                days[d] = False
                reasons[(spec.name, d)] = NOT_IN_RECORD
                failed.append(FailedFile(spec.name, d, "price_full", "not_run", NOT_IN_RECORD))
                continue
            days[d] = chain["full_loaded"]
            if chain["full_loaded"]:
                continue
            reasons[(spec.name, d)] = chain["failure"] or "unknown"
            for kind in wr.FULL_KINDS:
                f = chain["files"][kind]
                if f["loaded"]:
                    continue
                why = f["download_error"] if f["status"] == wr.STATUS_NOT_DOWNLOADED else None
                why = why or ", ".join(f["gates"]) or f["reason"]
                failed.append(FailedFile(spec.name, d, kind, f["status"], why))
        loads.append(ChainLoads(spec, days))
    summaries = []
    for d in window:
        ok = sum(cl.days[d] for cl in loads)
        rate = ok / len(chains)
        summaries.append(DaySummary(d, ok, len(chains), rate, rate > threshold))
    cells = len(chains) * len(window)
    success = sum(cl.successes for cl in loads) / cells if cells else 0.0
    streak, s_start, s_end = longest_streak(summaries)

    best_rate: float | None = None
    best_start: date | None = None
    n = REQUIRED_WINDOW_DAYS
    for i in range(len(window) - n + 1):
        chunk = window[i : i + n]
        rate = sum(cl.days[d] for cl in loads for d in chunk) / (len(chains) * n)
        if best_rate is None or rate > best_rate:
            best_rate, best_start = rate, chunk[0]
    # A window with a missing day has failures in it, so only a window above the threshold counts;
    # a record-less day can never pass because it adds failures for every chain.
    meets = best_rate is not None and best_rate > threshold
    return Window(
        start=start, end=last, chains=loads, days=summaries, success_rate=success,
        longest_streak=streak, streak_start=s_start, streak_end=s_end,
        best_window_rate=best_rate, best_window_start=best_start, meets_criterion=meets,
        failed=failed, failure_reasons=reasons, records=by_day,
        missing_days=[d for d in window if d not in by_day],
    )  # fmt: skip


def chain_stats(win: Window, spec: ChainSpec) -> dict[str, Any]:
    """Per-chain reliability over the days that have a record."""
    seen = reached = downloaded_full = loaded_full = quarantined = failed = 0
    tally: Counter[str] = Counter()
    hours: list[float] = []
    ages: list[float] = []
    for d in sorted(win.records):
        chain = _chain_in_record(spec, win.records[d])
        if chain is None:
            continue
        seen += 1
        reached += chain["portal"]["reachable"] in ("OK", "REACHABLE") or chain["downloaded"] > 0
        full = [chain["files"][k] for k in wr.FULL_KINDS]
        downloaded_full += any(f["downloaded"] for f in full)
        loaded_full += chain["full_loaded"]
        quarantined += any(f["quarantined"] for f in full)
        failed += any(f["failed"] for f in full)
        for kind in wr.FULL_KINDS:
            f = chain["files"][kind]
            if not f["loaded"]:
                cause = f["download_error"] if f["status"] == wr.STATUS_NOT_DOWNLOADED else None
                cause = cause or ", ".join(f["gates"]) or f["reason"] or f["status"]
                tally[f"{kind} {f['status']}: {_normalise(str(cause))}"] += 1
            if f["published_at"]:
                when = datetime.fromisoformat(f["published_at"])
                hours.append(when.hour + when.minute / 60)
            if f["age_hours"] is not None:
                ages.append(f["age_hours"])
    return {"seen": seen, "reached": reached, "downloaded_full": downloaded_full,
            "loaded_full": loaded_full, "quarantined": quarantined, "failed": failed,
            "tally": tally, "hours": hours, "ages": ages}  # fmt: skip


def _hhmm(hour: float) -> str:
    return f"{int(hour):02d}:{int(round((hour - int(hour)) * 60)) % 60:02d}"


# --- rendering -------------------------------------------------------------------------------


def _verdict(win: Window) -> str:
    if win.window_days < REQUIRED_WINDOW_DAYS:
        return f"not met: {win.window_days} of {REQUIRED_WINDOW_DAYS} days so far"
    return "met" if win.meets_criterion else "not met"


def render(records: list[dict], problems: list[str], end: date | None = None,
           generated_at: datetime | None = None) -> str:  # fmt: skip
    generated_at = generated_at or datetime.now(UTC)
    lines: list[str] = []
    add = lines.append
    if not records:
        add("# Phase 0 exit window: runner rehearsal")
        add("")
        add(f"> **{wr.LABEL[0].upper() + wr.LABEL[1:]}.** No records yet.")
        for p in problems:
            add(f"- unusable record: {p}")
        return "\n".join(lines) + "\n"

    win = build_window(records, end=end)
    latest = win.records[max(win.records)]
    countries = Counter(r["run"]["runner_ip_country"] for r in win.records.values())

    add(
        f"# Phase 0 exit window, runner rehearsal: {win.start.isoformat()} to {win.end.isoformat()}"
    )
    add("")
    add(
        "> **Runner rehearsal, not the VPS window.** The nightly loads here run on GitHub-hosted "
        "runners, which are not Israeli IPs, into a throwaway database, one Stores, one PriceFull "
        "and one PromoFull file per chain. The exit needs fourteen consecutive nightly loads on the "
        "VPS (`phase-0-exit-report.md`). Nothing below may be pasted into that report as evidence, "
        "and the decision stays **NO-GO**."
    )
    add("")
    add(
        f"Generated {generated_at:%Y-%m-%d %H:%M} UTC by `scripts/exit_window/report.py` from "
        f"{len(records)} daily record(s) ({len(win.missing_days)} day(s) without one). Labels follow "
        "`docs/README.md`: every number here is **measured** by one of those runs; the "
        "judgements in the verdict column are **derived** from them."
    )
    add("")
    add(
        "Runner IP country per record: "
        + ", ".join(f"{c} ({n})" for c, n in sorted(countries.items()))
        + "."
    )
    add("")

    # criteria ---------------------------------------------------------------------------------
    stores_phys = sum(c["stores"]["physical"] for c in latest["chains"].values())
    stores_geo = sum(c["stores"]["with_coordinates"] for c in latest["chains"].values())
    add("## Criteria of issue #60, evaluated honestly")
    add("")
    best = (
        f"best 14 days {_pct(win.best_window_rate)} from {win.best_window_start.isoformat()}"
        if win.best_window_rate is not None
        else f"{win.window_days} day(s) of records, 14 needed"
    )
    lines += _table(
        ["Criterion", "Status on the runner rehearsal", "Why"],
        [
            (
                f"1. More than {_pct(SUCCESS_THRESHOLD)} nightly loads over {REQUIRED_WINDOW_DAYS} consecutive days",
                f"**{_verdict(win)}**",
                f"{_pct(win.success_rate)} over the whole window ({best}); longest streak of days "
                f"above {_pct(SUCCESS_THRESHOLD)}: {win.longest_streak}. Chains a runner cannot "
                "reach count as failures.",
            ),
            (
                "2. Every physical store has coordinates",
                "not evaluable here",
                f"Latest record: {stores_geo} of {stores_phys} physical stores in the downloaded "
                "Stores files have coordinates. A rehearsal loads one Stores file per chain, not "
                "every store, and geocoding is a separate step (`docs/geocoding.md`).",
            ),
            (
                "3. Promo parsing for the top chains, with a checked sample",
                "not evaluable here",
                "The counts per reward type are below; the sample needs a person with the raw "
                "descriptions and the throwaway database is gone.",
            ),
            (
                "4. Basket SQL over a radius",
                "not evaluated here",
                "It needs the loaded real database (`phase-0-exit-report.md`, section 4).",
            ),
            ("Go or no-go", "**NO-GO**, unchanged", "A rehearsal is not the exit validation."),
        ],
    )
    add("")

    # 1. nightly loads --------------------------------------------------------------------------
    add("## 1. Nightly loads")
    add("")
    add(
        f"- Window: {win.window_days} day(s), {win.start.isoformat()} to {win.end.isoformat()}, "
        f"{len(D13_CHAINS)} chains (the ten of D13)."
    )
    ok = sum(c.successes for c in win.chains)
    add(
        f"- Success rate: **{_pct(win.success_rate)}** ({ok} of {len(D13_CHAINS) * win.window_days} "
        "chain-days with a loaded `price_full` or `promo_full` file). Criterion: above "
        f"{_pct(SUCCESS_THRESHOLD)} over {REQUIRED_WINDOW_DAYS} consecutive days: **{_verdict(win)}**."
    )
    if win.longest_streak:
        add(
            f"- Longest streak of days above {_pct(SUCCESS_THRESHOLD)}: **{win.longest_streak}** "
            f"({win.streak_start.isoformat()} to {win.streak_end.isoformat()})."
        )
    else:
        add(f"- Longest streak of days above {_pct(SUCCESS_THRESHOLD)}: **0**.")
    stats = {c.chain.name: chain_stats(win, c.chain) for c in win.chains}
    reached = [c for c in win.chains if stats[c.chain.name]["downloaded_full"]]
    if reached and len(reached) < len(win.chains):
        r_ok = sum(c.successes for c in reached)
        add(
            f"- Information only, not the criterion: over the {len(reached)} chain(s) that "
            f"produced a full file at least once from a runner, {r_ok} of "
            f"{len(reached) * win.window_days} chain-days loaded ({_pct(r_ok / (len(reached) * win.window_days))}). "
            "The others: " + ", ".join(c.chain.name for c in win.chains if c not in reached) + "."
        )
    add("")
    add(
        "Per chain and day (`ok` = a full file reached `loaded` that day, `FAIL` = it did not, "
        "`--` = no record for the day):"
    )
    add("")
    days = [s.day for s in win.days]
    header = ["Chain", "Rate", *(d.strftime("%m-%d") for d in days)]
    rows = [
        [
            c.chain.name,
            _pct(c.rate),
            *("ok" if c.days[d] else ("--" if d in win.missing_days else "FAIL") for d in days),
        ]
        for c in win.chains
    ]
    rows.append(["**All chains**", _pct(win.success_rate), *(_pct(s.rate) for s in win.days)])
    lines += _table(header, rows)
    add("")

    # reliability per chain ----------------------------------------------------------------------
    add("### Per chain: reach, files, publication time")
    add("")
    add(
        "Days counted are the days with a record that includes the chain. *Reached* is a portal "
        "answer or a downloaded file; *full file* is a PriceFull or PromoFull. Publication hours are "
        "Israel time; age is the file's age when the rehearsal loaded it (the stale gate allows 36 "
        "hours)."
    )
    add("")
    rows = []
    for c in win.chains:
        s = stats[c.chain.name]
        pub = (
            f"{_hhmm(min(s['hours']))} to {_hhmm(max(s['hours']))} (median {_hhmm(statistics.median(s['hours']))})"
            if s["hours"]
            else ""
        )
        age = f"{statistics.median(s['ages']):.1f} h" if s["ages"] else ""
        rows.append([c.chain.name, s["seen"], s["reached"], s["downloaded_full"], s["loaded_full"],
                     s["quarantined"], s["failed"], pub, age])  # fmt: skip
    lines += _table(
        ["Chain", "Days", "Reached", "Full file downloaded", "Full file loaded",
         "Quarantined", "Failed", "Full files published", "Median age"], rows)  # fmt: skip
    add("")

    # causes ------------------------------------------------------------------------------------
    add("### Why full files did not load")
    add("")
    cause_rows = []
    for c in win.chains:
        for key, n in stats[c.chain.name]["tally"].most_common(3):
            cause_rows.append([c.chain.name, n, key])
    if cause_rows:
        lines += _table(["Chain", "Files", "Kind, status and cause (numbers masked)"], cause_rows)
    else:
        add("Every full file of every chain in the window loaded.")
    add("")
    if win.failed:
        add("<details><summary>Every full file that did not load, by day</summary>")
        add("")
        shown = win.failed[-MAX_FAILURE_ROWS:]
        lines += _table(
            ["Day", "Chain", "Kind", "Status", "Reason"],
            [(f.day.isoformat(), f.chain_id, f.kind, f.status, f.reason) for f in shown],
        )
        if len(win.failed) > len(shown):
            add("")
            add(f"({len(win.failed) - len(shown)} older rows not shown.)")
        add("")
        add("</details>")
        add("")

    # latest record ------------------------------------------------------------------------------
    add(f"## 2. The latest record, {latest['date']}")
    add("")
    run = latest["run"]
    add(
        f"Source {run['source']}, clock {run['clock']}, commit {run.get('commit') or 'n/a'}, "
        f"{run['duration_seconds']:.0f} s in all ({run['download_seconds']:.0f} s downloading, "
        f"{run['load_seconds']:.0f} s loading)."
        + (f" Run: {run['run_url']}." if run.get("run_url") else "")
    )
    add("")
    rows = []
    for chain in latest["chains"].values():
        f = chain["files"]

        def cell(x: dict) -> str:
            if x["status"] == wr.STATUS_NOT_DOWNLOADED:
                return "no file"
            gates = f" ({', '.join(x['gates'])})" if x["gates"] else ""
            return f"{x['status']}{gates}"

        pf, pr = f["price_full"], f["promo_full"]
        rows.append([
            chain["name"], f"{chain['portal']['reachable']} ({chain['portal']['http_status']})",
            cell(f["stores"]), cell(pf), cell(pr),
            pf["items"] if pf["items"] is not None else "",
            pf["prices"] if pf["prices"] is not None else "",
            pr["promos"] if pr["promos"] is not None else "",
            _hhmm_published(pf), _hhmm_published(pr),
        ])  # fmt: skip
    lines += _table(
        ["Chain", "Portal", "Stores", "PriceFull", "PromoFull", "Items", "Prices", "Promos",
         "PriceFull published", "PromoFull published"], rows)  # fmt: skip
    add("")
    unreachable = [c for c in latest["chains"].values() if c["downloaded"] == 0]
    if unreachable:
        add("Chains that produced no file in the latest record, and why:")
        add("")
        lines += _table(
            ["Chain", "Reason"],
            [(c["name"], c["failure"] or "; ".join(c["download_errors"])) for c in unreachable],
        )
        add("")
    if latest["alerts"]:
        add(
            f"Alerts raised by the Scheduler that day: {len(latest['alerts'])} "
            f"({', '.join(sorted({a['kind'] for a in latest['alerts']}))})."
        )
        add("")

    # criteria 2 and 3 from the record -------------------------------------------------------------
    add("## 3. Promo parsing and store coordinates, as the records show them")
    add("")
    add(
        "Promotions the loader wrote in the latest record, by reward type (an `other` promo is a "
        "parsing gap, not a pass; the checked sample of criterion 3 is still a person's job):"
    )
    add("")
    rows = []
    for spec in D13_CHAINS:
        chain = _chain_in_record(spec, latest)
        if chain is None:
            continue
        promos = chain["promos_by_reward"]
        total = sum(promos.values())
        other = promos.get("other", 0)
        kinds = ", ".join(f"{k} {n}" for k, n in sorted(promos.items()))
        rows.append([spec.name + (" (main)" if spec.main else ""), total,
                     _pct(other / total) if total else "", kinds,
                     f"{chain['stores']['with_coordinates']} of {chain['stores']['physical']}"])  # fmt: skip
    lines += _table(["Chain", "Promos", "`other` share", "By reward type",
                     "Physical stores with coordinates"], rows)  # fmt: skip
    add("")

    if problems:
        add("## Records that could not be used")
        add("")
        for p in problems:
            add(f"- {p}")
        add("")
    return "\n".join(lines) + "\n"


def _hhmm_published(f: dict) -> str:
    if not f["published_at"]:
        return ""
    when = datetime.fromisoformat(f["published_at"])
    return when.strftime("%m-%d %H:%M")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", type=Path, required=True, help="checkout of the data branch")
    ap.add_argument("--out", type=Path, default=None, help="Markdown file (default stdout)")
    ap.add_argument("--end", default=None, help="last day of the window (default: last record)")
    args = ap.parse_args(argv)
    records, problems = ws.load_records(args.data)
    end = date.fromisoformat(args.end) if args.end else None
    text = render(records, problems, end=end)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
