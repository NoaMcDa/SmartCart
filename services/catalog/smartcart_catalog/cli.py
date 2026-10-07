"""``smartcart-catalog`` command line (entry point declared in pyproject.toml).

* ``smartcart-catalog seed``                       taxonomy, product type rules, canonicals
* ``smartcart-catalog normalize [--chain ID]``     normalize items, report what did not parse
* ``smartcart-catalog extract [--extractor ...]``  attribute extraction for pending items
* ``smartcart-catalog cost-report``                tokens and estimated USD per model batch

Extending: other modules add commands to the same ``app`` through a ``register(app)`` function.
Every module named in ``EXTENSIONS`` is imported at the bottom of this file and its
``register(app: typer.Typer) -> None`` is called, e.g. in ``smartcart_catalog/cli_matching.py``::

    def register(app: typer.Typer) -> None:
        @app.command()
        def embed(...) -> None: ...

A module that does not exist yet is skipped; an import error inside an existing module is raised.
"""

from __future__ import annotations

import importlib
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from typing import Annotated, Any

import psycopg
import typer
from psycopg.rows import dict_row

from smartcart_catalog.settings import Settings, load_settings

app = typer.Typer(add_completion=False, no_args_is_help=True, help="SmartCart canonical catalog.")

EXTENSIONS: tuple[str, ...] = ("smartcart_catalog.cli_matching", "smartcart_catalog.cli_seo")


class ExtractorName(StrEnum):
    rule = "rule"
    claude = "claude"


# --- seams the tests replace ---------------------------------------------------------------------


@contextmanager
def open_connection(settings: Settings) -> Iterator[psycopg.Connection]:
    if not settings.database_url:
        raise typer.BadParameter("DATABASE_URL is not set")
    with psycopg.connect(settings.database_url) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        yield conn


def build_extractor(name: ExtractorName, settings: Settings) -> Any:
    from smartcart_catalog.seed import load_catalog

    catalog = load_catalog(settings.catalog_data_dir)
    if name is ExtractorName.rule:
        from smartcart_catalog.extract.rule import RuleExtractor

        return RuleExtractor(catalog)
    from smartcart_catalog.extract.claude import ClaudeExtractor

    key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
    return ClaudeExtractor(
        model=settings.extraction_model,
        max_tokens=settings.extraction_max_tokens,
        effort=settings.extraction_effort,
        poll_seconds=settings.extraction_poll_seconds,
        api_key=key,
        catalog=catalog,
    )


# --- commands ------------------------------------------------------------------------------------


@app.command()
def seed(
    check: Annotated[bool, typer.Option(help="Validate the files only, no database.")] = False,
) -> None:
    """Validate data/*.yaml and upsert taxonomy, product type rules and canonicals."""
    from smartcart_catalog.seed import SeedError, load_catalog, seed_all
    from smartcart_catalog.taxonomy import TaxonomyError

    settings = load_settings()
    try:
        catalog = load_catalog(settings.catalog_data_dir)
    except (SeedError, TaxonomyError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(
        f"files ok: {len(catalog.taxonomy)} taxonomy nodes, {len(catalog.rules)} product types,"
        f" {len(catalog.canonicals)} canonicals"
    )
    if check:
        return
    with open_connection(settings) as conn:
        with conn.transaction():
            report = seed_all(conn, catalog)
    typer.echo(f"taxonomy:   {report.taxonomy}")
    typer.echo(f"rules:      {report.rules}")
    typer.echo(f"canonicals: {report.canonicals}")


@app.command("normalize")
def normalize_cmd(
    chain: Annotated[str | None, typer.Option(help="Only this chain id.")] = None,
    show: Annotated[int, typer.Option(help="Print up to N items with issues.")] = 20,
) -> None:
    """Normalize items (sizes, multipacks, weighed goods) and report what did not parse.

    Read-only: normalization is a pure function, so consumers call it directly."""
    from smartcart_catalog.normalize import normalize_with_issues

    settings = load_settings()
    sources: Counter[str] = Counter()
    base_units: Counter[str] = Counter()
    total = multipacks = flagged = 0
    examples: list[str] = []
    with open_connection(settings) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, chain_id, item_code, raw_name, quantity, unit, is_weighed FROM items"
            " WHERE (%(chain)s::text IS NULL OR chain_id = %(chain)s::text) ORDER BY id",
            {"chain": chain},
        )
        for row in cur:
            total += 1
            result = normalize_with_issues(row, item_id=row["id"])
            sources[result.source] += 1
            base_units[result.item.base_unit or "none"] += 1
            multipacks += result.item.pack_count > 1
            if result.issues:
                flagged += 1
                if len(examples) < show:
                    examples.append(f"  {row['id']} {row['raw_name']!r}: {'; '.join(result.issues)}")
    typer.echo(f"{total} items" + (f" in chain {chain}" if chain else ""))
    typer.echo(f"size from: {dict(sources)}")
    typer.echo(f"base unit: {dict(base_units)}")
    typer.echo(f"multipacks: {multipacks}; with issues: {flagged}; unparseable: {sources['none']}")
    for line in examples:
        typer.echo(line)


@app.command()
def extract(
    extractor: Annotated[
        ExtractorName | None, typer.Option(help="rule or claude (default: $EXTRACTOR).")
    ] = None,
    chain: Annotated[str | None, typer.Option(help="Only this chain id.")] = None,
    limit: Annotated[int | None, typer.Option(help="Stop after N items.")] = None,
    batch_size: Annotated[int | None, typer.Option(help="Items per batch.")] = None,
) -> None:
    """Extract attributes for items without them (or marked retry). Re-running skips done items."""
    from smartcart_catalog.extract.queue import count_pending, run_extraction

    settings = load_settings()
    name = extractor or ExtractorName(settings.extractor)
    if name is ExtractorName.claude and settings.anthropic_api_key is None:
        typer.echo("EXTRACTOR=claude needs ANTHROPIC_API_KEY", err=True)
        raise typer.Exit(2)
    impl = build_extractor(name, settings)
    with open_connection(settings) as conn:
        typer.echo(f"{count_pending(conn, chain)} items pending")
        run = run_extraction(
            conn, impl,
            batch_size=batch_size or settings.extraction_batch_size,
            limit=limit, chain=chain,
            max_attempts=settings.extraction_max_attempts,
            commit=True,
        )
    typer.echo(
        f"{run.items} items: {run.ok} ok, {run.retry} retry, {run.failed} failed"
        f" ({run.extractor}{', ' + run.model if run.model else ''})"
    )
    for b in run.batches:
        typer.echo(
            f"  batch {b['batch_id']}: {b['input_tokens']} in / {b['output_tokens']} out tokens,"
            f" estimated ${b['estimated_usd']} (estimate)"
        )


@app.command("cost-report")
def cost_report_cmd(
    runs: Annotated[int, typer.Option(help="How many recent runs.")] = 20,
) -> None:
    """Tokens in/out per model batch and estimated USD at batch rates (an estimate, not a bill)."""
    from decimal import Decimal

    from smartcart_catalog.extract.queue import cost_report

    settings = load_settings()
    with open_connection(settings) as conn:
        lines = cost_report(conn, runs=runs)
    if not lines:
        typer.echo("no model extraction batches recorded")
        return
    typer.echo("run  batch                          model              requests  in_tok  out_tok"
               "  cache_rd  est_usd")
    total_in = total_out = 0
    total_usd = Decimal(0)
    for ln in lines:
        typer.echo(
            f"{ln.run_id:<4} {ln.batch_id:<30} {ln.model or '-':<18} {ln.requests:>8}"
            f" {ln.input_tokens:>7} {ln.output_tokens:>8} {ln.cache_read_input_tokens:>9}"
            f"  {ln.estimated_usd or '-'}"
        )
        total_in += ln.input_tokens
        total_out += ln.output_tokens
        total_usd += Decimal(ln.estimated_usd or 0)
    typer.echo(
        f"total: {total_in} input tokens, {total_out} output tokens,"
        f" ${total_usd} estimated at batch rates ($1 in / $5 out per MTok for"
        " claude-sonnet-5-5; estimate)"
    )


# --- extensions ------------------------------------------------------------------------------------


def _load_extensions() -> None:
    for module_name in EXTENSIONS:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise
        module.register(app)


_load_extensions()
