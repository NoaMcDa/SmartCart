"""Arabic matching command for the ``smartcart-catalog`` CLI (issue #73).

``cli.py`` (the catalog CLI app) calls ``register(app)`` once ``smartcart_catalog.cli_arabic`` is
listed in its ``EXTENSIONS`` tuple. Until then, or standalone::

    uv run python -m smartcart_catalog.cli_arabic evaluate-ar --fail-below 0.98

The database is ``$DATABASE_URL`` (migrated; the command seeds the canonicals, with their
``names_ar``, unless ``--no-seed``). The query embedder of the API is ``$API_QUERY_EMBEDDER``
(``hash`` when unset); Arabic retrieval is lexical, the vector retriever only suggests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer


def _connect():
    from smartcart_ingest import db as dbmod

    conn = dbmod.connect()
    conn.execute("SET TIME ZONE 'UTC'")
    return conn


def evaluate_ar(
    fail_below: Annotated[
        float | None,
        typer.Option(help="Exit 1 if any_brand precision is below this (e.g. 0.98)."),
    ] = None,
    queries: Annotated[Path | None, typer.Option(help="Arabic query set (YAML).")] = None,
    floor: Annotated[
        float | None,
        typer.Option(help="Confidence at which a row counts as served (default: the API's 0.75)."),
    ] = None,
    no_seed: Annotated[bool, typer.Option("--no-seed", help="Use the canonicals as loaded.")] = False,
    json_out: Annotated[bool, typer.Option("--json", help="Print the metrics as JSON.")] = False,
    show_errors: Annotated[int, typer.Option(help="Print up to N wrong answers.")] = 30,
) -> None:
    """Precision and recall of Arabic list lines resolved by /parse-list (synthetic set)."""
    from smartcart_catalog.evaluate_ar import (
        DEFAULT_QUERIES,
        format_report,
        load_lines,
        passes,
        run_evaluation,
    )

    lines = load_lines(queries or DEFAULT_QUERIES)
    with _connect() as conn:
        report = run_evaluation(conn, lines, seed=not no_seed, floor=floor)
        conn.commit()
    if json_out:
        typer.echo(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    else:
        typer.echo(format_report(report, show_errors))
        typer.echo(f"set size: {len(lines)} lines (synthetic)")
    if fail_below is not None and not passes(report, fail_below):
        got = report.precision.get("any_brand")
        typer.echo(
            f"FAIL: any_brand precision {got if got is not None else 'n/a'} < {fail_below}",
            err=True,
        )
        raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Add the Arabic evaluation to the catalog CLI."""
    app.command("evaluate-ar")(evaluate_ar)


app = typer.Typer(help="SmartCart Arabic matching.", no_args_is_help=True)


@app.callback()
def _main() -> None:
    """Keeps ``evaluate-ar`` a named command when this module runs on its own."""


register(app)

if __name__ == "__main__":
    app()
