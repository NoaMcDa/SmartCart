"""``smartcart-ingest`` command line (entry point declared in pyproject.toml).

Commands match the systemd units in ``infra/vps``:

* ``smartcart-ingest migrate``                          apply pending SQL migrations
* ``smartcart-ingest run --mode full [--chain ID ...]``  daily full sync (06:00 and 08:30)
* ``smartcart-ingest run --mode delta [--chain ID ...]`` hourly deltas for the main chains
* ``smartcart-ingest status``                           file_tracking counts by chain and status

``run`` exits 1 when a chain could not run (portal down after backoff, no adapter) or a file
failed to parse or load; quarantines are not errors. Alerts carry the details either way.
"""

from __future__ import annotations

import importlib
import json
import logging
import pkgutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from typing import Annotated

import psycopg
import structlog
import typer

from smartcart_ingest import db as dbmod
from smartcart_ingest import tracking
from smartcart_ingest.alerts import build_alerter
from smartcart_ingest.download import Fetcher, ScraperFetcher, quiet_upstream_loggers
from smartcart_ingest.rawstore import RawStore, rawstore_from_settings
from smartcart_ingest.scheduler import D13_CHAINS, RunReport, Scheduler
from smartcart_ingest.settings import Settings, load_settings

app = typer.Typer(add_completion=False, no_args_is_help=True, help="SmartCart ingestion worker.")
log = structlog.get_logger("smartcart_ingest.cli")


class Mode(StrEnum):
    full = "full"
    delta = "delta"


# --- seams the tests replace -------------------------------------------------------------------


@contextmanager
def open_connection(settings: Settings) -> Iterator[psycopg.Connection]:
    """Autocommit, so each tracking update is durable on its own and every load is exactly one
    transaction (``conn.transaction()``)."""
    with dbmod.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("SET TIME ZONE 'UTC'")
        yield conn


def build_fetcher(settings: Settings) -> Fetcher:
    return ScraperFetcher()


def build_rawstore(settings: Settings) -> RawStore:
    return rawstore_from_settings(settings)


def register_adapters() -> list[str]:
    """Import every module under ``smartcart_ingest.adapters`` so the chains register."""
    import smartcart_ingest.adapters as pkg

    names = []
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name != "base":
            importlib.import_module(f"{pkg.__name__}.{mod.name}")
            names.append(mod.name)
    return names


# --- commands ----------------------------------------------------------------------------------


def _stderr_logger(*args: object) -> structlog.PrintLogger:
    # Looked up on every call, so a redirected sys.stderr (tests, CliRunner) is honoured.
    return structlog.PrintLogger(file=sys.stderr)


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    quiet_upstream_loggers(level)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.KeyValueRenderer(key_order=["timestamp", "level", "event"]),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=_stderr_logger,
        cache_logger_on_first_use=False,
    )


@app.command()
def migrate() -> None:
    """Apply pending migrations from supabase/migrations."""
    settings = load_settings()
    with dbmod.connect(settings.database_url, autocommit=True) as conn:
        applied = dbmod.migrate(conn)
    if applied:
        for name in applied:
            typer.echo(f"applied {name}")
    else:
        typer.echo("no pending migrations")


def _print_report(report: RunReport) -> None:
    for c in report.chains:
        typer.echo(json.dumps({"mode": report.mode, **c.as_dict()}, ensure_ascii=False))


@app.command()
def run(
    mode: Annotated[
        Mode,
        typer.Option("--mode", help="full: Stores, PriceFull, PromoFull. delta: Price, Promo."),
    ],
    chain: Annotated[
        list[str] | None,
        typer.Option(
            "--chain",
            help="Chain id, repeatable. Default: the D13 chains (full) or the due main chains"
            " (delta).",
        ),
    ] = None,
) -> None:
    """Download, gate and load transparency files."""
    settings = load_settings()
    register_adapters()
    from smartcart_ingest.adapters.base import REGISTRY

    fetcher = build_fetcher(settings)
    rawstore = build_rawstore(settings)
    alerter = build_alerter(settings.alert_webhook_url)
    chains = list(chain) if chain else None
    try:
        with open_connection(settings) as conn:
            sched = Scheduler(conn, fetcher, rawstore, alerter, settings)
            if chains is None:
                wanted = (
                    [c.chain_id for c in D13_CHAINS]
                    if mode is Mode.full
                    else sched.due_delta_chains()
                )
                chains = [c for c in wanted if c in REGISTRY]
                missing = [c for c in wanted if c not in REGISTRY]
                if missing:
                    log.warning("no adapter registered yet, skipping", chains=missing)
            report = sched.run_full(chains) if mode is Mode.full else sched.run_delta(chains)
    finally:
        close = getattr(fetcher, "close", None)
        if callable(close):
            close()
    _print_report(report)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def status() -> None:
    """Print file_tracking counts by chain and status, and quarantined files per chain."""
    settings = load_settings()
    with open_connection(settings) as conn:
        counts = tracking.status_counts(conn)
        quarantined = tracking.quarantine_counts(conn)
    if not counts:
        typer.echo("no files tracked")
        return
    typer.echo(f"{'chain':<16} {'status':<12} {'files':>7}")
    for chain_id, st, n in counts:
        typer.echo(f"{chain_id:<16} {st:<12} {n:>7}")
    if quarantined:
        typer.echo("")
        typer.echo(f"{'chain':<16} {'quarantined':>11} {'last 24h':>9}")
        for chain_id, total, recent in quarantined:
            typer.echo(f"{chain_id:<16} {total:>11} {recent:>9}")


if __name__ == "__main__":  # pragma: no cover
    app()
