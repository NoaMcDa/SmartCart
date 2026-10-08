"""Catalog growth commands for the ``smartcart-catalog`` CLI: backlog, native-report.

``cli.py`` calls ``register(app)``; standalone::

    uv run python -m smartcart_catalog.cli_growth backlog --top 20

* ``backlog``        what the catalog should learn next (issue #52, docs/catalog.md section 9):
  queries users searched for and found nothing, clustered and ranked by frequency over the last 30
  days, and products in the price files that no canonical covers, ranked by how many stores carry
  them. The ranking query is ``supabase/queries/catalog_backlog.sql``.
* ``native-report``  the numbers the native-app decision needs (issue #56) from the views of
  migration 20261011100300_retention.sql, each with its sample size, next to the criteria of
  decision D15 (a proposal: docs/decisions.md). The report only compares numbers with criteria
  that were written down before the data was seen; the owner decides.

The database is ``$DATABASE_URL``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer


def _connect():
    from smartcart_ingest import db as dbmod

    conn = dbmod.connect()
    conn.execute("SET TIME ZONE 'UTC'")
    return conn


# --- backlog ----------------------------------------------------------------------------------


def render_backlog(rows: list[dict[str, Any]], days: int) -> str:
    kinds = (
        ("missed_query", f"Searched for and not found (last {days} days)", "misses", "spellings"),
        ("unmapped_item", "In the price files, no canonical covers it", "stores", "chains"),
    )
    lines: list[str] = []
    for kind, title, demand, secondary in kinds:
        part = [r for r in rows if r["kind"] == kind]
        lines.append(f"{title}: {len(part)} shown")
        if not part:
            lines.append("  (nothing yet)")
        for r in part:
            more = [e for e in (r["examples"] or []) if e != r["label"]][:3]
            tail = f"  also: {', '.join(more)}" if more else ""
            lines.append(
                f"  {r['position']:>3}. {r['label']}  [{r['demand']} {demand},"
                f" {r['secondary']} {secondary}]{tail}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def backlog_cmd(
    top: Annotated[int, typer.Option(help="Rows per list.")] = 20,
    days: Annotated[int, typer.Option(help="Window for search misses, in days.")] = 30,
    min_similarity: Annotated[
        float, typer.Option(help="Trigram similarity at which two queries count as one demand.")
    ] = 0.5,
    min_misses: Annotated[int, typer.Option(help="Hide demands asked for fewer times.")] = 1,
    item_days: Annotated[
        int, typer.Option(help="An uncovered item counts when a load touched it in this many days.")
    ] = 60,
) -> None:
    """The top missed queries and uncovered products: the input for the next canonical batch."""
    from smartcart_catalog.active import catalog_backlog

    with _connect() as conn:
        rows = catalog_backlog(conn, days=days, top=top, min_similarity=min_similarity,
                               min_misses=min_misses, item_days=item_days)  # fmt: skip
        conn.rollback()
    typer.echo(render_backlog(rows, days))


# --- native-app decision metrics (issue #56, D15) ---------------------------------------------

NATIVE_CRITERIA: dict[str, Any] = {
    "window_weeks": 12,
    "d30_retention": 0.15,
    "d30_min_eligible": 100,
    "ios_share": 0.30,
    "ios_min_actors": 50,
    "ios_not_installed_share": 0.50,
    "ios_not_installed_min_actors": 30,
    "push_open_rate": 0.15,
    "push_min_sent": 100,
    "store_mode_share": 0.20,
    "store_mode_min_user_weeks": 100,
    "scan_success": 0.80,
    "scan_min_completed": 50,
}
"""PROPOSALS (decision D15 in docs/decisions.md), written before any retention data exists. They
are planning choices, not research facts: the research marks no benchmark for a Hebrew grocery
PWA's retention. The owner confirms or changes them before the numbers are looked at."""


def _ratio(num: int | float, den: int | float) -> float | None:
    return None if not den else float(num) / float(den)


def native_metrics(conn, weeks: int | None = None) -> dict[str, Any]:
    """The decision inputs, pooled over the last ``weeks`` complete or running weeks.

    Retention pools the last ``weeks`` cohorts (a cohort counts in Dn only when day n is over).
    Push, store mode and scans pool the weekly rows of the window (user-weeks for the shares).
    """
    weeks = weeks or NATIVE_CRITERIA["window_weeks"]
    since = conn.execute(
        "SELECT date_trunc('week', now() AT TIME ZONE 'Asia/Jerusalem')::date - %s * 7", (weeks - 1,)
    ).fetchone()[0]

    cohorts = conn.execute(
        "SELECT cohort_week, cohort_size, d1_eligible, d1_retained, d7_eligible, d7_retained,"
        " d30_eligible, d30_retained FROM native_cohort_retention WHERE cohort_week >= %s"
        " ORDER BY cohort_week",
        (since,),
    ).fetchall()
    retention = {
        "cohorts": [
            {"week": r[0], "size": r[1], "d1": (r[3], r[2]), "d7": (r[5], r[4]), "d30": (r[7], r[6])}
            for r in cohorts
        ],
        "users": sum(r[1] for r in cohorts),
    }
    for n, (ie, ir) in {"d1": (2, 3), "d7": (4, 5), "d30": (6, 7)}.items():
        eligible = sum(r[ie] for r in cohorts)
        retained = sum(r[ir] for r in cohorts)
        retention[n] = {"eligible": eligible, "retained": retained, "rate": _ratio(retained, eligible)}

    installs = conn.execute(
        "SELECT platform, sum(installs), sum(installers) FROM native_installs_by_platform"
        " WHERE week >= %s GROUP BY platform ORDER BY platform",
        (since,),
    ).fetchall()
    push = conn.execute(
        "SELECT coalesce(sum(active_users), 0), coalesce(sum(opt_in_users), 0),"
        " coalesce(sum(pushes_sent), 0), coalesce(sum(push_opened), 0)"
        " FROM native_push_engagement WHERE week >= %s",
        (since,),
    ).fetchone()
    store = conn.execute(
        "SELECT coalesce(sum(active_users), 0), coalesce(sum(store_mode_users), 0),"
        " coalesce(sum(store_mode_events), 0), coalesce(sum(single_events), 0),"
        " coalesce(sum(split_events), 0) FROM native_store_mode_usage WHERE week >= %s",
        (since,),
    ).fetchone()
    scans = conn.execute(
        "SELECT count(*) FILTER (WHERE name = 'scan_started'),"
        " count(*) FILTER (WHERE name = 'scan_completed' AND props->>'outcome' <> 'cancelled'),"
        " count(*) FILTER (WHERE name = 'scan_completed' AND props->>'outcome' = 'found')"
        " FROM events WHERE name IN ('scan_started', 'scan_completed')"
        " AND (created_at AT TIME ZONE 'Asia/Jerusalem')::date >= %s",
        (since,),
    ).fetchone()
    funnel = {
        r[0]: {"actors": r[1], "installers": r[2], "push_opt_in": r[3], "store_mode": r[4],
               "not_installed_share": None if r[5] is None else float(r[5])}
        for r in conn.execute(
            "SELECT platform, actors_seen, installers, push_opt_in_users, store_mode_users,"
            " not_installed_share FROM native_platform_funnel ORDER BY platform"
        ).fetchall()
    }  # fmt: skip
    all_actors = sum(f["actors"] for f in funnel.values())
    return {
        "since": since,
        "weeks": weeks,
        "retention": retention,
        "installs": [{"platform": p, "installs": int(i), "installers": int(u)} for p, i, u in installs],
        "push": {
            "user_weeks": int(push[0]), "opt_in_user_weeks": int(push[1]),
            "opt_in_rate": _ratio(push[1], push[0]),
            "sent": int(push[2]), "opened": int(push[3]), "open_rate": _ratio(push[3], push[2]),
        },  # fmt: skip
        "store_mode": {
            "user_weeks": int(store[0]), "store_mode_user_weeks": int(store[1]),
            "share": _ratio(store[1], store[0]), "events": int(store[2]),
            "single": int(store[3]), "split": int(store[4]),
            "events_per_user_week": _ratio(store[2], store[1]),
        },  # fmt: skip
        "scans": {"started": scans[0], "completed": scans[1], "found": scans[2],
                  "success_rate": _ratio(scans[2], scans[1])},  # fmt: skip
        "platforms": funnel,
        "ios": {
            "actors": funnel.get("ios", {}).get("actors", 0),
            "share": _ratio(funnel.get("ios", {}).get("actors", 0), all_actors),
            "not_installed_share": funnel.get("ios", {}).get("not_installed_share"),
        },
    }


def native_verdicts(m: dict[str, Any], c: dict[str, Any] = NATIVE_CRITERIA) -> list[dict[str, Any]]:
    """One row per D15 criterion: observed, threshold, sample and status (met, not_met or
    inconclusive when the sample is below its minimum)."""

    def row(name, observed, fmt, threshold, sample, minimum, ok):
        if observed is None or sample < minimum:
            status = "inconclusive"
        else:
            status = "met" if ok(observed) else "not_met"
        return {"criterion": name, "observed": None if observed is None else fmt(observed),
                "threshold": threshold, "sample": sample, "minimum": minimum, "status": status}  # fmt: skip

    d30 = m["retention"]["d30"]
    return [
        row("C1 D30 retention (pooled cohorts)", d30["rate"], pct,
            f">= {c['d30_retention']:.0%}", d30["eligible"], c["d30_min_eligible"],
            lambda v: v >= c["d30_retention"]),
        row("C2 iOS share of platform-tagged actors", m["ios"]["share"], pct,
            f">= {c['ios_share']:.0%}", sum(f["actors"] for f in m["platforms"].values()),
            c["ios_min_actors"], lambda v: v >= c["ios_share"]),
        row("C3 iOS actors who never installed the PWA (no web push)",
            m["ios"]["not_installed_share"], pct, f">= {c['ios_not_installed_share']:.0%}",
            m["ios"]["actors"], c["ios_not_installed_min_actors"],
            lambda v: v >= c["ios_not_installed_share"]),
        row("C4 push open rate (opens / pushes sent)", m["push"]["open_rate"], pct,
            f">= {c['push_open_rate']:.0%}", m["push"]["sent"], c["push_min_sent"],
            lambda v: v >= c["push_open_rate"]),
        row("C5 store mode used (share of active user-weeks)", m["store_mode"]["share"], pct,
            f">= {c['store_mode_share']:.0%}", m["store_mode"]["user_weeks"],
            c["store_mode_min_user_weeks"], lambda v: v >= c["store_mode_share"]),
        row("C6 barcode scan success in the PWA", m["scans"]["success_rate"], pct,
            f">= {c['scan_success']:.0%} (below = a native camera is worth it)",
            m["scans"]["completed"], c["scan_min_completed"], lambda v: v >= c["scan_success"]),
    ]


def native_outcome(rows: list[dict[str, Any]]) -> tuple[str, str]:
    """(outcome, why) from the D15 rules; the report states it, the owner decides.

    * ``inconclusive``  C1 has too few users: collect more before deciding anything.
    * ``stay_pwa``      C1 not met: people do not come back, a wrapper does not fix that.
    * ``evaluate_capacitor``  C1 met and iOS push is the blocker (C2, C3 and C4 met).
    * ``stay_pwa_fix_gaps``  C1 met but the push case is not made: file the PWA gaps found.
    React Native is never an outcome of these numbers alone (D15): it needs a Capacitor pilot that
    fails a requirement (C6 still under its threshold with the native camera plugin, or a need for
    background location or offline sync a WebView cannot meet).
    """
    by = {r["criterion"][:2]: r["status"] for r in rows}
    if by["C1"] == "inconclusive":
        return "inconclusive", "D30 retention has fewer than the minimum eligible users."
    if by["C1"] == "not_met":
        return "stay_pwa", "D30 retention is below its threshold; packaging does not fix that."
    if by["C2"] == by["C3"] == by["C4"] == "met":
        return "evaluate_capacitor", (
            "Retention holds, many iOS users cannot get web push and push is opened: a Capacitor"
            " wrapper (same Next.js code) is worth a pilot."
        )
    if "not_met" in (by["C2"], by["C3"], by["C4"]):  # all three are needed, so one miss settles it
        return "stay_pwa_fix_gaps", "Retention holds but the native-push case is not made: stay PWA."
    return "inconclusive", "Retention holds, but the push case (C2 to C4) has too few users."


def pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1%}"


def render_native_report(m: dict[str, Any], today: datetime) -> str:
    rows = native_verdicts(m)
    outcome, why = native_outcome(rows)
    r = m["retention"]
    lines = [
        f"# Native-app decision report, {today.date().isoformat()}",
        "",
        f"Window: the last {m['weeks']} weeks (from {m['since']}, Israel-time weeks starting Monday)."
        f" Actors are signed-in user ids or browser session ids: one person on two browsers is two"
        f" actors, so retention is a lower bound.",
        "Criteria are proposals (decision D15), written before the data was seen; they are estimates,"
        " not research facts.",
        "",
        "## Cohort retention (first app_opened week)",
        "",
        "| Cohort week | Users | D1 | D7 | D30 |",
        "|---|---|---|---|---|",
    ]
    for c in r["cohorts"]:
        cells = [f"{pct(_ratio(*c[k]))} ({c[k][0]}/{c[k][1]})" if c[k][1] else "n/a (0)"
                 for k in ("d1", "d7", "d30")]  # fmt: skip
        lines.append(f"| {c['week']} | {c['size']} | {' | '.join(cells)} |")
    lines += [
        f"| **pooled** | {r['users']} | " + " | ".join(
            f"**{pct(r[k]['rate'])}** ({r[k]['retained']}/{r[k]['eligible']})" for k in ("d1", "d7", "d30")
        ) + " |",
        "",
        "Each cell is retained/eligible: an actor is eligible for Dn only once day n is over.",
        "",
        "## Installs by platform",
        "",
        "| Platform | Install events | Distinct installers |",
        "|---|---|---|",
        *[f"| {i['platform']} | {i['installs']} | {i['installers']} |" for i in m["installs"]],
        *([] if m["installs"] else ["| (none yet) | 0 | 0 |"]),
        "",
        "## Push, store mode and scans",
        "",
        f"- Push opt-in: {m['push']['opt_in_user_weeks']} opt-in user-weeks of {m['push']['user_weeks']}"
        f" active user-weeks ({pct(m['push']['opt_in_rate'])}); there is no \"prompt shown\" event,"
        " so this is a floor.",
        f"- Push opened: {m['push']['opened']} of {m['push']['sent']} pushes sent"
        f" ({pct(m['push']['open_rate'])}).",
        f"- Store mode: {m['store_mode']['store_mode_user_weeks']} of {m['store_mode']['user_weeks']}"
        f" active user-weeks ({pct(m['store_mode']['share'])}); {m['store_mode']['events']} opens"
        f" ({m['store_mode']['single']} single, {m['store_mode']['split']} split).",
        f"- Barcode scans: {m['scans']['found']} found of {m['scans']['completed']} completed"
        f" ({pct(m['scans']['success_rate'])}); {m['scans']['started']} started.",
        "",
        "## Platforms (all time, actors with a platform on an install, push or store-mode event)",
        "",
        "| Platform | Actors | Installed PWA | Push opt-in | Store mode | Never installed |",
        "|---|---|---|---|---|---|",
        *[f"| {p} | {f['actors']} | {f['installers']} | {f['push_opt_in']} | {f['store_mode']} |"
          f" {pct(f['not_installed_share'])} |" for p, f in m["platforms"].items()],
        *([] if m["platforms"] else ["| (none yet) | 0 | 0 | 0 | 0 | n/a |"]),
        "",
        "## D15 criteria against the numbers",
        "",
        "| Criterion | Observed | Threshold | Sample (minimum) | Status |",
        "|---|---|---|---|---|",
        *[f"| {v['criterion']} | {v['observed'] or 'n/a'} | {v['threshold']} |"
          f" {v['sample']} ({v['minimum']}) | {v['status']} |" for v in rows],
        "",
        f"**Outcome by the D15 rules: {outcome}.** {why} The owner decides.",
        "",
    ]
    return "\n".join(lines)


def native_report_cmd(
    weeks: Annotated[int, typer.Option(help="Window in weeks (cohorts and weekly rows).")] = 12,
    out: Annotated[Path | None, typer.Option(help="Write the report here, else print.")] = None,
) -> None:
    """Retention cohorts, installs, push, store mode and scans, with sample sizes and D15 verdicts."""
    with _connect() as conn:
        metrics = native_metrics(conn, weeks)
        conn.rollback()
    text = render_native_report(metrics, datetime.now(UTC))
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"written {out}")
    else:
        typer.echo(text)


def register(app: typer.Typer) -> None:
    """Add the growth commands to the catalog CLI."""
    app.command("backlog")(backlog_cmd)
    app.command("native-report")(native_report_cmd)


if __name__ == "__main__":
    standalone = typer.Typer(add_completion=False, no_args_is_help=True)
    register(standalone)
    standalone()
