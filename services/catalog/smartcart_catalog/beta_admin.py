"""Closed beta administration for the ``smartcart-catalog`` CLI (issue #40, docs/beta-plan.md).

* ``beta-invite``    make invite codes for one segment and print them with their join links
                     (``{API_PUBLIC_WEB_URL}/beta/join/<code>``).
* ``beta-feedback``  read the feedback members sent from the app. It is stored with the segment and
                     a rating and without the user, and only this command shows the text.
* ``beta-report``    the existing report (``cli_seo.beta_report_cmd``: the three metrics against the
                     proposed thresholds, unchanged) plus a section that breaks the rejection rate
                     and paste-to-results time down by segment, with sample sizes, and counts who
                     was invited, joined and is active. The thresholds are not touched here: they
                     stay the owner's proposals (``cli_seo.BETA_THRESHOLDS``) and a segment gets no
                     verdict of its own, only its numbers and whether its sample is large enough
                     to read.

Tables and views: ``supabase/migrations/20261011100700_beta.sql``. The connection is the same
service connection as the other reports (``DATABASE_URL``).
"""

from __future__ import annotations

import os
import secrets
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from smartcart_catalog import cli_seo
from smartcart_catalog.cli_seo import BETA_THRESHOLDS, LEVELS

SEGMENTS: tuple[str, ...] = ("large_family", "kosher", "periphery", "general")
SEGMENT_LABELS = {
    "large_family": "large families",
    "kosher": "kosher-conscious",
    "periphery": "periphery",
    "general": "anyone else",
}
# 32 characters without 0, 1, I and O, so a code read out loud or typed from a screenshot survives.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_GROUP = 5
DEFAULT_EXPIRY_DAYS = 60
DEFAULT_WEB_URL = "http://localhost:3000"


class Segment(StrEnum):
    large_family = "large_family"
    kosher = "kosher"
    periphery = "periphery"
    general = "general"


def _connect():
    # One place to patch in tests: the same connection the other reports use.
    return cli_seo._connect()


def new_code(rng: secrets.SystemRandom | None = None) -> str:
    """``XXXXX-XXXXX``: ten characters of a 32-letter alphabet, about 2^50 possibilities."""
    pick = (rng or secrets.SystemRandom()).choice
    return "-".join("".join(pick(CODE_ALPHABET) for _ in range(CODE_GROUP)) for _ in range(2))


def web_origin(explicit: str | None = None) -> str:
    """The public web origin for join links: the option, ``API_PUBLIC_WEB_URL``, the first CORS
    origin the API allows, else localhost."""
    for candidate in (
        explicit,
        os.environ.get("API_PUBLIC_WEB_URL"),
        (os.environ.get("API_CORS_ORIGINS") or "").split(",")[0],
    ):
        if candidate and candidate.strip():
            return candidate.strip().rstrip("/")
    return DEFAULT_WEB_URL


def join_link(origin: str, code: str) -> str:
    return f"{origin.rstrip('/')}/beta/join/{code}"


def create_invites(
    conn, segment: str, count: int, max_uses: int, expires_at: datetime | None
) -> list[str]:
    """Insert ``count`` fresh codes (a collision is simply drawn again) and return them."""
    codes: list[str] = []
    while len(codes) < count:
        code = new_code()
        row = conn.execute(
            "INSERT INTO beta_invites (code, segment, max_uses, expires_at)"
            " VALUES (%s, %s, %s, %s) ON CONFLICT (code) DO NOTHING RETURNING code",
            (code, segment, max_uses, expires_at),
        ).fetchone()
        if row is not None:
            codes.append(code)
    return codes


def beta_invite_cmd(
    segment: Annotated[Segment, typer.Option(help="Which group these invitations are for.")],
    count: Annotated[int, typer.Option(min=1, max=500, help="How many codes to make.")] = 1,
    max_uses: Annotated[
        int, typer.Option(min=1, max=1000, help="People who may join with one code.")
    ] = 1,
    expires_days: Annotated[
        int, typer.Option(min=0, help="Days until the codes expire; 0 = never.")
    ] = DEFAULT_EXPIRY_DAYS,
    web_url: Annotated[
        str | None,
        typer.Option(help="Public web origin for the links (default: API_PUBLIC_WEB_URL)."),
    ] = None,
) -> None:
    """Make invite codes for a segment and print each with its join link."""
    origin = web_origin(web_url)
    expires = datetime.now(UTC) + timedelta(days=expires_days) if expires_days else None
    with _connect() as conn:
        codes = create_invites(conn, segment.value, count, max_uses, expires)
    for code in codes:
        typer.echo(f"{code}\t{join_link(origin, code)}")
    when = f"expire {expires.date().isoformat()}" if expires else "never expire"
    typer.echo(
        f"{count} code(s) for {segment.value}, {max_uses} place(s) each, {when}."
        " Send one link per person.",
        err=True,
    )
    if origin == DEFAULT_WEB_URL:
        typer.echo(
            "warning: the links use localhost; set API_PUBLIC_WEB_URL or pass --web-url.", err=True
        )


# --- feedback --------------------------------------------------------------------------------


def read_feedback(
    conn, since: date | None = None, segment: str | None = None, limit: int = 200
) -> list[tuple[int, datetime, str, int, str]]:
    clauses, params = [], {"limit": limit}
    if since:
        clauses.append("created_at >= %(since)s")
        params["since"] = since
    if segment:
        clauses.append("segment = %(segment)s")
        params["segment"] = segment
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return conn.execute(
        f"SELECT id, created_at, segment, rating, body FROM beta_feedback {where}"
        " ORDER BY created_at DESC, id DESC LIMIT %(limit)s",
        params,
    ).fetchall()


def render_feedback(rows: list[tuple[int, datetime, str, int, str]]) -> str:
    if not rows:
        return "No feedback in this window."
    by_segment: dict[str, list[int]] = defaultdict(list)
    for _, _, seg, rating, _ in rows:
        by_segment[seg].append(rating)
    lines = ["Average rating by segment (1 to 5, n = answers in this window):"]
    for seg in SEGMENTS:
        if seg in by_segment:
            r = by_segment[seg]
            lines.append(f"  {seg}: {sum(r) / len(r):.1f} (n={len(r)})")
    lines.append("")
    for fid, at, seg, rating, body in rows:
        lines.append(f"#{fid}  {at.astimezone(UTC):%Y-%m-%d %H:%M} UTC  {seg}  rating {rating}/5")
        if body:
            lines.extend(f"    {ln}" for ln in body.splitlines() or [body])
    return "\n".join(lines)


def beta_feedback_cmd(
    since: Annotated[
        datetime | None, typer.Option(formats=["%Y-%m-%d"], help="Only feedback from this day on.")
    ] = None,
    segment: Annotated[Segment | None, typer.Option(help="Only this segment.")] = None,
    limit: Annotated[
        int, typer.Option(min=1, max=5000, help="Newest first, at most this many.")
    ] = 200,
) -> None:
    """Print what beta members wrote in the app (stored without their identity)."""
    with _connect() as conn:
        rows = read_feedback(
            conn, since.date() if since else None, segment.value if segment else None, limit
        )
    typer.echo(render_feedback(rows))


# --- the report by segment ---------------------------------------------------------------------


def segment_metrics(conn, since: date | None = None) -> dict[str, Any]:
    """Rejection rate and paste-to-results per segment over the window, plus the membership
    counts. Same definitions as ``cli_seo.beta_metrics``, restricted to events whose signed-in
    user is a current beta member (``events.user_id`` joined to ``beta_members``)."""
    window = "AND e.created_at >= %(since)s" if since else ""
    params = {"since": since}
    shown = {
        (seg, lvl): (int(n), int(users))
        for seg, lvl, n, users in conn.execute(
            "SELECT m.segment, e.props->>'flex_level',"
            " coalesce(sum((e.props->>'count')::integer), 0), count(DISTINCT e.user_id)"
            " FROM events e JOIN beta_members m ON m.user_id = e.user_id"
            f" WHERE e.name = 'substitutions_shown' {window} GROUP BY 1, 2",
            params,
        ).fetchall()
    }
    rejected = {
        (seg, lvl): int(n)
        for seg, lvl, n in conn.execute(
            "SELECT m.segment, e.props->>'flex_level', count(*)"
            " FROM events e JOIN beta_members m ON m.user_id = e.user_id"
            f" WHERE e.name = 'substitution_verdict' AND e.props->>'verdict' = 'not_good' {window}"
            " GROUP BY 1, 2",
            params,
        ).fetchall()
    }
    paste = {
        seg: {
            "results": int(n),
            "users": int(users),
            "median_ms": None if med is None else float(med),
            "p90_ms": None if p90 is None else float(p90),
        }  # fmt: skip
        for seg, n, users, med, p90 in conn.execute(
            "SELECT m.segment, count(*), count(DISTINCT e.user_id),"
            " percentile_cont(0.5) WITHIN GROUP (ORDER BY (e.props->>'duration_ms')::numeric),"
            " percentile_cont(0.9) WITHIN GROUP (ORDER BY (e.props->>'duration_ms')::numeric)"
            " FROM events e JOIN beta_members m ON m.user_id = e.user_id"
            f" WHERE e.name = 'results_shown' AND e.props ? 'duration_ms' {window} GROUP BY 1",
            params,
        ).fetchall()
    }
    active = {
        seg: int(n)
        for seg, n in conn.execute(
            "SELECT m.segment, count(DISTINCT e.user_id)"
            " FROM events e JOIN beta_members m ON m.user_id = e.user_id"
            f" WHERE e.name = 'app_opened' {window} GROUP BY 1",
            params,
        ).fetchall()
    }
    members = dict(conn.execute("SELECT segment, count(*) FROM beta_members GROUP BY 1").fetchall())
    places = {
        seg: (int(codes), int(pl))
        for seg, codes, pl in conn.execute(
            "SELECT segment, count(*), sum(max_uses) FROM beta_invites GROUP BY 1"
        ).fetchall()
    }
    out: dict[str, Any] = {}
    for seg in SEGMENTS:
        out[seg] = {
            "codes": places.get(seg, (0, 0))[0],
            "places": places.get(seg, (0, 0))[1],
            "joined": int(members.get(seg, 0)),
            "active": active.get(seg, 0),
            "rejection": {
                lvl: {
                    "shown": shown.get((seg, lvl), (0, 0))[0],
                    "users": shown.get((seg, lvl), (0, 0))[1],
                    "rejected": rejected.get((seg, lvl), 0),
                }
                for lvl in LEVELS
            },
            "paste_to_results": paste.get(
                seg, {"results": 0, "users": 0, "median_ms": None, "p90_ms": None}
            ),
        }
    return out


def render_segment_section(
    seg_metrics: dict[str, Any], thresholds: dict[str, Any] = BETA_THRESHOLDS
) -> str:
    min_shown, min_results = thresholds["min_shown"], thresholds["min_results"]
    lines = [
        "## By segment",
        "",
        "Only events from signed-in beta members count here (their user id joined to the segment of"
        " the invite code they used); signed-out visitors and people who left the beta are in the"
        " overall table above and in no segment. n is the sample size. A segment has no verdict of"
        " its own: the proposed thresholds apply to the overall rates, and a small n says nothing"
        " yet.",
        "",
        "### Who is in",
        "",
        "| Segment | Codes | Places | Joined | Active (opened the app) |",
        "|---|---|---|---|---|",
    ]
    for seg in SEGMENTS:
        m = seg_metrics[seg]
        lines.append(
            f"| {seg} ({SEGMENT_LABELS[seg]}) | {m['codes']} | {m['places']} | {m['joined']}"
            f" | {m['active']} |"
        )
    joined = sum(seg_metrics[s]["joined"] for s in SEGMENTS)
    lines += ["", f"Joined in total: {joined} (the plan asks for 20 to 50).", ""]

    lines += [
        "### Substitution rejection rate by segment",
        "",
        "| Segment | Level | Shown (n) | Rejected | Rate | Users | Sample |",
        "|---|---|---|---|---|---|---|",
    ]
    for seg in SEGMENTS:
        for lvl in LEVELS:
            r = seg_metrics[seg]["rejection"][lvl]
            if r["shown"] == 0:
                lines.append(f"| {seg} | {lvl} | 0 | {r['rejected']} | - | 0 | none |")
                continue
            rate = r["rejected"] / r["shown"]
            sample = "ok" if r["shown"] >= min_shown else f"small (<{min_shown})"
            lines.append(
                f"| {seg} | {lvl} | {r['shown']} | {r['rejected']} | {rate:.1%} | {r['users']}"
                f" | {sample} |"
            )
    lines += [
        "",
        "### Paste to results by segment",
        "",
        "| Segment | Results (n) | Users | Median | p90 | Sample |",
        "|---|---|---|---|---|---|",
    ]
    for seg in SEGMENTS:
        p = seg_metrics[seg]["paste_to_results"]
        if p["results"] == 0 or p["median_ms"] is None:
            lines.append(f"| {seg} | 0 | 0 | - | - | none |")
            continue
        sample = "ok" if p["results"] >= min_results else f"small (<{min_results})"
        lines.append(
            f"| {seg} | {p['results']} | {p['users']} | {p['median_ms'] / 1000:.1f} s"
            f" | {p['p90_ms'] / 1000:.1f} s | {sample} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_full_report(
    metrics: dict[str, Any], seg_metrics: dict[str, Any], since: date | None, today: date
) -> str:
    """The unchanged overall report followed by the by-segment section."""
    base = cli_seo.render_beta_report(metrics, since, today)
    return base.rstrip("\n") + "\n\n" + render_segment_section(seg_metrics)


def beta_report_cmd(
    since: Annotated[
        datetime | None, typer.Option(formats=["%Y-%m-%d"], help="Start of the window.")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Write the report here, else print.")] = None,
    fail_on_miss: Annotated[
        bool, typer.Option("--fail-on-miss", help="Exit 1 when the rejection-rate gate is not met.")
    ] = False,
) -> None:
    """The closed beta's rejection rate, paste-to-results time and return visits with verdicts,
    then the same by segment with sample sizes."""
    start = since.date() if since else None
    with _connect() as conn:
        metrics = cli_seo.beta_metrics(conn, start)
        seg_metrics = segment_metrics(conn, start)
    text = render_full_report(metrics, seg_metrics, start, datetime.now(UTC).date())
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        typer.echo(f"written {out}")
    else:
        typer.echo(text)
    gate = [r for r in cli_seo.beta_verdicts(metrics) if r[4]]
    if fail_on_miss and any(r[3] != "pass" for r in gate):
        raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Add the beta commands. ``beta-report`` replaces the one ``cli_seo`` registered (same
    options, same first sections) so there is a single command with the segment breakdown; this
    module is listed after ``cli_seo`` in ``cli.EXTENSIONS``."""
    app.registered_commands[:] = [
        c for c in app.registered_commands if (c.name or "") != "beta-report"
    ]
    app.command("beta-invite")(beta_invite_cmd)
    app.command("beta-feedback")(beta_feedback_cmd)
    app.command("beta-report")(beta_report_cmd)
