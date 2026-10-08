"""Promo cycle commands for the ``smartcart-catalog`` CLI (issue #69). See docs/promo-cycles.md.

* ``promo-cycles CANONICAL``   the per-chain cycle table for one canonical (id or slug)
* ``promo-backtest``           hit and false-alarm rates of the baseline, on the database's
                               promo history or (``--synthetic``) on generated history

The database is ``$DATABASE_URL`` (``cli.open_connection``).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

import typer

from smartcart_catalog import promo_cycles as pc


def _canonical_id(conn, ref: str) -> tuple[int, str]:
    row = conn.execute(
        "SELECT id, display_name_he FROM canonical_products WHERE id::text = %s OR slug = %s",
        (ref, ref),
    ).fetchone()
    if row is None:
        raise typer.BadParameter(f"no canonical product {ref!r}")
    return row[0], row[1]


def _include_clubs(clubs: list[str]) -> pc.IncludeClub | None:
    if not clubs:
        return None
    marked = {" ".join(c.split()).casefold() for c in clubs}

    def include(club_name, chain_name, chain_clubs) -> bool:
        return " ".join((club_name or "").split()).casefold() in marked

    return include


def promo_cycles_cmd(
    canonical: Annotated[str, typer.Argument(help="Canonical product id or slug.")],
    club: Annotated[list[str], typer.Option(help="A club the user marked (repeat). Club-only promos count only for these, by exact name.")] = [],  # noqa: B006
    as_of: Annotated[str | None, typer.Option(help="Today, YYYY-MM-DD (default: today, UTC).")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Print JSON instead of a table.")] = False,
) -> None:
    """Print the promo cycle estimate per chain for one canonical product."""
    from smartcart_catalog import cli

    today = date.fromisoformat(as_of) if as_of else datetime.now(UTC).date()
    with cli.open_connection(cli.load_settings()) as conn:
        cid, name = _canonical_id(conn, canonical)
        rows = pc.promo_cycles(conn, cid, today, _include_clubs(club))
    if as_json:
        typer.echo(json.dumps(
            {"canonical_id": cid, "as_of": today.isoformat(), "chains": [
                {"chain_id": r.chain_id, "chain_name": r.chain_name, "windows": len(r.windows),
                 **{k: (v.isoformat() if isinstance(v, date) else v)
                    for k, v in r.estimate.__dict__.items()}}
                for r in rows
            ]}, ensure_ascii=False, indent=2,
        ))
        return
    typer.echo(f"{name} (canonical {cid}), as of {today.isoformat()}")
    if not rows:
        typer.echo("no promo history")
        return
    head = ("chain", "windows", "cycles", "median gap", "confidence", "last ends", "next from", "next to", "advice")
    table = [head] + [
        (
            f"{r.chain_name} ({r.chain_id})", str(len(r.windows)), str(r.estimate.cycles_seen),
            "-" if r.estimate.median_gap_days is None else f"{r.estimate.median_gap_days:g} d",
            f"{r.estimate.confidence:.2f}",
            *("-" if d is None else d.isoformat() for d in (r.estimate.last_end, r.estimate.next_from, r.estimate.next_to)),
            r.estimate.advice,
        )
        for r in rows
    ]
    widths = [max(len(row[i]) for row in table) for i in range(len(head))]
    for row in table:
        typer.echo("  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip())
    typer.echo(
        f"gate: at least {pc.MIN_CYCLES} cycles and confidence {pc.MIN_CONFIDENCE} (estimates);"
        " a prediction is a hint, never a promise"
    )


def synthetic_series(start: date, end: date) -> dict[str, list[list[pc.Window]]]:
    """The fixed synthetic mix the docs quote, 20 series of each kind."""
    return {
        "regular, 28 to 49 days, jitter 0 to 2": [
            pc.synthetic_history(s, start, end, 28 + s % 4 * 7, jitter_days=s % 3) for s in range(20)
        ],
        "42 days, jitter 5, 10-day promos": [
            pc.synthetic_history(100 + s, start, end, 42, jitter_days=5, duration_days=10) for s in range(20)
        ],
        "35 days, jitter 3, a quarter of cycles skipped": [
            pc.synthetic_history(200 + s, start, end, 35, jitter_days=3, skip_prob=0.25) for s in range(20)
        ],
        "irregular, gaps 10 to 90 days": [
            pc.irregular_history(300 + s, start, end, 10, 90) for s in range(20)
        ],
    }


def promo_backtest_cmd(
    synthetic: Annotated[bool, typer.Option(help="Generated history instead of the database.")] = False,
    min_windows: Annotated[int, typer.Option(help="Windows of history before the first prediction.")] = pc.MIN_CYCLES + 1,
    days: Annotated[int, typer.Option(help="History length in days.")] = 540,
) -> None:
    """Walk-forward backtest: hit rate and false-alarm rate of the predictions that pass the gate."""
    end = datetime.now(UTC).date()
    start = end - timedelta(days=days)
    by_kind: dict[str, dict[str, object]] = {}
    if synthetic:
        kinds = synthetic_series(start, end)
        series = [s for group in kinds.values() for s in group]
        by_kind = {k: pc.backtest(v, min_windows=min_windows).as_dict() for k, v in kinds.items()}
        source = "synthetic (smartcart-catalog promo-backtest --synthetic)"
    else:
        from smartcart_catalog import cli

        with cli.open_connection(cli.load_settings()) as conn:
            pairs = conn.execute(
                "SELECT DISTINCT ic.canonical_id FROM promo_items AS pi"
                " JOIN item_canonical AS ic ON ic.item_id = pi.item_id"
                " WHERE ic.flex_level IN ('exact', 'any_brand')"
            ).fetchall()
            series = [
                list(c.windows)
                for (cid,) in pairs
                for c in pc.promo_cycles(conn, cid, end)
            ]
        source = "database"
    result = pc.backtest(series, min_windows=min_windows)
    out: dict[str, object] = {"source": source, "series": len(series), "history_days": days,
                              **result.as_dict()}
    if by_kind:
        out["by_kind"] = by_kind
    typer.echo(json.dumps(out, indent=2))


def register(app: typer.Typer) -> None:
    app.command("promo-cycles")(promo_cycles_cmd)
    app.command("promo-backtest")(promo_backtest_cmd)
