"""SEO and growth commands for the ``smartcart-catalog`` CLI: export-seo, basket-index, beta-report.

``cli.py`` calls ``register(app)``; standalone::

    uv run python -m smartcart_catalog.cli_seo export-seo --out apps/web/public/seo

* ``export-seo``    categories.json, products.json and quality.json for the static SEO pages and
  the methodology page (issues #35, #21). ``--from-files`` needs no database (no prices, and
  quality.json is left alone).
* ``basket-index``  prices the fixed basket per chain, writes ``basket-index.json`` and the press
  report ``docs/reports/basket-index-YYYY-MM.md`` (issue #44).
* ``beta-report``   the closed beta's three metrics from the ``events`` table against the
  proposed thresholds (issue #40, docs/beta-plan.md).

The database is ``$DATABASE_URL``. See docs/seo.md.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from smartcart_catalog.export_seo import MAX_PAGES

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "apps" / "web" / "public" / "seo"
DEFAULT_REPORTS = REPO_ROOT / "docs" / "reports"


def _connect():
    from smartcart_ingest import db as dbmod

    conn = dbmod.connect()
    conn.execute("SET TIME ZONE 'UTC'")
    return conn


def export_seo_cmd(
    out: Annotated[Path, typer.Option(help="Output directory.")] = DEFAULT_OUT,
    max_pages: Annotated[
        int, typer.Option(help="Page budget: categories plus best-ranked products.")
    ] = MAX_PAGES,
    from_files: Annotated[
        bool,
        typer.Option(
            "--from-files",
            help="Read data/*.yaml instead of the database: no prices, quality.json untouched.",
        ),
    ] = False,
) -> None:
    """Write categories.json, products.json and quality.json for the static pages."""
    from smartcart_catalog.basket_index import ensure_index
    from smartcart_catalog.export_seo import (
        export_from_db,
        export_from_files,
        read_canonicals,
        rows_from_catalog,
    )
    from smartcart_catalog.seed import load_catalog
    from smartcart_catalog.taxonomy import default_data_dir

    now = datetime.now(UTC)
    if from_files:
        catalog = load_catalog(default_data_dir())
        result = export_from_files(catalog, out, max_pages=max_pages, now=now)
        canonicals = rows_from_catalog(catalog)[1]
    else:
        with _connect() as conn:
            result = export_from_db(conn, out, max_pages=max_pages, now=now)
            canonicals = read_canonicals(conn)
    ensure_index(out, canonicals, now)  # the published basket definition, months are kept
    typer.echo(
        f"{result.categories['page_count']} category pages + {result.products['page_count']}"
        f" product pages = {result.pages} pages;"
        f" {result.products['count']} canonicals, {result.products['priced_count']} with prices"
    )
    if result.quality is not None:
        q = result.quality
        typer.echo(
            "quality: "
            + (f"run {q['run_id']} of {q['measured_at']}" if q["available"] else "no evaluate run")
        )
    typer.echo(f"written to {out}")


def basket_index_cmd(
    month: Annotated[
        str | None, typer.Option(help="YYYY-MM, default: the current month (UTC).")
    ] = None,
    out: Annotated[Path, typer.Option(help="SEO data directory.")] = DEFAULT_OUT,
    reports: Annotated[Path, typer.Option(help="Press report directory.")] = DEFAULT_REPORTS,
    reviewed_by: Annotated[
        str | None,
        typer.Option(help="Name of the person who checked the numbers. Needed to publish."),
    ] = None,
    acknowledge: Annotated[
        list[str] | None,
        typer.Option(help="Error check code a human reviewed and accepts (repeatable)."),
    ] = None,
) -> None:
    """Price the fixed basket per chain, run the pre-publication checks, write the files.

    Without --reviewed-by the month is a draft the web page does not show. With it, the month is
    published unless an unacknowledged error check is open (exit 1, the draft is still written)."""
    from smartcart_catalog import basket_index as bi
    from smartcart_catalog.export_seo import read_canonicals, read_unit_prices, write_json

    now = datetime.now(UTC)
    month = month or now.strftime("%Y-%m")
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise typer.BadParameter("month must look like 2026-10") from exc
    with _connect() as conn:
        canonicals = {c.slug: c for c in read_canonicals(conn)}
        unknown = [line.slug for line in bi.BASKET_V1 if line.slug not in canonicals]
        if unknown:
            typer.echo(f"basket items missing from canonical_products: {unknown}", err=True)
            raise typer.Exit(2)
        prices = read_unit_prices(conn)
    definition = bi.basket_definition(
        bi.BASKET_V1, {s: (c.display_name_he, c.base_unit) for s, c in canonicals.items()}
    )
    index_path = out / bi.INDEX_FILE
    index = bi.load_index(index_path) or bi.empty_index(definition, now)
    index["basket"] = definition  # the definition of the current version is code, not data
    outcome = bi.evaluate_month(
        index, month, bi.BASKET_V1, prices,
        now=now, reviewed_by=reviewed_by, acknowledge=acknowledge or (),
    )  # fmt: skip
    write_json(index_path, bi.merge_month(index, outcome.doc, now))
    report_path = reports / f"basket-index-{month}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = bi.render_report(outcome.doc, definition)
    report_path.write_text(report, encoding="utf-8")
    # The press copy the /basket-index page links to exists only while the month is published.
    public_copy = out / "reports" / report_path.name
    if outcome.doc["status"] == "published":
        public_copy.parent.mkdir(parents=True, exist_ok=True)
        public_copy.write_text(report, encoding="utf-8")
    else:
        public_copy.unlink(missing_ok=True)
    ranked = [c for c in outcome.doc["chains"] if c["complete"]]
    typer.echo(f"{month}: {len(ranked)} chains ranked, status {outcome.doc['status']}")
    for c in outcome.doc["checks"]:
        typer.echo(f"  {c['level']}: {c['code']}: {c['message']}")
    typer.echo(f"written {index_path} and {report_path}")
    if outcome.blocked:
        codes = ", ".join(c["code"] for c in outcome.blocked)
        typer.echo(
            f"NOT PUBLISHED: open errors {codes}. Fix the data, or review and pass"
            " --acknowledge CODE.",
            err=True,
        )
        raise typer.Exit(1)
    if reviewed_by is None:
        typer.echo("draft: run again with --reviewed-by NAME after checking the report")


# --- closed beta report (issue #40) ----------------------------------------------------------------

BETA_THRESHOLDS: dict[str, Any] = {
    "rejection_rate": {"exact": 0.02, "any_brand": 0.05, "close": 0.15},
    "min_shown": 100,
    "paste_to_results_median_ms": 5_000,
    "paste_to_results_p90_ms": 10_000,
    "min_results": 30,
    "returning_share": 0.40,
}
"""PROPOSALS, recorded in docs/beta-plan.md before recruiting starts. They are not measured values
and not research facts. Rejection rate gates the public launch; the other two are signals."""

LEVELS = ("exact", "any_brand", "close")


def beta_metrics(conn, since: date | None = None) -> dict[str, Any]:
    """The three metrics over the window starting at ``since`` (all events when None).

    Definitions match the views in migration 20261007120000_events.sql: rejection rate is
    ``not_good`` verdicts over substitutions shown (the ``count`` of ``substitutions_shown``),
    paste-to-results is ``results_shown.duration_ms``, and a returning user is one whose first
    ``app_opened`` day is before the week they are active in.
    """
    window = "AND created_at >= %(since)s" if since else ""
    params = {"since": since}
    shown = dict(
        conn.execute(
            "SELECT props->>'flex_level', coalesce(sum((props->>'count')::integer), 0)"
            f" FROM events WHERE name = 'substitutions_shown' {window} GROUP BY 1",
            params,
        ).fetchall()
    )
    rejected = dict(
        conn.execute(
            "SELECT props->>'flex_level', count(*) FROM events"
            f" WHERE name = 'substitution_verdict' AND props->>'verdict' = 'not_good' {window}"
            " GROUP BY 1",
            params,
        ).fetchall()
    )
    results, median, p90 = conn.execute(
        "SELECT count(*),"
        " percentile_cont(0.5) WITHIN GROUP (ORDER BY (props->>'duration_ms')::numeric),"
        " percentile_cont(0.9) WITHIN GROUP (ORDER BY (props->>'duration_ms')::numeric)"
        f" FROM events WHERE name = 'results_shown' AND props ? 'duration_ms' {window}",
        params,
    ).fetchone()
    returning = conn.execute(
        "SELECT week, active_users, returning_users, returning_share FROM beta_return_visits"
        " WHERE week < date_trunc('week', now() AT TIME ZONE 'Asia/Jerusalem')::date"
        " ORDER BY week DESC LIMIT 1"
    ).fetchone()
    users = conn.execute(
        "SELECT count(DISTINCT coalesce(user_id::text, session_id)) FROM events"
        f" WHERE name = 'app_opened' {window}",
        params,
    ).fetchone()[0]
    return {
        "users": users,
        "rejection": {
            lvl: {"shown": int(shown.get(lvl, 0)), "rejected": int(rejected.get(lvl, 0))}
            for lvl in LEVELS
        },
        "paste_to_results": {
            "results": results,
            "median_ms": None if median is None else float(median),
            "p90_ms": None if p90 is None else float(p90),
        },
        "returning": None
        if returning is None
        else {
            "week": returning[0], "active_users": returning[1],
            "returning_users": returning[2],
            "share": None if returning[3] is None else float(returning[3]),
        },  # fmt: skip
    }


def beta_verdicts(metrics: dict[str, Any], thresholds: dict[str, Any] = BETA_THRESHOLDS):
    """(metric, observed, threshold, status, gating) rows; status is pass, fail or inconclusive
    (sample too small). Only the rejection rates gate the public launch (issue #40)."""
    rows: list[tuple[str, str, str, str, bool]] = []
    for lvl in LEVELS:
        m = metrics["rejection"][lvl]
        limit = thresholds["rejection_rate"][lvl]
        if m["shown"] < thresholds["min_shown"]:
            rows.append((f"rejection rate, {lvl}", f"{m['rejected']} of {m['shown']} shown",
                         f"<= {limit:.0%} with at least {thresholds['min_shown']} shown",
                         "inconclusive", True))  # fmt: skip
            continue
        rate = m["rejected"] / m["shown"]
        rows.append((f"rejection rate, {lvl}", f"{rate:.1%} ({m['rejected']} of {m['shown']})",
                     f"<= {limit:.0%}", "pass" if rate <= limit else "fail", True))  # fmt: skip
    p = metrics["paste_to_results"]
    if p["results"] < thresholds["min_results"] or p["median_ms"] is None:
        rows.append(("paste to results", f"{p['results']} results", "", "inconclusive", False))
    else:
        for key, label in (("median_ms", "median"), ("p90_ms", "p90")):
            limit = thresholds[f"paste_to_results_{key}"]
            rows.append((f"paste to results, {label}", f"{p[key] / 1000:.1f} s",
                         f"<= {limit / 1000:.0f} s",
                         "pass" if p[key] <= limit else "fail", False))  # fmt: skip
    r = metrics["returning"]
    if r is None or r["share"] is None:
        rows.append(("return visits", "no complete week yet", "", "inconclusive", False))
    else:
        rows.append(("return visits", f"{r['share']:.0%} of {r['active_users']} active users"
                     f" (week of {r['week']})", f">= {thresholds['returning_share']:.0%}",
                     "pass" if r["share"] >= thresholds["returning_share"] else "fail", False))  # fmt: skip
    return rows


def render_beta_report(metrics: dict[str, Any], since: date | None, today: date) -> str:
    rows = beta_verdicts(metrics)
    gating = [r for r in rows if r[4]]
    if any(r[3] == "fail" for r in gating):
        verdict = "NOT MET: at least one rejection rate is above its threshold."
    elif any(r[3] == "inconclusive" for r in gating):
        verdict = "INCONCLUSIVE: too few substitutions shown at some level. Extend the beta."
    else:
        verdict = "MET: every rejection rate is within its threshold."
    lines = [
        f"# Closed beta report, {today.isoformat()}",
        "",
        f"Window: {since.isoformat() if since else 'all events'} to {today.isoformat()}."
        f" Active users (app opened): {metrics['users']}.",
        "",
        "Thresholds are proposals (docs/beta-plan.md), not measured values.",
        "",
        "| Metric | Observed | Threshold | Status | Gates launch |",
        "|---|---|---|---|---|",
        *[f"| {m} | {o} | {t or '-'} | {s} | {'yes' if g else 'no'} |" for m, o, t, s, g in rows],
        "",
        f"**Rejection-rate gate: {verdict}**",
        "",
    ]
    return "\n".join(lines)


def beta_report_cmd(
    since: Annotated[
        datetime | None, typer.Option(formats=["%Y-%m-%d"], help="Start of the window.")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Write the report here, else print.")] = None,
    fail_on_miss: Annotated[
        bool, typer.Option("--fail-on-miss", help="Exit 1 when the rejection-rate gate is not met.")
    ] = False,
) -> None:
    """The closed beta's rejection rate, paste-to-results time and return visits, with verdicts."""
    start = since.date() if since else None
    with _connect() as conn:
        metrics = beta_metrics(conn, start)
    text = render_beta_report(metrics, start, datetime.now(UTC).date())
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"written {out}")
    else:
        typer.echo(text)
    gate = [r for r in beta_verdicts(metrics) if r[4]]
    if fail_on_miss and any(r[3] != "pass" for r in gate):
        raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Add the SEO and growth commands to the catalog CLI."""
    app.command("export-seo")(export_seo_cmd)
    app.command("basket-index")(basket_index_cmd)
    app.command("beta-report")(beta_report_cmd)


if __name__ == "__main__":  # python -m smartcart_catalog.cli_seo export-seo ...
    standalone = typer.Typer(add_completion=False, no_args_is_help=True)
    register(standalone)
    standalone()
